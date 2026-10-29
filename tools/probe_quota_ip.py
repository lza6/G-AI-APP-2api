# -*- coding: utf-8 -*-
"""额度维度定案工具 —— 每个出口 IP 各自额度独立吗？单 IP 到底给多少条？

用法:
    # proxies.txt 每行一个代理, 例如 socks5h://host:port 或 http://host:port
    GAI_PROXY_LIST=proxies.txt python probe_quota_ip.py

结论（作者实测）: 额度按**出口 IP** 计, 单 IP 精确 50 条; 同出口换新 device-id 不重置。
"""
import os
import sys
import time
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "gateway"))
sys.stdout.reconfigure(encoding="utf-8")

from gai_proto import GaiClient

MODEL = "GPT:4.1-mini"
LIMIT = int(os.getenv("GAI_LIMIT", "200"))


def load_proxies() -> list[str]:
    path = os.getenv("GAI_PROXY_LIST", "")
    if not path or not os.path.exists(path):
        raise SystemExit("需要 GAI_PROXY_LIST 指向代理清单文件（每行一个代理）")
    return [ln.strip() for ln in open(path, encoding="utf-8") if ln.strip() and not ln.startswith("#")]


def ask(c: GaiClient, q="Reply with OK") -> tuple[str, str]:
    out = []
    try:
        for ev in c.chat(q, ai_version=MODEL, conversation_id=str(uuid.uuid4())):
            d = ev.get("data") or {}
            out.append(d.get("answer") or ev.get("message") or "")
            if sum(len(x) for x in out) > 120:
                break
    except Exception as e:  # noqa: BLE001
        return "ERR", f"{type(e).__name__}: {e}"[:90]
    t = "".join(out).strip()
    low = t.lower()
    if "free usage limit" in low:
        return "QUOTA", t[:60]
    if "upgrade to vip" in low:
        return "VIP", t[:60]
    if not t:
        return "EMPTY", ""
    return "OK", t[:60]


def drain(proxy: str, label: str) -> dict:
    c = GaiClient(proxies={"http": proxy, "https": proxy}, timeout=120)
    for i in range(1, LIMIT + 1):
        kind, msg = ask(c)
        print(f"  [{label}] #{i:3d} {kind:6s} {msg}", flush=True)
        if kind != "OK":
            return {"exit": label, "free": i - 1, "stop": kind, "device": c.device_id}
        time.sleep(0.2)
    return {"exit": label, "free": LIMIT, "stop": "LIMIT_NOT_REACHED", "device": c.device_id}


if __name__ == "__main__":
    results = []
    for idx, proxy in enumerate(load_proxies(), 1):
        label = f"exit{idx}"
        print(f"\n===== {label} 全新设备，连续提问 =====")
        r = drain(proxy, label)
        results.append(r)
        print(f"  → 免费 {r['free']} 条后 {r['stop']}")

    print("\n===== 同出口换新设备，验证是否仍被拦（证明按 IP 而非设备） =====")
    for proxy, r in zip(load_proxies(), results):
        c2 = GaiClient(proxies={"http": proxy, "https": proxy}, timeout=120)
        print(f"  [{r['exit']}] 新设备 {c2.device_id} ->", ask(c2))

    import json
    json.dump(results, open("quota_by_ip.json", "w", encoding="utf8"), ensure_ascii=False, indent=1)
