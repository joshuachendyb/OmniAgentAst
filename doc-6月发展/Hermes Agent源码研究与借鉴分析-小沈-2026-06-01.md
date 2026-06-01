# Hermes Agent源码研究与借鉴分析

**创建时间**: 2026-06-01 17:10:33
**编写人**: 小沈   **版本**: v2.1
**文档完成时间**: 2026-06-02 05:42:40
**研究范围**: Nous Research Hermes（82万行Python，2019文件）——三次深度研究后的综合分析。只关注**Agent逻辑和模型调用**，不涉及多平台消息推送。
**代码统计**: 核心研读~20文件，~12,000行

---

## 版本历史

| 版本 | 时间 | 签名 | 更新内容 |
|------|------|------|---------|
| **v2.1** | **2026-06-02 05:42:40** | **小沈** | **根据源码分析修正架构描述：§1.2删除"第4层对应Hermes api_call"错误对照，改为Hermes无独立LLM服务层；§1.4删除虚假的4层架构图，改为AIAgent单体+模块化组件的真实结构** |
| **v2.0** | **2026-06-01 18:41:34** | **小沈** | **基于调试笔记深度重构：新增§6流式输出模式；修复丢失6项内容（流式上下文清洗器（StreamingContextScrubber）/三种调取模式/检查点机制/自改进对比/注册模式示例/DEFAULT_AGENT_IDENTITY）；每章增加对比我方系统/使用方法/价值说明/借鉴点分析** |

---

## 一、研究背景与目标

### 1.1 为什么要研究Hermes Agent

OpenCode（Go版，~6.2k核心行）定位是轻量AI编码助手，架构简洁但缺少以下维度的覆盖。Hermes Agent（82万行Python）恰好补全了这些维度：

| 维度 | OpenCode | Hermes Agent（可借鉴） |
|------|---------|----------------------|
| 上下文管理 | SummaryMessageID截断 | Token计数+压缩触发+结构化摘要+会话轮换 |
| 工具安全 | 黑名单check | 三层guardrails（allow/warn/block/halt） |
| 记忆系统 | 无 | 结构化记忆nudge + 技能进化系统 + 三层跨会话记忆 |
| 流式输出 | SSE→前端 | stream_consumer的sync→async队列中转 |
| 并发工具调用 | 同步串行 | ConcurrentToolDispatch（path-scope isolation） |
| 模型调用 | vendor接口 | api_mode统一区分chat_completions/anthropic_messages等 |
| 工具注册 | 静态列表硬编码 | AST自动扫描 + 模块级register()装饰器 |
| 上下文压缩 | SummaryMessageID截断 | 结构化摘要 + 会话轮换 |
| 自我改进 | 无 | Fork自改进循环（background_review） |
| 开放技能标准 | 无 | agentskills.io 开放协议 |

**核心结论**：
Hermes的**Agent循环**、**工具系统**对四层架构的**执行引擎层**有直接参考价值。
Hermes的**记忆系统**和**自改进循环**对**编排层**有启发。
### 1.2 我方架构定位（快速对照）

**Hermes不是分层架构，是"AIAgent单体+模块化组件"模式。以下对照基于技术逻辑等价性，非结构一致。**

| 我方层次 | Hermes对应 | 技术差异 |
|---------|-----------|---------|
| **第4层 LLM服务层** | 无独立层。model adapters（anthropic_adapter/chat_completion_helpers/codex_responses_adapter等）是AIAgent内部调用的辅助模块，api_call是AIAgent方法 | Hermes无provider抽象，api_mode选择不同adapter路径；我方的Router/Provider/重试/限流全套不在Hermes范围 |
| **第3层 执行引擎层** | 部分对应。AIAgent类的run_conversation()驱动turn循环（4751行），协调工具调度+模型调用+上下文管理 | Hermes的turn循环和工具调度在同一类内通过self访问，我方分独立层通过接口通信 |
| **第2层 编排层** | 无对应。execute_turn每次独立，无跨turn编排 | 一致，双方均无为编排单独成层 |
| **第1层 接入层** | stream_consumer queue生产者-消费者模式 | 基本对应，Hermes的背压控制可参考 |

### 1.3 研究分层策略

```
Pass 1（架构层）：Agent循环 / 上下文管理 / api_mode区分
        ↓
Pass 2（组件层）：工具注册 / Guardrails / 并发调度
        ↓
Pass 3（模式层）：sync→async队列中转 / 流式模式 / 记忆系统
```


### 1.4 实际架构（源码结构）

**Hermes不是分层架构，是AIAgent单体（Coordinator模式）+ 模块化子组件。** 子组件通过AIAgent实例的self访问，不是通过层间接口隔离。

```
┌─────────────────────────────────────────────────────────────┐
│              AIAgent（run_agent.py 4831行）                    │
│         全能协调器 — 持有全部状态（model/session/messages     │
│         /tools/iteration_budget），驱动全部流程               │
│                                                               │
│         __init__ → agent/agent_init.py（1657行初始化）        │
│         run_conversation() → agent/conversation_loop.py       │
│         （4751行turn循环，协调工具调度+模型调用+上下文管理）  │
├───────────────────┬───────────────────┬───────────────────────┤
│  模型通信适配器     │  工具系统           │  上下文管理          │
│  (按api_mode切换)  │                     │                     │
│  anthropic_adapter │  model_tools.py    │  context_compressor  │
│  chat_comp_helpers │  （路由1067行）     │  context_engine      │
│  codex_resp_adapter│  tools/registry    │  prompt_caching      │
│  bedrock_adapter   │  （模块自注册）      │                     │
│  gemini_native/    │  tools/*_tool.py   │  记忆系统            │
│  gemini_cloudcode  │  （40+工具实现）     │                     │
│                    │  agent/tool_       │  memory_manager      │
│                    │  guardrails        │  memory_provider     │
│                    │  tool_dispatch_    │                     │
│                    │  helpers           │  提示词构建          │
│                    │  tool_executor     │                     │
│                    │  tool_result_class │  prompt_builder      │
├───────────────────┴───────────────────┴───────────────────────┤
│  支撑模块：retry_utils / error_classifier / iteration_budget   │
│  message_sanitization / trajectory                            │
└─────────────────────────────────────────────────────────────┘
```

**关键特征**（与我方4层架构的区别）：

- Hermes **没有"LLM服务层"**：api_call是AIAgent方法，model adapters是方法级辅助，无Provider/无Router/无独立重试
- Hermes **没有"模型调用层"**：adapter按api_mode选一个路径，但都是AIAgent内部调用的helper
- 工具系统 **散在三处**：`tools/`存实现、`model_tools.py`存路由、`agent/`存安全/调度/执行
- 子模块是 **组件不是层**：通过`self.xxx`访问AIAgent状态，不是通过接口
- 和我方最接近的部分是 **conversation_loop.py的turn循环** 和 **stream_consumer的queue模式**

---
## 二、流式输出模式 ⭐⭐⭐（对我方SSE有直接参考价值）

### 2.1 sync→async 队列中转（stream_consumer）

**核心问题**：LLM调用是同步的（或线程同步），但SSE推送是异步的。Hermes用 `queue.Queue` 做同步→异步的中转——同步回调只管往队列里放，async 协程从队列里取。

```
LLM线程（同步）                      SSE推送协程（异步）
    │                                     │
    ├─ on_delta(text) ──queue.Queue──→  run() drain
    ├─ on_segment_break() ──────────→  分割事件
    └─ on_done() ───────────────────→  完成信号
```

**核心组件**：

| 组件 | 说明 |
|------|------|
| **queue.Queue** | 线程安全队列，LLM的同步回调入队，async协程出队 |
| **run()** | 异步协程，不断drain队列，逐步推送给前端 |
| **on_delta(text)** | 同步回调，LLM吐出文本时调用 |
| **on_segment_break()** | tool_call边界标记，触发前端分段渲染 |
| **think_block过滤** | 状态机过滤推理过程文本 |

### 2.2 对我方SSE推送的参考

```
我方方案：
  LLM流式响应 → sync callback → queue.Queue → async drain → SSE推送
                                                     ↓
                                             rate-limit控制推送频率
```

直接采用 queue.Queue 生产者-消费者模式，替换Hermes的platform adapter层，替换为SSE SSEEvent发送。

### 2.3 流式上下文清洗器（`memory_manager.py:62-225`，源码类名 StreamingContextScrubber）

**用途**：状态机，从流式SSE文本中剥离 `<memory-context>...</memory-context>` 标签跨度。

**为什么需要**：一次性正则表达式会在标签跨chunk时失效——标签开始在一个chunk末尾，结束在下一个chunk开头。

**状态**：
- `_in_span: bool` —— 当前是否在标签内
- `_buf: str` —— 持有可能成为标签前缀的尾部字节
- `_at_block_boundary: bool` —— 验证开放标签是否为块级

**核心方法**：
- `feed(text)`: 返回去除标签后的可见文本
- `flush()`: 流结束时处理尾部

**对我方价值**：
- 状态机模式比正则表达式更可靠——跨chunk标签安全剥离
- 可用于SSE推送到前端前的元数据标签清洗（如 `<!-- experience -->` 标签剥离）

### 对我方价值对比

| 维度 | Hermes做法 | 我方现状 | 借用策略 |
|------|-----------|---------|---------|
| **队列中转** | queue.Queue sync→async | 已有类似 | **确认**——我方使用的就是同一生产者-消费者模式 |
| **segment_break** | tool_call边界触发分段 | 无 | **参考**——tool_call边界触发前端分段渲染 |
| **think_block过滤** | 状态机过滤推理过程 | 无 | **参考**——过滤推理过程文本 |
| **流式上下文清洗器（StreamingContextScrubber）** | 跨chunk标签清洗 | 无 | **参考**——SSE推送前的元数据标签剥离 |
| **前置过滤vs后置过滤** | 入队前过滤 | 出队后过滤 | **参考**——入队前过滤减少无效chunk推送 |

**使用方法**：
1. 第1层（接入层）SSE推送链路中，LLM同步回调入队 → `queue.Queue` → async drain出队 → SSE write
2. `on_segment_break()` 在 tool_call 边界触发前端分段渲染
3. `流式上下文清洗器（StreamingContextScrubber）` 可用于SSE元数据标签剥离

---
## 三、Agent-引擎层

### 3.2 AIAgent类（run_agent.py:294）——薄转发器

核心入口类 `AIAgent`（`run_agent.py:294`, 4816行）本质是一个**薄转发器**。`__init__`（`run_agent.py:317`）将所有参数原封转发给 `agent.agent_init.init_agent()`。关键行为均在 `agent/` 子模块中实现：

| 行为 | 实际实现文件 |
|------|-------------|
| 初始化 + 工具发现 + 系统提示构建 | `agent/agent_init.py` |
| 对话主循环 | `agent/conversation_loop.py`（4707行） |
| API 调用 + 流式处理 | `agent/chat_completion_helpers.py`（2457行） |
| 工具执行（顺序/并发） | `agent/tool_executor.py`（1016行） |
| 工具调用路由 | `agent/agent_runtime_helpers.py` |
| 系统提示组装 | `agent/system_prompt.py` + `agent/prompt_builder.py` |
| 上下文压缩 | `agent/conversation_compression.py` + `agent/context_compressor.py` |
| 内存管理 | `agent/memory_manager.py` + `agent/memory_provider.py` |
| 工具循环护栏 | `agent/tool_guardrails.py` |

### 3.3 对我方四层架构的对应

| 我方层次 | Hermes对应 | 差异 | 借鉴策略 |
|---------|-----------|------|---------|
| 第4层 LLM服务层 | run_agent.py中的api_call | Hermes直接调OpenAI SDK，未抽象Provider层 | **不借**——我方已有更优的Provider抽象 |
| 第3层 执行引擎层 | conversation_loop.py + tools/ | **最有参考价值**——turn循环+工具系统 | **重点借鉴**——护栏/并发调度 |
| 第2层 编排层 | 无独立层，混在run_agent.py中 | Hermes没有单独的编排层 | **部分借鉴**——自改进循环/技能进化 |
| 第1层 接入层 | stream_consumer的queue生产者-消费者模式 | SSE推送的背压控制 | **参考**——queue中转模式 |

---

## 四、Agent核心循环 ⭐⭐⭐（对我方最有价值）

### 3.1 对话循环 flow

入口 `AIAgent.run_conversation()` → `agent.conversation_loop.run_conversation()`（`conversation_loop.py:351`）。

#### 3.1.1 循环条件（`conversation_loop.py:796`）

```python
while (api_call_count < agent.max_iterations) or agent._budget_grace_call:
```

主条件：API调用次数未超 `max_iterations`。`_budget_grace_call` 在上下文token接近极限时给予一次额外机会，让LLM输出最终结果避免截断。

**我方不采用cost预算**，但我们需关注**token计数用于上下文管理**——每次迭代后统计messages总token数，接近上下文窗口时触发压缩或截断。

#### 3.1.2 每次迭代的完整 flow

```
开始迭代
  │
  ├─ 检查中断请求
  ├─ 检查上下文token数（接近极限时触发压缩）
  ├─ 准备 API 消息
  │   ├─ 修复 tool_call 参数
  │   ├─ 注入外部记忆预取内容
  │   ├─ 注入系统提示 + 临时提示
  │   ├─ 注入预填信息
  │   ├─ 应用 Anthropic prompt caching
  │   └─ 清理孤立工具结果
  │
  ├─ API 调用尝试（内层 retry 循环，指数退避）
  │
  ├─ 解析 LLM 响应
  │
  ├─ 分支 A：有 tool_calls
  │   ├─ 去重和裁剪：_cap_delegate_task_calls() + _deduplicate_tool_calls()
  │   ├─ 构建 assistant_message → 追加到 messages
  │   ├─ agent._execute_tool_calls() —— 分派工具执行
  │   │   ├─ _should_parallelize_tool_batch() 决定并发/顺序
  │   │   └─ 每步调用前：guardrails.before_call()
  │   │   └─ 每步调用后：guardrails.after_call()
  │   ├─ 检查 guardrail_halt_decision
  │   └─ 检查 is_compress_needed → 触发上下文压缩
  │
  └─ 分支 B：无 tool_calls
      ├─ 空白响应 → 重试 / 回退前轮次内容 / 思考预填
      └─ 有内容 → 预处理后跳出循环
```

#### 3.1.3 循环退出原因

| 退出原因 | 含义 | 我方对应 |
|----------|------|---------|
| `interrupted_by_user` | 用户中断 | 我方已有（task.cancel） |
| `context_limit` | 上下文token接近极限触发退出 | **我方缺失**——需加token计数 |
| `guardrail_halt` | 工具循环护栏触发暂停 | **我方缺失** |
| `text_response(finish_reason=...)` | 正常文本响应 | 我方已有 |
| `max_iterations_reached` | 达到 max_iterations | 我方有简单版本 |

循环退出后若 `final_response is None`（max_iterations达到但无响应），额外调用一次无工具API请求生成摘要（`_handle_max_iterations`, `conversation_loop.py:4332`）。

### 3.2 上下文Token管理（计数+压缩触发）⭐⭐⭐⭐

**我方不做cost预算**，但Hermes的token计数和上下文管理机制值得借鉴。

**我们需要什么**：不关心cost价格，但需要token计数来合理管理LLM上下文窗口——何时触发压缩、何时截断历史、何时grace_call。

#### Hermes的IterationBudget结构（我方参考但不取cost）

```python
# Hermes原始做法（我方只取max_turns，不取max_cost）
class IterationBudget:
    max_turns: int = 50       # 我方：取——消息轮次数限制
    timeout: int = 600        # 我方：可选——超时控制
    max_cost: float = 0.50    # 我方：❌ 不要——不做cost预算
    behavior: str = "stop"    # 我方：取——边界行为控制
    grace_call: bool = True   # 我方：取——允许一次额外LLM调用输出最终结果
```

**核心价值**：grace_call机制——在token接近上下文窗口极限时，允许模型再输出一次最终结果再终止，避免截断不完整响应。

#### 我方的上下文管理方案

```python
class ContextManager:
    """管理LLM消息上下文的token计数与压缩触发"""
    
    def __init__(self, max_context_tokens: int = 128000):
        self.max_context_tokens = max_context_tokens
        self.compress_threshold = 0.75      # token达75%触发压缩
        self.hard_limit_ratio = 0.95        # token达95%强制截断
        self.grace_on_limit = True          # 极限前给一次机会
    
    def check_messages(self, messages: list) -> ContextStatus:
        """检查当前消息列表的token状态"""
        total = self._count_tokens(messages)
        if total >= self.max_context_tokens * self.hard_limit_ratio:
            return ContextStatus.HARD_LIMIT     # 强制截断历史
        if total >= self.max_context_tokens * self.compress_threshold:
            return ContextStatus.COMPRESS_NOW   # 触发压缩
        return ContextStatus.OK
        
    def should_grace(self, has_pending_tool: bool) -> bool:
        """极限前是否允许额外一次LLM调用"""
        return self.grace_on_limit and has_pending_tool
```

#### 对我方价值对比

| 维度 | Hermes做法 | 我方现状 | 借用策略 |
|------|-----------|---------|---------|
| **max_turns** | API调用次数限制 | 无 | **直接引入**——防止无限循环 |
| **grace_call** | 极限前多给一次机会 | 无 | **直接复用**——防止截断 |
| **behavior模式** | stop/warn/ignore | 无 | **参考**——stop是安全默认 |
| **cost核算** | 模型价格表×tokens | **不需要** | ❌ 不做cost预算 |
| **token计数** | 隐式在消息构建中 | 无 | **必须引入**——用于上下文管理 |
| **压缩触发** | is_compress_needed() | 无 | **直接复用**——token阈值触发压缩 |

**使用方法**：
1. 在第3层（执行引擎层）新建 `ContextManager` 组件
2. 统计每次LLM调用后的总token数，逼近阈值时触发压缩
3. `grace_call` 在上下文接近极限时若还有进行中的tool_call则允许一次额外llm调用
4. token计数使用tiktoken（或同类库），不涉及cost价格计算

### 3.3 工具循环护栏（tool_guardrails.py, 475行）⭐⭐⭐⭐

**纯副作用自由控制器**，不依赖任何 AIAgent 状态——可独立测试和验证。

#### 3.3.1 四种检测类型

| 检测类型 | 触发条件 | 默认阈值 |
|---------|---------|---------|
| **精确失败重复** | 相同的 `ToolCallSignature`（tool_name + 规范参数hash）连续失败 | warn=2, block=5 |
| **同工具失败** | 同一 tool_name 的失败 | warn=3, halt=8 |
| **幂等无进展** | 幂等工具返回相同结果哈希 | warn=2, block=5 |
| **变异工具** | 变异工具不跟踪无进展 | - |

#### 3.3.2 四级响应

| 级别 | 含义 | 行为 |
|------|------|------|
| `allow` | 允许执行 | 无操作 |
| `warn` | 警告（追加到工具结果） | 运行时在工具结果尾部追加 `[Tool loop warning: ...]` |
| `block` | 阻塞执行（返回合成错误） | `before_call` 返回 `action="block"`，合成 `{"error": "Blocked..."}` |
| `halt` | 暂停整个轮次 | `after_call` 设置 `_tool_guardrail_halt_decision`，循环跳出 |

#### 3.3.3 幂等工具名单

`IDEMPOTENT_TOOL_NAMES`：`read_file`, `search_files`, `web_search`, `web_extract`, `session_search`, `browser_snapshot` 等只读操作。

`MUTATING_TOOL_NAMES`：`terminal`, `execute_code`, `write_file`, `patch`, `todo`, `memory` 等写操作。

#### 对我方价值对比

| 维度 | Hermes做法 | 我方现状 | 借用策略 |
|------|-----------|---------|---------|
| **检测维度** | 4种（失败重复/同工具/幂等/变异） | 只检查命令黑名单 | **部分引入**——先做精确失败重复检测 |
| **响应级别** | 4级（allow/warn/block/halt） | 只有通过/禁止 | **直接引入**——warn用于软限制，halt用于硬停止 |
| **副作用** | 纯函数，不依赖AIAgent状态 | 耦合在agent中 | **直接复用**——独立测试 |
| **幂等名单** | 显式声明幂等/变异工具 | 无 | **直接复用**——配置化 |

**使用方法**：
1. 独立 `tool_guardrails.py` 模块，纯函数设计
2. 维护 `ToolCallSignature` → 即 `(tool_name, normalized_args_hash)`
3. 每次工具调用前 `guardrails.before_call(signature)` → allow/block
4. 每次工具调用后 `guardrails.after_call(signature, result)` → 更新计数
5. 幂等工具名单和变异工具名单从配置加载

### 3.4 工具执行 flow 详解

`AIAgent._execute_tool_calls()`（`run_agent.py:4471`）：

1. `_should_parallelize_tool_batch()` 检查工具批是否可并行
2. 读类工具可并行；文件读写需检查路径是否冲突
3. 串行路径 → `agent/tool_executor.execute_tool_calls_sequential()`
4. 并行路径 → `agent/tool_executor.execute_tool_calls_concurrent()`

**每个工具调用的执行步骤**（`tool_executor.py:110`+）：

1. `guardrails.before_call()`：检查是否blocked（hard_stop模式）
2. **检查点**：`write_file`/`patch`/`terminal` 前创建文件系统检查点——用于失败时回滚
3. `agent._invoke_tool()` → `agent_runtime_helpers.invoke_tool()` → `handle_function_call()`
4. `guardrails.after_call()`：记录观察结果，若warn追加指导文本

**检查点机制**（调试笔记补充，我方缺失）：在写操作前创建文件系统快照，工具执行失败时可回滚到执行前状态。三个触发工具：`write_file`、`patch`、`terminal`。

**三种并发判定**：

| 类型 | 策略 |
|------|------|
| NEVER_PARALLEL | 串行执行（写操作、状态修改） |
| PARALLEL_SAFE | 完全并发（只读操作、独立计算） |
| 路径不重叠 | 并发执行（操作不同文件/资源） |

#### 对我方价值对比

| 维度 | Hermes做法 | 我方现状 | 借用策略 |
|------|-----------|---------|---------|
| **并发判定** | NEVER_PARALLEL/PARALLEL_SAFE/路径不重叠 | 全部串行 | **直接复用**——异步并发执行只读工具 |
| **路径检测** | 检查文件路径是否冲突 | 无 | **参考**——可简化，先做NEVER_PARALLEL和PARALLEL_SAFE |
| **执行方式** | 线程池(同步工具)+asyncio(异步工具) | asyncio | **适配**——Hermes用线程，我方用asyncio.gather |
| **检查点机制** | write_file/patch/terminal前快照 | 无 | **参考**——对文件操作工具提供回滚能力 |

---

## 四、Prompt 架构 ⭐⭐（部分借鉴）

### 4.1 三层系统提示架构

核心文件：`agent/system_prompt.py`（407行）+ `agent/prompt_builder.py`（1507行）。

`build_system_prompt_parts()`（`system_prompt.py:61`）返回字典 `{stable, context, volatile}`，由 `build_system_prompt()` 用 `"\n\n"` 连接。

**关键设计决策**：提示**每个会话只构建一次**，缓存于 `agent._cached_system_prompt`，仅上下文压缩后重建。日期格式（`%A, %B %d, %Y`）而非分钟精度，保持前缀缓存命中。

#### 4.1.1 三层结构

| 层级 | 内容 | 缓存策略 | 对应我方 |
|------|------|---------|---------|
| **稳定层（stable）** | 身份/工具指导/技能/平台/环境 | 可缓存，很少变 | system prompt主体 |
| **上下文层（context）** | 调用者system_message/上下文文件 | 会话级缓存 | 项目上下文 |
| **易变层（volatile）** | 记忆快照/用户配置/时间戳 | 每次重构 | 经验注入 |

**三层组装**（`system_prompt.py:61`）：
```python
def build_system_prompt_parts():
    return {
        "stable": stable_layer,     # 身份+工具+技能+平台+环境（每次会话构建一次）
        "context": context_layer,   # 项目上下文+system_message
        "volatile": volatile_layer  # 记忆快照+用户配置+时间戳（每轮重构）
    }
```

#### 稳定层详细门控条件（调试笔记补充）

稳定层包含20+条件门控组件，关键在于**按工具存在性动态注入**：

| 组件 | 门控条件 | 对我方参考 |
|------|---------|-----------|
| SOUL.md 身份 | `agent.load_soul_identity` | 类似AGENTS.md身份定义 |
| `DEFAULT_AGENT_IDENTITY`（回退） | SOUL.md未加载 | **直接可借**——身份回退模板 |
| HERMES_AGENT_HELP_GUIDANCE | 始终注入 | 通用行为引导 |
| TASK_COMPLETION_GUIDANCE | 默认True+有工具 | 完成标准引导 |
| memory/session_search/skills行为指导 | 按valid_tool_names存在性 | **按工具集动态注入** |
| 模型操作指导（Google/GPT/Grok） | 按模型名称匹配 | **不采用**——我方不针对模型 |
| 技能提示 | 存在技能工具 | 经验注入 |
| 环境探测 | `agent._environment_probe` | 环境上下文 |
| 平台提示 | 按platform键匹配 | **不采用**——单平台 |

**DEFAULT_AGENT_IDENTITY**（`prompt_builder.py:120-128`）——身份回退模板：
```python
"You are Hermes Agent, an intelligent AI assistant created by Nous Research. "
"You are helpful, knowledgeable, and direct. You assist users with a wide "
"range of tasks including answering questions, writing and editing code, "
"analyzing information, creative work, and executing actions via your tools. "
"You communicate clearly, admit uncertainty when appropriate, and prioritize "
"being genuinely useful over being verbose unless otherwise directed below. "
"Be targeted and efficient in your exploration and investigations."
```

### 4.2 提示缓存策略（`agent/prompt_caching.py`, 79行）

策略名：**`system_and_3`**（Anthropic原生）。

- 最多 **4 个 `cache_control` 断点**
- 第1个：系统提示消息（`role == "system"`）
- 最多3个：最后3条非system消息
- TTL可选：`"5m"`（默认）或 `"1h"`
- 输入深拷贝避免污染

### 4.3 平台提示（prompt_builder.py:442-621）

为每个平台（whatsapp/telegram/discord/slack等15+平台）定义了专门的平台提示，告诉模型该平台的界面特性。

**我方不采用**——我们是单平台（Web SSE），不需要多平台提示。

### 对我方价值对比

| 维度 | Hermes做法 | 我方现状 | 借用策略 |
|------|-----------|---------|---------|
| **三层结构** | stable/context/volatile | 单层system prompt | **参考**——三层有利于缓存命中 |
| **缓存策略** | 会话级缓存，仅压缩后重建 | 无缓存 | **参考**——减少重复prompt构建成本 |
| **前缀缓存友好** | 日期格式到天，非分钟 | 无特殊处理 | **参考**——provider侧缓存需要稳定的前缀 |
| **记忆注入** | 易变层动态注入 | 无 | **参考**——volatile层是记忆注入的理想位置 |
| **动态门控** | 按valid_tool_names存在性注入 | 静态prompt | **参考**——按可用工具集动态组装 |
| **DEFAULT_AGENT_IDENTITY** | 身份回退模板 | 无 | **直接可借**——我方agent身份基座 |
| **平台提示** | 15+平台提示 | 单平台 | **不采用** |

**使用方法**：
1. 第2层（编排层）构建system message时，可参考三层分离
2. 稳定层：身份/工具定义（每次会话构建一次）
3. 易变层：当前经验/knowledge nudge（每轮注入）
4. 日期格式使用 `YYYY-MM-DD` 而非精确到秒，保持前缀一致性
5. 按工具集动态注入：只有可用工具才注入对应的使用指导

---

## 五、工具系统 ⭐⭐⭐（直接可借）

### 5.1 AST 自动扫描注册（`tools/registry.py`, 589行）

#### 5.1.1 核心机制

`discover_builtin_tools()`（`registry.py:48`）：

1. 扫描 `tools/*.py` 所有文件（排除 `__init__`、`registry.py`、`mcp_tool.py`）
2. 对每个文件做AST解析，检查模块级的 `registry.register()` 调用
3. 通过 `importlib.import_module()` 导入——模块级调用自动执行注册

**消除手动 `ensure_tools_registered()` 的必要性**！

**重要澄清**：Hermes **没有工具基类**（没有 `BaseTool`、`AbstractTool` 这类继承体系）。工具就是**普通的 Python 函数**（同步或异步），通过 `registry.register()` 注册为一个 `ToolEntry` 实例。`ToolEntry`（`registry.py:77`）是一个**纯数据持有器**（`__slots__` 优化），不是可继承的 ABC：

```python
class ToolEntry:
    __slots__ = ("name", "toolset", "schema", "handler", "check_fn",
                 "requires_env", "is_async", "description", "emoji",
                 "max_result_size_chars", "dynamic_schema_overrides")
    def __init__(self, name, toolset, schema, handler, ...):
        self.name = name
        self.handler = handler   # 就是普通函数引用
        ...
```

**AST 自动扫描场景**：消除"注册汇总文件"——每个工具文件在模块级调用 `registry.register()`，import 时自动注册。不需要一个中央文件来 `import` 所有工具文件。

#### 5.1.2 三种 register() 写法风格

下面三个 `registry.register()` 调用**做的事情完全一样**——把一个工具名、它接收什么参数（schema）、谁来干活（handler）、什么环境能用（check_fn）注册到系统。区别只是写法风格：

```python
# 风格1：命名函数 + 参数少 → 一行（file_tools.py:1436-1439）
registry.register(name="read_file", toolset="file", schema=READ_FILE_SCHEMA,
    handler=_handle_read_file, check_fn=_check_file_reqs, emoji="📖",
    max_result_size_chars=100_000)

# 风格2：lambda 函数 + 参数多 → 多行（web_tools.py:1326）
registry.register(
    name="web_search", toolset="web", schema=WEB_SEARCH_SCHEMA,
    handler=lambda args, **kw: web_search_tool(args.get("query", ""), limit=...),
    check_fn=check_web_api_key, requires_env=_web_requires_env(),
    is_async=False, emoji="🔍", max_result_size_chars=100_000)

# 风格3：命名函数 + 参数多 → 多行（terminal_tool.py:2590）
registry.register(
    name="terminal", toolset="terminal", schema=TERMINAL_SCHEMA,
    handler=_handle_terminal, check_fn=check_terminal_requirements,
    emoji="💻", max_result_size_chars=100_000)
```

**关键理解**：

- **handler = 谁来干活**。传一个函数引用，工具被调用时就执行这个函数
- 写法上只有两种情况：**命名函数**（`_handle_read_file`，在文件前面定义好了）或 **lambda**（就地写一行逻辑，不值得起名字）
- 格式用一行还是多行？**纯粹看参数多少**，参数少凑得下一行就行，参数多就换行整齐点。**和业务逻辑无关**

**所以不要把"三种模式"当成三种注册方式，它们就是同一个 register()**，写法习惯不同而已。

#### 5.1.3 ToolEntry 结构

| 字段 | 含义 | 我方对应 |
|------|------|---------|
| `name` | 工具名 | tool name |
| `toolset` | 所属工具集 | category |
| `schema` | OpenAI格式JSON schema | Pydantic model |
| `handler` | 调用函数 | tool function |
| `check_fn` | 可用性检测函数 | 环境检测 |
| `requires_env` | 需要的环境变量列表 | env check |
| `is_async` | 是否异步 | 同步/异步 |
| `emoji` | 显示emoji | 前端展示 |
| `max_result_size_chars` | 结果大小上限 | 截断策略 |
| `dynamic_schema_overrides` | 运行时动态schema覆盖 | 我方暂无 |

#### 5.1.4 check_fn TTL 缓存（`registry.py:109-148`）

- **TTL**: 30秒（`_CHECK_FN_TTL_SECONDS`）
- **缓存键**: Callable 函数对象本身
- **线程安全**: `_check_fn_cache_lock`（`threading.Lock`）
- **异常处理**: 任何异常视为 `False`（工具标记为不可用）

`get_definitions()` 中还有一层**单次调用内缓存**，避免同一 `check_fn` 在同一 definitions 请求中被重复调用。

#### 5.1.5 内置工具总览

Hermes 共约 **68 个 `registry.register()` 调用**，分布在约 **32 个工具文件**中。按 toolset 分类：

| toolset | 文件 | 工具数 | 典型工具 |
|---------|------|--------|---------|
| **file** | `file_tools.py` | 4 | read_file, write_file, patch, search_files |
| **web** | `web_tools.py` | 2 | web_search, web_extract |
| **terminal** | `terminal_tool.py` | 1 | terminal |
| **browser** | `browser_tool.py` + `browser_cdp_tool.py` + `browser_dialog_tool.py` | ~13 | navigate, click, snapshot, fill, evaluate... |
| **code_execution** | `code_execution_tool.py` | 1 | execute_code |
| **vision** | `vision_tools.py` | 2 | vision_query, vision_extract |
| **memory** | `memory_tool.py` | 1 | memory（经验读写） |
| **session_search** | `session_search_tool.py` | 1 | session_search（跨会话FTS5搜索） |
| **skills** | `skills_tool.py` | 2 | skills_list, skill_view |
| **skill_manager** | `skill_manager_tool.py` | 1 | skill_manage（create/edit/patch/delete/write/remove） |
| **delegate** | `delegate_tool.py` | 1 | delegate_task（子代理委派） |
| **todo** | `todo_tool.py` | 1 | todo（待办管理） |
| **kanban** | `kanban_tools.py` | 9 | 项目/任务/看板管理 |
| **image_gen** | `image_generation_tool.py` | 1 | image_generation |
| **video_gen** | `video_generation_tool.py` | 1 | video_generation |
| **tts** | `tts_tool.py` | 1 | text_to_speech |
| **computer_use** | `computer_use_tool.py` | 1 | computer（屏幕点击） |
| **clarify** | `clarify_tool.py` | 1 | clarify（向用户提问澄清） |
| **cron** | `cronjob_tools.py` | 1 | cron_schedule |
| **agent_mix** | `mixture_of_agents_tool.py` | 1 | mixture_of_agents (MoA) |
| **homeassistant** | `homeassistant_tool.py` | 4 | 智能家居控制 |
| **feishu** | `feishu_doc_tool.py` + `feishu_drive_tool.py` | 5 | 飞书文档/云盘 |
| **discord** | `discord_tool.py` | 2 | 消息推送 |
| **yuanbao** | `yuanbao_tools.py` | 5 | 腾讯元宝集成 |
| **x_search** | `x_search_tool.py` | 1 | X/Twitter搜索 |

**核心认知**：Hermes 的工具是**"扁平函数集合"**，不是"类继承体系"。这与我方当前设计一致——工具就是一个函数 + schema 描述。`ToolEntry` 只是给这个函数加上元数据标签（toolset、check_fn、emoji 等）。

#### 5.1.6 完整生命周期：从注册到给LLM再到执行

```
编写工具 → register() → 系统启动 → get_definitions() → 发LLM → LLM调用 → dispatch()
  │            │           │            │                   │        │
  │   schema是  │   AST扫描  │  检查     │  {"type":"function",│ LLM   │ 调 handler
  │   OpenAI   │  .py文件  │  check_fn │   "function":{      │ 返回  │ 执行
  │   格式dict  │  import   │  是否可用  │    "name":"...",   │ tool_ │
  │   (手写)   │  自动注册  │            │    "description":, │ call  │
  │            │           │            │    "parameters":{}}}|       │
  └─READ_FILE_ └─registry  └─check_fn_ └─get_definitions()──┘       └─dispatch()
    SCHEMA       .register()  cached      第383行                      第390行
    第1281行                                                  ↓
                                                        实际发给LLM的样子：
                                                        {"type": "function",
                                                         "function": {
                                                           "name": "read_file",
                                                           "description": "...",
                                                           "parameters": {
                                                             "type": "object",
                                                             "properties": {...}
                                                           }
                                                         }}
```

**关键理解**：`schema` 字段（如 `READ_FILE_SCHEMA`）在定义时**已经是 OpenAI 格式**了——它就是个 dict，里面写了 `name`、`description`、`parameters`。`get_definitions()` 只是套了个 `{"type": "function"}` 的外壳（`registry.py:383`）。所以不存在"从 handler 转换成 OpenAI 格式"这回事——schema 和 handler 是分开的，schema 一开始就是 OpenAI 格式。

| 维度 | Hermes做法 | 我方现状 | 借用策略 |
|------|-----------|---------|---------|
| **注册模式** | AST自动扫描 + register()调用 | 手动ensure_tools_registered() | **直接引入**——AST自动扫描更干净 |
| **三种风格** | 一行式/lambda/命名函数 | 单一模式 | **参考**——按工具复杂度选择风格 |
| **check_fn缓存** | 30s TTL + 线程安全 | 每次调用检查 | **直接复用**——check_fn缓存减少IO开销 |
| **可插拔** | importlib动态导入 | 静态导入 | **参考**——动态导入支持插件扩展 |
| **ToolEntry结构** | 完整字段（含emoji/check_fn等） | 简单注册 | **参考**——丰富ToolEntry字段 |

**使用方法**：
1. 保留我方 `ToolRegistry`，但注册方式改为AST自动扫描
2. 文件命名约定：`tools/*_register.py` 为AST扫描目标
3. 三种注册风格：简单工具一行式、中等工具命名函数、复杂工具多行lambda
4. `check_fn` 缓存：30秒TTL，`lru_cache` 或自定义实现
5. `max_result_size_chars` 引入截断保护

### 5.2 工具分组（Toolset）（`toolsets.py`, 882行）

68 个工具不可能全部塞给 LLM。Hermes 把它们分成**组**（toolset），按需启用：

```python
TOOLSETS = {
    "web":       {"tools": ["web_search", "web_extract"], "includes": []},
    "terminal":  {"tools": ["terminal", "process"],       "includes": []},
    "browser":   {"tools": ["browser_navigate", ...],     "includes": []},
    "debugging": {"tools": ["terminal", "process"], "includes": ["web", "file"]},
}
```

**关键特性**：
- 一个工具可属于多个组（`web_search` 既在 `web` 也在 `debugging`）
- `includes`：组可以包含其他组。比如启用 `debugging` 时，自动带入 `terminal` + `web` + `file` 全部工具
- 展开时递归扁平化，不会死循环（有循环检测）

**对我方**：我方目前只有简单 category 分类，Hermes 的 `includes` 支持"调试模式 = 终端 + 网页 + 文件"这种组合逻辑，可参考。

### 5.3 LLM说"调这个工具"→ 怎么接住并执行（`model_tools.py`, 1067行）

LLM 返回一条 `tool_call`"我要调用 read_file，参数是 path=xxx"，到真正执行 `_handle_read_file`，中间经过几道处理：

```
LLM说"调 read_file(path='xxx')"
       ↓
handle_function_call(name, args)
  │
  ├─ coerce_tool_args()         → 参数类型修正
  │                                schema 说 offset 是 integer，
  │                                但有的模型返回 "1"（字符串），
  │                                这里转成 1（数字）
  │                                不然 Python range("1") 报错
  │
  ├─ 安全检查/审批              → 写文件前确认用户同意
  ├─ 读循环跟踪                → 连续读相同文件会重置计数器
  │
  └─ registry.dispatch(name, args)  → 找到 handler 并执行
       ├─ 如果是异步工具        → 用持久化事件循环跑
       └─ 出错                 → 清洗错误信息再返回（防干扰LLM）
```

**`coerce_tool_args()` 不是多余的**——LLM 不一定严格按 JSON Schema 类型输出，有的模型数字经常传成字符串。不加这层，`range("1")` 直接崩。

**对我方参考**：

| Hermes做法 | 我方对应 | 差异 | 复用策略 |
|------------|---------|------|---------|
| `coerce_tool_args()` 类型强制转换（string→int/bool） | `ToolRetryEngine.normalize_params()` 只做参数名过滤 | 我方schema是Pydantic（Hermes是dict），但原理一样 | 在 `normalize_params()` 中追加类型转换逻辑：遍历 `input_schema.properties`，按type字段将字符串转成对应Python类型 |
| `_sanitize_tool_error()` 清洗错误信息（去XML标签/特殊字符） | **缺失**——错误文本原样返回 | 无 | 新建 `_sanitize_tool_error()`，用正则剥离 `<...>` 标签和不可见字符后再返回给LLM |

### 5.4 六种执行后端（`tools/environments/`, ~4970行）

所有后端实现同一接口 `BaseEnvironment.execute()`，通过 `_create_environment()` 工厂函数基于 `TERMINAL_ENV` 环境变量选择：

| 后端 | 适用场景 | 对我方参考 |
|------|---------|-----------|
| **local** | 开发/测试 | 我方当前唯一模式 |
| **docker** | 隔离执行 | **参考**——安全沙箱 |
| **singularity** | HPC/科学计算 | 暂不引入 |
| **modal** (直连) | 云端Serverless | 暂不引入 |
| **modal** (托管) | Nous托管 | 暂不引入 |
| **daytona** | 云端开发环境 | 暂不引入 |
| **ssh** | 远程机器 | **参考**——远程执行 |

**通用模型**：spawn-per-call——每个命令启动一个新的 `bash -c` 进程。会话快照在init时捕获一次，每个命令前重新source。CWD通过stdout标记持久化。

**Liveness 机制**：
- `touch_activity_if_due()`: 每10秒发射活动回调
- 中断检查：每个命令执行中定期检查 `is_interrupted()`

#### 对我方价值对比

| 维度 | Hermes做法 | 我方现状 | 借用策略 |
|------|-----------|---------|---------|
| **统一接口** | BaseEnvironment.execute() | Python subprocess | **参考**——接口统一化 |
| **spawn-per-call** | 每个命令新进程，无状态污染 | 同 | **一致**——我方也如此 |
| **liveness回调** | 10s emit | 无 | **参考**——长时间命令的进度通知 |
| **环境选择** | 配置化 | 硬编码 | **参考**——配置化支持扩展 |

---



## 七、记忆系统 ⭐⭐（架构参考，暂不深入）

### 7.1 MemoryManager + MemoryProvider 抽象

#### 7.1.1 MemoryProvider 抽象基类（`agent/memory_provider.py`, 296行）

```python
class MemoryProvider(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...                # 唯一标识符
    
    @abstractmethod
    def is_available(self) -> bool: ...       # 配置/凭据就绪检查
    
    @abstractmethod
    def initialize(self, session_id): ...     # 创建资源、建立连接
    
    @abstractmethod
    def get_tool_schemas(self) -> List[Dict]: ...  # 返回OpenAI格式工具定义
    
    @abstractmethod
    def handle_tool_call(self, tool_name, args) -> str: ...  # 执行工具调用
    
    # 可选覆盖
    def system_prompt_block(self): return ""  # 注入到系统提示的静态文本
    def prefetch(self, query, session_id): return ""  # 预取上下文
    def sync_turn(self, user, assistant): pass  # 持久化完成轮次
    def shutdown(self): pass
```

#### 7.1.2 MemoryManager（`agent/memory_manager.py`, 653行）

编排**内置内存**（MEMORY.md + USER.md）+ **至多一个外部内存提供者**。

关键方法：

| 方法 | 功能 |
|------|------|
| `prefetch_all(query, session_id)` | 预取所有外部提供者内容 |
| `sync_all(text)` | 同步所有提供者 |
| `handle_tool_call(tool_name, args)` | 按 `_tool_to_provider` 路由到正确提供者 |
| `get_all_tool_schemas()` | 聚合所有提供者的工具定义 |

**工具调用路由**：`handle_tool_call()` 在 `_tool_to_provider` 字典中查找工具名，未找到返回 `tool_error`，找到则委托给 `provider.handle_tool_call()`。

#### 7.1.3 MemoryProvider 可选钩子（调试笔记补充）

| 钩子 | 触发时机 |
|------|---------|
| `on_turn_start(turn_number, message)` | 每轮开始 |
| `on_session_end(messages)` | 会话结束时 |
| `on_session_switch(new_session_id, ...)` | 会话ID轮换时 |
| `on_pre_compress(messages)` | 压缩前提取洞察 |
| `on_delegation(task, result, ...)` | 子代理完成时 |
| `on_memory_write(action, target, content, metadata)` | 内置内存写入时镜像 |

#### 对我方价值对比

| 维度 | Hermes做法 | 我方现状 | 借用策略 |
|------|-----------|---------|---------|
| **MemoryProvider抽象** | ABC定义可插拔后端 | 无记忆系统 | **架构参考**——先了解，后续需要时引入 |
| **MemoryManager门面** | 多provider编排 | 无 | **参考**——observer模式管理多个记忆源 |
| **工具路由** | provider → tool 映射表 | 无 | **参考**——扩展性设计 |
| **生命周期钩子** | on_turn_start/on_session_end等 | 无 | **参考**——经验存储的事件驱动接口 |

### 7.2 三层跨会话记忆系统

| 层级 | 存储方式 | 检索延迟 | 信息类型 | 我方参考 |
|------|---------|---------|---------|---------|
| **L1: 消息级检索** | SQLite + FTS5 | 毫秒 | 历史消息全文检索 | **直接可借**——FTS5+trigram双表 |
| **L2: 外部记忆提供者** | 插件式（Honcho等） | 百毫秒~秒级 | 用户模型+辨证洞察 | **架构参考** |
| **L3: 文件式记忆** | MEMORY.md/USER.md | 毫秒 | 声明式持久化知识 | **参考**——类似我方经验存储 |

#### FTS5 全文搜索策略（L1核心）

```sql
-- 双表策略：英文用unicode61，CJK用trigram
CREATE VIRTUAL TABLE messages_fts USING fts5(content, tokenize='unicode61');
CREATE VIRTUAL TABLE messages_fts_trigram USING fts5(content, tokenize='trigram');
```

**查询策略**：
```
query → sanitize_fts5() → 检查是否是CJK（含中文字符）
  ├─ 非CJK → messages_fts MATCH（快速路径）
  └─ CJK → 检查每个token字符数
      ├─ ≥3 CJK字符 → messages_fts_trigram MATCH
      └─ 1-2 CJK字符 → LIKE子串匹配（降级）
```

**降级机制**：当Python构建的SQLite没有FTS5模块时，优雅降级为LIKE查询。

#### 会话搜索工具3种形状

| 形状 | 参数 | 行为 |
|------|------|------|
| **DISCOVERY** | `query` | FTS5搜索→按会话谱系去重→每个命中返回snippet+±5消息窗口+bookends |
| **SCROLL** | `session_id` + `around_message_id` | 以指定消息为中心±window条消息，无FTS5 |
| **BROWSE** | 无参数 | 返回最近会话（标题/预览/时间戳） |

**对我方参考**：三种形状分离了不同查询场景——搜索用DISCOVERY，追溯用SCROLL，概览用BROWSE。

### 7.3 上下文压缩（`agent/conversation_compression.py` + `agent/context_compressor.py`）

#### 触发时机

1. **预检压缩**（`conversation_loop.py:587`）：进入主循环前估算token数，超过阈值则压缩
2. **工具执行后**（`conversation_loop.py:3885`）：每次工具执行后检查 `should_compress()`
3. **手动触发**：用户 `/compress` 命令

#### 压缩流程

```
compress_context(messages, system_message)
  ├─ 1. 惰性可行性检查（首次压缩时探测辅助模型）
  ├─ 2. 获取压缩锁（防止同一session并发→会话分叉）
  ├─ 3. 通知内存提供者 on_pre_compress()
  ├─ 4. 运行 context_compressor.compress()
  ├─ 5. 处理压缩中止（辅助LLM失败时无操作返回）
  ├─ 6. 追加待办快照
  ├─ 7. 使系统提示失效 + 重建
  ├─ 8. 轮换SQLite会话（结束旧会话、创建子会话）
  ├─ 9. 通知上下文引擎 + 内存提供者
  ├─ 10. 多次压缩警告（≥2次后警告质量下降）
  └─ 11. 释放压缩锁
```

**对我方价值**：
- 结构化摘要模板（Active Task / In Progress / Pending / Remaining）——直接可借
- 缩放预算：默认20%上下文窗口——合理比例
- 尾部保护：保留最后N条消息——保护最近上下文
- 惰性可行性检查：首次压缩时才探测辅助模型，不浪费初始化时间
- 压缩锁：防止同一session并发压缩→会话分叉

### 7.4 Honcho辨证记忆系统（`plugins/memory/honcho/__init__.py`, 1800+行）

#### 核心机制

Honcho是一个AI-native跨会话用户建模系统，通过 `MemoryProvider` ABC接入Hermes。

#### 5个工具

| 工具 | 用途 | 是否调用LLM |
|------|------|-------------|
| `honcho_profile` | 读取/更新对等卡片（curated facts） | ❌ 无LLM |
| `honcho_search` | 语义搜索原始对话摘要 | ❌ 无LLM |
| `honcho_context` | 获取完整会话上下文快照 | ❌ 无LLM |
| `honcho_reasoning` | LLM合成回答问题 | ✅ Honcho端LLM |
| `honcho_conclude` | 创建/删除持久化结论 | ❌ 直接写入 |

#### 辨证推理（Dialectic Reasoning）

**重要澄清**：Honcho使用的"dialectic"并非"支持方+反对方碰撞"模式，而是**多层递进式LLM推理**：

| depth | 行为 | 说明 |
|-------|------|------|
| depth=1 | 1次冷启动/温会话查询 | 单人设问，LLM直接回答 |
| depth=2 | 第0次 + 第1次自审 | 第1次对第0次结果进行差距分析 |
| depth=3 | 第0次 + 第1次 + 第2次调和 | 第2次检查一致性，调和矛盾 |

**提前退出**：`_signal_sufficient()` 检测输出是否≥100字符且有结构化内容 → 跳过后续pass。

#### 三种调取模式（调试笔记补充）

| 模式 (recall_mode) | 自动注入 | 工具可用 | 使用场景 |
|-------------------|---------|---------|---------|
| **context** | ✅ | ❌ | 完全自动，无感知 |
| **tools** | ❌ | ✅ | Agent自主决策调取 |
| **hybrid** | ✅ | ✅ | 自动辅助 + 按需深查 |

#### 节奏控制（Cadence Gating）

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `dialecticCadence` | 1（新配置2） | 辨证调用间隔（轮次数） |
| `contextCadence` | 1 | 基础上下文刷新间隔 |
| `injectionFrequency` | "every-turn" | 或"first-turn"（仅首轮注入） |

空结果退避：`_dialectic_empty_streak` 累计空返回 → cadence递增（上限base×8）。

### 对我方价值对比

| 维度 | Hermes做法 | 我方现状 | 借用策略 |
|------|-----------|---------|---------|
| **FTS5双表** | unicode61+trigram | 无全文搜索 | **直接可借**——SQLite FTS5 |
| **三层记忆架构** | L1 FTS5 / L2 Provider / L3 File | 无 | **架构参考** |
| **搜索3形状** | DISCOVERY/SCROLL/BROWSE | 无 | **参考**——分离查询场景 |
| **上下文压缩** | 结构化摘要+会话轮换 | 无 | **参考**——结构化摘要模板可借 |
| **Honcho辨证** | 多层递进推理+cadence控制 | 无 | **暂不引入**——过于复杂 |
| **三种调取模式** | context/tools/hybrid | 无 | **参考**——hybrid模式（自动+按需）最灵活 |
| **MemoryProvider抽象** | ABC可插拔 | 无 | **架构参考**——预留接口 |

---

## 八、自改进与技能体系 ⭐⭐（远期借鉴）

### 8.1 Fork自改进循环（`agent/background_review.py`, 597行）

#### 核心机制

每次对话轮次结束后，`AIAgent.run_conversation` 可能调用 `spawn_background_review_thread()`，fork出一个**守护线程**（daemon thread），对对话快照进行评估。线程创建一个新的 `AIAgent` 实例运行review prompt，执行写操作直通memory + skill存储，但**不触碰主的对话状态和提示缓存**。

| 设计 | 实现 | 对我方价值 |
|------|------|-----------|
| **运行时继承** | 继承父代理的provider/model/base_url/api_key/credential_pool | 避过OAuth/凭据池无法重构造的问题 |
| **工具白名单** | 仅允许memory+skills工具，其余在运行时deny | 安全的自省沙箱 |
| **缓存共享** | 继承 `_cached_system_prompt` + `session_start` + `session_id` | Anthropic前缀缓存命中→~26%成本降低 |
| **静默执行** | stdout/stderr→devnull + `suppress_status_output = True` | 用户不感知后台活动 |
| **自动拒绝危险命令** | `_bg_review_auto_deny` 回调→返回"deny" | 防止死锁（守护线程中input()无意义） |
| **去重摘要** | `summarize_background_review_actions()` 与 `prior_snapshot` 对比 | 避免重复展示陈旧操作 |

#### 三种Prompt

| Prompt | 触发条件 |
|--------|---------|
| `_MEMORY_REVIEW_PROMPT` (34-43) | review_memory=True, review_skills=False |
| `_SKILL_REVIEW_PROMPT` (45-233) + 组合 | review_skills=True, review_memory=False |
| `_COMBINED_REVIEW_PROMPT` | 两者均为True |

Memory review prompt关注用户个人信息/偏好；Skill review prompt含4个行动优先级（update loaded→update existing→add support file→create new umbrella）。

#### 与OmniAgent对比（调试笔记补充）

Hermes的review fork模型对OmniAgent的改进点：forking AIAgent比我们在 `tools/` 中内联review更清洁；tool whitelist模式可直接套用为当前Agent的沙箱模式。

#### 对我方价值对比

| 维度 | Hermes做法 | 我方现状 | 借用策略 |
|------|-----------|---------|---------|
| **自改进** | fork线程评估对话 | 无 | **远期考虑**——第2层编排层可扩展 |
| **工具白名单沙箱** | 仅允许安全工具 | 无 | **参考**——子任务限制工具权限 |
| **静默执行** | 守护线程，用户不感知 | 无 | **参考** |
| **去重摘要** | prior_snapshot对比 | 无 | **参考**——避免重复 |
| **review fork vs 内联** | 独立子实例 | 内联review | **参考**——fork更清洁，状态隔离更好 |

### 8.2 技能生成系统（Skills Generation）

**三个子系统**：

| 子系统 | 职责 | 行数 |
|--------|------|------|
| skill_manager_tool.py | 6种操作（create/edit/patch/delete/write_file/remove_file） | 1034 |
| skills_tool.py | 渐进式披露（skills_list→skill_view） | 1524 |
| skills_hub.py | 注册中心适配器（GitHub/WellKnown/Official） | 3748 |

**SKILL.md 格式规范**：
```yaml
---
name: skill-name         # ≤64字符
description: ...         # ≤1024字符
version: 1.0.0           # 可选
platforms: [macos]       # 可选
prerequisites:
  env_vars: [API_KEY]
  commands: [curl, jq]
---
```

**目录规范**：
```
my-skill/
├── SKILL.md          # 主指令（必须）
├── references/       # 引用文档
├── templates/        # 模板文件
├── scripts/          # 可重复运行的脚本
└── assets/           # agentskills.io补充文件标准
```

**Security Guard（`tools/skills_guard.py`）**：对hub安装的技能进行安全扫描（内容哈希、信任仓库列表、可疑模式检测）。Agent自创的技能默认跳过扫描。

#### 对我方价值对比

| 维度 | Hermes做法 | 我方现状 | 借用策略 |
|------|-----------|---------|---------|
| **技能目录规范** | references/templates/scripts/assets | 无 | **参考**——标准化技能存储 |
| **渐进式披露** | 列表→详情 | 无 | **参考**——减少token |
| **安全扫描** | 内容哈希+信任列表 | 无 | **参考**——社区技能安全 |
| **自改进集成** | 对话后自动提炼技能 | 无 | **远期考虑** |

### 8.3 agentskills.io 开放技能标准

**开放标准**，定义了AI agent技能的组织格式、元数据和发现机制。

**核心发现协议**：
```
GET {base_url}/.well-known/skills/index.json
```

**信任等级系统**：builtin → trusted → community

**对我方价值**：暂不引入，但有参考价值——后续支持社区技能市场时可参考。

---

## 九、可直接复用的代码级模式

### 9.1 指数退避 + jitter

**Hermes做法**（基于OpenAI SDK的重试，与我方OpenCode翻译一致）：

```python
def should_retry(attempts: int, err: Exception) -> tuple[bool, int]:
    # 仅重试429（限流）和500（服务端错误）
    if not is_retryable(err):            # 只认429/500
        return False, 0
    
    if attempts > max_retries (8):       # 最大8次
        return False, 0
    
    retry_ms = get_retry_after(err)      # 优先服务端Retry-After头
    if retry_ms is None:
        backoff_ms = 2000 * (2 ** (attempts - 1))  # 2s, 4s, 8s, 16s...
        jitter_ms = backoff_ms * 0.2              # +20%固定jitter
        retry_ms = int(backoff_ms + jitter_ms)
    
    return True, retry_ms
```

**我方**：OpenCode研究已翻译过Python版本，逻辑一致。

### 9.2 Session busy检查

**Hermes做法**（与OpenCode一致）：

```python
class Agent:
    def __init__(self):
        self._active_requests: dict[str, asyncio.Task] = {}
    
    def is_session_busy(self, session_id: str) -> bool:
        return session_id in self._active_requests
    
    def cancel_session(self, session_id: str):
        if session_id in self._active_requests:
            self._active_requests[session_id].cancel()
            del self._active_requests[session_id]
```

**我方**：已在第1层实现 `_active_tasks: dict[str, asyncio.Task]`，可直接复用。

### 9.3 Cost核算

**Hermes做法**（与OpenCode一致）：

```python
def calc_cost(model_config: ModelConfig, usage: TokenUsage) -> float:
    cost = (
        model_config.cost_per_1m_in_cached / 1_000_000 * usage.cache_creation_tokens +
        model_config.cost_per_1m_out_cached / 1_000_000 * usage.cache_read_tokens +
        model_config.cost_per_1m_in / 1_000_000 * usage.input_tokens +
        model_config.cost_per_1m_out / 1_000_000 * usage.output_tokens
    )
    return cost
```

**我方**：第3层usage tracking，与OpenCode一致。

### 9.4 MemoryProvider 抽象（预留）

如需引入记忆系统，直接使用以下抽象接口：

```python
class MemoryProvider(ABC):
    @abstractmethod
    def name(self) -> str: ...
    @abstractmethod
    def is_available(self) -> bool: ...
    @abstractmethod
    def initialize(self, session_id): ...
    @abstractmethod
    def get_tool_schemas(self) -> list[dict]: ...
    @abstractmethod
    def handle_tool_call(self, tool_name, args) -> str: ...
    
    # 可选
    def system_prompt_block(self): return ""
    def prefetch(self, query, session_id): return ""
    def sync_turn(self, user, assistant): pass
```

### 9.5 FTS5 双表全文搜索

```python
# 直接可借——SQLite FTS5双表策略
# 表1：英文 unicode61 tokenizer
CREATE VIRTUAL TABLE messages_fts USING fts5(content, tokenize='unicode61');
# 表2：CJK trigram tokenizer（≥3字符中文子串搜索）
CREATE VIRTUAL TABLE messages_fts_trigram USING fts5(content, tokenize='trigram');

# 查询策略
def search_messages(query: str):
    if has_cjk_chars(query):
        if min_token_len(query) >= 3:
            return fts_trigram_search(query)  # trigram精确路径
        else:
            return like_search(query)         # 1-2字符降级为LIKE
    else:
        return fts_search(query)              # 英文快速路径
```

---

## 十、不应借用的部分

| Hermes的做法 | 我方的理由 |
|-------------|-----------|
| **IterationBudget cost预算**（max_cost费用计算） | 我方不做cost价格核算，只做token计数用于上下文管理 |
| **多层平台适配**（Telegram/Discord/Slack等15+平台提示） | 我方单平台（Web SSE），不需要多平台提示 |
| **Honcho辨证记忆**（depth 1-3递进推理） | 过于复杂，我方目前无记忆需求，先做简单经验存储 |
| **MCP工具支持** | 已决定不需要MCP |
| **Agent持有3个不同provider实例** | 我方只维护一个统一model实例，不需要多provider |
| **Anthropic prompt caching特殊策略** | 我方不针对特殊provider做特殊处理 |
| **agent 60参数初始化** | 我方参数更精简，职责更分离 |
| **Full ReAct循环** | 我方使用Plan→Execute，减少LLM往返 |
| **每delta写一次DB** | 过于频繁，改为checkpoint/批量写 |
| **模块级register() AST扫描的实现细节** | 注册机制可借，但AST扫描不是必须——简单遍历import也能做到 |
| **agentskills.io社区技能市场** | 远期可能有用，但目前不需要 |

---

## 十一、总结与借鉴矩阵

### 11.1 核心借鉴模式

Hermes Agent对四层架构最值得借鉴的**核心模式**：

1. **ContextManager** — token计数+压缩触发+grace_call，管理LLM上下文窗口
2. **ToolGuardrails** — deny_list→signature→args_hash三层安全
3. **ConcurrentToolDispatch** — 智能并发控制模型（NEVER_PARALLEL/PARALLEL_SAFE/路径检测）
4. **三层系统提示** — stable/context/volatile分离，利于缓存
5. **FTS5双表搜索** — unicode61 + trigram解决中英文全文搜索
6. **sync→async队列中转** — queue.Queue做生产者-消费者，同步回调入队、async协程出队推SSE
7. **MemoryProvider抽象** — 可插拔记忆后端接口
8. **Fork自改进** — 守护线程静默评估对话（远期）

### 11.2 完整借鉴矩阵

| 子系统 | 可借性 | 核心可借内容 | 我方位置 | 优先级 |
|--------|-------|-------------|---------|--------|
| **ContextManager** | ⭐⭐⭐⭐ | token计数+压缩触发+grace_call（不做cost） | 第3层上下文管理 | **P0 立即** |
| **ToolGuardrails** | ⭐⭐⭐⭐ | 4检测+4级别，纯函数独立可测 | 第3层安全子系统 | **P0 立即** |
| **工具并发调度** | ⭐⭐⭐⭐ | NEVER_PARALLEL/PARALLEL_SAFE/路径检测 | 第3层工具调度 | **P1 近期** |
| **AST自动扫描注册** | ⭐⭐⭐⭐ | 消除手动ensure_tools_registered() | 第3层工具注册 | **P1 近期** |
| **check_fn TTL缓存** | ⭐⭐⭐⭐ | 30s缓存避免重复环境探测 | 第3层工具注册 | **P1 近期** |
| **sync→async队列中转** | ⭐⭐⭐⭐ | queue.Queue中转+segment_break | 第1层SSE推送 | **P1 近期** |
| **三层系统提示** | ⭐⭐⭐ | stable/context/volatile分离 | 第2层system message | **P2 中期** |
| **FTS5双表搜索** | ⭐⭐⭐⭐ | unicode61+trigram + 降级LIKE | 第2层经验检索 | **P2 中期** |
| **上下文压缩** | ⭐⭐⭐ | 结构化摘要+会话轮换 | 第3层context管理 | **P2 中期** |
| **流式上下文清洗器（StreamingContextScrubber）** | ⭐⭐⭐ | 跨chunk标签清洗状态机 | 第1层SSE过滤 | **P2 中期** |
| **MemoryProvider抽象** | ⭐⭐⭐ | ABC可插拔接口 | 第2层经验存储 | **P3 远期** |
| **Fork自改进** | ⭐⭐ | 守护线程静默评估 | 第2层编排 | **P3 远期** |
| **技能生成系统** | ⭐⭐ | SKILL.md规范 + 渐进式披露 | 经验管理 | **P3 远期** |
| **agentskills.io** | ⭐ | 开放技能标准 | 暂不引入 | **未来** |
| **Honcho辨证记忆** | ⭐ | 多层递进推理 | 暂不引入 | **未来** |
| **平台适配/多provider** | ❌ | 我方单平台，不处理provider差异 | 不采用 | ❌ |
| **每delta写DB** | ❌ | 过于频繁 | 不采用 | ❌ |

### 11.3 Hermes vs OpenCode 互补

| 维度 | 取OpenCode | 取Hermes |
|------|-----------|---------|
| 架构简洁度 | ✅ 轻量清晰 | ❌ 过于复杂 |
| Provider接口 | ✅ 强类型泛型接口 | ❌ 直接调SDK |
| 流式事件 | ✅ 10种ProviderEvent | ❌ 未抽象 |
| 工具安全 | ❌ 只有黑名单 | ✅ 三层guardrails |
| 上下文管理 | ❌ 无 | ✅ token计数+压缩触发 |
| 工具并发 | ❌ 串行 | ✅ 智能并行调度 |
| 记忆系统 | ❌ 无 | ✅ FTS5+Provider+File三层 |
| 自改进 | ❌ 无 | ✅ Fork守护线程模式 |
| 代码可翻译性 | ✅ Go→Python直接 | ❌ Python原生 |

**结论**：OpenCode解决了"怎么做简洁"的问题，Hermes解决了"怎么做完整"的问题。我们的设计方向是**取OpenCode的简洁架构，取Hermes的完整能力**。

---

## 十二、下一步实施建议

### 第一阶段（P0 立即）

| 任务 | 代码量 | 参考来源 |
|------|--------|---------|
| 实现 `ContextManager`（token计数+压缩触发+grace_call） | ~100行 | Hermes §3.2 |
| 实现 `ToolGuardrails`（精确失败重复检测） | ~150行 | Hermes §3.3 |
| 翻译 `shouldRetry` 指数退避 | ~50行 | Hermes/OpenCode §9.1 |

### 第二阶段（P1 近期）

| 任务 | 代码量 | 参考来源 |
|------|--------|---------|
| 工具并发调度（NEVER_PARALLEL/PARALLEL_SAFE） | ~200行 | Hermes §3.4 |
| AST自动扫描注册 + check_fn缓存 | ~150行 | Hermes §5.1 |
| `coerce_tool_args()` 类型转换 | ~80行 | Hermes §5.3 |
| queue.Queue中转 + segment_break | ~100行 | Hermes §6.1 |

### 第三阶段（P2 中期）

| 任务 | 代码量 | 参考来源 |
|------|--------|---------|
| 三层系统提示重构 | ~200行 | Hermes §4.1 |
| FTS5双表全文搜索 | ~120行 + SQL | Hermes §7.2 |
| 上下文压缩（结构化摘要） | ~300行 | Hermes §7.3 |
| 流式上下文清洗器（StreamingContextScrubber） | ~80行 | Hermes §6.3 |

---

**文档完成时间**: 2026-06-01 18:41:34
**编写人**: 小沈
