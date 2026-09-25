# [71]后端重启运行中的未完成任务从 LLM/tool checkpoint 继续执行

> 编写人：小欧 2026-09-25 15:03:52
>
> 文档名称更新为：后端重启运行中的未完成任务从 LLM/tool checkpoint 继续执行（变更时间：2026-09-25 15:06:43，小欧）

| 版本 | 时间 | 作者 | 更新内容 |
|------|------|------|---------|
| v1.0 | 2026-09-25 15:03:52 | 小欧 | 创建本文档：R4（后端重启后未完成任务续算）概要设计，回答"解决什么问题/价值""与 P3 的关系""概要实施方案"三问。 |
| v1.1 | 2026-09-25 15:25:28 | 小欧 | 补全第四章"现状架构与缺口分析"：后端五层现状架构+9 个缺口（G1~G9）、前端四段现状架构+7 个缺口（F1~F7）、前后端缺口归属对照、目标形态与风险提示；定性结论为补缺口非重新设计。 |
| v1.2 | 2026-09-25 15:31:37 | 小欧 | 新增第五章"实施时序：待 [63] 实施完成后择机实施"：前置依赖门、择机窗口判据、串行合并纪律、分期落地清单与启动前检查表。 |

> 本文为**概要设计**，定演进方向、能力边界与实施路线；详细设计（checkpoint schema、恢复状态机、事务边界）需在此基础上另行立项细化。

---

## 一、要解决什么问题、什么场景、有什么价值

### 1.1 问题定义

R4 指 [63] 第七章明确定义的能力边界缺口：

> 后端重启后，运行中的**未完成任务**从 LLM/tool checkpoint 继续执行。[63] 规定 R4 **不在 P3 内实现**，需独立的 Agent checkpoint/resume 方案。

现状（[63] 完成后）：后端进程一重启，未完成任务即返回 `task_interrupted`，前端降级加载 DB 历史，用户必须**手动重新发起**整个任务。

### 1.2 触发场景

| 场景 | 触发方式 | 用户影响 |
|------|---------|---------|
| 发布升级 | 发版、`--reload` 重启、配置生效重启 | 运行中长任务中断 |
| 崩溃恢复 | OOM、异常退出、依赖服务重启 | 同上 |
| 跨时段长任务 | 任务执行数十分钟~数小时 | 维护窗口内白跑 |
| 被动中断 | 断电、容器迁移、ECS 重建 | 同上 |

### 1.3 价值

1. **长任务不因运维动作白跑**：部署/崩溃不再是任务的"审判"，最多续点重跑；
2. **消除重跑代价**：前 80% 进度（文件处理、多轮工具调用、LLM 推理链）被保全，只补剩余工作；
3. **任务记录完整闭环**：`开始→中断→续算→完成` 全链路事件连续，检验报告、审计记录无断档；
4. **提升平台可靠性心智**：用户敢于把关键长任务交给系统，而不是盯着跑完才敢动。

---

## 二、[63] 完成后的系统现状，R4 与 P3 的关系

### 2.1 [63] 完成后的能力现状

| 能力 | 交付内容 | 状态 |
|------|---------|------|
| 前端 L1 内存 Store | 路由/标签页切换不断流 | P1 交付 |
| 前端 L2 持久化+续传 | 刷新后 GET `after_seq` 续传（300s 窗口内） | P2 交付 |
| 前端 L3 DB 兜底 | 窗口外回退历史，行为不劣化 | P1/P2 交付 |
| 后端 R1 内存级续传 | 运行中断线按 `event_log` 续传 | 已支持 |
| 后端 R2 终态事件回放 | 完成后从 Journal 按 seq 精确回放 | P3 交付 |
| 后端 R3 重启后已完成任务回放 | 重启后已完成任务仍可回放 | P3 交付 |
| **后端 R4 未完成任务续算** | **重启后从 checkpoint 继续计算** | **缺口，本文立项** |

### 2.2 R4 与 P3 的关系：有关系，但 P3 ≠ R4

**结论先行：R4 依赖 P3，必须建立在 P3 之上，但绝不能当作 P3 的附赠品。**

| 维度 | P3（事件 Journal） | R4（checkpoint/resume） |
|------|-------------------|------------------------|
| 持久化什么 | **外部可观察事件**（step/chunk/final…） | **Agent 内部执行状态**（推理循环、LLM 上下文、工具调用栈） |
| 恢复什么 | **回放已发生**（读历史） | **继续未完成**（推进计算） |
| 是否需要执行引擎 | 否，纯读取 | 是，需重建 agent_runner 并驱动循环 |
| 幂等要求 | 低（只读回放，无副作用） | **高**（工具副作用严禁重放两次） |
| 前端感知 | 回放特殊标记 | `task_resumed` 续算信号 + 同一 seq 流继续 |

**依赖点（为什么要搭在 P3 上）：**

1. **seq 单调续写**：续算后新事件必须继续 append 到**同一 task_id** 的 `chat_stream_events`，seq 与中断前严格连续——这正是 P3 的 `task_id + seq` 主键与唯一 seq 分配器提供的；
2. **终态权威**：`chat_tasks.status` 仍是判"是否需续算"的权威（P3 7.9.1 已固定）；
3. **degraded 语义复用**：checkpoint 写失败、恢复失败要复用 P3 的 `persistence_degraded` 体系，不另造一套状态。

**P3 不能满足 R4 的地方（[63] 7.9 原话）：**

> "后端进程已经消失，不能凭空继续一个未完成的 LLM/tool 执行。R4 不得伪装成'事件持久化已解决'。"

事件日志是**回声**，不是**状态**；完整 replay 已发生事件也无法反推 Agent 内部下一步决策。因此 R4 必须在 P3 之上**新增执行状态层**。

---

## 三、概要设计实施方案

### 3.1 目标架构（三层叠加）

```text
事件层（P3 已建）    chat_stream_events —— 已发生事件的持久回放源
状态层（R4 新增）    task_checkpoint  —— Agent 执行状态的持久化快照
执行层（R4 新增）    恢复驱动渲染 —— 重建 agent_runner 从 checkpoint 推进
```

- 事件层解决"别人看得到发生了什么"；
- 状态层解决"系统自己记得接下来该干什么"；
- 执行层解决"把'记得的'重新跑成'进行的'"。

### 3.2 checkpoint 内容（最小集）

| 分类 | 必须含 | 说明 |
|------|--------|------|
| 任务元数据 | task_id、session_id、最后 seq、LLM 配置版本 | 决定续算到哪个任务、用哪套配置 |
| 循环状态 | 当前 step 索引、pending tool 调用参数、reasoning 阶段 | 决定从哪个意面继续 |
| LLM 上下文 | 已消费消息数组的**压缩引用**（或可重建的摘要） | 禁止完整重放全部 tokens，否则续算成本翻倍 |
| 工具调用栈 | 已完成/进行中/待执行三态清单 | 未完成副作用显式降级为"需重做" |
| 不可序列化资源 | 进行中命令、文件句柄 | 明确标记为"不可恢复，须重做该步骤" |

### 3.3 写入时机

```text
每个"不可逆副作用"之前   → checkpoint（防止副作用后崩溃丢状态）
每个工具 result 之后      → checkpoint（进度锚点）
final 之前               → 终态前置 checkpoint（防"差一步没打成"）
```

- 写入频率需实测：过高则 SQLite 写放大，过低则恢复粒度粗；参考 P3 7.5.2 的批量提交预算，checkpoint 使用独立小表、低频写。

### 3.4 恢复流程

```text
后端启动引导
  → 扫 chat_tasks 中"非终态"任务
  → 有 checkpoint：
        校验 task/session/配置版本 → 重建 agent_runner
        → 从 checkpoint 续跑执行层
        → 新事件继续 append 同一 task 的 Journal，seq 连续
        → 前端无需重连感知，按 after_seq 自然续拉
  → 无 checkpoint 或损坏：维持 task_interrupted（现状语义，不劣化）
```

### 3.5 幂等与副作用安全（R4 实战最大风险）

1. **副作用登记表**：每个副作用写 `task_id + step 序号 + 幂等 key`；
2. **恢复避重**：恢复时凡"已完成副作用"一律不重放；"进行中"标记为需重做，禁止盲重放；
3. **LLM 调用缓存**：已消费上下文用压缩引用，避免续算重复计费/结果漂移；
4. **operationId/generation 校验**：恢复后若 session 侧 generation 已过期，丢弃结果，防止跨代串写（复用 [63] 4.5 约定）。

### 3.6 模块划分

| 文件 | 职责 |
|------|------|
| 新增 `services/agent/checkpoint_store.py` | checkpoint 存取（窄接口：load/save/remove） |
| 改造 `agent_runner.py` | 注入 checkpoint 写入点 + 提供恢复入口 |
| 改造 `stream_orchestrator.py` | 启动引导扫描 + 恢复驱动接线 |
| 改造 `db_initializer.py` | 建 `task_checkpoint` 表（幂等迁移） |
| 新增 副作用登记模块 | 幂等 key 管理与重放避重判定 |

### 3.7 与 [70]/[69]/[63] 的边界

- **[70] ConnectionScope**：恢复后的连接必须走统一 ConnectionScope 创建，禁止恢复路径裸建新连接；
- **[69] LLM 连接资源**：续算重连复用统一资源池，不绕过限流/超时；
- **[63] P3**：R4 只复用 P3 的 seq 分配器、终态权威、degraded 体系；不重写事件格式，不新增第二套事件白名单；
- 三方必须串行合并，禁止对 `agent_runner.py` 同时做多套未协调 diff。

### 3.8 降级与透明度

| 情形 | 行为 |
|------|------|
| 无 checkpoint | `task_interrupted`，维持现状，不劣化 |
| checkpoint 损坏/校验失败 | 降级 `task_interrupted`，保留错误日志 |
| 续算中途再崩溃 | 返回最近完好 checkpoint 继续（最多损失一个 checkpoint 间隔） |
| 前端 | 新增 `task_resumed` 事件；异常仍用既有 `task_interrupted` |

### 3.9 风险与对策

| 风险 | 对策 |
|------|------|
| LLM 重放成本/结果漂移 | 上下文压缩引用 + 缓存已消费 tokens |
| 工具副作用重复执行 | 副作用登记 + 幂等 key + 进行中标记重做 |
| checkpoint 与 Journal 不一致 | 写 checkpoint 与更新 seq 走同一事务边界 |
| 恢复后串写/跨代状态 | operationId/generation 过期丢弃 |
| SQLite 写放大 | checkpoint 低频独立表 + 实测预算 |

### 3.10 实施路线（概要级分段）

| Phase | 内容 | 验证门 |
|-------|------|--------|
| A 详细设计 | checkpoint schema、恢复状态机、事务边界、副作用登记契约 | 设计评审 + 三堂会审 |
| B checkpoint 写入 | 写入点布点 + `task_checkpoint` 表 + 注入 agent_runner | 写入/恢复数据不丢失单测 |
| C 恢复引擎 | 启动扫描 + agent_runner 恢复入口 + 同一 seq 续写 | 进程被杀重启后能续算到完成 |
| D 幂等登记 | 副作用登记 + 重放避重 + LLM 缓存 | 已完成副作用零重放 |
| E 端到端验证 | 真实后端 + 真实 LLM 长任务杀进程续算；后端重启中途再崩 | [63] P4~P9 + R4 用例全过 |

### 3.11 验收门（概要级）

1. 进程被杀 → 重启 → 未完成任务自动续算到完成，前端 `after_seq` 连续、无重复；
2. 恢复前后 seq 单调、同 task 不分裂成两个任务链；
3. 已完成副作用不重放、未执行步骤不跳过；
4. 无 checkpoint 时保持 `task_interrupted`，行为不劣化；
5. checkpoint 写入性能在预算内，不拖慢实时链路；
6. [70] ConnectionScope、[69] 连接池与 [63] P3/P1/P2 用例全部回归通过；
7. 通过合规、合理、关联逻辑三堂会审，不引入第二套 seq、不新增重复事件白名单。

---

## 四、现状架构与缺口分析（后端 / 前端）

> 本章为代码核实结论：逐层说明"现在到底是什么架构"，再按层列出**不支持"服务端断开重启后持续运行"**的缺口并给出确切个数，最后分别对后端、前端定性为"重新设计"还是"补缺口"。核实时间 2026-09-25 15:25:28，核实文件见 4.8。

### 4.1 后端现状架构（五层 + 一条续传链）

```text
① 接入层    chat_routes / stream_orchestrator：POST /chat/stream 起任务；db_ops 命名空间注入；_agent_tasks 强引用保活
② 流态层    task_state.StreamBuffer：event_log(append-only, seq=len) + cond + done，publish 唯一写入口
③ 消费层    stream_reader(buffer, after_seq)：按 seq 从 offset 转发 SSE，done 置位即收流
④ 执行层    agent_runner.run_react_background → react_loop.run_react_cycle：ReAct 循环 + 10 处 publish + finally 终态落库
⑤ 状态层    Agent 实例内存态（UniversalAgent / BaseAgent / MessageBuilder）+ running_tasks 控制态
⑥ 持久层    SQLite：chat_tasks(status 权威) / chat_task_steps(步骤) / token_usage(用量) / chat_user_message
```

**续传链现状（只覆盖"进程不死"）**：

```text
前端 GET /chat/stream/{task_id}?after_seq=N
  → stream_orchestrator.resume_sse → get_stream_buffer(task_id)
      命中：stream_reader 从 offset=N 续读 event_log（内存 R1）
      未命中：logger.warning + 404（重启后必然走此支）
```

**各层关键事实**：

| 层 | 现状事实 | 生命周期 |
|----|---------|---------|
| 流态层 | `agent_streams: dict[task_id, StreamBuffer]`，`publish` 持锁完成 seq 分配+append+notify | **进程内存**；任务结束 `loop.call_later(300, reclaim_stream_buffer)` 延迟 300s 回收 |
| 执行层 | `run_agent_in_background` 独立 asyncio 后台任务，`_background_tasks` 强引用防 GC；finally 内终态 UPDATE `chat_tasks.status` | **进程内存**；进程退出即整体消失，无 finally |
| 状态层 | `llm_call_count`、`_consecutive_reasoning_only`、`_last_error`、`_usage_events`、三类 token 累计、`MessageBuilder.conversation_history`/`last_total_tokens`/裁剪压缩标记 | **Agent 实例内存**，无 checkpoint |
| 持久层 | `chat_tasks.status` 默认 `executing`，终态 completed/failed/cancelled/paused；步骤明细 `chat_task_steps` | SQLite，**只有结果，没有过程状态** |
| 回收 | 缓冲 300s 后回收；`task_cleanup` 清理 `running_tasks` | 回收后连"已完成任务"的事件也只在 DB 步骤表里 |

**重启后的真实行为链（代码事实，非推测）**：

```text
进程重启 → agent_streams/running_tasks 清空
  → 前端重连 GET /chat/stream/{task_id} → get_stream_buffer 返回 None → 404 + warning
  → 前端重试 3 次全失败 → 转入 pollSessionTaskStatus：GET /sessions/{sid}/tasks 每 5s × 30 次
      任务在 chat_tasks 中仍是 executing（崩溃未写终态）→ 30 次都不命中终态
  → 弹 "连接已断开且任务仍在执行，请手动确认任务状态" → 用户只能手动重发整个任务
```

### 4.2 后端缺口清单（共 9 个）

| 编号 | 缺口 | 所在层 | 后果 |
|------|------|-------|------|
| G1 | **执行状态无持久化**：`llm_call_count`/reasoning 连续计数/`_last_error`/usage 事件/token 三类累计全在 Agent 实例内存 | 状态层 | 重启后不知"跑到第几步、错在哪、已花多少 token" |
| G2 | **LLM 上下文无快照**：`MessageBuilder.conversation_history`、`last_total_tokens`、裁剪/压缩标记（`_summary`/`_pruned`/`_compressed`）不可重建为"等价上下文" | 状态层 | 续算要么丢上下文（结果漂移），要么全量重放（成本翻倍） |
| G3 | **工具调用栈无三态登记**：已完成/进行中/待执行没有 `task_id + step + 幂等 key` 落库 | 执行层 | 恢复时无法判断哪些副作用已完成，重放即重复写文件/重复执行命令 |
| G4 | **流态缓冲纯内存 + 300s 回收，无 Journal**：`chat_stream_events` 表当前**不存在**（P3 未实施） | 流态层 | 重启后连"已发生过什么"都取不到，只能 404 |
| G5 | **无恢复驱动**：`agent_runner` 无 resume 入口；启动流程不扫描 `chat_tasks` 中非终态任务 | 执行层 | 没有任何代码会把"中断的任务"重新推起来 |
| G6 | **不可序列化资源无降级规则**：进行中 shell 会话、文件落盘 `finalize` 未完成、LLM 连接池快照/pause event | 状态层 | 恢复时这些态"假装存在"必然崩，或被静默丢弃造成半成品 |
| G7 | **无续算信号**：事件类型里没有 `task_resumed`，前端无法区分"历史回放"与"正在续算" | 流态层 | 用户看到流突然继续，误判为重放/重复 |
| G8 | **checkpoint 写入时机与事务边界未定义**：与 Journal seq、`chat_tasks.status` 的同事务关系缺契约 | 持久层 | 状态与事件可能撕裂（事件已发、状态未落） |
| G9 | **崩溃后非终态任务无终态收敛**：`chat_tasks.status` 永久停留 `executing`，无 `interrupted` 收敛态 | 持久层 | 前端轮询永远等不到终态，只能提示用户手动确认 |

**定性结论：补缺口，不是重新设计。**

理由（四条，均可对照上表）：

1. **主干链路完整可复用**：ReAct 循环（`react_loop`）、事件单写入口（`StreamBuffer.publish`）、终态权威（`chat_tasks.status`）、seq 单调机制**全部已存在且在线上跑**；缺的只是"把状态从内存搬到 DB"和"启动时把任务推起来"两块；
2. **缺口是"点"不是"面"**：9 个缺口中 6 个（G1/G2/G3/G6/G8/G9）是**在既有对象上加持久化字段与写点**，不触碰既有控制流；G4 属 P3 已立项范围，G5/G7 各为一个新入口 + 一个新事件类型；
3. **重新设计会退化既有能力**：若另起一套执行引擎，则要重做 seq 分配、终态语义、HITL 暂停/取消、token 四层累计、文件 A/B 落盘——这些均已有大量回归用例，重设计等于主动制造退化，违反"禁止 backward"与 YAGNI；
4. **补缺口的落点已被 [63]/[69]/[70] 划定**：事件源归 P3、连接与资源所有权归 [69]/[70]，R4 只在其上叠"状态层 + 执行层"，无架构冲突。

### 4.3 前端现状架构（内存真源 + 备份 + 重连 + 降级四段）

```text
① 发送/连接   useSSE.sendMessageInternal：POST /chat/stream 起任务；fetch + ReadableStream + AbortController（非 EventSource）
② 真源        React state + ref：executionSteps / executionStepsRef / lastSeqRef(-1) / serverTaskId / usageAccumRef
③ 备份        sessionStorage：sse_execution_steps_backup_{sessionId}，5s 防抖，外壳 {steps, source, timestamp}，恢复时剔除 preview 行
④ 重连        指数退避 + Full Jitter，maxAttempts=3；GET /chat/stream/{task_id}?after_seq=lastSeq+1；请求头超时 180s、空闲超时 60s（心跳/HITL 挂起）
⑤ 重试耗尽    pollSessionTaskStatus：GET /sessions/{sid}/tasks 每 5s × 30 次，终态或不存在则静默收尾，超时提示手动确认
⑥ 会话恢复    useChatSession：URL session_id → loadHistoryMessages(DB 历史)；否则 restoreState(sessionStorage)
```

**前端关键事实**：

| 项 | 现状 | 限制 |
|----|------|------|
| 事件真源 | 组件内存（`useSSE` 内 state/ref），[63] 设计的 L1 全局 Store **尚未实现** | 切页面/刷新即丢 |
| 续传游标 | `lastSeqRef` 组件内私有，**不从备份恢复** | 刷新后即使有 taskId 也无正确 after_seq |
| 备份完整性 | 5s 防抖快照，非事务；预览 action 行被剔除；容量满则跳过写入 | 只能"看个大概"，不能当续传依据 |
| 无 taskId 分支 | 重连态若 `serverTaskId` 为空，`sendMessageInternal` 直接抛错终止重连（防重复起任务） | 首响应未到即断线 = 任务失联 |
| 后端重启 | 前端无对应事件语义，只能靠 4/5 轮询猜 | 用户只见"请手动确认" |

### 4.4 前端缺口清单（共 7 个）

| 编号 | 缺口 | 后果 |
|------|------|------|
| F1 | **无跨页面/跨刷新共享 Store**（L1 未落地）：事件真源在组件内存 | 切页丢流，刷新丢流 |
| F2 | **无 taskId + after_seq 的续拉恢复路径**：`lastSeqRef` 不持久化，恢复即 `after_seq=0` 语义缺失 | 刷新后无法精确续传，只能重看或丢帧 |
| F3 | **备份态不是可续传游标**：无 `{last_seq, task_id, status}` 元数据外壳，5s 防抖可能落后 | 恢复点不精确，可能重复渲染或丢步 |
| F4 | **后端重启无可拉事件源**（依赖 G4）：Journal 不存在 | 轮询只能看终态，看不到"续算过程" |
| F5 | **无 `task_resumed` / `task_interrupted` 事件语义与 UI**：无"任务已中断/已从断点续算"提示 | 用户无法判断任务真实状态，信任度受损 |
| F6 | **降级路径口径不统一**：sessionStorage 恢复 / DB 历史回放 / 轮询静默收尾 / 手动确认提示，四条路径无统一终态模型 | 同一场景不同入口表现不一致 |
| F7 | **seq 基线与去重未跨视图共享**：`lastSeqRef` 私有，多入口/多组件各自计数 | 同一 task 被多处消费时易重复渲染 |

**定性结论：同样是补缺口，不是重新设计。**

理由：前端的流式消费、重连退避、续传 URL、轮询观察、降级历史**均已实装且有测试覆盖**；7 个缺口中 F1/F3/F7 是"把已有内存态提升为可共享、可持久化的真源"，F2/F5 是"补一条恢复路径 + 两个事件语义"，F4/F6 依赖后端 G4 与统一终态模型。整套前端交互骨架（fetch+reader+AbortController+错误中心）无需变更，**改动面集中在状态真源与事件语义两处**。

### 4.5 前后端缺口对照与归属

| 缺口 | 归属 | 依赖 | 是否 R4 范围 |
|------|------|------|------------|
| G1/G2/G3/G6/G8/G9 | 后端状态层 + 持久层 | 依赖 G4 的 Journal seq 事务 | 是（R4 核心） |
| G4 | 后端流态层 | [63] P3 | 由 P3 交付，R4 消费 |
| G5/G7 | 后端执行层 / 流态层 | 依赖 G1~G3 | 是 |
| F1/F3/F7 | 前端状态真源 | 无 | 是（[63] P1 落地后叠加） |
| F2/F5 | 前端恢复路径 + 事件语义 | 依赖 G7 | 是 |
| F4/F6 | 前端拉取源 / 降级模型 | 依赖 G4、G9 | 与 P3 串行 |

**合计：后端 9 个缺口 + 前端 7 个缺口 = 16 个缺口；定性为"在现有五层后端架构与四段前端架构上补缺口"，不重新设计。**

### 4.6 补缺口后的目标形态（与第三章呼应）

```text
后端：既有五层不动
      ① 接入层：启动后扫 chat_tasks 非终态 → 交恢复入口（新增，不改原 POST 链）
      ② 流态层：Journal（P3）落地后，event_log 与 chat_stream_events 双写同事务
      ③ 消费层：stream_reader 不变，续算事件天然按 seq 续读
      ④ 执行层：agent_runner 新增 resume 入口，复用 run_react_cycle，不新建执行引擎
      ⑤ 状态层：新增 task_checkpoint 存取 + 注入点（唯一新增状态源）
      ⑥ 持久层：非终态任务补 interrupted 收敛态

前端：既有四段不动
      内存真源 → 共享 Store（[63] P1）+ 备份外壳补 {task_id, last_seq, status}
      重连链 → 复用现有 after_seq=lastSeq+1，仅把 lastSeq 改为可持久化来源
      事件语义 → 新增 task_resumed / task_interrupted 两类展示
```

### 4.7 风险提示（诚实边界）

1. 16 个缺口**不是 16 个独立任务**：G4 归 P3、F1 归 [63] P1，R4 实际需新建的是 `task_checkpoint` 表、写入点、恢复入口、副作用登记四件事；
2. G3（副作用幂等）是**唯一无法用代码量衡量风险**的缺口，若登记契约设计不严，恢复即可能重复写文件/重复执行命令，必须在 Phase A 详细设计中先定契约；
3. 前端 F5 若先于后端 G7 上线，会出现"前端等一个永不到来的事件"，故前后端必须**同窗口交付**，禁止前端单边先行。

### 4.8 本章核实文件清单

| 文件 | 核实用途 |
|------|---------|
| `backend/app/services/task/task_state.py` | StreamBuffer/publish/agent_streams/回收接口 |
| `backend/app/services/agent/agent_runner.py` | 后台任务保活、finally 终态落库、300s 回收、事件通道路由 |
| `backend/app/services/agent/react_loop.py` | ReAct 循环与 publish 发射点 |
| `backend/app/services/agent/universal_agent.py`、`base_agent.py`、`message_builder.py` | Agent 实例态与 LLM 上下文态 |
| `backend/app/services/chat/stream_orchestrator.py` | 续传端点、db_ops 注入、`reclaim_stream_buffer` |
| `backend/app/db/db_initializer.py` | `chat_tasks`/`chat_task_steps`/`token_usage` 表结构（确认 `chat_stream_events` 不存在） |
| `frontend/src/hooks/useSSE.ts` | 内存真源、sessionStorage 备份、after_seq 重连、轮询观察 |
| `frontend/src/features/chat/hooks/useChatSession.ts`、`useChatPersistence.ts` | 会话恢复与 DB 历史降级路径 |

---

## 五、实施时序：待 [63] 实施完成后择机实施

> 结论先行：R4 **不在 [63] 实施期间并行开工**，待 [63] 全部交付并稳定运行后，再择机实施。本章给出前置门、择机判据、合并纪律与启动检查表。

### 5.1 为何必须排在 [63] 之后

| 依据 | 说明 |
|------|------|
| 第四章 G4 | Journal（`chat_stream_events`）当前**不存在**，是 R4 续写 seq 连续、崩溃后取回事件的前提；[63] P3 未落地时 R4 无事件源可接 |
| 第二章依赖点 1 | 续算后新事件必须续写同一 `task_id` 的 Journal，seq 严格连续——该 seq 分配器与唯一约束由 P3 提供 |
| 第二章依赖点 3 | checkpoint 写失败/恢复失败要复用 P3 的 `persistence_degraded` 体系，语义不另造 |
| 冲突面 | [63] P1/P2/P3 与 R4 都要改 `stream_orchestrator`（启动引导、续传端点）与 `agent_runner`（写入点/恢复入口）；并行必冲突 |
| 回归面 | R4 的验收门依赖 [63] P1~P9 全部用例先稳定；基线不绿时无法判定 R4 引入的问题归属 |

### 5.2 前置门（全部满足才允许启动 R4）

| 门 | 判据 |
|----|------|
| 门 1 | [63] P1（前端 L1 内存 Store）、P2（持久化+续传）、P3（后端 Journal）**全部交付并合入主干** |
| 门 2 | `chat_stream_events` 表已建、`task_id + seq` 唯一约束与 seq 分配器已上线并有对账日志 |
| 门 3 | [63] P1~P9 与 fre2e_01~12 全绿，连续两轮无新增 flaky |
| 门 4 | [69] LLM 连接池、[70] ConnectionScope 方案已实施（恢复路径必须走统一连接/资源所有权，禁止裸建） |
| 门 5 | 第四章 16 个缺口已逐条复核，确认无新增缺口、无归属变更 |

### 5.3 择机窗口判据（满足越多越宜开工）

1. **无并行改造**：同一分支无其他涉及 `agent_runner` / `stream_orchestrator` / `task_state` 的在途改动；
2. **有稳定基线**：主干连续运行稳定，无热修补丁在飞；
3. **可验证窗口**：具备"杀后端进程 → 重启 → 观察续算"的完整真实验证条件（真实后端 + 真实 LLM + 真实工具 + 真实 SQLite）；
4. **负载可承受**：R4 引入启动期扫库与 checkpoint 低频写，需在低峰窗口实施与观察；
5. **回退成本可控**：新增表与新增写点均为加法，实施期出现异常可**停用恢复入口**回到 [63] 完成态（不需回滚 [63] 成果）。

### 5.4 串行合并纪律（铁律）

1. **一次一方案**：同一时间窗内只允许 [63] 或 R4 之一改上述三个核心文件，禁止交叉 diff；
2. **R4 落地顺序**：Phase A 详细设计 → Phase B checkpoint 写入 → Phase C 恢复引擎 → Phase D 幂等登记 → Phase E 端到端验证，逐门推进，前一门不过不启下一门；
3. **禁止提前埋点**：R4 不得在 [63] 未完成时以"临时开关"形式预埋进主干，避免半成品状态长期共存；
4. **禁止测试文件入库**（沿用仓库铁律，E2E 用例如需特批由北京老陈裁定）；
5. **文档同步**：每阶段完成后回写本文档版本历史与 [63] 的 R4 状态行，不留"口头已完成"。

### 5.5 启动前检查表（Phase A 开工前逐项打勾）

- [ ] [63] P1/P2/P3 已合入主干，Journal 对账日志无异常
- [ ] [63] P1~P9、fre2e_01~12 全绿且已连续两轮
- [ ] [69]/[70] 已实施，恢复路径的连接与资源归属明确
- [ ] 第四章 16 个缺口复核完成，归属无变化（G4 归 P3、F1 归 P1 已确认消化）
- [ ] 详细设计评审通过：`task_checkpoint` schema、恢复状态机、事务边界、副作用登记契约
- [ ] 三堂会审（合规 / 合理 / 关联逻辑）通过并留痕
- [ ] 已确认降级语义：无/坏 checkpoint 一律回 `task_interrupted`，行为不劣化
- [ ] 已确认前后端同窗口交付（F5 不得先于 G7 单边上线）

### 5.6 若长期未择机：当前状态如何对外表述

- 能力口径：后端 R1（内存级续传）/R2/R3 已由 [63] 交付，**R4（未完成任务续算）未实施**；
- 用户可见行为：后端重启后未完成任务返回 `task_interrupted`（[63] 完成后），前端降级 DB 历史，用户手动重发；
- 严禁表述：不得把"事件已持久化"说成"任务可续跑"，也不得暗示续算已在计划内自动进行。

---

> 更新人：小欧 2026-09-25 15:31:37
> v1.0 创建完成：明确 R4 问题定义与价值、与 P3 的边界关系、概要实施方案与实施路线。
> v1.1 补全第四章：后端五层现状架构 + 9 个缺口、前端四段现状架构 + 7 个缺口、缺口归属对照与"补缺口非重新设计"定性结论。
> v1.2 新增第五章：明确 R4 待 [63] 实施完成后择机实施，含前置门、择机判据、串行合并纪律、启动前检查表与未实施时的对外表述纪律。