# -*- coding: utf-8 -*-
"""G.AI 2API 本地压测（R1）

测什么:
  1) 网关在并发下的稳定性（是否出现 5xx / 连接被上游掐断 SSL EOF）
  2) 端到端延迟分布（P50/P95），上游错误如何被快速映射
不测什么:
  真实吞吐量 —— 上游按 IP 限 5 条免费额度，额度耗尽后一律 429 快速失败，
  因此本轮的数字反映「网关+上游通道」的工程特性，不是模型生成吞吐。
"""
import asyncio
import json
import statistics
import sys
import time

import aiohttp

sys.stdout.reconfigure(encoding="utf-8")

GATEWAY = "http://127.0.0.1:8971"
BODY = {
    "model": "GPT:4.1-mini",
    "messages": [{"role": "user", "content": "Reply with the single word: OK"}],
    "stream": False,
}


async def one(session: aiohttp.ClientSession) -> dict:
    t0 = time.perf_counter()
    try:
        async with session.post(GATEWAY + "/v1/chat/completions", json=BODY,
                                timeout=aiohttp.ClientTimeout(total=180)) as r:
            await r.read()
            return {"status": r.status, "ms": (time.perf_counter() - t0) * 1000}
    except Exception as e:  # noqa: BLE001
        return {"status": -1, "err": f"{type(e).__name__}: {e}"[:120], "ms": (time.perf_counter() - t0) * 1000}


async def level(conc: int, total: int) -> dict:
    conn = aiohttp.TCPConnector(limit=conc)
    async with aiohttp.ClientSession(connector=conn) as s:
        t0 = time.perf_counter()
        sem = asyncio.Semaphore(conc)

        async def worker():
            async with sem:
                return await one(s)

        results = await asyncio.gather(*[worker() for _ in range(total)])
        wall = time.perf_counter() - t0

    lat = sorted(r["ms"] for r in results)
    status: dict[int, int] = {}
    for r in results:
        status[r["status"]] = status.get(r["status"], 0) + 1
    errs = [r.get("err") for r in results if r["status"] == -1]
    return {
        "conc": conc, "total": total, "wall_s": round(wall, 2),
        "rps": round(total / wall, 2),
        "p50_ms": round(statistics.median(lat)),
        "p95_ms": round(lat[min(len(lat) - 1, int(len(lat) * 0.95))]),
        "max_ms": round(lat[-1]),
        "status": status, "samples": list(status)[:5],
        "err_sample": errs[:3],
    }


async def main():
    ladder = [(1, 5), (5, 15), (10, 30), (20, 40), (30, 60)]
    rows = []
    for conc, total in ladder:
        row = await level(conc, total)
        rows.append(row)
        print(f"conc={conc:2d} n={total:3d} wall={row['wall_s']:6.2f}s rps={row['rps']:6.2f} "
              f"p50={row['p50_ms']:5d}ms p95={row['p95_ms']:5d}ms status={row['status']}"
              + (f" err={row['err_sample']}" if row["err_sample"] else ""), flush=True)
        await asyncio.sleep(2)
    json.dump(rows, open("stress_round1_conn20.json", "w", encoding="utf8"), ensure_ascii=False, indent=1)
    print("\n写入 stress_round1_conn20.json")


if __name__ == "__main__":
    asyncio.run(main())
