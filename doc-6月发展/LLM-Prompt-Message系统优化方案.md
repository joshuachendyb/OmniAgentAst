# LLM-Prompt-Message系统优化方案

**创建时间**: 2026-06-25  
**版本**: v5.0  
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
| v4.0 | 2026-06-25 | 小欧 | 全文精简：删除1-4章冗余草稿，保留问题诊断+目标，第五章为唯一设计 |
| v4.1 | 2026-06-25 | 小健 | 审核修正：①1.1/3.1.1描述准确化 ②1.2/3.1.3行号修正 ③3.2.1内联代码补全prompt_logger ④3.3补充bug修复 ⑤3.6.5 FCFormatError时机约束 ⑥3.6.3 call_llm_stream走BaseAIService ⑦3.7 error_handler与exit_with_error关系明确 ⑧3.6.7 FC降级与截断重试关系 ⑨3.4删除YAGNI常量 ⑩实施计划补充依赖/集成测试/前端映射/回滚方案 |
| v5.0 | 2026-06-25 | 小欧 | 文档丢失后重建：基于代码实际状态更新实施进度，标注已完成/未完成项，补充FC降级未启用的关键发现 |
| v5.1 | 2026-06-25 | 小欧 | 实施完成：①react_cycle接入call_llm_with_fallback ②前端SSE添加fc_format_error类型 ③FCFormatError穿透call_llm_stream异常处理 ④修复call_llm_with_fallback参数名bug ⑤集成测试6/6通过 |

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

| 目标 | 当前状态 | 目标状态 | 实施状态 |
|------|---------|---------|---------|
| 调用链简化 | 3层（react_cycle→call_llm→call_llm_stream） | 2层（react_cycle→call_llm_stream） | ✅ **已完成** |
| FC容错 | 无降级，FC格式错误直接FAILED | 条件降级到Text模式，任务不中断 | ✅ **已完成** |
| 错误处理 | 分散7个文件 | 集中error_handler.py | ✅ **已完成** |
| Agent状态 | 5个值，无可重试 | 6个值，含RETRYABLE_ERROR | ✅ **已完成** |
| 常量管理 | 散落4个文件硬编码 | 集中llm_constants.py | ✅ **已完成** |

**遵循原则**：KISS-DIRECT（直线调用）| SRP（单一职责）| DRY（消除重复）| YAGNI（移除无用抽象）| 禁止backward（彻底重构）

---

## 三、架构简化详细设计（基于代码实际状态）

> **设计原则**：代码修改可分批向后，但修改设计一次性全部到位。边边角角的修改不行，必须大换血更新。
>
> **编写人**：小欧 | **审核人**：小健 | **日期**：2026-06-25 | **版本**：v5.0

---

### 3.1 当前架构问题诊断（基于代码实际状态）

#### 3.1.1 调用链过长（3层→2层）✅ 已解决

**优化前调用链**：
```
react_cycle._process_single_step → call_llm → call_llm_stream → BaseAIService.request_stream → LLMClient.request_stream
```

**优化后调用链**（当前代码）：
```
react_cycle._process_single_step → call_llm_stream → BaseAIService.request_stream → LLMClient.request_stream
```

**已完成**：`call_llm()` 已删除，其逻辑内联到 `_process_single_step`。`llm_caller.py` 已更名为 `llm_stream.py`。

#### 3.1.2 原llm_caller.py 职责混乱 ✅ 已解决

**已完成**：
- `llm_caller.py` → `llm_stream.py`（重命名 ✅）
- `call_llm_fc_stream` → `call_llm_stream`（函数重命名 ✅）
- `call_llm()` 函数已删除（内联到react_cycle ✅）
- `_log_llm_response()` 统一日志入口已提取 ✅
- `_build_answer_response()` 重复return bug已修复 ✅

#### 3.1.3 错误处理分散在7个文件 ✅ 已部分解决

**已完成**：`error_handler.py` 已创建，`handle_react_error()` 统一处理ReAct循环错误。

**保留 `exit_with_error` 的场景**（确定要FAILED，不需要重试）：
- 空响应保护（react_cycle L119-126）
- 安全blocked（action_handler L58-65）
- 用户拒绝（action_handler L88-95）

#### 3.1.4 AgentStatus缺少可重试状态 ✅ 已解决

**已完成**：`RETRYABLE_ERROR` 已添加到 `AgentStatus` 枚举。

状态转换规则：
```
IDLE → THINKING → EXECUTING
EXECUTING → COMPLETED | FAILED | RETRYABLE_ERROR
RETRYABLE_ERROR → EXECUTING（重试成功）| FAILED（重试耗尽）
```

#### 3.1.5 配置散落 ✅ 已解决

**已完成**：`llm_constants.py` 已创建，所有硬编码已收敛。

| 参数 | 当前位置 | 状态 |
|------|---------|------|
| `max_tokens` | 不设置（传None） | ✅ OK |
| `temperature` | `llm_constants.LLM_TEMPERATURE` | ✅ 已迁移 |
| `tool_choice="auto"` | `llm_constants.LLM_TOOL_CHOICE` | ✅ 已迁移 |
| `TOOL_CACHE_TTL=300` | `llm_constants.TOOL_CACHE_TTL` → `universal_agent.py` 类属性引用 | ✅ 已迁移 |
| `MAX_CONTEXT_CHARS` | `constants.py` | ✅ OK |
| `DEFAULT_MAX_STEPS` | `constants.py` | ✅ OK |
| `max_retries=3` | `llm_constants.LLM_MAX_RETRIES` | ✅ 已迁移 |
| `stream_options` | `llm_constants.LLM_STREAM_OPTIONS` | ✅ 已迁移 |
| `FC重试次数` | `llm_constants.FC_MAX_RETRIES` | ✅ 已迁移 |
| `FC降级开关` | `llm_constants.FC_FALLBACK_ENABLED` | ✅ 已迁移 |

---

### 3.2 合并原llm_caller到react_cycle（消除透传层）✅ 已完成

**当前2层**（已实施）：
```
_process_single_step → call_llm_stream → BaseAIService.request_stream
```

#### 3.2.1 已完成的操作

1. ✅ **删除 `call_llm()` 函数**（原llm_caller.py:17-41）
2. ✅ **逻辑内联到 `_process_single_step()`**：

```python
# react_cycle.py _process_single_step 内部（当前代码）
from app.services.agent.llm_stream import call_llm_stream
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

# 直接调用 call_llm_stream
async for chunk_or_response in call_llm_stream(agent, messages, openai_tools):
    ...
```

3. ✅ **`llm_caller.py` 已更名为 `llm_stream.py`**

---

### 3.3 llm_stream.py 瘦身 ✅ 已完成

**当前 llm_stream.py 包含**：
- `call_llm()` — ✅ 已删除
- `call_llm_stream()`（原call_llm_fc_stream） — ✅ 保留，统一的LLM流式调用（FC+Text双模式）
- `call_llm_with_fallback()` — ✅ 新增，FC降级主入口（**但react_cycle未调用，见3.6**）
- `_build_tool_calls_response()` — ✅ 保留
- `_build_answer_response()` — ✅ 保留，重复return bug已修复
- `_yield_error_response()` — ✅ 保留
- `_log_llm_response()` — ✅ 保留，统一日志入口

**`call_llm_stream` 新增 `tools=None` 参数** — 传入 `tools=None` 时自动走Text模式（降级后备）。

---

### 3.4 新增LLM常量文件 ✅ 已完成

**文件路径**：`backend/app/services/llm/llm_constants.py`

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

**已完成修改**：

1. ✅ `base_service.py:171-173` — 用 `LLM_MAX_RETRIES` / `LLM_STREAM_OPTIONS` 替换硬编码
2. ✅ `llm_stream.py` — 用 `LLM_TOOL_CHOICE` 替换硬编码 `"auto"`
3. ✅ `universal_agent.py:20,33` — 用 `TOOL_CACHE_TTL` 替换硬编码（通过import）
4. ✅ `BaseAIService.__init__` 的 `temperature` 默认值 — 用 `LLM_TEMPERATURE` 替换

---

### 3.5 AgentStatus 新增 RETRYABLE_ERROR ✅ 已完成

**文件**：`backend/app/services/agent/types/agent_status.py`

```python
class AgentStatus(Enum):
    IDLE = "idle"
    THINKING = "thinking"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYABLE_ERROR = "retryable_error"  # 小欧 2026-06-25: 可重试错误（FC格式错误等）
```

**状态转换规则**：
```
IDLE → THINKING → EXECUTING
EXECUTING → COMPLETED | FAILED | RETRYABLE_ERROR
RETRYABLE_ERROR → EXECUTING（重试成功）| FAILED（重试耗尽）
```

---

### 3.6 FC条件降级机制（⚠️ 部分完成 — 代码已写，未接入循环）

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

**① call_llm_with_fallback — FC降级主入口**（✅ 已实现，⚠️ 未接入）：

```python
# llm_stream.py:145 — 已实现
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
        async for item in call_llm_stream(agent, messages, tools=None):
            yield item
    else:
        yield _yield_error_response(f"FC模式失败: {last_error}", agent)
```

**② call_llm_stream — 统一流式调用（FC + Text）**（✅ 已实现）：

`call_llm_fc_stream` 已改名为 `call_llm_stream`，新增 `tools=None` 参数。`tools=None` 时自动走Text模式（无tool_calls，仅返回content），无需额外函数。

> **关键**：Text模式降级仍通过 `agent.llm_client.request_stream(messages, tools=None)` 调用，即走 `BaseAIService.request_stream`，而非直接调 `LLMClient.request_stream`。这样保留：①重试机制（max_retries=3）②usage提取 ③tool_calls聚合（Text模式无tool_calls，自动跳过）。直接调LLMClient会丢失这些能力。

> **reasoning支持**：Text模式与FC模式共用同一个 `call_llm_stream` 函数体，已有 `full_reasoning` 累积和 `is_reasoning` 判断，无需额外处理。`tools=None` 时LLM不返回tool_calls，自然走answer分支。

#### 3.6.4 ⚠️ 未完成的关键步骤

**当前 `react_cycle.py:124` 直接调用 `call_llm_stream`，未调用 `call_llm_with_fallback`**：

```python
# react_cycle.py:124 当前代码
async for chunk_or_response in call_llm_stream(agent, messages, openai_tools):
    ...
```

**应改为**：
```python
# react_cycle.py:124 目标代码
async for chunk_or_response in call_llm_with_fallback(agent, messages, openai_tools):
    ...
```

**这是FC降级机制启用的唯一剩余步骤。**

#### 3.6.5 降级条件

| 错误类型 | 是否降级 | 说明 |
|---------|---------|------|
| FC格式错误（tool_calls JSON解析失败） | 是 | LLM返回了坏的工具调用 |
| 流式错误（stream_error） | 否 | 直接返回错误 |
| 网络错误/超时 | 否 | 不降级，直接抛出 |
| CancelledError | 否 | 不降级，直接抛出 |

#### 3.6.6 FCFormatError 异常类 ✅ 已完成

**新增异常类**（在 `services/llm/core.py:16-18`）：

```python
class FCFormatError(Exception):
    """FC格式错误 — LLM返回的tool_calls无法解析"""
    pass
```

**base_service.py 修改**（✅ 已完成）：

```python
# base_service.py:242-244 当前代码
if tool_call_accumulator and not tool_calls_list:
    from app.services.llm.core import FCFormatError
    raise FCFormatError(f"所有tool_calls参数解析失败: {failed_parses}")
```

> **关键约束**：`FCFormatError` 必须在流结束后（`yield StreamChunk(tool_calls=tool_calls_list)` 之前）抛出，不能在中间yield后抛出。因为 `request_stream` 是async generator，已yield的chunk无法收回。实际代码中，tool_calls的解析在流结束后统一进行（base_service.py:212-238），此时尚未yield最终的tool_calls StreamChunk，所以在此处raise是安全的。

#### 3.6.7 FC降级决策树

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

#### 3.6.8 FC降级与截断重试的关系

FC降级（本节3.6）和截断重试（react_cycle.py:138-151 `_should_retry_truncated_tool`）是**两个独立层**，不冲突：

| 维度 | FC降级（3.6） | 截断重试（react_cycle） |
|------|-------------|---------------------|
| 触发条件 | tool_calls JSON解析失败（base_service.py层） | LLM返回answer但内容短+历史有未执行tool_call（react_cycle层） |
| 发生位置 | `base_service.py` → `FCFormatError` → `call_llm_with_fallback` | `react_cycle.py` → `_should_retry_truncated_tool` → 注入observation |
| 恢复方式 | 重试FC → 降级Text模式 | 注入observation让LLM重新调用工具 |
| 优先级 | 先于截断重试（base_service层在react_cycle层之下） | 后于FC降级（只有LLM成功返回answer后才可能触发） |

**执行顺序**：FC降级在LLM调用层处理格式错误，截断重试在ReAct循环层处理语义截断。两者不会同时触发——FC格式错误时LLM没有返回有效answer，截断重试条件不满足。

---

### 3.7 统一错误处理模块 ✅ 已完成

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
    return ErrorStep(step=step, error_type="tool_execution_error",
                     error_message=str(error), recoverable=True)


def _handle_network_error(agent, error, step):
    """网络错误 → 可重试"""
    logger.error(f"[ErrorHandler] 网络错误: {error}")
    agent.status = AgentStatus.RETRYABLE_ERROR
    return ErrorStep(step=step, error_type="network_error",
                     error_message=str(error), recoverable=True)
```

---

### 3.8 重构后的目录结构

```
services/agent/
├── core_agent/
│   ├── __init__.py
│   ├── base_agent.py              # 不变
│   ├── react_cycle.py             # ✅ 已修改：内联call_llm逻辑，调用llm_stream
│   ├── error_handler.py           # ✅ 新增：统一错误处理
│   ├── agent_initializer.py       # 不变
│   ├── initialize_run_state.py    # 不变
│   ├── step_emitter.py            # 不变
│   ├── tool_manager.py            # 不变
│   └── handlers/
│       ├── action_handler.py      # 不变
│       └── answer_handler.py      # 不变
├── llm_stream.py                  # ✅ 重命名：llm_caller → llm_stream，删除call_llm，call_llm_stream统一FC+Text模式
├── message_builder.py             # 不变（已优化过）
├── observation_formatter.py       # 不变
├── chunk_buffer.py                # 不变
├── tool_cache_manager.py          # 不变
├── tool_executor.py               # 不变
├── tool_retry_engine.py           # 不变
├── universal_agent.py             # ✅ 已修改：TOOL_CACHE_TTL迁移到常量
├── agent_utils/
│   ├── fc_message_types.py        # 不变
│   └── message_utils.py           # 不变
├── steps/                         # 不变
└── types/
    ├── agent_status.py            # ✅ 已修改：新增RETRYABLE_ERROR
    └── result_types.py            # 不变

services/llm/
├── __init__.py                    # 不变
├── base_service.py                # ✅ 已修改：用常量替换硬编码，FCFormatError支持
├── client_sdk.py                  # 不变
├── core.py                        # ✅ 已修改：新增FCFormatError异常类
├── llm_constants.py               # ✅ 新增：LLM层常量
├── stream_parser.py               # 不变
└── model_adapters/                # 不变
```

---

### 3.9 修改清单（按文件）

| # | 文件 | 操作 | 具体修改 | 状态 |
|---|------|------|---------|------|
| 1 | `services/llm/llm_constants.py` | **新增** | LLM层所有常量 | ✅ **已完成** |
| 2 | `services/llm/core.py` | 修改 | 新增 `FCFormatError` 异常类 | ✅ **已完成** |
| 3 | `services/llm/base_service.py` | 修改 | ①用常量替换硬编码(L168-169) ②tool_calls全解析失败时抛FCFormatError | ✅ **已完成** |
| 4 | `services/agent/llm_stream.py`（原llm_caller.py） | **重命名+修改** | ①重命名 ✅ ②删除`call_llm()` ✅ ③`call_llm_fc_stream`→`call_llm_stream` ✅ 支持tools=None ✅ ④新增`call_llm_with_fallback()` ✅ ⑤prompt_logger.log_llm_call迁入 ✅ ⑥用常量替换硬编码 ✅ | ✅ **已完成** |
| 5 | `services/agent/core_agent/react_cycle.py` | 修改 | ①内联call_llm逻辑到_process_single_step ✅ ②导入路径改llm_stream ✅ ③用error_handler替换内联错误处理 ✅ | ⚠️ **部分完成**：未调用`call_llm_with_fallback` |
| 6 | `services/agent/core_agent/error_handler.py` | **新增** | 统一错误处理模块 | ✅ **已完成** |
| 7 | `services/agent/types/agent_status.py` | 修改 | 新增RETRYABLE_ERROR | ✅ **已完成** |
| 8 | `services/agent/universal_agent.py` | 修改 | TOOL_CACHE_TTL迁移到常量 | ✅ **已完成** |

---

### 3.10 数据流变化

**优化前**：
```
react_cycle._process_single_step
  → call_llm(agent)                    # 透传包装
    → call_llm_stream(agent, msg, tools)
      → BaseAIService.request_stream
```

**优化后（当前代码）**：
```
react_cycle._process_single_step
  → [内联] trim_history + prepare_messages + get_openai_tools
  → call_llm_stream(agent, msg, tools)         # FC模式
  → call_llm_stream(agent, msg, tools=None)    # Text模式（降级后备，同一函数）
      → BaseAIService.request_stream
```

**目标（FC降级启用后）**：
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

| # | 任务 | 对应设计 | 前置依赖 | 负责人 | 优先级 | 状态 |
|---|------|---------|---------|--------|--------|------|
| 1 | 新增 `llm_constants.py` 常量文件 | 3.4 | — | 小欧 | P0 | ✅ **已完成** |
| 2 | 新增 `FCFormatError` 异常类 + base_service.py FC格式错误抛出 | 3.6.5 | — | 小欧 | P0 | ✅ **已完成** |
| 3 | 删除 `call_llm()`，内联到 `_process_single_step`（含prompt_logger） | 3.2 | 1 | 小欧 | P0 | ✅ **已完成** |
| 4 | `llm_caller.py` 重命名为 `llm_stream.py` + 修复重复return bug | 3.3 | 3 | 小欧 | P0 | ✅ **已完成** |
| 5 | `call_llm_fc_stream`→`call_llm_stream` 支持tools=None + 新增`call_llm_with_fallback()` | 3.6 | 2, 4 | 小沈 | P0 | ✅ **已完成** |
| 6 | 新增 `error_handler.py` 统一错误处理 | 3.7 | 7 | 小欧 | P1 | ✅ **已完成** |
| 7 | `AgentStatus` 新增 `RETRYABLE_ERROR` | 3.5 | — | 小沈 | P1 | ✅ **已完成** |
| 8 | `universal_agent.py` TOOL_CACHE_TTL 迁移到常量 | 3.4 | 1 | 小健 | P1 | ✅ **已完成** |
| 9 | `base_service.py` 用常量替换硬编码 | 3.4 | 1 | 小健 | P1 | ✅ **已完成** |
| 10 | 前端SSE状态映射：新增 `fc_format_error` 类型识别 | 3.5 | 7 | 小健 | P1 | ✅ **已完成** |
| 11 | FC降级集成测试：模拟FCFormatError→验证降级到Text模式 | 3.6 | 5 | 小沈 | P1 | ✅ **已完成**（6/6通过） |
| 12 | react_cycle.py 调用 `call_llm_with_fallback` 替换 `call_llm_stream` | 3.6.4 | 5 | 小欧 | P0 | ✅ **已完成** |

---

## 五、风险与验收

### 5.1 主要风险

| 风险 | 缓解措施 |
|------|----------|
| 重构引入新bug | 分阶段实施 + 充分测试 + 灰度发布 |
| FC降级逻辑误触发 | FCFormatError严格定义 + 仅FC格式错误才降级 + 网络错误不降级 |
| llm_stream重命名（已完成） | 导入路径已更新（react_cycle.py），无其他文件引用call_llm |
| FC降级接入后性能影响 | FC降级仅在FC格式错误时触发，正常流程无额外开销 |

### 5.2 验收标准

| 指标 | 当前状态 | 目标状态 | 验收标准 |
|------|----------|----------|----------|
| FC降级机制 | 代码已写，未接入 | 完全启用 | react_cycle调用call_llm_with_fallback，FC格式错误时自动降级到Text模式，任务不中断 |
| 调用链简化 | ✅ 2层调用 | 2层调用 | call_llm已删除，react_cycle直接调用call_llm_stream |
| 错误统一处理 | ✅ error_handler | 集中error_handler | ReAct循环错误走handle_react_error |
| RETRYABLE_ERROR状态 | ✅ 已添加 | 添加 | AgentStatus枚举新增，状态转换规则明确 |
| 常量集中 | ✅ llm_constants.py | llm_constants.py | LLM参数全部从常量读取，无硬编码 |
| 任务成功率 | 受FC失败影响 | 提升 | FC失败时任务仍能完成 |

---

**文档状态**：v5.1（小欧实施完成，所有12项任务已完成）  
**关键修复**：①react_cycle接入call_llm_with_fallback（FC降级启用） ②FCFormatError穿透call_llm_stream的except Exception ③call_llm_with_fallback参数名bug修复（tools→openai_tools） ④前端SSE添加fc_format_error类型 ⑤集成测试6/6通过  
**下一步**：运行完整系统测试验证FC降级在真实环境中的表现