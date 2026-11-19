# question 与 interact 交互事件设计规范说明

> 文档号：[49] | 签名：商量 | 时间：2026-11-19 15:00:00
> 编写/更新人：商量（签名）
> 存放：D:\NDOOmniAgent\doc-11月优化\[49]question与interact交互事件设计规范说明-商量-2026-11-19.md
> 性质：**设计说明文档** —— 回答"为什么这样设计"，不重复字段契约与代码位置
> 分工：[48] 管实现规范（字段契约、代码位置、复用指引）；本文管设计思想、决策取舍、分层关系、设计演进
> 前置：[37] question/schedule 业务设计；[47] notice（单向通知）规范；[48] interact 实现规范

## 目录

- [1. 设计背景：为什么要抽象出 interact](#1-设计背景为什么要抽象出-interact)
- [2. 设计目标与原则](#2-设计目标与原则)
- [3. 整体分层架构](#3-整体分层架构)
- [4. question 业务设计](#4-question-业务设计)
- [5. interact 框架设计](#5-interact-框架设计)
- [6. 关键设计决策与取舍](#6-关键设计决策与取舍)
- [7. 与相邻范式的关系](#7-与相邻范式的关系)
- [8. 设计演进](#8-设计演进)
- [9. 设计约束与不变量](#9-设计约束与不变量)
- [10. 扩展到下一个交互 tool](#10-扩展到下一个交互-tool)
- [11. 验证要点](#11-验证要点)

---

## 1. 设计背景：为什么要抽象出 interact

question 最初以一对专用事件实现：发问 `question_required`、收口 `question_resolved`（见 [37]）。落地后暴露出两个结构性问题：

1. **框架被 tool 语义污染**：专用事件把 question 的专属字段（questions/backend_timeout/outcome）平铺在框架事件里，框架层不得不认识这些字段。再来一个交互 tool（确认、选择）就要再发明一对专用事件，框架无法复用。
2. **同类事件各自为政**：notice 已经抽象出单向通知通道（[47]），而双向交互没有统一范式——question 自有一套、HITL 授权借用 `paused/resumed` 又是一套，概念割裂。

抽象出 interact 的目的：**把"agent 与用户的双向交互"提升为框架一等公民**，让任何交互 tool 只填自己的 `kind` 与 `payload`，框架层零语义。question 成为第一个使用者，也是验证该范式的范例。

## 2. 设计目标与原则

| 目标 | 设计手段 |
|---|---|
| 框架不认识 tool 语义 | 框架级字段只有 interaction_id/kind/event/content/payload；questions 等特殊性全在 payload |
| 双向、可多轮 | interaction_id 关联多轮；event 区分发起与收口；阻塞 Future 唤醒后端 |
| 新增交互 tool 框架零改 | sseParser 只解析通用字段；transport 按 kind 一个分支；UI 放各自目录 |
| 与单向通知并列 | notice（[47]）=单向；interact=双向，两者不混用 |
| 不退化 | 落库与喂 LLM 照常；仅呈现通道变化（工具行隐藏、事件上浮） |

核心设计原则：**框架层提供"消息通道"，业务层提供"交互语义"**。两者边界清晰，改动互不穿透。

## 3. 整体分层架构

一次 question 交互穿过六层，责任自上而下逐层收窄：

| 层 | 组件 | 职责 | 持有 question 特殊性？ |
|---|---|---|---|
| 工具入口 | `question` 工具（agent_register 注册） | LLM 调用入口；`hide_from_steps` 不画通用工具行 | 否（仅声明） |
| 发射器 | `StepEmitter.ask_question` | 配置/超时双分支决策、buffer 守卫、下传 auto_confirm | 否（只算窗口） |
| 业务网关 | `question_gateway.ask_question` | create→发 ask→SUSPENDED→wait→发收口→EXECUTING | 是（编排流程） |
| 三原语 | `hitl_question` create/wait/resolve | Future 阻塞、过期清理、三态结构化结果 | 是（阻塞机制） |
| 框架事件 | `InteractStep` / `emit_interact` / 类型登记 | 通用事件载体与统一发射，SSE-only 不落库 | 否（零语义） |
| 前端链路 | sseParser → interactHandlers → QuestionDock → answer API | 解析通用字段、按 kind 分派、UI 呈现、用户回传 | 是（UI 与回传） |

数据流：`LLM 调 question → 发射器算窗口 → 网关发 interact(ask) → 前端浮层 → 用户答/取消/超时 → answer API → resolve Future → 网关发 interact(收口) → 后端继续`。

## 4. question 业务设计

### 4.1 阻塞机制

采用 `SUSPENDED + asyncio.Future`（与 HITL 确认同构，但 question 只收集答案、不写信任库）：

- `create_question` 建 pending entry（future/questions/created_at），返回 `question_id = {task_id}:{随机8位}`。
- `wait_for_question_result` 轮循等待 Future，超时/取消/任务取消均以结构化结果返回。
- 等待段 `try/finally` 保证三条路径（作答/超时/抛错）都掀掉 SUSPENDED，否则任务终态被误判为 paused。
- 过期清理复用 HITL 同源超时配置，防 pending 表内存泄漏。

### 4.2 超时双分支

窗口长度由发射器按 HITL 开关唯一判定（公式单源复用 `_resolve_timeouts`）：

| 模式 | 条件 | 后端窗口 | 到点行为 |
|---|---|---|---|
| 真人工 | HITL 开 | security.hitl.timeout（约 120s） | 按专家指令兜底作答 |
| 旁路 | HITL 关 | 短窗（约 10s，窗口内仍可抢答） | 按各题首选项兜底作答 |

窗口模式以 `auto_confirm` 随事件链下传，网关与工具层据此取兜底文案，不再各自重读配置（单一真源）。

### 4.3 三态收口

收口结果归一为三种 event，且**三态都发收口帧**：

| event | 触发 | 后端结果 |
|---|---|---|
| answered | 用户提交答案 | answers + success |
| cancelled | 用户放弃 | error + 提示中断推进 |
| expired | 窗口到点未答 | 兜底答案 + 对应前缀文案 |

防御点：entry 被过期清理摘除时按 expired 处理——若三态全假会被上层读成"用户已回答"并以空答案成功收口（历史缺陷，已修）。

### 4.4 前端呈现与回传

- 倒计时前端纯展示（读 payload.backend_timeout），**清窗权威在后端收口帧**——避免前后端双计时源漂移。
- 用户提交/取消走 `/chat/stream/answer`，唤醒对应 Future。
- question 的专属逻辑全留在 `useQuestionDock.ts` 与 `components/question/`；框架层不感知。

## 5. interact 框架设计

### 5.1 框架字段与语义分工

框架只定义"一条交互消息是什么"，不定义"某个 tool 怎么交互"：

| 字段 | 语义层 | 说明 |
|---|---|---|
| interaction_id | 框架 | 交互标识，同 id 多轮关联、不同 id 独立 |
| kind | 半框架 | 交互种类标识（question/confirm/...），框架仅按它分派，不解释内容 |
| event | 框架 | 这条消息发生了什么（ask/answered/cancelled/expired），四态通用 |
| content | 框架 | 人可读文案 |
| payload | 业务 | 各 tool 特殊内容，框架零解释 |

### 5.2 两层分派

- **解析层**（sseParser）：只解析框架通用字段，push 事件列表并投 `onInteract`；不认识任何 kind 的含义。
- **分派层**（interactHandlers）：按 kind 路由到各 tool 的 store 逻辑；question 分支读写 pendingQuestion/hitlWaitingKeys。

新增交互 tool 只在分派层加一个分支，解析层与 step 载体零改动。

### 5.3 通道路由

- interact 登记 `ALL_STEP_TYPES`（仅 SSE 组）与 `SSE_ONLY_TYPES`（不落库），自动进入 SSE 转发白名单。
- 交互 tool 注册 `hide_from_steps=True`：产出由专属 UI 呈现，不画通用工具行；但落库与喂 LLM 照常（与呈现通道解耦）。
- stepFilter 将 interact 归 meta：否则进入业务流水线却无渲染分支，会导致查看区空白。

## 6. 关键设计决策与取舍

### 6.1 为什么 event 用叶子语义，不用 phase 或 phase+outcome

- **否 `phase`**：phase 暗示强生命周期顺序，但交互的特点是"这次与下次可以有关、也可以无关"，每帧是独立消息；且 phase 是从 notice 抄来的，不是从交互本质推导。
- **否 `phase + outcome`**：`done/resolve` 是上位概念，`answered/cancelled/expired` 是具体结果，两层重复。event 用具体结果作叶子（一字段说清"发生了什么"），具体业务值（如 confirm 的 rejected）放 payload。

结论：event 单一字段、四态叶子、无冗余——从"事件就是发生了什么"的本质推导。

### 6.2 为什么收口三态都发帧

旧 paused/resumed 的教训是"收口事件不一定发"，前端只能靠别处清窗，单一权威源缺失。interact 规定 ask 之后必有一个收口帧（answered/cancelled/expired），前端清窗只认收口帧，逻辑对称且可靠。

### 6.3 为什么用专用 InteractStep 而非 MetaStep kwargs

interact 字段是框架一等公民（四字段 + payload），专用类让契约显式、可读、可验证；MetaStep kwargs 适合零散元信息，不适合承载一等事件。此处选 clarity 而非复用 kwargs。

### 6.4 为什么 sseParser 只投通用字段

解析层一旦认识 kind 语义，新增 tool 就要改解析层，违反"框架零改"。把语义留在 transport 分派层，解析层保持稳定。

## 7. 与相邻范式的关系

### 7.1 与 notice（单向通知）

| 维度 | notice [47] | interact（本文） |
|---|---|---|
| 方向 | 单向（后端→前端） | 双向（后端发起→用户响应→回传） |
| 代表 | schedule | question |
| 前端呈现 | 专属卡片 | 专属浮层 |
| 字段 | kind + phase + items | kind + event + payload |

两者并列，不混用：通知用 notice，交互用 interact。

### 7.2 与 HITL 的 paused/resumed

需区分两个概念：

- **暂停/恢复按钮**：走 HTTP 端点（`/chat/stream/pause|resume`），是任务级控制，与交互事件无关。
- **HITL 授权弹窗**：借用 `paused/resumed` SSE 事件名，带 confirm_id/trust_impact 等授权字段，本质是"问用户做不做"——与 interact 是同类（双向交互）。

授权弹窗在架构上可收敛为 `interact(kind=confirm)`，但它是安全关键路径且 paused 名有双重语义（按钮控制 + 授权交互），需独立重构轮次并配完整 E2E，不在本次 question 改造范围内。此处仅记录方向，不动代码。

## 8. 设计演进

| 阶段 | 形态 | 设计动因 |
|---|---|---|
| [37] 初版 | question 专用事件对 question_required/resolved（MetaStep） | 先落地 question 业务，不复用 paused（语义不同） |
| 11-18 落地 | 三原语 + 网关 + 超时双分支 + 三态收口 | 补齐阻塞机制、兜底、边界防御 |
| 11-19 升格 | 通用 interact 框架，question 作首个使用者 | 抽象双向交互范式，框架零 tool 语义；event 叶子语义定案 |
| 未来（未决） | HITL 授权收敛到 interact(kind=confirm) | 消除 paused/resumed 双重语义；需独立 E2E |

演进主线：**从"为 question 发明事件"到"为交互发明框架"**——工具语义持续从框架层向业务层下沉。

## 9. 设计约束与不变量

以下约束是范式正确性的保证，后续改动不得破坏：

1. 框架层零 tool 语义：InteractStep / emit_interact / sseParser 不得出现任何 tool 专属字段。
2. 收口单一权威：ask 之后必有且仅有一个收口帧；前端清窗只认收口帧。
3. 呈现与业务解耦：hide_from_steps 只影响工具行呈现，落库/喂 LLM 不变。
4. 单一真源：窗口模式（auto_confirm）、倒计时、清窗判定各只有一个权威点。
5. 新增 tool 框架零改：扩展只动工具注册、transport 分派分支、专属 UI 三处。
6. 不 backward：新范式直接替换旧事件，不留兼容垫片。

## 10. 扩展到下一个交互 tool

以 confirm（授权确认）为例，设计 Follow 顺序（具体步骤见 [48]）：

1. 工具注册声明 `hide_from_steps=True`。
2. 后端业务流程调 `emit_interact(interaction_id, kind='confirm', event=ask/answered/cancelled/expired, payload=...)`；授权的特殊字段（trust_impact/path/params）放 payload。
3. 前端 interactHandlers 加 `kind==='confirm'` 分支，读写自己的 store 字段。
4. 专属 UI 组件呈现；阻塞机制按需要复用 Future 范式或独立实现。
5. 框架层（InteractStep / emit_interact / sseParser / stepFilter）零改动——这是对第 5 节分层设计是否成立的验收标准。

## 11. 验证要点

- 一次 question 全链路：ask 帧带 questions/backend_timeout → 用户答 → answered 收口帧 → 浮层消失、后端继续。
- 三态收口：answered/cancelled/expired 都发收口帧；过期清理（entry=None）按 expired 处理。
- 窗口双分支：HITL 开/关分别走长窗/短窗，兜底文案判据随 auto_confirm 下传。
- 分层不穿透：框架层文件无 question 专属字段；新增 tool 时框架层零改。
- 不变量：interact 仅 SSE 不落库；question hide_from_steps=True；stepFilter 归 meta 不导致查看区空白。

---

**编写/更新人：商量（签名）**
**时间：2026-11-19 15:00:00**
