# 逆向过程与证据（R1）

记录「怎么破的」而不是「破了什么」，方便复现与复用方法。协议细节见 `PROTOCOL.md`。

---

## 1. 侦察（10 分钟）

```bash
unzip -l "G.AI v2.6.8 (Premium).apk"        # 923 个文件 → 判定 Flutter
# 关键特征：assets/flutter_assets/、lib/arm64-v8a/libapp.so、libflutter.so
# 只有 arm64-v8a（无 x86_64）→ 模拟器必须支持 arm 转译，直接放弃动态路线
```

Python 扫 `libapp.so` 取 URL，一次命中上游域名：

```
https://api.chatgai.fun
https://api.chatgeine.cc/redirect/webHome?bundle=com.aichatmaster.chat
```

**证据等级：已验证**（真实解析 APK 得到）

## 2. blutter 反编译（15 分钟，一次成功）

```bash
cd <WORKDIR>/blutter
python blutter.py <apk>/lib/arm64-v8a <WORKDIR>/blutter_out
```

输出 `Dart version: 3.6.2, Snapshot: f956f595…`，产出：

| 产物 | 用途 |
|---|---|
| `asm/<package>/<file>.dart` | 带**字符串字面量注释**的反汇编，最有价值 |
| `objs.txt` | 静态对象池（枚举值、常量 Map 都在这里） |
| `pp.txt` | 对象池全量（含所有 String 常量） |
| `blutter_frida.js` | 动态挂钩脚本（本轮未用） |

**关键判断**：`asm/ai_chat/...` 目录里是 `env.dart`、`api/request.dart`、`providers/auth.dart` 这样的**原始文件名** ⇒ APK 未做 Dart 混淆 ⇒ 协议逻辑可以直接照读，不需要动态调试。

> 这是本案例最大的效率来源：**先判断有没有混淆**，有混淆才上 frida，没混淆静态一遍过。

## 3. 定位签名链（核心 20 分钟）

在 `asm/ai_chat/api/request.dart` 里 `grep '^  _ '` 拿到方法清单，一眼看到：

```
_createGPTSign   0x8d9758
aesEncryption    0x8d9da0
_randomStr       0x901244
_createHeader    0x654bb8
```

`blutter` 的反汇编注释里带常量字符串，于是签名算法是**逐条读出来的**，不是猜的：

```asm
0x8d9844: r2 = "bundle"        →  data['bundle'] = ...
0x8d984c: r3 = "com.aichatmaster.chat.gp"
0x8d9864: r2 = "nonce"
0x8d987c: r2 = "version"
0x8d98d8: r2 = "timestamp"
0x8d9c04: r16 = "t6KeG6aKR5pm65oWn5aqS6LWE57O757ufS2V2aW4uWWFuZw"   ← 盐
0x8d9c64: bl  #0xbe01a4  ; [package:crypto/src/hash.dart] Hash::convert  ← SHA1
0x8d9c78: r2 = "signature"
```

AES 参数同理（`0x8d9dc4` / `0x8d9ddc`）：

```asm
r2 = "Ka7Ya98107EdGXQa"    →  Key
r2 = "yc0q2icx1oq4lijm"    →  IV
```

模式不是读代码猜的，而是查构造函数的默认参数对象：`AES()` 传入 `Obj!AESMode@e163a1`，在 `objs.txt` 里查到该对象 `off_10: "cbc"` ⇒ **CBC**。

## 4. 三条经验教训（方法层面）

### 4.1 反汇编里的 `stp A, B` 顺序不能想当然

`_StringBase::+` 被渲染成 `stp x16, x3, [SP]` + `bl`，看不出谁是接收者。**验证方式是找同文件里语义已知的拼接**：`_randomStr` 里 `str += char` 是显然的，由此确定「先 push 的是参数、后 push 的是接收者」，推出签名串是 `"k=v" + 前面累积` 的正常顺序，而不是反序。

### 4.2 别急着穷举，先用上游错误信息做二进制搜索

一开始按「排序 + 拼接 + 盐」实现，上游回 `签名失败`。此时**不要**盲目扩大穷举组合（我穷举了 32 种组合，全部失败，浪费 5 分钟）。改用**单字段二分**：

```
{"question":"hi"}                        → 通过（被 会话ID为空 拦住）
{"question":"hi","chatType":1}           → 签名失败
{"question":"hi","conversationId":""}    → 签名失败
{"question":"hi","conversationId":"<uuid>"} → 通过
```

三次实验就得出真因：**服务端只把「认识的、非空的」字段纳入签名**。这是算法本身完全正确、但输入集合不对的经典情况。

### 4.3 「错误文案」比「错误码」信息量大得多

上游是 Java/Spring，校验失败会直接说缺哪个参数：

```
Required request parameter 'language' ... is not present
Required request parameter 'bundleId' ... is not present
Request method 'POST' not supported
The current model is offline. Please switch to a different model.
```

顺着这些文案把端点矩阵补齐，比读代码更快。注意部分中文错误是 **GBK 字节**（UTF-8 解码会变 `ǩ��ʧ��`），要按 `latin1→gbk` 还原。

## 5. 环境坑（本机特有，可复用）

| 坑 | 现象 | 解法 |
|---|---|---|
| 代理隧道掐连接 | `requests` 连续请求报 `SSL: UNEXPECTED_EOF_WHILE_READING` | 显式 `proxies={...}` + `Connection: close`；httpx 侧用固定连接池 + 重试 |
| `httpx 0.28` API 变更 | `AsyncClient(proxies=...)` 直接 TypeError | 改 `proxy=` |
| 后台进程清理 | 用 `*server.py*` 模糊匹配 `Stop-Process`，**误杀本机约 20 个其它项目的 demo** | 按端口定位 PID：`(Get-NetTCPConnection -LocalPort <port>).OwningProcess`，绝不用文件名模糊匹配 |
| 后台日志看不到 | `cmd \| tail` 会缓冲到进程结束 | `nohup python -u x.py > x.log 2>&1`，不带管道 |

## 6. 证据台账

| 结论 | 证据类型 | 具体 |
|---|---|---|
| AES 参数正确 | 已验证 | 上游成功解密我们构造的 `security`，并对内容做了业务校验 |
| 签名算法正确 | 已验证 | 上游不再回 `签名失败`，进入模型调度阶段 |
| 无鉴权 | 已验证 | 仅带 `x-device-id` 即返回真实模型输出 |
| 模型目录 | 已验证 | `/model/modelConfig` 返回 9 + 247 项 |
| 免费额度耗尽 | 已验证 | 连续成功 ~15 条后同 IP 全量 `error_code=-2` |
| 额度按 IP | 合理推断 | 换全新 `x-device-id` / 加 `userId` / 加 `deviceMac` 均不重置 |
| 额度重置周期 | 待验证 | 观察 70 分钟未恢复 |
| 199 个模型可用性 | 待验证 | 扫描中途额度耗尽，分类被污染 |
| 多轮上下文 | 待验证 | 需额度恢复 |
| 文生图/文件/语音 | 待验证 | 端点与参数已静态确认，未实跑 |

## 7. 未走的路（说明为什么没走）

- **动态 frida**：APK 仅 arm64，本机只有 x86_64 AVD；且静态未混淆，动态收益为零。
- **Dart 源码重建**（reFlutter / Doldrums）：本案例不需要，类名/方法名/常量全在。
- **伪造内购绕过 VIP**：`/app/new/order/google/latest/verify` 返回空校验数组，但进一步攻击属于越界，未做。
