# Agent 状态管理重构设计方案

**创建时间**: 2026-06-28 23:40:40  
**更新时间**: 2026-06-28 23:47:48  
**版本**: v1.2  
**作者**: 小欧  
**设计目标**: handler 零接触状态，react_cycle 唯一负责状态流转

---

## 版本记录

| 版本 | 时间 | 更新内容 | 作者 |
|------|------|---------|------|
| v1.0 | 2026-06-28 23:40:40 | 初始版本，完整设计方案 A/B | 小欧 |
| v1.1 | 2026-06-28 23:55:00 | 删除方案A，方案B 精炼为唯一方案，章节重新编号，补充风险分析和实施步骤 | 小欧 |
| v1.2 | 2026-06-28 23:47:48 | 追加详细设计 v2：逐文件代码规格，9 个文件的完整改动定义 | 小欧 |

---

## 一、背景与问题

### 1.1 当前问题

Agent 状态赋值分散在 10 处、6 个文件中，无统一入口、无合法转换校验：

| 文件 | 行号 | 当前写法 | 问题 |
|------|------|---------|------|
| `base_agent.py` | 53 | `self.status = AgentStatus.IDLE` | 初始化，可保留 |
| `base_agent.py` | 98 | `self.status = AgentStatus.FAILED` | 在 set_failed 内部，OK |
| `base_agent.py` | 104 | `self.status = AgentStatus.COMPLETED` | 在 set_completed 内部，OK |
| `react_cycle.py` | 188 | `agent.status = AgentStatus.CANCELLED` | 直接赋值 |
| `react_cycle.py` | 281 | `agent.status = AgentStatus.EXECUTING` | 直接赋值 |
| `react_cycle.py` | 295 | `agent.status = AgentStatus.THINKING` | 直接赋值 |
| `initialize_run_state.py` | 60 | `agent.status = AgentStatus.THINKING` | 直接赋值 |
| `step_emitter.py` | 32 | `self.agent.status = AgentStatus.RETRYABLE_ERROR` | 直接赋值 |
| `run_sse_stream.py` | 212 | `agent.status = AgentStatus.CANCELLED` | 直接赋值 |
| `run_sse_stream.py` | 228 | `agent.status = AgentStatus.FAILED` | 直接赋值 |

此外，handler 层直接调 `agent.set_failed()` 和 `agent.set_completed()`，绕过了编排层的控制。

### 1.2 根因分析

**根因1：无状态机**。没有合法转换表，任何代码可以在任何时候设任意状态。代码层没有契约约束，程序员只能靠记忆和文档来避免误用。

**根因2：无唯一入口**。状态赋值没有集中管控，谁想设就设。改了 A 处的状态，B 处又在另一个分支改，两处逻辑冲突时只能在运行时暴露。

**根因3：层次混淆**。状态管理本质上是编排层的职责，但 handler（执行层）、step_emitter（工具层）、run_sse_stream（运输层）都在设状态。每一层的改动都可能无意中改变状态流转逻辑。

**根因4：无非法转换检测**。例如从 `IDLE` 直接到 `COMPLETED` 不会报错，只在运行时产生奇怪的行为。状态转换的错误在 agent 行为异常时才被发现，定位成本高。

### 1.3 设计目标

| 目标 | 说明 | 验收标准 |
|------|------|---------|
| **零处直接赋值** | 不允许 `agent.status = X` 出现在业务代码中 | grep 'agent\.status\s*=' 返回仅 __init__ 一行 |
| **统一入口** | 所有状态变更必须经过 `status_table.set_status()` | 所有调用均通过 import 的函数 |
| **合法转换校验** | 运行时检测非法转换，提前暴露错误 | 非法转换时抛 `ValueError`，500ms 内可定位 |
| **层次隔离** | handler 不碰状态，编排层唯一负责状态流转 | handler 代码中无 `set_failed`/`set_completed`/`status=` 调用 |
| **测试不改** | handler 测试协议保持不变，仅调整 Mock 方式 | 测试通过率 100%，不改 handler 测试的业务逻辑 |

### 1.4 设计原则

本方案遵守以下原则：

| 原则 | 在本方案中的体现 |
|------|----------------|
| **SRP — 单一职责** | `status_table.py` 只做一件事：管理状态转换。不处理 SSE 事件、不处理 DB、不处理 LLM 调用 |
| **KISS-DIRECT — 简单直接** | 函数式，不用类。`set_status(agent, new_status)` — 3 行代码内部逻辑。直来直去，没有中间层 |
| **SLAP — 同一抽象层** | `react_cycle.py` 编排状态流转（高层），不混入 `agent.status = X` 的底层实现。底层实现封装在 `status_table.py` |
| **YAGNI — 不过度设计** | 不加注册表、不加回调、不加事件总线。当前只需要一个状态转换校验 + 四个导出函数 |
| **禁止 backward** | 旧代码全部改，不保留 `base_agent.set_failed()` 兼容方法。一次性彻底迁移，不存在新旧两套并存的过渡期 |

---

## 二、方案B：handler 零接触状态

### 2.1 架构总览

```
┌─────────────────────────────────────────────────────────────┐
│                       运输层                                  │
│    run_sse_stream.py                                         │
│    ┌─ 捕获外部异常 → 调 set_failed/set_cancelled            │
│    └─ 正常流程：不做任何状态操作                               │
├─────────────────────────────────────────────────────────────┤
│                       编排层                                  │
│    react_cycle.py                                            │
│    ┌─ run_react_cycle() — 主循环，唯一设状态的地方             │
│    ├─ _process_single_step() — 调度 handler，据结果设状态    │
│    └─ _dispatch_handler() — 分发 handler，收集返回结果       │
├─────────────────────────────────────────────────────────────┤
│                       执行层                                  │
│    handlers/answer_handler.py                                │
│    handlers/action_handler.py    ← 只返回结果 dict，不碰状态  │
│    error_handler.py                                          │
│    step_emitter.py                                           │
├─────────────────────────────────────────────────────────────┤
│                       状态机                                  │
│    status_table.py                                           │
│    ┌─ _TRANSITIONS — 合法转换表（数据）                      │
│    └─ 4 个导出函数：set_status/set_failed/set_completed/     │
│                          set_cancelled （函数）               │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 合法转换表

```
IDLE        → THINKING                     [启动 agent]
THINKING    → EXECUTING                    [LLM 返回工具调用]
THINKING    → COMPLETED / FAILED           [LLM 返回最终答案 / LLM 返回空]
EXECUTING   → THINKING                     [工具执行完，需要继续思考]
EXECUTING   → COMPLETED / FAILED           [工具 return_direct / 工具执行失败]
CANCELLED   → (终态，不可转换)
COMPLETED   → (终态，不可转换)
FAILED      → (终态，不可转换)
```

**终态不可转换的含义**：一旦 agent 进入 CANCELLED、COMPLETED、FAILED 之一，任何后续调 `set_status` 都会抛 `ValueError`。这意味着 react_cycle 的 while 循环会在下一次循环判断时 break，不会再次尝试。

**数据表定义**：

```python
_TRANSITIONS = {
    AgentStatus.IDLE:      {AgentStatus.THINKING},
    AgentStatus.THINKING:  {AgentStatus.EXECUTING, AgentStatus.COMPLETED, AgentStatus.FAILED},
    AgentStatus.EXECUTING: {AgentStatus.THINKING, AgentStatus.COMPLETED, AgentStatus.FAILED},
    AgentStatus.CANCELLED: set(),
    AgentStatus.COMPLETED: set(),
    AgentStatus.FAILED:    set(),
}
```

### 2.3 三层职责边界

| 层级 | 文件 | 职责 | 能否改状态 |
|------|------|------|-----------|
| **运输层** | `run_sse_stream.py` | SSE 收发、DB 存取、用户取消、捕获外部异常 | ❌ 正常流程不能。仅在用户取消时调 `set_cancelled`、捕获到顶层未预期异常时调 `set_failed` |
| **编排层** | `react_cycle.py` | 主循环调度、根据 handler 返回结果设状态、异常兜底 | ✅ 唯一正常设状态的地方 |
| **执行层** | `handlers/answer_handler.py` | 处理 LLM 返回的 final answer，生成 ThoughtStep/FinalStep | ❌ 绝对不能，只能返回结果 dict |
| **执行层** | `handlers/action_handler.py` | 处理 LLM 返回的工具调用，生成 ThoughtStep/ActionStep/ObservationStep | ❌ 绝对不能，只能返回结果 dict |
| **执行层** | `step_emitter.py` | 创建 ErrorStep/ObservationStep/FinalStep 等步骤对象 | ❌ `exit_with_error` 不设状态，只创建 ErrorStep |
| **执行层** | `error_handler.py` | 处理 LLM 解析错误、网络异常等 | ❌ 不设状态，只创建/返回 ErrorStep |
| **状态机** | `status_table.py` | 唯一改得动 `agent.status` 的地方，提供合法转换校验 | ✅ 唯一物理上改属性的地方 |

**运输层（run_sse_stream.py）的例外说明**：
- 用户取消（`KeyboardInterrupt` 或前端发取消信号）：这是运输层的直接责任，它持有连接上下文，不能等到编排层去处理。允许调 `set_cancelled`
- 顶层未预期异常：例如数据库连接断开、LLM 客户端 HTTP 错误等。这些发生在编排层之外，运输层捕获后调 `set_failed`
- 正常流程（无取消、无异常）下，运输层不做任何状态操作

### 2.4 Handler 返回协议

#### 2.4.1 协议定义

handler 不再调任何 `set_xxx` 函数，改为在 yield 完所有事件后，通过 async generator 的 `return` 机制返回一个结果 dict：

```python
HandlerResult = {
    "action":   "continue" | "complete" | "fail",
    "response": str,          # 最终回复内容（complete 时）
    "error_msg": str,         # 错误消息（fail 时）
    "error_type": str,        # 错误类型（fail 时）
    "step": ErrorStep | None, # 已创建的 ErrorStep（fail 时）
}
```

#### 2.4.2 返回规则矩阵

| action | 含义 | 触发场景 | 携带字段 | 编排层的响应 |
|--------|------|---------|---------|-------------|
| `"continue"` | 需要继续循环 | 工具调用执行完后，需要让 LLM 继续思考 | — | 不设状态，继续下一轮 while 循环 |
| `"complete"` | 任务正常完成 | LLM 返回 final answer；工具 return_direct 完成 | `response` | `set_completed(agent)` → break |
| `"fail"` | 任务失败 | LLM 返回空内容；工具执行失败；解析错误 | `error_msg`, `error_type`, `step` | `set_failed(agent, error_msg)` → break |
| `"cancelled"` | 用户取消 | 编排层检测到取消标志（当前 react_cycle 已有） | — | `set_cancelled(agent)` → break |

**注意**：`"cancelled"` 目前已经在 react_cycle 中处理（line 188），不是 handler 返回的。handler 不需要返回 `"cancelled"`。

#### 2.4.3 为什么用 async generator return 而不是 yield 一个特殊 step

Python 3.6+ 的 async generator 支持 `return value` 语法，调用方通过 `StopAsyncIteration` 异常的 `.value` 属性获取。

这里不使用在末尾 yield 一个 MetaStep 的原因：

| 方案 | 问题 | 结论 |
|------|------|------|
| yield HandlerResultStep | SSE 流中混入非业务事件，前端需要特殊处理 | ❌ 不适合 |
| yield MetaStep(type="handler_result") | 同上，且需要新增 MetaStep 类型 | ❌ 过度设计 |
| async generator return | Python 原生机制，不产生额外事件流，调用方天然知晓 handler 已结束 | ✅ 选择本方案 |

### 2.5 异常兜底策略

当编排层（react_cycle）调用 handler 的过程中出现未预期异常时，编排层自身负责兜底：

```
编排层捕获异常
    → 创建 ErrorStep（含异常信息）
    → yield ErrorStep（给前端看）
    → set_failed(agent, str(error))（设状态）
    → 下一次 while 循环判断时 break
```

这意味着，即使 handler 内部崩溃了，状态流转仍然是可控的：一定经过 `set_failed`，一定是合法转换，一定不会出现悬空状态。

### 2.6 RETRYABLE_ERROR 的处理

**RETRYABLE_ERROR** 在方案B 中被**彻底删除**，原因：

| 论据 | 说明 |
|------|------|
| 历史原因 | RETRYABLE_ERROR 原本用于 FCFormatError/NetworkError 的重试，但这些错误在 llm_stream 内部已经处理了，外部代码永远接不到 |
| 当前使用 | `exit_with_error` 中设 RETRYABLE_ERROR 但 `recoverable=True` 的调用方目前为零 |
| 状态机纯净性 | RETRYABLE_ERROR 既不是终态也不是中间态，循环中需要特殊判断，增加了复杂度 |
| 替代方案 | 如果未来需要 recoverable 逻辑，应该在编排层检查 ErrorStep 的 recoverable 元数据，而不是通过 agent status |

具体删除内容：

| 文件 | 删除内容 |
|------|---------|
| `step_emitter.py:32` | `if recoverable: self.agent.status = AgentStatus.RETRYABLE_ERROR` |
| `react_cycle.py:294-295` | `if agent.status == AgentStatus.RETRYABLE_ERROR: agent.status = AgentStatus.THINKING; continue` |
| `react_cycle.py:327` | `if agent.status != AgentStatus.RETRYABLE_ERROR:` 条件判断 |

`AgentStatus.RETRYABLE_ERROR` 枚举值保留（不删除枚举），以防其他地方引用导致编译错误。但不再被任何业务代码设置或判断。

---

## 三、文件改动说明

### 3.1 新建：`status_table.py`

**路径**: `backend/app/services/agent/core_agent/status_table.py`

**职责**: 函数式状态机，唯一能改得动 `agent.status` 的地方。纯函数 + 数据表，不用类。

**函数签名**：

```python
def set_status(agent, new_status: AgentStatus, reason: str = "") -> None:
    """
    唯一改得动 agent.status 的函数。
    
    参数：
        agent: UniversalAgent 实例（必须）
        new_status: 要转换到的目标状态（必须）
        reason: 状态变更原因，非空时输出日志（可选）
    
    异常：
        ValueError: 当转换不合法时抛出
    
    使用示例：
        set_status(agent, AgentStatus.EXECUTING)
        set_status(agent, AgentStatus.EXECUTING, "准备执行工具调用")
    """

def set_failed(agent, reason: str = "") -> None:
    """快捷函数：设 FAILED"""

def set_completed(agent) -> None:
    """快捷函数：设 COMPLETED"""

def set_cancelled(agent) -> None:
    """快捷函数：设 CANCELLED"""
```

**内部逻辑**（`set_status`）：

```
1. 从 _TRANSITIONS 中查找 agent.status → 允许的目标集合
2. 若 new_status not in allowed：
   抛 ValueError(f"非法状态转换: {current} → {new_status}")
3. 若合法：
   agent.status = new_status
4. 若 reason 非空：
   logger.info(f"[Agent] {agent.status}: {reason}")
```

**日志格式**：

```
[Agent] AgentStatus.EXECUTING: 准备执行工具调用
[Agent] AgentStatus.FAILED: LLM返回空内容
```

日志级别用 INFO，因为这是正常流程的一部分，不是错误。只有底层的状态流转日志，不记录业务详情（业务详情由调用方记录）。

### 3.2 修改：`base_agent.py`

**改动内容**：删除三个方法

| 当前方法 | 操作 |
|---------|------|
| `set_failed(self, reason="")` | **删除**。所有调用方改为 `from status_table import set_failed; set_failed(agent, reason)` |
| `set_completed(self)` | **删除**。所有调用方改为 `from status_table import set_completed; set_completed(agent)` |
| `set_cancelled(self)` | **删除**。所有调用方改为 `from status_table import set_cancelled; set_cancelled(agent)` |

**保留的内容**：

| 行号 | 代码 | 保留原因 |
|------|------|---------|
| 53 | `self.status = AgentStatus.IDLE` | 初始化赋值，不是状态流转。没有 agent 实例之前无法调 set_status |
| — | `_create_cancelled_chunk()` | 与状态管理无关，属于 SSE 消息格式 |

**为什么不保留委托方法？**

方案B 的设计目标是 handler 零接触状态。如果保留 `base_agent.set_failed()` 委托方法，handler 仍然可以调它，实际上就绕过了"handler 不碰状态"的原则。为了防止 handler 开发者误用，必须彻底删除，让 `from status_table import set_failed` 成为唯一方式。这叫做"消除默认路径"（remove the obvious way to do it wrong）。

### 3.3 修改：`answer_handler.py`

**路径**: `backend/app/services/agent/core_agent/handlers/answer_handler.py`

**当前行为**：
- LLM 返回 final answer 时，在 yield 完所有事件后调 `agent.set_completed()`
- LLM 返回空内容时，调 `agent.set_failed("LLM返回空内容")`

**改为**：

```diff
  # 当前代码（两种路径）：
  
  # 路径1：空内容
- agent.set_failed("LLM返回空内容")
+ return {"action": "fail", "error_msg": "LLM返回空内容", "error_type": "empty_response"}
  
  # 路径2：正常完成
- agent.set_completed()
+ return {"action": "complete", "response": content}
```

**改动影响**：
- handler 签名从 `async generator → None` 变为 `async generator → dict`
- handler 内部的 yield 逻辑完全不变
- 仅末尾的 `set_xxx` 改为 `return {dict}`
- 测试需要捕获 handler 的返回值并验证

### 3.4 修改：`action_handler.py`

**路径**: `backend/app/services/agent/core_agent/handlers/action_handler.py`

**当前行为**：
- 工具 return_direct 完成时，在 yield 完所有事件后调 `agent.set_completed()`

**改为**：

```diff
  # 当前代码：
- agent.set_completed()
+ return {"action": "complete", "response": _status.get("message", "")}
```

### 3.5 修改：`error_handler.py`

**路径**: `backend/app/services/agent/core_agent/error_handler.py`

**当前行为**：
- 所有 `_handle_*` 函数在创建 ErrorStep 后调 `agent.set_failed(str(error))`
- 包括：`_handle_fc_format_error`、`_handle_network_error`、`_handle_empty_response`、`_handle_max_retries` 等

**改为**：
- 所有 `_handle_*` 函数不再调 `set_failed`，只返回 ErrorStep 列表
- 调用方 `react_cycle.py` 负责在收到 ErrorStep 后调 `set_failed`

**具体改动**：

```diff
  def _handle_fc_format_error(agent, error: FCFormatError):
      step = ErrorStep(error=str(error), ...)
-     agent.set_failed(str(error))
      return [step]
  
  def _handle_network_error(agent, error: NetworkError):
      step = ErrorStep(error=str(error), ...)
-     agent.set_failed(str(error))
      return [step]
  
  # ... 其余 _handle_* 函数同理
```

```diff
  # handle_react_error 入口函数（最外层的统一入口）：
  def handle_react_error(agent, error: Exception) -> List[Step]:
      # ... 内部 dispatch 到 _handle_* ...
-     agent.set_failed(str(error))
+     # 只返回 ErrorStep 列表，不设状态
+     return steps
```

### 3.6 修改：`step_emitter.py`

**路径**: `backend/app/services/agent/core_agent/step_emitter.py`

**当前方法** — `exit_with_error`：

```python
def exit_with_error(self, error_message, error_type="general", recoverable=False):
    if recoverable:
        self.agent.status = AgentStatus.RETRYABLE_ERROR
    else:
        self.agent.set_failed(error_message)
    return ErrorStep(error=error_message, type=error_type)
```

**改为**：

```python
def exit_with_error(self, error_message, error_type="general", recoverable=False):
    # recoverable 参数保留（预留），但在此处不设任何状态
    # 调用方（react_cycle）负责在收到 ErrorStep 后调 set_failed
    return ErrorStep(error=error_message, type=error_type)
```

**改动说明**：
- `exit_with_error` 只创建并返回 ErrorStep，不再修改 `agent.status`
- 调用方看到 ErrorStep 后，自行决定是否调 `set_failed`
- `recoverable` 参数保留不动，仅供未来扩展（当前所有调用方传 `recoverable=False`）

### 3.7 修改：`react_cycle.py`

**路径**: `backend/app/services/agent/core_agent/react_cycle.py`

这是改动最核心的文件。方案B 的所有变化在此汇总。

#### 3.7.1 import 变更

```diff
+ from app.services.agent.core_agent.status_table import (
+     set_status, set_failed, set_completed, set_cancelled,
+ )
```

#### 3.7.2 `_dispatch_handler` 方法 — 改为收集 handler 返回值

**当前**（async generator，内部 handler 直接设状态）：

```python
async def _dispatch_handler(self, agent, llm_response, chunk_buffer):
    parsed_type = llm_response.get("type", "answer")
    if parsed_type == "action":
        async for event in self._handle_action(agent, llm_response, chunk_buffer):
            yield event
    elif parsed_type == "answer":
        async for event in self._handle_answer(agent, llm_response, chunk_buffer):
            yield event
    elif parsed_type == "error":
        content = llm_response.get("content", "")
        agent.set_failed(content or "LLM流式错误")
        yield agent._step_emitter.emit(ErrorStep(error=content or "LLM流式错误"))
    else:
        agent.set_failed(f"LLM返回未知响应类型: {parsed_type}")
        yield agent._step_emitter.emit(FinalStep(...))
```

**改为**（捕获 handler 的返回 dict，error/else 分支直接返回 dict）：

```python
async def _dispatch_handler(self, agent, llm_response, chunk_buffer):
    parsed_type = llm_response.get("type", "answer")
    
    if parsed_type == "action":
        result = None
        try:
            async for event in handle_action(agent, llm_response, chunk_buffer):
                yield event
        except StopAsyncIteration as e:
            result = e.value
        return result
    
    if parsed_type == "answer":
        result = None
        try:
            async for event in handle_answer(agent, llm_response, chunk_buffer):
                yield event
        except StopAsyncIteration as e:
            result = e.value
        return result
    
    if parsed_type == "error":
        content = llm_response.get("content", "")
        yield agent._step_emitter.emit(ErrorStep(error=content or "LLM流式错误"))
        return {"action": "fail", "error_msg": content or "LLM流式错误"}
    
    # 未知类型
    yield agent._step_emitter.emit(FinalStep(
        content=f"LLM返回未知响应类型: {parsed_type}",
    ))
    return {"action": "fail", "error_msg": f"LLM返回未知响应类型: {parsed_type}"}
```

#### 3.7.3 `_process_single_step` — 据 handler 结果设状态

**当前**：

```python
async def _process_single_step(self, agent, chunk_buffer):
    llm_response = await agent.llm_client.chat(
        messages=agent.messages,
        tools=agent.enabled_tool_defs,
    )
    async for event in self._dispatch_handler(agent, llm_response, chunk_buffer):
        yield event
```

**改为**：

```python
async def _process_single_step(self, agent, chunk_buffer):
    llm_response = await agent.llm_client.chat(
        messages=agent.messages,
        tools=agent.enabled_tool_defs,
    )
    
    handler_result = None
    try:
        async for event in self._dispatch_handler(agent, llm_response, chunk_buffer):
            yield event
    except StopAsyncIteration as e:
        handler_result = e.value
    
    if handler_result:
        action = handler_result.get("action")
        if action == "complete":
            set_completed(agent)
        elif action == "fail":
            error_msg = handler_result.get("error_msg", "")
            set_failed(agent, error_msg)
        elif action == "continue":
            pass  # 不设状态，继续循环
```

#### 3.7.4 `run_react_cycle` — 状态赋值替换 + 删除 RETRYABLE_ERROR

**当前直接赋值**（需要替换的行）：

| 行号 | 当前代码 | 改为 |
|------|---------|------|
| 78 | `agent.set_failed(content or "LLM流式错误")` | 已在上层 `_dispatch_handler` 的 error 分支处理，此行删除 |
| 90 | `agent.set_failed(f"LLM返回未知响应类型: {parsed_type}")` | 已在上层 `_dispatch_handler` 的 else 分支处理，此行删除 |
| 174 | `agent.set_failed("LLM返回空响应")` | 改为：`set_failed(agent, "LLM返回空响应")` |
| 188 | `agent.set_cancelled()` | 改为：`set_cancelled(agent)` |
| 222 | `agent.set_failed(f"handler 异常: {e}")` | 改为：`set_failed(agent, f"handler 异常: {e}")` |
| 274 | `agent.set_failed(f"循环异常: {e}")` | 改为：`set_failed(agent, f"循环异常: {e}")` |
| 281 | `agent.status = AgentStatus.EXECUTING` | 改为：`set_status(agent, AgentStatus.EXECUTING)` |
| 288 | `agent.set_failed(str(execute_result) or "工具调用失败")` | 改为：`set_failed(agent, str(execute_result) or "工具调用失败")` |
| 314 | `agent.set_failed(f"步骤异常: {e}")` | 改为：`set_failed(agent, f"步骤异常: {e}")` |

**删除 RETRYABLE_ERROR 相关**：

| 行号 | 当前代码 | 操作 |
|------|---------|------|
| 294 | `if agent.status == AgentStatus.RETRYABLE_ERROR:` | **删除** 这个 if 块 |
| 295 | `agent.status = AgentStatus.THINKING; continue` | **删除** （包含在上行 if 块中） |
| 327 | `if agent.status != AgentStatus.RETRYABLE_ERROR:` | **删除** 条件，直接执行被保护的代码 |

#### 3.7.5 `run_react_cycle` — 异常兜底流程（完整版）

以下是 `run_react_cycle` 方法在方案B 中的整体流程：

```
while agent.status in (THINKING, EXECUTING):
    try:
        if agent.cancelled:
            set_cancelled(agent)
            yield agent._step_emitter.emit(FinalStep(...))
            break
        
        # LLM 调用
        llm_response = llm_client.chat(...)
        if not llm_response:
            set_failed(agent, "LLM返回空响应")
            yield ErrorStep(error="LLM返回空响应")
            break
        
        # 执行工具（如果有）
        if llm_response.get("type") == "action":
            set_status(agent, EXECUTING)
            execute_result = tool_manager.execute(...)
            if execute_result.get("code") != 0:
                set_failed(agent, str(execute_result) or "工具调用失败")
                yield ErrorStep(...)
                break
        
        # 调度 handler（dispatch 已在 _process_single_step 中处理）
        async for event in _process_single_step(...):
            yield event
    
    except CancelledError:
        set_cancelled(agent)
        yield ErrorStep(error="用户取消")
        break
    
    except Exception as e:
        set_failed(agent, f"循环异常: {e}")
        yield ErrorStep(error=str(e))
        break

finally:
    # 确保终态有 FinalStep
    if agent.status == FAILED:
        yield FinalStep(content="任务执行失败")
    _finalize_cycle(agent)
```

### 3.8 修改：`run_sse_stream.py`

**路径**: `backend/app/services/react_sse_wrapper/run_sse_stream.py`

**改动内容**：

```diff
  # 用户取消
- agent.status = AgentStatus.CANCELLED
+ from app.services.agent.core_agent.status_table import set_cancelled
+ set_cancelled(agent)
  
  # 顶层未预期异常
- agent.status = AgentStatus.FAILED
+ from app.services.agent.core_agent.status_table import set_failed
+ set_failed(agent, str(e)[:200])
```

### 3.9 修改：`initialize_run_state.py`

**路径**: `backend/app/services/agent/core_agent/initialize_run_state.py`

**改动内容**：

```diff
- agent.status = AgentStatus.THINKING
+ from app.services.agent.core_agent.status_table import set_status
+ set_status(agent, AgentStatus.THINKING)
```

---

## 四、测试策略

### 4.1 测试改动量评估

| 测试文件 | 改动范围 | 改动量 | 策略 |
|---------|---------|--------|------|
| 直接测 handler 的测试（call handle_answer/handle_action 并验证结果） | handler 返回结果从 None 变成 dict，需要捕获返回值 | **大** | 每个测试末尾加 `StopAsyncIteration` 捕获逻辑或 wrap 一层 helper |
| 通过 react_cycle 测 handler 的测试（mock dispatch） | mock 需要伪造 handler 返回值 | **中** | 改 mock 的 return_value |
| 测 react_cycle 状态流转的测试 | 直接赋值改为调 status_table，Mock 需调整 | **中** | 用 `from status_table import *` 后 patch |
| 测 run_sse_stream 的测试 | import 变化 | **小** | 加 import mock |
| 测 initialize_run_state 的测试 | import 变化 | **小** | 加 import mock |
| `test_batch2_refactor_verification.py` | 源码检查测试需更新状态相关断言 | **小** | 更新断言 |

### 4.2 Handler 测试适配

handler 测试的核心改动：

```python
# 方案A（当前）：
async for event in handle_answer(agent, parsed, chunk_buffer):
    ...  # 验证事件

# 方案B（改为）：
result = None
try:
    async for event in handle_answer(agent, parsed, chunk_buffer):
        ...  # 验证事件（不变）
except StopAsyncIteration as e:
    result = e.value
assert result["action"] == "complete"
assert result["response"] == "预期内容"
```

**helper 函数**（减少重复）：

```python
async def collect_handler(handler_fn, *args, **kwargs):
    """执行 handler，返回 (events, result)"""
    events = []
    result = None
    try:
        async for event in handler_fn(*args, **kwargs):
            events.append(event)
    except StopAsyncIteration as e:
        result = e.value
    return events, result
```

测试中：

```python
events, result = await collect_handler(handle_answer, agent, parsed, chunk_buffer)
assert len(events) == 2
assert result["action"] == "complete"
```

### 4.3 回归测试

| 轮次 | 测试内容 | 预期结果 |
|------|---------|---------|
| 第1轮 | 全部 pytest | 问题归零（向零推进），记录所有失败 |
| 第2轮 | 修复第1轮问题后的全量回归 | 所有之前失败的问题消失 |
| 第3轮 | 最终验证 | passed=全部, failed=0, error=0 |

---

## 五、实施计划

### 5.1 分步实施

本方案分两步实施，每步都确保测试全通过：

**第一步：status_table + 非 handler 清除直接赋值**

| 序号 | 任务 | 涉及文件 | 测试影响 |
|------|------|---------|---------|
| 1.1 | 新建 `status_table.py` | `core_agent/status_table.py` | 无（新文件，无测试） |
| 1.2 | 改 `base_agent.py` — 删 set_failed/set_completed/set_cancelled | `core_agent/base_agent.py` | 极小（import 变化） |
| 1.3 | 改 `react_cycle.py` — 所有 `agent.status = X` 统一调 status_table（仅非 handler 部分） | `core_agent/react_cycle.py` | 中（mock 需调整） |
| 1.4 | 改 `step_emitter.exit_with_error` — 不碰状态 | `core_agent/step_emitter.py` | 小（返回不变，状态已移出） |
| 1.5 | 改 `error_handler` — 所有 `_handle_*` 不设状态 | `core_agent/error_handler.py` | 小（返回不变） |
| 1.6 | 改 `run_sse_stream.py` — 调 set_cancelled/set_failed | `react_sse_wrapper/run_sse_stream.py` | 小 |
| 1.7 | 改 `initialize_run_state.py` — 调 set_status | `core_agent/initialize_run_state.py` | 小 |
| 1.8 | 测试修复 + 全量回归 | `tests/` | 中 |

**第二步：handler 返回协议改造**

| 序号 | 任务 | 涉及文件 | 测试影响 |
|------|------|---------|---------|
| 2.1 | 改 `answer_handler.py` — return dict | `handlers/answer_handler.py` | **大（每个测试都要改）** |
| 2.2 | 改 `action_handler.py` — return dict | `handlers/action_handler.py` | **大** |
| 2.3 | 改 `react_cycle._dispatch_handler` — 捕获 handler 返回值 | `core_agent/react_cycle.py` | 中 |
| 2.4 | 改 `react_cycle._process_single_step` — 据结果设状态 | `core_agent/react_cycle.py` | 中 |
| 2.5 | handler 测试适配 | `tests/` | **大** |
| 2.6 | 全量回归 | `tests/` | 必须归零 |

### 5.2 实施顺序说明

第一步先做，确保"统一入口 + 合法转换校验"的基础设施落地，同时删除执行层的状态赋值（error_handler、step_emitter）。此时 handler 仍然通过 `base_agent.set_failed()`（已改为委托）设状态，测试基本不受影响。

第二步改 handler 返回协议，这是影响最大的部分。handler 从"yield + set_xxx"变为"yield + return dict"，所有 handler 测试需要适配返回值。这一步才真正实现"handler 零接触状态"。

### 5.3 版本号建议

| 步骤 | 版本号 | 说明 |
|------|--------|------|
| 第一步完成后 | PATCH+1 | 基础设施搭建，对外行为不变 |
| 第二步完成后 | MINOR+1 | handler 协议变更，虽对外仍不变，但改动较大 |

---

## 六、风险分析

### 6.1 风险矩阵

| 风险ID | 风险描述 | 概率 | 影响 | 等级 | 缓解措施 |
|--------|---------|------|------|------|---------|
| R001 | handler 改为 return dict 后，遗漏某处 set_xxx 未删除，导致双重设状态 | 中 | 高 | **高** | 第一步 grep 确认 handler 中所有 `set_` 调用，逐处审查 |
| R002 | 异步 generator 的 StopAsyncIteration 异常处理不当，导致 handler 返回值丢失 | 中 | 中 | **中** | 加单元测试验证 handler 返回值传播，测试中 assert result |
| R003 | REACT_CYCLE 的 while 循环中异常兜底路径遗漏 | 低 | 高 | **中** | 枚举 react_cycle 中每个异常路径，补充 set_failed |
| R004 | 测试改动量过大导致实施时间远超预期 | 高 | 低 | **中** | 分两步实施，第一步测试不改，第二步再适配 handler 测试 |
| R005 | 非法转换检测抛 ValueError 导致生产环境异常 | 低 | 中 | **低** | 测试覆盖所有合法流转路径；上线前跑完整回归 |

### 6.2 关键检查项

实施前逐项确认：

- [ ] 所有 handler 的 `agent.set_failed()` / `agent.set_completed()` 是否已全部改为 `return {dict}`
- [ ] `react_cycle._dispatch_handler` 是否所有分支都返回了 dict（包括 error / 未知类型）
- [ ] `exit_with_error` 的所有调用方是否在调用后补了 `set_failed`
- [ ] `error_handler.handle_react_error` 的所有调用方是否在收到 ErrorStep 后调了 `set_failed`
- [ ] `run_react_cycle` 的 while 循环中是否每个异常路径都有 set_failed/set_cancelled
- [ ] grep 'agent\.status\s*=' 是否仅返回 `__init__` 一行
- [ ] grep 'agent\.set_failed' / 'agent\.set_completed' / 'agent\.set_cancelled' 是否返回 0 行

---

## 七、附录

### 7.1 相关文件清单

| 文件 | 操作 | 备注 |
|------|------|------|
| `backend/app/services/agent/core_agent/status_table.py` | 新建 | 函数式状态机 |
| `backend/app/services/agent/core_agent/base_agent.py` | 修改 | 删除 set_failed/set_completed/set_cancelled |
| `backend/app/services/agent/core_agent/react_cycle.py` | 修改 | 核心改动：调 status_table + handler 结果编排 |
| `backend/app/services/agent/core_agent/handlers/answer_handler.py` | 修改 | 返回 dict |
| `backend/app/services/agent/core_agent/handlers/action_handler.py` | 修改 | 返回 dict |
| `backend/app/services/agent/core_agent/error_handler.py` | 修改 | 不设状态 |
| `backend/app/services/agent/core_agent/step_emitter.py` | 修改 | exit_with_error 不设状态 |
| `backend/app/services/react_sse_wrapper/run_sse_stream.py` | 修改 | 调 status_table |
| `backend/app/services/agent/core_agent/initialize_run_state.py` | 修改 | 调 set_status |
| `backend/tests/` | 修改 | 适配 handler 新返回协议 |

### 7.2 决策记录

| 决策项 | 结论 | 理由 |
|--------|------|------|
| 状态机实现方式 | 纯函数 + 数据表，不用类 | SRP/KISS-DIRECT：类带来不必要的抽象，一个函数 + 一个 dict 足以 |
| 合法转换检测时机 | 运行时抛 ValueError | 编译时无法检测状态流转路径，运行时抛异常是唯一可行的方式 |
| handler 返回方式 | async generator return | Python 原生支持，不引入新类型（如 MetaStep），SSE 流不受污染 |
| RETRYABLE_ERROR | 彻底删除 | 当前没有业务场景依赖它，保留只是死代码 |
| base_agent 三个方法 | 彻底删除，不留委托 | 消除 handler 误用的"默认路径" |
| 测试改动策略 | 分两步实施，第一步测试不改 | 降低实施风险，先确保基础设施正确 |

---

## 八、详细设计 v2 — 逐文件代码规格（diff 格式）

**章节说明**: 本章节为代码层级的详细设计 v2，使用 `-`（删除）和 `+`（新增）标记改动内容。实施时严格按此规格执行。

---

### 8.1 新建 `status_table.py`

**路径**: `backend/app/services/agent/core_agent/status_table.py`

**完整代码**：

```python
_TRANSITIONS = {
    AgentStatus.IDLE:      {AgentStatus.THINKING},
    AgentStatus.THINKING:  {AgentStatus.EXECUTING, AgentStatus.COMPLETED, AgentStatus.FAILED},
    AgentStatus.EXECUTING: {AgentStatus.THINKING, AgentStatus.COMPLETED, AgentStatus.FAILED},
    AgentStatus.CANCELLED: set(),
    AgentStatus.COMPLETED: set(),
    AgentStatus.FAILED:    set(),
}

def set_status(agent, new_status, reason=""):
    allowed = _TRANSITIONS.get(agent.status, set())
    if new_status not in allowed:
        raise ValueError(f"非法转换: {agent.status} → {new_status}")
    agent.status = new_status
    if reason:
        logger.info(f"[Agent] {agent.status}: {reason}")

def set_failed(agent, reason=""):  set_status(agent, AgentStatus.FAILED, reason)
def set_completed(agent):          set_status(agent, AgentStatus.COMPLETED)
def set_cancelled(agent):          set_status(agent, AgentStatus.CANCELLED)
```

---

### 8.2 修改 `base_agent.py` — 删 3 个方法

**删除**：

```diff
# 删掉这 3 个方法
- def set_failed(self, reason): ...
- def set_completed(self): ...
- def set_cancelled(self): ...
```

保留 `_create_cancelled_chunk` 和 `__init__` 里 `self.status = AgentStatus.IDLE`（初始化不算流转）。

---

### 8.3 修改 `answer_handler.py` — 不碰状态，返回结果

```diff
- agent.set_failed("LLM返回空内容")
- agent.set_completed()
+ # 所有 agent.set_failed/set_completed 都删掉
+ # 函数签名改为返回 dict:
+ return {"action": "complete", "response": content}  # 正常
+ return {"action": "fail", "error_msg": "LLM返回空内容", "step": error_step}  # 空内容
```

---

### 8.4 修改 `action_handler.py` — 同理

```diff
- agent.set_completed()
+ return {"action": "complete", "response": ...}
```

---

### 8.5 修改 `step_emitter.py` — 不碰状态

```diff
  def exit_with_error(self, step_count, error_type, error_message, recoverable=False):
-     if recoverable:
-         self.agent.status = AgentStatus.RETRYABLE_ERROR
-     else:
-         self.agent.set_failed(error_message)
+     # 不设状态，只创建 ErrorStep 返回
      error_step = ErrorStep(step=step_count, error_type=error_type, ...)
      return self.emit(error_step)
```

---

### 8.6 修改 `error_handler.py` — 不碰状态

```diff
  def _handle_fc_format_error(agent, error, step):
-     agent.set_failed(str(error))
+     # 不设状态，只创建 ErrorStep
      return ErrorStep(step=step, error_type="fc_format_error", ...)

  def _handle_network_error(agent, error, step):
-     agent.set_failed(str(error))
+     # 不设状态，只创建 ErrorStep
      return ErrorStep(step=step, error_type="network_error", ...)
```

然后 `handle_react_error` 的 else 分支也把 `agent.set_failed(str(error))` 删掉。

---

### 8.7 修改 `react_cycle.py` — 唯一设状态的地方

所有 `agent.status = X` 和 `agent.set_failed/set_completed/set_cancelled` 都改成：

```diff
- agent.status = AgentStatus.EXECUTING
+ from app.services.agent.core_agent.status_table import set_status, set_failed, set_completed
+ set_status(agent, AgentStatus.EXECUTING)

- agent.status = AgentStatus.CANCELLED
+ set_cancelled(agent)

- agent.set_failed("...")
+ set_failed(agent, "...")
```

`_process_single_step` 收到 handler 返回的 dict 后设状态：

```python
result = await _dispatch_handler(agent, parsed, chunk_buffer)
if isinstance(result, dict):
    action = result.get("action")
    if action == "complete":
        set_completed(agent)
    elif action == "fail":
        set_failed(agent, result.get("error_msg", ""))
```

---

### 8.8 修改 `run_sse_stream.py` — 外部异常用函数

```diff
- agent.status = AgentStatus.CANCELLED
+ from app.services.agent.core_agent.status_table import set_cancelled, set_failed
+ set_cancelled(agent)

- agent.status = AgentStatus.FAILED
+ set_failed(agent, str(e)[:200])
```

---

### 8.9 修改 `initialize_run_state.py`

```diff
- agent.status = AgentStatus.THINKING
+ from app.services.agent.core_agent.status_table import set_status
+ set_status(agent, AgentStatus.THINKING)
```

---

### 8.10 变化总表

| 改动 | 原来 | 改后 |
|------|------|------|
| 新建文件 | — | `status_table.py` |
| 删除方法 | `base_agent.set_failed/completed/cancelled` | — |
| handler 改签名 | 不返回，直接设状态 | 返回 dict，不碰状态 |
| `step_emitter.exit_with_error` | 设 RETRYABLE_ERROR 或 FAILED | 只 emit |
| `error_handler` | 设 FAILED | 只创建 ErrorStep |
| `react_cycle` | 散落 6 处设状态 | 全部调 status_table 函数 |
| `run_sse_stream` | 2 处直接赋值 | 调 set_cancelled/set_failed |
| `initialize_run_state` | 1 处直接赋值 | 调 set_status |

**最终状态：零处 `agent.status = X` 直接赋值。**

---

**文档版本**: v1.2  
**更新时间**: 2026-06-28 23:47:48  
**编写人**: 小欧
