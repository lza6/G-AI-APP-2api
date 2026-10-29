# -*- coding: utf-8 -*-
"""R6: 全量 aiVersion 可用性扫描（FREE / VIP / OFFLINE / ERR）"""
import json
import sys
import time
import uuid

sys.stdout.reconfigure(encoding="utf-8")

from gai_proto import GaiClient

PROXIES = {"http": "<HTTP_PROXY>", "https": "<HTTP_PROXY>"}
PROMPT = "Reply with exactly: OK"


def classify(text: str) -> str:
    t = text.lower()
    if "vip" in t or "upgrade" in t:
        return "VIP"
    if "offline" in t:
        return "OFFLINE"
    if "sign" in t or "ǩ" in text:
        return "SIGNFAIL"
    if not text.strip():
        return "EMPTY"
    return "FREE"


def probe(client: GaiClient, ai_version: str) -> tuple[str, str, float]:
    t0 = time.time()
    out = []
    try:
        for ev in client.chat(PROMPT, ai_version=ai_version, conversation_id=str(uuid.uuid4())):
            d = ev.get("data") or {}
            msg = d.get("answer") or ev.get("message") or ""
            out.append(msg)
            if sum(len(x) for x in out) > 200:
                break
    except Exception as e:  # noqa: BLE001
        return "ERR", f"{type(e).__name__}: {str(e)[:80]}", time.time() - t0
    text = "".join(out)
    return classify(text), text[:80].replace("\n", " "), time.time() - t0


if __name__ == "__main__":
    models = json.load(open("models_full.json", encoding="utf8"))["data"]["capacityList"]
    names = sorted(models)
    c = GaiClient(proxies=PROXIES)
    results = {}
    for i, name in enumerate(names, 1):
        kind, sample, dt = probe(c, name)
        results[name] = {"kind": kind, "sample": sample, "latency": round(dt, 2)}
        print(f"[{i:3d}/{len(names)}] {name:42s} {kind:8s} {dt:5.1f}s  {sample[:50]}", flush=True)
        time.sleep(0.4)
        if i % 25 == 0:
            json.dump(results, open("model_matrix.json", "w", encoding="utf8"), ensure_ascii=False, indent=1)
    json.dump(results, open("model_matrix.json", "w", encoding="utf8"), ensure_ascii=False, indent=1)
    from collections import Counter
    print("\n=== SUMMARY ===")
    print(Counter(v["kind"] for v in results.values()))
    for kind in ("FREE", "VIP", "OFFLINE", "EMPTY", "ERR"):
        names_ = [k for k, v in results.items() if v["kind"] == kind]
        print(f"\n{kind} ({len(names_)}):")
        print("  " + ", ".join(names_[:200]))
