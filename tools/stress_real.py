# -*- coding: utf-8 -*-
"""R12: 真实生成（非额度拒绝路径）的并行实测 —— 首字延迟 / 总耗时 / 完整性"""
import asyncio
import json
import statistics
import sys
import time

import aiohttp

sys.stdout.reconfigure(encoding="utf-8")

GATEWAY = "http://127.0.0.1:8970"
PROMPTS = ["用一句话介绍你自己", "3 + 4 等于几，只回答数字", "写一句 8 字的广告语"]


async def one(s: aiohttp.ClientSession, q: str) -> dict:
    t0 = time.perf_counter()
    ttft = None
    text = []
    body = {"model": "GPT:4.1-mini", "stream": True,
            "messages": [{"role": "user", "content": q}]}
    try:
        async with s.post(GATEWAY + "/v1/chat/completions", json=body,
                          timeout=aiohttp.ClientTimeout(total=180)) as r:
            async for raw in r.content:
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                p = line[5:].strip()
                if p == "[DONE]":
                    break
                try:
                    ev = json.loads(p)
                except json.JSONDecodeError:
                    continue
                if "error" in ev:
                    return {"err": ev["error"].get("message", "")[:60], "ms": (time.perf_counter() - t0) * 1000}
                ch = (ev.get("choices") or [{}])[0].get("delta", {}).get("content")
                if ch:
                    if ttft is None:
                        ttft = (time.perf_counter() - t0) * 1000
                    text.append(ch)
    except Exception as e:  # noqa: BLE001
        return {"err": f"{type(e).__name__}: {e}"[:80], "ms": (time.perf_counter() - t0) * 1000}
    return {"ttft": ttft, "total": (time.perf_counter() - t0) * 1000,
            "chars": len("".join(text)), "text": "".join(text)[:40]}


async def main():
    conn = aiohttp.TCPConnector(limit=8)
    async with aiohttp.ClientSession(connector=conn) as s:
        print("=== 串行 3 条（真实生成） ===")
        for q in PROMPTS:
            r = await one(s, q)
            print(f"  {q[:12]:14s} -> {json.dumps(r, ensure_ascii=False)[:130]}")

        print("\n=== 并发 3 条（真实生成） ===")
        t0 = time.perf_counter()
        rows = await asyncio.gather(*[one(s, q) for q in PROMPTS])
        wall = time.perf_counter() - t0
        for q, r in zip(PROMPTS, rows):
            print(f"  {q[:12]:14s} -> {json.dumps(r, ensure_ascii=False)[:130]}")
        ttfts = [r["ttft"] for r in rows if r.get("ttft")]
        if ttfts:
            print(f"  墙钟 {wall:.2f}s | TTFT p50 {statistics.median(ttfts):.0f}ms "
                  f"min {min(ttfts):.0f}ms max {max(ttfts):.0f}ms")
        json.dump(rows, open("stress_real.json", "w", encoding="utf8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    asyncio.run(main())
