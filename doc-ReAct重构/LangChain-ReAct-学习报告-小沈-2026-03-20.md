# LangChain ReAct 学习报告

**文档版本**: v2.0
**创建时间**: 2026-03-20 05:28:39
**更新时间**: 2026-03-20 13:00:00
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
| **Stars** | 130K+ (GitHub) |
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
    log: str  # LLM 的完整原始输出（包含 Thought:Action:Action Input:）
```

**字段说明**:

| 字段 | 类型 | 说明 |
|------|------|------|
| `tool` | `str` | 要调用的工具名称 |
| `tool_input` | `str \| dict` | 工具的输入参数 |
| `log` | `str` | LLM 的**完整原始输出**（不只 Thought，而是整个输出） |

**关键理解**：`log` 字段是 LLM 的**完整原始输出**，包含 `Thought:...Action:...Action Input:...` 所有内容。格式化时**不需要**重新加 "Thought:" 前缀。

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

### 2.3 AgentStep

**来源**: `langchain_core.agents.AgentStep`

**定义**: 中间执行步骤（Action + Observation）

```python
class AgentStep(NamedTuple):
    action: AgentAction  # 执行的 Action
    observation: str  # 工具执行结果
```

**用途**：在 AgentExecutor 内部追踪每个 Action 的执行结果。

### 2.4 intermediate_steps

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

### 4.1 MRKLOutputParser（原始版本）

**来源**: `langchain.agents.mrkl.output_parser`

**实际源码**（已验证）:

```python
import re
from typing import Union
from langchain_core.agents import AgentAction, AgentFinish
from langchain_core.exceptions import OutputParserException
from langchain.agents.agent import AgentOutputParser

FINAL_ANSWER_ACTION = "Final Answer:"

class MRKLOutputParser(AgentOutputParser):
    """MRKL Output parser for the chat agent."""

    format_instructions: str = FORMAT_INSTRUCTIONS

    def parse(self, text: str) -> Union[AgentAction, AgentFinish]:
        includes_answer = FINAL_ANSWER_ACTION in text
        # 【关键】正则支持 Action1:、Action2: 等编号格式
        regex = (
            r"Action\s*\d*\s*:[\s]*(.*?)[\s]*Action\s*\d*\s*Input\s*\d*\s*:[\s]*(.*)"
        )
        action_match = re.search(regex, text, re.DOTALL)
        
        if action_match and includes_answer:
            # 如果 Final Answer 出现在 Action 之前，优先返回 Final Answer
            if text.find(FINAL_ANSWER_ACTION) < text.find(action_match.group(0)):
                start_index = text.find(FINAL_ANSWER_ACTION) + len(FINAL_ANSWER_ACTION)
                end_index = text.find("\n\n", start_index)
                return AgentFinish(
                    {"output": text[start_index:end_index].strip()}, text[:end_index]
                )
            else:
                raise OutputParserException(
                    f"Parsing LLM output produced both a final answer and a parse-able action:"
                    f" {text}"
                )

        if action_match:
            action = action_match.group(1).strip()
            action_input = action_match.group(2)
            tool_input = action_input.strip(" ")
            # 确保 SQL 查询不会被误删引号
            if tool_input.startswith("SELECT ") is False:
                tool_input = tool_input.strip('"')
            return AgentAction(action, tool_input, text)

        elif includes_answer:
            return AgentFinish(
                {"output": text.split(FINAL_ANSWER_ACTION)[-1].strip()}, text
            )

        # 详细错误处理
        if not re.search(r"Action\s*\d*\s*:[\s]*(.*?)", text, re.DOTALL):
            raise OutputParserException(
                f"Could not parse LLM output: `{text}`",
                observation="Invalid Format: Missing 'Action:' after 'Thought:'",
                llm_output=text,
                send_to_llm=True,  # 可回退给 LLM 重新尝试
            )
        elif not re.search(
            r"[\s]*Action\s*\d*\s*Input\s*\d*\s*:[\s]*(.*)", text, re.DOTALL
        ):
            raise OutputParserException(
                f"Could not parse LLM output: `{text}`",
                observation="Invalid Format: Missing 'Action Input:' after 'Action:'",
                llm_output=text,
                send_to_llm=True,
            )
        else:
            raise OutputParserException(f"Could not parse LLM output: `{text}`")
```

### 4.2 ReActSingleInputOutputParser（ReAct 专用版本）

**来源**: `langchain.agents.output_parsers.react_single_input`

**实际源码**（已验证）:

```python
class ReActSingleInputOutputParser(AgentOutputParser):
    """Parses ReAct-style LLM calls that have a single tool input."""

    def parse(self, text: str) -> Union[AgentAction, AgentFinish]:
        includes_answer = FINAL_ANSWER_ACTION in text
        regex = (
            r"Action\s*\d*\s*:[\s]*(.*?)[\s]*Action\s*\d*\s*Input\s*\d*\s*:[\s]*(.*)"
        )
        action_match = re.search(regex, text, re.DOTALL)
        
        if action_match:
            if includes_answer:
                raise OutputParserException(
                    f"Parsing LLM output produced both a final answer and a parse-able action:"
                    f" {text}"
                )
            action = action_match.group(1).strip()
            action_input = action_match.group(2)
            tool_input = action_input.strip(" ")
            tool_input = tool_input.strip('"')  # 移除引号
            return AgentAction(action, tool_input, text)

        elif includes_answer:
            return AgentFinish(
                {"output": text.split(FINAL_ANSWER_ACTION)[-1].strip()}, text
            )

        # 详细错误处理
        if not re.search(r"Action\s*\d*\s*:[\s]*(.*?)", text, re.DOTALL):
            raise OutputParserException(
                f"Could not parse LLM output: `{text}`",
                observation="Invalid Format: Missing 'Action:' after 'Thought:'",
                llm_output=text,
                send_to_llm=True,
            )
        elif not re.search(
            r"[\s]*Action\s*\d*\s*Input\s*\d*\s*:[\s]*(.*)", text, re.DOTALL
        ):
            raise OutputParserException(
                f"Could not parse LLM output: `{text}`",
                observation="Invalid Format: Missing 'Action Input:' after 'Action:'",
                llm_output=text,
                send_to_llm=True,
            )
        else:
            raise OutputParserException(f"Could not parse LLM output: `{text}`")
```

### 4.3 正则表达式详解

**正则**: `r"Action\s*\d*\s*:[\s]*(.*?)[\s]*Action\s*\d*\s*Input\s*\d*\s*:[\s]*(.*)"`

**组成说明**:

| 部分 | 含义 | 匹配示例 |
|------|------|---------|
| `Action\s*` | "Action" + 可选空格 | `Action `, `Action` |
| `\d*\s*` | 可选数字 + 可选空格 | `1`, `2`, `3`, ``（空） |
| `:[\s]*` | 冒号 + 可选空格 | `: `, `: ` |
| `(.*?)` | 非贪婪匹配（捕获组1） | `search`, `read_file` |
| `[\s]*` | 可选空格 | ` `, `` |
| `Action\s*\d*\s*Input\s*\d*\s*` | "Action" + 可选编号 + "Input" + 可选编号 | `Action Input`, `Action1Input2` |
| `:[\s]*` | 冒号 + 可选空格 | `: ` |
| `(.*)` | 贪婪匹配（捕获组2，剩余全部） | `{"query": "..."}` |

**能匹配的格式**:
```
Action: search                          ✅
Action: search                          ✅
Action1: search                         ✅
Action Input: {"query": "..."}          ✅
Action Input: {"query": "..."}          ✅
Action1Input: {"query": "..."}          ✅
```

**之前的错误正则**（学习报告 v1.0）：
```python
# ❌ 错误：不支持编号，且 Thought 部分多余
regex = r"Thought\s*(.*?)\nAction\s*(.*?)\n Action Input\s*(.*?)(?=\nObservation:|$)"
```

---

## 5 format_log_to_str

### 5.1 功能说明

将 `intermediate_steps` 格式化为字符串，用于拼接到 Prompt 中。

### 5.2 实际源码（已验证）

```python
from typing import List, Tuple
from langchain_core.agents import AgentAction

def format_log_to_str(
    intermediate_steps: List[Tuple[AgentAction, str]],
    observation_prefix: str = "Observation: ",
    llm_prefix: str = "Thought: ",
) -> str:
    """Construct the scratchpad that lets the agent continue its thought process.

    Args:
        intermediate_steps: List of tuples of AgentAction and observation strings.
        observation_prefix: Prefix to append the observation with.
             Defaults to "Observation: ".
        llm_prefix: Prefix to append the llm call with.
                Defaults to "Thought: ".

    Returns:
        str: The scratchpad.
    """
    thoughts = ""
    for action, observation in intermediate_steps:
        thoughts += action.log  # 直接使用 LLM 完整输出，不加前缀
        thoughts += f"\n{observation_prefix}{observation}\n{llm_prefix}"
    return thoughts
```

### 5.3 关键理解

**`action.log` 的内容**：LLM 的完整原始输出，例如：
```
Thought: I need to search for the weather.
Action: search
Action Input: {"query": "weather"}
```

**格式化后的输出**：
```
Thought: I need to search for the weather.
Action: search
Action Input: {"query": "weather"}
Observation: 72 degrees, sunny
Thought: 
```

**之前的错误理解**（v1.0）：
```python
# ❌ 错误：action.log 已包含完整输出，再加 "Thought:" 会重复
lines.append(f"Thought: {action.log}")
```

---

## 6 format_log_to_messages（现代版本）

### 6.1 功能说明

现代版本的格式化函数，返回消息列表（而非字符串），用于 Chat 模型。

### 6.2 实际源码（已验证）

```python
from typing import List, Tuple
from langchain_core.agents import AgentAction
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

def format_log_to_messages(
    intermediate_steps: List[Tuple[AgentAction, str]],
    template_tool_response: str = "{observation}",
) -> List[BaseMessage]:
    """Construct the scratchpad that lets the agent continue its thought process.

    Args:
        intermediate_steps: List of tuples of AgentAction and observation strings.
        template_tool_response: Template to format the observation with.
             Defaults to "{observation}".

    Returns:
        List[BaseMessage]: The scratchpad.
    """
    thoughts: List[BaseMessage] = []
    for action, observation in intermediate_steps:
        thoughts.append(AIMessage(content=action.log))  # LLM 输出作为 AI 消息
        human_message = HumanMessage(
            content=template_tool_response.format(observation=observation)
        )
        thoughts.append(human_message)  # 观察结果作为 Human 消息
    return thoughts
```

### 6.3 与 format_log_to_str 的对比

| 对比项 | format_log_to_str | format_log_to_messages |
|--------|-------------------|----------------------|
| **返回类型** | `str` | `List[BaseMessage]` |
| **适用场景** | 传统 Prompt 模型 | Chat 模型（GPT-4, Claude） |
| **消息格式** | 字符串拼接 | AIMessage + HumanMessage |
| **来源** | `langchain.agents.format_scratchpad.log` | `langchain.agents.format_scratchpad.log_to_messages` |

---

## 7 Stop Sequence 机制

### 7.1 作用

**防止 LLM 幻觉 Observation**。告诉 LLM 在输出到指定位置后停止，由运行时提供真实的 Observation。

### 7.2 配置方式

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

### 7.3 执行流程

```
1. LLM 生成: "Thought: ... Action: search Action Input: {...}"
2. 遇到 stop_sequence，停止生成
3. 运行时执行工具
4. 运行时注入: "\nObservation: 真实结果"
5. 继续下一轮 LLM 调用
```

---

## 8 trim_intermediate_steps

### 8.1 功能说明

防止 context overflow，裁剪过长的中间步骤。

### 8.2 实际源码（已验证）

```python
from typing import List, Tuple, Callable, Union
from langchain_core.agents import AgentAction

# AgentExecutor 中的 trim_intermediate_steps 属性
# 支持两种模式：
# - int: 保留最近 N 个步骤（-1 表示不裁剪）
# - Callable: 自定义裁剪函数

# 默认实现（int 模式）
def trim_intermediate_steps_by_count(
    intermediate_steps: List[Tuple[AgentAction, str]],
    max_steps: int = 15,
) -> List[Tuple[AgentAction, str]]:
    """裁剪中间步骤，保留最近的 N 步。"""
    if len(intermediate_steps) <= max_steps:
        return intermediate_steps
    return intermediate_steps[-max_steps:]

# 自定义裁剪函数模式
def custom_trim(
    intermediate_steps: List[Tuple[AgentAction, str]],
) -> List[Tuple[AgentAction, str]]:
    """自定义裁剪逻辑"""
    # 例如：只保留最后 3 步
    return intermediate_steps[-3:]
```

### 8.3 使用场景

当对话历史过长时，使用此函数裁剪早期的中间步骤。

---

## 9 AgentExecutor

### 9.1 功能说明

执行 Agent 的主循环，管理 LLM 调用、工具执行、错误处理、提前停止等功能。

### 9.2 实际源码（已验证，简化版）

```python
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union, Callable
from langchain_core.agents import AgentAction, AgentFinish, AgentStep
from langchain_core.exceptions import OutputParserException
from langchain_core.tools import BaseTool

class AgentExecutor:
    """Agent that is using tools."""
    
    agent: Union[BaseSingleActionAgent, BaseMultiActionAgent, Runnable]
    tools: Sequence[BaseTool]
    return_intermediate_steps: bool = False
    max_iterations: Optional[int] = 15  # 默认最多 15 轮
    max_execution_time: Optional[float] = None  # 最大执行时间
    early_stopping_method: str = "force"  # "force" 或 "generate"
    handle_parsing_errors: Union[bool, str, Callable] = False
    trim_intermediate_steps: Union[int, Callable] = -1  # -1 表示不裁剪
    
    def _iter_next_step(self, name_to_tool_map, color_mapping, inputs, 
                        intermediate_steps, run_manager=None):
        """执行一轮 ReAct 步骤"""
        try:
            # 1. 调用 Agent 的 plan() 方法
            output = self._action_agent.plan(
                intermediate_steps,
                callbacks=run_manager.get_child() if run_manager else None,
                **inputs,
            )
        except OutputParserException as e:
            # 2. 解析错误处理
            if isinstance(self.handle_parsing_errors, bool):
                raise_error = not self.handle_parsing_errors
            else:
                raise_error = False
            
            if raise_error:
                raise ValueError(
                    f"An output parsing error occurred. "
                    f"Pass `handle_parsing_errors=True` to retry. "
                    f"Error: {str(e)}"
                )
            
            # 构造错误观察
            if isinstance(self.handle_parsing_errors, bool):
                if e.send_to_llm:
                    observation = str(e.observation)  # 发回给 LLM
                    text = str(e.llm_output)
                else:
                    observation = "Invalid or incomplete response"
            elif isinstance(self.handle_parsing_errors, str):
                observation = self.handle_parsing_errors
            elif callable(self.handle_parsing_errors):
                observation = self.handle_parsing_errors(e)
            
            # 使用 _Exception 工具处理
            output = AgentAction("_Exception", observation, text)
            observation = ExceptionTool().run(output.tool_input)
            yield AgentStep(action=output, observation=observation)
            return

        # 3. AgentFinish → 返回最终结果
        if isinstance(output, AgentFinish):
            yield output
            return

        # 4. AgentAction → 执行工具
        actions: List[AgentAction]
        if isinstance(output, AgentAction):
            actions = [output]
        else:
            actions = output
        
        for agent_action in actions:
            yield agent_action
        
        for agent_action in actions:
            yield self._perform_agent_action(
                name_to_tool_map, color_mapping, agent_action, run_manager
            )
    
    def _perform_agent_action(self, name_to_tool_map, color_mapping, 
                              agent_action, run_manager=None):
        """执行单个工具"""
        if agent_action.tool in name_to_tool_map:
            tool = name_to_tool_map[agent_action.tool]
            return_direct = tool.return_direct
            
            observation = tool.run(
                agent_action.tool_input,
                verbose=self.verbose,
                callbacks=run_manager.get_child() if run_manager else None,
            )
        else:
            # 工具不存在时的处理
            observation = f"Tool {agent_action.tool} not found"
        
        return AgentStep(action=agent_action, observation=observation)
    
    def _should_continue(self, iterations: int, time_elapsed: float) -> bool:
        """判断是否继续执行"""
        if self.max_iterations is not None and iterations >= self.max_iterations:
            return False
        if self.max_execution_time is not None and time_elapsed >= self.max_execution_time:
            return False
        return True
    
    def return_stopped_response(self, early_stopping_method, intermediate_steps):
        """提前停止时的响应"""
        if early_stopping_method == "force":
            return AgentFinish(
                {"output": "Agent stopped due to iteration limit or time limit."}, ""
            )
        elif early_stopping_method == "generate":
            # 生成一个最终回答
            thoughts = ""
            for action, observation in intermediate_steps:
                thoughts += action.log
                thoughts += f"\nObservation: {observation}\nThought: "
            thoughts += "\n\nI now need to return a final answer based on the previous steps:"
            # 再调用一次 LLM 生成最终回答
            ...
```

### 9.3 关键功能

| 功能 | 说明 | 默认值 |
|------|------|--------|
| **max_iterations** | 最大迭代次数 | 15 |
| **max_execution_time** | 最大执行时间（秒） | None |
| **early_stopping_method** | 提前停止策略 | "force" |
| **handle_parsing_errors** | 解析错误处理 | False |
| **trim_intermediate_steps** | 中间步骤裁剪 | -1（不裁剪） |
| **return_intermediate_steps** | 返回中间步骤 | False |

### 9.4 错误处理机制

```
LLM 输出 → OutputParser 解析
                │
                ├─ 成功 → AgentAction / AgentFinish
                │
                └─ 异常 → OutputParserException
                           │
                           ├─ handle_parsing_errors=True
                           │   └─ 构造 AgentAction("_Exception", error_msg, ...)
                           │       └─ 使用 ExceptionTool 处理
                           │           └─ 回退给 LLM 重新尝试
                           │
                           ├─ handle_parsing_errors="custom msg"
                           │   └─ 使用自定义消息作为 Observation
                           │
                           └─ handle_parsing_errors=False
                               └─ 直接抛出异常
```

### 9.5 提前停止策略

| 策略 | 说明 |
|------|------|
| `"force"` | 直接返回 "Agent stopped due to iteration limit or time limit." |
| `"generate"` | 再调用一次 LLM，要求基于历史步骤生成最终回答 |

---

## 10 完整使用示例

### 10.1 基本用法

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

## 11 LangChain ReAct 的特点总结

### 11.1 优点

| 优点 | 说明 |
|------|------|
| **完整性高** | 提供完整的 ReAct 实现 |
| **灵活性强** | 支持自定义 Parser、Prompt、Tools |
| **错误处理完善** | OutputParserException 支持回退给 LLM |
| **多种格式化** | format_log_to_str + format_log_to_messages |
| **提前停止策略** | force 和 generate 两种策略 |
| **callbacks 支持** | 完整的回调机制 |

### 11.2 缺点

| 缺点 | 说明 |
|------|------|
| **抽象层级多** | 学习曲线陡峭 |
| **版本变化快** | API 经常变更 |
| **过度封装** | 难以理解底层逻辑 |

### 11.3 对 omniAgent 的参考价值

| 参考点 | 说明 |
|------|------|
| **AgentAction 字段设计** | `tool`, `tool_input`, `log`（log 是完整输出） |
| **AgentFinish 字段设计** | `return_values`, `log` |
| **Output Parser 正则** | 支持编号 Action1:，详细异常处理 |
| **format_log_to_str** | 直接使用 action.log，不加前缀 |
| **format_log_to_messages** | 现代 Chat 模型版本 |
| **Stop Sequence** | 防止 LLM 幻觉 |
| **trim_intermediate_steps** | 上下文管理 |
| **AgentExecutor 错误处理** | OutputParserException + send_to_llm |
| **提前停止策略** | force / generate |
| **callbacks 机制** | 完整的回调支持 |

---

## 12 关键源码链接

| 文件 | 说明 |
|------|------|
| [MRKL Output Parser](https://aidoczh.com/langchain/api_reference/_modules/langchain/agents/mrkl/output_parser.html) | 输出解析（实际源码） |
| [ReAct Output Parser](https://aidoczh.com/langchain/api_reference/_modules/langchain/agents/output_parsers/react_single_input.html) | ReAct 专用解析器 |
| [format_log_to_str](https://aidoczh.com/langchain/api_reference/_modules/langchain/agents/format_scratchpad/log.html) | 日志格式化（实际源码） |
| [format_log_to_messages](https://aidoczh.com/langchain/api_reference/_modules/langchain/agents/format_scratchpad/log_to_messages.html) | 消息版本格式化 |
| [Agent Executor](https://aidoczh.com/langchain/api_reference/_modules/langchain/agents/agent.html) | Agent 执行器 |

---

## 13 版本记录

| 版本 | 时间 | 更新内容 | 作者 |
|------|------|---------|------|
| v1.0 | 2026-03-20 05:28:39 | 初始版本 | 小沈 |
| v2.0 | 2026-03-20 13:00:00 | **深度修正**：基于实际 LangChain 源码修正 Output Parser 正则表达式（支持编号）、format_log_to_str 用法（action.log 直接使用）、AgentExecutor 错误处理机制（OutputParserException + send_to_llm）；新增 format_log_to_messages 现代版本、AgentStep 概念、提前停止策略（force/generate）、callbacks 机制、trim_intermediate_steps 两种模式 | 小沈 |

---

**文档结束**
