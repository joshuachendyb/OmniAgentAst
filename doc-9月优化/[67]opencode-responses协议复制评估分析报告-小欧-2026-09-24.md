# [67] opencode-responses协议复制评估分析报告

**文档名**: [67]opencode-responses协议复制评估分析报告-小欧-2026-09-24.md  
**编写人**: 小欧（资深后端开发/全架构设计与分析）  
**创建时间**: 2026-09-24 10:02:14  
**更新时间**: 2026-09-24 10:24:34  
**版本**: v1.5  
**状态**: 仅分析，未改动任何代码  
**关联文档**: `[66]Zen模型接入设计-小欧-2026-09-23.md`  
**对照源码**: `F:\agenttool\opencode-1.18.31\packages\llm\src\protocols\openai-responses.ts`（1022 行）

---

## 版本历史

| 版本 | 时间 | 签名 | 修改简介 |
|------|------|------|---------|
| v1.0 | 2026-09-24 10:02:14 | 小欧 | 首版：openai-responses.ts 完整性判定、可复制性评估、双方架构对照、真缺口清单、三方案对比、三堂会审预审、建议决议 |
| v1.1 | 2026-09-24 10:06:49 | 小欧 | 第七章由"建议决议"改写为"方案 A / 方案 C 各自代码改动范围"：逐文件、逐函数、逐行号精确清单 + 明确不改清单 + 测试用例明细 + 版本与验证；原建议决议 4 条移入 7.4 保留 |
| v1.2 | 2026-09-24 10:11:01 | 小欧 | 第六章由"三堂会审预审"改写为 4 小节：6.1 现状系统流程、6.2 方案 A 实施要点与逻辑流程、6.3 方案 C 实施要点与逻辑流程、6.4 优劣点对比；原三堂会审预审表原文保留于 6.4 末尾 |
| v1.3 | 2026-09-24 10:19:08 | 小欧 | 10遍精读核查修文档设计错误：①统一六/七章行号基准为 10:19:08；②五章5.3补与六/七章清单的衔接句；③六章/七章精修措辞与版本升 v1.3 |
| v1.4 | 2026-09-24 10:21:54 | 小欧 | 内联章节化：1.2 后新增 1.3/1.4/1.5（/responses 现状要点→逐项对照→小结缺口），补章节号与排版，原内容一字不丢，上下逻辑打通 |
| v1.5 | 2026-09-24 10:24:34 | 小欧 | v1.4 全文10遍核查修3处：①1.4.2请求构造行事实错误（"不转换请求体"→"简化转换"，与1.3.1/2.2/C14对齐）；②1.4.1终帧"三态"→"三值"消歧义；③1.3.2非JSON透传归属主循环（client_sdk.py:424-426） |

---

## 一、结论先行

### 1.1 它是不是独立的协议处理代码？

**是，而且是"协议全家桶"，不只是流解析。** `openai-responses.ts`（1022 行）四层一体：

| 层 | 内容 | 行数(约) |
|----|------|---------|
| 请求构造 | `lowerMessages`/`lowerOptions`/`fromRequest`：把内部统一消息模型**全量降维**成 Responses `input[]`（system/user/assistant/reasoning/item_reference/function_call/function_call_output 全形态） | 250+ |
| 流解析状态机 | `step()` 分派 20+ 事件名，含 reasoning summary_index 状态机、hosted tools 8 种、工具 ToolStream、终帧三态 | 450+ |
| 协议/传输装配 | `Protocol.make` + HTTP SSE 路由 + **WebSocket `response.create` 路由** | 150+ |
| Schema/错误 | Effect Schema 全量字段校验、`providerErrorMessage` 双形态错误提取、context-overflow 分类 | 150+ |

它不是"我们的 `responses_stream.py` 的放大版"——**架构物种不同**：它是 opencode 多协议框架（anthropic-messages / openai-chat / gemini / bedrock…）里平级的一个 protocol 插件，输出统一 `LLMEvent` 流，喂它自己的消费端。

### 1.2 要不要完整复制一个？

**不要完整复制。推荐"协议边缘补全"，拒绝"整模块搬运"。** 三条硬理由：

1. **范式不可移植**：TS + Effect（fiber/Schema/Stream）→ Python 无等价运行时，"复制"实为 **1000+ 行重写**，违背本项目"能复制就复制、不重写"铁规的反面——重写必引入新错误。
2. **架构不对接**：它的输出是 `LLMEvent`；我们 `BaseAIService` 整条链吃的是 **chat 形 `choices[0].delta`**。完整复制后还差一座"LLMEvent→chat 转换桥"，等于把上游解析链也重做，爆炸半径覆盖 base_service/react_cycle/前端——违反 KISS-DIRECT 与"前端迎合后端"。
3. **一半能力用不上（YAGNI）**：hosted tools（web_search/code_interpreter/mcp…）、reasoning `encrypted_content` 回放、`item_reference`、`store:false` 过滤、WebSocket 传输、prompt_cache_key/service_tier——muse 实网一个都不发；我们也没有 OpenAI 官方 key 的全量 Responses 场景。

**同时纠正一个隐含误解**：完整复制 ≠ 质量更高。我们当前真实缺口只有 **三块协议边缘**（见第四章），用约 100–150 行增量即可对齐官方语义；剩下 800+ 行是"别的物种的器官"。

### 1.3 /responses 端点现状处理要点（代码取证）

> 代码锚点：`backend/app/llm/responses_stream.py` + `client_sdk.py:216-225,407-436`。本节为现状实现逐项取证，为第二章架构对照与第四章缺口清单提供事实底座。

#### 1.3.1 协议判定与路由（`_adapt_request` 单点）

- `endpoint_for`：`muse-` 前缀 → `/responses`，其余走 `/chat/completions`（`adapters/opencodeZen.py:118-124`）
- `_is_responses = endpoint.endswith("/responses")`，全链唯一判定点（`client_sdk.py:222`）
- `to_responses_body`：`messages→input`、双层 `tools→flat`、删 `tool_choice/parallel_tool_calls`、强制 `stream:true`

#### 1.3.2 事件归一（`_norm_responses_delta`，`responses_stream.py:59-109`）

- 文本增量 `output_text.delta` → `content`；推理增量 `reasoning_summary_text.delta` → `reasoning`（独立通道）
- 文本整段快照（`output_text.done`/`content_part.done`/`output_item.done{message}`，`str`/`list` 兼容）→ `content_full`（保底源）
- 工具链四形态：`output_item.added{function_call}` 建档（`is_new`）＋ `function_call_arguments.delta` 增量 ＋ `done`/`output_item.done` 整段覆盖（`full=True`）
- 无产出事件（`ping`/`created` 等）→ `{}` 丢弃；非 JSON 行由主循环原样透传（防丢，`client_sdk.py:424-426`，非本函数职责）

#### 1.3.3 折叠去重状态机（`_fold_emit_delta` + `_DeltaFoldState:155-188`）

- 增量优先：出过增量后整段快照丢弃（防文本拼 4 次）；全程无增量时快照作唯一来源（保底）
- 工具稳定 `index`：按 `item_id` 分配（并行不串槽）；建档帧只带 `id`/`name`，参数由增量/快照帧供
- 参数增量按 `index` 去重，整段快照仅未出过增量时 `emit`

#### 1.3.4 终帧单遍评估（`_responses_completed_eval:130-152`）

- `response.completed` 单遍扫描 `output`：文本快照 ＋ `finish_reason` 推断（见 `function_call→tool_calls`，`incomplete_details→length`，否则 `stop`，因该端点无 `stop_reason` 字段）＋ `usage` 提取

#### 1.3.5 双消费端挂载

- `request_stream` 主循环：`responses` 事件逐帧归一为 `chat` 形 `choices[0].delta` 行，`BaseAIService` 既有解析链零改动读通（`client_sdk.py:407-436`）
- `_request_via_stream_collect`：纯 `chat` 消费（`client_sdk.py:323-324`），供 `force_stream` 非流式入口

### 1.4 现状处理的逐项对照（照 `responses_stream.py` 实证）

#### 1.4.1 要点级对照（我们的处理是否正确）

| 要点 | 官方/实测 | 我们的实现 | 结论 |
|------|-----------|-----------|------|
| 文本增量 | `output_text.delta` 为唯一增量源 | 直取 `delta` 产出 `content` | ✅ |
| 快照防重 | `done` 类事件带全量 | 增量优先，全程无增量才用快照保底 | ✅（正确且必要） |
| 工具链 | `added→delta→done` 序列 | 建档带 `call_id`、参数增量拼接、`done` 覆盖去重 | ✅ |
| 终帧 | `status`/`incomplete_details`/`usage`，无 `stop_reason` | `_responses_completed_eval` 单遍推断三值（`stop`/`length`/`tool_calls`）+ 取 `usage` | ✅ |
| 推理 | `reasoning_summary_text.delta` | 独立 `reasoning` 通道，不污染 `content` | ✅ |
| 未知事件 | 官方有数十种（`refusal`/`file_search` 等） | 归 `{}` 丢弃、非 JSON 透传 | ✅（`muse` 实测不发） |

#### 1.4.2 维度级逐项比对（opencode vs 我们）

| 维度 | opencode `openai-responses.ts` | 我们 `responses_stream.py` + `_adapt_request` | 结论 |
|------|-------------------------------|-----------------------------------------------|------|
| 定位 | 完整协议实现（请求构造 + 响应解析一体，Effect 状态机） | 仅响应归一层；请求侧靠 `_adapt_request` 改端点/`gate`，不做 `message→input` 全量 `lowering` | 分工不同 |
| 请求构造 | `lowerMessages` 把 `chat` 消息全量转换为 Responses `input[]`（`system`/`user`/`assistant`/`function_call_output`/`reasoning`/`item_reference` 全覆盖，含 `store=false` 时 `reasoning` 过滤） | 简化转换（`messages` 拼纯文本 `input` + `tools` 拍平 `flat`，见 1.3.1，非全量 `item` 图 `lowering`）；`force_stream` 非流式入口走流收集 | 他们重、我们轻（`zen` 端点收简化形） |
| 文本增量 | `response.output_text.delta` → `textDelta` | 同名事件 → `{"content"}` ✅ | 一致 |
| 文本快照保底 | 无（只认 `delta`） | `output_text.done` / `content_part.done` / `output_item.done(message)` / `completed` 四处快照、全程无 `delta` 才用 | 我们更全（`muse` 实测需保底） |
| 推理增量 | 5 个事件（`reasoning_text`/`summary`/`summary_text` × `delta`/`done` + `summary_part added/done`），带 `summary_index` 状态机 | 仅 `reasoning_summary_text.delta` 一个实证事件名（`v3.7.1` 删了猜测别名） | 他们按官方全集，我们按 `muse` 实测子集 |
| 工具链 | `output_item.added→start`、`function_call_arguments.delta→append`、`output_item.done→finish`；`id` 取 `call_id ?? item_id` | `added` 建档(`id=call_id`)、`args.delta`/`done`、`item.done` 整段覆盖；`id` 恒 `call_id`，不用 `item_id` 兜底（`C15/17/20` 回归证否） | 关键分歧点：他们容错兜底，我们实测否决兜底（`done` 帧会覆盖权威 `call_id`） |
| 并行工具 index | `ToolStream` 按 `item_id` 建流 | `_DeltaFoldState.tool_idx` 按 `item_id` 分配稳定 `index` | 机制等价 ✅ |
| 终帧 finish_reason | `completed`/`incomplete→finish(reason)`、`failed→providerError`；`incomplete_details.reason→length`/`content-filter`，有 `function_call→tool-calls` | 仅 `completed` 单遍扫描：`incomplete_details` 非空→`length`、有 `function_call→tool_calls`、否则 `stop` | 核心推断逻辑一致；他们多 `incomplete`/`failed`/`content_filter` 细分 |
| usage | `mapUsage` 拆 `cached`/`reasoning` 子集 | `completed` 帧直取 `response.usage` 透传 | 位置一致 ✅ |
| 终帧事件集 | `TERMINAL = {completed, incomplete, failed}` 三态 | 仅 `completed`；`failed`/`incomplete`/`error` 归 `{}` 丢弃 | 已知边界（`muse` 实网只发 `completed` 链） |
| hosted tools | 8 种（`web_search`/`code_interpreter`/`mcp`…）展开为 `toolCall`+`toolResult` 对 | 不处理 | 非 `muse` 场景，YAGNI ✅ |
| 输出形态 | 统一 `LLMEvent` 流（`textDelta`/`toolInputStart`/`toolCall`/`finish`…） | 归一为 OpenAI `chat` 形 `choices[0].delta` 行，让 `base_service` 既有解析链一字不改 | 目标不同：我们是兼容层，他们重写消费端 |

#### 1.4.3 一句话结论

协议核心（文本/工具/终帧/`finish_reason`/`usage` 推断）对得上，实现不是一回事：`opencode` 是"从零实现完整 Responses 协议客户端"（请求转换+全事件状态机+`LLMEvent` 输出）；我们是"给 `zen` `/responses` 端点做响应侧最小归一"（请求直发 `chat` 形、事件按 `muse` 实测收敛子集、输出 `chat` 形喂既有链路）。他们多覆盖的（`reasoning` 全事件、`incomplete`/`failed`、`hosted tools`、`content_filter`）都是 `muse` 实网未发或我们已知丢弃的边界。

### 1.5 待补缺口（若按官方全集对齐）

> 与第四章缺口清单同源，此处为 1.4 结论的直接推论；实施见第六章 6.2 / 第七章 7.1。

1. `response.incomplete` / `response.failed` / `error` 事件处理（现在丢弃）—— 对应缺口①
2. `content_filter` 的 `finish_reason` 细分 —— 对应缺口②
3. `reasoning` 事件别名（若 `muse` 将来发 `reasoning_text.delta` 等）—— 对应缺口③


## 二、双方架构对照（为什么不能整搬）

### 2.1 谁在哪里

```
opencode 世界:
  LLMRequest(内部模型) ──lower*──▶ Responses body ──HTTP/WS──▶ 服务端
       ▲                                          │
  LLMEvent 流 ◀──step()状态机◀── SSE 事件 ────────┘
       │
  自家 agent 消费（重写过）

我们 (OmniAgentAs):
  chat body ──_adapt_request(to_responses_body 简化转换)──▶ /responses ──▶ 服务端
       ▲                                                      │
  chat 形 delta 行 ◀──responses_stream 归一◀── SSE 事件 ───────┘
       │
  BaseAIService 既有 chat 解析链【一字不改】
```

### 2.2 关键差异矩阵

| 维度 | opencode openai-responses.ts | 我们 responses_stream + adapter | 评估 |
|------|------------------------------|--------------------------------|------|
| 定位 | 通用 Responses **客户端协议插件** | zen/muse **专用响应归一桥** | 物种不同 |
| 请求构造 | 全量 item 图降维（含多轮 assistant 回放） | `to_responses_body`：messages **拼成纯文本 input** + tools 拍平 | **我们有意简化**（muse 收 string input；完整 item 图是 OpenAI 官方形态） |
| 消费端 | 自研 LLMEvent | 喂既有 chat 链 | 我们的选择是"零侵入上游" |
| 流事件覆盖 | 20+ 事件全按官方 | 约 10 事件按 muse 实测子集 | **有缺口**（见第四章） |
| 终帧 | completed/incomplete/failed + error 四路 | 仅 completed | **缺口①** |
| finish_reason | max_output_tokens→length、content_filter→content-filter、未知 reason 兜底 | incomplete_details 粗判一律 length | **缺口②** |
| reasoning 事件 | 5 个别名 + summary_index 状态机 | 仅 `reasoning_summary_text.delta` 1 个 | **缺口③** |
| 错误帧 | failed/error 双形态提 message/code 上抛 | 丢 `{}` | **缺口①子项** |
| hosted tools | 8 种 | 无 | YAGNI（muse 不发） |
| WebSocket | 有 | 无（httpx SSE only） | YAGNI |
| 请求侧温度等 | `temperature`/`top_p` 进 body | `to_responses_body` 丢 temperature/seed（v3.3 既有，实网 200） | 已知非缺陷 |

### 2.3 一个必须点破的深层事实

我们的 `to_responses_body` 把多轮 messages **拍平成一段 text**——这在 **muse/zen 上实测 200**（E2E 已证），但它**不是** OpenAI 官方 Responses 的标准 `input[]` 多轮形态。含义：

- 若定位 = "接好 muse 免费层" → 简化转换是**正确的专用设计**，完整复制 lowerMessages 反而过度。
- 若定位 = "将来通吃 OpenAI 官方 /responses" → 请求侧也欠账（不止流侧），那是**另一个量级的工程**，应单独立项，而不是"顺手复制一个 ts 文件"。

**当前 [66] 的定位是前者**（zen/muse 接入），故完整复制既不必要也不合架构。

---

## 三、opencode 侧关键实现取证（对照依据）

### 3.1 终帧与错误（对照我方缺口①）

`openai-responses.ts` L613：

```
TERMINAL_TYPES = {response.completed, response.incomplete, response.failed}
```

- `completed` / `incomplete` → `onResponseFinish` 发 finish 事件（带 usage/finish_reason）
- `failed` → `onResponseFailed` 发 provider-error（提取 `response.error` 与顶层 `code/message`）
- 流中 `error` 事件 → `onError` 同样上抛

我方 `client_sdk.request_stream` 仅识别 `response.completed`；`incomplete`/`failed`/`error` 一路归 `{}` 丢弃。

### 3.2 finish_reason 映射（对照我方缺口②）

`mapFinishReason`（L523-529）：

- `incomplete_details.reason == max_output_tokens` → `length`
- `== content_filter` → `content-filter`
- reason 空且有 function_call → `tool-calls`，否则 `stop`
- 未知 reason → `unknown`（或 tool-calls）

我方 `_responses_completed_eval`：`incomplete_details` 非空一律 `length`，无 `content_filter` 分支。

### 3.3 reasoning 事件别名（对照我方缺口③）

`step()`（L925-936）识别：

- delta：`response.reasoning_text.delta` / `response.reasoning_summary.delta` / `response.reasoning_summary_text.delta`
- done：对应 3 个
- 另有 `reasoning_summary_part.added/done`（summary_index 状态机）

我方 `_norm_responses_delta` 仅识别 `response.reasoning_summary_text.delta`（v3.7.1 注明"唯一实证事件名，删猜测别名"）。

### 3.4 错误消息提取（opencode 双形态）

`providerErrorMessage`（L896-902）：顶层 `event.message/code` 与嵌套 `event.response.error.*` 二选一，`code: message` 拼接，可识别 `context_length_exceeded`。

---

## 四、真缺口清单（该补的"协议边缘"）

按官方语义 + opencode 实现对照，**与实网风险相关**的只有：

| # | 缺口 | 现状 | 风险 | 补全落点 |
|---|------|------|------|---------|
| ① | `response.incomplete` / `response.failed` / 流中 `error` 帧 | 丢弃 → 流可能无终帧静默截断 | 中（截断难诊断；failed 无错误文案） | 主循环终帧分支扩为四态；failed/error 提取 message 上抛（映射 LLMResponseError 或 stream_error） |
| ② | finish_reason 细分 | incomplete_details 非空→一律 length；无 content_filter | 低–中（content_filter 被误标 length，下游截断语义错） | `_responses_completed_eval` 按 reason 映射：max_output_tokens→length、content_filter→content_filter、有 function_call→tool_calls |
| ③ | reasoning 事件别名 | 仅 1 个实证名 | 低（muse 若升级发 `reasoning_text.delta` 则推理丢失） | `_norm_responses_delta` 补 2 个别名 → 同归 `{"reasoning"}` |

### 4.1 明确不补的（YAGNI，写死防反复）

- hosted tools 8 种（web_search/code_interpreter/mcp/computer_use…）
- reasoning `encrypted_content` 回放与 `item_reference`
- WebSocket `response.create` 传输
- 请求侧全量 `lowerMessages` item 图降维
- Effect Schema 校验层、prompt_cache_key/service_tier/include 等官方选项
- `store:false` 过滤链

依据：muse 实网不发、我们无 OpenAI 官方全量场景、[66] 定位为 zen/muse 专用接入。

---

## 五、方案对比（供北京老陈拍板）

### 5.1 方案 A：协议边缘补全（推荐）

- **做法**：只动 `responses_stream.py` + `client_sdk` 终帧分支，补第四章 ①②③；估计 +80~150 行、单文件为主。
- **优点**：对齐官方语义；爆炸半径最小；chat 链零改动；符合 KISS/YAGNI/复用优先；可 TDD 加 C23+ 用例。
- **缺点**：仍非"通用 Responses 客户端"——接受（定位如此）。
- **版本**：PATCH 级（v3.7.2）。

### 5.2 方案 B：完整复制 openai-responses.ts 语义（拒绝）

- **做法**：Python 重写请求降维 + 全事件状态机 + 可能引入 LLMEvent 中间层。
- **缺点**：约 1500–2000 行重写（违背"复制不重写"）；需动 base_service 或加巨型转换桥；测试面爆炸；80% 能力 muse 用不到；Effect 范式硬套必出隐性 bug。
- **结论**：**否决**——"看起来完整"的短视做法，实际是高风险架构漂移。

### 5.3 方案 C：中间态——responses 提升为一等协议（暂缓，清单见六/七章）

- **做法**：承认第三种异构协议，预留 protocol 分派位（`responses_stream.py` 头注释已写死这个未来："新增同级兄弟模块并按 protocol 能力位分派"），但本次不实施。
- **结论**：**作为演进方向记录**，等出现第二个 /responses 型协议（如 Anthropic /v1/messages）或需要通吃 OpenAI 官方时再启动。若北京老陈批准，则按第六章 6.3 与第七章 7.2 清单实施（前置依赖方案 A 已合入，见 7.2.1）。

---

## 六、系统流程与方案 A / 方案 C 实施要点（4 小节）

> 行号基准：2026-09-24 10:24:34 本地代码。三方案关系回顾：B 已否决；A 独立可实施；C 前置依赖 A 已合入（C 的流程 = A 流程 + 分派位改造，不重画归一细节）。

### 6.1 现状系统流程（v3.7.1，未补缺口）

#### 6.1.1 端到端调用链（现状）

```
react_step / summary
  └─ call_llm_with_fallback (llm_call.py L225)          # L2 重试 + FC→Text 降级
       └─ call_llm_stream (llm_call.py L82)             # 累积 content/reasoning/tool_calls/finish_reason
            └─ BaseAIService.request_stream (base_service.py L354)   # L1 HTTP 重试(≤max_retries) + SSE→StreamChunk
                 └─ LLMClient.request_stream (client_sdk.py L360)    # 组 body + 发 HTTP + 协议分派归一
                      ├─ chat 通道:   事件行原样 yield (L413–414)
                      └─ responses 通道: 事件 → chat 形 delta 行 (L420–436)
```

非流式入口：`LLMClient.request()` → zen `force_stream()==True` → `_request_via_stream_collect`（L292）→ **复用同一 `request_stream`** 累积为 `choices[0].message` 同构 dict——**流式与非流式共用一条归一主循环**。

#### 6.1.2 请求侧（发送前）现状

```
_build_request_body (chat 形 body)
  └─ _adapt_request (client_sdk.py L216)  # 单点, 流式/非流式共用
       ① ensure_gate_body     # zen: 补 bash/read stub + stream:true; 默认原样
       ② endpoint_for(model)  # muse- 前缀→/responses; 其余→/chat/completions
       ③ _is_responses = _endpoint.endswith("/responses")   # L222 URL 后缀嗅探 ← 协议判定现状
       ④ if _is_responses: to_responses_body  # messages 拼纯文本 input + tools 拍平 flat
       ⑤ 返回 (endpoint, body, per_request_headers, _is_responses: bool)
  └─ httpx.stream(POST) / (非流式 force_stream 不走 post)
       ≥400 → _raise_http_error (error_message_map 可覆盖文案)
```

#### 6.1.3 响应侧（SSE 逐帧）现状 — responses 分支

`client_sdk.request_stream` L408–436，`_is_responses==True` 时：

| 事件 type | 现状处理 | 结果 |
|-----------|---------|------|
| `response.output_text.delta` | `_norm` → `{"content"}` → `_fold` | ✅ emit chat delta |
| `response.output_text.done` / `content_part.done` / `output_item.done(message)` | `_norm` → `{"content_full"}` | ✅ 仅全程无 delta 时保底 emit |
| `response.reasoning_summary_text.delta` | `_norm` → `{"reasoning"}` | ✅ emit `reasoning_content`（**仅此 1 个事件名**） |
| `response.output_item.added{function_call}` | `_norm` → tool 建档(is_new) | ✅ emit tool_calls id/name |
| `function_call_arguments.delta/done`、`output_item.done{function_call}` | `_norm` → tool 增量/整段 | ✅ 按 index 去重 emit |
| **`response.completed`** | `_responses_completed_eval` L130 | ✅ 可选 content_full 补发 + `finish_reason`/`usage` 终帧 |
| **`response.incomplete`** | 落入 `_fold(_norm→{})` | ❌ **静默丢弃**（缺口①）— 无终帧、无 finish_reason、截断文本可能丢快照 |
| **`response.failed`** | 同上 | ❌ **静默丢弃**（缺口①）— 硬失败无错误文案，上游只见流"正常结束" |
| **`error`（流中错误帧）** | 同上 | ❌ **静默丢弃**（缺口①） |
| reasoning 别名 `reasoning_text.delta` / `reasoning_summary.delta` | `_norm→{}` | ❌ **丢推理**（缺口③） |

`_responses_completed_eval` 的 finish_reason 现状逻辑（L136–147）：

```
incomplete_details 非空? ──是──▶ fr = "length"   # 不区分 content_filter（缺口②）
        │否
        ▼
扫 output: 有 function_call → "tool_calls"; 否则 → "stop"
        │
        └── 且 incomplete_details 非空时【不扫 output】→ 截断流的 content_full 快照也丢
```

#### 6.1.4 归一之后（下游，现状已就绪、零改动依赖）

```
chat 形 SSE 行
  └─ base_service.request_stream 消费:
       _extract_usage        (L387) → usage_data
       _extract_finish_reason(L391) → finish_reason   # 四值 stop/length/tool_calls/content_filter 均可透传
       _extract_tool_calls   (L400) → 跨 chunk 累加器
       _parse_sse_data       (L429) → StreamChunk(content/reasoning/tool_calls) yield
       末帧 L486 → StreamChunk(is_done, usage, finish_reason, truncated)
       异常: LLMResponseError → L489 直接 raise 穿透
             其它 → L491 L1 重试 / stream_error chunk
  └─ call_llm_stream 消费 StreamChunk → 累积 + _finish_reason (L131)
  └─ call_llm_with_fallback:
       LLMResponseError → L2 指数退避重试 (L262) → 耗尽 → FC 降级 Text (L275)
```

#### 6.1.5 现状流程的三个病灶（对应第四章缺口）

1. **终帧只认 completed**：incomplete/failed/error 三态丢弃 → 上游把"截断/硬失败"当"正常完读"。
2. **finish_reason 粗判**：无 `content_filter` 分支；有 incomplete_details 时跳过 output 扫描。
3. **reasoning 单事件名**：官方 3 个别名只认 1 个。

判定源仍是 **URL 后缀嗅探**（L222 `endswith("/responses")"）——这是 6.3 方案 C 要换掉的架构点，与上述三病灶正交。

---

### 6.2 方案 A：实施要点与系统逻辑流程（v3.7.2，独立实施）

#### 6.2.1 实施要点（对应第七章 7.1，此处只讲"做什么、为何够"）

| # | 要点 | 落点 | 一句话理由 |
|---|------|------|-----------|
| A-① | **终帧四态**：completed/incomplete 共用 eval 出 finish 帧；failed/error 提取消息后 `raise LLMResponseError` | `client_sdk` L427 三段式 + `responses_stream` 新增 `_responses_error_message` | 硬失败必须上抛既有异常类型，复用 L489 穿透 → L2 → 降级的**现成容错链**，不新造 stream_error 协议 |
| A-② | **finish_reason 四分支**：`content_filter` > `length`(incomplete_details) > `tool_calls` > `stop`；eval 内**始终扫 output**（修截断丢快照） | `_responses_completed_eval` 逻辑体重写 | 对齐 opencode `mapFinishReason`；下游 `_extract_finish_reason`/`_build_answer_response` 本就收 content_filter，**零下游改动** |
| A-③ | **reasoning 三别名**：`reasoning_summary_text.delta`（实证）+ `reasoning_text.delta` + `reasoning_summary.delta`（官方）→ 同归 `{"reasoning"}` | `_norm_responses_delta` L75 判断改元组 | 归一片段形态不变 → `_fold`/主循环/下游零改动 |
| A-④ | **TDD C23–C27** + 回归 C14/C19b/C21/C22 | `test_client_sdk_adapter.py` | 锁四态、content_filter、上抛、别名 |

**不实施项**（YAGNI，第四章已写死）：hosted tools、encrypted reasoning、WebSocket、请求侧 lowerMessages、改 `base_service`/`error_classifier`/前端。

#### 6.2.2 方案 A 实施后的系统逻辑流程

**请求侧：与 6.1.2 完全相同**（`_adapt_request`、URL 嗅探、`to_responses_body` 均不动）。

**响应侧主循环（`request_stream` L408–436 改后逻辑）：**

```
async for SSE line:
  [DONE] → break
  _is_responses == False → yield 原行; continue          # chat 通道, 零变化
  解析 JSON; 非 dict → 原样透传                           # 零变化
  │
  ├─ type ∈ {response.completed, response.incomplete}          ★ A-① 扩态
  │    _responses_completed_eval(ev)                           ★ A-② 四分支+始终扫 output
  │    ├─ content_full 且全程无 delta → yield {_chat_frame content}
  │    └─ yield {_chat_frame {}, finish_reason, usage}         # 终帧与 chat 同构
  │    continue
  │
  ├─ type ∈ {response.failed, error}                          ★ A-① 硬失败
  │    msg = _responses_error_message(ev)                      # 顶层/嵌套双形态, `code: message`
  │    raise LLMResponseError(message=msg, details={type})     # 不 yield, 直接打断生成器
  │    │
  │    ▼ (异常传播, 非数据流)
  │    base_service L489: except LLMResponseError → raise      # 穿透 L1, 不空转重试
  │    call_llm_stream L134: raise
  │    call_llm_with_fallback L262: L2 指数退避重试            # 有界
  │    耗尽 → L275 FC 降级 Text → 仍败 → _yield_error_response
  │
  └─ 其它事件 → _fold_emit_delta(_norm_responses_delta(ev))   # 含 A-③ 三别名
       ├─ 命中 → yield {_chat_frame delta}                     # content/reasoning_content/tool_calls
       └─ 未命中({}) → 丢弃                                   # 信令帧(response.created等)仍丢, 无害
```

**finish_reason 判定流（A-②，`_responses_completed_eval` 内）：**

```
扫一遍 output:
  记 content_full (首个 message 文本, str/list 兼容)
  记 has_fc (存在 function_call)
reason = incomplete_details.reason
  reason == "content_filter"  → fr = "content_filter"     ★ 新
  incomplete_details 非空(其它 reason/裸dict) → "length"   # 保 C19b
  else has_fc → "tool_calls"
  else → "stop"
usage = response.usage (若有) → 随终帧带出
```

**下游（base_service / llm_call / 前端）流程：零改动**——chat 形终帧与既有 `_extract_finish_reason`（已声明四值）、`StreamChunk.finish_reason`、`_build_answer_response(finish_reason=...)` 全部原样接通；collect 路径（L313 累积循环）自动继承同一主循环行为。

#### 6.2.3 方案 A 流程特征小结

- **改的是"事件→结果"的映射表**，不是管道形状：仍是 `_is_responses` 布尔二分、仍是"归一后喂 chat 链"。
- 新增的唯一控制流出口是 **failed/error 的 raise**——该出口走的是系统**最老、最稳**的 `LLMResponseError` 容错轨，不是新轨。
- 默认 provider（chat 直通）代码路径一行不进。

---

### 6.3 方案 C：实施要点与系统逻辑流程（v3.8.0，前置 A 已合入）

#### 6.3.1 实施要点（对应第七章 7.2）

| # | 要点 | 落点 | 一句话理由 |
|---|------|------|-----------|
| C-① | **协议能力位 `protocol_for(model)`**：基类恒 `"chat"`；zen `muse-` 前缀 → `"responses"` | `adapters/base.py` + `opencodeZen.py` | 把"协议是什么"从 URL 猜测升为**适配器声明**；第三协议来时只加枚举+兄弟模块 |
| C-② | **`endpoint_for` 改读 `protocol_for` 单源**：`muse-` 前缀判断全库仅剩 1 处 | `opencodeZen.endpoint_for` | 消除"端点判断"与"协议判断"双处前缀逻辑漂移 |
| C-③ | **`_adapt_request` 第 4 返回位 `bool→str`**：`_is_responses` 改 `_protocol`；删 L222 `endswith` 嗅探 | `client_sdk._adapt_request` | 分派权威从 URL 后缀换成能力位 |
| C-④ | **主循环三分派**：`chat` 直通 / `responses` 走 A 全逻辑 / **未知协议位 raise**（不静默当 chat） | `client_sdk.request_stream` L413 起 | 未知协议吞成 chat = 未来事故；显式失败可维护 |
| C-⑤ | **闸门**：`grep _is_responses` 全库 0 命中；`grep startswith("muse-")` 仅 protocol_for 1 命中 | 验证步骤 | 禁 backward 双轨（F8） |
| C-⑥ | TDD C28–C31 + `test_adapters` 基类/zen 断言；`[66]` 补协议位一节 | 测试+文档 | 锁"分派改造零行为变化" |

**C 明确不做**：不实现 Anthropic 等第三协议（座空着，YAGNI）；不重写 A 的归一逻辑；不动 `base_service`/前端/注册表。

#### 6.3.2 方案 C 实施后的系统逻辑流程

**请求侧（`_adapt_request` 改后）：**

```
_build_request_body (chat 形, 不变)
  └─ _adapt_request (L216)
       ① ensure_gate_body                    # 不变
       ② _protocol = adapter.protocol_for(model)     ★ C-① 权威判定(取代嗅探)
       │     base 默认 → "chat"
       │     zen + muse- → "responses"; zen 其它 → "chat"
       ③ _endpoint = adapter.endpoint_for(model)     ★ C-② 内部已改读 protocol_for
       │     protocol=="responses" → "/responses"
       │     else → "/chat/completions"
       ④ if _protocol == "responses": to_responses_body   # 条件从 bool 改 str, 语义同
       ⑤ 返回 (endpoint, body, headers, _protocol: str)    ★ 第 4 位类型变更
```

**响应侧主循环（三分派）：**

```
async for SSE line:
  [DONE] → break
  │
  ├─ _protocol == "chat"                                 ★ C-④ 分支一
  │    yield 原行; continue                              # 等价现状 L413–414
  │
  ├─ _protocol != "responses"                            ★ C-④ 分支二(未知)
  │    raise LLMResponseError(f"未知协议能力位: {_protocol}")
  │    # 死码防御: 当前枚举仅 2 值; 防未来加枚举忘加分支时静默透传
  │
  └─ _protocol == "responses"                            ★ C-④ 分支三
       ═══ 以下 = 6.2.2 方案 A 全部分支, 原样包进本分支, 零重写 ═══
       completed/incomplete → eval 四分支 → 终帧 yield
       failed/error         → _responses_error_message → raise LLMResponseError
       其它                 → _norm(含三别名) → _fold → delta yield
```

**归一之后的下游流程：与 6.1.4 / 6.2.2 完全一致，零改动。**

**调用方适配点（仅 2 处，第七章 C3 已列）：**

| 调用点 | 改前 | 改后 |
|--------|------|------|
| `request()` L282 | `_endpoint, body, _dyn_headers, _ = ...` | 同解包（第 4 位语义变为 str，本就不消费） |
| `request_stream` L398 | `_..., _is_responses = ...` | `_..., _protocol = ...`；L407 `_DeltaFoldState` 条件、L413 分派全改读 `_protocol` |

#### 6.3.3 方案 C 流程特征小结

- **改的是"谁来回答这是什么协议"**（判定源：URL 嗅探 → 能力位），不是改数据加工内容。
- 分支从 `bool 二分` 变 `str 三分`（多出的"未知"是防御分支，正常流量不进）。
- A 的四态终帧/四分支 finish_reason/三别名逻辑作为 `responses` 分支的**既有体**被整体保留——C 与 A 在流程上是**包含关系**（C = A + 分派座），不是并列替换。
- 第三协议接入时的目标流程：`protocol_for` 扩枚举 → 新建 `xxx_stream.py` 兄弟模块 → 主循环加第 4 分支 → 其余全链（base_service/llm_call/前端）继续零改动。

---

### 6.4 方案 A / 方案 C 优劣点对比

#### 6.4.1 方案 A

| | 内容 |
|---|------|
| **优点** | ① **病灶直击**：三缺口（终帧/finish_reason/reasoning）全部闭合，muse 实网截断与硬失败不再静默；② **爆炸半径最小**：2 源文件+测试，默认 provider 零影响；③ **复用最大化**：failed 走现成 `LLMResponseError` 容错链、finish_reason 走现成透传链，零新协议零新抽象；④ **可独立交付**：PATCH 级，不依赖架构改造；⑤ 下游/collect/前端零改动 |
| **缺点** | ① **判定源未换**：仍靠 `endswith("/responses")` URL 嗅探——第三协议将来还得再动 `_adapt_request`；② 仍非通用 Responses 客户端（定位使然，非缺陷）；③ failed→SERVER 分类可能带来 1 次有界 L2 空转（残余风险，已评估接受）；④ 若未来 zen 改端点路径但不改协议，嗅探会误判（C-② 单源化才能根除） |

#### 6.4.2 方案 C（含前置 A）

| | 内容 |
|---|------|
| **优点** | ① **A 的全部优点继承**（病灶闭合在 A 已做）；② **判定源根治**：能力位单源，端点/协议永不分叉，URL 路径怎么变都不影响分派；③ **第三协议就座**：新异构协议 = 加枚举+兄弟模块+一分支，`base_service` 以下整条消费链继续零改动（架构预留兑现）；④ **未知协议显式失败**：比静默当 chat 透传更安全；⑤ 结构清晰：`chat`/`responses` 分支对读代码者一目了然 |
| **缺点** | ① **不能独立发**：前置 A，总改动面 6 源文件+双测试+[66] 文档，验证面更大；② **`_adapt_request` 返回值类型变更**（bool→str）是接口语义变化，漏改调用点即事故（虽仅 2 处，仍需 grep 闸）；③ 当前**没有第二协议消费者**——能力位现在就位属"提前铺轨"，严格说是 YAGNI 边缘（换来的是消除嗅探的技术债）；④ MINOR 版本，按 4.4 需用户明确同意；⑤ 改动与 A 在同文件重叠，若 A 未合先做 C 会冲突 |

#### 6.4.3 对照总表与选型建议

| 维度 | 现状 (6.1) | 方案 A (6.2) | 方案 C (6.3) |
|------|-----------|--------------|--------------|
| 三病灶（终帧/finish_reason/reasoning） | ❌ 全在 | ✅ 全闭 | ✅ 全闭（依赖 A） |
| 协议判定源 | URL 后缀嗅探 | 仍是嗅探（不变） | **能力位单源** |
| 主循环分支 | bool 二分 | bool 二分 | **str 三分** |
| failed/error 去向 | 静默丢 | raise→L2→降级 | 同 A |
| 未知协议 | N/A（嗅探不出） | N/A | 显式 raise |
| 第三协议就绪 | ❌ | ❌ | ✅（座空着） |
| 改动源文件 | — | 2 | 6（含 A 重叠 2） |
| 可独立发 | — | ✅ PATCH | ❌ 依赖 A，MINOR |
| 下游链（base_service→前端） | — | 零改动 | 零改动 |

**选型建议（供北京老陈拍板，不代决）**：

- **只要治现在流血的病** → 只做 **A**，立即可实施。
- **既要治病又要还"URL 嗅探"这笔架构债、并给第三协议留座** → **A 先行、C 紧随**（两步走，避免同文件双改冲突）。
- B 仍否决。

#### 6.4.4 附：原第六章"三堂会审预审（针对方案 A）"原文保留（v1.1）

| 审 | 结论 |
|----|------|
| 合规 | 补协议边缘属"增强不退化"；默认 provider 不进 responses 分支，零影响；不引入 backward 双轨 |
| 合理 | 缺口按实网风险排序 ①>②>③；落点仍在既有两文件，无新抽象层（无注册表/无中间层） |
| 关联逻辑 | 上游 base_service 对 finish_reason/stream_error 已有消费（截断/错误 chunk），补 content_filter 与 failed 上抛**顺势接通**而非新增协议；下游 collect 路径自动受益（同一主循环） |

**残余风险**：failed/error 上抛类型需选对（建议 `LLMResponseError` → 穿透 fallback 重试，或映射 stream_error chunk），实施前再核 `error_classifier` 分类是否把 provider failed 误判为可无限重试——实施时验证，不改码前不下结论。（v1.2 补注：已读码确认 `error_classifier` L133–134 将 `LLMResponseError` 归 SERVER 可重试，最坏为 L2 有界重试后降级，非死循环——见 7.1.3 A2-3 链路核对表。）

---

## 七、方案 A / 方案 C 实施的代码改动范围（精确清单）

> 行号基准：2026-09-24 10:24:34 本地代码。两方案关系：**方案 A 独立可实施；方案 C 前置依赖方案 A 已合入**（C 不重复做 A 的三块缺口；若强行跳过 A 只做 C，则 C 范围 = 7.1 全部 + 7.2 增量，文件会重叠冲突，不推荐）。方案 B 已否决，不列改动范围。

### 7.1 方案 A：协议边缘补全（独立实施，v3.7.2）

#### 7.1.1 改动文件总表

| # | 文件 | 动作 | 预估行变化 |
|---|------|------|-----------|
| A1 | `backend/app/llm/responses_stream.py` | 修改 | 约 +35 / −8 |
| A2 | `backend/app/llm/client_sdk.py` | 修改 | 约 +18 / −3 |
| A3 | `backend/tests/test_client_sdk_adapter.py` | 修改（追加用例） | 约 +95 / −0 |
| A4 | 两源文件编辑历史 | 修改（追加行） | 含于 A1/A2 |

**明确不改**：`base_service.py`、`core.py`、`error_classifier.py`、`adapters/*`、`reasoning.py`、`llm_call.py`、前端全部、`FUNCTIONS.md`（无新建全局公用函数）、`[66]` 文档（对照决策节走单独批示，不绑 A 的代码提交）。

#### 7.1.2 A1 `responses_stream.py` 逐点改动

**A1-0 编辑历史（L7 下方追加一行）**
```text
# 编辑历史: 2026-09-24 小欧 v3.7.2 协议边缘补全: ①终帧扩 completed/incomplete 共用 eval + failed/error 提取错误消息; ②finish_reason 细分 content_filter; ③reasoning 事件补 reasoning_text.delta/reasoning_summary.delta 别名
```
模块说明 L4 中 `completed 终帧` 改为 `终帧四态(completed/incomplete/failed/error)`。

**A1-1 缺口③ reasoning 别名 — 函数 `_norm_responses_delta`（L59–109）**

- **定位**：L75 现为单事件判断。
- **改前**：
```python
if et == "response.reasoning_summary_text.delta":   # 唯一实证推理增量事件名 — 小欧 2026-09-24 v3.7.1 删猜测别名
    d = data.get("delta")
    return {"reasoning": d} if d else {}
```
- **改后**（三名并列；`reasoning_summary_text.delta` 保持为实证主名，另两个为官方别名补盲）：
```python
if et in ("response.reasoning_summary_text.delta",
          "response.reasoning_text.delta",
          "response.reasoning_summary.delta"):   # v3.7.2 补官方别名 — 小欧 2026-09-24
    d = data.get("delta")
    return {"reasoning": d} if d else {}
```
- **同步 docstring**：L65 `①推理增量 reasoning_summary_text.delta(唯一实证事件名)` 改为 `①推理增量 reasoning_summary_text.delta(实证) + reasoning_text.delta / reasoning_summary.delta(官方别名, v3.7.2)`。
- **不改**：`_fold_emit_delta` 的 reasoning 分支（L165–167）——归一片段形态不变，折叠层零改动。

**A1-2 缺口② finish_reason 细分 + incomplete 复用 — 函数 `_responses_completed_eval`（L130–152）**

- **函数名不改**（KISS：调用点仅 client_sdk L429 一处；改名无收益）。语义扩展为 **completed 与 incomplete 共用**。
- **改前核心逻辑（L136–147）**：
```python
fr = "stop"
if resp.get("incomplete_details"):
    fr = "length"
else:
    for oi in resp.get("output") or []:
        ...
```
- **改后核心逻辑**（修两个问题：content_filter 细分；有 incomplete_details 时也扫 output 取 content_full/工具标记，原逻辑该分支直接跳过扫描会导致截断流丢文本快照）：
```python
content_full = None
has_fc = False
for oi in resp.get("output") or []:
    if not isinstance(oi, dict):
        continue
    if oi.get("type") == "function_call":
        has_fc = True
    elif oi.get("type") == "message" and content_full is None:
        content_full = _first_output_text(oi.get("content"))
reason = (resp.get("incomplete_details") or {}).get("reason")
if reason == "content_filter":
    fr = "content_filter"
elif resp.get("incomplete_details"):
    fr = "length"          # max_output_tokens 及裸 incomplete_details（保 C19b 行为）
elif has_fc:
    fr = "tool_calls"
else:
    fr = "stop"
```
- **优先级（对齐 opencode `mapFinishReason`）**：`content_filter` > `length`（incomplete_details 非空）> `tool_calls` > `stop`。
- **C19b 兼容**：既有用例 `incomplete_details: {reason: "max_output_tokens"}` → 仍 `length`，不断言 `content_filter` 分支以外的映射。
- **docstring（L131–134）改写**：注明 completed/incomplete 共用、reason 四分支、output 扫描不再被 incomplete_details 短路。

**A1-3 缺口① 终帧 failed/error — 新增函数 `_responses_error_message`（插在 `_responses_completed_eval` 之后，约 L153）**

```python
def _responses_error_message(ev: Dict) -> str:
    """response.failed / error → 用户可读错误串 — 小欧 2026-09-24 v3.7.2
    对齐 opencode providerErrorMessage 双形态: 顶层 event.code/message 与嵌套 response.error.*,
    二者皆有则 `code: message` 拼接; 皆空回落固定文案。"""
    nested = (ev.get("response") or {}).get("error") or {}
    message = ev.get("message") or nested.get("message") or ""
    code = ev.get("code") or nested.get("code") or ""
    if message and code:
        return f"{code}: {message}"
    return message or code or "responses 流式请求失败(provider 未返回错误详情)"
```
- **依赖**：仅 dict 取值，无新 import（模块保持只依赖 json/typing）。
- **不新增** `TERMINAL_TYPES` 常量集：分派只有 client_sdk 一个消费点，两处 `in` 元组字面量直写，避免无消费者的中间抽象（YAGNI）。

#### 7.1.3 A2 `client_sdk.py` 逐点改动

**A2-0 编辑历史（L32 下方追加一行）**
```text
编辑历史: 2026-09-24 小欧 - [67]v3.7.2 协议边缘补全: ①request_stream 终帧分支由仅 completed 扩为 completed/incomplete(共用 eval 出 finish 帧) + failed/error(提取消息 raise LLMResponseError 穿透 fallback); ②import 增 LLMResponseError 与 _responses_error_message; ③finish_reason 新增 content_filter 语义由 eval 落地, 本文件零改解析链
```

**A2-1 import 两处**

- **L52 前后新增**（与既有 `from app.llm.core import …` 无循环：`core.py` 不 import `client_sdk`；`base_service` 同时 import 二者属既有事实）：
```python
from app.llm.core import LLMResponseError   # v3.7.2 responses failed/error 上抛 — 小欧 2026-09-24
```
- **L53–56 的 responses_stream 导入列表追加** `_responses_error_message`：
```python
from app.llm.responses_stream import (
    _chat_frame, _DeltaFoldState, _fold_emit_delta,
    _norm_responses_delta, _responses_completed_eval,
    _responses_error_message,   # v3.7.2 — 小欧 2026-09-24
)
```

**A2-2 终帧分派 — `request_stream` 内 L427–433**

- **改前**：
```python
if _ev.get("type") == "response.completed":
    _cfull, _meta = _responses_completed_eval(_ev)
    ...
    continue
```
- **改后**（三段：finish 双态 / error 双态 / 普通帧兜底不变）：
```python
_et = _ev.get("type")
if _et in ("response.completed", "response.incomplete"):
    # v3.7.2: incomplete 与 completed 共用 eval — 小欧 2026-09-24
    _cfull, _meta = _responses_completed_eval(_ev)
    if _cfull and not _state.saw_text_delta:
        yield _chat_frame({"content": _cfull})
    yield _chat_frame({}, finish_reason=_meta["finish_reason"], usage=_meta.get("usage"))
    continue
if _et in ("response.failed", "error"):
    # v3.7.2: 硬失败上抛, 走 base_service L489 穿透 → llm_call fallback — 小欧 2026-09-24
    raise LLMResponseError(
        message=_responses_error_message(_ev),
        details={"responses_event": _et},
    )
_emit = _fold_emit_delta(_norm_responses_delta(_ev), _state)
if _emit:
    yield _chat_frame(_emit)
```
- **注释 L416–419**：`completed 走单遍分支` 改为 `completed/incomplete 走终帧分支, failed/error 上抛`。

**A2-3 错误上抛链路核对（零代码改动，实施时验证项）**

| 环节 | 既有行为（已读码确认） | 对 A 的含义 |
|------|----------------------|------------|
| `base_service.request_stream` L489–490 | `except LLMResponseError: raise` 穿透 | failed/error 不会在 L1 HTTP 重试圈空转 ✅ |
| `llm_call.call_llm_with_fallback` L262/L304 | 捕获 `LLMResponseError` 走 L2/降级 | 与 FC 解析失败同通道，语义一致 ✅ |
| `error_classifier` L133–134 | `LLMResponseError` → SERVER 可重试 | **残余风险**：provider 硬失败（如内容策略）可能被 L2 重试 1 次后降级——可接受（有界、非死循环）；**不改 classifier**（改动会波及全链路分类，超 A 范围） |
| `request()` collect 路径（L313–344） | 同样消费 `request_stream`，异常自然上抛 | collect 自动获得 failed/error 行为，零另改 ✅ |
| 非 responses chat 通道 | L413–414 直通，不进终帧分支 | 默认 provider 零影响 ✅ |

**A2-4 上游 finish_reason 消费（零代码改动）**

`base_service._extract_finish_reason` L584–593 已按 `choices[0].finish_reason` 原样透传；`StreamChunk.finish_reason` 字段已存在（core.py L98）。`content_filter` 为 OpenAI 兼容四值之一，**下游不需改**。

#### 7.1.4 A3 `test_client_sdk_adapter.py` 逐点改动

**A3-0 文件头编辑历史（L7 下方追加）**
```text
# 编辑历史: 2026-09-24 小欧 v3.7.2 新增 C23(incomplete 终帧) + C24(content_filter 细分) + C25(response.failed 上抛) + C26(error 帧上抛) + C27(reasoning 官方别名)
```

**A3-1 用例明细（全部插在 C22 之后、文件尾 L646 前；复用既有 `_mk_stream_ctx`/`_stream_ctx_dummy`/`_ref` 夹具，不新建夹具）**

| 用例 | 函数名 | 输入事件序列 | 断言 |
|------|--------|-------------|------|
| C23 | `test_c23_incomplete_terminal_frame` | `output_text.delta` + `response.incomplete`（response 含 `incomplete_details.reason=max_output_tokens`、`output[].message` 快照、`usage`） | 末帧 `finish_reason=="length"`；`usage.total_tokens` 透传；截断前文本经终帧快照补全（验证 A1-2 扫描不短路） |
| C24 | `test_c24_content_filter_finish_reason` | 仅 `response.completed`，`incomplete_details.reason=content_filter`，`output` 含 message | 末帧 `finish_reason=="content_filter"` |
| C25 | `test_c25_response_failed_raises` | `response.failed`，`response.error={code:"content_filter", message:"blocked"}` | `pytest.raises(LLMResponseError)`；`str(exc)` 含 `content_filter: blocked`；`exc.details["responses_event"]=="response.failed"` |
| C26 | `test_c26_error_event_raises` | 顶层 `{"type":"error","code":"server_error","message":"boom"}` | `pytest.raises(LLMResponseError)`；`str(exc)` 含 `server_error: boom` |
| C27 | `test_c27_reasoning_official_aliases` | `reasoning_text.delta`("A") + `reasoning_summary.delta`("B") + 既有 `reasoning_summary_text.delta`("C") + `output_text.delta`("T") | `reasoning_content` 拼接 `"ABC"`；`content=="T"` |
| 回归 | 既有 C14/C19/C19b/C21/C22 | 不改夹具 | 必须原样通过（尤其 C19b `max_output_tokens→length`、C21 实证事件名） |

**A3-2 导入追加（测试文件头部）**
```python
from app.llm.core import LLMResponseError   # C25/C26 — 小欧 2026-09-24
```

#### 7.1.5 方案 A 验证与版本

1. `python -m py_compile` 三个改动文件。
2. `pytest tests/test_client_sdk_adapter.py -x --tb=short`（全量 14 个既有 + 5 个新增，零 FAIL 才算过）。
3. 版本：源码注释 v3.7.2；**不打 tag、不写 version.txt**（tag 随用户统一指令）。
4. 提交（若获准）：按组分两笔——`feat:responses_stream.py …` + `fix:client_sdk.py …`（测试是否入库另遵"禁止 commit 测试文件"铁律，由北京老陈定）。

#### 7.1.6 方案 A 行数与风险汇总

| 项 | 值 |
|----|-----|
| 改动源文件 | 2（responses_stream.py、client_sdk.py） |
| 新增测试文件 | 0（追加于既有 test_client_sdk_adapter.py） |
| 新增函数 | 1（`_responses_error_message`，约 12 行） |
| 改写函数 | 1（`_responses_completed_eval` 逻辑体） |
| 条件分支改动 | 1 处（`_norm_responses_delta` reasoning 判断扩元组） |
| 主循环改动 | 1 处（L427–436 终帧三段式） |
| 总预估 | 源码净增约 45 行 + 测试约 95 行 |
| 默认 provider 影响 | **零**（全部代码在 `_is_responses` 门内） |
| 最大风险 | failed→LLMResponseError→SERVER 分类的有界 L2 重试（见 A2-3，接受不改） |

---

### 7.2 方案 C：responses 协议一等化（依赖 A 已合入，增量实施，v3.8.0）

> **定位**：把"endpoint 字符串嗅探出的 `_is_responses` 布尔"升级为"适配器声明的 protocol 能力位"，让 client_sdk 主循环按协议分派而非按 URL 后缀分派——这是为第三种协议（如 Anthropic `/v1/messages`）预留的分派座，**不含**任何新协议实现，**不含**方案 B 的事件全集移植。

#### 7.2.1 前置依赖

| 依赖 | 说明 |
|------|------|
| 方案 A 全部合入（7.1 四文件） | C 不重做 A；A 的终帧/别名逻辑成为 C 分派后 `responses` 分支的既有内容 |
| `endpoint_for`/`to_responses_body` 既有行为 | C 只换"判定源"，不换端点与 body 转换语义 |

#### 7.2.2 C 改动文件总表（增量）

| # | 文件 | 动作 | 预估行变化 |
|---|------|------|-----------|
| C1 | `backend/app/llm/adapters/base.py` | 修改 | 约 +10 / −1 |
| C2 | `backend/app/llm/adapters/opencodeZen.py` | 修改 | 约 +14 / −4 |
| C3 | `backend/app/llm/client_sdk.py` | 修改 | 约 +16 / −6 |
| C4 | `backend/app/llm/responses_stream.py` | 仅注释 | 约 +2 / −1 |
| C5 | `backend/tests/test_client_sdk_adapter.py` | 追加用例 | 约 +55 / −0 |
| C6 | `backend/tests/test_adapters.py` | 追加用例 | 约 +20 / −0 |
| C7 | `doc-9月优化\[66]…md` | 文档追加节 | 章节级 |

**明确不改**：`base_service.py`、`core.py`、`error_classifier.py`、`reasoning.py`、`llm_call.py`、`adapters/__init__.py`（注册表不动）、前端、`FUNCTIONS.md`（`protocol_for` 是适配器方法非全局函数）、不新建 `protocols/` 目录、不新建第二兄弟模块（YAGNI：座空着，来协议再占）。

#### 7.2.3 C1 `adapters/base.py` 逐点改动

**C1-0 编辑历史（L6 下追加）**
```text
# 编辑历史: 2026-09-24 小欧 v3.8.0 协议一等化: 新增 protocol_for 能力位(默认 "chat"), endpoint_for/to_responses_body 语义改由该位驱动说明
```

**C1-1 新增静态方法（插在 `endpoint_for` L30–32 之后）**
```python
@staticmethod
def protocol_for(model: str) -> str:
    """流协议能力位: "chat"(默认=现状直通) | "responses"(事件归一通道) — 小欧 2026-09-24 v3.8.0
    分派唯一权威: client_sdk 主循环按本位选通道, 不再嗅探 endpoint 后缀;
    未来第三协议(如 anthropic-messages)在此扩枚举并新增同级归一模块, 禁止 provider 化。"""
    return "chat"
```
**C1-2 docstring 修订**：`endpoint_for` L31 补一句 `路由结果须与 protocol_for 一致(muse-/responses 同源判定)`；`to_responses_body` L41 `仅 endpoint_for 返回 /responses 的适配器会覆写` 改为 `仅 protocol_for=="responses" 的适配器会覆写`。

#### 7.2.4 C2 `adapters/opencodeZen.py` 逐点改动

**C2-0 编辑历史（L7 下追加）**
```text
# 编辑历史: 2026-09-24 小欧 v3.8.0 协议一等化: 新增 protocol_for(muse-→responses); endpoint_for 改为读 protocol_for 单源, 消除与分派位的双处前缀判断
```

**C2-1 新增 `protocol_for`（muse- 前缀判断唯一化）**
```python
@staticmethod
def protocol_for(model: str) -> str:
    """muse- 前缀 → responses 协议, 其余 chat — 小欧 2026-09-24 v3.8.0
    本方法为协议判定唯一真源; endpoint_for 消费本方法, client_sdk 消费本方法。"""
    return "responses" if (model or "").startswith("muse-") else "chat"
```

**C2-2 改写 `endpoint_for`（现 L118–124）— 删本地前缀判断，改读能力位**
- **改前**：
```python
if (model or "").startswith("muse-"):
    return "/responses"
return "/chat/completions"
```
- **改后**：
```python
return "/responses" if OpencodeZenAdapter.protocol_for(model) == "responses" \
    else "/chat/completions"
```
- **收益**：`muse-` 前缀判断从 2 处（endpoint_for + client_sdk endswith 嗅探）收敛为 1 处（protocol_for）；拼接注释（L119–121 实网复现说明）原样保留。

**C2-3 `to_responses_body` 零逻辑改动**（调用条件从 `_is_responses` 改为 `_protocol=="responses"`，函数体不动）。

#### 7.2.5 C3 `client_sdk.py` 逐点改动

**C3-0 编辑历史（A2-0 行之后再追加）**
```text
编辑历史: 2026-09-24 小欧 - [67]v3.8.0 协议一等化: ①_adapt_request 返回值 _is_responses(bool, endswith 嗅探) 改为 _protocol(str, adapter.protocol_for 单源); ②request_stream 主循环按 _protocol=="responses"/"chat" 二分派, 删 endpoint 后缀嗅探; ③responses_stream 模块注释同步
```

**C3-1 `_adapt_request`（L216–225）**
- **改前 L222**：`_is_responses = _endpoint.endswith("/responses")`
- **改后**：
```python
_protocol = self._adapter.protocol_for(self.llm_model.model)   # 协议能力位唯一权威 — 小欧 2026-09-24 v3.8.0
if _protocol == "responses":
    body = self._adapter.to_responses_body(body, self.llm_model.model)
return _endpoint, body, self._adapter.per_request_headers(), _protocol
```
- docstring L217–218 同步：删"endswith 嗅探"表述，改"返回 protocol 能力位"。
- **一致性约束（注释写死，不 assert）**：`endpoint_for` 与 `protocol_for` 在 zen 内同源（C2 保证）；若未来二者打架，以 protocol_for 分派为准、endpoint 决定 URL——测试 C3x 专门锁一致。

**C3-2 `request()` 调用点 L282**
```python
_endpoint, body, _dyn_headers, _ = self._adapt_request(body)   # 第 4 位现为 _protocol, 非流式不消费 — 小欧 2026-09-24
```
（仅注释更新；解包变量本就是 `_`，零行为变化。）

**C3-3 `request_stream` 分派（现 L398、L407、L413–436）**
- **L398**：`_endpoint, body, _dyn_headers, _protocol = self._adapt_request(body)`
- **L407**：`_state = _DeltaFoldState() if _protocol == "responses" else None`
- **L413–415 改为显式二分派**：
```python
if _protocol == "chat":
    yield _body
    continue
if _protocol != "responses":
    # 未知协议能力位: 不静默当 chat 透传(防未来协议被误吞) — 小欧 2026-09-24 v3.8.0
    raise LLMResponseError(message=f"未知协议能力位: {_protocol}",
                           details={"protocol": _protocol})
# ↓ 以下为 responses 通道既有逻辑(含 A 的终帧三段式), 原样保留
```
- **注释 L416–419**：`_is_responses 时` 改为 `_protocol=="responses" 时`。
- **保留**：`[DONE]` 判断、非 JSON 透传、`_fold_emit_delta` 链、A 的三段式终帧——全部只是被包进 `responses` 分支，逻辑零重写（符合"复制不重写"）。

**C3-4 全文清点 `_is_responses`**：实施时 `grep _is_responses` 必须 **0 命中**（禁 backward 双轨，不留 bool 别名）。

#### 7.2.6 C4 `responses_stream.py` 仅注释

- 模块说明 L5 `client_sdk 主循环仅在 _is_responses 时` → `仅在 _protocol=="responses" 时`。
- 编辑历史追加：`v3.8.0 注释同步 protocol 能力位, 零逻辑改动`。
- **函数体零改动**（C 阶段不碰归一逻辑，避免与 A 的 diff 缠绕）。

#### 7.2.7 C5/C6 测试逐点

**C5 `test_client_sdk_adapter.py` 追加（A3 用例之后）**

| 用例 | 函数名 | 断言 |
|------|--------|------|
| C28 | `test_c28_protocol_for_muse_responses` | `_ref("opencodeZen","muse-…")` 客户端走 `request_stream`，mock 收集 `url=="/responses"`（协议位与端点一致） |
| C29 | `test_c29_protocol_for_default_chat` | 默认 provider `agnes`：`c._adapt_request(_build_request_body(...))` 第 4 位 `=="chat"`；body 未经 `to_responses_body`（仍有 `messages` 键、无 `input` 键） |
| C30 | `test_c30_zen_non_muse_protocol_chat` | `opencodeZen` + `big-pickle`（非 muse）：第 4 位 `=="chat"`，url 为 `/chat/completions` |
| C31 | `test_c31_responses_channel_still_normalizes` | **回归闸**：muse + `output_text.delta` + `completed` 仍归一为 chat 形帧（锁 C 分派不破坏 A） |
| 回归 | A3 全部 + 既有 C1–C22 | 零改动零 FAIL |

**C6 `test_adapters.py` 追加**

| 用例 | 断言 |
|------|------|
| 基类 | `ProviderAdapter.protocol_for("any")=="chat"`；`endpoint_for=="/chat/completions"` |
| zen | `OpencodeZenAdapter.protocol_for("muse-x")=="responses"`；`protocol_for("big-pickle")=="chat"`；`protocol_for("")=="chat"` |

#### 7.2.8 C7 `[66]` 文档伴随改动（非代码但随 C 同批）

- 在架构章（传输层/协议判定相关节）追加小节：**"协议能力位 protocol_for 与分派"**——能力位枚举表、与 endpoint_for 同源约束、第三协议接入三步骤（base 加枚举 → 新兄弟模块 → client_sdk 分支加一条）、YAGNI 声明（座空着不预建模块）。
- 版本历史行 + 编辑签名（编辑型，不删历史）。
- 同步全文残留 `_is_responses`/`endswith 嗅探` 表述（与代码同一原则 grep 清零）。

#### 7.2.9 方案 C 验证与版本

1. `grep -n "_is_responses" backend/app/llm/` → 0 命中。
2. `grep -n 'startswith("muse-")' backend/app/llm/` → 仅 `opencodeZen.protocol_for` 1 命中。
3. `python -m py_compile` 四个源文件 + `py_compile` 两个测试文件。
4. `pytest tests/test_client_sdk_adapter.py tests/test_adapters.py -x --tb=short`（A 用例 + C 用例 + 既有全绿）。
5. 版本 v3.8.0（MINOR：协议分派属结构性增强，按 4.4 需用户同意——即本清单获批即为同意）；**不打 tag**。

#### 7.2.10 方案 C 行数与风险汇总

| 项 | 值 |
|----|-----|
| 增量源文件 | 4（base/opencodeZen/client_sdk/responses_stream 注释） |
| 新增方法 | 1（`protocol_for` 基类默认 + zen 覆写，共 2 处定义） |
| 删除的判定 | `_endpoint.endswith("/responses")` 单点嗅探 |
| 主循环结构 | 直通 if → `chat`/`responses`/未知协议 三分支（未知=上抛不静默） |
| 总预估 | 源码净增约 40 行（含注释）+ 测试约 75 行 + [66] 一节 |
| 行为变化 | 已知路径 **零**（chat 仍直通、responses 仍同一归一链）；新增行为仅"未知协议位上抛"（当前枚举只有 2 值，死码防御） |
| 最大风险 | `_adapt_request` 返回值第 4 语义变更（bool→str）——两个调用点 L282/L398 均已列入 C3，grep `_is_responses` 清零作闸 |

---

### 7.3 两方案范围对照总表

| 维度 | 方案 A | 方案 C（含前置 A 则合计） |
|------|--------|--------------------------|
| 目标 | 协议语义正确（终帧/finish_reason/别名） | 协议分派架构就位（能力位取代 URL 嗅探） |
| 版本 | v3.7.2 PATCH | v3.8.0 MINOR |
| 源文件数 | 2 | 增量 4（总 6，A 的 2 文件会被 C 部分再改） |
| 新增函数 | 1（`_responses_error_message`） | +1 方法×2 定义（`protocol_for`） |
| 测试 | +5（C23–C27） | +7（C28–C31 + adapters 3 断言组） |
| 动 base_service？ | 否 | 否 |
| 动 adapters？ | 否 | 是（base + opencodeZen） |
| 第三协议就绪？ | 否 | 是（分派座就位，模块仍空） |
| 可独立发布？ | 是 | 否（必须 A 在前） |

### 7.4 原"建议决议"保留（v1.0 内容，未删）

1. **否决**完整复制 `openai-responses.ts`（方案 B）。
2. **批准方案 A**：补三块协议边缘（终帧四态 + finish_reason 细分 + reasoning 别名），版本 v3.7.2，TDD C23+。
3. **[66] 文档**补一节"与 opencode 协议实现对照及不复制决策"，把 YAGNI 不做项写死，防后人再提"要不要整个搬过来"。
4. 方案 C 写入 [66] 演进备注，不在本次实施。

**请北京老陈拍板**：按 7.4 执行 / 7.1 与 7.2 两清单是否需要调整范围？（确认前不动代码。）

---

**编写人**: 小欧  
**签名**: 小欧  
**编写时间**: 2026-09-24 10:02:14  
**更新时间**: 2026-09-24 10:21:54  
**更新人**: 小欧  
**更新签名**: 小欧  
**本次更新**: v1.1 第七章改写为方案 A/C 精确代码改动范围  
**v1.2 更新**: 第六章改写为 4 小节（现状流程 / A 要点与流程 / C 要点与流程 / 优劣对比）  
**v1.3 更新**: 10遍精读核查修文档设计错误（统一行号基准/补五章衔接/精修措辞）  
**v1.4 更新**: 内联章节化——1.2后补1.3/1.4/1.5并排版，不丢内容、打通1→2→4→6逻辑  
**v1.5 更新**: v1.4全文10遍核查修3处（请求构造事实错误/三态消歧义/透传归属），设计正确、上下一致
