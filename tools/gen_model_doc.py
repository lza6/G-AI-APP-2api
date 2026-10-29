# -*- coding: utf-8 -*-
"""把 model_matrix2.json 生成成 README 可用的模型清单 markdown"""
import json
import sys
from collections import Counter, defaultdict

sys.stdout.reconfigure(encoding="utf-8")

data = json.load(open("model_matrix2.json", encoding="utf8"))
order = ["FREE", "VIP", "OFFLINE", "EMPTY", "ERR", "QUOTA"]
cnt = Counter(v["kind"] for v in data.values())

lines = ["# 模型可用性实测清单", "",
         f"共扫描 **{len(data)}** 个 chat 模型（按供应商优先级排序），结果分布：", "",
         "| 分类 | 数量 | 含义 |", "|---|---|---|",
         f"| FREE | {cnt.get('FREE',0)} | 直接可用，真实出字 |",
         f"| VIP | {cnt.get('VIP',0)} | 服务端要求订阅 |",
         f"| EMPTY | {cnt.get('EMPTY',0)} | 返回空（多模态/绘图模型走 chat 通道） |",
         f"| OFFLINE | {cnt.get('OFFLINE',0)} | 服务端配置下线 |",
         f"| ERR | {cnt.get('ERR',0)} | 网络异常（代理抖动，非模型问题） |",
         f"| QUOTA | {cnt.get('QUOTA',0)} | 出口 IP 额度耗尽时无法判定 |", ""]

by_prefix = defaultdict(list)
for name, v in data.items():
    if v["kind"] != "FREE":
        continue
    by_prefix[name.split(":")[0]].append((name, v.get("latency", 0)))

lines += ["## 可用模型（FREE）明细", "",
          "| 模型 | 典型延迟 |", "|---|---|"]
for name, lat in sorted([x for lst in by_prefix.values() for x in lst]):
    lines.append(f"| `{name}` | {lat}s |")

lines += ["", "## 分类明细", ""]
for kind in order:
    names = sorted(k for k, v in data.items() if v["kind"] == kind)
    if names:
        lines.append(f"**{kind}**（{len(names)}）：" + "、".join(f"`{n}`" for n in names))
        lines.append("")

out = "MODELS.md"
open(out, "w", encoding="utf8").write("\n".join(lines))
print("写入", out, len(lines), "行")
print("\n".join(lines[:20]))
