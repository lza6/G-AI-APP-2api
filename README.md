# G.AI 2API（R1）

把 `G.AI v2.6.8`（`com.aichatmaster.chat`）的匿名聊天链路本地化成一个 **OpenAI 兼容网关 + 演示页**。

- ✅ 协议 100% 还原并实测通过（真实流式出字）
- ✅ 零鉴权：不登录、不注册、不需要 token
- ⚠️ 上游按**出口 IP** 限免费额度（配置 `free_message=5`，实测约 15 条后被硬拦）
- ⚠️ 高端模型走**服务端 VIP 校验**，不可绕过

---

## 30 秒跑起来

```bash
cd <WORKDIR>
pip install fastapi uvicorn httpx pycryptodome
# 本机需经代理出海；如直连可删掉 GAI_PROXY
GAI_PROXY=<HTTP_PROXY> GAI_PORT=8970 python server.py
```

打开 <http://127.0.0.1:8970/> 即演示页。

```bash
curl http://127.0.0.1:8970/v1/chat/completions \
  -H 'content-type: application/json' \
  -d '{"model":"GPT:4.1-mini","messages":[{"role":"user","content":"say hi"}]}'
```

## 接口

| Method | Path | 说明 |
|---|---|---|
| GET | `/` | 演示页 |
| GET | `/health` | 健康检查 |
| GET | `/v1/models` | OpenAI 兼容模型列表 |
| POST | `/v1/chat/completions` | OpenAI 兼容，支持 `stream` |
| POST | `/api/chat` | 透传上游原始 SSE 事件（含 `_t` 耗时） |
| POST | `/api/image` | 文生图同步通道（未验证额度） |

环境变量：`GAI_UPSTREAM` `GAI_PORT` `GAI_MAX_CONN`（默认 6，实测 **20 更优**） `GAI_PROXY` `GAI_PROXY_LIST` `GAI_MODEL` `GAI_TIMEOUT`

> **IP 池**：额度按出口 IP 计，因此网关内置了轮换开关。把出口代理写进一个文本文件（每行 `http://host:port`），
> 用 `GAI_PROXY_LIST=proxies.txt` 启动，每个请求按轮询换出口、每出口一套独立连接池 —— 每换一个出口就是一份新额度。

---

## 能力实测表

| 能力 | 状态 | 证据 |
|---|---|---|
| 匿名流式聊天 | ✅ 已验证 | 真实返回 `GPT:4.1-mini` / `GEMINI:gemini-3-flash-preview` 增量文本 |
| 多轮上下文（复用 `conversationId`） | ⏳ 待验证 | 服务端会回填 `conversation_id`；多轮记忆是否生效需额度恢复后复测 |
| 模型目录（9 个对外） | ✅ 已验证 | `/model/modelConfig` |
| 后端模型能力表（247 项） | ✅ 已验证 | `capacityList`，未暴露的 `aiVersion` 也可调 |
| **免 VIP 可用模型** | ✅ **74 个** | 145 个 chat 模型实测扫描，见 `MODELS.md` |
| OpenAI 兼容非流式 | ✅ 已验证 | `POST /v1/chat/completions` |
| OpenAI 兼容流式 | ✅ 已验证 | SSE `delta.content` + `[DONE]` |
| 演示页真实浏览器路径 | ✅ 已验证 | Playwright：下拉 9 模型、发消息、渲染、计时（`demo_proof.png`） |
| 文件上传 `/app/upload` | ✅ 已验证可用 | 无鉴权 multipart，返回 CDN URL + ossId |
| 语音音色目录 | ✅ 已验证 | `az:Ollie` / `az:Ada` 等 Azure TTS 音色 |
| 文生图 | ❌ 需 VIP | `/common/img/async/create` → `code:-3 vip has expired`；同步端点恒 500 |
| 语音合成 | ⏳ 未打通 | `needVoice=1` 聊天正常但流内无音频 |
| 读图问答 | ⏳ 待验证 | 签名集合特殊（`without: question/version/botId`），实测未对齐 |
| VIP 高端模型 | ❌ 服务端拦截 | Claude / GPT-6 / Gemini Pro 均返回需订阅 |

---

## 压测结果（R1）

> 重要前提：压测时本机出口 IP 的免费额度已耗尽，所有请求走「额度拒绝」快路径。
> 因此下表反映的是**网关 + 上游通道的工程特性（连接复用、稳定性、错误映射）**，不是模型生成吞吐。

本地代理 10808，出口在 AWS us-west-2，单跳 RTT ≈ 1.5s。

| 上游连接池 | 并发 | 请求数 | 墙钟 | RPS | P50 | P95 | 状态码分布 |
|---|---|---|---|---|---|---|---|
| 6 | 1 | 5 | 9.48s | 0.53 | 1763ms | 2871ms | 429×5 |
| 6 | 5 | 15 | 5.77s | 2.60 | 1488ms | 2716ms | 429×15 |
| 6 | 10 | 30 | 10.91s | 2.75 | 2904ms | 5208ms | 429×30 |
| 6 | 20 | 40 | 13.20s | 3.03 | 5389ms | 7293ms | 429×40 |
| 6 | 30 | 60 | 21.91s | 2.74 | 9182ms | 11592ms | 429×60 |
| **20** | 1 | 5 | 12.50s | 0.40 | 2487ms | 4148ms | 429×5 |
| **20** | 5 | 15 | 5.49s | 2.73 | 1689ms | 2596ms | 429×15 |
| **20** | 10 | 30 | 7.41s | 4.05 | 1817ms | 3718ms | 429×30 |
| **20** | 20 | 40 | 4.96s | **8.07** | 1490ms | 2495ms | 429×40 |
| **20** | 30 | 60 | 13.26s | 4.52 | 2599ms | 6667ms | 429×60 |

**结论**

1. **零 5xx、零连接异常、零 SSL 中断**，并发 30 下网关稳定。
2. 连接池 6 是明显的自设瓶颈（3 RPS → 换 20 后 8 RPS）。本机代理在 ~20 并发下仍稳定，与「隧道上限 6-7」的旧经验**不适用于本目标**。
3. 并发 30 开始退化（4.5 RPS）——代理侧饱和，建议网关 `GAI_MAX_CONN=20`、上游侧不超过 20 并发。
4. 端点本身在**单次生成**上的开销以代理 RTT 为主（~1.5s 起步），真实生成速度需额度恢复后复测（待办 R2）。

原始数据：`stress_round1.json`（连接池 6）、`stress_round1_conn20.json`（连接池 20）。

### 真实生成实测（换上带额度的出口 IP 后）

出口为境外 SOCKS5，链路多一跳，因此基线延迟高于默认代理。

| 场景 | 首字延迟 TTFT | 总耗时 | 输出 |
|---|---|---|---|
| 串行 · 自我介绍 | 3562ms | 3758ms | 31 字 |
| 串行 · 算术 | 4103ms | 4104ms | `7` |
| 串行 · 文案 | 4116ms | 4140ms | 10 字 |
| **并发 3 条** | p50 **3855ms**（min 3562 / max 4057） | 墙钟 **4.06s** | 全部正确 |

**关键结论：并发 3 条的墙钟（4.06s）与单条（3.7~4.1s）几乎相同 ⇒ 上游对同一 IP 的并发无串行化惩罚**，
真正的瓶颈是额度（50 条/IP）而不是并发能力。这也是「配 IP 池才有意义」的直接证据。

原始数据：`stress_real.json`。

---

## 文件清单

```
gai_proto.py          协议客户端（签名/AES/SSE 解析），可独立当库用
server.py             本地网关（FastAPI，OpenAI 兼容 + demo 接口）
demo.html             演示页（原生 JS，流式渲染 + 原始 SSE 面板 + 耗时）
stress_test.py        并发阶梯压测
probe_r1.py           createNewUser / 通道探测
probe_r2.py           模型表 / 配置探测
probe_fields.py       逐字段签名二分
probe_common.py       /common/sse/chat 打通脚本
probe_sse.py          SSE 端点探针
probe_quota.py        免费额度定位
probe_matrix.py       端点矩阵普查
probe_sign.py         签名方案穷举（历史留档）
scan_models.py        247 个 aiVersion 可用性扫描
e2e_demo.py           Playwright 真实浏览器验证
models_full.json      模型表 + 能力表原始返回
model_matrix.json     247 项可用性分类
demo_proof.png        演示页截图（真实运行）
docs/PROTOCOL.md      协议还原报告（核心）
docs/REVERSE_REPORT.md 逆向过程与证据
docs/NEWAPI_INTEGRATION.md  new-api 渠道对接交接书
```

## 风险与限制

1. **额度是 IP 维度的，每出口 IP 精确 50 条对话**（实测 `5.61.51.28` 第 51 条触发；同出口换新 device-id 仍被拦）。
   换算模型：可用量 = 50 × 有效出口 IP 数。这是能不能当渠道的唯一经济依据。
2. **VIP 模型不可用**：服务端校验；文生图同样需 VIP（`code:-3`）。伪造内购收据未验证且不建议尝试。
3. 未对上游做「是否会因大量并发拉黑 IP」的验证 —— 本轮压测全部落在额度拒绝快路径上，**不能据此断言并发安全**。
4. `/app/upload` 无鉴权可写对方 CDN，属对方资源滥用面，仅作能力记录，不建议用于生产。
5. 本仓库仅用于协议研究；上游服务条款、版权与合规风险由使用者承担。
