# LLM-Prompt-Message系统优化方案

**创建时间**: 2026-06-25  
**版本**: v4.1  
**编写人**: 小欧  
**审核人**: 小健  
**文档类型**: 技术设计文档(TDD)  
**目标**: 解决系统功能问题，提升稳定性和错误恢复能力

---

## 版本历史

| 版本 | 时间 | 作者 | 更新内容 |
|------|------|------|---------|
| v1.0 | 2026-06-25 | 小欧 | 初始版本 |
| v1.1 | 2026-06-25 | 小欧 | 修正分组逻辑和类型安全 |
| v2.0 | 2026-06-25 | 小欧 | 聚焦功能修复，移除复杂监控和性能优化 |
| v3.0 | 2026-06-25 | 小欧 | 第五章全面重写：架构简化详细设计 |
| v4.0 | 2026-06-25 | 小欧 | **全文精简：删除1-4章冗余草稿，保留问题诊断+目标，第五章为唯一设计** |
| v4.1 | 2026-06-25 | 小健 | **审核修正：①1.1/3.1.1描述准确化 ②1.2/3.1.3行号修正 ③3.2.1内联代码补全prompt_logger ④3.3补充bug修复 ⑤3.6.5 FCFormatError时机约束 ⑥3.6.3 call_llm_stream走BaseAIService ⑦3.7 error_handler与exit_with_error关系明确 ⑧3.6.7 FC降级与截断重试关系 ⑨3.4删除YAGNI常量 ⑩实施计划补充依赖/集成测试/前端映射/回滚方案 |

---

## 一、问题诊断

### 1.1 根本原因

| # | 根本原因 | 具体表现 | 影响 |
|---|---------|---------|------|
| 1 | **透传包装层** | `call_llm()`做5件事（计数/裁剪/消息/工具/日志）后转发，3层调用链 | KISS-DIRECT违反 |
| 2 | **FC-only无容错** | LLM返回坏tool_calls时静默跳过或直接FAILED | 任务中断 |
| 3 | **错误处理分散** | 7个文件各自处理错误，无统一分类和恢复策略 | 状态混乱 |
| 4 | **缺少可重试状态** | AgentStatus只有5个值，FC格式错误直接FAILED | 无法重试 |
| 5 | **配置散落** | temperature/tool_choice/max_retries等硬编码在4个文件 | 维护困难 |

### 1.2 错误处理分散现状

| 文件 | 错误处理内容 | 行号 |
|------|------------|------|
| `llm_stream.py`（原llm_caller.py） | LLM调用异常 → _yield_error_response | L136-141 |
| `react_cycle.py` | 空响应保护 → exit_with_error | L119-126 |
| `react_cycle.py` | 截断工具调用 → 注入重试observation | L138-151 |
| `react_cycle.py` | 循环异常 → exit_with_error | L195-200 |
| `action_handler.py` | 安全blocked → ErrorStep | L58-65 |
| `action_handler.py` | 用户拒绝 → ErrorStep | L88-95 |
| `step_emitter.py` | 统一ErrorStep创建+FAILED状态 | exit_with_error |

---

## 二、优化目标

| 目标 | 当前状态 | 目标状态 |
|------|---------|---------|
| 调用链简化 | 3层（react_cycle→call_llm→call_llm_stream） | 2层（react_cycle→call_llm_stream） |
| FC容错 | 无降级，FC格式错误直接FAILED | 条件降级到Text模式，任务不中断 |
| 错误处理 | 分散7个文件 | 集中error_handler.py |
| Agent状态 | 5个值，无可重试 | 6个值，含RETRYABLE_ERROR |
| 常量管理 | 散落4个文件硬编码 | 集中llm_constants.py |

**遵循原则**：KISS-DIRECT（直线调用）| SRP（单一职责）| DRY（消除重复）| YAGNI（移除无用抽象）| 禁止backward（彻底重构）

---

## 三、架构简化详细设计（基于代码现状，一次性设计到位）

> **设计原则**：代码修改可分批向后，但修改设计一次性全部到位。边边角角的修改不行，必须大换血更新。
>
> **编写人**：小欧 | **审核人**：小健 | **日期**：2026-06-25 | **版本**：v1.0

---

### 3.1 当前架构问题诊断（基于代码实际状态）

#### 3.1.1 调用链过长（3层→应2层）

**当前调用链**：
```
react_cycle._process_single_step → call_llm → call_llm_stream → BaseAIService.request_stream → LLMClient.request_stream
```

**问题**：`call_llm()` (原llm_caller.py:17-41，已更名为llm_stream.py) 做了5件事后转发：
1. `agent.llm_call_count += 1`
2. `agent.message_builder.trim_history()` + `prepare_messages_for_llm()`
3. `get_openai_tools(agent)`
4. `prompt_logger.log_llm_call(...)` 记录prompt日志（L27-35共9行）
5. 转发到 `call_llm_stream()`（原call_llm_fc_stream）

这是**透传包装层**，违反KISS-DIRECT，应内联到 `_process_single_step`。其中①②③④是准备逻辑，应内联；⑤是转发，删除即可。prompt日志记录（`prompt_logger.log_llm_call`）内联到 `_process_single_step`，在真正调用LLM前记录，符合SRP。

#### 3.1.2 原llm_caller.py 职责混乱（已更名为llm_stream.py）

`call_llm_stream()` (原llm_caller.py:101-166，函数名原call_llm_fc_stream) 混合了3种职责：
- **流式chunk收集**（full_content/full_reasoning/tool_calls_result）
- **响应构建**（_build_tool_calls_response / _build_answer_response / _yield_error_response）
- **prompt日志**（_log_llm_response）

这3个应该拆到各自该在的地方。

#### 3.1.3 错误处理分散在7个文件

| 文件 | 错误处理内容 | 行号 |
|------|------------|------|
| `llm_stream.py`（原llm_caller.py） | LLM调用异常 → _yield_error_response | L136-141 |
| `react_cycle.py` | 空响应保护 → exit_with_error | L119-126 |
| `react_cycle.py` | 截断工具调用 → 注入重试observation | L138-151 |
| `react_cycle.py` | 循环异常 → exit_with_error | L195-200 |
| `action_handler.py` | 安全blocked → ErrorStep | L58-65 |
| `action_handler.py` | 用户拒绝 → ErrorStep | L88-95 |
| `step_emitter.py` | 统一ErrorStep创建+FAILED状态 | exit_with_error |

没有统一的错误分类和恢复策略。

#### 3.1.4 AgentStatus缺少可重试状态

当前只有5个状态：`IDLE/THINKING/EXECUTING/COMPLETED/FAILED`。FC格式错误时直接FAILED，无法重试。

#### 3.1.5 配置散落

| 参数 | 当前位置 | 问题 |
|------|---------|------|
| `max_tokens` | BaseAIService.__init__ 参数，来自YAML | **不设置（传None）**，LLM自行决定 |
| `temperature` | BaseAIService.__init__，默认0.7 | 应该是常量 |
| `tool_choice="auto"` | 原llm_caller.py:111（已更名为llm_stream.py）硬编码 | 应该是常量 |
| `TOOL_CACHE_TTL=300` | universal_agent.py 类属性 | 应该在常量文件 |
| `MAX_CONTEXT_CHARS=200000` | constants.py | ✅ OK |
| `DEFAULT_MAX_STEPS=100` | constants.py | ✅ OK |
| `max_retries=3` (LLM层) | base_service.py:168 硬编码 | 应该是常量 |
| `stream_options` | base_service.py:169 硬编码 | 应该是常量 |
| `FC重试次数` | 文档设计2次，代码无实现 | 缺失 |
| `TASK_TIMEOUT` | constants.py | ✅ OK |

---

### 3.2 合并原llm_caller到react_cycle（消除透传层）

**当前3层**（文件已更名为llm_stream.py，函数已更名为call_llm_stream）：
```
_process_single_step → call_llm → call_llm_stream → BaseAIService.request_stream
```

**目标2层**：
```
_process_single_step → call_llm_stream → BaseAIService.request_stream
```

#### 3.2.1 具体操作

1. **删除 `call_llm()` 函数**（原llm_caller.py:17-41，已更名为llm_stream.py）
2. **将其全部逻辑内联到 `_process_single_step()`**：

```python
# react_cycle.py _process_single_step 内部
from app.services.agent.tool_cache_manager import get_openai_tools
from app.utils.prompt_logger import get_prompt_logger

agent.llm_call_count += 1
agent.message_builder.trim_history()
messages = agent.message_builder.prepare_messages_for_llm()
openai_tools = get_openai_tools(agent)

# prompt日志 — 原call_llm L27-35内联
prompt_logger = get_prompt_logger()
prompt_logger.log_llm_call(
    round_number=agent.llm_call_count, messages=messages,
    model=getattr(agent.llm_client, 'model', 'unknown'),
    provider=getattr(agent.llm_client, 'provider', 'unknown'),
    call_type="tools", tools=openai_tools,
)

# 直接调用 call_llm_stream（原call_llm_fc_stream）
async for chunk_or_response in call_llm_stream(agent, messages, openai_tools):
    ...
```

3. **`call_llm_stream()`（原call_llm_fc_stream）移到 react_cycle.py 同级**（或保留在 llm_stream.py 但删除 call_llm）

#### 3.2.2 影响范围

- `react_cycle.py:98-101` — 改为直接调用
- `llm_stream.py`（原llm_caller.py） — 删除 `call_llm()` 函数
- 无其他文件引用 `call_llm`（已确认只有 react_cycle.py 引用）

---

### 3.3 llm_stream.py 瘦身（重命名已完成 ✅）

**已完成**：`llm_caller.py` → `llm_stream.py`，`call_llm_fc_stream` → `call_llm_stream`

**当前 llm_stream.py（原llm_caller.py）包含**：
- `call_llm()` — 删除（内联到react_cycle，尚未实施）
- `call_llm_stream()`（原call_llm_fc_stream） — 保留，统一的LLM流式调用（FC+Text双模式）
- `_build_tool_calls_response()` — 保留
- `_build_answer_response()` — 保留
- `_yield_error_response()` — 保留
- `_log_llm_response()` — 保留

**Bug修复**：`_build_answer_response()` L97-98有重复return语句（死代码），删除L98。

**额外变化**：
- `call_llm_stream` 新增 `tools=None` 参数 — 传入 `tools=None` 时自动走Text模式（降级后备）
- `prompt_logger.log_llm_call` 从原 `call_llm` 迁移到此函数内部，在真正调用LLM前记录

---

### 3.4 新增LLM常量文件

**文件路径**：`backend/app/services/llm/llm_constants.py`

**原则**：不配置，写到常量文件。`max_tokens` 不设置（传None，LLM自行决定）。

```python
# backend/app/services/llm/llm_constants.py
# LLM层常量集中管理 — 小欧 2026-06-25

# --- LLM请求参数 ---
LLM_TEMPERATURE = 0.7
LLM_TOOL_CHOICE = "auto"
LLM_MAX_RETRIES = 3
LLM_STREAM_OPTIONS = {"include_usage": True}

# --- FC降级配置 ---
FC_FALLBACK_ENABLED = True
FC_MAX_RETRIES = 2  # FC模式最多重试2次，失败后降级到Text模式

# --- 工具缓存 ---
TOOL_CACHE_TTL = 300  # 5分钟

```

**参数说明**：

| 常量 | 值 | 来源 | 说明 |
|------|-----|------|------|
| `LLM_TEMPERATURE` | 0.7 | BaseAIService.__init__默认值 | 固化为常量 |
| `LLM_TOOL_CHOICE` | "auto" | 原llm_caller.py:111（已更名为llm_stream.py）硬编码 | 固化为常量 |
| `LLM_MAX_RETRIES` | 3 | base_service.py:168硬编码 | 固化为常量 |
| `LLM_STREAM_OPTIONS` | {"include_usage": True} | base_service.py:169硬编码 | 固化为常量 |
| `FC_FALLBACK_ENABLED` | True | 新增 | FC降级开关 |
| `FC_MAX_RETRIES` | 2 | 新增 | FC重试次数 |
| `TOOL_CACHE_TTL` | 300 | universal_agent.py类属性 | 迁移到常量文件 |
| `max_tokens` | **不设置** | — | 传None，LLM自行决定输出长度 |

**修改点**：

1. `base_service.py:168-169` — 用 `LLM_MAX_RETRIES` / `LLM_STREAM_OPTIONS` 替换硬编码
2. `llm_stream.py:111`（原llm_caller.py） — 用 `LLM_TOOL_CHOICE` 替换硬编码 `"auto"`
3. `universal_agent.py` — 用 `TOOL_CACHE_TTL` 替换类属性
4. `BaseAIService.__init__` 的 `temperature` 默认值 — 用 `LLM_TEMPERATURE` 替换

---

### 3.5 AgentStatus 新增 RETRYABLE_ERROR

**文件**：`backend/app/services/agent/types/agent_status.py`

```python
class AgentStatus(Enum):
    IDLE = "idle"
    THINKING = "thinking"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYABLE_ERROR = "retryable_error"  # 新增：可重试错误（FC格式错误等）
```

**状态转换规则**：
```
IDLE → THINKING → EXECUTING
EXECUTING → COMPLETED | FAILED | RETRYABLE_ERROR
RETRYABLE_ERROR → EXECUTING（重试成功）| FAILED（重试耗尽）
```

---

### 3.6 FC条件降级机制（核心新增）

#### 3.6.1 设计原则

**偶尔降级，非一直降级**。FC模式失败时降级到Text模式，仅针对当前请求，下次请求继续FC模式。

#### 3.6.2 降级流程

```
call_llm_stream(tools=openai_tools) 失败
  ↓
重试FC模式（最多FC_MAX_RETRIES=2次）
  ↓ 仍然失败
降级调用 call_llm_stream(tools=None)（不带tools，纯文本模式）
  ↓
返回answer类型响应
```

#### 3.6.3 关键实现

**实现位置**：在 `llm_stream.py`（原llm_caller.py）中。**函数重命名已完成**（`call_llm_fc_stream` → `call_llm_stream`），`tools=None` 参数和 `call_llm_with_fallback` 尚未实施。

**① call_llm_with_fallback — FC降级主入口**：

```python
async def call_llm_with_fallback(agent, messages, openai_tools):
    """FC模式失败时条件降级到Text模式 — 小欧 2026-06-25"""
    from app.services.llm.llm_constants import FC_FALLBACK_ENABLED, FC_MAX_RETRIES
    from app.services.llm.core import FCFormatError
    
    last_error = None
    
    for attempt in range(FC_MAX_RETRIES):
        try:
            async for item in call_llm_stream(agent, messages, tools=openai_tools):
                yield item
            return  # FC成功
        except FCFormatError as e:
            last_error = e
            logger.warning(f"[FC降级] FC模式第{attempt+1}次失败: {e}")
            continue
    
    # FC重试耗尽，降级到Text模式
    if FC_FALLBACK_ENABLED:
        logger.warning(f"[FC降级] FC模式{FC_MAX_RETRIES}次重试均失败，降级到Text模式")
        async for item in call_llm_stream(agent, messages, tools=None):  # tools=None = Text模式
            yield item
    else:
        yield _yield_error_response(f"FC模式失败: {last_error}", agent)
```

**② call_llm_stream — 统一流式调用（FC + Text）**：

`call_llm_fc_stream` 已改名为 `call_llm_stream`（✅ 已完成），新增 `tools=None` 参数。`tools=None` 时自动走Text模式（无tool_calls，仅返回content），无需额外函数。

> **关键**：Text模式降级仍通过 `agent.llm_client.request_stream(messages, tools=None)` 调用，即走 `BaseAIService.request_stream`，而非直接调 `LLMClient.request_stream`。这样保留：①重试机制（max_retries=3）②usage提取 ③tool_calls聚合（Text模式无tool_calls，自动跳过）。直接调LLMClient会丢失这些能力。
>
> **reasoning支持**：Text模式与FC模式共用同一个 `call_llm_stream` 函数体，已有 `full_reasoning` 累积和 `is_reasoning` 判断（L104/L125-127），无需额外处理。`tools=None` 时LLM不返回tool_calls，自然走answer分支。

#### 3.6.4 降级条件

| 错误类型 | 是否降级 | 说明 |
|---------|---------|------|
| FC格式错误（tool_calls JSON解析失败） | 是 | LLM返回了坏的工具调用 |
| 流式错误（stream_error） | 否 | 直接返回错误 |
| 网络错误/超时 | 否 | 不降级，直接抛出 |
| CancelledError | 否 | 不降级，直接抛出 |

#### 3.6.5 FCFormatError 异常类

**当前问题**：`call_llm_stream`（原call_llm_fc_stream）中FC格式错误（`_json.loads(tc["arguments"])` 失败）是**静默跳过**的（base_service.py:220-224），不会抛异常。

**修改方案**：当所有tool_calls都解析失败时，抛出 `FCFormatError`。

> **关键约束**：`FCFormatError` 必须在流结束后（`yield StreamChunk(tool_calls=tool_calls_list)` 之前）抛出，不能在中间yield后抛出。因为 `request_stream` 是async generator，已yield的chunk无法收回。实际代码中，tool_calls的解析在流结束后统一进行（base_service.py:212-238），此时尚未yield最终的tool_calls StreamChunk，所以在此处raise是安全的——调用方 `call_llm_with_fallback` 的 `async for` 会收到异常，之前yield的content/reasoning chunk已正常消费。

**新增异常类**（在 `services/llm/core.py` 中）：

```python
class FCFormatError(Exception):
    """FC格式错误 — LLM返回的tool_calls无法解析 — 小欧 2026-06-25"""
    pass
```

**base_service.py 修改**：

```python
# 当前（base_service.py:217-224）：
try:
    params = _normalize_tool_params(_json.loads(tc["arguments"])) if tc["arguments"] else {}
except _json.JSONDecodeError:
    logger.warning(f"[request_stream] tool_call '{tc['name']}' 参数JSON解析失败, 跳过")
    continue

# 改为：
failed_parses = []
try:
    params = _normalize_tool_params(_json.loads(tc["arguments"])) if tc["arguments"] else {}
except _json.JSONDecodeError:
    failed_parses.append(tc["name"])
    continue

# 流结束后检查（在 yield StreamChunk(tool_calls=tool_calls_list) 之前）：
if tool_call_accumulator and not tool_calls_list:
    # 所有tool_calls都解析失败 → FCFormatError
    raise FCFormatError(f"所有tool_calls参数解析失败: {failed_parses}")
```

#### 3.6.6 FC降级决策树

```
call_llm_stream 执行
  ├─ 成功 → 返回结果
  ├─ FCFormatError → 重试FC(最多2次)
  │   ├─ 重试成功 → 返回结果
  │   └─ 重试耗尽 → FC_FALLBACK_ENABLED?
  │       ├─ True → call_llm_stream(msg, tools=None) → 返回answer
  │       └─ False → 返回ErrorStep(retryable_error)
  ├─ stream_error → 返回ErrorStep
  ├─ NetworkError/TimeoutError → 不降级，抛出
  └─ CancelledError → 不降级，抛出
```

#### 3.6.7 FC降级与截断重试的关系

FC降级（本节3.6）和截断重试（react_cycle.py:138-151 `_should_retry_truncated_tool`）是**两个独立层**，不冲突：

| 维度 | FC降级（3.6） | 截断重试（react_cycle） |
|------|-------------|---------------------|
| 触发条件 | tool_calls JSON解析失败（base_service.py层） | LLM返回answer但内容短+历史有未执行tool_call（react_cycle层） |
| 发生位置 | `base_service.py` → `FCFormatError` → `call_llm_with_fallback` | `react_cycle.py` → `_should_retry_truncated_tool` → 注入observation |
| 恢复方式 | 重试FC → 降级Text模式 | 注入observation让LLM重新调用工具 |
| 优先级 | 先于截断重试（base_service层在react_cycle层之下） | 后于FC降级（只有LLM成功返回answer后才可能触发） |

**执行顺序**：FC降级在LLM调用层处理格式错误，截断重试在ReAct循环层处理语义截断。两者不会同时触发——FC格式错误时LLM没有返回有效answer，截断重试条件不满足。

---

### 3.7 统一错误处理模块

**文件路径**：`backend/app/services/agent/core_agent/error_handler.py`

**设计**：模块级函数，不用类。直接if/elif分派，不用注册表（KISS-DIRECT）。

> **与 `exit_with_error` 的关系**：`error_handler` 是 `exit_with_error` 的**替代**（仅限react_cycle循环异常处）。`exit_with_error` 固定设置 `AgentStatus.FAILED`，而 `error_handler` 根据错误类型设置不同状态（RETRYABLE_ERROR/FAILED）。修改点：
> - `react_cycle.py:195-200` 的 `except Exception` — 用 `handle_react_error()` 替换 `exit_with_error`
> - `llm_stream.py:136-141` 的LLM调用异常 — 用 `handle_react_error()` 替换 `_yield_error_response`
> - `step_emitter.py:exit_with_error` — **保留不动**，仍用于空响应保护(L119-126)、安全blocked(L58-65)、用户拒绝(L88-95)等**确定要FAILED**的场景

```python
# error_handler.py — 统一ReAct循环错误处理 — 小欧 2026-06-25

from app.services.agent.steps import ErrorStep
from app.services.agent.types import AgentStatus
from app.utils.logger import logger


def handle_react_error(agent, error, step):
    """统一处理ReAct循环中的错误 — if/elif直接分派"""
    error_type = _classify_error(error)
    
    if error_type == "fc_format_error":
        return _handle_fc_format_error(agent, error, step)
    elif error_type == "tool_execution_error":
        return _handle_tool_error(agent, error, step)
    elif error_type == "network_error":
        return _handle_network_error(agent, error, step)
    else:
        agent.status = AgentStatus.FAILED
        return ErrorStep(step=step, error_type="unknown_error", error_message=str(error))


def _classify_error(error):
    """错误分类 — 基于异常类型，不基于字符串匹配 — 小欧 2026-06-25"""
    from app.services.llm.core import FCFormatError
    from app.utils.error_classifier import UnifiedErrorClassifier, ErrorCategory
    
    if isinstance(error, FCFormatError):
        return "fc_format_error"
    
    category = UnifiedErrorClassifier.classify_error(error)
    if category in (ErrorCategory.NETWORK, ErrorCategory.CONNECT, ErrorCategory.TIMEOUT, ErrorCategory.EMPTY_RESPONSE):
        return "network_error"
    
    return "unknown_error"


def _handle_fc_format_error(agent, error, step):
    """FC格式错误 → 可重试"""
    logger.error(f"[ErrorHandler] FC格式错误: {error}")
    agent.status = AgentStatus.RETRYABLE_ERROR
    return ErrorStep(step=step, error_type="fc_format_error", 
                     error_message=str(error), recoverable=True)


def _handle_tool_error(agent, error, step):
    """工具执行错误 → 继续执行（不设FAILED）"""
    logger.error(f"[ErrorHandler] 工具错误: {error}")
    # 不更新agent状态，继续执行其他工具
    return ErrorStep(step=step, error_type="tool_execution_error",
                     error_message=str(error), recoverable=True)


def _handle_network_error(agent, error, step):
    """网络错误 → 可重试"""
    logger.error(f"[ErrorHandler] 网络错误: {error}")
    agent.status = AgentStatus.RETRYABLE_ERROR
    return ErrorStep(step=step, error_type="network_error",
                     error_message=str(error), recoverable=True)
```

**修改点**：
1. `react_cycle.py:195-200` — 用 `handle_react_error()` 替换 `exit_with_error`
   ```python
   # 当前：
   except Exception as e:
       yield agent._step_emitter.exit_with_error(step_count=..., error_type="runtime_error", ...)
       agent.status = AgentStatus.FAILED
   
   # 改为：
   except Exception as e:
       error_step = handle_react_error(agent, e, agent.llm_call_count)
       yield agent._step_emitter.emit(error_step)
   ```
2. `llm_stream.py:136-141`（原llm_caller.py）— LLM调用异常也走 `handle_react_error()`
3. `step_emitter.py:exit_with_error` — **保留不动**，用于确定要FAILED的场景（空响应、安全blocked、用户拒绝等）

---

### 3.8 重构后的目录结构

```
services/agent/
├── core_agent/
│   ├── __init__.py
│   ├── base_agent.py              # 不变
│   ├── react_cycle.py             # 修改：内联call_llm逻辑，调用llm_stream
│   ├── error_handler.py           # 新增：统一错误处理
│   ├── agent_initializer.py       # 不变
│   ├── initialize_run_state.py    # 不变
│   ├── step_emitter.py            # 不变
│   ├── tool_manager.py            # 不变
│   └── handlers/
│       ├── action_handler.py      # 不变
│       └── answer_handler.py      # 不变
├── llm_stream.py                  # 重命名：llm_caller → llm_stream，删除call_llm，call_llm_stream统一FC+Text模式
├── message_builder.py             # 不变（已优化过）
├── observation_formatter.py       # 不变
├── chunk_buffer.py                # 不变
├── tool_cache_manager.py          # 不变
├── tool_executor.py               # 不变
├── tool_retry_engine.py           # 不变
├── universal_agent.py             # 修改：TOOL_CACHE_TTL迁移到常量
├── agent_utils/
│   ├── fc_message_types.py        # 不变
│   └── message_utils.py           # 不变
├── steps/                         # 不变
└── types/
    ├── agent_status.py            # 修改：新增RETRYABLE_ERROR
    └── result_types.py            # 不变

services/llm/
├── __init__.py                    # 不变
├── base_service.py                # 修改：用常量替换硬编码，FCFormatError支持
├── client_sdk.py                  # 不变
├── core.py                        # 修改：新增FCFormatError异常类
├── llm_constants.py               # 新增：LLM层常量
├── stream_parser.py               # 不变
└── model_adapters/                # 不变
```

---

### 3.9 修改清单（按文件）

| # | 文件 | 操作 | 具体修改 |
|---|------|------|---------|
| 1 | `services/llm/llm_constants.py` | **新增** | LLM层所有常量 |
| 2 | `services/llm/core.py` | 修改 | 新增 `FCFormatError` 异常类 |
| 3 | `services/llm/base_service.py` | 修改 | ①用常量替换硬编码(L168-169) ②tool_calls全解析失败时抛FCFormatError |
| 4 | `services/agent/llm_stream.py`（原llm_caller.py） | **重命名+修改** | ✅ ①重命名已完成 ②删除`call_llm()` ③`call_llm_fc_stream`→`call_llm_stream`（✅ 函数重命名已完成）支持tools=None ④新增`call_llm_with_fallback()` ⑤prompt_logger.log_llm_call迁入 ⑥用常量替换硬编码 |
| 5 | `services/agent/core_agent/react_cycle.py` | 修改 | ①内联call_llm逻辑到_process_single_step ②导入路径改llm_stream ③用error_handler替换内联错误处理 |
| 6 | `services/agent/core_agent/error_handler.py` | **新增** | 统一错误处理模块 |
| 7 | `services/agent/types/agent_status.py` | 修改 | 新增RETRYABLE_ERROR |
| 8 | `services/agent/universal_agent.py` | 修改 | TOOL_CACHE_TTL迁移到常量 |

---

### 3.10 数据流变化

**优化前**：
```
react_cycle._process_single_step
  → call_llm(agent)                    # 透传包装
    → call_llm_stream(agent, msg, tools)
      → BaseAIService.request_stream
```

**优化后**：
```
react_cycle._process_single_step
  → [内联] trim_history + prepare_messages + get_openai_tools
  → call_llm_with_fallback(agent, msg, tools)   # 直接调用，含FC降级
    → call_llm_stream(agent, msg, tools)         # FC模式
    → call_llm_stream(agent, msg, tools=None)    # Text模式（降级后备，同一函数）
      → BaseAIService.request_stream
```

---

### 3.11 不修改的部分（明确排除）

| 模块 | 原因 |
|------|------|
| `message_builder.py` | 已在6-25优化过（D-1修复），算法已OK |
| `action_handler.py` | 业务逻辑正确，不需要改 |
| `answer_handler.py` | 简洁，不需要改 |
| `fc_message_types.py` | 类型安全，符合SRP |
| `steps/` 目录 | Step定义完整，不需要改 |
| `tool_cache_manager.py` | 缓存逻辑OK |
| `tool_retry_engine.py` | 重试逻辑OK |
| `observation_formatter.py` | 格式化逻辑OK |
| `react_sse_wrapper/` | SSE层不变 |
| `client_sdk.py` | HTTP层不变 |

---

## 四、实施计划

### 4.1 任务依赖关系

```
任务1(llm_constants) ──→ 任务9(base_service常量替换)
                    ──→ 任务4(llm_stream常量替换)
                    ──→ 任务8(universal_agent常量替换)
任务2(FCFormatError) ──→ 任务5(call_llm_with_fallback)
任务3+4(内联+重命名) ──→ 任务5(call_llm_with_fallback)
任务7(RETRYABLE_ERROR) ──→ 任务6(error_handler)
```

### 4.2 任务清单

| # | 任务 | 对应设计 | 前置依赖 | 负责人 | 优先级 |
|---|------|---------|---------|--------|--------|
| 1 | 新增 `llm_constants.py` 常量文件 | 3.4 | — | 小欧 | P0 |
| 2 | 新增 `FCFormatError` 异常类 + base_service.py FC格式错误抛出 | 3.6.5 | — | 小欧 | P0 |
| 3 | 删除 `call_llm()`，内联到 `_process_single_step`（含prompt_logger） | 3.2 | 1 | 小欧 | P0 |
| 4 | `llm_caller.py` 重命名为 `llm_stream.py` ✅已完成 + 修复重复return bug | 3.3 | 3 | 小欧 | P0 |
| 5 | `call_llm_fc_stream`→`call_llm_stream`（✅函数重命名已完成）支持tools=None + 新增`call_llm_with_fallback()` | 3.6 | 2, 4 | 小沈 | P0 |
| 6 | 新增 `error_handler.py` 统一错误处理 | 3.7 | 7 | 小欧 | P1 |
| 7 | `AgentStatus` 新增 `RETRYABLE_ERROR` | 3.5 | — | 小沈 | P1 |
| 8 | `universal_agent.py` TOOL_CACHE_TTL 迁移到常量 | 3.4 | 1 | 小健 | P1 |
| 9 | `base_service.py` 用常量替换硬编码 | 3.4 | 1 | 小健 | P1 |
| 10 | 前端SSE状态映射：新增 `retryable_error` 状态识别 | 3.5 | 7 | 小健 | P1 |
| 11 | FC降级集成测试：模拟FCFormatError→验证降级到Text模式 | 3.6 | 5 | 小沈 | P1 |


---

## 五、风险与验收

### 5.1 主要风险

| 风险 | 缓解措施 |
|------|----------|
| 重构引入新bug | 分阶段实施 + 充分测试 + 灰度发布 |
| FC降级逻辑误触发 | FCFormatError严格定义 + 仅FC格式错误才降级 + 网络错误不降级 |
| llm_stream重命名（已完成） | 导入路径已更新（react_cycle.py），无其他文件引用call_llm |

### 5.2 验收标准

| 指标 | 当前状态 | 目标状态 | 验收标准 |
|------|----------|----------|----------|
| FC降级机制 | 无 | 实现 | FC格式错误时自动降级到Text模式，任务不中断 |
| 调用链简化 | 3层调用 | 2层调用 | call_llm删除，react_cycle直接调用call_llm_stream |
| 错误统一处理 | 分散7个文件 | 集中error_handler | ReAct循环错误走handle_react_error |
| RETRYABLE_ERROR状态 | 无 | 添加 | AgentStatus枚举新增，状态转换规则明确 |
| 常量集中 | 散落4个文件 | llm_constants.py | LLM参数全部从常量读取，无硬编码 |
| 任务成功率 | 受FC失败影响 | 提升 | FC失败时任务仍能完成 |

---

**文档状态**：v4.1（小健审核修正，补充10项设计缺陷和遗漏）  
**下一步**：团队评审 → 按实施计划执行