# -*- coding: utf-8 -*-
"""R10: 文件上传 + 读图/文档问答链路"""
import json
import struct
import os
import sys
import time
import uuid
import zlib

import requests

sys.stdout.reconfigure(encoding="utf-8")

from gai_proto import headers, seal

BASE = "https://api.chatgai.fun"
EX = os.getenv("GAI_PROXY", "http://127.0.0.1:8080")
P = {"http": EX, "https": EX}


def make_png(w=64, h=64, rgb=(220, 40, 40)) -> bytes:
    """生成一张纯色 PNG（不依赖 Pillow）"""
    raw = b"".join(b"\x00" + bytes(rgb) * w for _ in range(h))

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw))
            + chunk(b"IEND", b""))


def upload(png: bytes, name="file.png"):
    body = seal({})
    h = headers()
    h["content-type"] = "multipart/form-data"
    files = {"file": (name, png, "image/png")}
    for _ in range(3):
        try:
            r = requests.post(BASE + "/app/upload", files=files, data=body, headers=h, proxies=P, timeout=180)
            return r.status_code, r.text
        except Exception as e:  # noqa: BLE001
            err = f"{type(e).__name__}: {e}"[:90]
            time.sleep(1.2)
    return -1, err


if __name__ == "__main__":
    png = make_png()
    print("PNG bytes:", len(png))
    code, text = upload(png)
    print("upload ->", code, text[:600])
    try:
        d = json.loads(text)
        url = (d.get("data") or {}) if isinstance(d.get("data"), dict) else d.get("data")
        print("parsed data:", str(url)[:300])
    except Exception as e:  # noqa: BLE001
        print("parse fail", e)
