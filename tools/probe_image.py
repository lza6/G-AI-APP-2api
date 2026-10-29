# -*- coding: utf-8 -*-
"""R9: 文生图通道探测（同步 /common/img/create 与异步 /common/img/async/*）"""
import json
import os
import sys
import time
import uuid

import requests

sys.stdout.reconfigure(encoding="utf-8")

from gai_proto import headers, seal

BASE = "https://api.chatgai.fun"
EXIT = os.getenv("GAI_PROXY", "http://127.0.0.1:8080")
P = {"http": EXIT, "https": EXIT}


def plain(path, params, tries=3):
    h = headers()
    for _ in range(tries):
        try:
            r = requests.post(BASE + path, data=json.dumps(params, ensure_ascii=False),
                              headers=h, proxies=P, timeout=180)
            return r.status_code, r.text
        except Exception as e:  # noqa: BLE001
            err = f"{type(e).__name__}: {e}"[:90]
            time.sleep(1.2)
    return -1, err


def signed(path, params, tries=3):
    h = headers()
    for _ in range(tries):
        try:
            r = requests.post(BASE + path, data=json.dumps(seal(params), ensure_ascii=False),
                              headers=h, proxies=P, timeout=180)
            return r.status_code, r.text
        except Exception as e:  # noqa: BLE001
            err = f"{type(e).__name__}: {e}"[:90]
            time.sleep(1.2)
    return -1, err


if __name__ == "__main__":
    mac = uuid.uuid4().hex[:12]
    cases = [
        ("sync/nano-banana", "plain", "/common/img/create",
         {"botId": "", "prompt": "a red apple on a table", "model": "GEMINI:nano-banana", "style": "natural", "mac": mac}),
        ("sync/baidu-nano", "plain", "/common/img/create",
         {"botId": "", "prompt": "a red apple on a table", "model": "BAIDU:nano-banana", "style": "natural", "mac": mac}),
        ("async/nano-banana", "signed", "/common/img/async/create",
         {"aiVersion": "GEMINI:nano-banana", "prompt": "a red apple on a table",
          "overrideSize": "", "imageUrl": "", "userId": "", "styleText": "", "mac": mac}),
    ]
    for name, kind, path, params in cases:
        fn = plain if kind == "plain" else signed
        code, text = fn(path, params)
        print(f"\n### {name} ({kind}) -> {code}\n{text[:700]}")
