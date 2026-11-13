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

*编写人: 商量 — 2026-11-13*
