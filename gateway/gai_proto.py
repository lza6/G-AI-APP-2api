# -*- coding: utf-8 -*-
"""G.AI v2.6.8 (com.aichatmaster.chat) 上游协议客户端

静态还原来源（blutter 反编译包 package:ai_chat）:
  api/request.dart::_createGPTSign  0x8d9758  签名
  api/request.dart::aesEncryption   0x8d9da0  AES-128-CBC/PKCS7
  api/request.dart::_randomStr      0x901244  32 位 nonce
  api/request.dart::_createHeader   0x654bb8  请求头
  api/request.dart::request         0x624d14  明文 REST 通道（不签名）
"""
from __future__ import annotations

import hashlib
import json
import random
import time
import uuid
from typing import Any, Iterator

import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

BUNDLE = "com.aichatmaster.chat.gp"
APP_VERSION = "2.6.8"
BASE = "https://api.chatgai.fun"

AES_KEY = b"Ka7Ya98107EdGXQa"
AES_IV = b"yc0q2icx1oq4lijm"
SALT = "t6KeG6aKR5pm65oWn5aqS6LWE57O757ufS2V2aW4uWWFuZw"
NONCE_ALPHABET = "qwertyuiopasdfghjklzxcvbnmQAZXSWEDCVFRTGBNHYUJMKIOLP1234567890"

# _createGPTSign 内联 remove 的字段：参与加密但不参与签名
SIGN_EXCLUDE = ("language", "type", "voice", "needVoice", "imageUrls",
                "botPrompt", "userId", "needSearch", "tonePrompt")

PROXIES: dict[str, str] | None = None


def nonce(n: int = 32) -> str:
    return "".join(random.choice(NONCE_ALPHABET) for _ in range(n))


def aes_encrypt(plain: str) -> str:
    return AES.new(AES_KEY, AES.MODE_CBC, AES_IV).encrypt(pad(plain.encode(), 16)).hex()


def aes_decrypt(hexstr: str) -> str:
    return unpad(AES.new(AES_KEY, AES.MODE_CBC, AES_IV).decrypt(bytes.fromhex(hexstr)), 16).decode()


def dart_value(v: Any) -> str:
    """模拟 Dart 插值 '$k=${data[k]}' 的取值渲染"""
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (list, tuple)):
        return "[" + ", ".join(dart_value(x) for x in v) + "]"
    if isinstance(v, dict):
        return "{" + ", ".join(f"{k}: {dart_value(x)}" for k, x in v.items()) + "}"
    return str(v)


def sign_string(data: dict[str, Any], extra_exclude: tuple[str, ...] = ()) -> str:
    keys = sorted(k for k in data if k not in SIGN_EXCLUDE and k not in extra_exclude)
    return "&".join(f"{k}={dart_value(data[k])}" for k in keys)


def signature(data: dict[str, Any], extra_exclude: tuple[str, ...] = ()) -> str:
    return hashlib.sha1((sign_string(data, extra_exclude) + SALT).encode()).hexdigest()


def seal(params: dict[str, Any], version: str = APP_VERSION,
         without: tuple[str, ...] = ()) -> dict[str, Any]:
    """without: 对应 Dart 侧 _createGPTSign(params, without: [...])，
    部分端点会额外排除字段（如 /imageAi/readImageSeeAnswer 排除 question/version/botId）"""
    data = dict(params)
    data["bundle"] = BUNDLE
    data["nonce"] = nonce()
    data["version"] = version
    data["timestamp"] = int(time.time())
    data["signature"] = signature(data, without)
    body = {
        "bundle": BUNDLE,
        "security": aes_encrypt(json.dumps(data, ensure_ascii=False, separators=(",", ":"))),
        "bundleId": BUNDLE,
    }
    if params.get("imageUrls") is not None:
        body["imageUrls"] = params["imageUrls"]
    return body


def headers(device_id: str | None = None, user_id: str = "", lang: str = "en") -> dict[str, str]:
    return {
        "UserType": "app_user",
        "content-language": "zh_CN",
        "x-bundle-id": BUNDLE,
        "x-app-version": APP_VERSION,
        "x-language": lang,
        "x-device-type": "android",
        "x-device-id": device_id or uuid.uuid4().hex[:16],
        "x-sys-type": "android",
        "x-sys-version": "13",
        "x-country": "US",
        "x-user-id": user_id,
        "content-type": "application/json",
        "Connection": "close",
    }


class GaiClient:
    """一个实例 = 一台虚拟设备（device-id 池化的最小单元）"""

    def __init__(self, device_id: str | None = None, user_id: str = "", base: str = BASE,
                 timeout: int = 180, proxies: dict[str, str] | None = None):
        self.base = base.rstrip("/")
        self.device_id = device_id or uuid.uuid4().hex[:16]
        self.user_id = user_id
        self.timeout = timeout
        self.proxies = proxies if proxies is not None else PROXIES

    # ---- 明文 REST 通道（不加密，供模型表/配置类接口用） ----
    def rest(self, path: str, params: dict | None = None, method: str = "GET") -> dict:
        h = headers(self.device_id, self.user_id)
        url = self.base + path
        if method == "GET":
            r = requests.get(url, params=params or {}, headers=h, timeout=self.timeout, proxies=self.proxies)
        else:
            r = requests.post(url, data=json.dumps(params or {}, ensure_ascii=False), headers=h,
                              timeout=self.timeout, proxies=self.proxies)
        return r.json()

    # ---- 加密通道 ----
    def sse(self, path: str, params: dict, show_raw: bool = False) -> Iterator[dict]:
        body = seal(params)
        r = requests.post(self.base + path, data=json.dumps(body), headers=headers(self.device_id, self.user_id),
                          timeout=self.timeout, proxies=self.proxies, stream=True)
        for line in r.iter_lines(decode_unicode=False):
            if not line:
                continue
            text = line.decode("utf-8", "replace")
            if text.startswith("data:"):
                payload = text[5:].strip()
                if payload == "[DONE]":
                    return
                try:
                    yield json.loads(payload)
                except json.JSONDecodeError:
                    if show_raw:
                        yield {"_raw": text}
            elif show_raw:
                yield {"_raw": text}

    def chat(self, question: str, ai_version: str = "GPT:4.1-mini", conversation_id: str | None = None,
             need_search: bool = False, language: str = "en", show_raw: bool = False) -> Iterator[dict]:
        return self.sse("/common/sse/chat", {
            "question": question,
            "conversationId": conversation_id or str(uuid.uuid4()),
            "type": "1",
            "needSearch": need_search,
            "language": language,
            "aiVersion": ai_version,
        }, show_raw=show_raw)


if __name__ == "__main__":
    c = GaiClient(proxies={"http": "<HTTP_PROXY>", "https": "<HTTP_PROXY>"})
    print("sign_string:", sign_string({"a": 1, "b": 2, "type": "1"}))
    cid = str(uuid.uuid4())
    for ev in c.chat("用一句话介绍你自己", ai_version="GPT:4.1-mini", conversation_id=cid, language="zh"):
        a = ev.get("data", {}).get("answer", "")
        print(a, end="", flush=True)
    print("\n[DONE]")
