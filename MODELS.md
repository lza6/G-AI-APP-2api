# 模型可用性实测清单

共扫描 **145** 个 chat 模型（按供应商优先级排序），结果分布：

| 分类 | 数量 | 含义 |
|---|---|---|
| FREE | 74 | 直接可用，真实出字 |
| VIP | 56 | 服务端要求订阅 |
| EMPTY | 11 | 返回空（多模态/绘图模型走 chat 通道） |
| OFFLINE | 4 | 服务端配置下线 |
| ERR | 0 | 网络异常（代理抖动，非模型问题） |
| QUOTA | 0 | 出口 IP 额度耗尽时无法判定 |

## 可用模型（FREE）明细

| 模型 | 典型延迟 |
|---|---|
| `BOLATU:claude-haiku-4-5-20251001` | 5.6s |
| `BOLATU:claude-haiku-5-5` | 3.42s |
| `BOLATU:claude-sonnet-4-20250514` | 2.41s |
| `BOLATU:gemini-2.0-flash` | 3.36s |
| `BOLATU:gemini-2.5-flash-preview-04-17` | 2.62s |
| `BOLATU:gemini-3-flash-preview` | 2.87s |
| `BOLATU:gemini-3-pro-preview` | 3.9s |
| `BOLATU:gemini-3.1-flash-lite-preview` | 2.11s |
| `BOLATU:gemini-3.5-flash-lite` | 2.3s |
| `BOLATU:gpt-4.1` | 5.11s |
| `BOLATU:gpt-4o-all` | 2.64s |
| `BOLATU:gpt-5` | 3.6s |
| `BOLATU:gpt-5-mini` | 3.25s |
| `BOLATU:gpt-5-nano` | 3.44s |
| `BOLATU:gpt-5.1` | 3.77s |
| `BOLATU:gpt-5.2` | 3.08s |
| `BOLATU:gpt-5.4` | 2.78s |
| `BOLATU:gpt-5.6-luna` | 2.57s |
| `BOLATU:gpt-6-luna` | 2.86s |
| `BOLATU:grok-3` | 3.09s |
| `BOLATU:grok-3-copy` | 3.43s |
| `BOLATU:grok-3-copy2` | 7.43s |
| `BOLATU:grok-3-reasoner` | 8.94s |
| `BOLATU:grok-3-reasoner-copy` | 5.16s |
| `BOLATU:grok-4` | 4.67s |
| `BOLATU:grok-4-1-fast-non-reasoning` | 6.92s |
| `BOLATU:grok-4-1-fast-reasoning` | 13.5s |
| `BOLATU:grok-4-fast-non-reasoning` | 8.44s |
| `BOLATU:grok-4-fast-reasoning` | 6.27s |
| `BOLATU:grok-4.1` | 5.4s |
| `CLAUDE:v4` | 2.3s |
| `DEEPSEEK:v3` | 2.45s |
| `DEEPSEEK:v3-0324` | 2.32s |
| `DEEPSEEK:v3-1-250821` | 9.59s |
| `DEEPSEEK:v3.2-no-thinking` | 3.12s |
| `DEEPSEEK_OFFICIAL:deepseek-v4-flash` | 2.23s |
| `GEMINI:gemini-3-flash-preview` | 2.47s |
| `GEMINI:gemini-3.1-flash-lite-preview` | 2.37s |
| `GEMINI:gemini-3.5-flash-lite` | 2.05s |
| `GEMINI:v1.5-flash` | 2.35s |
| `GEMINI:v1.5-pro` | 2.47s |
| `GEMINI:v2.0-flash` | 2.72s |
| `GEMINI:v2.5-flash` | 2.72s |
| `GEMINI:v3.0-pro` | 3.62s |
| `GEMINI:v3.5-16` | 2.64s |
| `GPT:4.1-mini` | 4.6s |
| `GPT:4o` | 3.34s |
| `GPT:gpt-5-nano` | 3.17s |
| `GPT:gpt-5.1` | 3.32s |
| `GPT:gpt-5.2` | 2.77s |
| `GPT:gpt-5.4` | 3.33s |
| `GPT:gpt-5.6-luna` | 3.15s |
| `GPT:gpt-6-luna` | 2.77s |
| `GPT:v3.5` | 4.53s |
| `GPT:v4` | 4.56s |
| `GPT:v5` | 3.59s |
| `GPT:v5-mini` | 3.85s |
| `OPEN_ROUTER:anthropic/claude-haiku-4.5` | 3.23s |
| `OPEN_ROUTER:anthropic/claude-haiku-5.5` | 2.4s |
| `OPEN_ROUTER:google/gemma-4-31b-it` | 1.95s |
| `OPEN_ROUTER:mistral-small-creative` | 2.4s |
| `OPEN_ROUTER:mistralai/mistral-nemo` | 2.65s |
| `OPEN_ROUTER:step-3.5-flash` | 3.41s |
| `OPEN_ROUTER:step-3.5-flash-free` | 2.87s |
| `XAI:grok-4` | 3.82s |
| `XAI:grok-4-1-fast-non-reasoning` | 2.32s |
| `XAI:grok-4-1-fast-reasoning` | 3.6s |
| `XAI:grok-4-copy` | 4.44s |
| `XAI:grok-4-copy2` | 4.04s |
| `XAI:grok-4-fast-non-reasoning` | 2.25s |
| `XAI:grok-4-fast-reasoning` | 4.27s |
| `XAI:grok-4.20-beta-non-reasoning` | 2.97s |
| `XAI:grok-4.20-beta-reasoning` | 4.1s |
| `XAI:v4` | 3.82s |

## 分类明细

**FREE**（74）：`BOLATU:claude-haiku-4-5-20251001`、`BOLATU:claude-haiku-5-5`、`BOLATU:claude-sonnet-4-20250514`、`BOLATU:gemini-2.0-flash`、`BOLATU:gemini-2.5-flash-preview-04-17`、`BOLATU:gemini-3-flash-preview`、`BOLATU:gemini-3-pro-preview`、`BOLATU:gemini-3.1-flash-lite-preview`、`BOLATU:gemini-3.5-flash-lite`、`BOLATU:gpt-4.1`、`BOLATU:gpt-4o-all`、`BOLATU:gpt-5`、`BOLATU:gpt-5-mini`、`BOLATU:gpt-5-nano`、`BOLATU:gpt-5.1`、`BOLATU:gpt-5.2`、`BOLATU:gpt-5.4`、`BOLATU:gpt-5.6-luna`、`BOLATU:gpt-6-luna`、`BOLATU:grok-3`、`BOLATU:grok-3-copy`、`BOLATU:grok-3-copy2`、`BOLATU:grok-3-reasoner`、`BOLATU:grok-3-reasoner-copy`、`BOLATU:grok-4`、`BOLATU:grok-4-1-fast-non-reasoning`、`BOLATU:grok-4-1-fast-reasoning`、`BOLATU:grok-4-fast-non-reasoning`、`BOLATU:grok-4-fast-reasoning`、`BOLATU:grok-4.1`、`CLAUDE:v4`、`DEEPSEEK:v3`、`DEEPSEEK:v3-0324`、`DEEPSEEK:v3-1-250821`、`DEEPSEEK:v3.2-no-thinking`、`DEEPSEEK_OFFICIAL:deepseek-v4-flash`、`GEMINI:gemini-3-flash-preview`、`GEMINI:gemini-3.1-flash-lite-preview`、`GEMINI:gemini-3.5-flash-lite`、`GEMINI:v1.5-flash`、`GEMINI:v1.5-pro`、`GEMINI:v2.0-flash`、`GEMINI:v2.5-flash`、`GEMINI:v3.0-pro`、`GEMINI:v3.5-16`、`GPT:4.1-mini`、`GPT:4o`、`GPT:gpt-5-nano`、`GPT:gpt-5.1`、`GPT:gpt-5.2`、`GPT:gpt-5.4`、`GPT:gpt-5.6-luna`、`GPT:gpt-6-luna`、`GPT:v3.5`、`GPT:v4`、`GPT:v5`、`GPT:v5-mini`、`OPEN_ROUTER:anthropic/claude-haiku-4.5`、`OPEN_ROUTER:anthropic/claude-haiku-5.5`、`OPEN_ROUTER:google/gemma-4-31b-it`、`OPEN_ROUTER:mistral-small-creative`、`OPEN_ROUTER:mistralai/mistral-nemo`、`OPEN_ROUTER:step-3.5-flash`、`OPEN_ROUTER:step-3.5-flash-free`、`XAI:grok-4`、`XAI:grok-4-1-fast-non-reasoning`、`XAI:grok-4-1-fast-reasoning`、`XAI:grok-4-copy`、`XAI:grok-4-copy2`、`XAI:grok-4-fast-non-reasoning`、`XAI:grok-4-fast-reasoning`、`XAI:grok-4.20-beta-non-reasoning`、`XAI:grok-4.20-beta-reasoning`、`XAI:v4`

**VIP**（56）：`BOLATU:claude-fable-5`、`BOLATU:claude-fable-5-1`、`BOLATU:claude-opus-4-7`、`BOLATU:claude-opus-4.8`、`BOLATU:claude-opus-5-5`、`BOLATU:claude-sonnet-4-6`、`BOLATU:claude-sonnet-5`、`BOLATU:claude-sonnet-5-5`、`BOLATU:gemini-2.5-pro-preview-03-25`、`BOLATU:gemini-3.1-pro-preview`、`BOLATU:gemini-3.5-flash`、`BOLATU:gemini-3.6-flash`、`BOLATU:gemini-3.7-flash`、`BOLATU:gemini-3.8-flash`、`BOLATU:gemini-4-argon`、`BOLATU:gpt-5.5`、`BOLATU:gpt-5.6-sol`、`BOLATU:gpt-6-astra`、`BOLATU:gpt-6.1-sol`、`BOLATU:gpt-6.1-terra`、`BOLATU:grok-4.20-beta-non-reasoning`、`BOLATU:grok-4.20-beta-non-reasoning-copy`、`BOLATU:grok-4.20-beta-reasoning`、`BOLATU:grok-4.20-beta-reasoning-copy`、`BOLATU:grok-4.5`、`BOLATU:grok-4.6`、`BOLATU:grok-4.7`、`DEEPSEEK:doubao-seed-1-8`、`DEEPSEEK:v3.2-thinking`、`DEEPSEEK_OFFICIAL:deepseek-v4-pro`、`GEMINI:gemini-3.1-pro-preview`、`GEMINI:gemini-3.5-flash`、`GEMINI:gemini-3.6-flash`、`GEMINI:gemini-3.7-flash`、`GEMINI:gemini-3.8-flash`、`GEMINI:gemini-4-argon`、`GEMINI:v2.5-pro`、`GPT:gpt-5.5`、`GPT:gpt-5.6-sol`、`GPT:gpt-6-astra`、`GPT:gpt-6-sol`、`GPT:gpt-6.1-sol`、`GPT:gpt-6.1-terra`、`OPEN_ROUTER:anthropic/claude-fable-5`、`OPEN_ROUTER:anthropic/claude-fable-5.1`、`OPEN_ROUTER:anthropic/claude-opus-4.8`、`OPEN_ROUTER:anthropic/claude-opus-5.5`、`OPEN_ROUTER:anthropic/claude-sonnet-5`、`OPEN_ROUTER:anthropic/claude-sonnet-5.5`、`OPEN_ROUTER:claude-opus-4.6`、`OPEN_ROUTER:claude-opus-4.7`、`OPEN_ROUTER:claude-sonnet-4.6`、`OPEN_ROUTER:nvidia/nemotron-3-ultra-550b-a55b`、`XAI:grok-4.5`、`XAI:grok-4.6`、`XAI:grok-4.7`

**OFFLINE**（4）：`GEMINI:v1.0-pro`、`GEMINI:v3.5`、`GEMINI:v4`、`OPEN_ROUTER:mistral-small-3.2-24b-instruct`

**EMPTY**（11）：`BOLATU:gpt-6-sol`、`BOLATU:grok-3-deepsearch`、`BOLATU:grok-3-deepsearch-copy`、`BOLATU:grok-3-deepsearch-copy2`、`DEEPSEEK:R1`、`DEEPSEEK:v3.2-no-thinking-online`、`GPT:4o-mini`、`GPT:o1-mini`、`GPT:v3.5-16`、`GPT:v4.0`、`XAI:grok-2-vision`
