# Conversation History 三层结构技术设计说明 — MessageBuilder / chat_task_steps / chat_stream_events

## 基础信息

| 项 | 内容 |
|---|---|
| **代码基线 tag** | `v1.1.5` |
| **基线 commit** | `34cbb0438812ce8db7655462304fc1f05a571c9b` |
| **基线提交标题** | `docs:[4]任务正常执行中莫名被中断分析与处理方案入库 - 小欧-2026-10-02` |
| **基线时间** | 2026-10-02 |
| **version.txt 记录** | `v1.1.5`（更新时间 2026-10-02 15:00:28 - 小欧-2026-10-02） |

> 本文档全部结论均基于上述 tag + commit 的**最新本地代码**逐行核实，往后代码变动需重新校核文中行号。

## 文档信息

| 项 | 内容 |
|---|---|
| **版本** | v1.4 |
| **创建时间** | 2026-10-03 06:55:10 |
| **更新时间** | 2026-10-03 07:20:15 |
| **编写人** | 小欧 |

## 版本历史

| 版本 | 时间 | 更新人 | 更新说明 |
|---|---|---|---|
| v1.0 | 2026-10-03 06:55:10 | 小欧 | 新建。基于两轮代码核查（`message_builder.py` / `history_loader.py` / `db_initializer.py` / `stream_event_journal.py` / `agent_runner._route_step_to_db` / `task_state.StreamBuffer`）撰写四章：三者定义 / 三者关系 / 用途与需求满足度 / 架构合理性评估。全部结论均标注代码行号出处，可逐条复核。 |
| v1.1 | 2026-10-03 07:02:40 | 小欧 | **头部增「基础信息」节**：锁定代码基线 `v1.1.5` + commit `34cbb0438`（含完整 40 位 hash、提交标题、基线时间、version.txt 记录），并声明全文档结论以该基线为准、代码变动后需重新校核行号。同时校准首版 4 处行号偏差（`chat_task_steps` DDL L165→L105、`MessageBuilder` 字段 L104→L106、`_load_previous_messages` L165→L166 及其内部偏移）。 |
| v1.2 | 2026-10-03 06:59:36 | 小欧 | **增第五章「升级差异说明」**，确立本文档的升级维护规范：① 5.1 补写规则 R1~R4（基线变动即补 / 行号复核 / 结论重审 / 只增不删）；② 5.2 差异记录表（版本 × tag × commit × 变更文件 × 变更内容 × 影响 × 行号复核）；③ 5.3 架构评估增量（追加型，旧行禁止删除）；④ 5.4 待观察项 D1~D4 挂账追踪。 |
| v1.3 | 2026-10-03 07:07:49 | 小欧 | **4.2 全节重写: 四问题逐条溯源 + 规范判定 + 解决方案**(原表仅4句结论无依据)。① **D1 更正为误判并删除**——原判据只看 reclaim_memory_buffer 的 docstring, 未检索 Journal 独立清理链路; 实际 retention_cleanup + 每小时调度 + 配置项 + 孤儿行 LEFT JOIN 兜底 + 活跃判活时钟容差 + 全精度时间比较均已实现, 并补记「否定性结论须检索全仓」的教训; ② **D2** 定性为「缺事后校验而非缺机制」, 方案定为启动期批量对账(实时对账违反 KISS-DIRECT), 明确不自动补写(会引入第二套真源, 违反 DRY/SRP); ③ **D3 升为最高优先级**, 论证 trim_history 因「装载早于队列建立」而必然失效, 方案三道闸收敛于 _load_previous_messages, 第1闸必须是 SQL LIMIT(Python 侧截断已晚于入库); ④ **D4 修正为两个正交集合**(_SSE_ONLY_TYPES 9项写入侧 ⊂ M_SKIP 14项统计侧, 差集5项为「落库但不计」), 方案为按语义二分并改 import, 否决「flags 注册表」(14个枚举值属 YAGNI 过度设计)。全部方案附 10 大规范逐条判定表。 |
| v1.4 | 2026-10-03 07:20:15 | 小欧 | **第五章改写为「遗留问题的修改方案」**（原仅维护规则，无方案）。① 5.0 定优先级与落地顺序：D4→D3→D2（D4 纯重构零行为变化先热手）；② **5.1 D3 详述三道闸方案**（SQL LIMIT / token 预算 / 最近优先），含「trim_history 为何必然失效」的时序论证、SLAP 分层表、5 条否决做法及规范依据、4 步落地与验收；③ **5.2 D4** 给出按语义二分 + 单向 import 方案，4 条否决做法（否决 flags 注册表/合并两集/断言一致/第三处类型清单）；④ **5.3 D2** 给出启动期批量对账方案，含「为何不自动补写」三条论证（反推业务步会引入第二套真源，违反 DRY/SRP，并引 agent_runner.py:107/471 两处既有踩坑留痕为证）、5 条否决做法；⑤ 每节均附 10 大规范逐条判定表；⑥ 原升级维护规则顺延为 5.4。 |

---

## 一、三者是什么

### 1.1 一句话定义

三者处在**不同层级**，不是同类事物的三个副本：

| # | 名称 | 层级 | 物理形态 | 生命周期 | 定义位置 |
|---|---|---|---|---|---|
| ① | **`conversation_history`** | **语义层（概念）** | 进程内内存 `List[Dict]` | **任务结束即丢** | `message_builder.py:72` `MessageBuilder.conversation_history` |
| ② | **`chat_task_steps`** | **语义层（持久化）** | SQLite 表 | 永久 | `db_initializer.py:105` |
| ③ | **`chat_stream_events`** | **传输层（持久化）** | SQLite 表 | 永久 | `db_initializer.py:182` |

**关键认知**：`conversation_history` 不是一个表，是**每次任务临时装配出来的一个列表**；②③ 才是物理表。① 与 ② 是「同一语义内容的两种形态」（内存态 / 落库态），③ 与它们是「不同语义层面的平行存档」。

### 1.2 ① `conversation_history` — LLM 请求的消息队列

`MessageBuilder` 的 docstring 第一行即定义：

> `conversation_history` 唯一状态管理器 — 组装/存储/裁剪/准备

结构（`message_builder.py:106-110`）：

```python
self.conversation_history: List[Dict[str, Any]] = []   # 主队列
self.temp_history: List[Dict[str, Any]] = []           # _temp_reasoning 临时消息
self.MAX_CONTEXT_TOKENS: int                            # 上下文上限
self._max_rounds: int                                   # 最多保留 FC 轮数
self._trim_trigger_ratio: float                          # 裁剪触发比
```

对外 12 个方法（`inspect.getmembers` 实测）：`init_history` / `inject_history` / `add_system_message` / `add_user_message` / `add_assistant_message` / `add_assistant_tool_call` / `add_tool_result` / `add_observation` / `pop_temp_messages` / `trim_history` / `prepare_messages_for_llm` / `reset_per_run`。

**assistant 消息进 history 的四种形态**（docstring 实录，DeepSeek 实测）：

| 形态 | 场景 | 入库内容 |
|---|---|---|
| (a) Action 轮 | 调工具 | `{"role":"assistant","tool_calls":[...]}` — **content 与 reasoning_content 均不入** |
| (b) Answer 轮 | 最终回答 | `{"role":"assistant","content":"最终答案文本"}` |
| (c) Reasoning-only | thought-only | `{"role":"assistant","content":"","reasoning":...,"_temp_reasoning":true}`，持久化前 `pop_temp_messages()` 弹掉 |
| (d) 异常/警告轮 | 空转/未调工具/error | `{"role":"assistant","content":"[硬编码警告/错误文本]"}` |

### 1.3 ② `chat_task_steps` — 业务步骤落库表

DDL（`db_initializer.py:105-115`，逐字）：

```sql
CREATE TABLE IF NOT EXISTS chat_task_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ai_message_id INTEGER NOT NULL,   -- v2.0 改名: message_id → ai_message_id
    session_id     TEXT NOT NULL,
    step_index     INTEGER NOT NULL,  -- 轮内序号
    step_json      TEXT NOT NULL,     -- 整步 JSON
    created_at     TEXT,              -- 本地ISO无Z
    task_id        TEXT,              -- 锚: 任务
    usage          TEXT,              -- 该轮 token 明细副本
    user_message_id INTEGER           -- v2.0 冗余: 免 JOIN 直达 user 消息
);
CREATE UNIQUE INDEX idx_steps_unique
    ON chat_task_steps(ai_message_id, task_id, step_index);   -- db_initializer.py:350
```

**只存业务步。** `agent_runner._route_step_to_db` 用 `M_SKIP`（实测 14 项）过滤后，非业务步直接 `return`，**不入此表**：

```
authorization_required, cancelled, chunk, context_overview, error, final_stats,
paused, rejected, resumed, retrying, start, stats, thought-start, usage
```

**余下的业务步** = `action` / `observation` / `thought` / `final`（`count_business_steps` docstring 明录）。

写入链路（10-01 重构后）：`buffer.publish` → `persist_sink` → `_route_step_to_db` → `_enqueue_step`（**只入队即返回**）→ `_drain_steps` 消费者 → `_write_step` → `db.atxn(retry_locked=3)` → `append_execution_step`。

### 1.4 ③ `chat_stream_events` — SSE 帧存档（Journal）

DDL（`db_initializer.py:182-192`，逐字）：

```sql
CREATE TABLE IF NOT EXISTS chat_stream_events (
    task_id     TEXT NOT NULL,
    session_id  TEXT NOT NULL,
    seq         INTEGER NOT NULL,
    event_type  TEXT NOT NULL,
    payload_json TEXT NOT NULL,   -- 原始 SSE 帧
    created_at  TEXT NOT NULL,
    PRIMARY KEY (task_id, seq)
);
CREATE INDEX idx_stream_events_type
    ON chat_stream_events(task_id, event_type, seq);
```

写入：`agent_runner.py:309` `create_task_stream_buffer(task_id, session_id, journal_append)` → `stream_event_journal.append` → `INSERT OR IGNORE`。

**不过滤，一帧不落。** 含 `usage` / `paused` / `retrying` / `stats` / `final_stats` 等全部 14 项非业务帧。

---

## 二、三者的关系

### 2.1 整体数据流图

```
                         ┌─────────────────────────────────────────┐
                         │  ① MessageBuilder.conversation_history  │
                         │     （内存 List，任务结束即丢）          │
                         │  唯一消费者：react_step 发给 LLM 的 messages│
                         └───────────────▲─────────────────────────┘
                                         │ inject_history（任务启动时装配一次）
                                         │
   ┌─────────────────────────────────────┴──────────────────────────────────┐
   │                        DB 持久层（永久）                                │
   │                                                                        │
   │  chat_user_message ──┐                                                  │
   │  （用户侧正文）      ├──► history_loader._load_previous_messages()      │
   │  chat_tasks ─────────┤    · independent → return []（从零）             │
   │  （任务行 + 链指针）  │    · linked      → 链根首user_id ~ 本任务user_id 前 │
   │        ↓             │                                                  │
   │  chat_task_steps ────┘    逐对重建:                                     │
   │  （助手侧唯一数据源）      user / assistant(content+tool_calls) / observation│
   └────────────────────────────────────────────────────────────────────────┘
                                         │
   ═══════════════════════════════════════╪═════════════════════════════════
   ║ 同源事件 · 两条平行出口（10-01 起）  ║
                                         │
              agent._step_emitter / handle_action 直连 buf.publish
                                         │
                              ┌──────────┴──────────┐
                              │  StreamBuffer.publish │  ← seq 分配 + append 在锁内原子完成
                              └───┬──────────────┬───┘
                    persist_sink    │              │   journal_sink(同源不同向)
                   (过滤后投递)      │              │
                              ┌─────▼─────┐   ┌────▼──────────────────┐
                              │  ② 队列    │   │  ③ Journal.append      │
                              │ _step_queue│   │ INSERT OR IGNORE      │
                              └─────┬─────┘   └────┬──────────────────┘
                                    │              │
                          _drain_steps 消费者   read_after(task_id, after_seq)
                                    │              │
                                    ▼              ▼
                          ┌──────────────┐   ┌────────────────────────┐
                          │chat_task_steps│   │chat_stream_events      │
                          │  (业务步/过滤) │   │  (全帧/不过滤)          │
                          └──────────────┘   └────────────────────────┘
                                    │              │
                       统计口径 / 历史重建      GET /chat/stream/{task_id}
                                    │              ?after_seq=N  断线重连回放
                                    ▼              ▼
                        chat_tasks.total_steps   前端 SSE 续传
                        final_stats.step_count
```

### 2.2 两两关系判定表

| 关系 | 判定 | 依据 |
|---|---|---|
| ① ↔ ② | **同源同内容，形态不同**（内存态 / 落库态） | ①由②装配而来；②是①的持久化真源 |
| ① ↔ ③ | **无直接关系** | ③不参与 LLM 上下文；①不读③ |
| ② ↔ ③ | **同源事件，平行出口，粒度不同** | 同一次 `buf.publish` 分别喂 `persist_sink`（过滤）与 `journal_sink`（不过滤） |

### 2.3 关键澄清：③ 不是 ② 的备份

| 维度 | ② `chat_task_steps` | ③ `chat_stream_events` |
|---|---|---|
| 过滤 | **过滤 14 类非业务步** | **不过滤** |
| 粒度 | 消息/步骤级 | **帧级** |
| 排序键 | `step_index`（轮内） | `seq`（task 内全局递增，带断点续传语义） |
| `final` 形态 | 取 `agent._pending_final_db` **长条**（含 `response`） | 原始帧，**可能是剥过的短条** |
| 用途 | 历史重建 / 统计口径 | 断线重连回放 |
| 会丢吗 | 会（进程被杀时队列内帧全丢） | 不丢（同事务写入） |

**推论**：③ 的数据量恒大于 ②，两者**不可互相替代**。

---

## 三、用途场景与需求满足度

### 3.1 场景覆盖矩阵

| 场景 | 走哪条路 | 满足 |
|---|---|---|
| LLM 多轮上下文 | ①（`prepare_messages_for_llm` → 发请求） | ✅ |
| 上下文超限裁剪 | ①`trim_history`（`_trim_trigger_ratio` / `_max_rounds`） | ✅ |
| reasoning 临时消息不入库 | ①`pop_temp_messages` 弹 `_temp_reasoning` | ✅ |
| 会话历史重建（助手侧） | ② → `load_execution_steps` → `_parse_tool_calls` / `_parse_observations` | ✅ |
| 任务详情页步骤回放 | ② → `load_steps_by_task` | ✅ |
| `total_steps` 统计口径 | ② → `count_business_steps`（唯一真源） | ✅ |
| **link 任务装入前任务历史** | ② + `chat_tasks` 链指针 → `_load_previous_messages(linked)` | ✅ |
| **SSE 断线重连/续传** | ③ → `read_after(task_id, after_seq)` | ✅ |
| 任务异常被杀后回放 | ③（② 会丢，已由 `flush_sink` 补） | ✅ |

### 3.2 link 任务装入前任务历史 — 已实现，无需新表

`history_loader.py:166-222` 完整实现，注释逐条实录：

| 模式 | 行为 | 出处 |
|---|---|---|
| `independent`（新任务，默认） | **`return []`** — 从零开始，不带任何链上历史（防误灌） | L176-180 |
| `linked`（续聊） | 沿「链根首条 user 消息 id → 本任务 user 消息 id**之前**」范围加载 | L181-203 |

链指针落在 `chat_tasks` 两列：`context_link_mode` / `context_root_task_id`。

```python
_lower_id = SELECT user_message_id FROM chat_tasks WHERE task_id=?   -- 链根下界
pairs = fetch_session_user_message_pairs(conn, session_id,
                                         lower_id=_lower_id,
                                         upper_id=upper_message_id)
```

**上界严格小于本任务 user 消息 id**——原用 `BETWEEN lo AND upper` 会把本任务自己的 user 消息也装入，与本次 `user_input` 重复（2026-08-17 小健三堂会审-E1 修复，L198-200 注释实录）。

逐对重建（L205-222）：

```python
{"role":"user","content": p["user_content"]}
{"role":"assistant","content": p["ai_content"], "tool_calls": _parse_tool_calls(...)}
+ _parse_observations(...)      # observation 作独立消息插回
```

**结论：不需要新增表。** 链指针（`chat_tasks` 两列）+ 内容源（`chat_user_message` + `chat_task_steps`）已构成完整闭环。

### 3.3 已知的一处不一致（已修）

**现象**：`chat_task_steps` 0 行，而 `chat_stream_events` 事件齐全。

**根因**：10-01 重构后 `_enqueue_step` **只入队即返回**，真落库在 `_drain_steps` 协程。进程被杀（如 `task_interrupted`）时队列内帧全丢。

**修法**（2026-10-02 已提交 `88d5014f8`）：`StreamBuffer` 增 `flush_sink`，`agent_runner` 注入 `_flush_steps`，`react_loop` 每轮迭代顶 `await` 一次。被打断最多丢本轮（无工具副作用），不丢已完成轮次。

---

## 四、架构合理性评估

### 4.1 评估维度

| 维度 | 评价 | 依据 |
|---|---|---|
| **单一真源** | ✅ 合理 | 业务步真源唯一（`chat_task_steps`）；`count_business_steps` 明录「单一真源」；10-01 已退役末尾扫描 `event_log` 机制 |
| **职责分离** | ✅ 合理 | 传输层（③）与语义层（②）分开，各司其职。③ 不污染统计口径，② 不承载重连 |
| **写入路径收口** | ✅ 合理 | 10-01 把落库路由挂到 `buffer.persist_sink` 而非调用点。注释明录原因：「事件有三条发布路径（`_emit_publish` / `handle_action` 直连 `_buf.publish` / `_events` 批量），挂调用点必漏」 |
| **分层清晰** | ✅ 合理 | `task_state.py` 保持 **DB-agnostic**，只暴露 `persist_sink` / `flush_sink` 回调，不感知 `chat_task_steps` |
| **锁粒度** | ✅ 合理 | `seq` 分配 + `append` 在锁内原子完成；`persist_sink` 调用于**锁外**（注释明录：sink 含 Prompt 日志文件写，持锁会把所有 publish 串行化） |
| **幂等性** | ✅ 合理 | `ON CONFLICT DO NOTHING` 配 `idx_steps_unique`；`append_execution_step` 对 `task_id` 缺失 **fail-loud**（实测 SQLite 唯一索引中 NULL 互不相等） |
| **失败隔离** | ✅ 合理 | `_write_step` 有限重试 + **失败只记不抛**（docstring：抛穿会打断 finally 后续终态链致 SSE 挂死） |

### 4.2 已识别问题（经 2026-10-03 复核，含 1 条误判更正）

> **v1.3 复核结论**：v1.0/v1.1 记录的 D1「Journal 无清理机制」**经代码核实为误判，已删除**。原判据只看 `reclaim_memory_buffer` 的 docstring，未检索 Journal 的独立清理链路。教训：**否定性结论必须检索全仓，不可由单点代码外推**。

#### 4.2.1 问题清单

| # | 问题 | 本质 | 违反规范 | 严重度 | 状态 |
|---|---|---|---|---|---|
| ~~D1~~ | ~~Journal 无 TTL/清理机制~~ | — | — | — | ❌ **误判已删除**（详见 4.2.2） |
| D2 | ②③ 双写无事后校验 | 缺观测手段，非缺机制 | 无（YAGNI：有实证，不违反） | 低 | 待决策 |
| D3 | `linked` 模式无链长上限 | **事后兜底无效，当场炸** | 无（属既有能力补边界） | **高** | 待决策 |
| D4 | 落库过滤集与统计过滤集各自硬编码 | 同一语义两处定义 | **DRY** | 中 | 待决策 |

#### 4.2.2 D1 更正：Journal 清理机制**早已完备**

v1.0/v1.1 误判源于只读 `reclaim_memory_buffer`（`task_state.py:176`，其 docstring 确实写「只回收内存缓冲，不触碰 Journal」），未继续检索 Journal 侧的独立清理链路。实际实现：

| 组件 | 位置 | 说明 |
|---|---|---|
| `retention_cleanup(retention_days)` | `stream_event_journal.py:96` | 删已终态且超保留期的事件 |
| `checkpoint_wal()` | `stream_event_journal.py:83` | WAL 页回写主库并截断 |
| 调度任务 | `main.py:250 _start_journal_retention_task` | **每小时一次，独立后台任务，绝不进请求链路** |
| 配置项 | `settings_registry.py:232` | `tuning.live_front.journal_retention_days`，默认 **7 天**，`range_=[1,30]` |

三点设计质量值得肯定（**原结论完全未覆盖**）：

**① 用 `LEFT JOIN` 而非 `INNER JOIN`，孤儿行有兜底**

```sql
LEFT JOIN chat_tasks t ON t.task_id = e.task_id
WHERE (t.status IN ('completed','failed','cancelled') AND ...)
   OR (t.task_id IS NULL AND e.created_at < ?)   -- 孤儿行
```

源码注释实录：**「孤儿行（无 chat_tasks 行：建 buffer 早于 insert_task，写库失败即产生）按事件自身 created_at 兜底清理，否则 INNER JOIN 会把它整个丢弃、永不清理导致 Journal 无限增长」**。——「Journal 无限增长」这个风险点作者早已识别并堵死。

**② 活跃任务判活用「最近事件时间窗」而非「非终态」**

`is_producer_alive` 注释实录：**「非终态不等于已停摆——任务仍在跑、只是长时间无新事件（慢思考/HITL 静默/工具长耗时）时也会这样，误判会中断回放」**。并用 `_CLOCK_SKEW_TOLERANCE_SECONDS` 处理时钟回拨（否则死任务永不收敛）。

**③ 时间比较用全精度 isoformat**

源码注释实录：**「全精度 isoformat()：与 `get_local_iso_timestamp()` 存储格式一致；`timespec="seconds"` 截微秒会让同秒边界的字符串比较误判 — 小欧 2026-09-29 21:37:55」**。——真踩过坑才会写下的注释。

**结论**：D1 不是设计债，是已完成实现。**保留此条仅为记录 v1.0 的误判，不作为待办。**

#### 4.2.3 D2 — ②③ 双写一致性

**现状**：`flush_sink`（2026-10-02 提交 `88d5014f8`）已把丢帧窗口收窄到「最多丢本轮，且本轮无工具副作用」。

**真正缺的不是机制，是事后校验。** 代码中已有对账范式（`agent_runner.py:834`，token 明细 SUM vs 权威累计列，不一致即告警不阻断），但**未覆盖 ②③ 之间**。

**规范判定**：

| 规范 | 判断 |
|---|---|
| YAGNI | ⚠️ 不违反——已出实证（`task_interrupted` 样本 steps 0 行而 Journal 齐），属「有据可依」而非「凭空预防」 |
| KISS-DIRECT | ⚠️ 方案必须克制：实时对账 = 每次 publish 都比对 = O(n) 扫描拖慢热路径，**违规** |
| SRP | ✅ 对账是独立职责，不侵入写入链路 |

**方案：启动期批量对账，不做运行期实时对账**

```
main.py startup
  └─ 新增 journal_steps_reconcile()
       ├─ GROUP BY task_id 取 Journal 各任务终态帧数
       ├─ 比对 chat_task_steps 行数
       └─ 不一致 → logger.error（只告警留痕，不自动修）
```

理由：矛盾**只在进程被杀时产生**，属启动期一次性可检出；运行期实时对账违反 KISS-DIRECT。

**为什么不自动补写**：`ON CONFLICT` + `step_index` 虽幂等，但 Journal 帧已被 `_SSE_ONLY_TYPES` 过滤逻辑处理过，反推业务步需重放该判定 → 引入第二套真源，**违反 DRY/SRP**。

**为什么不建对账表**：为观测建新存储，YAGNI 拒绝，日志足够。

#### 4.2.4 D3 — `linked` 模式无链长上限（优先级最高）

**为何最严重——它是唯一「事后兜底无效」的一条**：

| | D2 | **D3** |
|---|---|---|
| 表现 | 口径漂移 | `_load_previous_messages` **在 LLM 请求前执行，装载本身即 OOM/超时** |
| 时机 | 事后可查 | **事前，无处兜底** |
| `trim_history` 能救吗 | — | ❌ **救不了**——装载发生在 `init_history`/`inject_history` 之前，队列尚未建立 |

**现有兜底 `trim_history`（`message_builder.py:172`）双条件**：

| 条件 | 判据 |
|---|---|
| A（增量） | 本轮粗估 − 上轮精确 > `COMPACTION_BUFFER` |
| B（绝对值） | 历史 > `MAX_CONTEXT_TOKENS × TRIM_TRIGGER_RATIO`（3/4，北京老陈 2026-08-17 定案） |

另有 `if msg_count <= 5: return` 短路。**但这些都在队列建好之后才生效，对 D3 无效。**

**规范判定**：不违反任何一条——属给既有能力补边界，而非新增能力。

**方案：三道闸，全部收敛在 `history_loader._load_previous_messages` 一处**

| 闸 | 位置 | 判据 |
|---|---|---|
| 1. SQL 层 LIMIT | **SQL `LIMIT`（关键）** | `fetch_session_user_message_pairs(..., limit=N)`，N 取 `tuning.context.max_history_pairs`（默认 20） |
| 2. token 预算 | 装载后累加 | 超 budget 即停；budget 从 `MessageBuilder.MAX_CONTEXT_TOKENS` **派生**（复用，不新增常量） |
| 3. 最近优先 | 超限截断策略 | 保留**离本任务最近**的 N 条，而非最老的 N 条 |

**关键：第 1 闸必须是 SQL `LIMIT`，不能是 Python 侧 `for ... break`。** 全量行已从 SQLite 读入内存后才截断毫无意义——这正是当前 `trim_history` 救不了 D3 的根本原因。

**分层依据（SLAP）**：装载是 DB 层职责，裁剪是消息队列层职责。限制加在 SQL 层（数据访问抽象内），不散落到调用方。

**为什么不做「链上全量 + prompt 摘要」**：需引入摘要生成链路（新组件 + 新 LLM 调用 + 缓存），违反 YAGNI，且当前无超长链崩溃实证表明必要。

#### 4.2.5 D4 — 两个正交过滤集各自硬编码

**实为两个用途不同的集合，非同一集合的重复**（实测差集）：

| 集合 | 位置 | 数量 | 维度 | 语义 |
|---|---|---|---|---|
| `_SSE_ONLY_TYPES` | `agent_runner.py:235` | **9** | **写入侧** | 不过滤则不落 `chat_task_steps` |
| `M_SKIP` | `agent_telemetry.py:63` | **14** | **统计侧** | 不计入业务步数 |

实测关系：`_SSE_ONLY_TYPES` ⊂ `M_SKIP`（反向差集为空）。

差集 5 项（`M_SKIP - _SSE_ONLY_TYPES`）：`authorization_required`、`context_overview`、`final_stats`、`start`、`stats`——**这 5 项确实落 `chat_task_steps`（需回放），但不算业务步（用户不可见的框架事件）**。

**故两者不重复，而是「落不落库」与「算不算数」两个正交维度。** 新增一种 SSE 类型时必须同时判断两处，v1.0 原文「新增 SSE 类型需手工同步」只对了一半——漏判的是「两个维度都要判」。

**已有防护**：`agent_telemetry.py:36` 注释实录「2026-09-11 设计缺陷修复：`_log_task_end` 的步骤剔除集由**硬编码 3 种改为复用 `_M_SKIP`（单一来源）**」——**已做过一次 DRY 收敛**，方向正确。

**规范判定**：

| 规范 | 判断 |
|---|---|
| **DRY** | ⚠️ 本质问题 |
| YAGNI | ⚠️ 不违反——新增类型漏改某处是**必然发生**，非「可能」 |
| **OCP** | 解法方向：新增类型应「不改既有代码」 |

**方案：按语义分两组表达，`_SSE_ONLY_TYPES` 改为 import（零行为变化纯重构）**

```python
# agent_telemetry.py — M_SKIP 提为单一真源，内部按语义二分
_SSE_ONLY            = frozenset({"thought-start","chunk","error","usage","paused",
                                 "resumed","retrying","cancelled","rejected"})          # 9: 不落库
_PERSISTED_NON_BIZ   = frozenset({"start","stats","context_overview",
                                 "final_stats","authorization_required"})             # 5: 落库但不计
M_SKIP = _SSE_ONLY | _PERSISTED_NON_BIZ                                                  # 14

# agent_runner.py — 改为 import, 删除本地重复定义
from app.monitoring.agent_telemetry import _SSE_ONLY as _SSE_ONLY_TYPES
```

**收益**：新增类型的决策顺序自解释——先问「落不落库」归第一组，再问「算不算数」归第二组。

**为什么不用「每类型带 flags 注册」**：需建注册表 + `persist`/`count` 两个 flag，是**为 14 个枚举值过度设计**，违反 YAGNI。分类法已足够。

### 4.3 总体结论

**架构合理。** 三层各司其职、无职责重叠、无逆向依赖，且三条关键风险（多路径漏挂、锁粒度、失败传播）均已在 10-01/10-02 两轮重构中针对性处理并留有代码注释。

**不建议新增「任务级 conversation history」表**，理由：

| 判据 | 结论 |
|---|---|
| 需求是否已满足 | ✅ `linked` 模式完整实现（3.2），链指针已在 `chat_tasks` |
| 是否已有等价载体 | ✅ `chat_tasks`(链指针) + `chat_user_message`(用户侧) + `chat_task_steps`(助手侧) 三表已覆盖 |
| 新增表的边际收益 | 仅省一次 JOIN，SQL 已在 100 行内完成 |
| 违反的规范 | `AGENTS.md` **YAGNI / 禁过度设计** |

真要新增，前提是先回答：**它要解决 4.2 中哪一条 D1~D4？** 答不出则属无源之表。

## 五、遗留问题的修改方案（D2 / D3 / D4）

> **本章目的**：给出三个遗留问题的**可落地修改方案**，每个方案均附「10 大规范逐条判定」，并列出**否决的其他做法及理由**，确保方案本身不违反项目编码纪律。
>
> **与第四章关系**：第四章 4.2 是**问题诊断**（是什么、为什么算问题）；本章是**解决方案**（怎么改、改完什么形态）。D1 已于 v1.3 确认为误判并删除，不在本章范围。

### 5.0 三问题速览

| 优先级 | 编号 | 问题 | 规范判定 | 是否违反 10 规范 | 本章节次 |
|---|---|---|---|---|---|
| **P0** | **D3** | `linked` 模式无链长上限，`trim_history` 必然失效 | 不违反——属给既有能力补边界 | ❌ 不违反 | 5.1 |
| **P1** | **D4** | 落库过滤集与统计过滤集各自硬编码 | **违反 DRY**；YAGNI 不违反（有必然性） | ✅ **违反 DRY** | 5.2 |
| **P2** | **D2** | ②③ 双写缺事后校验 | 不违反——机制已由 `flush_sink` 收窄，仅缺观测 | ❌ 不违反 | 5.3 |

**落地顺序建议**：D4 → D3 → D2。

| 顺序 | 理由 |
|---|---|
| D4 先行 | 纯重构、**零行为变化**、回归面最小，先把手感热起来 |
| D3 次之 | 需改SQL 与配置，但影响面收敛在 `_load_previous_messages` 一个入口 |
| D2 最后 | 纯新增观测代码，不改任何既有行为；且其价值依赖 D3 先落地 |

---

### 5.1 【P0】D3 — `linked` 模式无链长上限

#### 5.1.1 问题本质

`_load_previous_messages` 在 `linked` 模式沿链装载：

```
链根首条 user_message_id ←→ 本任务 user_message_id（不含）
```

**无条数上限、无 token 上限。** 链长 N 个任务 → 一次装载 N 轮对话。

#### 5.1.2 为何 `trim_history` 必然失效（关键论证）

`MessageBuilder.trim_history`（`message_builder.py:172`）双条件触发：

| 条件 | 判据 |
|---|---|
| A（增量） | 本轮粗估 − 上轮精确 > `COMPACTION_BUFFER` |
| B（绝对值） | 历史 > `MAX_CONTEXT_TOKENS × TRIM_TRIGGER_RATIO` |

**但它工作在「队列已建好」之后**：`_load_previous_messages` 的结果先经 `inject_history` 注入 `conversation_history`，队列才存在。而**装载动作本身**（SQL 取行 + `_parse_observations` 解析）在队列建立之前就已把全部数据读进内存。

```
_load_previous_messages()  ← 大数据量在此产生（无界）
      ↓
inject_history()           ← 此刻才建队列
      ↓
prepare_messages_for_llm() → trim_history()  ← 裁剪只作用于已注入的队列
```

**结论**：`trim_history` 是**队列内裁剪**，D3 是**队列外装载**，后者不在前者能力范围内。故 v1.0/v1.1 原文「依赖 ① `trim_history` 兜底」是**错误判断**。

#### 5.1.3 规范判定

| 规范 | 判定 |
|---|---|
| SRP | ✅ 不违反——限制加在数据装载层，各司其职 |
| DRY | ✅ 不违反——第 2 闸的 budget 从 `MessageBuilder.MAX_CONTEXT_TOKENS` **派生**，不新增常量 |
| KISS-DIRECT | ⚠️ 方案必须是一处 SQL 边界 + 一次累加，不得引入新组件 |
| SLAP | ✅ 不违反——限制收敛在 `_load_previous_messages` 单入口，不散落调用方 |
| YAGNI | ✅ 不违反——**无实证表明必要**，故不做「链上摘要」类重型方案（见 5.1.6 否决） |
| 禁止 backward | ✅ 不违反——新增可选参数，不改既有调用语义 |
| OCP | ✅ 达标——`fetch_session_user_message_pairs` 新增可选参数，既有 3 个调用方零改动 |
| 复用优先 | ✅ 达标——复用 `fetch_session_user_message_pairs` / `MAX_CONTEXT_TOKENS` |

#### 5.1.4 方案：三道闸

**第 1 闸：SQL 层 `LIMIT`（最关键）**

```python
# storage.py:809 fetch_session_user_message_pairs 新增可选参数
def fetch_session_user_message_pairs(conn, session_id, lower_id=None,
                                     upper_id=None, limit=None) -> list:
    ...
    sql += " ORDER BY cum.id ASC"
    if limit is not None:
        # 最近优先: 先 DESC 取最近 N 条, 再回 ASC 保序
        # 必须在 SQL 层截断——全量行读入内存后再截已无意义
        sql = _wrap_recent_n(sql, limit)   # SELECT * FROM (原SQL ORDER BY cum.id DESC LIMIT ?) ORDER BY cum.id ASC
    rows = conn.execute(sql, params).fetchall()
```

调用侧（`history_loader.py`）传入配置：

```python
N = get_config().get("tuning.context.max_history_pairs", 20)
pairs = fetch_session_user_message_pairs(conn, session_id,
                                         lower_id=_lower_id,
                                         upper_id=upper_message_id,
                                         limit=N)          # ← linked 模式才传
```

**为什么第 1 闸必须是 SQL `LIMIT`**：Python 侧 `for ... break` 发生在 `fetchall()` 之后，全量行已进入内存——这正是当前 `trim_history` 救不了 D3 的同一个原因。**截断必须下推到 SQL。**

**第 2 闸：token 预算（防「消息少但每条巨大」）**

```python
_budget = _agent_message_builder_budget()   # 从 MessageBuilder.MAX_CONTEXT_TOKENS 派生，不新增常量
_acc = 0
for p in pairs:
    _acc += estimate_tokens(p["user_content"]) + estimate_tokens(p.get("ai_content"))
    if _acc > _budget:
        pairs = pairs[:_idx]   # 保留最近部分
        break
```

**为什么需要**：`LIMIT 20` 拦不住「20 条超长消息」。

**第 3 闸：最近优先语义**

`limit` 取**离本任务最近**的 N 条，而非最老的前 N 条。与 LLM 关注近因的固有特性一致。

#### 5.1.5 分层依据（SLAP）

| 层 | 职责 | 本次改动 |
|---|---|---|
| SQL 层（`storage.fetch_*`） | 数据取多少 | 加 `LIMIT` |
| 装载层（`history_loader._load_previous_messages`） | 取回后如何组装 | 加 token 预算闸 |
| 队列层（`MessageBuilder`） | 队列内裁剪 | **不动**（它管的是自己队列的膨胀，不是装载量） |

**为什么不把限制加在 `MessageBuilder`**：那会让它承担「数据源裁剪」职责，与 SLAP 冲突——队列层无法判断一条消息是「历史」还是「本轮」。

#### 5.1.6 否决的其他做法

| 方案 | 否决理由 | 违反规范 |
|---|---|---|
| 链上全量 + prompt 摘要压缩 | 需引入摘要生成链路（新组件 + 新 LLM 调用 + 缓存 + 降级策略），且**当前无超长链崩溃实证** | YAGNI |
| 只加第 2 闸（token 预算，不加 SQL LIMIT） | 全量行已入内存才裁剪，极长链仍在**入库阶段** OOM | — |
| 在 `history_loader` 内Python 侧 `break` | 见5.1.4，等于没修 | — |
| 改 `MAX_CONTEXT_TOKENS` 全局下调 | 连带压缩所有任务的本轮上下文，超出本问题范围 | 禁止 backward（牵连既有行为） |
| 给`linked` 加显式配置开关（默认开/关） | 增加一个用户需理解的模式开关，而正确行为本就是「有上限」 | YAGNI |

#### 5.1.6 落地步骤与验收

| 步 | 动作 | 验收 |
|---|---|---|
| 1 | `fetch_session_user_message_pairs` 加可选 `limit`，`ORDER BY cum.id DESC LIMIT ?` 子查询回包 `ASC` | 现有 3 个调用方（`execution_stream` / `message_service` / `stream_orchestrator`）行为**零变化** |
| 2 | `settings_registry` 注册 `tuning.context.max_history_pairs`，默认 20，`range_=[1,200]` | 配置加载期可校验 |
| 3 | `_load_previous_messages` linked 分支传 `limit` + 加token 预算闸 | 造一条 50 任务链，断言注入后 `len(conversation_history)` 受控 |
| 4 | 回归 | `linked` / `independent` 两模式各跑一次真实对话；`test_p9_04_multi_step` 等历史用例全绿 |

**风险**：`independent` 模式不受影响（本就 `return []`）；`execution_stream` / `message_service` 不传 `limit` 即保持原行为（**OCP 达标**）。

---

### 5.2 【P1】D4 — 落库过滤集与统计过滤集各自硬编码

#### 5.2.1 问题本质

实测两个集合**用途不同**，非重复定义：

| 集合 | 位置 | 数量 | 维度 | 语义 |
|---|---|---|---|---|
| `_SSE_ONLY_TYPES` | `agent_runner.py:235` | **9** | **写入侧** | 不过滤则不落 `chat_task_steps` |
| `M_SKIP` | `agent_telemetry.py:63` | **14** | **统计侧** | 不计入业务步数 |

关系：`_SSE_ONLY_TYPES` ⊂ `M_SKIP`（反向差集为空）。

差集 5 项（`M_SKIP − _SSE_ONLY_TYPES`）= `authorization_required`、`context_overview`、`final_stats`、`start`、`stats`——**落库（需回放）但不算业务步（用户不可见的框架事件）**。

**故二者正交**：「落不落库」与「算不算数」是两个独立决策。新增一种 SSE 类型时必须**两处都判**。

#### 5.2.2 规范判定

| 规范 | 判定 |
|---|---|
| **DRY** | ✅ **违反**——同一语义（哪些帧不是业务步）在两处定义 |
| YAGNI | ✅ 不违反——新增类型漏改是**必然发生**（非「可能」），且已有 DRY 收敛先例 |
| KISS-DIRECT | ⚠️ 方案须是「分组 + import」，不得引入注册表 |
| OCP | ✅ 达标目标——新增类型应「不改既有代码」 |
| 复用优先 | ✅ 达标——`_SSE_ONLY_TYPES` 直接复用 `agent_telemetry` |

#### 5.2.3 方案：按语义二分 + 单向 import

```python
# agent_telemetry.py — M_SKIP 提为单一真源, 内部按语义二分(不改变集合内容, 纯重构)
_SSE_ONLY          = frozenset({"thought-start","chunk","error","usage","paused",
                               "resumed","retrying","cancelled","rejected"})           # 9: 仅 SSE 不落库
_PERSISTED_NON_BIZ = frozenset({"start","stats","context_overview",
                               "final_stats","authorization_required"})                # 5: 落库但不计业务步
M_SKIP = _SSE_ONLY | _PERSISTED_NON_BIZ                                                 # 14 单一真源
_M_SKIP = M_SKIP   # 本模块内原名保持, 零改动既有引用
```

```python
# agent_runner.py — 删除本地重复定义, 改为 import
from app.monitoring.agent_telemetry import _SSE_ONLY as _SSE_ONLY_TYPES
```

**收益**：新增类型的决策顺序自解释——**先问「落不落库」归第一组，再问「算不算数」归第二组**，且两组都是一次决策、互不干扰。

**行为零变化**：`M_SKIP` 的 14 项内容与顺序完全不变。

#### 5.2.4 否决的其他做法

| 方案 | 否决理由 | 违反规范 |
|---|---|---|
| 每类型带 `persist`/`count` flags 注册表 | 为 **14 个枚举值**建注册表 + 双flag，是典型的过度设计 | YAGNI / KISS-DIRECT |
| 把 `_SSE_ONLY_TYPES` 合并进 `M_SKIP`（一个集用两处） | **语义错误**——会连带把 `start`/`stats` 等 5 项从落库侧剔除，改变既有行为 | 禁止 backward |
| 新增 startup 断言「两集一致」 | 断言的是「错误的关系」（本就不该完全相等），反而固化误解 | SRP |
| 改用 `MetaStep`/`FinalStep` 类的 `TYPE` 常量驱动判定 | 类型信息已由 `count_business_steps` 的 `getattr(s,"TYPE","")` 读取（兼容对象/字典两形态），此处已覆盖；再引入第三处类型清单属重复 | DRY |

#### 5.2.5 落地步骤与验收

| 步 | 动作 | 验收 |
|---|---|---|
| 1 | `agent_telemetry.py` 内二分定义 `M_SKIP`，保持 14 项内容与顺序不变 | `assert len(M_SKIP)==14`；`M_SKIP - _SSE_ONLY == {那 5 项}` |
| 2 | `agent_runner.py` 删本地定义，改 import | `import` 后 `agent_runner._SSE_ONLY_TYPES` 与原 9 项**逐项相等** |
| 3 | 回归 | `test_final_stats_real_bugs.py`（含 `test_p2`/`test_p3` 断言 `_M_SKIP` 语义者）全绿；`chat_tasks.total_steps` 与 `final_stats.step_count` 与改前一致 |

**风险**：零——纯重构，集合内容与行为完全不变。这是三个方案里**最安全**的一个，故排P1 先做。

---

### 5.3 【P2】D2 — ②③ 双写缺事后校验

#### 5.3.1 问题本质

`buf.publish` 一帧两出：

```
persist_sink  → _SSE_ONLY_TYPES 过滤 → _step_queue → chat_task_steps      （② 过滤后）
journal_sink  → INSERT OR IGNORE                                       → chat_stream_events （③ 全帧）
```

`flush_sink`（2026-10-02 提交 `88d5014f8`）已把丢帧窗口收窄到「最多丢本轮，且本轮尚未执行工具 → 无副作用」。

**真正缺的不是机制，是事后校验**：代码中已有对账范式（`agent_runner.py:834`，token 明细 SUM vs 权威累计列，不一致即告警不阻断），但**未覆盖 ②③ 之间**。

#### 5.3.2 规范判定

| 规范 | 判定 |
|---|---|
| SRP | ✅ 不违反——对账是独立职责，不侵入写入链路 |
| DRY | ⚠️ 方案不得引入第二套真源去「自动补写」 |
| KISS-DIRECT | ⚠️ **运行期实时对账违规**——每次 publish 比对 = O(n) 扫描拖慢热路径 |
| YAGNI | ✅ 不违反——已出实证（`task_interrupted` 样本 steps 0 行而 Journal 齐），属有据可依 |
| 禁止 backward | ✅ 不违反——纯新增观测代码 |

#### 5.3.3 方案：启动期批量对账（不做运行期实时对账）

```python
# stream_event_journal.py 新增
async def journal_steps_reconcile() -> list[dict]:
    """Journal(③) vs chat_task_steps(②) 事后对账 — 小欧 2026-10-03
    只告警不自动修: 反推业务步需重放 _SSE_ONLY_TYPES 判定 → 会引入第二套真源(违反DRY/SRP)。
    启动期一次性可检出矛盾, 无需运行期实时比对(违反KISS-DIRECT)。"""
    def _q(conn):
        return conn.execute("""
            SELECT e.task_id,
                   COUNT(*) AS journal_frames,
                   (SELECT COUNT(*) FROM chat_task_steps s WHERE s.task_id = e.task_id) AS step_rows
            FROM chat_stream_events e
            GROUP BY e.task_id
        """).fetchall()
    ...   # 不一致 → 组装待告警列表
```

```python
# main.py startup 挂载(与 _start_journal_retention_task 同模式)
async def _reconcile_once() -> None:
    bad = await journal_steps_reconcile()
    for b in bad:
        logger.error(f"[Reconcile] task={b['task_id']} Journal帧={b['journal_frames']} steps行={b['step_rows']}")
```

#### 5.3.4 为什么不做自动补写（关键论证）

表面看 `ON CONFLICT DO NOTHING` + `step_index` 幂等，补写即可。但：

1. Journal 帧**已经被 `_SSE_ONLY_TYPES` 过滤逻辑处理过**，从 Journal 反推「哪些是业务步」需重放该判定 → **同一语义出现第二套实现，违反 DRY**
2. `_SSE_ONLY_TYPES` 未来增项时，补写逻辑会静默漏补 → **埋一个更隐蔽的洞**
3. `agent_runner.py:107/471` 已有先例注释：「Prompt 日志比 DB 多 preview 行（2x 误报，对账表）」「preview action 不落库（齿轮先行，DB/Prompt 对账 2x 误报防线）」——**作者已在两处因口径不一致踩坑并留痕**，再引入第三套反推逻辑风险极高

#### 5.3.5 否决的其他做法

| 方案 | 否决理由 | 违反规范 |
|---|---|---|
| 运行期每次 publish 后比对 | O(n) 扫描拖慢热路径，且矛盾只在进程被杀时产生 | **KISS-DIRECT** |
| 自动补写缺失的 steps | 见 5.3.4，引入第二套真源 | **DRY / SRP** |
| 建 `steps_reconcile` 对账表 | 为观测建新存储 | YAGNI |
| 复用 token 对账逻辑 | token 对账比的是「明细 SUM vs 累计列」，②③ 比的是「帧数 vs 行数」，口径与维度均不同 | DRY |
| 什么都不做 | 矛盾只在被杀时产生且无观测手段，等于把问题埋进日志里 | YAGNI（有实证） |

#### 5.3.6 落地步骤与验收

| 步 | 动作 | 验收 |
|---|---|---|
| 1 | 新增 `journal_steps_reconcile()` | 单测覆盖：构造「Journal 有/steps 无」与「两者相等」两态 |
| 2 | `main.py` startup 挂 `_reconcile_once`（只告警不抛） | 启动日志出现 `[Reconcile]` 行；干净库不输出 |
| 3 | 回归 | 全量单测全绿；启动耗时增量 < 50ms（一次性查询） |

**风险**：低——纯新增，不改既有行为；查询失败仅 `logger.warning`，不影响聊天主链路（沿用 `retention_cleanup` 的失败降级范式）。

---

### 5.4 升级差异说明

> 本节为**文档维护规范**，与上述三个方案的实施记录相互独立。

#### 5.4.1 补写规则

| # | 规则 | 说明 |
|---|---|---|
| R1 | 基线变动即补 | 代码 tag 或 HEAD commit 变化后，**先补本章差异表**，再更新头部「基础信息」 |
| R2 | 行号复核 | 变动涉及的文件须重新核对本文所有行号引用，逐一在「复核结果」列打勾 |
| R3 | 结论重审 | 若变动影响三者的层级/关系/用途/合理性判断，须在 5.4.3 追加新的评估行，**禁止删除旧行** |
| R4 | 只增不删 | 本节为追加型，保留全部历史版本记录 |

#### 5.4.2 差异记录表

| 版本 | 代码基线 tag | 基线 commit | 变更文件 | 变更内容 | 对本文的影响 | 行号复核 |
|---|---|---|---|---|---|---|
| v1.0 | `v1.1.5` | `34cbb0438` | —（首版基线） | 首版撰写 | — | ✅ 已复核 |
| v1.1 | `v1.1.5` | `34cbb0438` | 仅本文档 | 头部增「基础信息」节，锁定基线；校准首版 4 处行号偏差 | 无（仅文档） | ✅ 已复核 |
| v1.2 | `v1.1.5` | `34cbb0438` | 仅本文档 | 增 5.1~5.4「升级差异说明」 | 无（仅文档） | ✅ 已复核 |
| v1.3 | `v1.1.5` | `34cbb0438` | 仅本文档 | 4.2 全节重写（D1 更正为误判并删除；D2~D4 补规范判定与方案） | 诊断章节重写 | ✅ 已复核 |
| *（待填）* | | | | | | |

#### 5.4.3 架构评估增量

每次基线变动后，**追加**一行，旧行保留：

| 版本 | 评估维度 | 结论 | 与上版差异 |
|---|---|---|---|

#### 5.4.4 待观察项

经 2026-10-03 复核的结论，代码变动后需重新评估（详见 4.2）：

| 编号 | 待观察项 | 复核结论 | 违反规范 | 优先级 | 方案节次 |
|---|---|---|---|---|---|
| ~~D1~~ | Journal 清理机制 | ❌ **误判已删除**——`retention_cleanup` + 每小时调度 + 孤儿行兜底均已实现 | — | 无 | — |
| D2 | ②③ 双写无事后校验 | 成立（仅缺校验，机制已由 `flush_sink` 收窄） | 无 | P2 | 5.3 |
| D3 | `linked` 无链长上限 | 成立且最严重（`trim_history` 因装载早于队列建立而必然失效） | 无 | **P0** | 5.1 |
| D4 | 两个正交过滤集各自硬编码 | 成立（`_SSE_ONLY_TYPES` 9 项 ⊂ `M_SKIP` 14 项，非重复） | **DRY** | P1 | 5.2 |

---

*编写人：小欧　创建时间：2026-10-03 06:55:10　更新时间：2026-10-03 07:20:15*
