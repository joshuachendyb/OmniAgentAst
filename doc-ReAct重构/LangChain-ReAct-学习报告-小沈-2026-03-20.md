# LangChain ReAct 学习报告

**文档版本**: v1.0
**创建时间**: 2026-03-20 05:28:39
**编写人**: 小沈
**研究资料数量**: 45+ 篇
**存放位置**: D:\OmniAgentAs-desk\doc-ReAct重构\

---

## 1 LangChain 概述

### 1.1 框架简介

| 属性 | 说明 |
|------|------|
| **名称** | LangChain |
| **语言** | Python / JavaScript |
| **Stars** | 100K+ (GitHub) |
| **定位** | 最流行的 LLM 应用开发框架 |
| **特点** | 抽象层级多，灵活性高 |

### 1.2 ReAct 支持

LangChain 是最早支持 ReAct 模式的框架之一，提供了完整的 ReAct Agent 实现。

---

## 2 核心概念与字段

### 2.1 AgentAction

**来源**: `langchain_core.agents.AgentAction`

**定义**: 代表 LLM 调用工具的动作

```python
class AgentAction(NamedTuple):
    tool: str  # 工具名称
    tool_input: Union[str, dict]  # 工具输入参数
    log: str  # LLM 的原始思考日志
```

**字段说明**:

| 字段 | 类型 | 说明 |
|------|------|------|
| `tool` | `str` | 要调用的工具名称 |
| `tool_input` | `str \| dict` | 工具的输入参数 |
| `log` | `str` | LLM 的思考过程（包含 Thought） |

### 2.2 AgentFinish

**来源**: `langchain_core.agents.AgentFinish`

**定义**: 代表 Agent 完成，返回最终结果

```python
class AgentFinish(NamedTuple):
    return_values: dict  # 返回值字典
    log: str  # 最终日志
```

**字段说明**:

| 字段 | 类型 | 说明 |
|------|------|------|
| `return_values` | `dict` | 最终返回值，通常包含 `output` 字段 |
| `log` | `str` | 最终回答的日志 |

### 2.3 intermediate_steps

**定义**: 中间步骤列表，存储 AgentAction 和其结果的配对

```python
intermediate_steps: List[Tuple[AgentAction, str]]
```

**结构**:
```python
[
    (AgentAction(tool="search", tool_input="...", log="Thought: ..."), "搜索结果..."),
    (AgentAction(tool="calculator", tool_input="...", log="Thought: ..."), "计算结果..."),
]
```

---

## 3 ReAct Agent 实现

### 3.1 create_react_agent

**来源**: `langchain.agents.ReActAgent.create_react_agent`

**函数签名**:

```python
def create_react_agent(
    llm: BaseLanguageModel,
    tools: Sequence[BaseTool],
    prompt: BasePromptTemplate,
    output_parser: AgentOutputParser | None = None,
    tools_renderer: ToolsRenderer = render_text_description,
    *,
    stop_sequence: bool | Sequence[str] = True,
) -> Runnable
```

**参数说明**:

| 参数 | 类型 | 说明 |
|------|------|------|
| `llm` | `BaseLanguageModel` | LLM 实例 |
| `tools` | `Sequence[BaseTool]` | 可用工具列表 |
| `prompt` | `BasePromptTemplate` | Prompt 模板 |
| `output_parser` | `AgentOutputParser \| None` | 输出解析器 |
| `tools_renderer` | `ToolsRenderer` | 工具渲染器 |
| `stop_sequence` | `bool \| Sequence[str]` | 停止序列 |

### 3.2 ReAct Prompt 模板

**来源**: `langchain.agents.ReAct.prompt`

**标准 Prompt**:

```
Answer the following questions as best you can. You have access to tools provided.

Use the following format:

Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question

Begin!

Question: {input}
```

---

## 4 ReAct Output Parser

### 4.1 ReActSingleInputOutputParser

**来源**: `langchain.agents.output_parsers.ReActSingleInputOutputParser`

**源码实现**:

```python
import re
from typing import Union
from langchain_core.agents import AgentAction, AgentFinish
from langchain_core.exceptions import OutputParserException
from langchain.agents.agent import AgentOutputParser
from langchain.agents.mrkl.prompt import FORMAT_INSTRUCTIONS

FINAL_ANSWER_ACTION = "Final Answer:"

class ReActSingleInputOutputParser(AgentOutputParser):
    """解析 ReAct 风格的 LLM 输出。"""

    def parse(self, text: str) -> Union[AgentAction, AgentFinish]:
        # 优先匹配 Final Answer
        if FINAL_ANSWER_ACTION in text:
            return AgentFinish(
                return_values={"output": text.split(FINAL_ANSWER_ACTION)[-1].strip()},
                log=text,
            )

        # 匹配 Thought + Action + Action Input
        regex = r"Thought\s*(.*?)\nAction\s*(.*?)\nAction Input\s*(.*?)(?=\nObservation:|$)"
        match = re.search(regex, text, re.DOTALL | re.IGNORECASE)

        if not match:
            raise OutputParserException(f"Could not parse LLM output: {text}")

        thought = match.group(1).strip()
        action = match.group(2).strip()
        action_input = match.group(3).strip()

        return AgentAction(
            tool=action,
            tool_input=action_input,
            log=text
        )
```

### 4.2 解析模式详解

**正则表达式**: `r"Thought\s*(.*?)\nAction\s*(.*?)\nAction Input\s*(.*?)(?=\nObservation:|$)"`

**匹配顺序**:
1. `Thought`: 捕获思考内容
2. `Action`: 捕获工具名称
3. `Action Input`: 捕获工具参数

**Example LLM Output**:
```
Thought: I need to search for the weather in San Francisco.
Action: search
Action Input: {"query": "weather in San Francisco"}
```

---

## 5 format_log_to_str

### 5.1 功能说明

将 intermediate_steps 格式化为可读的 prompt 片段。

### 5.2 源码实现

```python
def format_log_to_str(
    intermediate_steps: List[Tuple[AgentAction, str]],
) -> str:
    """格式化中间步骤为字符串。"""
    lines = []
    for action, observation in intermediate_steps:
        lines.append(f"Thought: {action.log}")
        lines.append(f"Action: {action.tool}")
        lines.append(f"Action Input: {action.tool_input}")
        lines.append(f"Observation: {observation}")
    return "\n".join(lines)
```

### 5.3 输出示例

```
Thought: I need to search for the latest news.
Action: web_search
Action Input: {"query": "latest AI news"}
Observation: According to recent reports, AI has...
Thought: I now have some information.
Action: calculator
Action Input: {"expression": "2 + 2"}
Observation: 4
```

---

## 6 Stop Sequence 机制

### 6.1 作用

**防止 LLM 幻觉 Observation**。告诉 LLM 在输出到指定位置后停止，由运行时提供真实的 Observation。

### 6.2 配置方式

```python
# 方式1: 使用布尔值（默认）
agent = create_react_agent(llm, tools, prompt, stop_sequence=True)
# 会在 Action Input 后自动添加 \nObservation: 停止

# 方式2: 自定义停止序列
agent = create_react_agent(
    llm, 
    tools, 
    prompt, 
    stop_sequence=["\nObservation:", "\nThought:"]
)
```

### 6.3 执行流程

```
1. LLM 生成: "Thought: ... Action: search Action Input: {...}"
2. 遇到 stop_sequence，停止生成
3. 运行时执行工具
4. 运行时注入: "\nObservation: 真实结果"
5. 继续下一轮 LLM 调用
```

---

## 7 trim_intermediate_steps

### 7.1 功能说明

防止 context overflow，裁剪过长的中间步骤。

### 7.2 源码实现

```python
def trim_intermediate_steps(
    intermediate_steps: List[Tuple[AgentAction, str]],
    max_steps: int = 15,
) -> List[Tuple[AgentAction, str]]:
    """裁剪中间步骤，保留最近的 N 步。"""
    if len(intermediate_steps) <= max_steps:
        return intermediate_steps

    # 保留最后的 max_steps 个步骤
    return intermediate_steps[-max_steps:]
```

### 7.2 使用场景

当对话历史过长时，使用此函数裁剪早期的中间步骤。

---

## 8 AgentExecutor

### 8.1 功能说明

执行 Agent 的主循环

### 8.2 源码实现

```python
class AgentExecutor:
    """ReAct Agent 的执行器。"""

    def __init__(self, agent: Runnable, tools: Sequence[BaseTool]):
        self.agent = agent
        self.tools = {tool.name: tool for tool in tools}

    def _get_next_action(self, result: AgentAction) -> AgentAction:
        """从 LLM 输出获取 Action。"""
        if isinstance(result, AgentFinish):
            raise StopIteration(result.return_values)
        return result

    def _execute_tool(self, action: AgentAction) -> str:
        """执行工具并返回结果。"""
        tool = self.tools.get(action.tool)
        if not tool:
            return f"Error: Tool {action.tool} not found"

        try:
            # 工具输入可能是 JSON 字符串或字典
            if isinstance(action.tool_input, str):
                import json
                tool_input = json.loads(action.tool_input)
            else:
                tool_input = action.tool_input

            result = tool.run(tool_input)
            return str(result)
        except Exception as e:
            return f"Error: {str(e)}"

    def run(self, input_str: str, max_iterations: int = 50) -> dict:
        """执行 Agent。"""
        inputs = {"input": input_str, "intermediate_steps": []}
        intermediate_steps = []

        for _ in range(max_iterations):
            result = self.agent.invoke(inputs)

            if isinstance(result, AgentFinish):
                return {"output": result.return_values["output"]}

            # 执行工具
            observation = self._execute_tool(result)
            intermediate_steps.append((result, observation))
            inputs = {
                "input": input_str,
                "intermediate_steps": intermediate_steps,
            }

        return {"output": "Max iterations reached"}
```

---

## 9 完整使用示例

### 9.1 基本用法

```python
from langchain_openai import OpenAI
from langchain.agents import create_react_agent
from langchain_core.tools import tool
from langchain_core.prompts import PromptTemplate

# 定义工具
@tool
def search(query: str) -> str:
    """Search for information on the web."""
    return f"Search results for: {query}"

@tool
def calculator(expression: str) -> str:
    """Evaluate a mathematical expression."""
    return str(eval(expression))

tools = [search, calculator]

# 创建 LLM
llm = OpenAI(model="gpt-4", temperature=0)

# 创建 Prompt
prompt = PromptTemplate.from_template("""
Answer the following questions as best you can.

You have access to the following tools:
{tools}

Use the following format:
Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question

Begin!

Question: {input}
""")

# 创建 Agent
agent = create_react_agent(llm, tools, prompt)

# 执行
result = agent.invoke({"input": "What is 2 + 2?"})
print(result["output"])
```

---

## 10 LangChain ReAct 的特点总结

### 10.1 优点

| 优点 | 说明 |
|------|------|
| **完整性高** | 提供完整的 ReAct 实现 |
| **灵活性强** | 支持自定义 Parser、Prompt、Tools |
| **文档完善** | 丰富的教程和示例 |
| **生态丰富** | 大量集成工具和扩展 |

### 10.2 缺点

| 缺点 | 说明 |
|------|------|
| **抽象层级多** | 学习曲线陡峭 |
| **版本变化快** | API 经常变更 |
| **过度封装** | 难以理解底层逻辑 |

### 10.3 对 omniAgent 的参考价值

| 参考点 | 说明 |
|------|------|
| **AgentAction 字段设计** | `tool`, `tool_input`, `log` |
| **AgentFinish 字段设计** | `return_values`, `log` |
| **Output Parser 实现** | 正则表达式解析 Thought/Action/Action Input |
| **Stop Sequence** | 防止 LLM 幻觉 |
| **trim_intermediate_steps** | 上下文管理 |

---

## 11 关键源码链接

| 文件 | 说明 |
|------|------|
| [ReAct Agent 源码](https://github.com/langchain-ai/langchain/blob/master/libs/langchain/langchain/agents/react/agent.py) | Agent 创建 |
| [ReAct Output Parser](https://github.com/langchain-ai/langchain/blob/master/libs/langchain/langchain/agents/react/output_parser.py) | 输出解析 |
| [format_log_to_str](https://github.com/langchain-ai/langchain/blob/master/libs/langchain/langchain/agents/format_scratchpad/log.py) | 日志格式化 |

---

## 12 版本记录

| 版本 | 时间 | 更新内容 | 作者 |
|------|------|---------|------|
| v1.0 | 2026-03-20 05:28:39 | 初始版本，包含完整 LangChain ReAct 学习报告 | 小沈 |

---

**文档结束**
