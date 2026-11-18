# question 与 schedule 工具设计文档

> 文档号: [37] | 作者: 商量 | 日期: 2026-11-14
> 更新: 2026-11-18 - 商量 - 复核前端 UI/UE 设计参照系统既有代码范式, 补 §7.4.3 范式对齐结论并同步 §6.4/§12 B5/§13 前端用例
> 目录: D:\NDOOmniAgent\doc-11月优化\[37]question与schedule工具设计-商量-2026-11-14.md
> 前置研究: 20261113-102752-37dc\question_todowrite_research.md(18KB, opencode2.2.5源码 + Claude Code/Spring AI 对比)
> 前端深研: 2026-11-14 追加 opencode question 前端(§7.4.0) —— **DockPrompt 底部停靠面板范式, 非 Modal 弹窗; Omni HITL 不能复用**

---

## 0. 设计结论(先读)

| 工具 | 名称 | 本质 | 分类 | 人工干预 | 超时 |
|---|---|---|---|---|---|
| **question** | question | 阻塞式人机问答 | **AGENT(本次新增)** | **继承 `security.hitl.enabled`(同一开关)** | 复用 `security.hitl.timeout`(默认120s) |
| **schedule** | schedule | 会话内任务/计划清单 | **AGENT(本次新增)** | 无需(纯回显) | 无 |

**关键决策**:
1. **question 从禁用名单移除** —— 真值源 `config.yaml tuning.agent.disabled_tools`, 内置 `UNAVAILABLE_OFFICIAL_TOOLS` 同步摘除
2. **question 超时复用 `security.hitl.timeout`(默认120s)** —— 与 HITL 确认超时同源
3. **question 人工干预开关继承 HITL 同一开关** (`security.hitl.enabled`) —— 不单独设 question 开关
4. **schedule 一期方案 A** —— 纯回显, 见 §4
5. **两个工具都不属于现有任何分类** —— 新增 `ToolCategory.AGENT`, 见 §5
6. **question 不复用 `paused` 事件** —— 新增独立事件对 `question_required` / `question_resolved`, 见 §6
7. **实施顺序铁律** —— 先写工具内核 + 单测跑通(阶段A, 不注册/不改配置/不动 SSE), 再接系统(阶段B), 见 §12

**本文档的可实施性说明**: §1~§4 为 opencode 设计依据(研究结论, 保留原文); §5~§13 为本仓落地的**可执行契约**——函数签名/返回结构/事件字段/登记表/测试用例/实施顺序, 全部与本仓当前代码逐行对齐。落地现状核对见 §14.1(截至本文档补充时, 代码落地为 0)。

---

## 1. 背景与目标

Omni 系统(商汤智能体)当前具备 HITL 人工确认机制(`services/task/hitl_confirmation.py`), 但:
- **无多问题多选项问答能力** —— HITL 是 confirm/reject 二值确认(授权), 无法做"收集偏好/澄清歧义/获取决策"的语义问答
- **无任务/计划清单工具** —— 模型执行长任务(≥3步)时无工作清单展示, 用户看不到执行计划

本设计为 Omni 增加两个工具:
- **question**: 执行中向用户提问(收集偏好/澄清歧义/获取实现决策), 阻塞式, 按 opencode 主体设计
- **schedule**: 会话内任务/计划清单(用户可见的执行计划), 功能类似 opencode todoWrite, 名词改为 schedule(计划)

---

## 2. opencode2.2.5 question 研究(设计依据)

### 2.1 源码位置
- 实现: `packages/core/src/tool/plugin/question.ts` (132行)
- Schema: `packages/schema/src/question.ts` (22行)

### 2.2 功能(description)
```
Use this tool when you need to ask the user questions during execution. This allows you to:
1. Gather user preferences or requirements
2. Clarify ambiguous instructions
3. Get decisions on implementation choices as you work
4. Offer choices to the user about what direction to take.
```

### 2.3 Input/Output

**Input**:
```ts
{ questions: [{ question:str, header:str, options:[{label,description}], multiple?:bool }] }  // 非空数组
```
- `header`: 极短标签(max 30 chars)
- `multiple`: 是否允许多选(默认单选)
- `options`: 可用选项(label+description)

**Output**:
```ts
{ answers: [[str,...], ...] }  // 每问题答案数组
```

### 2.4 执行逻辑
```
execute(input, context):
  1. permission.assert({action:"question", resources:["*"]})  → 权限校验
  2. forms.ask({sessionID, title:"Questions", metadata:{kind:"question", tool:{messageID,id}},
                fields: input.questions.map(toField)})        → 阻塞式交互表单
  3. 结果分流:
       cancelled+message → ToolFailure(message)   [非交互客户端, 模型继续]
       cancelled         → die(CancelledError)    [用户关闭, 步骤结束]
       正常              → 组装 output.answers
  4. return {output:{answers}, content: toModelContent(...), metadata:{answers}}
```

**toField**(每问题转表单字段):
```ts
{ key:`q${index}`, title:header, description:question,
  type: multiple ? "multiselect" : "string",
  options: options.map(o => ({value:o.label, label:o.label, description:o.description})),
  custom: true }   // 自动加"Type your own answer"自定义输入
```

**toModelContent**(反馈给 LLM 的摘要):
```
User has answered your questions: "q1"="答案1, 答案2", "q2"="...". You can now continue with the user's answers in mind.
```

### 2.5 关键设计
1. **阻塞式**: `forms.ask` 挂起 agent 执行, 用户回答后才返回 → 答案直接进 LLM 上下文
2. **多问题**: `questions` 数组, 每问题独立字段 `q0/q1/...`
3. **多选/单选**: `multiple` 开关
4. **自定义输入**: `custom:true` 自动加自定义输入, 不要求 LLM 单独提供
5. **取消语义**: 关闭(步骤结束) vs 带消息(模型继续) 分流

---

## 3. opencode2.2.5 todoWrite 研究(设计依据)

### 3.1 源码位置
- 实现: `packages/core/src/tool/plugin/todo.ts` (83行)
- 描述: `packages/core/src/tool/todowrite.txt` (7行)

### 3.2 功能(description)
```
Create and update a todo list for the current session. The user sees it as your working plan.
Use it proactively when a task has 3 or more distinct steps, or when the user gives several tasks
or asks for a todo list. Skip it for a single simple task or a purely conversational request. When in doubt, use it.
- Send the full list on every call; it replaces the previous one.
- Mark items `in_progress` when you start them and `completed` as soon as they're actually done.
- Only call it when the list changes.
```

### 3.3 Input/Output

**Input**:
```ts
{ todos: [{ content:str, status:"pending"|"in_progress"|"completed"|"cancelled" }] }  // 完整清单(整体替换)
```

**Output**:
```ts
{ todos: [{ content, status }] }  // 原样回显
```

### 3.4 执行逻辑
```
execute(input, context):
  1. permission.assert({action:"todowrite", resources:["*"], save:["*"]})  → 权限校验
  2. 纯回显: Effect.as({
       output: { todos: input.todos },
       content: summarize(input.todos),   // 摘要给 LLM
       metadata: { todos: input.todos },  // 清单给前端
     })
```

**summarize**(摘要生成):
```ts
if (todos.length === 0) return "Todos cleared"
counts = `${completed}/${total} completed`
       + (in_progress ? `, ${n} in progress` : "")
       + (pending ? `, ${n} pending` : "")
       + (cancelled ? `, ${n} cancelled` : "")
active = in_progress 项的 content 列表
return `Todos updated: ${counts}${active.length ? `. In progress: ${active.join(", ")}` : ""}`
```

### 3.5 关键设计
1. **纯回显, 零落库**: 不写文件/DB, 清单状态在 LLM 上下文
2. **整体替换**: 每次传全量清单, 非增量
3. **摘要给 LLM**: `content` 给模型自省
4. **metadata 给前端**: `metadata.todos` 承载清单渲染
5. **实验门控**: `experimental.todo === true` 才启用(默认关闭)

---

## 4. schedule 两方案差异说明(用户提问核心)

> **名词说明**: 用户拍板"功能类似但名词改为 **schedule(计划)**", 即 Omni 的清单工具叫 `schedule`, 不叫 `todowrite`。以下用"方案A/方案B"指代两种实现深度, 均以 schedule 为工具名。

### 4.1 方案A: 纯回显(一致 opencode)

**一句话**: 模型每次调用 `schedule` 时把**完整清单**传进来, 后端**原样回显**并生成摘要, 不落任何状态。清单的"记忆"完全在模型自己的上下文里。

**行为**:
- 模型调用 `schedule({items:[{content:"步骤1", status:"in_progress"}, ...]})`
- 后端返回 `{data:{items}, llm_data:{summary}}`(原样回显 + 摘要)
- 模型下次更新时**再次传完整清单**(整体替换)
- **无任何内部状态** —— 后端不记录"上一次清单", 不校验"是否变化"

**优点**:
- 实现极简(纯函数, 零落库, 零状态)
- 与 opencode 完全一致, 行为可预期
- 无并发/一致性风险

**缺点**:
- **无强制单任务**: 模型可以同时标多个 `in_progress`, 用户看到的"进行中"可能多个
- **无 nag 提醒**: 模型若忘记更新清单(长链路健忘), 清单会停留在旧状态, 无人提醒
- 清单状态仅存在于模型上下文, 会话中断即丢失(无持久化)

### 4.2 方案B: 单任务聚焦 + nag 提醒(Claude Code 特性)

**一句话**: 在方案A基础上, 后端**维护会话内清单状态**, **强制 in_progress 唯一**, 并**连续3轮未更新时自动注入提醒**。

**行为**:
- 后端为每个会话维护一份清单状态(内存或DB)
- **单任务聚焦**: 模型把某项标 `in_progress` 时, 后端**自动把其他 in_progress 项改为 completed**(强制唯一)
- **nag 提醒**: 连续 3 轮 LLM 调用未更新清单时, 后端**自动注入提醒文本**给模型(防健忘)
- 清单状态可跨调用持久化(会话内)

**优点**:
- **强制单任务聚焦** → 用户看到的"进行中"永远唯一, 更清晰
- **nag 提醒** → 防模型长链路健忘, 清单不会陈旧
- 状态可持久化(会话恢复)

**缺点**:
- 实现更复杂(需会话级状态管理 + 轮次计数器)
- 行为与 opencode 不一致(模型需适应"自动完成旧任务")
- 有并发/一致性风险(多轮并发更新)

### 4.3 差异对照表

| 维度 | 方案A(纯回显) | 方案B(单任务聚焦+nag) |
|---|---|---|
| 后端状态 | 无(纯函数) | 有(会话级清单状态) |
| in_progress 唯一 | ❌ 可多个 | ✅ 强制唯一 |
| nag 提醒 | ❌ 无 | ✅ 连续3轮未更新注入 |
| 持久化 | 无(模型上下文) | 可持久化(会话恢复) |
| 实现复杂度 | 低(纯函数) | 中(状态机+计数器) |
| 与 opencode 一致 | ✅ 完全一致 | ❌ 增强版 |

### 4.4 建议
- **一期推荐方案A**(纯回显, 一致 opencode): 实现简单、行为可预期, 先跑通链路
- **方案B(单任务聚焦+nag) 二期**: 待一期稳定后按需增强(Claude 特性, 非必须)

> 注: 用户若明确选方案B, 设计按方案B落地; 本文档默认按方案A(一期) + 方案B(二期) 规划。

---

## 5. 工具分类归属(用户提问: 两个 tool 属什么类)

### 5.1 现状: 现有分类装不进去

`app/tools/tool_types.py` 的 `ToolCategory` 当前 9 个成员(含已删 SHELL 留下的空位号 2):

| 分类 | value | order | 中文名 | 语义 |
|---|---|---|---|---|
| FILE | file | 0 | 文件操作工具 | 读写/查找/压缩本地文件 |
| FUNDAMENTAL | fundamental | 1 | 基础工具 | 基础信息获取(搜索/抓页/时间) |
| NETWORK | network | 3 | 网络请求工具 | HTTP/下载/端口 |
| DESKTOP | desktop | 4 | 桌面交互工具 | 窗口/鼠标/键盘/剪贴板 |
| DOCUMENT | document | 5 | 文档操作工具 | docx/xlsx/pdf/媒体 |
| DATAANALYSIS | dataanalysis | 6 | 数据分析工具 | SQL/数据统计 |
| SYSTEM | system | 7 | 系统管理工具 | 进程/事件日志/任务 |
| TIMER | timer | 8 | 定时器工具 | 定时器/时间计算 |
| WIN_REGISTRY | win_registry | 9 | 注册表工具 | 注册表读写 |

**判定**: 两个工具都是"**智能体与用户/与自身计划交互**"的语义, 既不操作文件/网络/硬件, 也不做数据处理——
- question 不是 NETWORK(不发起网络), 不是 SYSTEM(不管理系统), 落任何一个现有分类都是**语义错配**
- schedule 更明显: 零副作用纯回显, 不属于任何"操作类"分类

**结论: 不在现有分类里, 必须新增。**

### 5.2 决策: 新增 `ToolCategory.AGENT`

```python
# app/tools/tool_types.py
AGENT = ("agent", 10, "智能体交互工具")   # 追加在 WIN_REGISTRY=9 之后
```

**理由**:
1. **OCP**: `ToolCategory` 本身就是"新增分类只改此文件"的单一登记源(`CATEGORY_ORDER`/`CATEGORY_NAMES` 自动派生), 新增成员零副作用
2. **order=10 追加在尾部**: 不动 order=2 的 SHELL 空位(避免 `searchtool` 描述排序变化, 见该文件 2026-10-02 编辑历史)
3. **语义成组**: 后续同类工具(如 elicitation/plan/agent 自省类)自然归入, 不再散落
4. **对 LLM 可见性不变**: 分类只影响 `load_category` 分组与 `searchtool` 描述, 不改变单工具的 `visible_to_llm` 判据

### 5.3 连带登记(新增分类必须同步的 2 处)

| 位置 | 修改 | 不做的后果 |
|---|---|---|
| `tool_types.py` | `AGENT = ("agent", 10, "智能体交互工具")` | 分类不存在, 注册时 `ToolCategory.AGENT` 导入失败 |
| `tool_constants.py` `CATEGORY_MODULES` | `"agent": ("app.tools.agent", "_register_agent_tools")` | 启动注册时该分类无模块 → 工具永不注册(静默 0 工具) |

> `CATEGORY_ORDER` / `CATEGORY_NAMES` 为自动派生, **不需手改**(DRY)。

---

## 6. question 的事件模型(用户提问: 也是 paused? 要改造 paused 吗?)

### 6.1 结论: 不复用 `paused`, 新增独立事件对

**不改造 `paused` 的 4 条硬理由**:

| # | 理由 | 具体耦合 |
|---|---|---|
| 1 | `paused` 与 confirm_id 强绑定 | `sseParser.ts` case `paused` 直接把 `confirm_id/tool_name/params/safety_level` 塞进 `onAuthorizationRequired` → `AuthorizationModal`; 加 `kind` 判据要在这条链上处处分流 |
| 2 | `paused` 与信任落库强绑定 | `hitl_confirm` 内部 `create_confirmation(tool_name, path)` → `resolve_confirmation(trust_session)` → 写 `chat_session_trust`; question 无信任语义, 混入即污染 |
| 3 | `paused` 与确认 API 强绑定 | `/chat/stream/confirm` 只认 `confirm_id + confirmed + trust_session` 二值; question 要的是 `answers: [[...]]` 多值 |
| 4 | `paused` 与状态推导强绑定 | `hitlWaitingKeys` 决定 `status` 回 `active` 还是保持 `paused`; 混入会让"授权"与"问答"的等待集互相污染 |

**复用 `paused` 的成本 = 新增独立事件对的成本**, 但前者要动 6 个既有文件的分支判断(等于给所有现存 HITL 路径加回归风险), 后者只做**新增**(既有路径零改动)。按 KISS-DIRECT + 禁止 backward, 选独立事件。

### 6.2 事件定义

沿用本仓已有的 `MetaStep` 元事件机制(`steps/base.py`), 与 `notice` 信封(kind+phase 多子事件)是同一思路, 但 **question 是阻塞事件, 不能借用非阻塞的 notice**:

| 事件 type | 时机 | 语义 | 落库 | 关键字段 |
|---|---|---|---|---|
| `question_required` | 工具进入阻塞前 | 请用户回答 | ❌ 仅 SSE | `question_id`, `questions`(归一化数组) |
| `question_resolved` | 阻塞结束(回答/取消/超时) | 问询已关闭 | ❌ 仅 SSE | `question_id`, `outcome`(answered/cancelled/expired) |

**帧样例**(SSE, 裸键由 `MetaStep._extra_fields` 从 step_model 派生):
```json
{"type":"question_required","step":7,"content":"需要你回答 2 个问题",
 "question_id":"task_xxx:9f3a1c2d",
 "questions":[{"header":"认证","question":"选择认证方式?","options":[{"label":"OAuth","description":"..."}],"multiple":false}]}
{"type":"question_resolved","step":7,"content":"用户已回答","question_id":"task_xxx:9f3a1c2d","outcome":"answered"}
```

**为什么不用一对事件 name 承载子类型(如 `question phase=start/done`)**: 本仓 `notice` 用 `kind+phase` 是因为通知种类多(4+)且语义同族; question 只有"请答/已结"两态且**必须阻塞转发**(仅 SSE、不进持久化、不进统计), 两个扁平 type 更直白, 且与 `paused/resumed` 的既有成对范式一致。

### 6.3 后端登记点(6 处, 缺一不放行)

| # | 文件 | 改动 | 说明 |
|---|---|---|---|
| 1 | `services/agent/steps/__init__.py` `ALL_STEP_TYPES` | 加 `"question_required"`, `"question_resolved"`(仅SSE 组) | 唯一登记源; `_SSE_FORWARD_TYPES` 由它自动派生 |
| 2 | `monitoring/agent_telemetry.py` `SSE_ONLY_TYPES` | 加同两项 | 不落 `chat_task_steps` |
| 3 | `monitoring/agent_telemetry.py` `M_SKIP` | 无需改(并集自动含) | 断言 `not (SSE_ONLY & PERSISTED_NON_BIZ)` 保持成立 |
| 4 | `services/chat/stream_orchestrator.py` | 无需改(`_SSE_FORWARD_TYPES = ALL_STEP_TYPES - {"thought"}`) | 白名单自动覆盖(OCP) |
| 5 | `services/agent/steps/base.py` `MetaStep` docstring | 注释补两个 type | 契约文档, 非逻辑 |
| 6 | `services/agent/handlers/question_gateway.py`(新) | 唯一发射点 | 对称 `hitl_gateway` |

> **纪律**: `steps/__init__.py` 头部要求"新增任何 Step/事件类型必须先在此登记, 并携带通道路由表(SSE/DB/短信号)逐行对照"——本事件的通道路由为 **SSE✓ / DB✗ / 短信号✗**。

### 6.4 前端改动点(8 处)

> 复核补正(2026-11-18): 原 6 处漏了 SSE 白名单与快照类型两处, 帧会被静默丢弃/切会话丢状态。以系统既有代码范式为准, 现为 8 处。

| # | 文件 | 改动 |
|---|---|---|
| 1 | `types/chat.ts` | `StatusMessage.type` 联合加 `'question_required' \| 'question_resolved'`; 加 `question_id?: string; questions?: QuestionItem[]; outcome?: string` |
| 2 | `services/sseParser.ts` | `KNOWN_EVENT_TYPES` 白名单(L185)加两个 type(漏加则帧在 switch 前被丢弃、seq 不推进); 加 `case 'question_required' / 'question_resolved'`, 调 `handlers.onQuestionRequired/onQuestionResolved` |
| 3 | `streams/backupTypes.ts` | 加 `QuestionItem`/`PendingQuestionPayload` 类型; `SessionSnapshot` 加 `pendingQuestion` 字段 |
| 4 | `streams/chatStreamTransport.ts` | 新增 `questionHandlers` 组: 写 `pendingQuestion` + `hitlWaitingKeys`(复用, 见 6.5) |
| 5 | `streams/chatStreamStore.ts` | 会话态加 `pendingQuestion`; 进快照(`bump` 字面量)+`SNAPSHOT_KEYS`+`toBackupOf`; 加 `acknowledgeQuestion(sessionId)` |
| 6 | `components/layout/SessionPanelRegistry.ts` | `SlotName` 加 `'question'` |
| 7 | `components/layout/SessionLayout.tsx` | 底部停靠区加 `question` 行, 位置在 `input` 槽上方(对齐 opencode composer 上方) |
| 8 | `hooks/useChatPanels.tsx` | 注册 `question.dock` 槽(参照 `taskinfo.bar`/`input.chat` 注册模式), 新 props 进 useMemo 依赖数组 |

### 6.5 状态推导: 复用 `hitlWaitingKeys`, 不新增等待集合

**关键取舍**: `hitlWaitingKeys` 的真实语义是"**正在等待人工**的 id 集合", 不是"授权专用"。question 与 HITL 的等待语义完全相同(不超时、不显示流式、等用户动作), 因此:

- `question_required` → `hitlWaitingKeys.add(question_id)`
- `question_resolved` → `hitlWaitingKeys.delete(question_id)`

**收益**: `status` 回 `active` 还是保持 `paused` 的推导、`isHitlWaitingRef` 计时保护、终态清空、持久化/备份字段——**全部零改动**(该集合 23 处引用、5 个文件)。

**代价与约束**: 集合内 id 分属两个命名空间(`{task_id}:{hex}` 形态相同), 所以:
- 任何 `delete` 必须**按 id 精确删**(现状已是), 严禁 `clear()`
- `onResumed`/`onRejected` 只删自己的 `confirm_id`, 不得按前缀/通配删
- question_id 与 confirm_id 生成时**共用同一格式**但**永不相等**(各自独立 `uuid4().hex[:8]`)

> 若未来出现"同一 id 需区分来源"的需求, 再拆 `questionWaitingKeys`; 一期不做(YAGNI)。

---

## 7. question 工具设计(Omni 落地)

### 7.1 总体原则(用户拍板)
1. **按 opencode 主体设计** —— 多问题/多选/自定义输入/阻塞式
2. **从禁用名单移除** —— `challenge` 见 §11 配置真值源
3. **超时复用 `security.hitl.timeout`(默认120s)** —— 与 HITL 确认超时同源
4. **人工干预开关继承 HITL** —— 复用 `security.hitl.enabled`
5. **工具层不得 `import app.services`**(守护测试硬规则) —— 阻塞能力经 `tools/context.py` 的 ContextVar **注入回调**取得

### 7.2 注入契约(本仓真实形态)

工具是 `tools` 层的叶子, 不能反向依赖 `services`。本仓既有的三处先例(`_current_hooks` / `_current_text_task` / `_current_notice_callback`)全部采用同一模式, question 照此新增:

```python
# app/tools/context.py 追加(与 _current_notice_callback 同构)
# "问询回调": 入口层(tool_executor)持 agent 注入,
#   签名 async (questions: List[Dict[str, Any]]) -> Dict[str, Any]
#   返回 {"answers": List[List[str]], "cancelled": bool, "expired": bool, "reason": str}
_current_question_callback: ContextVar[Optional[object]] = ContextVar("current_question_callback", default=None)

def get_current_question_callback() -> Optional[object]: ...
def set_current_question_callback(callback): ...   # 返回 token
def reset_current_question_callback(token) -> None: ...
```

**注入点**: `services/agent/tool_executor.py` 的 `execute_tool`, 与 `_invoke_notice` 并列(同一 `try/finally` 收口):

```python
async def _invoke_question(questions):
    return await agent._step_emitter.ask_question(questions)   # 阶段B: 由 question_gateway 承担

_question_token = set_current_question_callback(_invoke_question) if _has_emitter else None
```

> 为什么经 `agent._step_emitter` 而不是 `tool_executor` 直连 services: `hitl_confirm` 也持 `agent._step_emitter.emit(...)`, 发射器本就属 agent; 阶段B 在发射器上挂 `ask_question` 方法(内部调 `question_gateway`), 保持 `tool_executor` 只做注入不持业务。

### 7.3 Schema(本仓形态: 不用嵌套 BaseModel)

**约束来源(实测本仓契约, 不是偏好)**:
- `ToolRetryEngine._validate_params` 只校验**顶层**键名/必填/type 粗判, **不实例化**嵌套 Pydantic 模型 → 嵌套模型给了虚假的安全感
- `registry.register(input_model=...)` 经 `_generate_input_schema` → `_fix_schema_types`, 嵌套 BaseModel 会生成 `$defs/$ref`, 该函数**不内联**, 部分 provider 严格校验会拒
- 本仓现有 25 个工具目录**零例**使用嵌套 BaseModel

```python
# app/tools/agent/agent_schema.py
class QuestionInput(BaseModel):
    questions: List[Dict[str, Any]] = Field(
        ..., description="问题数组(1~8项)。每项: {question:完整问题, header:极短标签(≤30字), "
                         "options:[{label:选项文本, description:选项说明}](1~9项), multiple:是否多选(默认false)}"
    )

class ScheduleInput(BaseModel):
    items: List[Dict[str, Any]] = Field(
        ..., description="完整计划清单(整体替换, 传[]即清空)。每项: {content:任务简述, "
                         "status:pending|in_progress|completed|cancelled}"
    )
```

**语义校验在工具内手工完成**(见 §8.1 校验矩阵), 校验失败返回 `build_error` + `hint`, 让 LLM 自纠——与 timer/dataanalysis 等既有工具同款做法。

### 7.4 前端(基于 opencode DockPrompt 范式, **非 Modal 弹窗**)

> **核心结论(用户驱动)**: question 页面**不能复用 HITL 弹框**。opencode 的 question 是**卡片式底部停靠面板**(DockPrompt, 内嵌 composer 上方), 而 Omni HITL 是 **antd Modal 居中弹窗**(520px 遮罩居中)。两者形态/交互/数据流完全不同。详见 §7.4.0 对比。

#### 7.4.0 opencode question 前端研究(设计依据)

**形态 = DockPrompt 卡片式底部停靠面板**(`session-ui/src/components/dock-prompt.tsx`):
- 卡片: `bg-base` + `border-radius:10px` + `box-shadow:elevation-raised`, 内嵌 composer 上方
- 三区: header(标题+进度+最小化)/ content(options + 自定义输入)/ footer(dismiss+back+next/submit)
- 最大高度受 `--question-prompt-max-height` 约束(视口内自适应, 不溢出)

**两套渲染**(`session-question-dock.tsx` 按 `settings.general.newQuestionUI()` 切换):
- `session-question-dock-classic.tsx`(871行) —— question 专用默认版
- `session-question-dock-experimental.tsx`(1572行) —— 精细动画版(spring/ghost 切换/滚动羽化)
- `session-elicitation-dock.tsx`(288行) —— 通用表单版(string/number/boolean/multiselect/external)

**挂载点**(`session/composer/session-composer-region.tsx`):
- `SessionQuestionDock` / `SessionElicitationDock` / `SessionPermissionDock` 都停靠在 composer 上方
- 通过 `controller.state.question/elicitation/permission` 驱动, `Grow+card` 堆叠

**数据流**(`core/src/form.ts` Form 服务):
- 后端 `create` → `bus.publish(Form.Event.Created)` → 前端订阅 → 渲染 DockPrompt
- 前端 `form.reply({sessionID, formID, answer})` / `form.cancel({sessionID, formID})` → 后端 `Deferred.succeed`
- `ask` = create + 阻塞等待(question 工具用)

**交互特性**(比 Omni HITL 强得多):
| 特性 | 说明 |
|---|---|
| 多问题分页 | `questions[]` 数组, tab 切换 + 进度条分段(`question-progress-segment`) |
| 单选/多选 | radio / checkbox, `multiple` 开关 |
| 自定义输入 | `custom:true` 自动加"输入自己的答案"输入框 |
| 数字快捷键 | `1-9` 选选项 |
| 键盘导航 | ArrowUp/Down/Home/End/Enter/Escape/Ctrl+Enter/Alt+Left |
| 最小化/恢复 | 折叠动画(spring) |
| 状态缓存 | `questionCache`(Map: tab/answers/custom/customOn, 防会话切换丢失) |

**FormInfo 结构**(`client/src/promise/generated/types.ts`):
```ts
FormInfo = { id, sessionID, title, metadata?, fields: FormFields }
FormStringField = { key, title?, description?, type:"string", options?, custom? }
FormMultiselectField = { key, title?, description?, type:"multiselect", options, custom?, default? }
FormAnswer = { [x:string]: string|number|boolean|string[] }
```

#### 7.4.1 Omni HITL 现状与差距(为什么不能复用)

**Omni HITL**(`components/AuthorizationModal/index.tsx` + `HITLModalShell.tsx`):
- antd `Modal` **居中弹窗**(520px 宽, 橙色/蓝色边框, 遮罩居中)
- **二值确认**: 允许/拒绝 + 信任勾选 + 倒计时环
- 数据流: SSE `paused` 帧 → `Store.pendingAuthorization` → `useAuthorization` → Modal
- 只处理**单工具操作确认**, 无多问题/多选/自定义输入

**差距表**:
| 维度 | Omni HITL | opencode question | 结论 |
|---|---|---|---|
| 形态 | Modal 居中弹窗 | DockPrompt 底部停靠卡片 | **不能复用** |
| 交互 | 二值(允许/拒绝) | 多问题/多选/自定义 | **不能复用** |
| 数据流 | confirm_id 单确认 | form_id 多字段 | **不能复用** |
| 技术栈 | React + antd | SolidJS + 自研 | 移植范式, 非拷组件 |

#### 7.4.2 Omni question 前端设计(新文件, 基于 opencode 范式)

**目录**: `frontend/src/features/chat/components/question/`(与 taskinfo/config/input 同层, 会话内面板)
- `QuestionDock.tsx` —— 卡片式底部停靠面板(header/content/footer 三区)
- `QuestionOption.tsx` —— 单选项(antd `Radio.Group`/`Checkbox` + 数字快捷键)
- `QuestionCustomInput.tsx` —— 自定义输入框(antd `Input.TextArea`)
- `useQuestionDock.ts` —— 状态管理(tab/answers/custom/customOn, 经 `useChatStreamSession` 读 `pendingQuestion`)

> 复核补正(2026-11-18): 不建 `QuestionDock.css`。系统既有范式是无 CSS Modules/组件级 CSS 文件, 组件内联 `style={{}}`, 视觉值统一取 TS 设计 token(§7.4.3)。opencode `question-prompt.css` 只作范式参考, 不拷样式。

> **归属依据**: chat 会话内面板(taskinfo/config/input)统一放 `features/chat/components/` 下, 由 `useChatPanels.tsx` 按 slot 注册; `components/` 一级目录仅放页面级全局组件(如 AuthorizationModal, ChatPage 引用)。QuestionDock 是会话内停靠面板, 应归 `features/chat/components/question/`。

**挂载点**(而非 Modal):
- 复用 `SessionLayout` 底部停靠区(`features/chat/components/layout/SessionLayout.tsx:219-232`, taskinfo/config/input 三槽)
- question dock 停靠 **input 槽上方**(与 opencode composer 上方一致)
- 通过 `SessionPanelRegistry` 注册新槽 `question`(参照 taskinfo/config/input 注册模式)
- **需扩展 `SessionPanelRegistry.ts:15-27` `SlotName` 联合类型**, 加 `'question'`
- 面板注册在 `useChatPanels.tsx`(参照 taskinfo.bar:331 / input.chat:357 注册模式)

**数据流**:
- `question_required` 帧 → `chatStreamTransport.questionHandlers` → `chatStreamStore.pendingQuestion`
- `useQuestionDock` 订阅 `pendingQuestion` → 渲染 QuestionDock
- 提交 → `taskControlApi.answerQuestion(questionId, answers)` → 后端 `resolve_question`
- 关闭 → `taskControlApi.answerQuestion(questionId, [], cancel=True)` → 后端按 cancelled 收口 + 前端 `acknowledgeQuestion(sessionId)`(防切回重弹)

**交互**(照搬 opencode):
- 多问题分页(tab + 进度条分段)
- 单选/多选(radio/checkbox)
- 自定义输入(custom 恒开, 与 opencode `custom:true` 一致)
- 数字快捷键 1-9 + 键盘导航(Arrow/Home/End/Enter)
- Escape=dismiss(cancel)、Ctrl+Enter=next/submit、Alt+Left=back
- 最小化/恢复(折叠)
- 状态缓存(questionCache, 防会话切换丢失)

#### 7.4.3 系统前端范式对齐复核(2026-11-18)

> 用户要求"页面 UI/UE 设计参考系统的规范进行", 系统规范 = 前端既有代码范式(非 opencode 样式原文)。逐项复核结论如下, 与 §7.4.2 一起作为实施契约。

| 维度 | 系统既有范式(实证文件) | question 落地约束 |
|---|---|---|
| 组件库 | antd 5 (`Button`/`Tag`/`Typography`/`Checkbox`/`Input`/`Progress`), `@ant-design/icons`, 全中文文案, 交互元素带 `aria-label` 与 `data-testid` | `QuestionOption` 用 `Radio.Group`/`Checkbox`, 自定义输入用 `Input.TextArea`, 按钮用 antd `Button`, 不手写原生标签 |
| 视觉真源 | `utils/stepStyles.ts` 的 `Colors/FontSize/FontWeight/Spacing/Radius/BorderWidth`, `theme/spacing.ts` 的 `Gap/LineHeight`, `theme/controlScale.ts` 的 `CONTROL_HEIGHT*/CONTROL_RADIUS/FOCUS_RING_*`, `theme/tokens.ts` 的 `chatTokens` | 所有颜色/间距/字号/圆角/控件高度/焦点环取 token, 禁裸数字; 全局只有 `--font-mono` 一个 CSS 变量, 不新增组件 CSS 文件 |
| 停靠区 | `SessionLayout.tsx:219-232` 底部 dock 顺序 taskinfo→config→input, 行容器无边框无高度(高度随内容), 根 gap 分隔 | question 行插在 input 上方; 卡片用 `Colors.BG.PRIMARY` 底 + `Colors.BORDER.LIGHT` 边 + `Radius.LG` + `boxShadow`, 高度受 `Size.PARAMS_PANEL_MAX_H` 类约束不溢出视口 |
| 数据流 | `useAuthorization.ts`: `useChatStreamSession` 读 store 快照 → 映射为请求态(同 id 去重) → fire-and-forget 调 `taskControlApi` → 成功后 `acknowledge*` 清快照 | `useQuestionDock` 同构: 读 `pendingQuestion` → `QuestionRequest`, 提交经新增 `taskControlApi.answerQuestion`, 收口 `acknowledgeQuestion` |
| SSE 登记 | `sseParser.ts` `KNOWN_EVENT_TYPES` 白名单 + `case` 双登记, 漏一则帧静默丢弃 | 两个 type 必须同时进白名单与 switch(§6.4 #2) |
| 快照持久化 | `chatStreamStore.ts` `bump()` 字面量 + `SNAPSHOT_KEYS` + `toBackupOf()` 三处同步, 缺一切会话丢状态/重连不恢复 | `pendingQuestion` 三处齐改(§6.4 #5) |
| E2E 可测 | `e2e_case/*.spec.ts` 用 `getByTestId`/`getByRole`, `frontend/src/tests/` 被 gitignore | 面板/选项/提交/关闭各给稳定 `data-testid`, 前端用例见 §13.3 B5 |

### 7.5 超时与降级

| 场景 | 行为 | LLM 侧结果 |
|---|---|---|
| `security.hitl.enabled=false` | 不创建问询, 不阻塞 | `error` + hint「人工问答已关闭, 请自行决策并说明假设后继续」 |
| 回调未注入(直调工具/无 agent) | 同上, 不阻塞 | `error` + 同上 hint |
| 等待超时(`security.hitl.timeout`) | 后端关闭问询, 发 `question_resolved(outcome=expired)` | `error` + hint「用户未在N秒内回答, 请基于最合理假设继续, 不要重新提问」 |
| 用户取消(关闭面板) | 后端关闭问询, 发 `question_resolved(outcome=cancelled)` | `error` + hint「用户已放弃本次提问, 请停止推进并在最终回答中说明已中断」 |
| 用户回答 | — | `success`, `summary` 含问答对, LLM 直接据以继续 |
| 回调内部异常 | 工具捕获, 不外抛 | `error` + hint「问询通道异常, 请自行决策后继续」 |

> **与 opencode 的差异(有意为之)**: opencode 用 `die(CancelledError)` 终止步骤; 本仓工具层的异常会被重试引擎归类成失败并重试/吞掉, 用异常做控制流会失真。故取消/超时统一以 `build_error + hint` 表达, 由模型收口——语义等价, 且不引入新的控制流通道。

---

## 8. schedule 工具设计(Omni 落地, 按方案A)

### 8.1 后端结构

**Schema**: 见 §7.3 `ScheduleInput`。

**校验矩阵**(工具内手工校验, 失败均 `build_error`):

| 校验项 | 规则 | hint |
|---|---|---|
| items 类型 | 必须是 list(可为空) | 「items 必须是数组」 |
| 单条类型 | 必须是 dict | 「每项必须是对象」 |
| content | 非空字符串, ≤200 字 | 「任务简述不能为空/过长」 |
| status | ∈ {pending,in_progress,completed,cancelled} | 「status 只能取四个值之一」 |
| 条数 | ≤50 | 「清单过长, 请合并相似任务」 |

**执行逻辑**(纯回显, 零状态):
```python
async def schedule(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    normalized, err = _normalize_items(items)     # 校验 + 归一
    if err:
        return build_error(data={"items": []}, llm_data=_llm_data("error", err, [], 0))
    summary = _summarize(normalized)              # 照搬 opencode summarize
    return build_success(
        data={"items": normalized},               # 原样回显
        llm_data=_llm_data("success", "", normalized, elapsed_ms),
    )
```

**`_summarize`(照搬 opencode, 中文口径)**:
```python
if not items: return "计划已清空"
total = len(items); completed = 已计数
parts = [f"{completed}/{total} 已完成"]
for s in ("in_progress", "pending", "cancelled"): 有则追加 f"{n} 进行中/待开始/已取消"
active = [i["content"] for i in items if i["status"] == "in_progress"]
return f"计划已更新: {', '.join(parts)}" + (f"。进行中: {', '.join(active)}" if active else "")
```

### 8.2 前端(一期零新增, 二期面板)

**一期(方案A)**: 清单以 **observation 文本**呈现(用户可见的执行计划), 零前端改动。
- `llm_data.summary` 已含"3/5 已完成, 进行中: 编写代码", observation 渲染即用户可见
- 依据: 本仓 tool_result **无 `metadata` 通道**(只有 `tool_name/llm_data/data_text/raw_data/other_data`), `data.items` 不进前端渲染链路

**二期(可选, 独立事件)**: 新增 `schedule_updated` 事件 + `TaskListPanel` 面板, 与 question 事件同一套登记纪律(§6.3)。
- 需先决定: 事件是否落库(建议仅 SSE), 面板是否跨会话恢复(建议否)

> **为什么不一期就做面板**: 一期目标是跑通"模型有计划 → 用户看得见"闭环; 面板需要新增事件类型+槽位+持久化三项登记, 与 question 的 6 处前端改动叠加会把首版回归面放大一倍。按 YAGNI 分期。

### 8.3 权限与开关
- 无需 HITL 确认(纯信息展示, 零副作用, 无 save 语义)
- 无需人工干预开关
- **不进 `TOOL_RETRY_CONFIG`**(无重试语义)

---

## 9. 本仓契约对齐(实施前必读)

> 本节是"设计文档能不能直接写成能跑的代码"的关键。原版 §5.2/§6.1 的代码形状与本仓契约不符, 已在此逐条订正。

### 9.1 工具函数签名

**本仓铁律**: 工具是 `async def tool(**typed_params)`, 由引擎 `tool(**normalized_input)` 调用(参数名=Schema 属性名, 多传/少传在 `_validate_params` 阶段就被拦)。
**不是** `def tool(input: dict, context)`——设计文档原版按 opencode 的 `execute(input, context)` 写, 在本仓会直接 TypeError。

```python
async def question(questions: List[Dict[str, Any]]) -> Dict[str, Any]: ...
async def schedule(items: List[Dict[str, Any]]) -> Dict[str, Any]: ...
```

### 9.2 返回结构

**本仓铁律**: `build_success(data=, llm_data=, other_data=, **extra)` / `build_error(...)`。
**没有 `metadata` 通道**——原版 `build_success({"output":..., "metadata":...})` 把 opencode 的返回形状误当成本仓参数(那个 dict 会被当成 `data`)。

| 通道 | 消费者 | question 内容 | schedule 内容 |
|---|---|---|---|
| `data` | 工具间/调试/落盘 | `{answers, questions}` | `{items}` |
| `llm_data.summary` | LLM 与 observation 文本 | 问答对摘要 | 计划统计摘要 |
| `llm_data.action` | 观察行渲染 | `{tool, tool_zh, params}` | 同 |
| `llm_data.status` | `is_success` 判据(`exec_code`) | success/error + code/detail/hint | 同 |
| `llm_data.duration_ms` / `metrics` | 遥测 | 耗时 / `{wait_ms}` | 耗时 / 计数 |

`tool_zh` 取值(短名词, 遵 2026-10-12 约定): question → `提问`; schedule → `计划`。

### 9.3 参数校验深度

`_validate_params` 只做顶层: 非法键名 → `ERR_INVALID_PARAMS`; 缺必填 → `ERR_MISSING_PARAM`; type 粗判。
**不做**嵌套校验、不做范围校验 → 全部落在工具内(§7.3 / §8.1), 并用 `hint` 引导 LLM 自纠。

### 9.4 超时保险丝(★ 不处理必被误杀)

`tool_retry_engine._compute_fuse` 两条路径:
- 有 inner timeout 参数 → `inner × (max_retries+1) + INSURANCE_BUFFER(30)`
- **无 inner(question 属此类)** → `min(base_timeout × (attempt+1), PROGRESSIVE_MAX=300)`, `base = TOOL_TIMEOUTS.get("question", TOOL_TIMEOUTS["default"]=60)`

**实测后果**: question 无 `timeout` 参数 → 保险丝 = 60s; 而 `security.hitl.timeout` 默认 120s(可配到 86400) → **用户还没答完就被 `asyncio.wait_for` 掐死**。

**必须的改法**(阶段B, 一行分支, 不引入注册表):
```python
# _compute_fuse 开头
if action == "question":
    from app.config import get_config
    from app.constants import HITL_TIMEOUT as _D
    return int(float(get_config().get("security.hitl.timeout", _D))) + INSURANCE_BUFFER
```
配套: **不把 question 写进 `TOOL_RETRY_CONFIG`** → `max_retries=0` → 不会重复弹问。

### 9.5 Schema → LLM 可见性

- `$defs/$ref` 不内联(§7.3), 故用扁平模型
- `register(input_model=...)` 会自动生成 `input_schema`, `expose_to_llm=True` 默认
- 两工具都**不放** `TOOL_TIMEOUT_HINTS`(question 超时由网关表达, schedule 无超时)
- 两工具都**不放** `TOOL_CATEGORY_OVERRIDE`(分类由注册时的 `category=ToolCategory.AGENT` 决定)

---

## 10. 注册接入点(两工具共通, 阶段B执行)

### 10.1 新建类别目录
```
backend/app/tools/agent/
├── __init__.py          # 导出 _register_agent_tools(参照 timer/__init__.py: 显式 import + __all__)
├── agent_register.py    # _register_agent_tools() 注册两工具
├── agent_schema.py      # QuestionInput / ScheduleInput
├── question.py          # question 工具实现
└── schedule.py          # schedule 工具实现
```

> **__init__.py 规范**: 现有目录 __init__.py 只导出 `_register_*` 函数(注册入口), 工具实现函数经 register 内部引用; 与 timer 范式一致。

### 10.2 接入点(5 处)

| # | 文件 | 改动 |
|---|---|---|
| 1 | `tool_types.py` | `ToolCategory` 加 `AGENT = ("agent", 10, "智能体交互工具")` |
| 2 | `tool_constants.py` | `CATEGORY_MODULES` 加 `"agent": ("app.tools.agent", "_register_agent_tools")` |
| 3 | `tools_alias_mapper.py` | `PARAM_ALIASES` 加 `question`/`schedule` 条目(键名归一: `qs→questions`, `todos→items`, `todo→items`, `tasks→items`, `plan→items`, `content/text→content`, `state→status`) |
| 4 | `tools_alias_mapper.py` | `UNAVAILABLE_OFFICIAL_TOOLS` 移除 `question`(回落默认与配置保持一致) |
| 5 | `config/config.yaml` `tuning.agent.disabled_tools` | 移除 `question` (**真值源**) |

> **首次注入补正(2026-11-18)**: 注册≠注入。默认 `UniversalAgent._INITIAL_CATEGORIES` 只有 FUNDAMENTAL+FILE, 若不加 AGENT, 两工具不会出现在首次工具列表, 只能等 LLM 主动 `searchtool` 动态加载(实测不主动搜即永远看不到)。本次把 `ToolCategory.AGENT` 加入初始注入集, 实测首次工具列表含 question/schedule; `config.yaml.example` 同步移除 question。

### 10.3 agent_register.py 模板(参照 timer_register.py)

```python
AGENT_TOOL_DESCRIPTIONS = {
    "question": "执行中向用户提问, 收集偏好/澄清歧义/获取实现决策。questions 为问题数组, "
                "每项含 question(完整问题)/header(短标签)/options(选项数组)/multiple(是否多选)。"
                "适用于: 需要用户决策、指令存在歧义、多个方案需用户选择时。阻塞等待回答后继续。",
    "schedule": "创建/更新当前会话的任务计划清单(用户可见的执行计划)。items 为完整清单(整体替换), "
                "每项含 content(任务简述)/status(pending|in_progress|completed|cancelled)。"
                "适用于: 任务≥3个步骤、用户给了多项任务、用户索要计划时。单一简单任务不要用。",
}
AGENT_INPUT_MODELS = {"question": QuestionInput, "schedule": ScheduleInput}
AGENT_TOOL_EXAMPLES = {
    "question": [{"questions": [{"question": "选择哪种认证方式?", "header": "认证",
                                 "options": [{"label": "OAuth", "description": "第三方登录"},
                                             {"label": "JWT", "description": "自建账号体系"}]}]}],
    "schedule": [{"items": [{"content": "分析需求", "status": "completed"},
                            {"content": "编写代码", "status": "in_progress"},
                            {"content": "测试", "status": "pending"}]}],
}
```

---

## 11. 配置变更(阶段B)

```yaml
security:
  hitl:
    enabled: true        # 已存在, question 复用此开关(继承)
    timeout: 120         # 已存在, question 超时复用 + 保险丝基准(§9.4)
tuning:
  agent:
    disabled_tools: skill, subagent, patch, execute   # 修改: 移除 question
# 无新增配置键
```

> **⚠ 禁用名单已配置化(2026-11-10)**: 真值源是 `config.yaml tuning.agent.disabled_tools`(当前 L754, `question, skill, subagent, patch, execute`); `UNAVAILABLE_OFFICIAL_TOOLS` 只是**内置回落默认**(仅配置缺键/不可读/形状异常时用)。`get_disabled_official_tools()` 读配置即热生效。**改了内置元组但不改配置 = 不生效**。

---

## 12. 实施顺序(用户铁律: 先工具, 后接入)

### 12.1 阶段A: 工具内核 + 单测(不注册/不改配置/不动 SSE)

**目标**: 两个工具函数能在**零系统依赖**下跑通全部行为分支。

**产物**:
| 文件 | 内容 | 是否被动生效 |
|---|---|---|
| `app/tools/agent/__init__.py` | 空壳(不导出注册函数) | ❌ 无 `CATEGORY_MODULES` 条目 → 永不 import |
| `app/tools/agent/agent_schema.py` | `QuestionInput` / `ScheduleInput` | ❌ 同上 |
| `app/tools/agent/question.py` | `question()` + 校验 + 降级 + 摘要 | ❌ 同上 |
| `app/tools/agent/schedule.py` | `schedule()` + 校验 + 摘要 | ❌ 同上 |
| `app/tools/context.py` | 追加 question 回调 ContextVar(get/set/reset) | ✅ 生效但**零消费方**(无人 set) |
| `app/tools/tool_constants.py` | 追加 `ERR_QUESTION` / `ERR_SCHEDULE` 两个错误码 | ✅ 生效但**零引用** |

**验收**: §13 全部用例通过; `import app.tools.agent.question` 在**未注册**状态下可正常调用(注入替身回调)。

**不做**: 不写 `agent_register.py`; 不改 `CATEGORY_MODULES`/`ToolCategory`/`PARAM_ALIASES`/`disabled_tools`; 不建 `question_gateway.py`; 不碰 SSE/前端; 不改 `_compute_fuse`。

### 12.2 阶段B: 接系统(分 5 步, 每步可独立验证)

| 步 | 内容 | 验证 |
|---|---|---|
| B1 | 注册: `ToolCategory.AGENT` + `CATEGORY_MODULES` + `agent_register.py` + 别名 + 禁用名单 | 启动日志有 2 个工具; LLM 工具列表可见; 直调 registry 元数据正确 |
| B2 | 超时保险丝特判(§9.4) | question 在 `hitl.timeout=120` 下不被 60s 截杀 |
| B3 | `question_gateway.py`(create/emit/wait/resolve) + `hitl_question.py` 三原语(对称 `hitl_confirmation`) + `/chat/stream/answer` API | 真实后端: 发问 → SSE 见 `question_required` → API 回答 → 工具拿到 answers |
| B4 | 事件登记 6 处(§6.3) + `tool_executor` 注入回调 | 全链路 SSE 顺序正确; 断连重连不重复弹 |
| B5 | 前端 8 处(§6.4) + QuestionDock(§7.4.2/§7.4.3, antd + 设计 token 内联样式) | `npm run check:full` 0 error; e2e: 多问题/多选/自定义/取消/超时五条路径 |

> **禁止跳步**: B2 必须早于 B3, 否则 120s 等待在 60s 被掐死后会误判成"网关 bug"。

### 12.3 二期(可选)

| 项 | 内容 |
|---|---|
| P6 | schedule 方案B(单任务聚焦 + nag) + schedule 面板事件 |
| P7 | question 最小化/动画版(对齐 opencode experimental) |

---

## 13. 测试用例(阶段A 必须全绿)

### 13.1 question 用例

| # | 场景 | 输入 | 期望 |
|---|---|---|---|
| Q1 | 空数组 | `questions=[]` | error, detail 含"至少一个问题" |
| Q2 | 超上限 | 9 个问题 | error, detail 含"最多8" |
| Q3 | 缺 question | `[{"header":"h"}]` | error, detail 点名第 1 个字段 |
| Q4 | header 过长 | header 31 字 | error |
| Q5 | options 空 | `options=[]` | error |
| Q6 | options 超 9 项 | 10 个 | error |
| Q7 | option 缺 label | `[{"description":"x"}]` | error |
| Q8 | multiple 非 bool | `"yes"` | error |
| Q9 | 开关关闭 | 替身 enabled=False | error + hint 含"自行决策", **不阻塞** |
| Q10 | 回调未注入 | 不 set ContextVar | error + hint 同 Q9, **不阻塞** |
| Q11 | 正常回答 | 替身返回 `answers=[["OAuth"],["PostgreSQL"]]` | success; `data.answers` 等长; `summary` 含两个答案; `metrics.wait_ms>=0` |
| Q12 | 超时 | 替身返回 `expired=True` | error + hint 含"未在…回答" |
| Q13 | 取消 | 替身返回 `cancelled=True` | error + hint 含"已放弃" |
| Q14 | 替身抛异常 | raise RuntimeError | error(不外抛), hint 含"通道异常" |
| Q15 | 返回值形状 | Q11 结果 | 顶层键 ⊆ {data,llm_data,other_data}; `llm_data.status.exec_code` 存在; `tool_zh=提问` |
| Q16 | schema 无 `$defs` | `QuestionInput.model_json_schema()` | `"$defs" not in` 且 `"$ref" not in json.dumps` |

### 13.2 schedule 用例

| # | 场景 | 输入 | 期望 |
|---|---|---|---|
| S1 | 正常 3 项 | pending/in_progress/completed 各一 | success; summary 含 "1/3 已完成"; 含"进行中: …" |
| S2 | 清空 | `items=[]` | success; summary == "计划已清空" |
| S3 | 非 list | `items={"a":1}` | error |
| S4 | 单条非 dict | `items=["x"]` | error |
| S5 | content 空 | `content=""` | error, detail 点名第 n 项 |
| S6 | content 超长 | 201 字 | error |
| S7 | status 非法 | `status="done"` | error, detail 列出四个合法值 |
| S8 | 超 50 项 | 51 项 | error |
| S9 | 全 completed | 2 项 completed | summary 含 "2/2 已完成", 不含"进行中" |
| S10 | 返回值形状 | S1 结果 | 同 Q15; `tool_zh=计划`; `data.items` 等长归一 |
| S11 | schema 无 `$defs` | `ScheduleInput.model_json_schema()` | 同 Q16 |

### 13.3 阶段B 补充用例(接系统后)

| # | 场景 | 期望 |
|---|---|---|
| B-T1 | `_compute_fuse("question", {}, 60, 0, 0)` | `= hitl.timeout + INSURANCE_BUFFER`(当前 15, 非 60/300) |
| B-T2 | 注册后 `tool_registry.get_tool("question").category` | `ToolCategory.AGENT` |
| B-T3 | 真实链路: LLM 调 question → 用户答 | SSE 顺序 `question_required` → (answer API) → `question_resolved` → observation |
| B-T4 | 真实链路: 超时 | `question_resolved(outcome=expired)` + observation 为 error |
| B-T5 | 并发两条 question | 两个 id 各自独立, 答一个不影响另一个; `hitlWaitingKeys` 剩 1 时 status 仍 `paused` |
| B-T6 | 会话切走再切回 | QuestionDock 重新出现(读 `pendingQuestion`), 不重复请求后端 |
| B-T7 | `disabled_tools` 移除 question 后 | LLM 工具列表含 question; 旧配置(含 question)回落仍禁用 |
| B-T8 | 前端 SSE 白名单 | `KNOWN_EVENT_TYPES` 含两个 type; 帧进 `pendingQuestion` 不丢 seq |
| B-T9 | 前端 dock 渲染 | `question_required` → QuestionDock 出现在 input 槽上方, 单选/多选/自定义/分页齐全, 样式取设计 token |
| B-T10 | 前端提交/取消/切会话 | `answerQuestion` 提交后 `question_resolved`→dock 消失; 取消同理; 切走再切回 dock 从快照恢复不重弹 |
| B-T11 | 前端规范检查 | `npm run check:full`(typecheck + lint + format:check) 0 error |

---

## 14. 落地核对与风险

### 14.1 落地现状核对(本文档补充时实测)

| 检查项 | 结果 |
|---|---|
| `backend/app/tools/agent/` 目录 | ❌ 不存在 |
| `question.py` / `schedule.py` | ❌ 不存在 |
| `ToolCategory.AGENT` | ❌ 不存在(9 个成员, 无 agent) |
| `CATEGORY_MODULES["agent"]` | ❌ 不存在 |
| HITL question 三原语 | ❌ 不存在(`hitl_confirmation` 只有 confirm 三原语) |
| `question_required` 事件 | ❌ 未登记 |
| 前端 `components/question/` | ❌ 不存在 |
| `pendingQuestion` / `answerQuestion` | ❌ 不存在 |
| `config.yaml disabled_tools` | ⚠️ 仍含 `question`(L754) |
| `UNAVAILABLE_OFFICIAL_TOOLS` | ⚠️ 仍含 `question` |

**结论**: 设计文档存在(commit `24e4e6112`), 落地代码为 **0**。

### 14.2 风险清单

| # | 风险 | 影响 | 处置 |
|---|---|---|---|
| R1 | 保险丝按 default=60s 截杀 120s 等待 | question 永远等不到回答 | §9.4 特判, **B2 先于 B3** |
| R2 | question 误 `import app.services` | 触发 tools 层越层守护规则 | 强制走 ContextVar 注入(§7.2) |
| R3 | 嵌套 BaseModel 生成 `$defs/$ref` | 部分 provider 拒绝该工具 | 扁平 `List[Dict[str, Any]]`(§7.3) |
| R4 | 复用 `paused` 会污染信任落库 | 无信任语义的问询写进 `chat_session_trust` | 独立事件对(§6.1) |
| R5 | `hitlWaitingKeys` 混用后按 id 误删 | 一条问答结束把授权等待也清了 | 只按精确 id 删, 严禁 `clear()`(§6.5) |
| R6 | 长链路忘记更新 schedule | 清单陈旧 | 方案B(二期) |
| R7 | 并发多问询上限 | 内存泄漏/前端堆叠 | 复用 `tuning.hitl.max_pending_confirmations` 上限 + 过期清理(与 HITL 同款) |
| R8 | LLM 滥用 question(每步都问) | 用户被打断 | description 明确"仅在需要决策/歧义时"; 后续可加同类调用频次提示 |

---

## 15. 决策记录

| # | 决策 | 拍板人 | 日期 |
|---|---|---|---|
| 1 | question 按 opencode 主体设计 | 用户 | 2026-11-14 |
| 2 | question 从禁用名单移除 | 用户 | 2026-11-14 |
| 3 | question 超时复用 security.hitl.timeout(默认120s) | 用户 | 2026-11-14 |
| 4 | question 人工干预开关继承 HITL(security.hitl.enabled) | 用户 | 2026-11-14 |
| 5 | todoWrite 功能类似, 名词改 schedule(计划) | 用户 | 2026-11-14 |
| 6 | schedule 一期方案A(纯回显), 方案B二期 | 商量(建议) | 2026-11-14 |
| 7 | question 前端**不能复用 HITL 弹框**, 改用 opencode DockPrompt 底部停靠面板范式 | 用户 | 2026-11-14 |
| 8 | Omni question dock 停靠 SessionLayout 底部停靠区(input 槽上方) | 商量(建议) | 2026-11-14 |
| 9 | 三堂会审: 前端 QuestionDock 归 `features/chat/components/question/`(非 components/) | 商量(三堂会审) | 2026-11-14 |
| 10 | 三堂会审: 禁用名单移除 question 改 `config.yaml tuning.agent.disabled_tools`(已配置化) | 商量(三堂会审) | 2026-11-14 |
| 11 | 新增 `ToolCategory.AGENT`(order 10), 两工具归此类(不属现有任何分类) | 用户提问驱动 | 2026-11-18 |
| 12 | 不复用 `paused`, 新增 `question_required`/`question_resolved` 事件对 | 用户提问驱动 | 2026-11-18 |
| 13 | question 阻塞能力经 `tools/context.py` ContextVar 注入回调(工具层禁 services) | 契约对齐 | 2026-11-18 |
| 14 | 复用 `hitlWaitingKeys` 承载 question 等待集, 不新增等待集合 | 契约对齐 | 2026-11-18 |
| 15 | 先工具内核+单测(阶段A), 再注册接系统(阶段B) | 用户 | 2026-11-18 |
| 16 | schedule 一期不加前端面板, 以 observation 文本呈现(本仓无 metadata 通道) | 契约对齐 | 2026-11-18 |
| 17 | question 前端 UI/UE 以系统既有代码范式为准(antd 5 + 设计 token 内联样式 + dock 槽), 不建组件 CSS 文件、不拷 opencode 样式 | 用户要求(复核) | 2026-11-18 |
| 18 | AGENT 分类加入 `UniversalAgent._INITIAL_CATEGORIES`, 两工具首次即注入 LLM 工具列表(不等 searchtool 动态发现) | 用户提问驱动 | 2026-11-18 |

---

## 16. 参考源码(关键行)

| 工具 | 文件 | 关键行 |
|---|---|---|
| opencode question 前端 | `packages/app/src/session/requests/session-question-dock-classic.tsx` | 全文(871行, classic 默认版) |
| opencode question 前端 | `packages/app/src/session/requests/session-question-dock-experimental.tsx` | 全文(1572行, 动画版) |
| opencode question 前端 | `packages/app/src/session/requests/session-elicitation-dock.tsx` | 全文(288行, 通用表单版) |
| opencode dock 挂载 | `packages/app/src/session/composer/session-composer-region.tsx` | L59-106(question/elicitation/permission 停靠) |
| opencode dock 容器 | `packages/session-ui/src/components/dock-prompt.tsx` | 全文(29行, 通用停靠容器) |
| opencode question 样式 | `packages/session-ui/src/components/question-prompt.css` | 全文(527行, 视觉参考) |
| opencode Form 服务 | `packages/core/src/form.ts` | create:124/ask:152/reply:180/cancel:199 |
| opencode FormInfo 类型 | `packages/client/src/promise/generated/types.ts` | FormStringField:625/FormMultiselect:643/FormInfo:2656 |
| opencode question | `packages/core/src/tool/plugin/question.ts` | Input:23-25, execute:62-111, toField:119-132, toModelContent:38-46 |
| opencode question schema | `packages/schema/src/question.ts` | Option:6-9, base:11-16, Prompt:18, Answer:21 |
| opencode todoWrite | `packages/core/src/tool/plugin/todo.ts` | Info:13-19, Input:21-23, summarize:30-41, execute:61-78 |
| Omni HITL 弹窗 | `frontend/src/components/AuthorizationModal/index.tsx` | 全文(656行, 二值确认) |
| Omni HITL 壳 | `frontend/src/components/AuthorizationModal/HITLModalShell.tsx` | 全文(55行, antd Modal) |
| Omni 底部停靠区 | `frontend/src/features/chat/components/layout/SessionLayout.tsx` | L219-232(taskinfo/config/input dock) |
| Omni SSE 帧定义 | `frontend/src/types/chat.ts` | StatusMessage:161-177(paused/resumed/notice) |
| Omni 授权 hook | `frontend/src/features/chat/hooks/useAuthorization.ts` | 全文(197行, SSE→Modal) |
| Omni 事件 Store | `frontend/src/features/chat/streams/chatStreamStore.ts` | pendingAuthorization:386/快照:640-680/acknowledge:1518 |
| Omni 传输层 | `frontend/src/features/chat/streams/chatStreamTransport.ts` | hitlHandlers:1048-1128 |
| Omni SSE 解析 | `frontend/src/features/chat/services/sseParser.ts` | case paused/resumed:1012-1073 |
| Omni 面板注册表 | `frontend/src/features/chat/components/layout/SessionPanelRegistry.ts` | SlotName:15-27(需加 'question') |
| Omni 面板注册 | `frontend/src/features/chat/hooks/useChatPanels.tsx` | taskinfo.bar:331/input.chat:357(注册模式) |
| Omni HITL 原语 | `backend/app/services/task/hitl_confirmation.py` | create:100/wait:129/resolve:174/清理:77 |
| Omni HITL 网关 | `backend/app/services/agent/handlers/hitl_gateway.py` | emit paused:127-134/emit resumed:146-149 |
| Omni 事件登记源 | `backend/app/services/agent/steps/__init__.py` | ALL_STEP_TYPES:66-85/NOTICE_KINDS:92-97 |
| Omni 仅SSE 集合 | `backend/app/monitoring/agent_telemetry.py` | SSE_ONLY_TYPES:100-108 |
| Omni SSE 转发表 | `backend/app/services/chat/stream_orchestrator.py` | _SSE_FORWARD_TYPES:1306 |
| Omni 工具注入点 | `backend/app/services/agent/tool_executor.py` | 注入:101-137 |
| Omni 工具上下文 | `backend/app/tools/context.py` | 三个 ContextVar 范式:35-116 |
| Omni 工具注册 | `backend/app/tools/registry.py` | register:133-184 |
| Omni 工具分类 | `backend/app/tools/tool_types.py` | ToolCategory:29-49 |
| Omni 分类模块表 | `backend/app/tools/tool_constants.py` | CATEGORY_MODULES:411-421 |
| Omni 保险丝 | `backend/app/tools/tool_retry_engine.py` | _compute_fuse:382-403/_validate_params:566+ |
| Omni 返回构造 | `backend/app/tools/tool_response.py` | build_success:38/build_error:55/is_success:168 |
| Omni 工具注册模板 | `backend/app/tools/timer/timer_register.py` | 全文(144行) |
| Omni 工具实现模板 | `backend/app/tools/timer/timer_set.py` | 签名:97/llm_data:70-95 |
| Omni 禁用名单 | `backend/app/tools/tools_alias_mapper.py` | UNAVAILABLE_OFFICIAL_TOOLS:414/get_disabled:417 |
| Omni 禁用配置 | `config/config.yaml` | tuning.agent.disabled_tools:754 |
| Omni HITL 配置 | `config/config.yaml` | security.hitl:707-711 |
