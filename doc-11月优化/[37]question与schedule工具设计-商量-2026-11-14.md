# question 与 schedule 工具设计文档

> 文档号: [37] | 作者: 商量 | 日期: 2026-11-14
> 目录: F:\OmniAgentAs-01\doc-11月优化\[37]question与schedule工具设计-商量-2026-11-14.md
> 前置研究: 20261113-102752-37dc\question_todowrite_research.md(18KB, opencode2.2.5源码 + Claude Code/Spring AI 对比)
> 前端深研: 2026-11-14 追加 opencode question 前端(§5.4.0) —— **DockPrompt 底部停靠面板范式, 非 Modal 弹窗; Omni HITL 不能复用**

---

## 0. 设计结论(先读)

| 工具 | 名称 | 本质 | 设计依据 | 人工干预 | 超时 |
|---|---|---|---|---|---|
| **question** | question | 阻塞式人机问答 | opencode 主体设计 | **继承 `security.hitl.enabled`(同一开关)** | 复用 `security.hitl.timeout`(默认120s) |
| **schedule** | schedule | 会话内任务/计划清单 | opencode todoWrite 功能类似, 名词改 schedule | 无需(纯回显) | 无 |

**关键决策**:
1. **question 从禁用名单移除** (从 `UNAVAILABLE_OFFICIAL_TOOLS` 摘除) —— 用户已拍板
2. **question 超时复用 `security.hitl.timeout`(默认120s)** —— 用户已拍板, 与 HITL 确认超时同源
3. **question 人工干预开关继承 HITL 同一开关** (`security.hitl.enabled`) —— 用户已拍板, 不单独设 question 开关
4. **schedule 一期方案** —— 见 §4 两方案差异说明, 建议方案A(纯回显, 一致 opencode), 方案B(单任务聚焦+nag) 二期

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
- 后端返回 `{items, summary, metadata}`(原样回显 + 摘要)
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

## 5. question 设计(Omni 落地)

### 5.1 总体原则(用户拍板)
1. **按 opencode 主体设计** —— 多问题/多选/自定义输入/阻塞式
2. **从禁用名单移除** —— `UNAVAILABLE_OFFICIAL_TOOLS` 摘除 `question`
3. **超时复用 `security.hitl.timeout`(默认120s)** —— 与 HITL 确认超时同源
4. **人工干预开关继承 HITL** —— 复用 `security.hitl.enabled`(不单独设 question 开关)

### 5.2 后端(新文件 `backend/app/tools/agent/question.py`)

> Schema 模型集中定义于 `agent_schema.py`(见 §7.1), 此处仅展示结构。

**Schema** (Pydantic):
```python
class QuestionOption(BaseModel):
    label: str          # 显示文本(1-5词, 简洁)
    description: str = ""  # 选项解释

class QuestionItem(BaseModel):
    question: str       # 完整问题
    header: str         # 极短标签(max 30 chars)
    options: list[QuestionOption]  # 可用选项
    multiple: bool = False  # 是否允许多选

class QuestionInput(BaseModel):
    questions: list[QuestionItem]  # 非空数组
```

**执行逻辑**:
```python
def question(input: dict, context) -> dict:
    # 1. 校验 questions 非空
    # 2. 人工干预开关: 读 security.hitl.enabled
    #    - 关闭 → 不阻塞, 返回空答案 + 提示(模型继续, 降级)
    #    - 开启 → 进入阻塞问答
    # 3. 生成 question_id(独立于 confirm_id, 不污染信任落库链路)
    # 4. 复用 HITL 阻塞机制: create_question → SSE 事件 question_required → wait_for_question_result
    # 5. 结果分流:
    #      cancelled+message → ToolFailure(message)   [模型继续]
    #      cancelled         → CancelledError         [步骤结束]
    #      timeout(120s)     → ToolFailure("question 超时")  [模型继续, 防挂起]
    #      正常              → 组装 output.answers
    # 6. return {output:{answers}, content: toModelContent(...), metadata:{answers}}
```

### 5.3 HITL 扩展(`services/task/hitl_confirmation.py`)
新增(或泛化)三个函数, **与二值确认并存不混用**:
- `create_question(task_id, questions) -> question_id`  —— 创建待答请求(独立命名空间)
- `wait_for_question_result(question_id, timeout) -> {answers, cancelled, expired}`  —— 阻塞等待
- `resolve_question(question_id, answers) -> None`  —— 用户回答落库

**关键**: 新增独立事件类型 `question_required`(与 `paused` 并存), 新增 `_PendingQuestion` 存储(与 `_PendingConfirmation` 分离), **避免污染信任落库链路**(HITL confirm 有 trust_session 语义, question 无)。

### 5.4 前端(基于 opencode DockPrompt 范式, **非 Modal 弹窗**)

> **核心结论(用户驱动)**: question 页面**不能复用 HITL 弹框**。opencode 的 question 是**卡片式底部停靠面板**(DockPrompt, 内嵌 composer 上方), 而 Omni HITL 是 **antd Modal 居中弹窗**(520px 遮罩居中)。两者形态/交互/数据流完全不同。详见 §5.4.0 对比。

#### 5.4.0 opencode question 前端研究(设计依据)

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

#### 5.4.1 Omni HITL 现状与差距(为什么不能复用)

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

#### 5.4.2 Omni question 前端设计(新文件, 基于 opencode 范式)

**目录**: `frontend/src/features/chat/components/question/`(与 taskinfo/config/input 同层, 会话内面板)
- `QuestionDock.tsx` —— 卡片式底部停靠面板(header/content/footer 三区)
- `QuestionOption.tsx` —— 单选项(radio/checkbox + 数字快捷键)
- `QuestionCustomInput.tsx` —— 自定义输入框
- `useQuestionDock.ts` —— 状态管理(tab/answers/custom/customOn)
- `QuestionDock.css` —— 视觉(参照 opencode question-prompt.css)

> **归属依据**: chat 会话内面板(taskinfo/config/input)统一放 `features/chat/components/` 下, 由 `useChatPanels.tsx` 按 slot 注册; `components/` 一级目录仅放页面级全局组件(如 AuthorizationModal, ChatPage 引用)。QuestionDock 是会话内停靠面板, 应归 `features/chat/components/question/`。

**挂载点**(而非 Modal):
- 复用 `SessionLayout` 底部停靠区(`features/chat/components/layout/SessionLayout.tsx:219-232`, taskinfo/config/input 三槽)
- question dock 停靠 **input 槽上方**(与 opencode composer 上方一致)
- 通过 `SessionPanelRegistry` 注册新槽 `question`(参照 taskinfo/config/input 注册模式)
- **需扩展 `SessionPanelRegistry.ts:15-27` `SlotName` 联合类型**, 加 `'question'`(当前仅 topbar/left/right/rightBottom/taskinfo/config/input)
- 面板注册在 `useChatPanels.tsx`(参照 taskinfo.bar:331 / input.chat:357 注册模式)

**数据流**(扩展 SSE 帧):
- 后端 SSE 新增 `question_required` 帧(与 `paused` 并存, 独立命名空间)
- 前端 `chatStreamTransport.ts` 新增 `onQuestionRequired` → `chatStreamStore` 写入 `pendingQuestion`
- `useQuestionDock` 订阅 `pendingQuestion` → 渲染 QuestionDock
- 提交 → `taskControlApi.answerQuestion(questionId, answers)` → 后端 `resolve_question`
- 关闭 → `chatStreamStore.acknowledgeQuestion(sessionId)`(防切回重弹)

**交互**(照搬 opencode):
- 多问题分页(tab + 进度条分段)
- 单选/多选(radio/checkbox)
- 自定义输入(custom:true)
- 数字快捷键 1-9 + 键盘导航(Arrow/Home/End/Enter)
- Escape=dismiss(cancel)、Ctrl+Enter=next/submit、Alt+Left=back
- 最小化/恢复(折叠)
- 状态缓存(questionCache, 防会话切换丢失)

### 5.5 超时与降级
- 超时: `security.hitl.timeout`(默认120s), 超时转 ToolFailure 让模型继续(防挂起)
- 人工干预关闭(`security.hitl.enabled=false`): 不阻塞, 返回空答案+提示(模型继续)

---

## 6. schedule 设计(Omni 落地, 按方案A)

### 6.1 后端(新文件 `backend/app/tools/agent/schedule.py`)

> Schema 模型集中定义于 `agent_schema.py`(见 §7.1), 此处仅展示结构。

**Schema** (Pydantic):
```python
class ScheduleItem(BaseModel):
    content: str   # 任务简述
    status: Literal["pending", "in_progress", "completed", "cancelled"]

class ScheduleInput(BaseModel):
    items: list[ScheduleItem]  # 完整清单(整体替换)
```

**执行逻辑**(纯回显):
```python
def schedule(input: dict, context) -> dict:
    items = input["items"]
    summary = summarize(items)   # 照搬 opencode summarize
    return build_success({
        "output": {"items": items},
        "content": summary,          # 摘要给 LLM
        "metadata": {"items": items} # 清单给前端
    })
```

**summarize**(照搬 opencode):
```python
def summarize(items):
    if not items: return "计划已清空"
    total = len(items)
    completed = sum(1 for i in items if i.status == "completed")
    parts = [f"{completed}/{total} 已完成"]
    for s in ("in_progress", "pending", "cancelled"):
        n = sum(1 for i in items if i.status == s)
        if n: parts.append(f"{n} {s.replace('_',' ')}")
    active = [i.content for i in items if i.status == "in_progress"]
    return f"计划已更新: {', '.join(parts)}" + (f"。进行中: {', '.join(active)}" if active else "")
```

### 6.2 前端(扩展 `frontend/src/features/chat/components/layout/TaskListPanel.tsx`)
- 消费 SSE 事件(新类型 `schedule_updated`)或 tool 的 metadata.items
- 渲染清单: 每项 status 徽标(pending/in_progress/completed/cancelled) + content
- 状态推进: 模型调用 schedule 更新 → 前端刷新

### 6.3 权限
- 无需 HITL 确认(save=["*"] 语义, 白名单直通)
- 无需人工干预开关(schedule 是纯信息展示, 无风险)

---

## 7. 注册接入点(两工具共通)

### 7.1 新建类别目录
```
backend/app/tools/agent/
├── __init__.py          # 导出 _register_agent_tools(参照 timer/__init__.py 范式: 显式 import + __all__)
├── agent_register.py    # _register_agent_tools() 注册两工具
├── agent_schema.py      # QuestionInput / ScheduleInput 等 Pydantic 模型
├── question.py          # question 工具实现
└── schedule.py          # schedule 工具实现
```

> **__init__.py 规范**: 现有目录 __init__.py 只导出 `_register_*` 函数(注册入口), 工具实现函数经 register 内部引用, 不直接暴露; 与 timer 范式一致即可。

### 7.2 接入点(4处)
1. `tool_constants.py` → `CATEGORY_MODULES` 加 `"agent": ("app.tools.agent", "_register_agent_tools")`
2. `tool_types.py` → `ToolCategory` 加 `AGENT = ("agent", 10, "智能体交互工具")`(序号10, 追加在 WIN_REGISTRY=9 之后; 序号2是 SHELL 分类删除后留的空位, 不动避免 searchtool 排序变化)
3. `tools_alias_mapper.py` → `PARAM_ALIASES` 加 `question`/`schedule` 条目(键名归一化)
4. `tools_alias_mapper.py` → `UNAVAILABLE_OFFICIAL_TOOLS` **移除 `question`**(用户拍板)

> **⚠ 禁用名单已配置化(2026-11-10 小欧)**: 真值源是 `config.yaml tuning.agent.disabled_tools`(L833, 当前 `question, skill, subagent, patch, execute`), `UNAVAILABLE_OFFICIAL_TOOLS` 只是**内置回落默认**(仅配置缺键/不可读/形状异常时用)。`get_disabled_official_tools()` 读配置即热生效。
> **正确修改点 = `config.yaml tuning.agent.disabled_tools` 移除 `question`**(改为 `skill, subagent, patch, execute`), 而非改内置元组(改了不生效, 因配置键存在即覆盖)。同时把内置 `UNAVAILABLE_OFFICIAL_TOOLS` 也移除 `question` 保持回落默认一致(可选, 避免旧配置异常时 question 又被禁)。

### 7.3 agent_register.py 模板(参照 timer_register.py)
```python
AGENT_TOOL_DESCRIPTIONS = {
    "question": """执行中向用户提问, 收集偏好/澄清歧义/获取实现决策。questions为问题数组, 每问题含question/header/options/multiple。适用场景: 需要用户决策、澄清歧义时使用。""",
    "schedule": """创建/更新当前会话的任务计划清单(用户可见的执行计划)。items为完整清单(整体替换), 每项含content/status。适用场景: 长任务(≥3步)执行时展示工作计划。""",
}
AGENT_INPUT_MODELS = {"question": QuestionInput, "schedule": ScheduleInput}
AGENT_TOOL_EXAMPLES = {
    "question": [{"questions": [{"question":"选择认证方式?", "header":"认证", "options":[{"label":"OAuth"},{"label":"JWT"}]}]}],
    "schedule": [{"items":[{"content":"分析需求","status":"completed"},{"content":"编写代码","status":"in_progress"},{"content":"测试","status":"pending"}]}],
}
```

---

## 8. 阶段划分

| 阶段 | 内容 | 验证 |
|---|---|---|
| **P1 后端 question** | question 工具 + HITL 扩展(create_question/wait/resolve) | pytest 单测(非阻塞路径) |
| **P2 前端 question** | QuestionDock + SSE 事件 + Store | 前端单测 + e2e |
| **P3 后端 schedule** | schedule 纯回显 + summarize | pytest(照搬 opencode 测试) |
| **P4 前端 schedule** | TaskListPanel 展示位 | 前端单测 |
| **P5 注册收口** | 类别/别名/禁用名单移除 | 全量回归 |
| **P6(二期) 方案B** | 单任务聚焦 + nag 提醒(可选) | 按需 |

---

## 9. 配置变更(需写入 config.yaml)

```yaml
security:
  hitl:
    enabled: true        # 已存在, question 复用此开关(继承)
    timeout: 120         # 已存在, question 超时复用(默认120s)
tuning:
  agent:
    disabled_tools: skill, subagent, patch, execute   # 修改: 移除 question(原包含 question), 用户拍板
# 无新增配置键 —— question 继承 HITL 开关与超时, schedule 无需配置; 仅修改现有 disabled_tools
```

> **⚠ 禁用名单配置化说明**: `disabled_tools` 是唯一真值源(2026-11-10 小欧), 移除 question 需在此修改; 内置 `UNAVAILABLE_OFFICIAL_TOOLS` 仅作回落默认, 同步移除 question 保持一致(见 §7.2 注)。

---

## 10. 决策记录

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
| 9 | 三堂会审: 前端 QuestionDock 归 `features/chat/components/question/`(非 components/), 与 taskinfo/config/input 同层 | 商量(三堂会审) | 2026-11-14 |
| 10 | 三堂会审: 禁用名单移除 question 改 `config.yaml tuning.agent.disabled_tools`(已配置化, 改内置元组不生效) | 商量(三堂会审) | 2026-11-14 |

---

## 11. 参考源码(关键行)

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
| Omni HITL 弹窗 | `frontend/src/components/AuthorizationModal/index.tsx` | 全文(656行, 二值确认) |
| Omni HITL 壳 | `frontend/src/components/AuthorizationModal/HITLModalShell.tsx` | 全文(55行, antd Modal) |
| Omni 底部停靠区 | `frontend/src/features/chat/components/layout/SessionLayout.tsx` | L219-232(taskinfo/config/input dock) |
| Omni SSE 帧 | `frontend/src/types/chat.ts` | StatusMessage:166-175(paused/resumed) |
| Omni 授权 hook | `frontend/src/features/chat/hooks/useAuthorization.ts` | 全文(197行, SSE→Modal) |
| Omni 事件 Store | `frontend/src/features/chat/streams/chatStreamStore.ts` | pendingAuthorization:384/acknowledge:1512 |
| Omni 传输层 | `frontend/src/features/chat/streams/chatStreamTransport.ts` | onQuestionRequired(新增, §5.4.2) |
| Omni 面板注册表 | `frontend/src/features/chat/components/layout/SessionPanelRegistry.ts` | SlotName:15-27(需加 'question') |
| Omni 面板注册 | `frontend/src/features/chat/hooks/useChatPanels.tsx` | taskinfo.bar:331/input.chat:357(注册模式) |
| Omni 禁用配置 | `config/config.yaml` | tuning.agent.disabled_tools:833(真值源) |
| opencode question | `packages/core/src/tool/plugin/question.ts` | Input:23-25, execute:62-111, toField:119-132, toModelContent:38-46 |
| opencode question schema | `packages/schema/src/question.ts` | Option:6-9, base:11-16, Prompt:18, Answer:21 |
| opencode todoWrite | `packages/core/src/tool/plugin/todo.ts` | Info:13-19, Input:21-23, summarize:30-41, execute:61-78 |
| Omni HITL | `backend/app/services/task/hitl_confirmation.py` | create:100, wait:129 |
| Omni 禁用名单 | `backend/app/tools/tools_alias_mapper.py` | UNAVAILABLE_OFFICIAL_TOOLS |
| Omni 注册 | `backend/app/tools/tool_constants.py` | CATEGORY_MODULES:404 |
| Omni 类别 | `backend/app/tools/tool_types.py` | ToolCategory |
| Omni 注册模板 | `backend/app/tools/timer/timer_register.py` | 全文(144行) |
| Omni 配置 | `config/config.yaml` | security.hitl:756-759 |
