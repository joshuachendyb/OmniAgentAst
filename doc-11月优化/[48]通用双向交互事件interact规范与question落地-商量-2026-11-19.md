# 通用双向交互事件 `interact` 规范与 question 落地文档

> 文档号: [48] | 签名: 商量 | 时间: 2026-11-19 14:20:00
> 编写/更新人: 商量（签名）
> 存放: D:\NDOOmniAgent\doc-11月优化\[48]通用双向交互事件interact规范与question落地-商量-2026-11-19.md
> 性质: **规范类文档** —— 定义「通用双向交互事件 interact」，question 为首个落地范例
> 前置: [47] 通知事件类 tool 规范（notice 是单向通知，interact 是双向交互，两者并列）
> 更新: 2026-11-19 商量 - 本文定义的是 interact **事件帧契约**（type/interaction_id/kind/event/payload），本次 question 工具内部参数(single/阈值)与返回三态(success/warning/error)重构不改变事件帧结构；工具层契约详见 [37] §7.3/§9.2、设计决策见 [49] §4.3

## 目录

- [1. 规范定位](#1-规范定位)
- [2. 事件契约](#2-事件契约)
- [3. 为什么 event 是叶子语义](#3-为什么-event-是叶子语义)
- [4. 后端规范](#4-后端规范)
- [5. 前端规范](#5-前端规范)
- [6. question 落地（首个范例）](#6-question-落地首个范例)
- [7. 关键代码位置](#7-关键代码位置)
- [8. 复用指引](#8-复用指引)
- [9. 验证](#9-验证)

---

## 1. 规范定位

agent 工具按「与用户交互方式」分三类：

| 类别 | 本质 | 代表 | 前端呈现 | 规范 |
|---|---|---|---|---|
| 业务类 tool | 操作外部资源，产出业务结果 | read/write/shell | observation 步入业务流水线 | 本仓既有 |
| 通知事件类 tool | 单向通知用户（后端→前端） | schedule | notice → 专属卡片 | [47] |
| **交互事件类 tool** | **双向交互（后端发起→用户响应→回传）** | **question（首个）** | **interact → 专属浮层** | 本文 |

交互事件类 tool 的特征：
1. 不操作外部资源，产出的是 agent 与用户的交互（问询/确认/选择）。
2. 双向：后端发消息 → 前端专属 UI 呈现 → 用户响应 → 回传唤醒后端阻塞。
3. 可多轮：多条 interact 消息可关联（同 interaction_id）也可独立（不同 id）。
4. 非业务 tool：不画通用工具行（hide_from_steps），但落库 + 喂 LLM 照常。

**notice（单向通知）与 interact（双向交互）并列**，是两个不同维度的事件框架。

## 2. 事件契约

interact 事件字段（框架级，不认识任何 tool 特殊语义）：

| 字段 | 类型 | 职责 |
|---|---|---|
| `type` | 固定 `interact` | 事件类型 |
| `interaction_id` | str | 交互标识；同 id=多轮关联，不同 id=独立交互（调用方决定，框架不预设） |
| `kind` | str | 交互种类（question/confirm/select...），各 tool 自填 |
| `event` | `ask`/`answered`/`cancelled`/`expired` | 这条消息发生了什么（叶子语义） |
| `content` | str | 人可读文案（事件列表显示） |
| `payload` | dict，可选 | 各 tool 特殊内容（questions/backend_timeout/具体结果值），完全开放，框架零解释 |

**event 四态**（通用，所有交互共有）：

| event | 语义 | 说明 |
|---|---|---|
| `ask` | 发起交互 | 后端口径：向用户提问/请求 |
| `answered` | 对方成功响应 | 答了/同意/选了（各 kind 的具体值在 payload） |
| `cancelled` | 对方放弃 | 取消/拒绝 |
| `expired` | 超时未响应 | 窗口到点 |

## 3. 为什么 event 是叶子语义

设计过程中否掉了两个候选，记录理由（避免后来者重犯）：

- **否 `phase`（start/done/failed）**：phase 暗示强先后顺序（一条生命周期线），但 interact 的特点是"上一次和下一次可以有关、也可以无关"——每帧是独立消息，phase 的强顺序语义不成立。且 phase 是从 notice 抄来的，不是从 interact 特点推导。
- **否 `phase`+`outcome` 两字段**：`resolve`/`done` 是上位概念，`answered`/`cancelled`/`expired` 是具体结果，放两层会重复。event 用具体结果值作叶子（一字段说清"发生了什么"），具体业务值（如 confirm 的 rejected）放 payload。

**结论**：event 单一字段、四态叶子、通用、无冗余——从"事件"本质推导（事件就是"发生了什么"）。

## 4. 后端规范

| 组件 | 文件 | 职责 |
|---|---|---|
| step 载体 | `app/services/agent/steps/interact_step.py` | `InteractStep(ReasoningStep)`，承载 interaction_id/kind/event/payload，content 走基类 get_content |
| 唯一发射器 | `app/services/agent/step_emitter.py::emit_interact` | 构造 InteractStep → publish；各 tool 不自己构造 step |
| step 登记 | `app/services/agent/steps/__init__.py::ALL_STEP_TYPES` | 加 `interact`（仅 SSE 组） |
| 落库过滤 | `app/monitoring/agent_telemetry.py::SSE_ONLY_TYPES` | 加 `interact`（SSE-only 不落库） |
| 工具行屏蔽 | tool 注册 `hide_from_steps=True` | 交互 tool 不画通用工具行（框架层 visible_in_steps 统一判据） |

`emit_interact(interaction_id, kind, event, content, payload?)` —— 统一签名，各交互 tool 复用。

## 5. 前端规范

| 组件 | 文件 | 职责 |
|---|---|---|
| 类型 | `types/execution.ts` / `types/chat.ts` | `interact` 事件类型 + interaction_id/kind/event/payload 字段 |
| 载荷接口 | `streams/chatStreamTypes.ts::InteractPayload` | 交互事件载荷类型单一真源 |
| 解析 | `services/sseParser.ts` | `case 'interact'`：解析通用字段 → push 事件列表 → 投 `onInteract`；不认识 kind 含义 |
| 分派 | `streams/chatStreamTransport.ts::interactHandlers` | 按 kind 分派到各 tool 专属 store 逻辑；新增 kind 加分支，框架零改 |
| meta 归类 | `components/pipeline/stepFilter.ts::META_STEP_TYPES` | `interact` 归 meta（不进业务流水线，否则查看区空白） |

**两层分派**：sseParser 只解析通用字段（不认识 kind 语义），transport 按 kind 分派业务——新增交互 tool 只改 transport 一个分支。

## 6. question 落地（首个范例）

question 的一次交互：

| 环节 | event | payload | 后端流程 |
|---|---|---|---|
| 发问 | `ask` | `{questions, backend_timeout}` | create_question → emit_interact(ask) → SUSPENDED → wait Future |
| 作答 | `answered` | — | resolve_question → emit_interact(answered) |
| 放弃 | `cancelled` | — | resolve_question(cancelled) → emit_interact(cancelled) |
| 超时 | `expired` | — | 窗口到点 → 兜底作答 → emit_interact(expired) |

question 的特殊性（questions/倒计时/answer API/阻塞 Future）全留在 `handlers/question_gateway.py` + `hooks/useQuestionDock.ts` + `components/question/`，框架层的 interact 只提供通用消息通道。

## 7. 关键代码位置

| 层 | 文件 | 要点 |
|---|---|---|
| step | `backend/app/services/agent/steps/interact_step.py` | InteractStep 四字段载体 |
| 发射 | `backend/app/services/agent/step_emitter.py` | emit_interact 统一发射器 |
| 登记 | `backend/app/services/agent/steps/__init__.py` / `agent_telemetry.py` | ALL_STEP_TYPES / SSE_ONLY_TYPES |
| question 接入 | `backend/app/services/agent/handlers/question_gateway.py` | create→ask→wait→answered/cancelled/expired |
| 前端类型 | `frontend/src/types/execution.ts` / `chat.ts` / `streams/chatStreamTypes.ts` | interact 类型 + InteractPayload |
| 前端链路 | `frontend/src/features/chat/services/sseParser.ts` / `streams/chatStreamTransport.ts` / `components/pipeline/stepFilter.ts` | 解析 + 分派 + meta 归类 |
| question UI | `frontend/src/features/chat/hooks/useQuestionDock.ts` / `components/question/` | 特殊性原地不动 |

## 8. 复用指引（下一个交互 tool）

1. 工具注册声明 `hide_from_steps=True`
2. 后端业务流程中调 `emit_interact(interaction_id=..., kind=自己的名, event=ask/answered/cancelled/expired, payload=自己的数据)`
3. 前端 `interactHandlers` 加一个 kind 分支，读写自己的 store 字段
4. 专属 UI 组件呈现，特殊性留在自己的目录
5. 框架层（InteractStep / emit_interact / sseParser / stepFilter）零改动

## 9. 验证

- InteractStep 序列化：ask 帧带 payload、answered 帧不带（空字段不输出）
- interact 登记 ALL_STEP_TYPES + SSE_ONLY_TYPES；question hide_from_steps=True（实测）
- 后端 41 单测全过；前端 typecheck/eslint/prettier 全过、7 单测全过

---

**编写/更新人: 商量（签名）**
**时间: 2026-11-19 14:20:00**
