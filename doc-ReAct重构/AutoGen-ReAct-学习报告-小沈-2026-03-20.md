# AutoGen ReAct 学习报告

**文档版本**: v2.0
**创建时间**: 2026-03-20 05:45:00
**更新时间**: 2026-03-20 13:15:00
**编写人**: 小沈
**研究资料数量**: 20+ 篇
**存放位置**: D:\OmniAgentAs-desk\doc-ReAct重构\

---

## 1 AutoGen 概述

### 1.1 框架简介

| 属性 | 说明 |
|------|------|
| **名称** | Microsoft AutoGen |
| **语言** | Python / C# / TypeScript |
| **Stars** | 55K+ (GitHub) |
| **定位** | 多 Agent 对话框架 |
| **特点** | 支持人机协作，代码执行，Function Calling 原生支持 |

### 1.2 版本差异（重要）

| 特性 | AutoGen 0.2 (旧版) | AutoGen 0.4 (新版) |
|------|------------------|------------------|
| **Agent 基类** | `ConversableAgent` | `BaseChatAgent` |
| **工具注册** | `register_function()` | `FunctionTool` 直接传入 |
| **ReAct 模式** | Prompt 驱动（文本解析） | Function Calling 驱动（原生工具调用） |
| **循环控制** | `max_consecutive_auto_reply` | `max_tool_iterations` |
| **代码执行** | `UserProxyAgent` | `CodeExecutorAgent` |

**本报告主要基于 AutoGen 0.4（最新版）分析。**

---

## 2 核心概念（AutoGen 0.4）

### 2.1 AssistantAgent（核心 Agent）

**来源**: `autogen_agentchat.agents.AssistantAgent`

**定义**: 提供工具使用的助手 Agent，**不是**简单的 LLM 调用器，而是完整的 Function Calling Agent。

```python
from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.openai import OpenAIChatCompletionClient

agent = AssistantAgent(
    name="assistant",
    model_client=OpenAIChatCompletionClient(model="gpt-4o"),
    tools=[get_current_time],  # 直接传入工具函数
    system_message="You are a helpful assistant.",
    max_tool_iterations=5,  # 最多执行 5 轮工具调用
    reflect_on_tool_use=True,  # 工具调用后反思
)
```

**关键参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| `name` | `str` | Agent 名称 |
| `model_client` | `ChatCompletionClient` | LLM 客户端 |
| `tools` | `List[BaseTool \| Callable]` | 可用工具列表 |
| `handoffs` | `List[HandoffBase \| str]` | 转交配置 |
| `system_message` | `str \| None` | 系统消息 |
| `max_tool_iterations` | `int` | 最大工具调用轮数（默认 1） |
| `reflect_on_tool_use` | `bool` | 是否在工具调用后生成反思回答 |
| `model_context` | `ChatCompletionContext` | 模型上下文管理 |
| `output_content_type` | `type[BaseModel] \| None` | 结构化输出类型 |

### 2.2 FunctionCall

**来源**: `autogen_core.FunctionCall`

**定义**: 代表 LLM 请求调用工具的结构化数据。

```python
class FunctionCall:
    id: str  # 唯一标识
    arguments: str  # 工具参数（JSON 字符串）
    name: str  # 工具名称
```

**字段说明**:

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | `str` | 调用的唯一标识（用于匹配结果） |
| `arguments` | `str` | 工具参数（JSON 字符串格式） |
| `name` | `str` | 要调用的工具名称 |

### 2.3 FunctionExecutionResult

**来源**: `autogen_core.models.FunctionExecutionResult`

**定义**: 工具执行的结果。

```python
class FunctionExecutionResult:
    content: str  # 执行结果
    call_id: str  # 对应的 FunctionCall id
    is_error: bool  # 是否出错
```

### 2.4 CreateResult

**来源**: `autogen_core.models.CreateResult`

**定义**: LLM 调用的返回结果。

```python
class CreateResult:
    content: str | List[FunctionCall]  # 文本回答或工具调用列表
    usage: RequestUsage  # token 使用量
    finish_reason: str  # 结束原因
    thought: str | None  # 思考过程（推理模型）
```

### 2.5 Workbench（工具执行环境）

**来源**: `autogen_core.tools.Workbench`

**定义**: 工具的管理和执行环境。

```python
from autogen_core.tools import StaticStreamWorkbench

# 内部实现（简化）
workbench = StaticStreamWorkbench(tools=[tool1, tool2])
# list_tools() - 列出可用工具
# call_tool(name, args) - 执行工具
```

---

## 3 AutoGen Tool Calling 实现（非 ReAct 文本解析）

### 3.1 重要说明

**AutoGen 0.4 不使用 ReAct 的文本解析模式（Thought:...Action:...Action Input:...）。**

AutoGen 0.4 使用 **Function Calling（原生工具调用）** 模式：
- LLM 返回结构化的 `FunctionCall` 对象
- 不需要正则表达式解析文本
- 不需要 Stop Sequence
- 不需要 Output Parser

### 3.2 执行流程（实际源码）

```
AssistantAgent.on_messages_stream()
    │
    ├── STEP 1: 添加消息到 model_context
    │
    ├── STEP 2: 更新 memory（如果有）
    │
    ├── STEP 3: 生成 message_id
    │
    ├── STEP 4: 调用 LLM (_call_llm)
    │   ├── messages = model_context.get_messages()
    │   ├── tools = workbench.list_tools() + handoff_tools
    │   ├── result = model_client.create(messages, tools)
    │   └── yield CreateResult 或 ModelClientStreamingChunkEvent
    │
    ├── STEP 5: 处理模型结果 (_process_model_result)
    │   │
    │   ├── 如果 content 是 str（文本回答）:
    │   │   └── yield TextMessage
    │   │
    │   ├── 如果 content 是 List[FunctionCall]（工具调用）:
    │   │   ├── yield ToolCallRequestEvent (tool_calls)
    │   │   ├── 执行工具: workbench.call_tool(name, args)
    │   │   ├── yield ToolCallExecutionEvent (results)
    │   │   ├── 将结果添加到 model_context
    │   │   ├── 检查 max_tool_iterations
    │   │   └── 继续循环（返回 STEP 4）
    │   │
    │   └── 如果有 handoff:
    │       └── yield HandoffMessage
    │
    └── STEP 6: 返回 Response
```

### 3.3 关键代码片段

```python
# _call_llm（简化）
async def _call_llm(model_client, model_context, workbench, handoff_tools, ...):
    all_messages = await model_context.get_messages()
    tools = [tool for wb in workbench for tool in await wb.list_tools()] + handoff_tools
    
    result = await model_client.create(
        messages=all_messages,
        tools=tools,
        cancellation_token=cancellation_token,
    )
    yield result

# _process_model_result（简化）
async def _process_model_result(model_result, inner_messages, ...):
    # 检查是否有工具调用
    if isinstance(model_result.content, list) and len(model_result.content) > 0:
        # yield 工具调用事件
        yield ToolCallRequestEvent(content=model_result.content, source=agent_name)
        
        # 执行工具
        for call in model_result.content:
            result = await workbench.call_tool(call.name, call.arguments)
            results.append(FunctionExecutionResult(
                content=result.to_text(),
                call_id=call.id,
                is_error=result.is_error,
            ))
        
        # yield 工具执行结果事件
        yield ToolCallExecutionEvent(content=results, source=agent_name)
        
        # 将结果添加到上下文
        await model_context.add_message(FunctionExecutionResultMessage(content=results))
        
        # 检查是否继续循环
        if tool_iteration < max_tool_iterations:
            # 继续调用 LLM（递归）
            ...
    else:
        # 文本回答
        yield TextMessage(content=str(model_result.content), source=agent_name)
```

### 3.4 消息类型

| 消息类型 | 说明 |
|---------|------|
| `TextMessage` | 文本消息 |
| `ToolCallRequestEvent` | 工具调用请求（包含 FunctionCall 列表） |
| `ToolCallExecutionEvent` | 工具执行结果（包含 FunctionExecutionResult 列表） |
| `ToolCallSummaryMessage` | 工具调用摘要 |
| `HandoffMessage` | 转交给其他 Agent |
| `StructuredMessage` | 结构化输出消息 |
| `ThoughtEvent` | 思考过程（推理模型） |
| `MemoryQueryEvent` | 记忆查询事件 |

---

## 4 AutoGen 0.2 的 ReAct 模式（旧版，仅供参考）

### 4.1 ReAct Prompt 格式

AutoGen 0.2 支持 ReAct 的文本解析模式：

```
Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take
Action Input: the input to the action
Observation: the result of the action
...
Thought: I now know the final answer
Final Answer: the final answer to the original input question
```

### 4.2 0.2 版本示例代码

```python
from autogen import AssistantAgent, UserProxyAgent, register_function

# 创建 Agent
user_proxy = UserProxyAgent(name="User", ...)
assistant = AssistantAgent(name="Assistant", ...)

# 注册工具
register_function(search_tool, caller=assistant, executor=user_proxy, ...)

# 执行
user_proxy.initiate_chat(assistant, message=react_prompt_message, ...)
```

### 4.3 0.2 版本执行流程

```
UserProxyAgent ── ReAct Prompt ──► AssistantAgent
                                    │
                                    │── LLM 生成 Thought/Action/Action Input
                                    │
UserProxyAgent ◄── Action Request ──│
     │
     │── 执行工具
     │
UserProxyAgent ── Observation ──► AssistantAgent
                                    │
                                    │── 继续循环
                                    │
                                    │── Final Answer
```

---

## 5 AutoGen 的独特功能

### 5.1 max_tool_iterations

控制工具调用的循环次数：

```python
agent = AssistantAgent(
    name="assistant",
    model_client=model_client,
    tools=[increment_counter, get_counter],
    max_tool_iterations=5,  # 最多 5 轮工具调用
    reflect_on_tool_use=True,
)
```

**行为**：
- `max_tool_iterations=1`（默认）：执行一轮工具调用后返回结果
- `max_tool_iterations=5`：模型可以连续请求 5 轮工具调用
- 一旦模型返回文本（而非工具调用），循环立即停止

### 5.2 reflect_on_tool_use

控制是否在工具调用后生成反思回答：

```python
# reflect_on_tool_use=False（默认）
# 工具调用结果直接返回
# Response: ToolCallSummaryMessage

# reflect_on_tool_use=True
# 工具调用后再调用一次 LLM 生成回答
# Response: TextMessage
```

### 5.3 Handoff（Agent 转交）

```python
agent = AssistantAgent(
    name="assistant",
    model_client=model_client,
    handoffs=["agent_b", "agent_c"],  # 可以转交给其他 Agent
)
```

### 5.4 结构化输出

```python
from pydantic import BaseModel

class AgentResponse(BaseModel):
    thoughts: str
    response: str

agent = AssistantAgent(
    name="assistant",
    model_client=model_client,
    output_content_type=AgentResponse,  # 输出结构化数据
)
```

### 5.5 Memory（记忆模块）

```python
from autogen_core.memory import ListMemory, MemoryContent

memory = ListMemory()
await memory.add(MemoryContent(content="User likes pizza.", mime_type="text/plain"))

agent = AssistantAgent(
    name="assistant",
    model_client=model_client,
    memory=[memory],
)
```

---

## 6 AutoGen vs LangChain ReAct 对比

| 对比项 | LangChain ReAct | AutoGen 0.4 |
|--------|----------------|-------------|
| **工具调用方式** | 文本解析（正则） | Function Calling（原生） |
| **Output Parser** | 必须（正则表达式） | 不需要（结构化） |
| **Stop Sequence** | 必须（防止幻觉） | 不需要 |
| **循环控制** | `max_iterations` | `max_tool_iterations` |
| **错误处理** | `handle_parsing_errors` | `is_error` 字段 |
| **Agent 通信** | 单 Agent | 多 Agent 通信 |
| **代码执行** | 无 | 内置 |
| **人机协作** | 无 | 原生支持 |

---

## 7 对 omniAgent 的参考价值

| 参考点 | 说明 |
|--------|------|
| **max_tool_iterations** | 控制工具调用循环次数 |
| **reflect_on_tool_use** | 工具调用后是否生成反思回答 |
| **FunctionCall 结构** | `id`, `arguments`, `name` |
| **FunctionExecutionResult** | `content`, `call_id`, `is_error` |
| **Workbench 模式** | 工具管理与执行分离 |
| **Message Types** | 丰富的消息类型体系 |
| **on_messages_stream** | 流式处理消息 |
| **Memory 模块** | Agent 记忆能力 |

---

## 8 关键资源链接

| 资源 | 说明 |
|------|------|
| [AutoGen GitHub](https://github.com/microsoft/autogen) | 官方仓库 |
| [AutoGen 0.4 文档](https://microsoft.github.io/autogen/stable/) | 最新文档 |
| [AssistantAgent 源码](https://github.com/microsoft/autogen/blob/main/python/packages/autogen-agentchat/src/autogen_agentchat/agents/_assistant_agent.py) | 核心 Agent |
| [FunctionTool 源码](https://github.com/microsoft/autogen/blob/main/python/packages/autogen-core/src/autogen_core/tools/_function_tool.py) | 工具实现 |

---

## 9 版本记录

| 版本 | 时间 | 更新内容 | 作者 |
|------|------|---------|------|
| v1.0 | 2026-03-20 05:45:00 | 初始版本 | 小沈 |
| v2.0 | 2026-03-20 13:15:00 | **深度修正**：区分 AutoGen 0.2（旧版 ReAct）和 0.4（Function Calling）；修正 AssistantAgent 为完整 Function Calling Agent；修正 FunctionCall 字段顺序（id, arguments, name）；新增 max_tool_iterations、reflect_on_tool_use、Workbench、消息类型体系；新增 on_messages_stream 执行流程；新增 AutoGen vs LangChain 对比 | 小沈 |

---

**文档结束**
