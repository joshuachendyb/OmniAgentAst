# Haystack ReAct 学习报告

**文档版本**: v1.0
**创建时间**: 2026-03-20 05:50:00
**编写人**: 小沈
**研究资料数量**: 15+ 篇
**存放位置**: D:\OmniAgentAs-desk\doc-ReAct重构\

---

## 1 Haystack 概述

### 1.1 框架简介

| 属性 | 说明 |
|------|------|
| **名称** | Haystack |
| **语言** | Python |
| **Stars** | 15K+ (GitHub) |
| **定位** | 开源 RAG 框架 |
| **特点** | 组件化设计，Agent 支持 |

### 1.2 ReAct 支持

Haystack 2.0+ 提供了完整的 Agent 实现，支持 ReAct 模式。

---

## 2 Haystack Agent 核心组件

### 2.1 Agent

**来源**: `haystack.components.agents.Agent`

**定义**: 工具调用 Agent

```python
from haystack.components.agents import Agent
from haystack.components.generators.chat import OpenAIChatGenerator
from haystack.tools import Tool

# 定义工具
def search(query: str) -> str:
    """Search for information on the web."""
    return f"Search results for: {query}"

def calculator(operation: str, a: float, b: float) -> float:
    """Perform mathematical calculations."""
    if operation == "multiply":
        return a * b
    elif operation == "percentage":
        return (a / 100) * b
    return 0

# 创建工具
tools = [
    Tool(
        name="search",
        description="Searches for information on the web",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query"}
            },
            "required": ["query"]
        },
        function=search
    ),
    Tool(
        name="calculator",
        description="Performs mathematical calculations",
        parameters={
            "type": "object",
            "properties": {
                "operation": {"type": "string", "description": "Operation: multiply, percentage"},
                "a": {"type": "number", "description": "First number"},
                "b": {"type": "number", "description": "Second number"}
            },
            "required": ["operation", "a", "b"]
        },
        function=calculator
    )
]

# 创建 Agent
agent = Agent(
    chat_generator=OpenAIChatGenerator(),
    tools=tools
)

# 执行
result = agent.run(
    messages=[ChatMessage.from_user("Calculate the appropriate tip for an €85 meal in France")]
)
```

### 2.2 Tool

**来源**: `haystack.tools.Tool`

**定义**: 工具定义

```python
from haystack.tools import Tool

tool = Tool(
    name="search",                    # 工具名称
    description="Search for info",     # 工具描述
    parameters={...},                  # JSON Schema 参数定义
    function=search_func             # 函数对象
)
```

### 2.3 State

**来源**: `haystack.components.agents.state.State`

**定义**: Agent 执行时的共享状态

```python
from haystack.components.agents.state import State

my_state = State(
    schema={"gh_repo_name": {"type": str}, "user_name": {"type": str}},
    data={"gh_repo_name": "my_repo", "user_name": "my_user_name"}
)

# 访问状态
repo_name = my_state.get("gh_repo_name")

# 设置状态
my_state.set("new_key", "new_value")
```

---

## 3 Haystack Agent 初始化参数

### 3.1 完整参数说明

```python
Agent(
    chat_generator: ChatGenerator,           # LLM 生成器
    tools: ToolsType | None = None,         # 可用工具
    system_prompt: str | None = None,        # 系统提示
    user_prompt: str | None = None,          # 用户提示模板
    required_variables: list[str] | None = None,  # 必需变量
    exit_conditions: list[str] | None = None,     # 退出条件
    state_schema: dict[str, Any] | None = None,  # 状态模式
    max_agent_steps: int = 100,              # 最大步数
    streaming_callback: StreamingCallbackT | None = None,
    raise_on_tool_invocation_failure: bool = False,
    tool_invoker_kwargs: dict[str, Any] | None = None,
    confirmation_strategies: dict | None = None,
)
```

### 3.2 exit_conditions

**说明**: 控制 Agent 何时停止

```python
# 默认退出条件
exit_conditions=["text"]  # 生成文本时退出

# 自定义退出条件
exit_conditions=["text", "search", "calculator"]
# 当生成文本或执行 search/calculator 工具后退出
```

---

## 4 Haystack Agent 执行流程

### 4.1 流程图

```
┌─────────────────────────────────────────────┐
│           Haystack Agent 执行流程            │
└─────────────────────────────────────────────┘

用户消息
    │
    ▼
┌─────────────────────────────────────────────┐
│           Agent.run()                       │
│                                              │
│  while (未达到退出条件):                      │
│    1. 调用 ChatGenerator                     │
│    2. 解析 LLM 响应                          │
│    3. 如果是工具调用 → 执行工具               │
│    4. 如果是文本 → 检查退出条件                │
│    5. 继续循环                               │
│                                              │
│  return result                              │
└─────────────────────────────────────────────┘
```

### 4.2 执行示例

```python
# 基本执行
result = agent.run(
    messages=[ChatMessage.from_user("What is 2 + 2?")]
)

# 使用 Prompt 模板
result = agent.run(
    language="French",
    document="The weather is lovely today."
)

# 访问结果
print(result["last_message"].text)
print(result["messages"])
```

---

## 5 Haystack Agent 代码示例

### 5.1 带确认的工具调用

```python
from haystack.components.agents import Agent
from haystack.components.generators.chat import OpenAIChatGenerator
from haystack.dataclasses import ChatMessage
from haystack.tools import tool
from haystack.confirmation_strategy import AutoDisableConfirmation

@tool
def delete_file(path: str) -> str:
    """Delete a file."""
    return f"Deleted: {path}"

agent = Agent(
    chat_generator=OpenAIChatGenerator(),
    tools=[delete_file],
    confirmation_strategies={
        "delete_file": AutoDisableConfirmation()
    }
)

result = agent.run(
    messages=[ChatMessage.from_user("Delete the file at /tmp/test.txt")]
)
```

### 5.2 多 Agent 系统

```python
from haystack import Pipeline
from haystack.components.agents import Agent

# 创建 Researcher Agent
researcher = Agent(
    chat_generator=OpenAIChatGenerator(),
    tools=[search_tool],
    system_prompt="You are a researcher..."
)

# 创建 Writer Agent
writer = Agent(
    chat_generator=OpenAIChatGenerator(),
    tools=[],
    system_prompt="You are a writer..."
)

# 在 Pipeline 中组合
pipeline = Pipeline()
pipeline.add_component("researcher", researcher)
pipeline.add_component("writer", writer)

# 连接组件
pipeline.connect("researcher", "writer")

result = pipeline.run({
    "researcher": {"messages": [ChatMessage.from_user("Research AI")]},
})
```

---

## 6 Haystack Agent 的特点总结

### 6.1 优点

| 优点 | 说明 |
|------|------|
| **RAG 集成** | 与 Haystack Pipeline 无缝集成 |
| **组件化** | 可在 Pipeline 中复用 |
| **确认策略** | 支持工具调用确认 |
| **状态管理** | 内置 State 管理 |

### 6.2 缺点

| 缺点 | 说明 |
|------|------|
| **ReAct 不透明** | 内部实现，不直接暴露 |
| **文档分散** | Agent 文档不够集中 |

### 6.3 对 omniAgent 的参考价值

| 参考点 | 说明 |
|------|------|
| **Tool 定义格式** | JSON Schema 参数定义 |
| **exit_conditions** | 退出条件控制 |
| **State 管理** | 共享状态机制 |
| **Pipeline 集成** | 多 Agent 组合 |

---

## 7 Haystack vs 其他框架对比

### 7.1 对比表

| 方面 | Haystack | LangChain | LlamaIndex |
|------|----------|-----------|------------|
| **RAG 深度** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Agent 支持** | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| **组件化** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |
| **多 Agent** | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ |

### 7.2 选择建议

- **主要做 RAG**: 使用 Haystack
- **主要做 Agent**: 使用 LangChain
- **平衡方案**: 使用 LlamaIndex

---

## 8 关键资源链接

| 资源 | 说明 |
|------|------|
| [Haystack GitHub](https://github.com/deepset-ai/haystack) | 官方仓库 |
| [Haystack 文档](https://docs.haystack.deepset.ai/) | 官方文档 |
| [Agent API](https://docs.haystack.deepset.ai/reference/agents-api) | Agent API 文档 |
| [多 Agent 教程](https://haystack.deepset.ai/tutorials/45_creating_a_multi_agent_system) | 多 Agent 教程 |

---

## 9 版本记录

| 版本 | 时间 | 更新内容 | 作者 |
|------|------|---------|------|
| v1.0 | 2026-03-20 05:50:00 | 初始版本，包含完整 Haystack ReAct 学习报告 | 小沈 |

---

**文档结束**
