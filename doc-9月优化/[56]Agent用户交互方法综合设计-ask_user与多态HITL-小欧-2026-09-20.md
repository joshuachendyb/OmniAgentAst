# [56] Agent用户交互方法综合设计——ask_user与多态HITL

**创建时间**: 2026-09-20 19:47:16
**更新时间**: 2026-09-20 20:33:26
**编写人**: 小欧

## 版本历史

| 版本 | 时间 | 修改简介 | 作者 |
|------|------|---------|------|
| v1.0 | 2026-09-20 19:47:16 | 建立文档。依据北京老陈决策：将 Agent 与用户交互的六项方法（A~F）深入研究后合并为一份总设计文档，深度研究级别，对照业界方案+本库代码给出可实施设计（消息契约+状态机+改动点）。 | 小欧 |
| v1.1 | 2026-09-20 20:33:26 | 全文档重排章节号：新增「二、交互模式全览与辨析」置于第一章之后（讲清六模式的定义/使用场景/辨析与复用关系，含 A 与 F 方向辨析、B 与现状权限确认的区别），原二~十三章整体后移一位（业界对照→三、方法A~F→四~九、统一契约→十、优先级→十一、风险→十二、附录→十三、结论→十四）；修正「保持打坎」错字为「保持打开」。 | 小欧 |
| v1.2 | 2026-09-20 20:57:24 | 按北京老陈指令重构「风险清单」章节：本次设计能解决的风险（超时/重校验/回喂语义/并发/豁免范围/事件登记/组件复用）其缓解措施已内嵌至四~十章实施注意，不再单列；剩余无法根治项收录为「十二、不能处理的问题」并逐条说明原因。 | 小欧 |

---

## 一、设计目标与总体原则

### 1.1 设计目标

本库 Agent（UniversalAgent + ReAct 循环）当前与用户的全部交互通道是 **HITL 权限拦截弹窗**（safety_gate → hitl_gateway → hitl_confirmation 三原语），形态单一（仅"允许/拒绝+信任"）。本文档将六种业界成熟的用户交互方法深度研究后统一设计：

| 编号 | 方法 | 英文 | 核心价值 |
|------|------|------|---------|
| A | 结构化询问 | ask_user / Question | 让 Agent 主动向用户提问，获取决策参数后继续执行 |
| B | 权限拦截（编辑/拒绝） | interrupt with edit/reject | 用户可编辑工具参数、拒绝并回喂理由 |
| C | 计划审批 | plan approval | 大动作前先展示计划，批准后执行 |
| D | 表单化采集 | elicitation | 按 JSON Schema 表单采集，结构化落参 |
| E | 策略化询问 | policy-driven ask | 按策略/信任自动决，少打扰 |
| F | 实时反馈与隔离上下文 | feedback & contest isolation | 运行中消息注入、上下文隔离 |

**核心设计基调**：复用现有 HITL 通道（confirm_id 生命周期/状态机/信任落库/拒绝回喂），扩展单调增长而不推倒重来：

1. `paused.kind` 扩展：`confirm`（现有权限拦截）与 `question`（结构化询问）；
2. action 多态化：`accept` / `edit` / `reject` / `respond`（对齐 LangChain HumanInTheLoopMiddleware 的 DecisionType）；
3. 拒绝理由回喂模型（对齐 Claude Code / OpenAI SDK），无需独立回环；
4. 信任落库（`trust.py`）即为 Claude Code "Always allow" 的等效物；
5. 前端按 `paused.kind` 渲染不同交互组件，最小改动。

### 1.2 总体原则（KISS-DIRECT）

- **直线增广**：所有新方法都走同一事件总线 `StreamBuffer.publish`（task_state.py 唯一写入口），不在 loop 中加旁路。
- **不新增回环**：拒绝理由/询问答复一律经 `resolve_confirmation` 多态 action 回流，由 hitl_gateway 统一回喂 LLM。
- **事件类型唯一登记**：新增事件类型必须先登记 `steps/__init__.py`，再被前端消费。
- **question 不经过安全分级**：ask_user 是"人机协作询问"，与工具执行权限拦截（path_auth/shellparam/...）完全解耦，两套 severity 体系。
- **后端为主、前端迎合**：消息契约以后端为准，前端只按契约渲染。

### 1.3 参考代码事实（本库现状）

| 项目 | 位置 | 现状 |
|------|------|------|
| 事件总线唯一写入口 | `services/task/task_state.py` StreamBuffer.publish | 分派/收口都在此 |
| ReAct 主循环 | `services/agent/react_loop.py` | 薄调度 |
| 单步分发 | `services/agent/react_dispatch.py` | 状态推断 + handler 分派 |
| 步骤处理器 | `services/agent/react_step.py`（605 行） | `_dispatch_handler` 返 List，逐条 publish |
| HITL 网关 | `handlers/hitl_gateway.py` | ConfirmSpec + hitl_confirm（paused→wait→resumed→resolve） |
| 安全门禁 | `handlers/safety_gate.py` | check_safety_and_confirm 三合一 |
| HITL 三原语 | `services/task/hitl_confirmation.py` | create/wait/resolve（resolve 为 async） |
| 事件类型登记 | `services/agent/steps/__init__.py` | 唯一登记处 |
| confirm 端点 | `api/v1/chat/chat_routes.py` `/chat/stream/confirm` | resolve_confirmation，code=confirm_stale 契约 |
| 信任落库 | `app/tools/trust.py` | 会话信任（Always allow 等效） |
| 工具元字段 | `app/tools/tool_types.py` | needs_confirmation / action_confirmation |
| 消息注入 | 2026-09-20 新增 B 机制 | inject_message_to_task 注入运行中任务 inbox |
| 前端弹窗 | `components/AuthorizationModal/index.tsx` + `hooks/useAuthorization.ts` + sseParser | paused/resumed 按 confirmId 并发区分 |

---

## 二、交互模式全览与辨析

本章在进入业界对照和逐方法设计之前，先把六种交互模式的整体概念、使用场景、相互区别讲清楚，避免混淆。

### 2.1 六种交互模式总览

| 模式 | 一句话定义 | 典型使用场景 |
|------|-----------|-------------|
| A 结构化询问 | Agent 主动向用户 **要决策参数**，用户回答后同一任务内继续执行 | 问存到哪个目录、批量处理范围、冲突时选方案、参数缺失时补关键词 |
| B 权限拦截（编辑/拒绝） | 工具执行前弹窗，用户除允许/拒绝外，可 **编辑参数放行** 或 **拒绝并附理由** | 路径写错想直接改对、命令参数不合预期、拒绝时想让 LLM 知道原因 |
| C 计划审批 | 高风险/多步骤动作序列执行前，展示「计划清单」，批准后一次性执行 | 批量删文件、整目录重命名、多命令流水线 |
| D 表单化采集 | 按 JSON Schema 以 **表单形式一次采集多个参数**，提交后批量回填 | 生成文档同时要文件名+目录+格式、批量创建需多个属性 |
| E 策略化询问 | 「要不要问」由策略决定：低风险自动放行、中风险按信任、高风险必问、黑名单直接拒绝 | 高频工具不每次弹窗、只读操作免打扰 |
| F 实时反馈与隔离上下文 | 任务运行中 **用户注入消息被当下采纳** + 多 session 上下文严格隔离 | 运行中「改成 E:\」「停下来」；多任务并发互不污染 |

### 2.2 使用场景归类（按用户视角）

| 用户什么时候会用到 | 对应模式 |
|-------------------|---------|
| Agent 问我「选哪个/写哪」 | A |
| 我想改掉 Agent 的某个操作再放行 | B（edit） |
| 我不想让 Agent 做某操作，并想让它明白原因 | B（reject+理由） |
| 我要先看清楚它要怎么做一批操作再放行 | C |
| 我要一次性填好几个参数 | D |
| 我不想被频繁询问 | E |
| 我在任务进行中想插话改方向 | F |

### 2.3 A 与 F 的区别（方向相反，勿混淆）

A 和 F 表面都是「用户提供了输入」，但本质不同：

| 维度 | A 结构化询问 | F 实时反馈 |
|------|-------------|-----------|
| 发起方 | **Agent→用户**：Agent 主动索要信息 | **用户→Agent**：用户中途主动插话 |
| 时序 | 同步阻塞：等回答后任务才继续 | 异步：下一轮 ReAct 采纳 |
| 语义 | 要「决策参数」（选哪个/写哪） | 给「方向指令」（改成/停下来） |
| 信息流向 | Agent 拉取 | 用户推送 |

**结论**：F 的 `inject_message_to_task` 机制已存在（2026-09-20 B 机制），本文档只做收口升级，不算新交互通道；A、F 方向相反、时序不同，必须分成两个独立模式。

### 2.4 B 与现有权限确认的关系

现有 HITL 弹窗只有「允许/拒绝」两个动作。B 增强后新增两个能力，都复用 `resolve_confirmation` 多态：

| 能力 | 与现状差异 | 必要性 |
|------|-----------|--------|
| **edit** | 现状拒绝后 LLM 要「猜参数→再弹→可能再被拒」，高频 1~2 次往返；edit 由用户直接改参数一次放行 | **高**：减少弹窗+减少 LLM 往返，实现集中在 `_PendingConfirmation.args` 覆盖 + safety 重校验 |
| **reject+理由** | 现状拒绝不留原因，LLM 只能猜；理由以用户口吻回喂后下轮直接改对 | **中**：可选优化，消除猜测，与现状拒绝计数语义兼容 |

### 2.5 模式间派生与复用关系

- **D 是 A 的 schema 超集**：同一 `question` 通道，`form_schema` 可空则退化为纯问题（MCP elicit 同款）；
- **C 复用 A 的 paused 通道**：`type=plan` 只是 paused 的一种 kind；
- **E 是策略仲裁层**：决定「要不要问、走哪条通道」，落在 `safety_gate.decide_intercept`，服务 A/B/C/D；
- **F 独立**：走 inbox 通道，不占用 paused 通道，与 [55] 多 Session 并发正交。

> 六模式全部复用 confirm_id 生命周期 + 三原语 + 信任落库，只扩展 `type` 与 `action` 两个字段，零推倒重来。

---

## 三、六方法业界方案深度对照

### 3.1 总对照表

| 方法 | Claude Code | LangGraph | LangChain（HITL Middleware） | MCP-Agent | OpenAI Agents SDK | 本库必选 |
|------|------------|-----------|------------------------------|-----------|-------------------|---------|
| A 结构化询问 | AskUserQuestion（多选，问题保持打开直到回答） | interrupt/Command(resume) | respond 决策 | elicit + schema | 需 needs_approval | **采用** |
| B 编辑/拒绝 | Edit 工具 + 拒绝回喂 | Command(update/ resume) | EditDecision.edited_action / RejectDecision.message | — | 审批中断 + 拒绝 | **采用** |
| C 计划审批 | Plan Mode（Shift+Tab×2，探索→批准→执行） | interrupt 在计划后 | ReviewConfig 策略 | — | — | **采用** |
| D 表单采集 | — | — | — | ctx.elicit(message, schema) → Accepted/Declined/Cancelled | — | **采用** |
| E 策略询问 | Always allow（信任） | — | ReviewConfig policy（approve/edit/reject/respond 按需） | — | 按调用决策 async 函数 | **采用** |
| F 隔离上下文 | 多 worktree 隔离 | 分支/子图 | 消息历史隔离 | — | RunState 序列化/恢复 | **采用** |

### 3.2 关键业界机制启示

**[LangGraph interrupt/Command(resume)]**
- `resume` 必须在同一 thread_id 上；`Command(resume=任意JSON值)` 的返回值成为 `interrupt()` 的返回值；恢复后节点从头部重跑；默认无限等待。
- **启示**：本库 confirm_id 生命周期与线程等价——resume 即 `resolve_confirmation`；恢复后从 `wait` 处继续而非重跑整环（本库更优，已验证超时不重放）。

**[LangChain HumanInTheLoopMiddleware]**
- `DecisionType = Literal["approve", "edit", "reject", "respond"]`；
- `EditDecision(edited_action)` 可改工具名+args → 改后整体重跑；
- `RejectDecision(message)` 以**用户拒绝口吻**回喂模型（不是系统错误）；
- `ReviewConfig` 即策略层。
- **启示**：本库 action 闭包 `{accept, edit, reject, respond}` 完全对齐此模型，天然可平滑演进。

**[MCP elicitation]**
- `ctx.elicit(message=..., schema=ConfirmBooking)` 暂停执行，返回 `AcceptedElicitation(data)` / `DeclinedElicitation()` / `CancelledElicitation()`；
- 需 app 侧配 `elicitation_callback`（如 console_elicitation_callback）。
- **启示**：D（表单采集）就是 A（结构化询问）的 schema 超集——同一通道，schema 可空则退化为纯问题。

**[OpenAI Agents SDK HITL]**
- 工具级 `needs_approval=True` 或**按调用决策的 async 函数**（对应本库 tool_types 元字段）；
- pending 审批以 interruption 显式浮在 run results；RunState 可序列化/恢复；
- **审批面是 run 级**：handoff / 嵌套 Agent.as_tool() 的审批都浮到外层 run。
- **启示**：本库多 session 并发（[55]多Session并发架构设计）天然满足"审批面 run 级"，confirm_id 全局唯一即可。

**[Claude Code AskUserQuestion / Plan Mode]**
- AskUserQuestion：多选提问，问题保持打坎直到用户回答（选选项或自由输入）；
- Plan Mode：Shift+Tab 两次进入（只探索不改码）→ 迭代计划直到同意 → 再切自动接受模式按步骤执行。
- **启示**：A 的交互形态（多选+保持打开）与 C 的"先展示计划、批准再执行"两阶段是本库 P0 核心。

---

## 四、方法A：结构化询问 ask_user

### 4.1 目标与场景

Agent 在执行**多分支任务**、**需要用户提供决策参数**、**语义歧义**、**多方案选择**时，主动弹出询问，用户回答后继续。

典型场景：
- 下载/生成文件时询问文件名、目标目录；
- 批量操作前询问范围（全部/指定子集）；
- 冲突时让用户选择方案（覆盖/保留/改名）；
- 参数缺失（如未给出要搜索的关键词）时请求用户补充。

### 4.2 与本库现状的差距

现状只有权限拦截（`confirm`），无"Agent 主动提问"通道；Agent 只能靠 `final` 结束任务"问"下一轮，无法在同一任务内获得参数继续执行。

### 4.3 后端实施方法

**核心载体**：复用 `hitl_gateway.hitl_confirm`，新增 `question` 形态（非阻塞式权限拦截）：

```python
# handlers/hitl_gateway.py 增补（示意，非最终代码）
class ConfirmSpec:
    kind: str                     # "confirm" | "question" | "plan" | "form"
    action: str                   # "accept" | "edit" | "reject" | "respond"
    ...
```

`question` 专用建立入口（建议在 `handlers/` 新增 `question_handler.py`，供 action 分支调用）：

```python
async def hitl_ask(
    agent,
    *,
    question: str,                # 问题正文（必填）
    options: list[str] | None,    # 候选选项（选填），None=自由输入
    field: str | None,            # 期望注入的字段名（选填），便于回填参数
    timeout: int | None = None,   # 默认独立窗口，不抢占 confirm 的 120s 语义
    reason: str | None = None,    # 为什么问（展示给用户）
) -> Step | None:
```

**执行流程**（复用三原语）：
1. `create_confirmation(confirm_id, kind="question", ...)`；
2. `publish(paused)`：`kind=question`、`action=respond`、`options=[...]`；
3. `await wait_confirmation(confirm_id)` 挂起（等价 LangGraph interrupt）；
4. 用户经 confirm 端点回 `respond + data`；
5. `resolve_confirmation` 置完成 → `publish(resumed, action=respond, data=...)`；
6. Agent 读取答复，继续 ReAct（答复由 hitl_gateway 包装进 observation 回喂 LLM）。

### 4.4 消息模式（Step/SSE/API）

**paused 帧新增字段（SSE `paused`）**：

```jsonc
{
  "event": "paused",
  "type": "question",                  // ✅ 新
  "confirm_id": "c_8f3a...",
  "question": "要下载的文件保存到哪个目录？",
  "options": ["D:\\downloads", "E:\\docs", "自由输入"],
  "field": "save_dir",                 // ✅ 新：答复回填字段
  "reason": "未指定目标路径，需用户决策",
  "auto_confirm": false,
  "confirm_timeout": 300
}
```

**confirm 端点请求体扩展**：

```jsonc
POST /api/v1/chat/stream/confirm
{
  "confirm_id": "c_8f3a...",
  "confirmed": true,
  "action": "respond",                  // ✅ 新："accept"|"edit"|"reject"|"respond"
  "data": "D:\\downloads",              // ✅ 新：respond/edit 的载荷
  "trust_session": false
}
```

**resumed 帧回显答复**：`resumed` 帧带 `action=respond`、`data=<用户答复>`，前端据此关闭询问组件并展示用户回答。

### 4.5 状态机

```
        create(kind=question)       用户点提交 action=respond,data=x -> resolve
init ────────────────► WAITING ─────────────────────────────► DONE
                        │ 超时(expired=True)                        │
                        └──────────────► TIMED_OUT ─────────────────┘
                                               （前端提示"已超时，任务继续"，Agent 收到 timeout 答复）
```

- 超时答复由 hitl_gateway 转成 LLM observation："用户在 300s 内未回答"，Agent 自行决策（跳过或默认值）。
- `question` 的信任落库选项默认隐藏（询问不产生信任；信任只属权限拦截）。

### 4.6 后端改动点

| 文件 | 改动 |
|------|------|
| `handlers/hitl_gateway.py` | ConfirmSpec 增 `kind/action/options/question/data`；新增 `hitl_ask()` |
| `handlers/` 新增 `question_handler.py` | 与 `hitl_gateway` 并行或托管在 gateway 内（推荐托管，复用三原语） |
| `services/task/hitl_confirmation.py` | `_PendingConfirmation` 增 `kind/action/data`；`resolve_confirmation` 接收多态 action |
| `services/agent/steps/__init__.py` | 若需独立事件类型可登记 `question`，否则复用 `paused`（推荐复用，前端按 kind 分发） |
| `chat_routes.py` `/confirm` | 解析 `action/data`，透传 `resolve_confirmation(confirm_id, action, data, trust)` |
| `tools/trust.py` | （不改）question 不写信任 |

### 4.7 前端最小改动点

| 文件 | 改动 |
|------|------|
| `features/chat/services/sseParser.ts` | paused 解析透传 `type/question/options/field/reason` |
| `hooks/useAuthorization.ts` | `handleAuthorizationRequired` 按 `kind` 分派：confirm→AuthorizationModal；question→新 `AskUserModal` |
| `types/chat.ts` | AuthorizationRequest 增 kind/question/options/field 字段 |
| `services/chat.ts` confirm | 请求体支持 `action/data` |
| `components/AskUserModal/`（新建） | 展示问题+选项列表/自由输入框，提交=confirm(action=respond, data)，取消=confirm(action=reject) |

**前端新增组件约 200 行**，完全复用 CountdownRing/倒计时/并发 confirmId 既有模式。

---

## 五、方法B：权限拦截 edit 与 reject

### 5.1 目标与场景

现有弹窗只有"允许/拒绝"。增强为：
- **edit**：用户不批准原始参数，可修改工具参数（改路径、改命令、改文件名）后放行；
- **reject**：拒绝，并可附理由，理由以"用户口吻"回喂 LLM，Agent 改弦更张。

### 5.2 业界对照

- LangChain `EditDecision(edited_action)`：改后**整体重跑**该工具调用；
- LangChain `RejectDecision(message)`：以用户拒绝口吻回喂，非系统错误；
- Claude Code：edit 交互后重新安全检查。

### 5.3 后端实施方法

**复用现有 confirm 端点**，`action` 字段承载三态：

```jsonc
POST /confirm
{
  "confirm_id": "c_...",
  "action": "edit" /* 或 "reject" */,
  "data": { "tool_name": "win_write_file", "arguments": {"path": "E:\\new.txt"} },  // edit 载荷
  "reject_reason": "路径不能写系统盘",   // reject 载荷
  "trust_session": false
}
```

**resolve_confirmation 多态处理**（`hitl_confirmation.py`）：

| action | 行为 |
|--------|------|
| accept | 原样放行（现状 confirmed=true） |
| edit | 覆盖 `PENDING.tool_call.args`，后续走 `safety_gate` 重校验（安全不退化），通过后执行修改后的调用 |
| reject | 以用户口吻生成 observation 回喂 LLM（非 error 通道，与现状拒绝计数语义一致：`rejected_count` 区分工具），Agent 可换参数/换工具/给出解释 |

**edit 后重跑安全检查**：对齐 Claude Code——改参数后不能跳过安全；在 `handle_action` 中 edit 分支重新 `check_safety_and_confirm`，若修改后仍危险则再次弹出（或按危险级直接 fail-safe 阻断）。

### 5.4 消息模式

- `paused` 帧不变（仍 `kind=confirm`），但 payload 增 `action_confirmation: ["accept","edit","reject"]` 供前端渲染「编辑/拒绝理由」控件（工具级配置，见方法E）。
- `resumed` 帧增 `action` 字段，前端据此显示"已修改参数执行"/"已拒绝（理由xxx）"。

### 5.5 状态机

```
WAITING ── action=accept ───────────────────────► RUN（原调用）
   │                                                   ▲
   ├── action=edit, data={args} ──► 安全检查 ──────────┤（重校验通过）
   │                                   └─ 仍危险 ─► 二次弹窗/阻断
   └── action=reject, reason ──► REJECTED ──► observation 回喂 LLM（Agent 换参数重来/给出解释）
```

### 5.6 后端改动点

| 文件 | 改动 |
|------|------|
| `hitl_confirmation.py` | `resolve_confirmation` 支持 edit（覆盖 args）/reject（采 reason） |
| `hitl_gateway.py` | resolve 后按 action 分发恢复路径；edit 走 safety 重校验 |
| `handle_action.py` | 拒绝后 observation 含 `agent_feedback`（用户理由），供 LLM 修正 |
| `chat_routes.py` | confirm 端点解析 `action/data/reject_reason` |
| `tool_types.py` | `action_confirmation` 元字段声明允许的 action 集合 |

### 5.7 前端改动点

- `AuthorizationModal/index.tsx`：增加"编辑参数"折叠区（仅 `action_confirmation` 含 edit 时显示）+ "拒绝理由"输入框（仅含 reject 时）；
- `useAuthorization.ts`：confirm 调用带 action/data/reject_reason；
- `sseParser.ts`：resumed 透传 action。

---

## 六、方法C：计划审批（plan approval）

### 6.1 目标与场景

对**多步骤/高风险**任务（如批量删文件、整个目录重命名、执行多命令流水线），在动作序列执行前弹出**计划卡**，用户批准后 Agent 一次性完成。

### 6.2 业界对照

- Claude Code Plan Mode：先探索→展示计划→批准→执行（Shift+Tab×2 切换 + 自动接受模式）；
- LangChain：ReviewConfig 策略可在计划节点触发 review。

### 6.3 后端实施方法

**轻量方案（推荐，KISS）**：不新增 Plan 步骤类型，在**首个 destructive 工具执行前**，Agent 根据自己的计划（可从 observation 连续性推导，或显式让 LLM 在开头输出 plan 段）汇总生成一次性 `kind=plan` 询问，展示"即将执行的操作清单"：

```jsonc
{
  "event": "paused",
  "type": "plan",
  "confirm_id": "c_...",
  "title": "批量删除确认",
  "plan_steps": [
    {"step": 1, "tool": "win_delete_file", "summary": "删除 D:\\tmp\\*.bak 共 23 个文件"},
    {"step": 2, "tool": "win_write_file",  "summary": "写入清理记录到 D:\\logs\\clean.log"}
  ],
  "options": ["批准执行", "取消"],
  "confirm_timeout": 600
}
```

**触发策略**（建议放 `safety_gate` 或 `react_dispatch` 计数层）：
- 同一任务内 action 工具数 ≥ N（如 3）；
- 或首个 `tool_delete / tool_execute`（多文件）；
- 或工具 `action_confirmation` 含 `approval_all` 元字段。

**批准后**：同任务剩余 action 不再逐条弹窗（免打扰），仅记录；这与 method E 的 `trust_session` 语义正交——计划审批是一次性批量豁免，信任是会话级豁免。

### 6.4 消息模式与状态机

- 复用 `paused` 帧，`type=plan` + `plan_steps` 列表；
- 状态机与 ask_user 相同（WAITING→DONE/TIMED_OUT）；
- `resumed` 帧 `action=accept` = 计划获批，Agent 继续；`action=reject` = 取消执行，Agent 输出"已取消" final。

### 6.5 改动点（后端/前端）

| 端 | 改动 |
|----|------|
| 后端 | `safety_gate`（或新 `plan_approval.py`）按触发策略创建 plan 确认；`hitl_gateway` 支持 `plan_steps` 字段 |
| 后端 | 批准后同任务批量豁免逐条弹窗（会话级变量 `_plan_approved`） |
| 前端 | `AuthorizationModal` 或新 `PlanApprovalCard`（只读列表 + 批准/取消两钮），纯展示组件 |

---

## 七、方法D：表单化采集（elicitation）

### 7.1 目标与场景

Agent 通过**结构化为表单**的一次交互采集多个参数（对齐 MCP `ctx.elicit(message, schema)`），提交后批量回填，减少弹窗次数。

### 7.2 业界对照

- MCP-Agent：`ctx.elicit()` 返回 `AcceptedElicitation(data)`（强类型）/`DeclinedElicitation()`/`CancelledElicitation()`，schema 用 JSON Schema 描述。

### 7.3 后端实施方法

**本质**：D 是 A 的 schema 超集——`kind=form`：

```jsonc
{
  "event": "paused",
  "type": "form",
  "confirm_id": "c_...",
  "form_schema": {
    "type": "object",
    "properties": {
      "name":  {"type": "string", "title": "文件名"},
      "dir":   {"type": "string", "title": "保存目录", "default": "D:\\downloads"},
      "format":{"type": "string", "enum": ["md","txt","json"], "title": "格式"}
    },
    "required": ["name"]
  },
  "submit_label": "生成文档",
  "confirm_timeout": 600
}
```

**解析回填**：`data` 为 JSON 对象，按 `field` 键映射注入工具参数或作为 observation 回喂 LLM。mcp-app 的 elicitation_callback 对应本库前端 `FormModal`（动态按 schema 渲染 AntD Form）。

### 7.4 改动点（后端/前端）

| 端 | 改动 |
|----|------|
| 后端 | `hitl_ask` 扩展 `form_schema` 参数；`resolve` 校验 data 符合 schema（Pydantic v2 动态 model） |
| 前端 | 新建 `FormModal`：按 schema 生成字段（Input/Select/TextArea），校验 required，提交=confirm(action=respond, data=表单值) |

---

## 八、方法E：策略化询问（policy-driven ask）

### 8.1 目标与场景

让"要不要问"由**策略决定**，而非一刀切：低风险自动放行、中风险按信任、高风险必问、黑名单直接拒绝。对齐 LangChain `ReviewConfig` 与 OpenAI 按调用决策 async 函数。

### 8.2 本库现状

已有两大基础：
- `trust.py` 会话信任落库（= Always allow）；
- `tool_types.py` 元字段 `needs_confirmation` / `action_confirmation`；
- `safety_gate` 按 `safety_level`（path_auth/shellparam/command_block/tool_delete/tool_execute/data_guard/unregistered/forbidden_zone）分级。

### 8.3 后端实施方法（策略仲裁层）

在 `safety_gate` 内新增**统一决策函数**（单一来源，杜绝散落判断）：

```python
def decide_intercept(level, trust, meta, history) -> str:
    # 返回: "approve" | "confirm" | "block" | "ask"
    # 黑名单(level=blocked/forbidden_zone) -> "block"
    # 会话信任覆盖该工具 -> "approve"
    # needs_confirmation=False -> "approve"
    # 高风险 -> "confirm"
    # 工具声明 action_confirmation -> "confirm"(带action集合)
    # 同一工具重复N次且已授权 -> 后续 "approve"（降噪）
```

**新增策略面**：
- 工具级：`needs_confirmation` 布尔 + `action_confirmation` 集合（已有）；
- Agent 级/会话级：`confirm_mode`（严格/宽松），来自设置（doc-9月优化 [54]设置新架构）；
- 频次降噪：同工具同 args 已确认两次以上 → 静默通过（可配置，默认关）。

### 8.4 消息契约

`paused` 帧 `auto_confirm=true`（现有）语义保留；策略命中 `approve` 时**不发 paused**，直接执行并在 `tool` 帧带 `action: "auto_approved"` 标记（供前端展示"已按策略放行"）。

### 8.5 改动点

| 文件 | 改动 |
|------|------|
| `safety_gate.py` | 抽出 `decide_intercept` 单一决策函数；接入频次降噪 |
| `tool_types.py` | 校验 `action_confirmation` 合法性（edit/reject/respond 枚举） |
| 前端 | `tool` 帧展示 `auto_approved` 徽标（可选），不弹窗 |

---

## 九、方法F：实时反馈与隔离上下文

### 9.1 目标与场景

- **实时反馈**：任务运行中用户可注入消息（"改成 E:\"、"停下来"），Agent 当下采纳（对齐 Anthropic background 更新指令）；
- **隔离上下文**：多 session 状态严格隔离，互不污染（对齐 Claude Code 多 worktree / [55]多Session并发架构设计）。

### 9.2 本库现状

- 已具备 `inject_message_to_task`（2026-09-20 B 机制，注入运行中任务 inbox）——F 的实时反馈基础已存在；
- [55]文档已设计多 Session 并发 + confirm_id 全局唯一——隔离上下文基础已存在。

### 9.3 后端实施方法（收口）

把 `inject_message_to_task` 升级为**一等公民反馈通道**：

1. inbox 头部读取（每轮 ReAct 或每个 action 前检查）；
2. 注入消息包装成 observation："用户中途指示：xxx"，优先级高于工具结果；
3. 任务状态机支持 `paused→feedback→resumed` 路径（用户中途指示已选工具的替代方案）；
4. 上下文隔离审计：确认 [55] 设计的 session 隔离无跨任务 leak（复用该文档验收项）。

### 9.4 改动点

| 文件 | 改动 |
|------|------|
| inbox 机制 | 每轮 action 前 flush 未读反馈，并入 observation |
| `react_loop.py` | 在循环顶部检查 inbox（薄） |
| 前端 | 运行中任务卡增加"留言"入口（已有雏形，随 [55] 完善） |

---

## 十、统一消息契约与总体状态机

### 10.1 统一 paused 契约（合流）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `event` | str | ✅ | `paused` |
| `type` | str | ✅ | `confirm`（权限）/ `question` / `plan` / `form` |
| `confirm_id` | str | ✅ | 全局唯一 |
| `action` | str | ✅ | 允许的决策：accept/edit/reject/respond |
| `question` | str | 条件 | question/plan/form 的问题正文 |
| `options` | list[str] | 条件 | question 候选（或 plan 的批准/取消） |
| `plan_steps` | list[obj] | 条件 | plan 明细 |
| `form_schema` | obj | 条件 | form 的 JSON Schema |
| `field` | str | 条件 | 答复回填字段 |
| `tool_name` | str | confirm | 被拦截工具 |
| `severity` | str | confirm | safe/destructive/dangerous |
| `safety_level` | str | confirm | 安全分级 |
| `auto_confirm` | bool | ✅ | 是否自动放行 |
| `confirm_timeout` | int | ✅ | 秒（question/plan 可更长） |
| `trust_session` | bool | ✅ | 是否可记住该信任 |

### 10.2 统一 resolve 载荷（合流）

```jsonc
POST /confirm
{
  "confirm_id": "c_...",
  "action": "accept|edit|reject|respond",
  "data": "任意JSON",           // respond 答复 / edit 后的 args
  "reject_reason": "str|空",     // reject 理由
  "trust_session": false
}
```

### 10.3 统一状态机（四态 + 分支）

```
                 ┌─ action=accept ─────────────► 正常执行(RUN)
create ─► WAITING─┼─ action=edit+data ──► 安全重校验 ──►(通过)RUN / (危险)二次弹窗
                 ├─ action=reject+reason ─► REJECTED ─► observation回喂(用户口吻)
                 └─ action=respond+data ─► DONE ─► observation回喂(答复)
  超时 ──► TIMED_OUT ─► observation回喂("用户未在限时内答复")
```

### 10.4 事件登记总则

- 新增 `paused/resumed` **字段扩展**无需登记（事件类型不变）；
- 若拆独立事件（如 `plan`、`question`）必须先登记 `steps/__init__.py`，再在前端 sseParser 增加分支。

---

## 十一、实施优先级（P0~P5）

| 级别 | 方法 | 估期 | 理由 |
|------|------|------|------|
| P0 | A 结构化询问 ask_user（kind=question + respond） | 2~3 天 | 最高价值，独立通道，复用三原语，前端新增组件即可 |
| P1 | B 编辑/拒绝（action=edit/reject + 理由回喂） | 2~3 天 | 弹窗高频痛点（编辑防错、拒绝回喂），改 resolve 多态 |
| P2 | E 策略化询问（decide_intercept + 频次降噪） | 2 天 | 少打扰，提升体感，纯后端仲裁收口 |
| P3 | C 计划审批（type=plan + plan_steps + 批量豁免） | 2 天 | 高风险多步任务刚需 |
| P4 | D 表单化采集（type=form + form_schema） | 2~3 天 | A 的 schema 超集，前端 FormModal 按 schema 渲染 |
| P5 | F 实时反馈收口（inbox 每轮 flush + 隔离审计） | 1~2 天 | 依赖 [55] 与 inject_message_to_task 现状 |

**实施顺序原则**：B 复用 A 的 action 扩展 → E 复用 B 的 action 集合 → C 复用 A 的 paused 契约 → D 复用 A 的 schema → F 独立。无循环依赖，每步可独立验证。

---

## 十二、不能处理的问题

> 说明：原「风险清单」中**本次设计能够解决**的项，其缓解措施已内嵌至对应方法章节的实施注意/方法说明中，不再单列：
> - question 超时答复 → 四章 4.5 状态机（TIMED_OUT → observation 回喂，任务不悬置）；
> - edit 跳过安全检查 → 五章 5.3 后端实施方法（edit 必走 `check_safety_and_confirm` 重校验）；
> - reject 理由被当错误 → 五章 5.3（observation 标记 `agent_feedback`，非 error 通道）；
> - question/confirm 并发 → 四章 4.3（复用 S15 confirm_id 并发区分，question 单任务同一时刻至多一个）；
> - plan 批量豁免误伤 → 六章 6.3（豁免仅限计划清单内已展示项，清单外仍逐条拦截）；
> - kind 扩展破坏旧前端 → 十章 10.4 事件登记总则（字段可选、向后仅增，前后端同发）；
> - 前端弹窗组件膨胀 → 四章 4.7（AskUserModal/FormModal 复用 AuthorizationModal 的倒计时/并发/trust 既有模式）。

> 本章仅保留**本次设计范围内无法根治**、需依赖外部条件或后续专项的事项。

| 不能处理的问题 | 原因（为什么本次解决不了） |
|---------------|---------------------------|
| LLM 是否在"恰当场景主动发起 ask_user / plan"不可强制 | ask_user 与 plan 的触发依赖模型自主调用（工具能力+prompt 引导），后端只能提供通道，无法用代码强制 LLM 在正确的时机发起提问；过强引导会退化为「每条都问」反而打扰用户 |
| 超时后 Agent 收尾行为不可完全预测 | 超时统一转「用户未答复」observation 后，Agent 是跳过、取默认值还是改问法，由模型自主决策，后端只保证状态不悬置（4.5），无法保证收尾方式一定符合用户隐含预期 |
| HITL 弹窗总次数无法由本设计兜底降低 | edit/plan/信任（E）已显著降频，但"某用户就是重视确认、每次都要看"属于用户偏好，无法硬编码关闭确认；需靠设置面 confirm_mode（严格/宽松）后续在设置页开放 |
| 跨任务（多 session）HITL 的全局优先级/仲裁 | 单 python 进程内并发已由 S15 confirm_id 区分；跨 [55] 多进程/多服务实例时 confirm 状态的全局一致性依赖 [55] 多 Session 并发架构的实现，不属于本文档单一交互设计可覆盖 |

---

## 十三、附录：业界方案参考

| 来源 | 网址 |
|------|------|
| Claude Code Tools (AskUserQuestion) | https://code.claude.com/docs/en/tools-reference |
| LangGraph interrupts 文档 | https://docs.langchain.com/oss/python/langgraph/interrupts |
| LangChain HumanInTheLoopMiddleware | https://github.com/langchain-ai/langchain/tree/master/libs/langchain_v1/langchain/agents/middleware/human_in_the_loop.py |
| MCP-Agent elicitation 概念 | https://docs.mcp-agent.com/concepts/elicitation |
| OpenAI Agents SDK Human in the loop | https://openai.github.io/openai-agents-python/human_in_the_loop/ |
| Claude Code Plan Mode / workflows | https://claude-codex.fr/en/advanced/workflows |

---

## 十四、结论摘要

1. 六方法（A~F）合并为一份设计，全部复用现有 HITL 通道，Zero 推倒重来；
2. 核心是 **paused 多态化**（`type` × `action`）+ **resolve 多态化**（accept/edit/reject/respond）+ **拒绝/答复统一 observation 回喂**；
3. P0=ask_user、P1=编辑/拒绝，先落地 80% 体感提升；
4. 前端按 kind 渲染对应组件，其余复用 AuthorizationModal 既有模式；
5. 安全防线（edit 重校验、plan 豁免仅限清单）不因交互增强而退化。