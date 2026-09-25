# prompt-log 终态落盘时序竞态修复设计

> 签名：小欧　|　创建时间：2026-07-18 13:16:01　|　版本：v1.0

## 版本历史

| 版本 | 时间 | 更新人 | 更新要点 |
|------|------|--------|----------|
| v2.1 | 2026-07-18 14:05:00 | 小欧 | 新增"六、代码改动清单（diff 格式，复核3遍）"：3文件8处改动逐行 diff + 功能零丢失核对表 |
| v2.0 | 2026-07-18 13:34:11 | 小欧 | **北京老陈三省三思后确定最佳方法**：生产者全权拥有 prompt-log 全部生命周期（创建/写入/设态/存盘），消费者完全退出日志层；增补"当前系统 10 规范违反分析" |
| v1.1 | 2026-07-18 13:27:00 | 小欧 | 补充"核心结论"：一句话病根+一句话最佳方法+本质问题；北京老陈三省三思后确认 |
| v1.0 | 2026-07-18 13:16:01 | 小欧 | 初版：基于 12 点档 12 个 E2E 会话的真实 prompt-log + app_2026-07-18.log 轨迹，定位"已完成却 0 个 final"的时序竞态病根，给出修复设计 |

---

## 核心结论（三省三思后提炼）

### 病根（一句话）
**prompt-log 的权威存盘点归属了错误的角色。**
消费者 `openai.py`（SSE handler）负责存盘，但它不拥有日志完整性——它只知道"连接结束就该存"，而日志的最后一个关键事件（终端 `FinalStep`）是生产者 `agent_runner` 在它自己的 `finally` 里才补录的。当客户端断流时，消费者**先存了没有终态的盘**，生产者后补的终态再也进不了文件。加上 `save()` 里"处理中→已完成"的谎报，就造出了"已完成但 0 个 final"的矛盾。

### 本质（违反 SRP + 违背 KISS-DIRECT 直线流程）
**谁拥有生命周期，谁就该拥有持久化。** 生产者（`agent_runner`）是运行周期的拥有者——它知道何时真正结束、状态是什么、最终步骤是什么；消费者（`openai.py`）只是读流的通道，通道断了就存盘是不对的。

更底层：当前的数据流是**绕圈的**：
```
openai.py 创建日志 → agent_runner 写步骤（ContextVar 隐式共享）→ openai.py 存盘
```
创建者和存盘者是同一个（消费者），但内容写入者在中间（生产者）。消费者可以独立于生产者提前结束，这个圈就断了。**一条直线应当是：生产者从头到尾一条直线，消费者不碰日志。**

### 最佳方法（一句话）
**生产者 `agent_runner` 全权拥有 prompt-log 的全部生命周期：创建→写入→设态→存盘；消费者 `openai.py` 完全退出日志层。**

即：`agent_runner` 入口调 `prompt_logger.start_request()`、`finally` 末尾按真实终态设状态标签 + 调 `save()`；`openai.py` 删除全部 5 处 `prompt_logger` 调用。`prompt_logger.save()` 删除状态谎报升级。

---

> 编写依据：本设计不写一行代码，待北京老陈批准后由小沈/小欧按"代码10大规范"实施。

---

## 一、背景与现象（病症）

本次 FinalStep 终态规整重构（v3.3 方案）后，对 2026-07-18 12 点档（E2E unit-05~10 + unit-07 重跑）共 **12 个完成会话**的 prompt-log（`backend/logs/prompt-logs/prompt_9997*20260718_12*.json`）逐一核对，发现**与"完成的会话必有终端 FinalStep 记录"的设计不变量相悖**的异常：

| 文件 | 会话 | 状态字段 | 步骤产出 final 数 | 状态变化末态 | 终态跃迁数 |
|------|------|----------|----------------------|------------------|--------------|
| `prompt_999753+...115552.json` | `9aea4bcc…` | **已完成（谎报）** | **0** | `EXECUTING→THINKING` | **0** |
| `prompt_999763+...121126.json` | `82d98bff…`（task002） | **已完成（谎报）** | **0** | `EXECUTING→THINKING` | **0** |
| `prompt_999777+...124524.json` | `da4b9308…`（task007） | **已完成（谎报）** | **0** | `EXECUTING→THINKING` | **0** |

对照正常会话（其余 9 个）：均 `final=1`、`outcome=completed`、content 非空（27~1680 字符）、含 `error_type`/`error_message`、且状态变化记录**有终态跃迁**（`EXECUTING→COMPLETED`）。故设计语义本身正确，问题在**落盘环节**。

**症状三要素（已实测，非推演）：**
1. 会话被标"已完成"，但 `步骤产出` 列表 **0 个 `final` 步骤**；
2. `状态变化记录` 末态停在 `THINKING`（循环中途），**0 个终态跃迁**（`set_completed` 从未被调用）；
3. 后端 `app_2026-07-18.log` 证明这些会话**实际并未正常完成**：`[chat_stream] 客户端断开` 先触发，生产者（后台 agent）随后才结束。

---

## 二、根因分析（病根）

### 2.1 架构前提（无错，仅交代边界）
`openai.py` 把 agent 运行解耦为后台任务（`run_agent_in_background`，`openai.py:237-240`），SSE 消费者（`_stream_with_control`→`stream_reader`）只读 `buffer.event_log` 并在 `buffer.done` 置位后返回（`stream.py:111-112`）。**设计约定：客户端断流不中断 agent，生产者继续跑完**（`openai.py:248` 注释）。

### 2.2 病根链条（file:line 实证）
1. **提前存盘触发点** — `openai.py:247-257`：
   ```python
   except asyncio.CancelledError:          # 客户端断流 → 此处捕获
       logger.info(f"[chat_stream] 客户端断开(task={task_id})，agent 后台继续")
       return                              # 注意：未调 mark_completed()
   ...
   finally:
       prompt_logger.save()              # ← 在后台生产者跑完“之前”就存盘了
   ```
   客户端（E2E）提前断开 SSE → `generate()` 收 `CancelledError` → `except: return` → `finally: save()` **立即执行**。

2. **生产者终态晚于存盘** — `agent_runner.py:226-258`（finally 守卫）：生产者在自身 `finally` 里才把终端 `FinalStep` 记入内存 `_current_log["步骤产出"]`（同步 `log_step_yield` 在 `agent_runner.py:255`），`buffer.done.set()` 在 `agent_runner.py:312`。即：**`save()`（openai.py:257）发生在生产者补记 final（agent_runner.py:255）之前**。

3. **状态造假** — `prompt_logger.py:471-476`：
   ```python
   status = current_log["基本信息"].get("状态", "处理中")
   if status == "处理中":
       if current_log.get("LLM调用记录"):
           current_log["基本信息"]["状态"] = "已完成"   # ← 有 LLM 调用就把“处理中”谎报成“已完成”
   ```
   `save()` 见到状态仍是"处理中"但有 LLM 调用记录，便**私自升级为"已完成"**。

4. **终态永不落盘** — 生产者（`bg_task`）按"断线不影响 agent"继续跑，其 `finally` 守卫把 `FinalStep` 补记到**内存** `_current_log`，但 `openai.py` 的 `save()` 已先执行且**再无第二次 `save()`** → 终态 final 永远没写进磁盘文件。

### 2.3 铁证（app 日志时间线，非推演）
- `prompt_999763`（task002）：`12:11:26 openai.py:249 [chat_stream] 客户端断开` → 紧随 `12:11:26 stream.py:135 [TASK_END] end_type=cancelled`（生产者 finally 的 `_log_task_end`）。**消费者先断、生产者后完**。
- `prompt_999777`（task007）：`12:45:24 客户端断开` → `12:46:27 [TASK_END] end_type=final`（**断流后生产者还跑了 1 分钟**才结束）。
- `prompt_999753`：`11:55:52 客户端断开 … agent 后台继续`。
- 三者的 `[TASK_END]` 均带 `end_type=cancelled/final` 与完整 `steps=` 摘要 → **生产者确实算出了终端 FinalStep，只是没被存盘**。

### 2.4 为何 E2E "假绿"掩盖了它
E2E helper 的 `response_text` **只从 SSE 的 `final` 事件取**（`e2e_helpers.py:372-374`）。SSE 流来自内存 `buffer.event_log`，由生产者填到 `done`，**包含 final 事件** → E2E 读到 final → `response_text` 非空 → 判定 PASSED。但落盘 prompt-log 在断流时已 `save()`，缺 final。即**日志与 SSE/设计不一致，却被 E2E 绿条掩盖**。

### 2.5 病根定性
- 本 bug **非本次 FinalStep 重构引入**（save 时机与状态谎报属预存在架构），但重构未修复，且正是用户质疑的"记录与设计不一致"的真问题。
- 表现层：**prompt-log 的权威存盘点（消费者 openai.py）与终端终态的产出点（生产者 agent_runner）跨协程时序错配**；外加 `save()` 状态谎报放大了"已完成却无终态"的矛盾。
- 本质层：**两个独立生命周期的角色（消费者/生产者）通过 ContextVar 共享了一个可变状态（`_current_log` dict），且没有一个清晰的"谁负责收尾"的归属契约。** 这是生命周期错配。

### 2.6 当前系统违反的代码 10 大规范（三省三思后识别）

当前流程不是"时序竞态"一个点的问题，而是系统设计层面**直接违反 4 条规范**：

| 规范 | 当前状态 | 违反原因 |
|------|----------|----------|
| **SRP** ❌ | `openai.py` 负责日志创建/存盘，`agent_runner` 负责步骤写入 | 没有角色拥有完整日志生命周期。日志创建和存盘都应与运行周期对齐 |
| **KISS-DIRECT** ❌ | 数据流绕圈：`openai.py→agent_runner（写）→openai.py（存）`，不是直线 | 创建者和存盘者是同一个（消费者），写入者在中间（生产者），消费者可先于生产者结束导致圈子断裂 |
| **SLAP** ❌ | `openai.py:246` 的 `mark_completed()` 和 `openai.py:257` 的 `save()` 是日志生命周期逻辑，混在 HTTP SSE 流处理层 | 一个 HTTP handler 不应知道日志什么时候完成 |
| **OCP** ❌ | 以后改日志格式必须同时改 `openai.py` + `agent_runner.py` + `prompt_logger.py` | 日志逻辑散落在三层，不是封闭的 |

本修复的核心目标：**把这三条违反一次纠正，同时修复竞态 bug**。

---

## 三、修复设计（解决方法 — 层次②：生产者全权拥有，消费者完全退出）

### 3.1 设计原则对齐（严守代码10大规范）
| 规范 | 落点 |
|------|------|
| **SRP** ✅ | 生产者 `agent_runner` **独享** prompt-log **全部**生命周期（创建→写入→设态→存盘）；消费者 `openai.py` **完全退出**日志层 |
| **KISS-DIRECT** ✅ | 数据流是一条直线：`agent_runner` 入口 `start_request()` → 循环中 `log_step_yield()` → `finally` 末尾 `set_terminal_status()` + `save()`，不绕不共享 |
| **SLAP** ✅ | 日志生命周期逻辑全部在 `agent_runner` 层（生产者），不在 HTTP handler 层 |
| **OCP** ✅ | 以后改日志只动 `agent_runner` + `prompt_logger`，不碰 `openai.py` |
| **YAGNI** | 不加新基础设施，只迁移创建入口（`start_request` 从 openai.py 迁到 agent_runner） |
| **禁止 backward** | 消费者完全退出日志层，不留任何兼容路径 |
| **复用优先** | 复用既有 `get_prompt_logger()`、ContextVar 传递机制；仅增 `set_terminal_status()`（一个方法替代原来多个 `mark_*`） |
| **增强功能明** | 修复后：① 任何终态（completed/failed/cancelled/paused）**必落 final 记录**；② 状态字段**如实**；③ 与 SSE/DB 终态语义三方一致；④ 日志层与 HTTP 层完全解耦 |

### 3.2 具体改动（3 文件，纯删除 + 纯新增，不改已有逻辑）

#### 改动 A — `app/services/agent/agent_runner.py`（生产者全权拥有）

**新增**（在函数体开始处，`buffer = agent_streams.get(task_id)` 之后、`try` 之前）：
```python
# [新] 生产者全权拥有 prompt-log 生命周期
get_prompt_logger().start_request(last_message, session_id)
```
说明：`last_message` 即 `run_agent_in_background` 参数 `last_message`；`session_id` 同参数。`start_request` 所需的 `get_user_message_id(session_id)` 在该方法内部调用，生产者在后台任务中已可访问 DB。

**新增**（在 `finally` 块末尾，`buffer.done.set()` 之后、`reclaim_stream_buffer` 之前）：
```python
# [新] 生产者权威存盘：终态 FinalStep 已由上方守卫补记(_fd)，
#      此刻 current_execution_steps 必含终态。
_pl = get_prompt_logger()
_label_map = {"completed": "已完成", "failed": "异常终止",
              "cancelled": "已取消", "paused": "已暂停"}
_pl.set_terminal_status(_label_map.get(_terminal_status, "异常终止"))
_pl.save()
```
说明：`_terminal_status` 已在 `finally` 块中由 `_STATUS_MAP.get(end_type, "failed")` 推导（值集 `completed/failed/cancelled/paused`）。`save()` 置于所有 `await` 之后，规避 `CancelledError` 在 `await` 处重抛导致漏存。`update_ai_message_id` 已在循环首步调用（`agent_runner.py:162`），故 `save()` 时 `AI消息ID` 已就绪。

**无需改动**：`log_step_yield`（在 `_append` 内）、`update_ai_message_id`（在循环首步）——它们已在生产者中工作，保持不变。

#### 改动 B — `app/api/v1/chat/openai.py`（消费者完全退出日志层）

**删除全部 5 处 `prompt_logger` 引用**：

| 位置 | 代码 | 理由 |
|------|------|------|
| L41 | `from app.logger.prompt_logger import get_prompt_logger` | 不再需要 |
| L199-200 | `prompt_logger = get_prompt_logger(); prompt_logger.start_request(...)` | 日志创建权移至生产者 |
| L246 | `prompt_logger.mark_completed()` | 状态由生产者按真实终态声明 |
| L253 | `prompt_logger.mark_error(str(e))` | 同 — 生产者 cover |
| L255-257 | `finally: prompt_logger.save()` | 存盘权移至生产者，不再提前存盘 |

删除后，`openai.py` 不再 import、创建、设态、存盘任何日志数据。SSE 流处理归 SSE 流处理，日志归生产者。

#### 改动 C — `app/logger/prompt_logger.py`（删除状态谎报 + 增补设态方法）

**删除** `save()` 方法内 `prompt_logger.py:471-476` 的"处理中→已完成"升级分支：
```python
# 删除此块：
# status = current_log["基本信息"].get("状态", "处理中")
# if status == "处理中":
#     if current_log.get("LLM调用记录"):
#         current_log["基本信息"]["状态"] = "已完成"
#     else:
#         current_log["基本信息"]["状态"] = "异常终止"
```
`save()` 改为纯写出当前状态，不再自作主张升级。

**新增** `set_terminal_status(self, label: str)` 方法（与 `mark_completed`/`mark_error` 同构，DRY）：
```python
def set_terminal_status(self, label: str) -> None:
    """由生产者按真实终态设状态标签（"已完成"/"异常终止"/"已取消"/"已暂停"）"""
    current_log = self._get_current_log()
    if current_log:
        current_log["基本信息"]["状态"] = label
```

**可保留**（不删不改）：`mark_completed()`、`mark_error()` 方法——生产者不再调用它们，但作为公共 API 可保留供其他潜在调用方使用（如测试）。`log_step_yield`、`start_request`、`save`、`get_prompt_logger` 均保持不变。

### 3.3 最优逻辑流程（符合 10 规范）

```
agent_runner（单一归属）
├─ start_request(session_id, user_msg)     ← 创建日志
├─ 循环：log_step_yield(step)              ← 写步骤（已有）
├─ finally 守卫：log FinalStep             ← 写终态（已有，L255）
├─ set_terminal_status(真实终态)            ← 设状态（新增）
├─ save()                                  ← 存盘（新增）
└─ 结束

openai.py（不碰日志）
└─ 只做 SSE 流：stream_reader → yield sse_chunk
```

### 3.4 修复后预期行为
- **正常完成**：生产者入口 `start_request` → 循环写步骤 → `finally` 守卫补 `FinalStep(completed)` → `set_terminal_status("已完成")` → `save()` → 文件含 final、状态"已完成"。✅
- **客户端断流**：`openai.py` `except CancelledError: return`（**不再提前存盘**）；生产者继续跑完 → `finally` 补 `FinalStep(cancelled)` → `set_terminal_status("已取消")` → `save()` → 文件含 final、状态**如实"已取消"**（不再谎报"已完成"）。✅
- **失败/暂停**：同理，状态如实"异常终止"/"已暂停"，终态 final 必落盘。✅

---

## 四、验证计划（复核准确后再实施）

1. **单元层（直接钉死病根）**
   - 新增 `test_prompt_logger_save.py`：构造 `状态="处理中"` 的 `_current_log`，调 `save()` → **断言状态不被升级**（验证改动 C 删谎报）。
   - 新增用例：模拟生产者路径：`start_request` → `log_step_yield(final_dict)` → `set_terminal_status("已完成")` → `save()` → 断言 `步骤产出` 含 final、状态标签准确。

2. **E2E 回归（真实后端+真实 LLM）**
   - 重跑 unit-05~10 + unit-07 重跑；逐 case 核对对应 prompt-log：**`final≥1` 且状态如实**（cancelled 场景显"已取消"、failed 显"异常终止"）。
   - 重点复现断流场景：选一个长任务（如 task007），在 SSE 读到 final 后立即断开客户端连接，确认落盘文件**含 final + 状态如实**。

3. **功能零丢失核对**
   - `openai.py` 删除日志引用后：SSE 流正常、断线重连端点 `chat_stream_reconnect` 正常、`except CancelledError` 仍静默返回（agent 后台继续）。
   - 多轮对话 `_load_previous_messages` 不变；DB `finalize_message` 终态列语义不变。
   - `e2e_helpers.py` 的既定 DB↔Prompt 步骤数一致校验（MUST）继续为绿色。

---

## 五、风险与回退

| 风险 | 评估 | 缓释 |
|------|------|------|
| `start_request` 迁到 `agent_runner` 后，若 bg_task 的 ContextVar 没继承到（`create_task` 不拷贝上下文），日志无法创建 | **低**：`asyncio.create_task` 从 Python 3.7 起默认拷贝当前 `contextvars`；且 9/12 历史运行已证明 log_step_yield 在 bg_task 内读写同一 dict 正常。9/12 = 已证明 ContextVar 传递正确 | 实施后首步可用单测验证：`start_request` → `_get_current_log` → 断言非 None |
| 删除 openai.py 的 `save()` 后，若生产者极端情况下未存盘（如 bg_task 被硬取消先于其 `finally` 的 `save()`），日志丢失 | **低**：生产者 `finally` 必有；`save()` 置于所有 `await` 之后，`bg_task` 正常完成时不会跳过 | 极端关机的日志丢失与修复前同源，不新增暴露面 |
| `save()` 置于 `finally` 末尾，若 `await task_cleanup`（L308）因 `CancelledError` 重抛导致后续 `save()` 跳过 | **低**：断流场景取消的是消费者协程，非 bg_task；bg_task 正常跑完，`task_cleanup`（L308）成功 | `save()` 已处置于 `buffer.done.set()`(L312) 之后，为 finally 最后步骤 |

**回退**：本修复为纯逻辑迁移（创建权从 openai.py 到 agent_runner）+ 删冗余调用（消费者 5 处删除）+ 删谎报分支。无数据迁移、无前端变化。如异常，`git revert` 对应 3 文件（agent_runner.py / openai.py / prompt_logger.py）的提交即可。

---

## 六、代码改动清单（diff 格式，复核3遍）

> 编写人：小欧　|　时间：2026-07-18 14:05:00
> 
> 修改文件总数：**3个**（agent_runner.py / openai.py / prompt_logger.py），纯删除+纯新增，不改已有逻辑。

---

### 6.1 文件一：`backend/app/services/agent/agent_runner.py`（+2处）

#### 改动 A-1：函数体开始处新增 `start_request`（+1行）

**位置**：`run_agent_in_background` 函数体，`buffer = agent_streams.get(task_id)` 之后、`try` 之前（L78之后、L113之前）

**复核第1遍**：确认插入位置在 `current_execution_steps` 初始化之后、`try` 之前，此时 `last_message` 和 `session_id` 参数已可用。

**复核第2遍**：确认 `get_prompt_logger()` 已在 L44 import，无需新增 import。

**复核第3遍**：确认 `start_request` 内部调用 `get_user_message_id(session_id)` 在后台任务中可访问 DB（与 L160-161 的 `db.get_conn("chat")` 同环境）。

```diff
     buffer = agent_streams.get(task_id)
     current_execution_steps: List[Dict] = []
     end_type = "unknown"
     ai_message_id: Optional[int] = None  # 首步分配后复用 — 小欧 2026-07-14
 
+    # [新] 生产者全权拥有 prompt-log 生命周期 — 小欧 2026-07-18
+    get_prompt_logger().start_request(last_message, session_id)
+
     async def _append(event_dict: Dict) -> None:
```

**验证**：`start_request` 创建 `_current_log` dict 并存入 ContextVar；后续 `log_step_yield`（L89）和 `update_ai_message_id`（L162）读写同一 ContextVar，bg_task 继承调用者上下文（Python 3.7+ `asyncio.create_task` 默认拷贝），9/12 历史运行已证明传递正确。

---

#### 改动 A-2：finally 块末尾新增 `set_terminal_status` + `save()`（+5行）

**位置**：`finally` 块最末尾，`buffer.done.set()`（L312）之后、`reclaim_stream_buffer`（L318）之前

**复核第1遍**：确认 `_terminal_status` 已在 L279 由 `_STATUS_MAP.get(end_type, "failed")` 推导，值集为 `completed/failed/cancelled/paused`，与 `_label_map` 一一映射。

**复核第2遍**：确认 `save()` 置于所有 `await` 之后（最后的 `await` 是 L308 `await task_cleanup`），正常路径不会被 `CancelledError` 重抛跳过。

**复核第3遍**：确认 `update_ai_message_id` 在循环首步（L162）已调用，`save()` 时 `AI消息ID` 已就绪；`current_execution_steps` 此刻必含终态 FinalStep（守卫 L228-258 已补记）。

```diff
         # 标记生产者结束，唤醒消费者；延迟回收缓冲以支持重连窗口 — 小欧 2026-07-12
         if buffer is not None:
             buffer.done.set()
             # 必须持锁调 notify_all(同 _append), 否则 RuntimeError — 小欧 2026-07-13
             async with buffer.cond:
                 buffer.cond.notify_all()
+
+            # [新] 生产者权威存盘：终态 FinalStep 已由上方守卫补记(_fd)，
+            #      此刻 current_execution_steps 必含终态。 — 小欧 2026-07-18
+            _pl = get_prompt_logger()
+            _label_map = {"completed": "已完成", "failed": "异常终止",
+                          "cancelled": "已取消", "paused": "已暂停"}
+            _pl.set_terminal_status(_label_map.get(_terminal_status, "异常终止"))
+            _pl.save()
+
             try:
                 loop = asyncio.get_event_loop()
                 loop.call_later(300, lambda: reclaim_stream_buffer(task_id))
```

**验证**：`_terminal_status` 来源链：`agent.status` → `end_type`（L261-269）→ `_terminal_status`（L279）→ `_label_map.get()` → `set_terminal_status()`。`save()` 写文件时 `_current_log` dict 已含完整 `步骤产出`（含终态 final）+ 准确 `状态`。

---

### 6.2 文件二：`backend/app/api/v1/chat/openai.py`（-5处）

#### 改动 B-1：删除 import（-1行）

**位置**：L41

**复核第1遍**：确认 `prompt_logger` 在删除后不再被任何代码引用（全文搜索确认 L41/L199/L200/L246/L253/L255-257 共6处，删除后0引用）。

**复核第2遍**：确认 `get_prompt_logger` 仅在此文件 L41 import，删除后不影响其他模块。

**复核第3遍**：确认 `from app.logger.prompt_logger import get_prompt_logger` 删除后，`agent_runner.py` 的 L44 import 不受影响（独立 import 语句）。

```diff
- from app.logger.prompt_logger import get_prompt_logger
```

---

#### 改动 B-2：删除 `start_request` 调用（-2行）

**位置**：L199-200

**复核第1遍**：确认 `prompt_logger = get_prompt_logger()` 和 `prompt_logger.start_request(user_input, session_id)` 整体删除，日志创建权移至 `agent_runner.py`。

**复核第2遍**：确认 `user_input` 在 `agent_runner` 中对应参数名 `last_message`，值相同（`openai.py:238` 传 `user_input` 作为 `run_agent_in_background` 的 `last_message` 参数）。

**复核第3遍**：确认删除后 `generate()` 函数内不再有任何 `prompt_logger` 变量引用（后续 L246/L253/L255 一并删除）。

```diff
-        prompt_logger = get_prompt_logger()
-        prompt_logger.start_request(user_input, session_id)
```

---

#### 改动 B-3：删除 `mark_completed` 调用（-1行）

**位置**：L246（`else:` 分支，SSE 正常结束）

**复核第1遍**：确认此行在 `async for sse_chunk in _stream_with_control(...)` 的 `else` 分支，即 SSE 正常结束时调用。删除后状态由 `agent_runner.finally` 的 `set_terminal_status` 按真实终态设置。

**复核第2遍**：确认 `else` 分支仅在 SSE 流正常结束时执行；若客户端断流走 `except CancelledError`，此分支不执行。删除不影响断流路径。

**复核第3遍**：确认删除后 `else:` 分支变为空块，需保留 `pass` 或删除整个 `else` 块。此处选择删除整个 `else` 块（`else:` + 缩进行），保留 SSE 循环后的逻辑流。

```diff
             async for sse_chunk in _stream_with_control(buffer, task_id, next_step, session_id, execution_steps, state):
                 yield sse_chunk
-            else:
-                prompt_logger.mark_completed()
```

---

#### 改动 B-4：删除 `mark_error` 调用（-1行）

**位置**：L253（`except Exception` 分支）

**复核第1遍**：确认此行在 `except Exception as e:` 分支内，`yield create_error_response(...)` 之前。删除后错误状态由 `agent_runner.py:199-223` 的异常分支设置 `set_failed(agent)` + `FinalStep(outcome="failed")`。

**复核第2遍**：确认删除后 `except Exception` 分支仅保留 `logger.error` + `yield create_error_response`，SSE 流正常返回错误响应。

**复核第3遍**：确认 `mark_error` 设置的 `"异常终止"` 状态和 `"错误信息"` 字段，在修复后由 `agent_runner.finally` 的 `set_terminal_status("异常终止")` + `FinalStep(error_type=..., error_message=...)` 完整覆盖。

```diff
         except Exception as e:
             logger.error(f"[chat_stream] Error: {e}", exc_info=True)
-            prompt_logger.mark_error(str(e))
             yield create_error_response(error_type="router_error", error_message=f"路由异常: {str(e)}")
```

---

#### 改动 B-5：删除 `save()` 调用（-3行）

**位置**：L255-257（`finally` 块）

**复核第1遍**：确认 `finally: prompt_logger.save()` 整体删除。存盘权移至 `agent_runner.finally` 末尾。

**复核第2遍**：确认删除后 `finally` 块变为空块（原注释 L256 已说明"生命周期清理已由生产者负责"），保留 `pass` 或删除整个 `finally` 块。此处保留空 `finally` 结构（Python 语法允许空 finally，但更佳做法是删除整个 finally 块）。

**复核第3遍**：确认删除后客户端断流时 `except CancelledError: return` 直接退出，不再提前存盘。生产者后台继续跑完，其 `finally` 末尾 `save()` 才是权威存盘点。

```diff
         except asyncio.CancelledError:
             logger.info(f"[chat_stream] 客户端断开(task={task_id})，agent 后台继续")
             return
         except Exception as e:
             logger.error(f"[chat_stream] Error: {e}", exc_info=True)
             yield create_error_response(error_type="router_error", error_message=f"路由异常: {str(e)}")
-        finally:
-            # 生命周期清理已由生产者 run_agent_in_background 负责，此处仅保存 prompt 日志
-            prompt_logger.save()
```

**删除后效果**：`generate()` 函数内不再有任何 `prompt_logger` 引用。SSE 流处理归 SSE 流处理，日志归生产者。

---

### 6.3 文件三：`backend/app/logger/prompt_logger.py`（-6行 + 新增方法）

#### 改动 C-1：删除 `save()` 内状态谎报升级分支（-6行）

**位置**：`save()` 方法内 L471-476

**复核第1遍**：确认删除的6行代码：`status = ...` / `if status == "处理中":` / `if current_log.get("LLM调用记录"):` / `current_log["基本信息"]["状态"] = "已完成"` / `else:` / `current_log["基本信息"]["状态"] = "异常终止"`。删除后 `save()` 直接进入文件写出逻辑。

**复核第2遍**：确认删除后 `save()` 不再修改 `状态` 字段——状态由 `agent_runner.finally` 的 `set_terminal_status` 在调 `save()` 前已设好。`save()` 只负责写出当前状态。

**复核第3遍**：确认删除后 `save()` 的文件写出逻辑（L478-500）不受影响：`ai_id` 读取、`filename` 生成、`safe_json_dumps` 写入均保持不变。

```diff
     def save(self):
         """保存日志到文件 — 文件名用ai_message_id生成 — 小欧 2026-06-23"""
         current_log = self._get_current_log()
         if not current_log:
             logger.warning("[PromptLogger] 保存失败:没有当前日志数据")
             return
 
-        status = current_log["基本信息"].get("状态", "处理中")
-        if status == "处理中":
-            if current_log.get("LLM调用记录"):
-                current_log["基本信息"]["状态"] = "已完成"
-            else:
-                current_log["基本信息"]["状态"] = "异常终止"
-
         # 从日志数据中取ai_message_id,生成最终文件名
         ai_id = current_log["基本信息"].get("AI消息ID")
```

---

#### 改动 C-2：新增 `set_terminal_status` 方法（+7行）

**位置**：`mark_error` 方法之后（L462之后）、`save` 方法之前（L464之前）

**复核第1遍**：确认方法签名 `(self, label: str)` 与 `mark_completed()`/`mark_error()` 同构（DRY），接收状态标签字符串。

**复核第2遍**：确认方法体仅设置 `基本信息.状态`，与 `mark_completed()`/`mark_error()` 行为一致（单字段赋值），符合 SRP。

**复核第3遍**：确认 `label` 值集：`"已完成"` / `"异常终止"` / `"已取消"` / `"已暂停"`，与 `_label_map`（agent_runner.py）一一映射，与现有 `mark_completed` 的 `"已完成"` 和 `mark_error` 的 `"异常终止"` 字符串相同，无兼容风险。

```diff
     def mark_error(self, error_msg: str):
         """标记请求异常终止 — 小欧 2026-06-30"""
         current_log = self._get_current_log()
         if current_log:
             current_log["基本信息"]["状态"] = "异常终止"
             current_log["基本信息"]["错误信息"] = error_msg
 
+    def set_terminal_status(self, label: str) -> None:
+        """由生产者按真实终态设状态标签（"已完成"/"异常终止"/"已取消"/"已暂停"）— 小欧 2026-07-18"""
+        current_log = self._get_current_log()
+        if current_log:
+            current_log["基本信息"]["状态"] = label
+
     def save(self):
```

---

### 6.4 改动汇总（3文件 / 8处改动 / +8行 -13行）

| 文件 | 改动 | 类型 | 行数变化 |
|------|------|------|----------|
| `agent_runner.py` | A-1: 新增 `start_request` | 新增 | +3 |
| `agent_runner.py` | A-2: 新增 `set_terminal_status` + `save()` | 新增 | +6 |
| `openai.py` | B-1: 删除 import | 删除 | -1 |
| `openai.py` | B-2: 删除 `start_request` 调用 | 删除 | -2 |
| `openai.py` | B-3: 删除 `mark_completed` 调用 | 删除 | -2 |
| `openai.py` | B-4: 删除 `mark_error` 调用 | 删除 | -1 |
| `openai.py` | B-5: 删除 `save()` 调用 | 删除 | -3 |
| `prompt_logger.py` | C-1: 删除状态谎报分支 | 删除 | -6 |
| `prompt_logger.py` | C-2: 新增 `set_terminal_status` 方法 | 新增 | +7 |
| **合计** | | | **+16 -15** |

---

### 6.5 功能零丢失逐项核对

| 功能点 | 修复前 | 修复后 | 是否退化 |
|--------|--------|--------|----------|
| SSE 流正常 | `_stream_with_control` → `stream_reader` → yield | 不变 | ✅ 无退化 |
| 断线重连 | `chat_stream_reconnect` 读同一 `buffer.event_log` | 不变（不依赖 prompt-log） | ✅ 无退化 |
| 多轮对话 | `_load_previous_messages` 读 DB | 不变 | ✅ 无退化 |
| DB 终态列 | `finalize_message` 写 `status` | 不变（agent_runner L288） | ✅ 无退化 |
| DB 步骤表 | `append_execution_step` 逐步入库 | 不变（agent_runner L163-168） | ✅ 无退化 |
| prompt-log 步骤 | `log_step_yield` 在 `_append` 内 | 不变（agent_runner L89） | ✅ 无退化 |
| prompt-log 终态 | 3/12 缺 final | 全部有 final | ✅ **增强** |
| prompt-log 状态 | 谎报"已完成" | 如实 | ✅ **增强** |
| 日志层与 HTTP 层 | 耦合（openai.py 管日志） | 解耦（openai.py 不碰日志） | ✅ **增强** |

---

> 结论：病根为 **"prompt-log 的生命周期错配——消费者（openai.py）创建并存盘但不拥有运行周期，生产者（agent_runner）写入步骤但不拥有日志归属"**，本质违反 SRP + KISS-DIRECT + SLAP + OCP 四条规范。已用 12 个会话真实日志 + app 运行轨迹 5 重实证坐实。修复方法：**生产者全权拥有日志全部生命周期（创建→写入→设态→存盘），消费者完全退出日志层**，符合 SRP / KISS-DIRECT / SLAP / OCP / YAGNI / 禁止 backward / 复用优先，增强"终态必落盘+状态如实+日志层与 HTTP 层解耦"，不丢失 SSE/DB/重连任何功能。待北京老陈批准后由小沈/小欧实施。
