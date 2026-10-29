# -*- coding: utf-8 -*-
"""G.AI 2API 本地网关 (R1)

对外:
  GET  /                     demo 页面
  GET  /health               健康检查
  GET  /v1/models            OpenAI 兼容模型列表
  POST /v1/chat/completions  OpenAI 兼容（支持 stream）
  POST /api/chat             demo 用简版接口（返回 SSE 事件流）
  GET  /api/models           模型目录（含中文名/能力标签）
"""
from __future__ import annotations

import asyncio
import itertools
import json
import os
import sys
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator

import httpx
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

sys.path.insert(0, str(Path(__file__).parent))
from gai_proto import BUNDLE, headers as build_headers, seal  # noqa: E402

UPSTREAM = os.getenv("GAI_UPSTREAM", "https://api.chatgai.fun")
PORT = int(os.getenv("GAI_PORT", "8970"))
MAX_CONN = int(os.getenv("GAI_MAX_CONN", "6"))
PROXY = os.getenv("GAI_PROXY", "<HTTP_PROXY>")
PROXY_LIST_FILE = os.getenv("GAI_PROXY_LIST", "")   # 每行一个 http://host:port，按 IP 轮换额度
TIMEOUT = float(os.getenv("GAI_TIMEOUT", "180"))

DEFAULT_MODEL = os.getenv("GAI_MODEL", "GPT:4.1-mini")

@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    for c in _clients.values():
        await c.aclose()
    _clients.clear()


app = FastAPI(title="G.AI 2API Gateway", version="1.0.0", lifespan=lifespan)

_limits = httpx.Limits(max_connections=MAX_CONN, max_keepalive_connections=MAX_CONN)
_clients: dict[str, httpx.AsyncClient] = {}
_sem = asyncio.Semaphore(MAX_CONN)

PROXIES: list[str] = []
if PROXY_LIST_FILE and Path(PROXY_LIST_FILE).exists():
    PROXIES = [ln.strip() for ln in Path(PROXY_LIST_FILE).read_text(encoding="utf-8").splitlines()
               if ln.strip() and not ln.startswith("#")]
_rr = itertools.count()


def pick_proxy() -> str:
    """IP 池轮换：额度是按出口 IP 计的，每换一个出口就是一份新额度"""
    if PROXIES:
        return PROXIES[next(_rr) % len(PROXIES)]
    return PROXY


def client(proxy: str | None = None) -> httpx.AsyncClient:
    """按代理复用连接池（同一出口 IP 复用，不同出口各自独立）"""
    key = proxy if proxy is not None else PROXY
    if key not in _clients:
        _clients[key] = httpx.AsyncClient(
            timeout=httpx.Timeout(TIMEOUT, connect=30.0),
            limits=_limits,
            proxy=key or None,
            headers={"accept-encoding": "identity"},
        )
    return _clients[key]


# ---------------------------------------------------------------- 上游调用
async def upstream_stream(path: str, params: dict[str, Any]) -> AsyncIterator[dict]:
    """向加密通道发起请求并逐行产出解析后的 JSON 事件"""
    body = seal(params)
    hdr = build_headers()
    last_err: Exception | None = None
    for attempt in range(3):
        try:
            proxy = pick_proxy()
            async with _sem:
                cli = client(proxy)
                req = cli.build_request("POST", UPSTREAM + path,
                                        content=json.dumps(body, ensure_ascii=False),
                                        headers=hdr)
                resp = await cli.send(req, stream=True)
                if resp.status_code != 200:
                    text = (await resp.aread()).decode("utf-8", "replace")
                    await resp.aclose()
                    yield {"_error": f"upstream {resp.status_code}: {text[:300]}"}
                    return
                pending = b""
                async for chunk in resp.aiter_bytes():
                    pending += chunk
                    while b"\n" in pending:
                        line, pending = pending.split(b"\n", 1)
                        line = line.strip()
                        if not line:
                            continue
                        text = line.decode("utf-8", "replace")
                        if text.startswith("data:"):
                            payload = text[5:].strip()
                            if payload == "[DONE]":
                                await resp.aclose()
                                return
                            try:
                                yield json.loads(payload)
                            except json.JSONDecodeError:
                                continue
                await resp.aclose()
                return
        except (httpx.ConnectError, httpx.ReadError, httpx.RemoteProtocolError, httpx.ConnectTimeout) as exc:
            last_err = exc
            await asyncio.sleep(0.4 * (attempt + 1))
            continue
    yield {"_error": f"network: {type(last_err).__name__}: {last_err}"}


async def upstream_json(path: str, params: dict[str, Any] | None = None, method: str = "GET") -> dict:
    hdr = build_headers()
    for attempt in range(3):
        try:
            cli = client(pick_proxy())
            if method == "GET":
                r = await cli.get(UPSTREAM + path, params=params or {}, headers=hdr)
            else:
                r = await cli.post(UPSTREAM + path, json=params or {}, headers=hdr)
            return r.json()
        except Exception:  # noqa: BLE001
            await asyncio.sleep(0.4 * (attempt + 1))
    return {"code": -1, "msg": "upstream unreachable"}


async def upstream_plain(path: str, params: dict[str, Any]) -> dict:
    """明文 REST（用于 /common/img/create 等不加密端点）"""
    hdr = build_headers()
    for attempt in range(3):
        try:
            r = await client(pick_proxy()).post(UPSTREAM + path, json=params, headers=hdr)
            return r.json()
        except Exception:  # noqa: BLE001
            await asyncio.sleep(0.4 * (attempt + 1))
    return {"code": -1, "msg": "upstream unreachable"}


async def complete(question: str, ai_version: str, conversation_id: str | None = None,
                   need_search: bool = False, language: str = "en") -> tuple[str, dict]:
    """非流式聚合"""
    cid = conversation_id or str(uuid.uuid4())
    parts: list[str] = []
    meta: dict[str, Any] = {"conversation_id": cid, "message_id": "", "chatNum": 0, "imgNum": 0}
    async for ev in upstream_stream("/common/sse/chat", {
        "question": question,
        "conversationId": cid,
        "type": "1",
        "needSearch": need_search,
        "language": language,
        "aiVersion": ai_version,
    }):
        if "_error" in ev:
            meta["error"] = ev["_error"]
            break
        d = ev.get("data") or {}
        if d.get("answer"):
            parts.append(d["answer"])
        if d.get("message_id"):
            meta["message_id"] = d["message_id"]
        if d.get("conversation_id"):
            meta["conversation_id"] = d["conversation_id"]
        meta["chatNum"] = ev.get("chatNum", meta["chatNum"])
        meta["imgNum"] = ev.get("imgNum", meta["imgNum"])
        if ev.get("code") not in (0, None) and not parts:
            meta["error"] = ev.get("message") or str(ev)
    return "".join(parts), meta


# ---------------------------------------------------------------- 工具函数
def flatten_messages(messages: list[dict]) -> tuple[str, str | None]:
    """把 OpenAI messages 摊平成单条 question（上游只接受单条 prompt）"""
    system = None
    lines: list[str] = []
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content")
        if isinstance(content, list):  # 多模态分段，取文本段
            content = " ".join(p.get("text", "") for p in content if isinstance(p, dict))
        content = (content or "").strip()
        if not content:
            continue
        if role == "system":
            system = content
        elif role == "assistant":
            lines.append(f"Assistant: {content}")
        else:
            lines.append(f"User: {content}")
    if len(lines) <= 1:
        q = lines[0][6:] if lines and lines[0].startswith("User: ") else (lines[0] if lines else "")
    else:
        q = "\n\n".join(lines)
    if system:
        q = f"[System instruction] {system}\n\n{q}"
    return q, system


def resolve_model(model: str | None) -> str:
    if not model:
        return DEFAULT_MODEL
    if ":" in model:
        return model
    alias = {
        "gpt-4.1-mini": "GPT:4.1-mini",
        "gpt-6-luna": "GPT:gpt-6-luna",
        "gpt-5.6-luna": "GPT:gpt-5.6-luna",
        "gpt-6-sol": "GPT:gpt-6-sol",
        "gemini-3-flash-preview": "GEMINI:gemini-3-flash-preview",
        "gemini-3-flash": "GEMINI:gemini-3-flash-preview",
        "gpt-4.1": "BOLATU:gpt-4.1",
    }
    return alias.get(model, model)


def est_tokens(text: str) -> int:
    return max(1, len(text) // 4)


# ---------------------------------------------------------------- 上游错误分类
ERR_PATTERNS = (
    ("quota", 429, ("free usage limit",)),
    ("vip", 403, ("upgrade to vip",)),
    ("offline", 503, ("model is offline", "current model is offline")),
    ("sign", 502, ("signature verification failed", "签名失败")),
    ("prompt_too_long", 400, ("cannot exceed",)),
)


def classify(text: str) -> tuple[str, int] | None:
    low = (text or "").lower()
    for kind, status, needles in ERR_PATTERNS:
        if any(n in low for n in needles):
            return kind, status
    return None


def openai_error(kind: str, status: int, message: str) -> JSONResponse:
    return JSONResponse({"error": {"message": message, "type": kind, "code": status}}, status_code=status)


# ---------------------------------------------------------------- 路由
@app.get("/health")
async def health():
    return {"ok": True, "upstream": UPSTREAM, "max_conn": MAX_CONN, "model": DEFAULT_MODEL,
            "proxy_pool": len(PROXIES) if PROXIES else 1}


@app.get("/api/models")
async def api_models():
    data = await upstream_json("/model/modelConfig", {"language": "en"})
    out = []
    for m in (data.get("data") or {}).get("modelList", []):
        out.append({"id": m.get("aiVersion"), "name": m.get("modeName"),
                    "vendor": m.get("modelType"), "apiType": m.get("apiType"),
                    "vip": m.get("vipStatus"), "search": m.get("enableSearch")})
    return {"code": 0, "data": out}


@app.get("/v1/models")
async def v1_models():
    data = await upstream_json("/model/modelConfig", {"language": "en"})
    rows = (data.get("data") or {}).get("modelList", [])
    return {"object": "list",
            "data": [{"id": m.get("aiVersion"), "object": "model", "created": 0,
                      "owned_by": m.get("modelType", "gai")} for m in rows]}


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    body = await request.json()
    messages = body.get("messages") or []
    stream = bool(body.get("stream"))
    model = resolve_model(body.get("model"))
    question, _ = flatten_messages(messages)
    if not question:
        return JSONResponse({"error": {"message": "empty messages"}}, status_code=400)

    cid = body.get("conversation_id") or body.get("user") or str(uuid.uuid4())
    created = int(time.time())
    rid = "chatcmpl-" + uuid.uuid4().hex[:24]

    if not stream:
        text, meta = await complete(question, model, cid)
        gate = classify(text) if text else None
        if gate and (meta.get("error") or gate[0] in ("quota", "vip", "offline", "prompt_too_long")):
            return openai_error(gate[0], gate[1], text.strip())
        if meta.get("error") and not text:
            return openai_error("upstream", 502, meta["error"])
        return {
            "id": rid, "object": "chat.completion", "created": created, "model": model,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": text},
                         "finish_reason": "stop"}],
            "usage": {"prompt_tokens": est_tokens(question), "completion_tokens": est_tokens(text),
                      "total_tokens": est_tokens(question) + est_tokens(text),
                      "_estimated": True},
            "x_gai": meta,
        }

    async def gen() -> AsyncIterator[bytes]:
        yield ("data: " + json.dumps({
            "id": rid, "object": "chat.completion.chunk", "created": created, "model": model,
            "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}]},
            ensure_ascii=False) + "\n\n").encode()
        async for ev in upstream_stream("/common/sse/chat", {
            "question": question, "conversationId": cid, "type": "1",
            "needSearch": False, "language": "en", "aiVersion": model,
        }):
            if "_error" in ev:
                yield ("data: " + json.dumps({"error": {"message": ev["_error"]}}) + "\n\n").encode()
                break
            d = ev.get("data") or {}
            delta = d.get("answer")
            if delta:
                gate = classify(delta)
                if gate:
                    yield ("data: " + json.dumps({
                        "error": {"message": delta.strip(), "type": gate[0], "code": gate[1]}},
                        ensure_ascii=False) + "\n\n").encode()
                    break
                yield ("data: " + json.dumps({
                    "id": rid, "object": "chat.completion.chunk", "created": created, "model": model,
                    "choices": [{"index": 0, "delta": {"content": delta}, "finish_reason": None}]},
                    ensure_ascii=False) + "\n\n").encode()
        yield ("data: " + json.dumps({
            "id": rid, "object": "chat.completion.chunk", "created": created, "model": model,
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}) + "\n\n").encode()
        yield b"data: [DONE]\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/chat")
async def api_chat(request: Request):
    """demo 用：直接透传上游事件（原始字段 + 耗时）"""
    body = await request.json()
    question = (body.get("question") or "").strip()
    if not question:
        return JSONResponse({"error": "question required"}, status_code=400)
    model = resolve_model(body.get("model"))
    cid = body.get("conversationId") or str(uuid.uuid4())
    need_search = bool(body.get("needSearch"))

    async def gen() -> AsyncIterator[bytes]:
        t0 = time.time()
        async for ev in upstream_stream("/common/sse/chat", {
            "question": question, "conversationId": cid, "type": "1",
            "needSearch": need_search, "language": body.get("language", "en"),
            "aiVersion": model,
        }):
            ev["_t"] = round((time.time() - t0) * 1000)
            yield ("data: " + json.dumps(ev, ensure_ascii=False) + "\n\n").encode()
        yield b"data: [DONE]\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/image")
async def api_image(request: Request):
    """文生图同步通道 /common/img/create"""
    body = await request.json()
    prompt = (body.get("prompt") or "").strip()
    if not prompt:
        return JSONResponse({"error": "prompt required"}, status_code=400)
    res = await upstream_plain("/common/img/create", {
        "botId": body.get("botId", ""),
        "prompt": prompt,
        "model": body.get("model", "GEMINI:nano-banana"),
        "style": body.get("style", "natural"),
        "mac": uuid.uuid4().hex[:16],
    })
    return res


@app.get("/", response_class=HTMLResponse)
async def index():
    return (Path(__file__).parent / "demo.html").read_text(encoding="utf-8")


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")
