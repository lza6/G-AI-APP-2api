# G.AI v2.6.8 上游协议还原报告

> 目标：`G.AI v2.6.8 (Premium)` — `com.aichatmaster.chat`（Google Play 变体 `com.aichatmaster.chat.gp`）
> 上游：`https://api.chatgai.fun`（AWS us-west-2），跳转域名 `https://api.chatgeine.cc`
> 分析方式：blutter 静态反编译（Flutter AOT，Dart 3.6.2，**未混淆**）+ 真实上游探测
> 证据等级：**已验证**＝实跑观察到 / **静态确认**＝读反编译代码确认 / **合理推断**＝有间接证据 / **待验证**＝缺条件

---

## 0. 结论速览

| 项目 | 结论 | 证据 |
|---|---|---|
| 鉴权 | **无鉴权**。不登录、不注册、无 token，凭 `x-device-id` 头即用 | 已验证 |
| 匿名聊天 | `POST /common/sse/chat` 真实流式出字（GPT / Gemini） | 已验证 |
| 请求加密 | AES-128-CBC/PKCS7，key/iv 硬编码在 `libapp.so` | 已验证（上游能解） |
| 请求签名 | `sha1(排序后 k=v 串 + 固定盐)`，32 位 hex | 已验证（上游校验通过） |
| 免费额度 | 服务端配置 `free_message=5`；实测约 15 次成功问答后同 IP 被硬拦 | 已验证 + 待验证 |
| 额度维度 | 疑似**按出口 IP**（换新 device-id 不重置） | 合理推断 |
| 模型可用面 | 对外暴露 9 个，后端能力表 247 个 `aiVersion`；高端模型需 VIP | 已验证 |
| VIP 校验 | **服务端**校验（"Please upgrade to VIP"），非客户端自报 | 已验证 |
| 二次风控 | 无图形验证码 / 无 JS 挑战 / 无设备指纹 SDK（仅 device_info 取机型） | 静态确认 |

**一句话**：这是一个**零鉴权、按 IP 限 5 条免费**的多模型中转；单 IP 可白嫖的算力很小，要变成可用渠道必须配 IP 池轮换。

---

## 1. 目标信息

| 项 | 值 |
|---|---|
| 包名 | `com.aichatmaster.chat`（支付包名 `...chat.gp`） |
| 版本 | 2.6.8（`x-app-version` / 签名 `version` 字段） |
| 引擎 | Flutter / Dart 3.6.2，arm64-v8a，release |
| 混淆 | **无**（类名、方法名、文件路径全部保留） |
| DEX / 加固 | 无加固；仅 ElaMods 二次打包痕迹（`E_l_a_Mods.xml`、`assets/El_a`） |
| 关键依赖 | `dio`、`dio_smart_retry`、`encrypt`、`crypto`、`device_info_plus`、`package_info_plus`、`in_app_purchase`、`firebase_*`、`youtube_explode_dart`、`google_mlkit_text_recognition` |
| 本地库 | `aichat.db`（sqflite，存历史消息，明文本地） |

反编译产物结构（`<WORKDIR>/blutter_out/asm/ai_chat/`）：

```
api/request.dart          ← 全部协议逻辑都在这里
api/api.dart              ← 业务接口封装（端点 + 参数名）
api/support/ChatSSE.dart  ← SSE 解析
api/schema/*.dart         ← DTO
providers/                ← riverpod 状态
ui/screens/chat/chat_view_controller.dart  ← 参数组装现场
```

---

## 2. 两条通道

App 有**两套完全不同的请求通道**，混用会失败：

### 通道 A：明文 REST（`Request::request`，addr `0x624d14`）

- Body 就是普通 JSON，**不加密、不签名**
- 只靠请求头
- 用于：模型表、配置、bot 列表、建号、支付校验、`/common/img/create`（同步文生图）

### 通道 B：加密信封（`Request::_createGPTSign` addr `0x8d9758` + `aesEncryption` addr `0x8d9da0`）

- Body = `{"bundle", "security", "bundleId", "imageUrls"?}`
- `security` = 明文 JSON 的 AES 密文（hex）
- 用于：所有 SSE 聊天、文件问答、异步文生图、上传

---

## 3. 通道 B 详解

### 3.1 请求体

```json
{
  "bundle":   "com.aichatmaster.chat.gp",
  "security": "<AES hex>",
  "bundleId": "com.aichatmaster.chat.gp",
  "imageUrls": null
}
```

`imageUrls` 仅当业务参数里带了它才外挂到外层（`_createGPTSign` 末尾单独赋值）。

### 3.2 AES 参数（静态确认 @ `0x8d9da0`）

| 项 | 值 |
|---|---|
| 算法 | AES-128 |
| 模式 | **CBC**（`AES(key)` 默认 `AESMode.cbc`，枚举常量 `Obj!AESMode@e163a1`） |
| 填充 | PKCS7 |
| Key | `Ka7Ya98107EdGXQa` |
| IV | `yc0q2icx1oq4lijm` |
| 输出 | `Encrypted.base16()` → **小写 hex** |

```python
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
hexstr = AES.new(b"Ka7Ya98107EdGXQa", AES.MODE_CBC, b"yc0q2icx1oq4lijm") \
            .encrypt(pad(plain.encode(), 16)).hex()
```

### 3.3 明文 JSON 结构

在业务参数基础上追加 5 个字段：

| 字段 | 生成规则 |
|---|---|
| `bundle` | `com.aichatmaster.chat.gp`（常量） |
| `nonce` | 32 位随机串，字母表 `qwertyuiopasdfghjklzxcvbnmQAZXSWEDCVFRTGBNHYUJMKIOLP1234567890` |
| `version` | `2.6.8` |
| `timestamp` | **秒级** Unix 时间戳（代码里 `_getCurrentMicros()` 后连除两次 1000） |
| `signature` | 见下 |

### 3.4 签名算法（静态确认 @ `0x8d9758`）

重现的 Dart 逻辑：

```dart
final data = jsonDecode(jsonEncode(params));      // 类型归一化
data['bundle']    = 'com.aichatmaster.chat.gp';
data['nonce']     = _randomStr();                 // 32 位
data['version']   = appVersion;                   // 2.6.8
data['timestamp'] = seconds;

var keys = data.keys.toList()
  ..remove('language')  ..remove('type')      ..remove('voice')
  ..remove('needVoice') ..remove('imageUrls') ..remove('botPrompt')
  ..remove('userId')    ..remove('needSearch')..remove('tonePrompt');   // 可选 without 再删
keys.sort();                                       // 字典升序
var s = '';
for (final k in keys) s += '$k=${data[k]}';        // 用 & 连接
data['signature'] = sha1(utf8(s + 't6KeG6aKR5pm65oWn5aqS6LWE57O757ufS2V2aW4uWWFuZw')).toString();
```

即：

```
raw  = "k1=v1&k2=v2&..."      # 排除上表字段，键名字典升序
sign = sha1(raw + SALT)        # hex 小写
SALT = t6KeG6aKR5pm65oWn5aqS6LWE57O757ufS2V2aW4uWWFuZw
```

**易踩的两个坑**：

1. **值必须按 Dart 字符串插值渲染**：`true/false`（不是 `True/False`）、`null`（不是 `None`）、列表 `[a, b]`、Map `{k: v}`。用 Python 的 `str()` 会让签名对不上。
2. **不要塞服务端未识别的字段**。服务端签名集合是**白名单**：它只把「自己认识的、且非空的」字段纳入签名。
   - 加 `chatType: 1` → 服务端不纳入 → `签名失败`
   - 加 `botId: 0` → 服务端纳入 → 通过
   - 传 `conversationId: ""` → 服务端当空值丢弃 → 签名不匹配
   实测：`{"question":"hi"}` 通过；`{"question":"hi","conversationId":""}` 失败；`{"question":"hi","conversationId":"<uuid>"}` 通过。

### 3.5 请求头（`_createHeader` addr `0x654bb8`）

| Header | 值 |
|---|---|
| `UserType` | `app_user` |
| `content-language` | `zh_CN` |
| `content-type` | `application/json` |
| `x-bundle-id` | `com.aichatmaster.chat.gp` |
| `x-app-version` | `2.6.8` |
| `x-language` | 语言码（`en`/`zh`…） |
| `x-device-type` | `android` |
| `x-device-id` | 16 位 hex 设备号（**可任意伪造**，服务端不校验真实性） |
| `x-sys-type` | `android` |
| `x-sys-version` | 系统版本 |
| `x-country` | 国家码 |
| `x-user-id` | 用户 ID，匿名时为空串 |

> 没有 `Authorization`、没有 Cookie。**身份就是 `x-device-id`**，且服务端并不验证它与真实设备绑定。

---

## 4. 端点矩阵

### 4.0 图片 / 文件 / 语音 能力的最终判定

| 能力 | 端点 | 判定 | 细节 |
|---|---|---|---|
| 文件上传 | `POST /app/upload` | ✅ **可用，无鉴权** | multipart 字段名 `file`；外层同时带 `bundle/security/bundleId`；返回 CDN URL + ossId |
| 文生图（异步） | `POST /common/img/async/create` | ❌ **需 VIP** | `code:-3 "Your vip has expired, please recharge"`，对所有 `draw` 模型一致 |
| 文生图（同步） | `POST /common/img/create` | ❌ 不可用 | 恒返回 `code:500 "Server exception"`；参数按 `{botId,prompt,model,style:"natural",mac}` 构造，换 botId/模型均无效 |
| 读图问答 | `POST /imageAi/readImageSeeAnswer` | ⏳ 待验证 | 端点存在；签名需额外排除 `question`/`version`/`botId`（`_createGPTSign(params, without: [...])`，已静态确认 @`0x9022e4`），但实测仍 `Signature verification failed`，说明服务端签名集合还有未识别差异 |
| 语音音色 | `/voiceManager/voiceTypeList` `/voiceList` | ✅ **目录可读** | 音色为 Azure TTS（`az:Ollie` 等） |
| 语音合成 | 聊天流 `needVoice` | ⏳ 未打通 | `needVoice` 必须传**整数 1**（布尔会报 `Can not cast Boolean to Integer`）；带 `needVoice=1&voice=az:Ollie` 时聊天正常但**流内不返回音频**，推测音频走独立通道 |
| 文档问答 | `/botchat/readAndGetSummaryAndAnswerThis` `/aiFile/...` | ⏳ 待验证 | 上传已通，二次链路未测 |

### 4.1 已实测可用

| Method | Path | 通道 | 关键参数 | 实测结果 | 证据 |
|---|---|---|---|---|---|
| POST | `/common/sse/chat` | 加密 | `question, conversationId, type="1", needSearch, language, aiVersion` | **200 + 真实流式出字** | 已验证 |
| POST | `/botchat/noAuth/sse/chat` | 加密 | `botId, question, conversationId` | 200，与上面共用同一额度池 | 已验证 |
| GET | `/model/modelConfig` | 明文 | `language` | 200，返回 9 个对外模型 + 247 项能力表 | 已验证 |
| GET | `/appOther/platform/getConfigByKey` | 明文 | `key` | 200，服务端配置（额度/价格/开关） | 已验证 |
| GET | `/mb/getGroups` | 明文 | `local, bundleId` | 200，分组 + 应用（bot）目录 | 已验证 |
| GET | `/cai/bot/base/getAdvertBotList` | 明文 | `bundleId, language` | 200，推荐 bot（id=20 Learning Assistant，botModel GPT-4o） | 已验证 |
| POST | `/mb/createNewUser` | 明文 | `deviceMac, bundleId, bundleVersion` | 200 `{"code":200,"msg":"ok"}`，不返回 userId、不发 Cookie | 已验证 |
| POST | `/app/upload` | 加密信封 + multipart | form 字段 `file`（**外层再带 bundle/security/bundleId**） | **200 无鉴权上传成功**：`{"url":"https://d2y0uux9dbhvzm.cloudfront.net/file-<uuid>.png","fileName":"file.png","ossId":"..."}` | 已验证 |
| GET | `/voiceManager/voiceTypeList` | 明文 | **`bundle`**（不是 bundleId）+ `language` | 200，语音类型（`en_female`/`en_male`…，`bundle` 字段列出全部白标包名） | 已验证 |
| POST | `/voiceManager/voiceList` | 明文 | `bundle, language` | 200，音色表；`voiceId` 形如 `az:Ollie` / `az:Ada`（Azure TTS 音色） | 已验证 |

### 4.2 已定位未逐一验证

| Method | Path | 用途 | 状态 |
|---|---|---|---|
| POST | `/cai/bot/base/groupAndbotInfoList` | bot 分组明细 | 待验证（需 `bundleId`） |
| GET | `/cai/bot/user/myBotList` | 我的 bot | 待验证 |
| POST | `/botchat/readAndGetSummaryAndAnswerThis` | 文档问答 | 待验证 |
| POST | `/botchat/noAuth/readAndGetSummaryAndAnswerThis` | 匿名文档问答 | 待验证 |
| POST | `/aiFile/readAndGetSummaryAndAnswerThis` | 文件问答 | 待验证 |
| POST | `/imageAi/readImageSeeAnswer` | 读图问答 | 待验证（签名集合未对齐，见 4.0） |
| POST | `/common/img/create` | 同步文生图 | 已验证 **不可用**（恒 500） |
| POST | `/common/img/async/create` | 异步文生图 | 已验证 **需 VIP**（`code:-3`） |
| GET | `/common/img/async/getResult/{id}` | 异步取图（`drawTaskStatus,imageUrlList,drawErrorCode,failReason`） | 因上一步 VIP 拦截，未进入 |
| POST | `/longText/parse/summarizeAndQuery` | 长文本总结 | 待验证 |
| GET | `/user/chat/getSearchResult` | 联网搜索取页 | 待验证 |
| POST | `/voiceManager/voiceUseReport` | 语音使用上报 | 待验证 |
| POST | `/mb/buildPrompt` | 组装提示词 | 待验证 |
| POST | `/app/user/redeem` | 兑换码 | 待验证 |
| POST | `/app/new/order/google/latest/verify` | Google 内购校验 | **已验证返回 200 但空数组**（未校验成功态，见风险） |
| POST | `/app/new/order/google/compensation/verify` | 内购补单 | 待验证 |
| POST | `/mb/errorLog/report` | 日志上报 | 待验证 |

---

## 5. 聊天流协议（已验证）

请求：

```json
POST /common/sse/chat
{ "question": "hi", "conversationId": "<uuid>", "type": "1",
  "needSearch": false, "language": "en", "aiVersion": "GPT:4.1-mini" }
```

响应 `text/event-stream`，每一帧 `data: {json}`：

```json
{"code":0,"shouldTokenize":"0","message":"success",
 "data":{"error_code":null,"answer":"Hi","message_id":"229424865",
         "conversation_id":"c848a30a-...","agent_message_type":null,"references":""},
 "chatNum":0,"imgNum":0}
```

- `answer` 是**增量片段**，需自行拼接（"Hi" + "!" + " How"）
- 结束帧：`data: [DONE]`
- `message_id` 在同一轮内不变；`conversation_id` 为服务端回填的会话 ID（下一轮回传能否续上下文：**待验证**，额度恢复后复测）
- `shouldTokenize` 恒为 `"0"`（未观察到大模型 tokenize 流）；`chatNum`/`imgNum` 本轮实测恒 0（额度是否走它：待验证）
- `references` 联网搜索时为链接数组

错误也走同一通道，`code` 为负：

| 文案 | `error_code` | 含义 | 网关映射 |
|---|---|---|---|
| `Your free usage limit has been reached. Please upgrade to VIP to continue.` | `-2` | 免费额度耗尽 | 429 |
| `Please upgrade to VIP to continue.` | - | 该模型需 VIP | 403 |
| `The current model is offline. Please switch to a different model.` | - | 该 aiVersion 下线 | 503 |
| `Signature verification failed.` / `签名失败` | - | 签名集合不匹配 | 502 |
| `The length of the prompt cannot exceed 50000 characters.` | - | 超长 | 400 |
| `会话ID为空` | - | 缺 conversationId（botchat 链路） | 400 |
| `机器人获取失败` | - | botId 不存在 | 400 |

---

## 6. 模型目录

### 6.1 对外暴露（`/model/modelConfig` 的 `modelList`，9 个）

| aiVersion | 显示名 | 类型 | 搜索 |
|---|---|---|---|
| `GPT:4.1-mini` | GPT-4.1 Mini | CHAT | ✓ |
| `GPT:gpt-6-luna` | GPT 6 Luna | CHAT | ✓ |
| `GPT:gpt-5.6-luna` | GPT-5.6 Luna | CHAT | ✓ |
| `GPT:gpt-6-sol` | GPT-6 Cyber | CHAT | ✓ |
| `GEMINI:gemini-3-flash-preview` | Gemini 3.0 Flash | CHAT | ✓ |
| `GEMINI:gemini-3.8-flash` | Gemini 4 Pro | CHAT | ✓ |
| `GEMINI:gemini-3.7-flash` | Gemini 4 Carbon | CHAT | ✓ |
| `GEMINI:gemini-omni-1.1-flash` | Gemini Omni | VIDEO | ✓ |
| `BOLATU:gpt-4.1` | GPT-4.1 | CHAT | ✓ |

### 6.2 后端能力表（`capacityList`，247 项）

服务端把**全部**后端模型能力都吐给了客户端，而 App 只展示 9 个。直接调未展示的 `aiVersion` 也能被受理（受 VIP 闸门限制）。

供应商前缀：`GPT` `BOLATU` `GEMINI` `XAI` `BAIDU` `DOUBAO` `DEEPSEEK` `DEEPSEEK_OFFICIAL` `OPEN_ROUTER` `QIANWEN` `KIMI` `GLM` `LLAMA3` `IFLYTEK` `MINIMAX` `KLING` `VEO` `RUNWAY` `PIXVERSE` `FLUX` `SD` `MJ` `DALL_E` `GOOGLE` `GPT_IMAGE_1` `BYTEPLUS` `STEPFUN`…

能力标签：`chat` / `file` / `image`（读图）/ `voice` / `draw`（文生图）/ `video`。

全量清单见 `model_matrix.json`（247 项 + 分类）。

### 6.3 实测分类（R2 干净重扫，145 个 chat 模型）

> R1 首次扫描时把「额度耗尽」误判成「需 VIP」，矩阵被污染。R2 用轮换出口（3×50 条预算）重扫，
> 并区分 `free usage limit` 与 `upgrade to VIP` 两条文案，结果如下。全量清单见 `MODELS.md`。

| 分类 | 数量 |
|---|---|
| **FREE（可直接用）** | **74** |
| VIP（服务端要求订阅） | 56 |
| EMPTY（多模态/绘图模型走 chat 通道返回空） | 11 |
| OFFLINE（服务端配置下线） | 4 |

**免 VIP 可用的代表性模型**：

```
GPT:4.1-mini  GPT:gpt-5.1  GPT:gpt-5.2  GPT:gpt-5.4  GPT:gpt-5.6-luna  GPT:gpt-6-luna
GEMINI:v2.5-flash  GEMINI:v3.0-pro  GEMINI:gemini-3-flash-preview  GEMINI:v1.5-pro
BOLATU:gpt-4.1  BOLATU:gpt-5  BOLATU:gpt-5-mini  BOLATU:gpt-5-nano  BOLATU:gpt-5.1/5.2/5.4
BOLATU:gemini-2.0-flash  BOLATU:gemini-3-pro-preview
BOLATU:claude-haiku-4-5  BOLATU:claude-haiku-5-5  BOLATU:claude-sonnet-4-20250514
BOLATU:grok-3  BOLATU:grok-4  BOLATU:grok-4.1  BOLATU:grok-4-1-fast-*
DEEPSEEK:v3  DEEPSEEK:v3-0324  DEEPSEEK:v3.2-no-thinking  CLAUDE:v4
XAI:grok-4  XAI:grok-4.20-beta-*  XAI:v4
OPEN_ROUTER:anthropic/claude-haiku-4.5  OPEN_ROUTER:step-3.5-flash …
```

**需 VIP 的代表性模型**：`Claude Opus/Sonnet 5 系`、`GPT:gpt-6-astra`、`GPT:gpt-6-sol`、`GPT:gpt-5.5`、`Gemini 3.5~4 系`、`grok-4.5~4.7`。

> 注意：`GPT:gpt-6-sol` 返回 EMPTY 而 `BOLATU:gpt-6-sol` 需 VIP —— 同模型不同路由不同策略，**调用前建议逐模型探测一次**。

---

## 7. 免费额度与风控

### 7.1 服务端配置（已验证）

```
GET /appOther/platform/getConfigByKey?key=gai_free_message
→ {"code":200,"data":"{ \"free_message\":5 }"}

GET ...?key=gai_free_switch
→ {"code":200,"data":"{ \"ios\":{\"enable\":\"true\"},\"gp\":{\"enable\":\"true\"} }"}
```

App 端对应 `freeMessageCountProvider` / `load free message config error`。
⚠️ 这个 `5` 只是**客户端展示用**的试用引导值，**不是服务端真实放行量**（见 7.2）。

### 7.2 实测：每出口 IP 精确 50 条（已验证）

用 4 个独立出口 IP 做对照实验：

| 出口 IP | 连续成功条数 | 第 N+1 条 | 换新 device-id 后 |
|---|---|---|---|
| `38.180.75.197` | ≥ 41（提前停止） | 未触限 | 通过 |
| `216.106.179.46` | ≥ 41（提前停止） | 未触限 | 通过 |
| `5.61.51.28` | **50** | 第 51 条 → `free usage limit` | **仍被拦** |
| `185.141.57.84`（本机默认出口，曾被 247 次扫描打穿） | 约 15 条成功后即被拦 | — | 仍被拦 |

**结论：**

- 额度维度 = **出口 IP**。同一出口换全新 `x-device-id` 依然被拦 ⇒ 与设备无关。
- 单 IP 额度 = **50 条对话**（`5.61.51.28` 精确到 51 条触发）。
- `/common/sse/chat` 与 `/botchat/noAuth/sse/chat` **共用同一额度池**。
- 加 `userId` / `deviceMac` 字段不重置。
- 触发后返回 `error_code=-2`；拦截持续观察 90 分钟未恢复，**重置周期待验证**（配置里 `tokens2.lastGrantDailyTime` 暗示按天）。

> 方法论提醒：第一次扫描时把额度耗尽后的响应误判成「需 VIP」（两者文案都含 upgrade to VIP），
> 导致 247 项矩阵被污染。**必须先区分 `free usage limit`（额度）与 `upgrade to VIP`（模型门槛）两条文案。**

### 7.3 真正的风险点

1. **VIP 是服务端校验**：高端模型（Claude / GPT-6 / Gemini Pro）无法绕过；`/app/new/order/google/latest/verify` 虽返回 200，但 `validSubscribed` 为空数组 ⇒ 伪造内购收据不可行（未做进一步攻击验证，也不建议做）。
2. **文生图需要 VIP**：`/common/img/async/*` 直接返回 `code:-3 Your vip has expired`，所有 `draw` 模型一致。
3. **`/mb/createNewUser` 不构成账号体系**：不返回 userId、不发 Cookie。
4. **`/app/upload` 完全无鉴权**（已验证），会往对方 CDN 写文件 —— 属对方资源滥用风险点，仅作能力记录。
5. **额度按 IP ⇒ 单渠道吞吐 = 50 × IP 数**。这是可量化的经济模型，也是该渠道唯一可行的用法。

---

## 8. 踩坑表

| 现象 | 真实原因 | 修法 |
|---|---|---|
| `签名失败` / `Signature verification failed` | 1) 值渲染用了 Python 的 `True/None`；2) 多带了服务端不认识的字段；3) 传了空字符串字段 | 按 Dart 插值渲染；只发白名单字段；不要传 `""` |
| `Request method 'POST' not supported` | 该端点是 GET（`/model/modelConfig`、`/mb/getGroups`、`/appOther/platform/getConfigByKey`） | 换 GET + query |
| `Required request parameter 'language' ... is not present` | 必填 query | 补 `language`；`/mb/getGroups` 的必填名是 **`local`** 不是 language |
| `The device MAC cannot be empty` | 给通道 A 端点塞了加密体 | 通道 A 用明文 JSON；且该端点即使传对字段也只回 `ok`，无实际收益 |
| `The current model is offline` | `aiVersion` 不在服务端启用列表 | 查 `capacityList` 并避开 `OFFLINE` |
| 大量 `SSL: UNEXPECTED_EOF_WHILE_READING` | 本机必须走 `<HTTP_PROXY>`；python `requests` 复用连接会被代理掐 | 显式 `proxies=` + `Connection: close`；或固定连接池 + 重试（实测 20 连接稳定） |
| 加 `chatType` 后签名失败 | 服务端签名白名单不含 `chatType` | 不带该字段 |
| `conversationId` 传空串 → 签名失败 | 空值被服务端丢弃 | 传真实 UUID |

---

## 9. 未验证 / 剩余风险

| 项 | 状态 |
|---|---|
| 额度重置周期（是否日更、几点） | 待验证（观察到 90 分钟未恢复；需跨天或长期观察同一 IP） |
| 模型矩阵 | ✅ 145 个 chat 模型已判（74 FREE / 56 VIP / 11 EMPTY / 4 OFFLINE），剩 60 个低频/绘图类未扫 |
| 文生图是否独立额度 | 不必验证 —— 已确定直接 VIP 拦截（`code:-3`） |
| 读图问答 `/imageAi/readImageSeeAnswer` | 待验证（签名集合未对齐，见 §4.0） |
| 文档问答（`/botchat/*`、`/aiFile/*`） | 待验证（上传已通，二次链路未测） |
| 语音合成 TTS | 未打通（流内无音频，推测走独立通道） |
| 联网搜索 `needSearch` + `/user/chat/getSearchResult` | 待验证（参数已读，未实跑） |
| 多轮上下文记忆（复用 `conversationId`） | 待验证 |
| 长上下文上限 | 已验证存在 `50000 字符` 提示阈值，真实截断行为待验证 |
| `shouldTokenize` / `chatNum` / `imgNum` 语义 | 待验证（实测恒 `"0"` / `0`） |
| iOS 变体是否同协议 | 未做（仅 Android APK） |
| 上游是否有 IP 黑名单（大量并发后） | 未观察到；本轮压测含 145 次真实生成，未触发额外限制，但**不能据此断言安全** |
