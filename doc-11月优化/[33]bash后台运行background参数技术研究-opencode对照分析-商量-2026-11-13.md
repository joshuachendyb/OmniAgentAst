# bash 后台运行 background 参数设计（opencode 源码实证 + OmniAgent 落地方案）

**编写人**: 商量
**日期**: 2026-11-13（初稿→修订①：审查修正通知机制→修订②：opencode 执行链路源码实证，纠正"任务终态只能降级桌面通知"的想当然结论，改为自动续跑方案→修订③：补同会话串行语义与前端左右结构处理→修订④：全文一致性核查，修正文内矛盾与实施缺口并融入正文）
**opencode 源码依据**（全部 2.2.5 实证）:
- `packages/core/src/tool/plugin/shell.ts`（L151-183 notifyWhenDone / L248-251 background 分支）
- `packages/core/src/session/session.ts`（L286-326 synthetic 定义）
- `packages/core/src/session/execution.ts`（L17-40 Interface / L109-146 coordinator）
- `packages/core/src/session/run-coordinator.ts`（L131-140 wake 语义 / L111-115 settle）
- `packages/core/src/session/inbox.ts`（L52-57 Promotable / L191-224 admit）
- `packages/core/src/session/runner/to-llm-message.ts`（L276-277 synthetic→user role）
- `packages/core/src/session/projector.ts`（L749-755 synthetic 落库投影）
- `packages/core/src/session/sql.ts`（L137-143 SessionInboxTable 持久化）

**OmniAgent 源码依据**:
- `backend/app/tools/fundamental/execute_shell_command.py` / `fundamental_schema.py`
- `backend/app/services/task/task_registry.py`（inject_message_to_task L138 / register_task 占位守卫 / drain_inbox L162）
- `backend/app/services/agent/react_step.py`（_absorb_inbox L238, L362）
- `backend/app/services/chat/stream_orchestrator.py`（L1000-1067 同 session 发起新任务完整路径）
- `backend/app/tools/tool_retry_engine.py`（L235-271 shell 专用执行器）

---

## 一、opencode 实证：后台命令完成后如何唤醒 LLM（完整执行链路）

> 本节为源码逐行实证，纠正初稿两处想当然：① synthetic 不是"直接合成消息写会话流"，而是**先入持久化 inbox 再唤醒**；② 任务结束后 opencode **不是降级通知，而是自动开新一轮 LLM**。

### 1.1 完整链路（五步）

```
后台命令完成 (notifyWhenDone, shell.ts:151)
  ① sessions.synthetic(sessionID, {text, description, metadata,
                                  delivery:"steer", resume:true})   session.ts:286
       ├─ 构造 type="synthetic" + SyntheticPayload 的 inbox item
       ├─ admission.admit() → 幂等落库 SQLite SessionInboxTable   inbox.ts:191, sql.ts:137
       │    （reconcile 先查同 id 已存在 → notificationID 复用防重复通知）
       └─ projector 投影: synthetic 同时写入 session message 历史   projector.ts:749
          （type="synthetic"，UI 显示 [Synthetic context]，重启/回放不丢）
  ② if (resume !== false && !revert) execution.wake(sessionID)      session.ts:323
  ③ wake 语义（run-coordinator.ts:131）——两种状态在这里分叉：
       ├─ execution 活跃（上一轮还在跑）→ pendingWake="steer" 门铃
       │    → 当前 drain 结束前再 drain 一次（吸收 synthetic，不打断工具）
       └─ execution 空闲（上一轮已正常结束）→ start(key, false, "steer")
            → 【启动全新 execution = 开新一轮 LLM】
  ④ 新 execution 的 drain → nextPromotable(db, sessionID, "steer") 从 inbox 提升消息
  ⑤ synthetic → Message.make({role:"user", content: text})          to-llm-message.ts:276
       → 同 session 完整历史 + 新 LLM 调用 → agent 自动续跑处理结果
```

### 1.2 关键实证结论

| # | 结论 | 源码证据 |
|---|------|---------|
| 1 | **synthetic 是持久化 inbox 消息，非内存直写** | SessionInboxTable 落库；重启后仍在 |
| 2 | **唤醒分两种状态，wake 统一处理**：活跃→门铃再 drain；空闲→**直接开新一轮 LLM** | run-coordinator.ts:131-140 `idle → start()` |
| 3 | **synthetic 以 user role 进入 LLM 上下文**（与 OmniAgent _absorb_inbox 同构） | to-llm-message.ts:276 |
| 4 | **幂等防重**：notificationID 复用，admit 前先 reconcile 查重 | inbox.ts:177-189, shell.ts:168 |
| 5 | **resume 可关**：`resume:false` 时只落库不唤醒（user shell 用此模式，session.ts:226）→ 通知与唤醒是两个独立开关 | session.ts:323 |
| 6 | **opencode 的"任务结束"只是 execution 空闲，session 长命**——这就是"任务终止后如何起新 LLM"的官方答案：wake-on-idle 自动续跑 | execution.ts:24-25 注释 |
| 7 | LLM prompt 明示可结束回答等唤醒："end your response; you will be resumed automatically" | shell.ts:25 BACKGROUND_INSTRUCTION |

---

## 二、OmniAgent 架构映射（上上下下对照）

| opencode 概念 | OmniAgent 对应 | 位置 | 差异 |
|--------------|---------------|------|------|
| session（长命会话） | **session_id**（长命） | 全链路 | 一致 |
| execution（一次运行，可空闲可唤醒） | **task_id**（一次任务，终态后 cleanup） | task_registry running_tasks | OmniAgent 任务终态即从注册表删除，无"空闲可唤醒"态 |
| synthetic inbox item（durable） | **无直接对应**——inject_message_to_task 是内存 inbox，且 uid>0 防御拒收系统消息 | task_registry.py:138-159 | 需新增 inject_system_notice |
| wake-on-idle 开新一轮 LLM | **无直接对应**——但编排层已有完整"同 session 发起新任务"路径（用户发消息即走此路） | stream_orchestrator.py:1000-1067 | 需新增"系统驱动续跑"入口复用该路径 |
| drain/门铃（活跃时吸收不打断工具） | ✅ 已有：_absorb_inbox 每轮 LLM 调用前吸收 inbox | react_step.py:362 | 一致，零改动 |
| SessionInboxTable 持久化 | chat_messages 落库（storage.insert_user_message） | storage.py | 续跑时通知文本作为 user message 落库即等价 |
| notificationID 幂等 | 无 | — | 续跑入口需带唯一 id 防重 |
| _SHELL_EXECUTOR 线程池/notify/kill_process_tree | ✅ 全部现役 | tool_retry_engine / fundamental / proc_utils | 复用 |

**核心映射结论**：OmniAgent 的 task ≈ opencode 的 execution，session 同构。opencode 的"execution 空闲后 wake 重启"在 OmniAgent 的等价物是"**任务终态后，在同 session 以系统驱动方式发起续跑任务**"——编排层发起新任务的完整路径（register_task→落库→run_agent_in_background→SSE 转发）现役可用，全部复用。

---

## 三、核心设计（修订②版）：通知、唤醒与三种任务状态

### 3.1 通知与唤醒统一入口

后台命令完成后执行 `_notify_and_wake(shell_id)`，按任务状态自动分叉（对齐 opencode wake 双语义）：

```
_notify_and_wake(shell_id):
  1. 读输出文件 → 通知文本([系统通知]前缀 + shell_id + 退出码 + 耗时 + 输出摘要 + output_file)
  2. 判定采用【session 级】两级判定(修订④, 与7.1统一; 原版只查原task_id会漏"原任务终态
     但同会话有新任务"的常态场景):
     ├─ 原任务 task_id 仍活跃(running/paused) → 状态A: inject_system_notice(task_id, text)
     ├─ 同 session 存在其他活跃任务(用户后发的新任务) → 状态A': 注入该活跃任务 inbox
     │    (经 has_active_task_in_session 查得占位 tid, 与编排层 B-3 守卫同款)
     ├─ 同 session 无任何活跃任务 → 状态B: resume_session_with_notice(session_id, text)
     └─ 原任务 cancelled → 状态C: kill 本任务名下后台进程树(用户已放弃) + 日志
  3. 注册表状态置 completed/failed; 释放后台并发名额; 结果文件保留(配置时长)
```

### 3.2 状态A：任务还在执行（= opencode 门铃路径）

```
后台命令完成 → inject_system_notice → inbox
→ agent 当前工具跑完（不打断工具，安全底线）
→ 下一轮 LLM 调用前 _absorb_inbox 吸收 → LLM 自然续跑
```

- **新增 `inject_system_notice(task_id, content)`**（task_registry.py，与 inject_message_to_task 并列）：同一 inbox 队列；**先 storage.insert_user_message 落库（带 system_notice 标记）拿真实 uid，再投 (content, uid) 元组**——对齐 opencode synthetic 双写（inbox+projector 持久化），重启不丢、前端历史可见；-1 仅作落库前瞬时占位，**落库后投真实 uid**，_absorb_inbox 吸收时锚演进正常零改动；**不放宽原函数 uid>0 防御**（那是防重落库红线，动了破插话功能）
- paused 同样可投递，恢复后吸收
- agent 正在跑长工具时通知等工具完成才吸收——与 opencode 门铃 drain 语义一致

### 3.3 状态B：任务已终态（= opencode wake-on-idle 路径）——**自动续跑，修正初稿**

> 初稿"降级为桌面通知等用户下次发话"是没读懂 opencode 的想当然。opencode 的答案（1.2 结论6）：**任务结束只是 execution 空闲，wake 直接开新一轮 LLM**。LLM 在发起 background 时已被明确告知"可以结束回答，完成后自动唤醒"——用户用 background=true 即已授权这次自动续跑，不违背"任务由用户驱动"（opencode 同语义）。

**新增 `resume_session_with_notice(session_id, notice_text, notice_id)`**（编排层新入口，复用 stream_orchestrator 现役发任务路径）：

```
1. 幂等守卫: notice_id 唯一（shell_id+完成时间戳），已续跑过则跳过（对齐 opencode notificationID reconcile）
2. 同 session 已有活跃任务（用户后发的新任务）→ 注入该活跃任务 inbox 回退状态A'路径
   （串行设计下的正常排队, 非异常; 与编排层 B-3 守卫同款）
3. 通知文本作为 user message 落库（storage.insert_user_message，带 system_notice 标记
   供前端区分渲染，对齐 opencode synthetic type 的 [Synthetic context] 展示）
4. 走编排层现役发任务全路径: register_task → create_stream_buffer → allocate ai_message
   → run_agent_in_background → SSE 转发（前端按既有任务流渲染，零新帧类型）
   系统驱动无 HTTP 连接: 复用"客户端断开静默返回, agent 后台继续"现役语义
   (stream_orchestrator.py:1069)——stream_buffer 事件全落 journal 持久化, 不等待前端消费者;
   前端经任务列表刷新/journal 重连机制发现新任务并回放(TaskListPanel 现役路径不变)。
   实施时从编排 generator 抽取"建任务核心段"为可独立调用的 async 函数
   (SRP 抽取, 用户路径与系统路径共用, DRY)
5. 续跑任务的 agent 上下文 = 同 session 完整历史（含 background=true 那轮的 llm_data
   shell_id/output_file）+ 通知文本 → LLM 自主决定后续动作（继续任务/汇报结果）
```

- **桌面 notify 降为可选补充**（配置开关，默认关）：续跑任务本身就有 SSE 流，前端已可见
- **续跑防失控**：续跑任务中若再发 background 命令且又终态，允许再续跑（链式，opencode 同款）；但**同一 shell_id 只允许触发一次续跑**（幂等守卫保证）
- **失败兜底**：续跑发起异常（如 DB 落库失败）→ logger.error + 桌面 notify + 结果文件保留，用户下次发话时 LLM 可用 bash_result 取回（bash_result 查询工具仍保留，双保险）

### 3.4 状态C：任务 cancelled

用户取消 = 放弃该任务一切后续：
- **不续跑**（opencode interrupt 语义：wake 属于被取消的 intent，interrupt 时 pendingWake 被清空，run-coordinator.ts:150-156 同款——取消后不复活）
- 任务 cleanup 时遍历后台注册表，`kill_process_tree` 终结本 task_id 名下后台进程（防 dev server 孤儿）

---

## 四、完整改造方案（3 层 + 配套，修订②版）

### 4.1 Schema 层（fundamental_schema.py ShellInput）

```python
background: bool = Field(
    default=False,
    description="后台运行命令并立即返回(适合dev server/长构建)。"
                "无需在命令末尾加&。完成时会自动收到系统通知并自动继续处理,"
                "不要轮询等待; 期间可继续其他工作或直接结束回答。"
                "后台命令默认无超时, 显式传timeout则生效。"
)
```

### 4.2 实现层（execute_shell_command.py shell()）

```python
def shell(command, shell_type="ps7", timeout=60, cwd=None,
          success_codes=None, background=False) -> Dict:
    # ... 参数校验/通用预处理/三路检测/语法修复 全保留 ...
    # 安全检查: 后台分支只放行白名单级命令, 中风险以上一律拒绝不弹窗
    #   (无值守场景中风险弹窗120s挂死是[9]卡死治理教训)
    if background:
        return _run_shell_background(processed_command, shell_type, cwd, cmd_short)
    # ... 现有前台逻辑零改动 ...
```

### 4.3 后台模块（新文件 shell_background.py）

```python
_BG_REGISTRY: Dict[str, dict] = {}   # {shell_id: {proc, output_file, task_id, command, status, started_at, notice_id}}
_BG_TASKS: set = set()               # Future 强引用集合(run_coroutine_threadsafe 返回值, done回调discard 防GC)
_BG_SEM = threading.BoundedSemaphore(  # 独立并发上限 tuning.shell_max_background 默认5
    int(get_config().get("tuning.concurrency.shell_max_background", 5)))
_MAIN_LOOP: asyncio.AbstractEventLoop = None  # 启动时缓存主事件循环引用

def _run_shell_background(command, shell_type, cwd, cmd_short) -> Dict:
    # 1. _BG_SEM 拿名额(拿不到明确失败); 2. Popen 非阻塞+输出重定向临时文件
    #    (轮转上限 tuning.shell_bg_log_max_mb 默认50MB, 保留最近2份, 防日志长跑写满磁盘)
    # 3. shell_id 注册 _BG_REGISTRY(记录 task_id; session_id 由 running_tasks[task_id]
    #    反查——现役字段零新依赖, 完成时判定活跃与续跑共用一份数据)
    # 4. 跨线程提交: shell() 在 _SHELL_EXECUTOR 工作线程执行, 线程内无事件循环,
    #    asyncio.create_task 直接调用必炸 → asyncio.run_coroutine_threadsafe(
    #    _wait_and_notify(shell_id), _MAIN_LOOP) 提交主循环, Future 入 _BG_TASKS
    # 5. 立即返回 build_success(data={shell_id, output_file, status:"running"},
    #      llm_data 同含 shell_id/output_file → 随历史留存)

async def _wait_and_notify(shell_id):
    # 1. await 进程退出(经线程池, 零占事件循环); 读输出文件(过 _truncate_shell_field 截断)
    # 2. _notify_and_wake: 状态A/A'注入 / 状态B自动续跑 / 状态C杀进程(见 3.1)
    # 3. 注册表置终态; 释放名额; 结果文件保留(配置时长)
```

### 4.4 配套新增

| 组件 | 位置 | 对应 opencode | 说明 |
|------|------|--------------|------|
| `inject_system_notice()` | task_registry.py | synthetic admit | 先落库（system_notice 标记）拿真实 uid 再投 inbox，同一 inbox，不放宽原防御 |
| `resume_session_with_notice()` | 编排层新入口 | `execution.wake` idle-start | 复用现役发任务全路径 + journal 持久化（无 HTTP 消费者）；notice_id 幂等；活跃任务则改注入 |
| `bash_result` 工具 | fundamental | — | 按 shell_id/output_file 查状态+输出（续跑失败兜底+中途读输出） |
| `tuning.shell_max_background` | 配置 | — | 后台并发上限默认5（名额生命周期=后台命令生命周期，占满明确失败） |
| `tuning.shell_bg_log_max_mb` | 配置 | — | 后台输出文件轮转上限默认50MB，保留最近2份 |
| 任务 cancelled 连带杀 | task cleanup 挂钩 | interrupt 清 pendingWake | kill_process_tree 终结本任务后台进程 |
| 结果文件清理 | _BG_REGISTRY | — | 保留可配置时长(默认24h) |

---

## 五、设计决策（修订②版，10 条）

| # | 决策 | 依据 |
|---|------|------|
| 1 | 后台不占 `_SHELL_PROC_SEM`，独立 `_BG_SEM`（默认5） | 后台长驻会占满前台并发槽饿死前台 |
| 2 | 后台默认无超时；显式传 timeout 则生效 | opencode shell.ts:195 同款 |
| 3 | 仍过安全检查；后台只放行白名单级，中风险以上拒绝不弹窗 | [9]卡死治理教训 |
| 4 | 通知与唤醒**分离**（对齐 opencode resume 开关）：inject 是投递，wake 是续跑判定 | session.ts:323 `resume !== false` |
| 5 | 状态B 自动续跑（同 session 系统驱动发新任务），非桌面通知降级 | opencode wake-on-idle 实证（1.2 结论6） |
| 6 | notice_id 幂等 + 竞态守卫（活跃任务则改注入） | opencode notificationID reconcile + OmniAgent B-3 守卫 |
| 7 | 通知文本落库为 user message（带 system_notice 标记） | opencode synthetic 持久化投影（durable） |
| 8 | cancelled 不续跑 + 连带杀后台进程 | opencode interrupt 清 pendingWake 语义 |
| 9 | `shell()` 保持同步函数，后台逻辑独立 async 模块 | tool_retry_engine.py:239 禁改 async def |
| 10 | LLM 提示写明"可结束回答等自动唤醒，勿轮询" | opencode BACKGROUND_INSTRUCTION 同款 |

## 六、已知边界（接受项）

- **长驻后台占满并发名额**：dev server 类命令永不结束，名额生命周期=后台命令生命周期（对齐前台 `_SHELL_PROC_SEM` 语义）→ 占满即明确失败并提示"后台并发已达上限"；名额数可配置（默认5），属容量管理非缺陷
- **服务重启**：内存注册表/等待协程丢失，后台进程成孤儿 → 启动时清理临时输出目录；结果文件在磁盘，bash_result 可查（opencode 有 claim 持久恢复，OmniAgent 首版不做，YAGNI）
- **通知延迟**：活跃任务的通知等当前工具完成才吸收 → 与 opencode 门铃语义一致
- **续跑链深度**：理论上可链式续跑（A后台完成→续跑→又发后台→又续跑）→ 幂等守卫保证每 shell_id 一次；opencode 同语义，不额外限深
- **多后台并发完成**：N 个后台命令同时完成且任务终态 → N 次续跑竞争，register_task 守卫使第一个续跑、其余改注入该续跑任务 → 天然串行化，无需额外处理

---

## 七、同会话串行语义与前端的处理（修订③，回答两个关键问题）

### 7.1 问题一：后台 shell 完成时，同会话两种情况如何执行？并行还是等待？

**先实证 opencode：同会话也是严格串行，无并行任务**。run-coordinator.ts:66 `executions = new Map<Key, Execution>()`——**每个 session key 只允许存在一个 execution**；wake 落在活跃 execution 上时只置 `pendingWake` 门铃（L134-137），等当前 drain 结束再 drain 一次，**绝不 start 第二个并行 execution**。opencode 的"并行"只存在于不同 session 之间（Map 不同 key）。

**OmniAgent 同构**：register_task 锁内同会话活跃任务互斥守卫（task_registry.py，B-3 TOCTOU 守卫，"同会话任务必须串行"），新消息遇活跃任务一律改道注入。两系统语义一致，**无需引入并行任务**。

**两种情况的完整处理**（shell_background 注册表记录 task_id + session_id，完成时按此判定）：

| 情况 | 判定 | 处理 | 并行/等待语义 |
|------|------|------|--------------|
| **情况1：无活跃任务**（原任务已终态，用户也没发新消息） | running_tasks 中该 session 无 running/paused 任务 | `resume_session_with_notice` 自动续跑 → 新任务成为该 session 唯一活跃任务 | 串行：续跑任务独占会话 |
| **情况2：有新实时任务在执行**（用户在原任务结束后又发了新消息，任务2 正在跑） | register_task 守卫返回占位 tid | **注入任务2 的 inbox**（inject_system_notice(占位tid, text)），等任务2 当前工具跑完、下一轮 LLM 调用前被 `_absorb_inbox` 吸收 | **等待不并行**：通知排队进任务2 上下文，任务2 的 LLM 在下一轮看到"任务1 的后台命令已完成"，自主决定处理（同会话历史含任务1 的 shell_id/output_file，可关联） |

- 情况2 不是边缘竞态，是**串行设计下的正常排队路径**
- 情况2 中若任务2 也终态了而通知还没被吸收（inbox 消息随任务 cleanup 转 orphan，drain_inbox 找回路径保证不丢）→ orphan 机制兜底，下次该 session 有任务时吸收；若长期无任务，bash_result 可查 + 桌面 notify 可选提醒
- **多后台同时完成且无活跃任务**：N 个通知各自触发 resume → 第一个成功，其余被守卫改道注入第一个续跑任务 → 天然串行合并，无需额外队列

### 7.2 问题二：前端"左右结构"（左任务清单+右流水线），系统通知如何显示？

**先实证 OmniAgent 前端结构**（frontend/src/features/chat）：左栏 TaskListPanel（任务清单列表）+ 右栏 RightViewer（当前任务流水线 PipelineRenderer），**不是聊天气泡流**。若把后台完成通知当普通 user message 渲染，会凭空出现一条"用户没说过的话"——必须与展示解耦。

**opencode 的解法（实证）**：synthetic 在 DB 是独立消息类型（type="synthetic"），TUI 显示为 `[Synthetic context]` 标签条目（recent-text.ts:57），**与 user 消息视觉区分**；只在喂给 LLM 时转 user role（to-llm-message.ts:276）。即：**存储类型区分 → 展示区分 → LLM 角色统一**，三者解耦。

**OmniAgent 落地（同哲学，复用现役机制）**：

| 层 | 处理 | 复用现役组件 |
|----|------|------------|
| **存储层** | 通知文本落库 user message，带 `system_notice=1` 标记（chat_user_message 加标记列或复用现有 meta 字段），**不冒充真实用户消息**；状态A/A'/B 三路径统一先落库再投递（inject_system_notice 内部落库拿真实 uid），对齐 opencode synthetic 双写 | storage.insert_user_message |
| **LLM 层** | history_loader 读到 system_notice 标记 → 照常转 user role 进上下文（对齐 opencode to-llm-message） | message_builder 既有 user 消息路径 |
| **前端-历史** | 历史加载遇 system_notice 标记 → **不渲染为用户气泡**，渲染为居中灰色系统通知条（"⚙ 后台命令已完成 · shell_xxx · 退出码0"） | 前端新增一个通知条渲染分支 |
| **前端-实时** | 续跑任务作为**新任务出现在左栏任务清单**（与用户发起的任务同款展示，可加"自动续跑"小徽标区分）；右栏流水线正常渲染该任务执行 | TaskListPanel/RightViewer 零结构改动 |
| **实时通知帧** | 任务内注入路径（情况2）复用现役 MetaStep notice 事件（kind="bg_shell_done"），在任务2 的流水线中显示一条通知行 | react_step notice/MetaStep 现役机制（同 trimming 通知） |

**结论**：通知的"展示形态"与"LLM 语义"完全解耦——LLM 眼里是 user role 消息（opencode 同款），用户眼里是系统通知条+新任务卡片（不冒充用户发言），前端左右结构零破坏。


---

## 八、详细设计（基于本地最新代码，逐文件代码清单）

> 代码基线：master@06d62ffd6。所有 diff 均以现役代码为锚点；新文件给完整代码，修改文件给精确 diff。
> 改动总览：后端 8 文件（3 新增 + 5 修改）、前端 2 文件（1 修改 + 1 内部新增渲染分支）、配置 2 项。

| # | 文件 | 类型 | 内容 |
|---|------|------|------|
| 8.1 | `backend/app/tools/fundamental/shell_background.py` | **新增** | 后台执行模块（注册表/信号量/等待通知协程） |
| 8.2 | `backend/app/tools/fundamental/execute_shell_command.py` | 修改 | shell() 加 background 参数与分支 |
| 8.3 | `backend/app/tools/fundamental/fundamental_schema.py` | 修改 | ShellInput 加 background 字段 |
| 8.4 | `backend/app/tools/fundamental/bash_result.py` | **新增** | bash_result 查询工具实现 |
| 8.5 | `backend/app/tools/fundamental/fundamental_register.py` | 修改 | 注册 bash_result |
| 8.6 | `backend/app/services/task/task_registry.py` | 修改 | 新增 inject_system_notice + cleanup 连带杀挂钩 |
| 8.7 | `backend/app/services/chat/stream_orchestrator.py` | 修改 | 抽取建任务核心段 + resume_session_with_notice |
| 8.8 | `backend/app/services/agent/steps/__init__.py` | 修改 | NOTICE_KINDS 补 bg_shell_done |
| 8.9 | `backend/app/config` 配置项 | 修改 | tuning.shell_max_background / shell_bg_log_max_mb |
| 8.10 | `frontend/.../TaskListPanel.tsx` | 修改 | system_notice 通知条渲染 + 自动续跑徽标（**含前端**） |

### 8.1 新增 `backend/app/tools/fundamental/shell_background.py`（完整代码）

```python
# -*- coding: utf-8 -*-
# 2026-11-13 商量 - 新建: bash 后台执行模块(设计文档[33]第8章)。非阻塞 Popen + 输出重定向
#   临时文件 + 主循环 run_coroutine_threadsafe 提交等待协程 + 完成通知唤醒(注入/续跑/杀进程三分叉)
# 编辑历史:
# (初版)
"""
S: shell_background — bash 工具后台执行支撑

职责(SRP): 只管"后台进程生命周期 + 完成后通知唤醒路由"; 通知判定逻辑在
_notify_and_wake(session级两级判定), 续跑入口在编排层 resume_session_with_notice。
shell() 保持同步函数(铁律, tool_retry_engine.py:239), 本模块异步部分经
run_coroutine_threadsafe 提交主事件循环执行。
"""
import asyncio
import os
import subprocess
import threading
import time
import uuid
from concurrent.futures import Future
from typing import Any, Dict, Optional

from app.config import get_config
from app.logger import logger
from app.tools.tool_response import build_success, build_error
from app.tools.tool_constants import ERR_SHELL_EXCEPTION

# ── 全局态 ──────────────────────────────────────────────
_BG_REGISTRY: Dict[str, dict] = {}   # {shell_id: {proc, output_file, task_id, command, shell_type, status, started_at, notice_id}}
_BG_LOCK = threading.Lock()          # 注册表读写锁(工作线程注册 vs 主循环协程更新)
_BG_TASKS: set = set()               # Future 强引用集合, done 回调 discard 防GC(仿 agent_runner._background_tasks)
_MAIN_LOOP: Optional[asyncio.AbstractEventLoop] = None  # 启动时缓存(main.py 启动钩子调 set_main_loop)

_BG_MAX = int(get_config().get("tuning.concurrency.shell_max_background", 5))
_BG_SEM = threading.BoundedSemaphore(_BG_MAX)
_BG_LOG_MAX_MB = int(get_config().get("tuning.shell_bg_log_max_mb", 50))
_BG_RESULT_RETAIN_HOURS = int(get_config().get("tuning.shell_bg_result_retain_hours", 24))


def set_main_loop(loop: asyncio.AbstractEventLoop) -> None:
    """main.py 启动时缓存主事件循环引用(供工作线程 run_coroutine_threadsafe 提交)"""
    global _MAIN_LOOP
    _MAIN_LOOP = loop


def _new_shell_id() -> str:
    return f"bgsh_{uuid.uuid4().hex[:12]}"


def _bg_output_dir() -> str:
    d = os.path.join(os.environ.get("TEMP", "."), "omni_bg_shell")
    os.makedirs(d, exist_ok=True)
    return d


def run_shell_background(command: str, shell_type: str, cwd: Optional[str],
                          task_id: str, cmd_short: str,
                          popen_factory) -> Dict[str, Any]:
    """启动后台命令并立即返回。popen_factory: 由调用方注入(Popen 构造, 复用 shell() 各
    shell_type 的启动参数装配, 避免本模块重复实现四种 shell 的命令行拼装 DRY)。
    返回 build_success 标准格式, data={shell_id, output_file, status:"running"}。"""
    if _MAIN_LOOP is None:
        return build_error(data={}, llm_data={
            "summary": f"执行Shell命令{cmd_short}，失败",
            "action": {"tool": "bash", "tool_zh": "执行", "params": {"command": command, "background": True}},
            "status": {"exec_code": "error", "message": "失败", "code": ERR_SHELL_EXCEPTION,
                       "detail": "主事件循环未初始化, 后台执行不可用", "hint": "服务启动中, 请稍后重试"},
            "duration_ms": 0, "metrics": {}})
    if not _BG_SEM.acquire(blocking=False):
        return build_error(data={}, llm_data={
            "summary": f"执行Shell命令{cmd_short}，失败",
            "action": {"tool": "bash", "tool_zh": "执行", "params": {"command": command, "background": True}},
            "status": {"exec_code": "error", "message": "失败", "code": ERR_SHELL_EXCEPTION,
                       "detail": f"后台并发已达上限({_BG_MAX}), 请等待现有后台命令结束",
                       "hint": "属容量管理, 非命令本身错误"},
            "duration_ms": 0, "metrics": {}})
    try:
        shell_id = _new_shell_id()
        output_file = os.path.join(_bg_output_dir(), f"{shell_id}.log")
        # stdout/stderr 合流写文件(2>&1 语义, 与 opencode info.file 单文件同构);
        # 轮转由 _rotate_check 在读取/通知时执行(见 bash_result), 进程写端只管写
        with open(output_file, "ab") as _f:  # 预创建, 防 Popen 竞态
            pass
        proc = popen_factory(command, cwd, output_file)  # stdout=open(file,'ab'), stderr=STDOUT
        if proc is None:
            _BG_SEM.release()
            return build_error(data={}, llm_data={
                "summary": f"执行Shell命令{cmd_short}，失败",
                "action": {"tool": "bash", "tool_zh": "执行", "params": {"command": command, "background": True}},
                "status": {"exec_code": "error", "message": "失败", "code": ERR_SHELL_EXCEPTION,
                           "detail": "后台进程启动失败", "hint": "请检查命令与解释器"},
                "duration_ms": 0, "metrics": {}})
        with _BG_LOCK:
            _BG_REGISTRY[shell_id] = {
                "proc": proc, "output_file": output_file, "task_id": task_id,
                "command": command, "shell_type": shell_type,
                "status": "running", "started_at": time.time(),
                "notice_id": f"{shell_id}_done",   # 幂等键(同 shell_id 恒定, 续跑只许一次)
            }
        # 跨线程提交: shell() 在 _SHELL_EXECUTOR 工作线程执行, 线程内无事件循环,
        # asyncio.create_task 直接调用必炸 → run_coroutine_threadsafe 提交主循环
        fut = asyncio.run_coroutine_threadsafe(_wait_and_notify(shell_id), _MAIN_LOOP)
        _BG_TASKS.add(fut)
        fut.add_done_callback(_BG_TASKS.discard)
        return build_success(
            data={"shell_id": shell_id, "output_file": output_file, "status": "running"},
            llm_data={
                "summary": f"执行Shell命令{cmd_short}，已转后台",
                "action": {"tool": "bash", "tool_zh": "执行",
                           "params": {"command": command, "background": True}},
                "status": {"exec_code": "success", "message": "已转后台运行",
                           "code": "", "detail": "",
                           "hint": "完成时会自动收到系统通知并自动继续处理, 不要轮询等待; "
                                   "期间可继续其他工作或直接结束回答"},
                "duration_ms": 0,
                "metrics": {"shell_id": {"value": shell_id, "text": f"后台ID {shell_id}"},
                            "output_file": {"value": output_file, "text": "输出文件"}}})
    except Exception as e:
        _BG_SEM.release()
        logger.error(f"[bg_shell] 后台启动异常: {e}", exc_info=True)
        return build_error(data={}, llm_data={
            "summary": f"执行Shell命令{cmd_short}，失败",
            "action": {"tool": "bash", "tool_zh": "执行", "params": {"command": command, "background": True}},
            "status": {"exec_code": "error", "message": "失败", "code": ERR_SHELL_EXCEPTION,
                       "detail": str(e), "hint": "后台启动异常"},
            "duration_ms": 0, "metrics": {}})


async def _wait_and_notify(shell_id: str) -> None:
    """等待后台进程退出并路由通知(主事件循环协程)。
    进程等待经默认线程池 offload, 零占事件循环; 通知路由按 session 级两级判定(设计 3.1)。"""
    from app.services.task.task_registry import (
        has_active_task_in_session, inject_system_notice, get_task_session,
    )
    info = _BG_REGISTRY.get(shell_id)
    if not info:
        return
    proc: subprocess.Popen = info["proc"]
    loop = asyncio.get_running_loop()
    # 阻塞 wait 卸载线程池; 后台命令无超时(设计决策2), 显式 timeout 由 wait 参数承载
    timeout = info.get("timeout") or None
    try:
        rc = await loop.run_in_executor(None, lambda: proc.wait(timeout))
        status = "completed" if rc == 0 else "failed"
    except subprocess.TimeoutExpired:
        from app.utils.proc_utils import kill_process_tree
        kill_process_tree(proc)
        rc = proc.returncode if proc.returncode is not None else -1
        status = "failed"
    except Exception as e:
        logger.error(f"[bg_shell] 等待异常({shell_id}): {e}", exc_info=True)
        rc = -1
        status = "failed"

    with _BG_LOCK:
        info["status"] = status
        info["returncode"] = rc
        info["finished_at"] = time.time()
    _BG_SEM.release()

    # ── 通知文本(摘要+尾部输出, 对齐 opencode resultMessages) ──
    duration = int(info["finished_at"] - info["started_at"])
    tail = _read_output_tail(info["output_file"], 600)
    text = (f"[系统通知] 后台命令已完成(shell_id={shell_id}, 退出码{rc}, 耗时{duration}s)\n"
            f"命令: {info['command'][:200]}\n"
            f"输出文件: {info['output_file']}\n"
            f"输出尾部:\n{tail}")

    task_id = info["task_id"]
    try:
        # ── 三分叉路由(session 级两级判定, 设计 3.1) ──
        session_id = get_task_session(task_id)
        if session_id is None:
            logger.warning(f"[bg_shell] {shell_id} 无法反查 session(任务已清理), 通知降级落盘: {info['output_file']}")
            return
        active_tid = await has_active_task_in_session(session_id)
        if active_tid is not None:
            # 状态A/A': 原任务或同会话新任务活跃 → 注入 inbox(先落库拿真实uid)
            ok = await inject_system_notice(active_tid, text)
            if not ok:
                logger.warning(f"[bg_shell] {shell_id} 注入失败(inbox满/终态窗口), 降级落盘: {info['output_file']}")
        else:
            # 状态B: 同会话无活跃任务 → 自动续跑(wake-on-idle)
            from app.services.chat.stream_orchestrator import resume_session_with_notice
            ok = await resume_session_with_notice(
                session_id, text, notice_id=info["notice_id"], source_task_id=task_id)
            if not ok:
                logger.warning(f"[bg_shell] {shell_id} 续跑发起失败, 降级落盘: {info['output_file']}")
    except Exception as e:
        logger.error(f"[bg_shell] 通知路由异常({shell_id}): {e}", exc_info=True)
    finally:
        _schedule_result_cleanup(shell_id)


def _read_output_tail(path: str, max_chars: int) -> str:
    """读输出文件尾部(轮转感知: 读当前份; 超限文件读末尾 max_chars)"""
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as f:
            if size > max_chars * 4:
                f.seek(-max_chars * 4, os.SEEK_END)
            data = f.read()
        return data.decode("utf-8", errors="replace")[-max_chars:]
    except OSError:
        return "(输出文件读取失败)"


def _rotate_check(shell_id: str) -> None:
    """轮转检查: 输出文件超 _BG_LOG_MAX_MB 时轮转(当前→.1, 旧.1→.2 删除)。
    后台进程持写端打开旧文件继续写(Windows 句柄语义), 轮转后新读取从 .1 取尾部。"""
    info = _BG_REGISTRY.get(shell_id)
    if not info:
        return
    path = info["output_file"]
    try:
        if os.path.getsize(path) > _BG_LOG_MAX_MB * 1024 * 1024:
            p1 = path + ".1"
            if os.path.exists(p1):
                os.remove(path + ".2")
                os.rename(p1, path + ".2")
            os.rename(path, p1)
            # 不重开写端: 进程仍持旧句柄, 输出续写 .1; bash_result 合并 .2+.1+当前
    except OSError:
        pass


def get_bg_info(shell_id: str) -> Optional[dict]:
    with _BG_LOCK:
        return dict(_BG_REGISTRY.get(shell_id) or {})


def kill_background_by_task(task_id: str) -> int:
    """任务 cancelled 连带杀: 终结本 task_id 名下全部后台进程(设计 3.4)。返回杀掉数。"""
    from app.utils.proc_utils import kill_process_tree
    n = 0
    with _BG_LOCK:
        targets = [sid for sid, i in _BG_REGISTRY.items() if i["task_id"] == task_id]
    for sid in targets:
        info = _BG_REGISTRY.get(sid)
        if info and info["status"] == "running":
            try:
                kill_process_tree(info["proc"])
                info["status"] = "killed"
                _BG_SEM.release()
                n += 1
                logger.info(f"[bg_shell] 任务取消连带杀后台进程: {sid} (task={task_id})")
            except Exception as e:
                logger.warning(f"[bg_shell] 连带杀失败({sid}): {e}")
    return n


def _schedule_result_cleanup(shell_id: str) -> None:
    """结果文件延迟清理(默认24h)。KISS: 惰性清理——新后台命令启动时顺带扫过期项,
    不起定时器(YAGNI)。"""
    now = time.time()
    with _BG_LOCK:
        expired = [sid for sid, i in _BG_REGISTRY.items()
                   if i.get("status") not in ("running", None)
                   and now - i.get("finished_at", now) > _BG_RESULT_RETAIN_HOURS * 3600]
    for sid in expired:
        info = _BG_REGISTRY.pop(sid, None)
        if info:
            for suf in ("", ".1", ".2"):
                try:
                    os.remove(info["output_file"] + suf)
                except OSError:
                    pass
```

**要点**：
- `popen_factory` 由 shell() 注入——四种 shell_type 的命令行装配（pwsh/-Command、bat、bash -l -c）留在 execute_shell_command.py 单点（DRY），本模块只管生命周期。
- `_MAIN_LOOP` 由 main.py 启动钩子调 `set_main_loop(asyncio.get_running_loop())` 缓存。
- 幂等键 `notice_id` 在注册时即固化（`{shell_id}_done`），续跑入口据此防重。

### 8.2 修改 `backend/app/tools/fundamental/execute_shell_command.py`（diff）

**① 头部编辑历史追加 + import**：

```diff
+# 2026-11-13 商量 - 新增 background 参数: 后台运行命令并立即返回(设计文档[33])。
+#   后台分支复用本文件全部前置(校验/预处理/三路检测/语法修复/安全检查), 仅执行段
+#   改走 shell_background.run_shell_background(popen_factory 注入四种 shell 的启动装配, DRY);
+#   前台路径零改动。安全检查: 后台分支中风险以上一律拒绝不弹窗([9]卡死治理教训)。
 import uuid
+from app.tools.fundamental import shell_background
+from app.tools.context import get_current_task_id   # 已有 import, 此处仅示意依赖关系
```

**② shell() 签名与 docstring**（L1047）：

```diff
 def shell(
     command: str, shell_type: Literal["ps7", "ps5", "cmd", "bash", None] = "ps7",
     timeout: int = 60, cwd: Optional[str] = None,
     success_codes: Optional[list[int]] = None,
+    background: bool = False,
 ) -> Dict[str, Any]:
```

**③ 安全检查段（L1183-1193 之后）追加后台安全收紧**：

```diff
     safety = check_shell_danger_command(processed_command, shell_type) or \
         check_shell_risk_command(processed_command, shell_type)
     if safety:
         d = int((_time_mod.perf_counter() - t0) * 1000)
         if safety.blocked:
             ...  # 原样不动
         if safety.needs_confirm:
             logger.warning(...)  # 原样不动
+    # ── 阶段 2.5【后台专属】: 安全收紧 — 商量 2026-11-13 ──
+    #  后台命令天然长驻/高影响: 中风险(需确认)命令在无值守场景弹窗 120s 挂死([9]教训),
+    #  故后台分支对 needs_confirm 一律拒绝(仅白名单级放行), 不弹窗。
+    if background and safety and safety.needs_confirm:
+        d = int((_time_mod.perf_counter() - t0) * 1000)
+        llm = _build_execute_shell_command_llm_data("error", d, processed_command, -1,
+            shell_type, ERR_SHELL_INJECTION, f"后台命令安全等级不足: {safety.message}",
+            timeout=timeout, cwd=cwd or "",
+            hint="该命令需人工确认, 不支持后台运行; 请去掉 background 参数前台执行",
+            cmd_short=cmd_short)
+        return build_error(data={}, llm_data=llm)
```

**④ 执行段入口（L1198 `_slot_acquired = False` 之前）插入后台分支**：

```diff
     # ── 阶段 3【PS/CMD分支】: 执行 ──
     ...
-    _slot_acquired = False
+    # ── 阶段 2.9【后台专属】: 转后台执行并立即返回 — 商量 2026-11-13 ──
+    #  不占 _SHELL_PROC_SEM(前台并发槽), 不进 drain_until_exit(阻塞读);
+    #  timeout 语义: 后台默认无超时, 显式传则生效(对齐 opencode shell.ts:195)
+    if background:
+        _task_id = get_current_task_id() or ""
+        def _popen_factory(cmd: str, workdir: Optional[str], outfile: str):
+            """四种 shell 的后台启动装配(与前台同款命令行, stdout/stderr 改指 outfile)"""
+            try:
+                _out = open(outfile, "ab")
+                if shell_type in ("ps7", "ps5"):
+                    exe = shutil.which("pwsh.exe" if shell_type == "ps7" else "powershell.exe") \
+                          or shutil.which("powershell.exe" if shell_type == "ps7" else "pwsh.exe")
+                    return subprocess.Popen([exe, "-NoProfile", "-Command", cmd],
+                        stdout=_out, stderr=subprocess.STDOUT, cwd=workdir, env=_sanitize_env())
+                if shell_type == "cmd":
+                    bat_encoding = locale.getpreferredencoding()
+                    bat_fd, bat_path = tempfile.mkstemp(suffix='.bat', text=True)
+                    with os.fdopen(bat_fd, 'w', encoding=bat_encoding, errors='replace') as f:
+                        f.write('@echo off\r\n' + cmd + '\r\n' + 'exit /b %errorlevel%\r\n')
+                    return subprocess.Popen(f'"{bat_path}"', shell=True,
+                        stdout=_out, stderr=subprocess.STDOUT, cwd=workdir, env=_sanitize_env())
+                bash_exe = _find_bash()
+                if not bash_exe:
+                    logger.error("[bg_shell] bash 解释器未找到")
+                    return None
+                return subprocess.Popen([bash_exe, "-l", "-c", cmd],
+                    stdout=_out, stderr=subprocess.STDOUT, cwd=workdir, env=_sanitize_env())
+            except Exception as e:
+                logger.error(f"[bg_shell] Popen 装配失败: {e}", exc_info=True)
+                return None
+        result = shell_background.run_shell_background(
+            processed_command, shell_type, cwd, _task_id, cmd_short, _popen_factory)
+        if result is not None and result.get("llm_data"):
+            result["llm_data"]["action"]["params"]["timeout"] = timeout  # 留痕供历史核对
+        return result
+    _slot_acquired = False
```

> 注：`result["llm_data"]` 结构以 tool_response 实际返回键为准（build_success 的 llm_data 直通），实施时按 build_success 返回结构调整此行。

### 8.3 修改 `backend/app/tools/fundamental/fundamental_schema.py`（diff）

```diff
 class ShellInput(BaseModel):
     ...
     success_codes: Optional[list[int]] = Field(
         default=None,
         description="..."
     )
+    background: bool = Field(
+        default=False,
+        description="后台运行命令并立即返回(适合dev server/长构建)。"
+                    "无需在命令末尾加&。完成时会自动收到系统通知并自动继续处理,"
+                    "不要轮询等待; 期间可继续其他工作或直接结束回答。"
+                    "后台命令默认无超时, 显式传timeout则生效。"
+    )
```

> ShellInput docstring【返回值结构】段同步补一行：`background=true 时: data={shell_id, output_file, status}`。

---

*编写人: 商量 — 2026-11-13*

### 8.4 新增 `backend/app/tools/fundamental/bash_result.py`（完整代码）

```python
# -*- coding: utf-8 -*-
# 2026-11-13 商量 - 新建: bash_result 后台命令结果查询工具(设计文档[33]第8章)。
#   按 shell_id 或 output_file 查后台命令状态+输出; 通知丢失兜底 + 中途读输出(非轮询)。
# 编辑历史:
# (初版)
"""
S: bash_result — 查询后台 Shell 命令状态与输出

支持两种查询键: shell_id(注册表内存态, 服务重启后失效) 或 output_file(磁盘文件, 恒可查)。
输出合并轮转份(.2+.1+当前)后过 _truncate_shell_field 截断(与前台同款, LLM 侧恒有界)。
"""
import os
from typing import Any, Dict, Optional

from app.logger import logger
from app.tools.fundamental import shell_background
from app.tools.fundamental.execute_shell_command import _truncate_shell_field
from app.tools.tool_constants import (
    ERR_PARAMETER_EMPTY, ERR_PARAMETER_INVALID,
    SHELL_OUTLIMIT_STDOUT_MAX_CHARS,
)
from app.tools.tool_response import build_success, build_error


def bash_result(
    shell_id: Optional[str] = None,
    output_file: Optional[str] = None,
) -> Dict[str, Any]:
    """查询后台 Shell 命令状态与输出

    参数:
        shell_id:    后台命令ID(bash background=true 返回值中的 shell_id)
        output_file: 输出文件路径(shell_id 注册表失效时按文件直查, 服务重启后仍可用)

    返回:
        data: {status(running/completed/failed/killed/unknown), command, returncode,
               duration_s, stdout(截断后)}
    """
    # ── 参数校验: 二选一必填 ──
    if not shell_id and not output_file:
        return build_error(data={}, llm_data={
            "summary": "查询后台命令结果，失败",
            "action": {"tool": "bash_result", "tool_zh": "查询", "params": {}},
            "status": {"exec_code": "error", "message": "失败", "code": ERR_PARAMETER_EMPTY,
                       "detail": "shell_id 与 output_file 至少提供一个",
                       "hint": "请从 bash background=true 的返回值或对话历史中取 shell_id"},
            "duration_ms": 0, "metrics": {}})

    # ── 路径1: shell_id 查注册表(含进程存活态) ──
    if shell_id:
        info = shell_background.get_bg_info(shell_id)
        if not info:
            # 注册表无此 id: 服务重启/已过期清理 → 若同目录文件在, 引导按文件查
            _guess = os.path.join(shell_background._bg_output_dir(), f"{shell_id}.log")
            if os.path.exists(_guess):
                info = {"output_file": _guess, "status": "unknown", "command": "", "task_id": ""}
            else:
                return build_error(data={}, llm_data={
                    "summary": f"查询后台命令{shell_id}，失败",
                    "action": {"tool": "bash_result", "tool_zh": "查询", "params": {"shell_id": shell_id}},
                    "status": {"exec_code": "error", "message": "失败", "code": ERR_PARAMETER_INVALID,
                               "detail": f"未找到后台命令 {shell_id}(服务重启或结果已过期清理)",
                               "hint": "请检查 shell_id 是否正确; 结果文件过期后不可恢复"},
                    "duration_ms": 0, "metrics": {}})

    # ── 路径2: output_file 直查(磁盘文件, 重启后可用) ──
    else:
        if not os.path.isfile(output_file):
            return build_error(data={}, llm_data={
                "summary": "查询后台命令结果，失败",
                "action": {"tool": "bash_result", "tool_zh": "查询", "params": {"output_file": output_file}},
                "status": {"exec_code": "error", "message": "失败", "code": ERR_PARAMETER_INVALID,
                           "detail": f"输出文件不存在: {output_file}",
                           "hint": "请核对文件路径"},
                "duration_ms": 0, "metrics": {}})
        info = {"output_file": output_file, "status": "unknown", "command": "", "task_id": ""}

    # ── 读输出(合并轮转份 .2 + .1 + 当前) ──
    path = info["output_file"]
    parts = []
    for suffix in (".2", ".1", ""):
        p = path + suffix
        if os.path.isfile(p):
            try:
                with open(p, "rb") as f:
                    parts.append(f.read())
            except OSError as e:
                logger.warning(f"[bash_result] 读输出失败({p}): {e}")
    raw = b"".join(parts)
    stdout_str = raw.decode("utf-8", errors="replace")
    stdout_str, _trunc = _truncate_shell_field(stdout_str, SHELL_OUTLIMIT_STDOUT_MAX_CHARS)

    duration_s = 0
    if "started_at" in info and "finished_at" in info:
        duration_s = int(info["finished_at"] - info["started_at"])

    data: Dict[str, Any] = {
        "status": info.get("status", "unknown"),
        "command": info.get("command", ""),
        "returncode": info.get("returncode"),
        "duration_s": duration_s,
        "stdout": stdout_str,
    }
    if _trunc:
        data["_truncated"] = True
    return build_success(
        data=data,
        llm_data={
            "summary": f"查询后台命令{shell_id or os.path.basename(path)}，成功",
            "action": {"tool": "bash_result", "tool_zh": "查询",
                       "params": {"shell_id": shell_id or "", "output_file": output_file or ""}},
            "status": {"exec_code": "success", "message": "成功", "code": "", "detail": "", "hint": ""},
            "duration_ms": 0,
            "metrics": {"status": {"value": data["status"], "text": f"状态 {data['status']}"},
                        "output_len": {"value": len(stdout_str), "text": f"输出{len(stdout_str)}字符"}}})
```

**Schema**（fundamental_schema.py 追加）：

```python
class BashResultInput(BaseModel):
    shell_id: Optional[str] = Field(
        default=None, description="后台命令ID(bash background=true 返回的 shell_id)"
    )
    output_file: Optional[str] = Field(
        default=None, description="输出文件路径(服务重启后 shell_id 失效时按文件直查)"
    )
```

### 8.5 修改 `backend/app/tools/fundamental/fundamental_register.py`（diff）

```diff
 from app.tools.fundamental.execute_shell_command import shell
+from app.tools.fundamental.bash_result import bash_result
 from app.tools.fundamental.fundamental_schema import (
+    BashResultInput,
     SendNotificationInput,
     ShellInput,
     ...
 )
 
 FUNDAMENTAL_TOOL_DEPENDENCIES = {
     ...
     "bash": [],  # 使用内置库
+    "bash_result": [],  # 使用内置库
 }
 
 FUNDAMENTAL_TOOL_DESCRIPTIONS = {
     ...
+    "bash_result": """查询后台Shell命令(bash background=true)的状态与输出。适用场景:后台命令完成通知丢失时取回结果、或中途查看后台命令当前输出。""",
 }
 
 FUNDAMENTAL_TOOL_EXAMPLES = {
     ...
+    "bash_result": [
+        {"shell_id": "bgsh_ab12cd34ef56"},
+        {"output_file": "C:\\Users\\...\\omni_bg_shell\\bgsh_ab12cd34ef56.log"},
+    ],
 }
 
     tool_methods = {
         ...
         "bash": shell,
+        "bash_result": bash_result,
     }
 
     TOOL_INPUT_MODELS = {
         ...
         "bash": ShellInput,
+        "bash_result": BashResultInput,
     }
```

> 头部 docstring "5个工具" 改 "6个工具"，清单补 bash_result 一行。

### 8.6 修改 `backend/app/services/task/task_registry.py`（diff）

**① 新增 `get_task_session` + `inject_system_notice`**（置于 inject_message_to_task 之后）：

```diff
 async def inject_message_to_task(task_id: str, content: str, user_message_id: int) -> bool:
     ...  # 原样不动


+def get_task_session(task_id: str) -> Optional[str]:
+    """反查任务的 session_id(后台 shell 完成通知路由用) — 商量 2026-11-13
+    任务已终态被 cleanup 删除时返回 None(由调用方降级落盘)。
+    同步函数: running_tasks 读走 _BG_REGISTRY 工作线程/主循环两处, 锁内快照读线程安全。"""
+    # 注: running_tasks_lock 是 asyncio.Lock, 此处不能同步持锁;
+    # dict 读在 CPython 下原子, cleanup 删除与读并发最坏返回 None, 语义安全
+    _t = running_tasks.get(task_id)
+    return _t.get("session_id") if _t else None
+
+
+async def inject_system_notice(task_id: str, content: str) -> bool:
+    """系统通知注入(后台 shell 完成通知等, 设计文档[33]) — 商量 2026-11-13
+    与 inject_message_to_task 并列同一 inbox; 不放宽其 uid>0 防御(防重落库红线)。
+    通知恒先落库拿真实 uid 再投递(对齐 opencode synthetic 双写):
+      ① storage.insert_user_message 落 chat_user_message(system_notice 标记见下)
+      ② bind_message_to_task 执行期归属(与用户插话同款)
+      ③ 投 (content, uid) 元组; _absorb_inbox 吸收时锚演进正常, 零改动
+    落库失败(DB 异常)不投递, 返回 False 由调用方降级(结果文件仍在)。
+    system_notice 标记: content 以 [系统通知] 前缀承载(零 DDL, 前端按前缀渲染,
+    历史回放/LLM 上下文均可见来源); 如后续需结构化标记再议加列, 首版 KISS。"""
+    from app.db import db
+    from app.services.chat import storage
+    async with running_tasks_lock:
+        _t = running_tasks.get(task_id)
+        if not _t or _t.get("status") not in ("running", "paused"):
+            return False
+        session_id = _t.get("session_id")
+        _q = _t.get("_inbox")
+        if _q is None or not session_id:
+            return False
+    try:
+        def _persist(conn):
+            uid = storage.insert_user_message(conn, session_id=session_id, content=content)
+            storage.bind_message_to_task(conn, uid, task_id)
+            return uid
+        uid = await db.atxn("chat", _persist, retry_locked=3)
+    except Exception as e:
+        logger.error(f"[TaskRegistry] 系统通知落库失败(task={task_id}): {e}", exc_info=True)
+        return False
+    if uid <= 0:
+        return False
+    async with running_tasks_lock:
+        _t = running_tasks.get(task_id)
+        if not _t or _t.get("status") not in ("running", "paused"):
+            return False   # 落库成功但任务恰终态: 消息已在历史, 下轮对话可见, 不丢
+        _q = _t.get("_inbox")
+        if _q is None:
+            return False
+        try:
+            _q.put_nowait((content, uid))
+        except asyncio.QueueFull:
+            logger.warning(f"[TaskRegistry] 系统通知注入被拒(inbox满, task={task_id})")
+            return False
+    logger.info(f"[TaskRegistry] 系统通知已注入(task={task_id}, uid={uid})")
+    return True
```

> 设计说明：锁外落库（db.atxn 耗时操作不持 running_tasks_lock，防锁内 await 长占）；投递前二次校验任务状态（落库窗口任务可能终态——消息已持久化在会话历史，用户下次发话 LLM 可见，语义不丢）。

**② cleanup_task 连带杀挂钩**（cancel 路径）：

```diff
 async def cleanup_task(task_id: str) -> bool:
     """清理非cancelled任务,返回True=已清理,False=保留(cancelled记录)"""
+    # 2026-11-13 商量: cancelled 任务连带杀名下后台 shell 进程(设计 3.4,
+    #   opencode interrupt 清 pendingWake 语义: 取消后不复活, 孤儿进程一并终结)
+    from app.tools.fundamental import shell_background
     async with running_tasks_lock:
         if task_id not in running_tasks:
             return False
         if running_tasks[task_id].get("status") != "cancelled":
             ...  # 原样不动
```

> 实施注意：kill 动作必须在锁外执行（kill_process_tree 可能阻塞），改为 cleanup_task 返回后由调用方（task_cleanup）调用 `shell_background.kill_background_by_task(task_id)`；task_registry 是数据层不持进程句柄操作（SRP）。即挂钩点实际放在 `task_registry.task_cleanup`（L377，编排收尾统一入口）：

```diff
 async def task_cleanup(task_id: str, llm_call_count: int = 0) -> None:
     """任务完成后清理"""
     ...
     cleaned = await cleanup_task(task_id)
+    # 2026-11-13 商量: 任务收尾连带清理名下后台 shell(取消→杀进程树; 正常终态→仅注销跟踪)
+    from app.tools.fundamental import shell_background
+    shell_background.kill_background_by_task(task_id)  # 内部只杀 status=running 项
     ...
```

### 8.7 修改 `backend/app/services/chat/stream_orchestrator.py`（diff）

**① 从编排 generator 抽取"建任务核心段"（SRP，用户路径与系统续跑路径共用）**：

现役 L1000-1061 段（_setup_task_db → allocate → file_persist → create_task(run_agent_in_background)）抽为：

```diff
+async def _create_and_launch_task(*, agent, session_id: str, task_id: str,
+                                   user_message_id: int, db_ops, state,
+                                   _task_start_time) -> tuple:
+    """建任务核心段: 落库任务行+分配ai_message+文件writer+起后台agent — 商量 2026-11-13
+    从编排 generator 抽取(SRP): 用户路径(chat_stream)与系统续跑路径
+    (resume_session_with_notice)共用同一建任务实现(DRY)。
+    返回 (ai_message_id, bg_task)。"""
+    _ai_message_id = None
+    from app.file_persist import SESSION_DIR_PREFIX, TASK_DIR_PREFIX
+    def _setup_task_db(conn):
+        db_ops.insert_task(conn)
+        _aid = allocate_and_insert_message(conn, session_id, task_id, user_message_id=user_message_id)
+        conn.execute("UPDATE chat_tasks SET ai_message_id=? WHERE task_id=?", (_aid, task_id))
+        conn.execute("UPDATE chat_tasks SET files_dir=? WHERE task_id=?",
+                     (f"files/{SESSION_DIR_PREFIX}{session_id}/{TASK_DIR_PREFIX}{task_id}/", task_id))
+        return _aid
+    _ai_message_id = await db.atxn("chat", _setup_task_db, retry_locked=3)
+    try:
+        from app.file_persist import create_task_writer
+        from app.utils.time_utils import get_local_iso_timestamp
+        _mr = getattr(getattr(agent, "llm_client", None), "llm_model", None)
+        agent.file_persist = create_task_writer(
+            session_id=session_id, task_id=task_id, ai_message_id=_ai_message_id,
+            start_time_iso=get_local_iso_timestamp(),
+            model=(_mr.model_dump(exclude_none=True) if hasattr(_mr, "model_dump") else None))
+    except Exception as _writer_e:
+        logger.warning(f"[chat] 任务文件writer创建失败(task={task_id}): {_writer_e}")
+    bg_task = asyncio.create_task(run_agent_in_background(
+        agent, task_id, user_input, None, session_id, state, _task_start_time,
+        db_ops=db_ops, ai_message_id=_ai_message_id))
+    _agent_tasks.add(bg_task)
+    bg_task.add_done_callback(_agent_tasks.discard)
+    await set_agent_task(task_id, bg_task)
+    return _ai_message_id, bg_task
```

（原 generator 内对应段替换为对 _create_and_launch_task 的调用，参数原样透传；user_input 经参数传入。）

**② 新增 `resume_session_with_notice`（模块级函数）**：

```diff
+_RESUMED_NOTICES: set = set()   # notice_id 幂等集合(内存态; 服务重启后集合清空,
+#   但 shell_id 注册表同样清空, 不会重放, 语义自洽)
+_RESUMED_LOCK = asyncio.Lock()
+
+
+async def resume_session_with_notice(session_id: str, notice_text: str,
+                                      notice_id: str, source_task_id: str = "") -> bool:
+    """系统驱动续跑: 后台 shell 完成且同会话无活跃任务时, 自动开新一轮任务 — 商量 2026-11-13
+    对齐 opencode execution.wake 空闲语义(run-coordinator.ts:131 idle→start)。
+    流程: 幂等守卫 → 通知落库为 user message → 复用 _create_and_launch_task 建任务
+          → 事件全落 journal(stream_buffer 持久化), 不等待前端消费者
+          (复用"客户端断开静默返回, agent 后台继续"现役语义 L1069)。
+    返回 True=续跑任务已发起; False=占位改注入(由调用方执行)/幂等跳过/发起失败。"""
+    async with _RESUMED_LOCK:
+        if notice_id in _RESUMED_NOTICES:
+            return True   # 幂等: 该通知已触发过续跑(对齐 opencode notificationID reconcile)
+        _RESUMED_NOTICES.add(notice_id)
+    try:
+        # 1. 占位守卫: 同会话已有活跃任务(用户恰好刚发消息) → 不续跑, 返回 False
+        #    由调用方(shell_background)改道注入该活跃任务(状态A'路径)
+        if await has_active_task_in_session(session_id):
+            return False
+        # 2. 通知落库为 user message(真实 uid; 前端历史按 [系统通知] 前缀渲染,
+        #    LLM 上下文以 user role 进入, 对齐 opencode to-llm-message)
+        from app.db import db
+        from app.services.chat import storage
+        def _persist(conn):
+            uid = storage.insert_user_message(conn, session_id=session_id, content=notice_text)
+            return uid
+        uid = await db.atxn("chat", _persist, retry_locked=3)
+        # 3. 生成新 task_id + 建 buffer(journal 持久化, 前端经任务列表/journal 重连发现)
+        task_id = generate_task_id()   # 现役 id 生成入口(与编排层同源)
+        create_task_stream_buffer(task_id, session_id)   # journal_sink 挂接, 事件不丢
+        _reg = await register_task(task_id, session_id=session_id)
+        if _reg:   # 返回 str=同会话被占位(并发窗口) → 落库消息已在, 返回 False 改注入
+            return False
+        # 4. 装配 agent + 建任务核心段(与用户路径共用, DRY)
+        agent = build_agent_for_session(session_id, source_task_id=source_task_id,
+                                        trigger="bg_shell_resume")
+        await _create_and_launch_task(agent=agent, session_id=session_id, task_id=task_id,
+                                      user_message_id=uid, db_ops=..., state=...,
+                                      _task_start_time=time.time())
+        logger.info(f"[bg_resume] 续跑任务已发起(session={session_id}, task={task_id}, "
+                    f"notice={notice_id}, uid={uid})")
+        return True
+    except Exception as e:
+        logger.error(f"[bg_resume] 续跑发起失败(session={session_id}, notice={notice_id}): {e}",
+                     exc_info=True)
+        return False
```

> 实施注意：
> - `build_agent_for_session` / `generate_task_id` / `create_task_stream_buffer` / `db_ops` / `state` 均为编排层现役符号，抽取时按实际签名适配；`trigger="bg_shell_resume"` 供任务卡片显示"自动续跑"徽标（透传进 chat_tasks 或 stream_buffer meta，前端按此渲染）。
> - SSE 消费：run_agent_in_background 的产出全部经 stream_buffer 落 journal；前端 TaskListPanel 轮询/刷新发现新任务后走**现役 journal 重连回放**（after_seq 机制），零新帧类型。
> - 续跑任务的 user_input 传通知文本摘要（供任务列表卡片显示"后台命令已完成…"）。

### 8.8 修改 `backend/app/services/agent/steps/__init__.py`（diff）

```diff
 NOTICE_KINDS = frozenset({
     ...
+    "bg_shell_done",   # 2026-11-13 商量: 后台 shell 完成通知(注入吸收轮播报, 设计 7.2)
 })
```

> 播报点：`_absorb_inbox` 吸收到 uid 对应 content 含 `[系统通知]` 前缀时，经现役 `_emit_publish` 直发一条 `notice(kind="bg_shell_done", phase="done")`（与 trimming 通知同款形态，react_step.py L365-368 同模式），前端流水线显示通知行。实施时在 `_absorb_inbox` 的 `_merged` 构造后追加：

```diff
     _merged = "\n".join(_contents)
+    # 2026-11-13 商量: 系统通知吸收时播报 bg_shell_done notice(前端流水线通知行)
+    if any(c.startswith("[系统通知]") for c in _contents):
+        _notice_step = build_step_dict(None, "notice", "后台命令已完成，结果已并入本轮上下文")
+        _notice_step["kind"] = "bg_shell_done"; _notice_step["phase"] = "done"
+        await _publish(_notice_step)
```

（`_publish`/`build_step_dict` 为 react_step.py 现役符号；实施按该文件 `_emit_publish` 收口约定接入。）

### 8.9 配置项（`backend/app/config` tuning 段）

```yaml
tuning:
  concurrency:
    shell_max_processes: 10        # 现役: 前台 shell 并发
    shell_max_background: 5        # 新增: 后台 shell 并发上限(名额生命周期=命令生命周期)
  shell_bg_log_max_mb: 50         # 新增: 后台输出文件轮转上限(保留 .1/.2 两份)
  shell_bg_result_retain_hours: 24 # 新增: 结果文件保留时长(惰性清理)
```

### 8.10 前端修改：`frontend/src/features/chat/components/layout/TaskListPanel.tsx`（**含前端**）

**改动1 — 任务卡片"自动续跑"徽标**（任务条目渲染处，trigger 字段透传后）：

```diff
+// 2026-11-13 商量: 自动续跑任务徽标(设计 7.2) — 与模型标签同款行内小徽标
+{t.trigger === 'bg_shell_resume' && (
+  <span style={{
+    marginLeft: 6, fontSize: FontSize.SMALL,
+    color: Colors.TEXT.SECONDARY,
+    border: `1px solid ${Colors.BORDER.LIGHT}`,
+    borderRadius: 4, padding: '0 4px',
+  }}>
+    自动续跑
+  </span>
+)}
```

**改动2 — 历史条目 `system_notice` 渲染分支**（任务卡片 user_input 摘要渲染处）：

```diff
+// 2026-11-13 商量: [系统通知] 前缀的 user 消息不渲染为用户发言气泡/摘要,
+//   改渲染居中灰色系统通知条(设计 7.2, 对齐 opencode [Synthetic context] 展示)
+const isSystemNotice = (text: string) => text?.startsWith('[系统通知]');
+
+// 任务卡片正文处:
+{isSystemNotice(t.user_input) ? (
+  <div style={{
+    textAlign: 'center', color: Colors.TEXT.SECONDARY,
+    fontSize: FontSize.SMALL, padding: `${Spacing.XS} 0`,
+  }}>
+    ⚙ {t.user_input.split('\n')[0].replace('[系统通知] ', '')}
+  </div>
+) : (
+  /* 原有 user_input 渲染不动 */
+)}
```

**改动3 — RightViewer 通知行渲染**（bg_shell_done notice 帧，复用现役 notice 渲染通道）：

```diff
+// 2026-11-13 商量: bg_shell_done 通知行 — 复用现役 notice 帧渲染管道
+//   (sseParser/StepRenderer 对 type=notice 已有通用渲染, 仅需在 kind 白名单
+//    或样式映射表加一项, 零新组件)
+const NOTICE_KIND_STYLES = {
+  ...,
+  bg_shell_done: { icon: '⚙', label: '后台命令完成' },
+};
```

> 前端改动评估：**3 处均为渲染层小改**，无状态管理/数据流/布局结构改动；SSE 帧类型零新增（bg_shell_done 走现役 notice 帧管道），TaskListPanel/RightViewer 零结构破坏。

### 8.11 实施顺序与验证清单

| 步 | 内容 | 验证 |
|----|------|------|
| 1 | 8.1 shell_background.py + main.py 挂 set_main_loop | 单测: 注册表/信号量/幂等键；跨线程提交冒烟 |
| 2 | 8.6 task_registry（inject_system_notice + task_cleanup 挂钩） | 单测: 落库→投递→_absorb_inbox 吸收全链（uid 真实、锚演进正常）；cancelled 连带杀 |
| 3 | 8.2/8.3 shell() 分支 + schema | 回归: 前台路径逐字节等价（background=False 全既有用例）；后台分支安全收紧（中风险拒绝） |
| 4 | 8.7 编排层抽取 + resume_session_with_notice | 集成: 任务终态后自动续跑（journal 落事件、任务列表可见）；活跃任务时改注入；幂等（同 notice_id 二次触发跳过） |
| 5 | 8.4/8.5 bash_result 工具 + 注册 | 单测: shell_id/output_file 双路径、轮转合并读、截断 |
| 6 | 8.8/8.10 通知帧 + 前端 | E2E: 三状态（活跃注入/终态续跑/取消杀进程）+ 前端通知条/徽标渲染 |
| 7 | 8.9 配置 | 默认值冒烟 |

**边界回归**：服务重启（注册表清空、结果文件可查）、inbox 满（降级落盘）、多后台并发完成（串行合并）、长驻命令占满名额（明确失败）。

---

*编写人: 商量 — 2026-11-13*
