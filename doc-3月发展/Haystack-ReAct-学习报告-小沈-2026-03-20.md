# Haystack ReAct 学习报告

**文档版本**: v2.0
**创建时间**: 2026-03-20 05:50:00
**更新时间**: 2026-03-20 13:30:00
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
| **特点** | 组件化设计，Function Calling Agent |

### 1.2 重要说明

**Haystack Agent 不使用 ReAct 的文本解析模式。它使用 Function Calling（原生工具调用）模式。**

- ❌ 不需要 Thought:...Action:...Action Input:... 文本格式
- ❌ 不需要 Output Parser / 正则表达式
- ❌ 不需要 Stop Sequence
- ✅ LLM 返回结构化的 tool_call
- ✅ ToolInvoker 自动执行工具

---

## 2 Haystack Agent 核心组件

### 2.1 Agent（实际源码）

**来源**: `haystack.components.agents.Agent`

**实际源码（执行流程）**:

```python
@component
class Agent:
    def __init__(
        self,
        *,
        chat_generator: ChatGenerator,           # LLM 生成器
        tools: ToolsType | None = None,         # 工具列表
        system_prompt: str | None = None,        # 系统提示
        user_prompt: str | None = None,          # 用户提示模板
        exit_conditions: list[str] | None = None,  # 退出条件
        state_schema: dict[str, Any] | None = None, # 状态模式
        max_agent_steps: int = 100,              # 最大步数
        raise_on_tool_invocation_failure: bool = False,
        confirmation_strategies: dict | None = None,
    ) -> None:
        ...
    
    def run(self, messages: list[ChatMessage] | None = None, **kwargs) -> dict[str, Any]:
        """核心执行循环"""
        # 初始化执行上下文
        exe_context = self._initialize_fresh_execution(messages, ...)
        
        # 主循环
        while exe_context.counter < self.max_agent_steps:
            # 1. 调用 ChatGenerator
            result = Pipeline._run_component(
                component_name="chat_generator",
                component={"instance": self.chat_generator},
                inputs={"messages": exe_context.state.data["messages"], ...},
            )
            llm_messages = result["replies"]
            exe_context.state.set("messages", llm_messages)
            
            # 2. 检查是否有工具调用
            if not any(msg.tool_call for msg in llm_messages) or self._tool_invoker is None:
                # 没有工具调用 → 退出循环
                exe_context.counter += 1
                break
            
            # 3. 执行工具（通过 ToolInvoker）
            tool_invoker_result = Pipeline._run_component(
                component_name="tool_invoker",
                component={"instance": self._tool_invoker},
                inputs={"messages": llm_messages, "state": exe_context.state, ...},
            )
            tool_messages = tool_invoker_result["tool_messages"]
            exe_context.state = tool_invoker_result["state"]
            exe_context.state.set("messages", tool_messages)
            
            # 4. 检查退出条件
            if self.exit_conditions != ["text"] and self._check_exit_conditions(...):
                break
            
            exe_context.counter += 1
        
        return {**exe_context.state.data, "last_message": msgs[-1]}
```

### 2.2 Tool（数据类）

**来源**: `haystack.tools.Tool`

**实际源码**:

```python
@dataclass
class Tool:
    name: str  # 工具名称
    description: str  # 工具描述
    parameters: dict[str, Any]  # JSON Schema 参数定义
    function: Callable  # 工具函数
    outputs_to_string: dict[str, Any] | None = None  # 输出转字符串配置
    inputs_from_state: dict[str, str] | None = None  # 状态输入映射
    outputs_to_state: dict[str, dict[str, Any]] | None = None  # 状态输出映射

    @property
    def tool_spec(self) -> dict[str, Any]:
        """返回工具规格（给 LLM 用）"""
        return {"name": self.name, "description": self.description, "parameters": self.parameters}
    
    def invoke(self, **kwargs) -> Any:
        """执行工具"""
        try:
            result = self.function(**kwargs)
        except Exception as e:
            raise ToolInvocationError(f"Failed to invoke Tool `{self.name}`", tool_name=self.name) from e
        return result
```

**字段说明**:

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | `str` | 工具名称 |
| `description` | `str` | 工具描述 |
| `parameters` | `dict` | JSON Schema 参数定义 |
| `function` | `Callable` | 工具函数（必须同步） |
| `outputs_to_string` | `dict \| None` | 如何将工具输出转为字符串给 LLM |
| `inputs_from_state` | `dict \| None` | 从 State 映射输入参数 |
| `outputs_to_state` | `dict \| None` | 将工具输出映射到 State |

### 2.3 State（状态管理）

**来源**: `haystack.components.agents.state.State`

```python
my_state = State(
    schema={"gh_repo_name": {"type": str}, "user_name": {"type": str}},
    data={"gh_repo_name": "my_repo", "user_name": "my_user_name"}
)
```

### 2.4 ToolInvoker（工具执行器）

**来源**: `haystack.components.tools.ToolInvoker`

**功能**: 接收 LLM 的 tool_call，执行对应的工具，返回结果。

---

## 3 Haystack Agent 执行流程

### 3.1 实际流程（基于源码）

```
┌─────────────────────────────────────────────┐
│           Haystack Agent 执行流程            │
└─────────────────────────────────────────────┘

用户消息
    │
    ▼
┌─────────────────────────────────────────────┐
│  while (counter < max_agent_steps):         │
│    │                                         │
│    ├── 1. ChatGenerator.run()               │
│    │   ├── messages: 历史消息                │
│    │   ├── tools: 工具列表                  │
│    │   └── 返回: llm_messages               │
│    │                                         │
│    ├── 2. 检查 tool_call                    │
│    │   ├── 无 tool_call → break（退出）     │
│    │   └── 有 tool_call → 继续              │
│    │                                         │
│    ├── 3. 确认策略（可选）                  │
│    │   └── confirmation_strategies          │
│    │                                         │
│    ├── 4. ToolInvoker.run()                 │
│    │   ├── 执行工具                         │
│    │   ├── 更新 State                      │
│    │   └── 返回: tool_messages              │
│    │                                         │
│    ├── 5. 检查退出条件                      │
│    │   ├── exit_conditions 匹配 → break    │
│    │   └── 不匹配 → 继续循环               │
│    │                                         │
│    └── counter += 1                         │
│                                              │
└─────────────────────────────────────────────┘
    │
    ▼
返回: {messages, last_message, ...state}
```

### 3.2 与 LangChain ReAct 的区别

| 对比项 | LangChain ReAct | Haystack Agent |
|--------|----------------|----------------|
| **LLM 输出** | 文本（Thought:...Action:...） | 结构化 tool_call |
| **解析方式** | 正则表达式 | 直接使用 |
| **工具执行** | 手动 | ToolInvoker 自动 |
| **循环控制** | max_iterations | max_agent_steps |
| **退出条件** | AgentFinish | exit_conditions |
| **状态管理** | intermediate_steps | State（schema） |
| **确认策略** | 无 | confirmation_strategies |

---

## 4 Haystack Agent 初始化参数

### 4.1 完整参数说明

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `chat_generator` | `ChatGenerator` | 必填 | LLM 生成器 |
| `tools` | `ToolsType \| None` | None | 工具列表 |
| `system_prompt` | `str \| None` | None | 系统提示 |
| `user_prompt` | `str \| None` | None | 用户提示模板 |
| `exit_conditions` | `list[str] \| None` | ["text"] | 退出条件 |
| `state_schema` | `dict \| None` | None | 状态模式 |
| `max_agent_steps` | `int` | 100 | 最大步数 |
| `raise_on_tool_invocation_failure` | `bool` | False | 工具失败是否抛异常 |
| `confirmation_strategies` | `dict \| None` | None | 确认策略 |

### 4.2 exit_conditions

```python
# 默认退出条件
exit_conditions=["text"]  # 生成文本时退出

# 指定工具退出
exit_conditions=["text", "search_tool"]  # 文本或 search_tool 执行后退出
```

---

## 5 Haystack Agent 代码示例

### 5.1 基本用法

```python
from haystack.components.agents import Agent
from haystack.components.generators.chat import OpenAIChatGenerator
from haystack.dataclasses import ChatMessage
from haystack.tools import Tool

def search(query: str) -> str:
    """Search for information on the web."""
    return f"Search results for: {query}"

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
    )
]

agent = Agent(chat_generator=OpenAIChatGenerator(), tools=tools)

result = agent.run(
    messages=[ChatMessage.from_user("What is the weather in Paris?")]
)
print(result["last_message"].text)
```

### 5.2 带状态的工具

```python
from haystack.tools import Tool

def save_to_state(text: str) -> str:
    return text

tool = Tool(
    name="save",
    description="Save text to state",
    parameters={"type": "object", "properties": {"text": {"type": "string"}}},
    function=save_to_state,
    outputs_to_state={"saved_text": {"source": "result", "handler": str.upper}},
    inputs_from_state={"repository": "repo"},
)
```

---

## 6 Haystack Agent 的特点总结

### 6.1 优点

| 优点 | 说明 |
|------|------|
| **RAG 集成** | 与 Haystack Pipeline 无缝集成 |
| **组件化** | 可在 Pipeline 中复用 |
| **确认策略** | 支持工具调用确认（Human-in-the-loop） |
| **State 管理** | 内置 State 管理（schema-based） |
| **Tool 状态映射** | inputs_from_state / outputs_to_state |

### 6.2 缺点

| 缺点 | 说明 |
|------|------|
| **不支持异步工具** | Tool.function 必须是同步函数 |
| **ReAct 文本解析** | 不支持（只有 Function Calling） |

### 6.3 对 omniAgent 的参考价值

| 参考点 | 说明 |
|--------|------|
| **Tool 定义格式** | JSON Schema 参数定义 |
| **exit_conditions** | 退出条件控制 |
| **State 管理** | 共享状态机制 |
| **Pipeline 集成** | 多 Agent 组合 |
| **confirmation_strategies** | 工具调用确认策略 |
| **Tool.outputs_to_string** | 输出转字符串配置 |

---

## 7 关键资源链接

| 资源 | 说明 |
|------|------|
| [Haystack GitHub](https://github.com/deepset-ai/haystack) | 官方仓库 |
| [Agent 源码](https://github.com/deepset-ai/haystack/blob/main/haystack/components/agents/agent.py) | Agent 核心实现 |
| [Tool 源码](https://github.com/deepset-ai/haystack/blob/main/haystack/tools/tool.py) | Tool 定义 |
| [Haystack 文档](https://docs.haystack.deepset.ai/) | 官方文档 |

---

## 8 版本记录

| 版本 | 时间 | 更新内容 | 作者 |
|------|------|---------|------|
| v1.0 | 2026-03-20 05:50:00 | 初始版本 | 小沈 |
| v2.0 | 2026-03-20 13:30:00 | **深度修正**：基于实际源码修正 Agent 执行流程（Function Calling 而非 ReAct 文本解析）；修正 Tool 为 dataclass 并新增 outputs_to_string/inputs_from_state/outputs_to_state 字段；新增 ToolInvoker 组件说明；新增 confirmation_strategies 确认策略；新增 Agent.run() 实际源码流程 | 小沈 |

---

**文档结束**
