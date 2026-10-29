# 交接书：把 G.AI 接入 new-api

> 读者假设：**完全没有本会话上下文**的人/会话，照着这份就能执行。
> 前置阅读：`docs/PROTOCOL.md`（协议）、`docs/REVERSE_REPORT.md`（证据）。

---

## 0. 先看这个：要不要接

| 维度 | 判断 |
|---|---|
| 可用性 | ✅ 匿名可用，零鉴权，模型真实出字 |
| 额度 | ⚠️ **每出口 IP 精确 50 条对话**（第 51 条触发），换 device-id 不重置 |
| 高端模型 | ❌ 服务端 VIP 校验，Claude / GPT-6 / Gemini Pro 全部不可用 |
| 免费可用模型 | **74 个**（`BOLATU:gpt-5/5.1/5.2/5.4`、`GPT:gpt-5.1/5.2/5.4`、`GPT:gpt-6-luna`、`BOLATU:claude-haiku-4-5`、`BOLATU:claude-sonnet-4-20250514`、`BOLATU:grok-4.1`、`XAI:grok-4`、`DEEPSEEK:v3`、`GEMINI:v2.5-flash` … 全量见 `MODELS.md`） |
| 稳定性 | 单次生成多一跳代理，基线 RTT ≈1.5s |

**结论：不适合当主力渠道。** 只有当「愿意用 IP 池换量」时才有意义（每 IP 约 5~15 条 × 池大小）。
若接，建议定位为 **补充渠道 / 试验渠道**，权重给低，并设置零级故障自动熔断。

---

## 1. 任务契约

| 项 | 内容 |
|---|---|
| 目标 | new-api 新增渠道类型，支持 `chat`（流式+非流式）；图片能力暂不接 |
| 不可改动 | `relaykit/` 模块独立性（不得 import 根模块）；不得改 `common/json.go` 之外引入 `encoding/json` 直调 |
| 交付标准 | `go build ./...` 通过 + `cd relaykit && GOWORK=off go build ./...` 通过 + 本地真实上游联调 1 次成功流式 + 错误映射表逐项验证 |
| 建议分支 | `feat/channel-gai` |

---

## 2. 协议速查（照抄即可）

```
上游:  https://api.chatgai.fun
通道:  POST /common/sse/chat   (text/event-stream)
请求体: {"bundle":"com.aichatmaster.chat.gp","security":"<hex>","bundleId":"com.aichatmaster.chat.gp"}
security = AES-128-CBC/PKCS7(明文JSON).hex()
  key = Ka7Ya98107EdGXQa    iv = yc0q2icx1oq4lijm
明文JSON = 业务参数 + bundle + nonce + version + timestamp + signature
  nonce     = 32 位, 字母表 qwertyuiopasdfghjklzxcvbnmQAZXSWEDCVFRTGBNHYUJMKIOLP1234567890
  version   = "2.6.8"
  timestamp = 秒
  signature = sha1( sortedNonExcluded(k=v, "&") + SALT )   # hex 小写
  SALT      = t6KeG6aKR5pm65oWn5aqS6LWE57O757ufS2V2aW4uWWFuZw
  签名排除字段 = language,type,voice,needVoice,imageUrls,botPrompt,userId,needSearch,tonePrompt
请求头:
  UserType: app_user    x-bundle-id: com.aichatmaster.chat.gp    x-app-version: 2.6.8
  x-device-id: <16位hex，可随机>   x-language: en   x-sys-type: android
  x-country: US        x-device-type: android    x-sys-version: 13
  content-language: zh_CN   content-type: application/json
响应帧: data: {"code":0,"message":"success","data":{"answer":"增量","message_id":"..","conversation_id":".."},"chatNum":0,"imgNum":0}
结束:   data: [DONE]
```

**两个必须照做的约束**：

1. 进签名的值按 Dart 插值渲染：`true/false`、`null`、列表 `[a, b]`、Map `{k: v}`。
2. **不要发服务端白名单之外的字段**（例如 `chatType`），也不要发空字符串字段 —— 否则 `签名失败`。参数集合固定为：
   `question` `conversationId` `type="1"` `needSearch` `language` `aiVersion`（bot 链路加 `botId`）。

---

## 3. 错误映射表（照此实现）

| 上游响应 | 网关错误 | HTTP | new-api 侧行为 |
|---|---|---|---|
| `answer` 含 `Your free usage limit has been reached` | `quota_exhausted` | 429 | 按「额度耗尽」处理，**不重试**，直接换渠道/换号 |
| `answer` 含 `Please upgrade to VIP to continue` | `vip_required` | 403 | 该模型永久不可用，**建议直接禁掉该模型** |
| `answer` 含 `The current model is offline` | `model_offline` | 503 | 触发渠道测试，标记模型不可用 |
| `answer`/`message` 含 `Signature verification failed` / `签名失败` | `sign_failed` | 502 | 协议实现 bug，告警 |
| `answer` 含 `cannot exceed 50000 characters` | `prompt_too_long` | 400 | 客户端错误，不重试 |
| `code != 0` 且无 `answer` | `upstream_error` | 502 | 可重试 1 次 |

> 注意：**错误也是 200 + SSE**，必须解析帧内容判定，不能只看 HTTP 状态码。

---

## 4. 路线 A：零 Go 代码旁挂（推荐先做）

把本目录的 `server.py` 当上游，new-api 里直接配一个 **OpenAI 兼容自定义渠道** 指向它。

```
new-api 渠道配置
  type:            OpenAI（或「自定义 OpenAI 兼容」）
  base_url:        http://127.0.0.1:8970/v1
  model:           GPT:4.1-mini 等 aiVersion 原样填（含冒号）
  其它 key:        随便填，网关不校验
```

要点：

- 模型名 **原样** 用 `aiVersion`（`GPT:4.1-mini`）；网关已内置 `gpt-4.1-mini → GPT:4.1-mini` 之类的简写别名。
- 网关侧并发：`GAI_MAX_CONN=20`（实测 20 连接下 8 RPS，6 连接只有 3 RPS）。
- 若要做 IP 池：在 `gai_proto.py` 里给 `GaiClient` 加 `proxy` 轮换，`server.py` 的 `_client` 换成「按请求选代理」的连接池；每 IP 计一份额度。

**优点**：零 Go 改动、当天可上线、可独立重启。
**缺点**：多一层进程；计费/限流在网关上做，new-api 看不到真实用量。

---

## 5. 路线 B：原生 Go 渠道（需要改代码）

新增 `relay/channel/gai/`：

```
relay/channel/gai/
  adaptor.go       ConvertOpenAIRequest / ConvertImageRequest / DoRequest / DoResponse
  dto.go           上游请求响应结构
  sign.go          AES-CBC + SHA1 签名 + nonce   ← 核心
  constants.go     常量：base、bundle、key、iv、salt、排除字段表、模型映射
```

关键实现点：

1. **sign.go**：`crypto/aes` + `crypto/cipher`（CBC + PKCS7 手工补位）+ `crypto/sha1`。nonce 用 `crypto/rand` 从 62 字符表取 32 位。
2. **DoRequest**：`multipart` 不用，走 `application/json`；`Content-Type` 与自定义头按 §2 设。
3. **DoResponse**：上游是 SSE，`dto.Usage` 需按 new-api 约定返回**值**而非指针（历史坑：`*dto.Usage` 断言会 panic）。把 `answer` 增量转成 OpenAI `delta.content`；`[DONE]` 转 `data: [DONE]`。
4. **usage**：上游不返回 token 用量 ⇒ 必须自行估算并标注来源（`len/4` 之类），计费口径与用户讲清楚，不要假装精确。
5. **模型列表**：从 `GET /model/modelConfig?language=en` 拉取，`aiVersion` 即模型名；`vipStatus != "0"` 的模型**不要**下发。
6. **conversationId**：OpenAI 请求里没有这个字段，建议用 `requestID` 或 `user` 派生，保证同一会话稳定。

**优点**：单进程、计费在 new-api 内、便于限流。
**缺点**：需求跨模块改动（channel + relay 常量 + 前端模型列表），验证成本高。

---

## 6. 计费锚点

| 计费锚点 | 值 | 说明 |
|---|---|---|
| 上游真实成本 | ≈0（免费额度内） | 超过额度即不可用，不是「按量付费」 |
| 可计费依据 | 自行估算 token | 上游不返回 usage，**必须标注为估算** |
| 建议定价 | 极低倍率或纯免费 | 该渠道价值在「有无」而非「质优」 |
| 限流 | **50 条 / 出口 IP** | 池大小 N ⇒ 日可用量 ≈ 50N；务必在网关侧按 IP 计数，耗尽即换出口或熔断 |
| 并发 | 无串行化惩罚 | 实测并发 3 条墙钟 ≈ 单条，瓶颈是额度不是并发 |

---

## 7. 验收清单

- [ ] `go build ./...` 通过
- [ ] `cd relaykit && GOWORK=off go build ./...` 通过
- [ ] 本地真实上游联调：非流式 1 次成功、流式 1 次逐字到达、`[DONE]` 正确
- [ ] 错误映射表 6 条逐项命中（可用额度耗尽后的真实响应验证 429，不需要 mock）
- [ ] 模型列表拉取正常，VIP 模型已过滤
- [ ] 超长 prompt（>50000 字符）返回 400 而非 502
- [ ] 并发 20 压测无 5xx（参考 `stress_round1_conn20.json`）
- [ ] 渠道故障时不拖垮网关（超时 + 熔断）

## 8. 回滚

- 路线 A：删掉渠道配置即可，无代码变更。
- 路线 B：revert `feat/channel-gai` 分支；无 DB 迁移、无配置持久化变更 ⇒ 回滚无数据风险。
