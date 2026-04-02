# LangChain ReAct 学习报告

**文档版本**: v2.1
**创建时间**: 2026-03-20 05:28:39
**更新时间**: 2026-03-20 14:15:00
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

## 12 字段级信息流转深度分析

### 12.1 核心问题：step 之间信息如何传递？

LangChain 的答案：通过 `intermediate_steps: List[Tuple[AgentAction, str]]`。

```
intermediate_steps = [
    (AgentAction(tool="search", tool_input="天气", log="Thought: ..."), "晴天25°C"),
    (AgentAction(tool="calculator", tool_input="2+2", log="Thought: ..."), "4"),
    ...
]
```

**关键机制**：`intermediate_steps` 是整个 ReAct 循环的核心。每一步的结果以 `(AgentAction, observation)` 元组 append 到这里，下一步读取它来了解之前发生了什么。

### 12.2 核心数据结构字段详解

#### AgentAction（实际源码）

```python
class AgentAction(Serializable):
    tool: str                    # 工具名称
    tool_input: Union[str, dict] # 工具输入参数
    log: str                     # LLM 的完整原始输出
    type: Literal["AgentAction"] = "AgentAction"  # 类型标识
    message_log: Sequence[BaseMessage]  # （子类）消息版本
```

| 字段 | 类型 | 意义 | 谁写入 | 谁读取 |
|------|------|------|--------|--------|
| `tool` | str | 工具名称 | OutputParser.parse() | _perform_agent_action() |
| `tool_input` | str/dict | 工具参数 | OutputParser.parse() | tool.run() |
| `log` | str | LLM 完整输出（含 Thought） | OutputParser.parse() | _construct_scratchpad() |
| `type` | Literal | 类型标识 | 自动 | 序列化/判断 |

**`log` 字段的关键作用**：
- 它是 LLM 的**完整原始输出**（包含 `Thought:...Action:...Action Input:...`）
- 在 `_construct_scratchpad()` 中被直接拼接到 prompt
- **不只存 Thought**，而是存整个 LLM 输出
- 这样下一步的 LLM 能看到之前完整的推理过程

#### AgentFinish（实际源码）

```python
class AgentFinish(Serializable):
    return_values: dict  # 返回值字典，通常 {"output": "最终回答"}
    log: str             # 最终日志（完整 LLM 输出）
    type: Literal["AgentFinish"] = "AgentFinish"
```

| 字段 | 类型 | 意义 | 谁写入 | 谁读取 |
|------|------|------|--------|--------|
| `return_values` | dict | 最终返回值 | OutputParser.parse() | _return() |
| `log` | str | 完整 LLM 输出 | OutputParser.parse() | 日志/debug |

#### AgentStep（实际源码）

```python
class AgentStep(Serializable):
    action: AgentAction  # 执行的 Action
    observation: Any     # 工具执行结果
```

| 字段 | 类型 | 意义 | 谁写入 | 谁读取 |
|------|------|------|--------|--------|
| `action` | AgentAction | 执行的 Action | _iter_next_step() | _consume_next_step() |
| `observation` | Any | 工具结果 | _perform_agent_action() | _consume_next_step() |

**AgentStep 的作用**：它是中间数据结构。`_iter_next_step()` yield AgentStep，`_consume_next_step()` 将其转换为 `(AgentAction, str)` 元组加入 `intermediate_steps`。

### 12.3 一个完整的循环：字段如何流转

#### 步骤 1：_iter_next_step（LLM 调用 + 解析）

```
输入：
├── intermediate_steps = [(AgentAction, "观察结果"), ...]  ← 之前的步骤
├── inputs = {"input": "用户问题", ...}                    ← 用户输入

处理：
├── 1. _prepare_intermediate_steps(intermediate_steps)
│   └── trim_intermediate_steps 裁剪（如果超过限制）
│
├── 2. agent.plan(intermediate_steps, **inputs)
│   └── agent._construct_scratchpad(intermediate_steps)  ← 关键！
│   │   └── 拼接: action.log + "\nObservation: " + observation + "\nThought: "
│   └── get_full_inputs() → {"input": ..., "agent_scratchpad": ..., "stop": ...}
│   └── llm_chain.predict(**full_inputs)
│   └── output_parser.parse(output) → AgentAction or AgentFinish
│
├── 3. 如果是 AgentFinish → yield，结束
├── 4. 如果是 AgentAction → yield AgentAction
└── 5. _perform_agent_action() → yield AgentStep

输出：
├── AgentAction（LLM 决定要调用的工具）
└── AgentStep（工具执行结果）
```

#### 步骤 2：_perform_agent_action（执行工具）

```
输入：AgentAction(tool="search", tool_input="天气", log="Thought: ...")

处理：
├── tool = name_to_tool_map[agent_action.tool]
├── observation = tool.run(agent_action.tool_input)
└── return AgentStep(action=agent_action, observation=observation)

输出：AgentStep(action=AgentAction, observation="晴天25°C")
```

#### 步骤 3：_consume_next_step（转换格式）

```
输入：[AgentAction, AgentStep(action, observation)]

处理：
├── 如果最后一个是 AgentFinish → 直接返回
└── 否则 → [(a.action, a.observation) for a in values if isinstance(a, AgentStep)]

输出：intermediate_steps.append((AgentAction, "晴天25°C"))
```

#### 步骤 4：回到步骤 1（下一轮）

```
intermediate_steps 现在包含新的 (AgentAction, observation)
    ↓
agent._construct_scratchpad(intermediate_steps) 读取所有步骤
    ↓
拼接成 prompt，传给 LLM
    ↓
LLM 看到之前的 Action + Observation → 输出新的推理
```

### 12.4 _construct_scratchpad：信息传递的核心

```python
def _construct_scratchpad(self, intermediate_steps):
    """构造 agent 的推理历史，传给下一步的 LLM。"""
    thoughts = ""
    for action, observation in intermediate_steps:
        thoughts += action.log  # LLM 完整输出（Thought:...Action:...Action Input:...）
        thoughts += f"\n{self.observation_prefix}{observation}\n{self.llm_prefix}"
    return thoughts
```

**信息传递过程**：

```
intermediate_steps = [
    (AgentAction(log="Thought: 我需要搜索天气\nAction: search\nAction Input: {\"query\": \"天气\"}"), 
     "晴天25°C"),
]

_construct_scratchpad() 输出：
"""
Thought: 我需要搜索天气
Action: search
Action Input: {"query": "天气"}
Observation: 晴天25°C
Thought: 
"""
    ↓
这个字符串被放入 agent_scratchpad 变量
    ↓
LLM 看到：
- System: "You are designed to help..."
- User: "天气怎么样？"
- (agent_scratchpad 中的推理历史)
    ↓
LLM 输出新的推理（基于之前的 Action + Observation）
```

### 12.5 字段流转图（完整版）

```
用户输入: "天气怎么样？"
    │
    ▼
┌─ AgentExecutor._iter_next_step ──────────────────────────┐
│  intermediate_steps = [] (第一次，空)                    │
│  inputs = {"input": "天气怎么样？"}                      │
│                                                           │
│  agent.plan(intermediate_steps, **inputs)                │
│  │                                                        │
│  ├─ _construct_scratchpad([]) → ""                       │
│  ├─ get_full_inputs() →                                   │
│  │    {"input": "天气怎么样？",                          │
│  │     "agent_scratchpad": "",                            │
│  │     "stop": ["\nObservation:", "\n\tObservation:"]}    │
│  ├─ llm_chain.predict(**inputs)                          │
│  │    → "Thought: 我需要搜索天气\nAction: search\nAction Input: {\"query\": \"天气\"}" │
│  └─ output_parser.parse(output)                          │
│       → AgentAction(                                      │
│           tool="search",                                  │
│           tool_input={"query": "天气"},                   │
│           log="Thought: 我需要搜索天气\nAction: search\nAction Input: {\"query\": \"天气\"}" │
│         )                                                 │
│                                                           │
│  yield AgentAction                                        │
│                                                           │
│  _perform_agent_action(AgentAction)                       │
│  │                                                        │
│  ├─ tool = name_to_tool_map["search"]                    │
│  ├─ observation = tool.run({"query": "天气"})             │
│  │    → "晴天25°C"                                       │
│  └─ yield AgentStep(action=AgentAction, observation="晴天25°C") │
└───────────────────────────────────────────────────────────┘
    │
    ▼
┌─ _consume_next_step ─────────────────────────────────────┐
│  输入: [AgentAction, AgentStep(action, "晴天25°C")]     │
│                                                           │
│  输出: [(AgentAction, "晴天25°C")]                       │
│  → intermediate_steps = [(AgentAction, "晴天25°C")]      │
└───────────────────────────────────────────────────────────┘
    │
    ▼
    回到 _iter_next_step（第2轮）
    │
    ├─ intermediate_steps = [(AgentAction(log="Thought:..."), "晴天25°C")]
    │
    ├─ _construct_scratchpad(intermediate_steps)
    │   → "Thought: 我需要搜索天气\nAction: search\nAction Input: {\"query\": \"天气\"}\nObservation: 晴天25°C\nThought: "
    │
    ├─ agent.plan(intermediate_steps, **inputs)
    │   → "Thought: 天气很好，不需要更多信息\nFinal Answer: 今天北京晴天，25°C"
    │
    └─ output_parser.parse(output)
        → AgentFinish(return_values={"output": "今天北京晴天，25°C"}, log="Thought: ...")
    │
    ▼
┌─ AgentExecutor._return ──────────────────────────────────┐
│  return output.return_values                              │
│  → {"output": "今天北京晴天，25°C"}                      │
└───────────────────────────────────────────────────────────┘
```

### 12.6 关键字段汇总表

#### AgentAction 各字段

| 字段 | 类型 | 意义 | 对下一步的影响 |
|------|------|------|---------------|
| `tool` | str | 工具名称 | 决定调用哪个工具 |
| `tool_input` | str/dict | 工具参数 | 传给工具执行 |
| `log` | str | LLM 完整输出 | 拼接到下一步的 prompt |
| `type` | Literal | 类型标识 | 判断是否是 AgentAction |

#### AgentFinish 各字段

| 字段 | 类型 | 意义 | 对下一步的影响 |
|------|------|------|---------------|
| `return_values` | dict | 最终返回值 | 返回给用户 |
| `log` | str | 完整 LLM 输出 | 日志/debug |
| `type` | Literal | 类型标识 | 结束循环 |

#### AgentExecutor 各字段

| 字段 | 类型 | 意义 | 默认值 |
|------|------|------|--------|
| `agent` | Agent | Agent 实例 | 必填 |
| `tools` | Sequence[BaseTool] | 工具列表 | 必填 |
| `max_iterations` | int | 最大迭代次数 | 15 |
| `max_execution_time` | float | 最大执行时间 | None |
| `early_stopping_method` | str | 提前停止策略 | "force" |
| `handle_parsing_errors` | bool/str/Callable | 错误处理 | False |
| `trim_intermediate_steps` | int/Callable | 步骤裁剪 | -1 |
| `return_intermediate_steps` | bool | 返回中间步骤 | False |

### 12.7 上一个 step 如何影响下一个 step？

**核心机制：通过 `intermediate_steps` 传递信息。**

```
Step N 的输出 → intermediate_steps.append((AgentAction, observation))
    ↓
Step N+1 的输入 → agent._construct_scratchpad(intermediate_steps)
    ↓
Step N+1 的 LLM 输入包含 Step N 的 action.log + observation
    ↓
Step N+1 的 LLM 输出受 Step N 影响
```

**关键理解**：`action.log` 是信息传递的关键。它保存了 LLM 的完整推理过程（包括 Thought、Action、Action Input），下一步的 LLM 通过 `_construct_scratchpad()` 读取这些信息，从而知道之前做了什么、得到了什么结果。

### 12.8 LangChain vs LlamaIndex 字段设计对比

| 对比项 | LangChain | LlamaIndex |
|--------|-----------|-----------|
| **存储方式** | `intermediate_steps: List[Tuple]` | `ctx.store["current_reasoning"]` |
| **Action 类型** | `AgentAction(tool, tool_input, log)` | `ActionReasoningStep(thought, action, action_input)` |
| **Observation 类型** | 无独立类型（直接存字符串） | `ObservationReasoningStep(observation)` |
| **Final 类型** | `AgentFinish(return_values, log)` | `ResponseReasoningStep(thought, response)` |
| **Thought 存储** | 在 `action.log` 里（整个输出） | 在 Action/Response 的 `thought` 字段里 |
| **格式化** | `_construct_scratchpad()` | `ReActChatFormatter.format()` |
| **step 间传递** | `intermediate_steps` 列表 | `current_reasoning` 列表 |

---

## 13 关键源码链接

| 文件 | 说明 |
|------|------|
| [MRKL Output Parser](https://aidoczh.com/langchain/api_reference/_modules/langchain/agents/mrkl/output_parser.html) | 输出解析（实际源码） |
| [ReAct Output Parser](https://aidoczh.com/langchain/api_reference/_modules/langchain/agents/output_parsers/react_single_input.html) | ReAct 专用解析器 |
| [format_log_to_str](https://aidoczh.com/langchain/api_reference/_modules/langchain/agents/format_scratchpad/log.html) | 日志格式化（实际源码） |
| [format_log_to_messages](https://aidoczh.com/langchain/api_reference/_modules/langchain/agents/format_scratchpad/log_to_messages.html) | 消息版本格式化 |
| [Agent Executor](https://aidoczh.com/langchain/api_reference/_modules/langchain/agents/agent.html) | Agent 执行器 |

---

## 14 版本记录

| 版本 | 时间 | 更新内容 | 作者 |
|------|------|---------|------|
| v1.0 | 2026-03-20 05:28:39 | 初始版本 | 小沈 |
| v2.0 | 2026-03-20 13:00:00 | **深度修正**：基于实际 LangChain 源码修正 Output Parser 正则表达式（支持编号）、format_log_to_str 用法（action.log 直接使用）、AgentExecutor 错误处理机制（OutputParserException + send_to_llm）；新增 format_log_to_messages 现代版本、AgentStep 概念、提前停止策略（force/generate）、callbacks 机制、trim_intermediate_steps 两种模式 | 小沈 |
| v2.1 | 2026-03-20 14:15:00 | **新增第12章：字段级信息流转深度分析**：基于实际源码分析 AgentAction/AgentFinish/AgentStep 各字段意义；_construct_scratchpad() 信息传递机制；intermediate_steps 如何实现 step 间信息传递；完整循环流转图；LangChain vs LlamaIndex 字段设计对比 | 小沈 |
| v2.2 | 2026-04-02 21:00:00 | **新增第13-16章**：action后端处理逻辑补充、LangChain tool类型详解、各type yield到前端字段、各type前端显示方法 | 小沈 |

---

## 13 Action 后端处理逻辑深度分析

### 13.1 LangChain Action 完整处理流程

**完整流程**：

```
LLM 输出 → OutputParser 解析 → AgentAction → 工具执行 → observation → intermediate_steps.append()
```

**详细步骤**：

#### 步骤1：LLM 返回原始文本
```python
# LLM 返回示例
llm_response = """Thought: I need to search for weather information
Action: search
Action Input: {"query": "weather in Beijing"}"""
```

#### 步骤2：OutputParser 解析
```python
# MRKLOutputParser 或 ReActSingleInputOutputParser 处理
from langchain.agents.output_parsers import ReActSingleInputOutputParser

parser = ReActSingleInputOutputParser()
agent_action = parser.parse(llm_response)
# 返回: AgentAction(
#   tool="search",
#   tool_input={"query": "weather in Beijing"},
#   log="Thought: I need to search for weather information\nAction: search\nAction Input: {\"query\": \"weather in Beijing\"}"
# )
```

**解析逻辑**（正则表达式）：
```python
# 支持 Action1: Action2: 等编号格式
regex = r"Action\s*\d*\s*:[\s]*(.*?)[\s]*Action\s*\d*\s*Input\s*\d*\s*:[\s]*(.*)"
action_match = re.search(regex, text, re.DOTALL)
action = action_match.group(1).strip()
action_input = action_match.group(2).strip()
return AgentAction(action, action_input, text)  # text 是完整原始输出
```

#### 步骤3：工具执行
```python
# AgentExecutor._perform_agent_action()
tool = name_to_tool_map[agent_action.tool]
observation = tool.run(
    agent_action.tool_input,
    verbose=self.verbose,
)
# 返回: "晴天25°C"
```

#### 步骤4：生成 AgentStep 并追加
```python
# AgentStep 包含 action 和 observation
agent_step = AgentStep(action=agent_action, observation=observation)

# 转换为 (AgentAction, str) 元组
intermediate_steps.append((agent_action, observation))
```

#### 步骤5：构造 scratchpad 传给下一步 LLM
```python
# _construct_scratchpad() 处理
def _construct_scratchpad(intermediate_steps):
    thoughts = ""
    for action, observation in intermediate_steps:
        thoughts += action.log  # 直接使用 LLM 完整输出
        thoughts += f"\nObservation: {observation}\nThought: "
    return thoughts
```

### 13.2 Action 处理的关键点

**action.log 的作用**：
- 保存 LLM 的**完整原始输出**（Thought + Action + Action Input）
- 在 `_construct_scratchpad()` 中直接拼接，不加前缀
- 下一步的 LLM 能看到之前完整的推理过程

**observation 的处理**：
- 工具执行结果直接作为字符串
- 通过 `observation_prefix`（默认 "Observation: "）拼接
- 通过 `llm_prefix`（默认 "Thought: "）提示 LLM 继续

**错误处理**：
```python
# 解析失败时 OutputParserException
except OutputParserException as e:
    if e.send_to_llm:
        # 发回给 LLM 重新尝试
        observation = str(e.observation)
    else:
        observation = "Invalid or incomplete response"
```

### 13.3 LangChain Action vs LlamaIndex Action

| 对比项 | LangChain | LlamaIndex |
|--------|-----------|-----------|
| **类型名称** | `AgentAction` | `ActionReasoningStep` |
| **字段** | `tool`, `tool_input`, `log` | `thought`, `action`, `action_input` |
| **Thought 存储** | 在 `log` 中（完整输出） | 在 `thought` 字段中 |
| **解析方式** | 正则表达式 | 正则表达式 |
| **信息传递** | `intermediate_steps` 列表 | `current_reasoning` 列表 |
| **格式化** | `_construct_scratchpad()` | `ReActChatFormatter.format()` |

---

## 14 LangChain Tool 类型详解

### 14.1 BaseTool（基类）

**定义**：所有工具的基类。

```python
from langchain_core.tools import BaseTool

class BaseTool(BaseModel):
    name: str                           # 工具名称（唯一标识）
    description: str                    # 工具描述（LLM 用它决定何时调用）
    args_schema: Optional[Type[BaseModel]]  # 参数 Schema（Pydantic 模型）
    return_direct: bool = False         # 是否直接返回给用户
    
    @abstractmethod
    def _run(self, *args, **kwargs) -> Any:
        """同步执行工具"""
        
    @abstractmethod
    async def _arun(self, *args, **kwargs) -> Any:
        """异步执行工具"""
```

### 14.2 StructuredTool（结构化参数工具）

**定义**：支持多参数、类型检查的工具。

```python
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

class CalculatorInput(BaseModel):
    x: int = Field(description="第一个数字")
    y: int = Field(description="第二个数字")
    operation: str = Field(description="操作类型: add, sub, mul, div")

def calculator(x: int, y: int, operation: str) -> str:
    """执行数学计算"""
    if operation == "add":
        return str(x + y)
    elif operation == "sub":
        return str(x - y)
    elif operation == "mul":
        return str(x * y)
    elif operation == "div":
        return str(x / y) if y != 0 else "Error: division by zero"

tool = StructuredTool.from_function(
    func=calculator,
    name="calculator",
    description="执行数学计算",
    args_schema=CalculatorInput,
    return_direct=False,
)
```

**关键字段**：
| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | str | 工具名称，LLM 调用时使用 |
| `description` | str | 工具描述，LLM 用它决定何时调用 |
| `args_schema` | BaseModel | 参数 Schema，用于类型检查和文档生成 |
| `return_direct` | bool | True 时工具结果直接返回给用户，不经过 LLM |
| `func` | Callable | 实际执行的函数 |
| `coroutine` | Callable | 异步版本的函数（可选） |

### 14.3 Tool（简单工具）

**定义**：单字符串输入的工具。

```python
from langchain_core.tools import Tool

# 简单工具：只接受一个字符串输入
search_tool = Tool(
    name="search",
    func=lambda query: f"搜索结果: {query}",
    description="搜索互联网获取信息",
)
```

### 14.4 FunctionTool（函数工具）

**定义**：从函数自动创建工具。

```python
# LangChain 0.2+ 推荐方式：直接传函数
def get_weather(city: str, unit: str = "celsius") -> str:
    """获取指定城市的天气信息。
    
    Args:
        city: 城市名称
        unit: 温度单位，celsius 或 fahrenheit
    """
    return f"{city} 的天气是晴天，25°C"

# 直接传给 agent
agent = create_agent(
    model="gpt-4",
    tools=[get_weather],  # 自动转换为 Tool
)
```

### 14.5 工具类型对比表

| 类型 | 输入方式 | 参数类型检查 | 适用场景 |
|------|---------|------------|---------|
| **Tool** | 单字符串 | 无 | 简单工具，如搜索 |
| **StructuredTool** | Pydantic Schema | 强类型 | 多参数工具，如计算器 |
| **BaseTool** | 自定义 | 自定义 | 需要完全控制 |
| **Function** | 函数签名 | 自动推断 | 快速创建工具 |

### 14.6 LangChain 工具的关键属性

**return_direct 机制**：
```python
# return_direct=True 的工具
final_answer_tool = StructuredTool.from_function(
    func=lambda answer: answer,
    name="final_answer",
    description="直接返回最终答案",
    return_direct=True,  # 关键：直接返回，不经过 LLM
)

# 执行流程：
# LLM 决定调用 final_answer → 工具执行 → 直接返回结果给用户
# （不回到 LLM 进行下一步推理）
```

**args_schema 的作用**：
1. **参数验证**：LLM 传参时自动验证类型
2. **文档生成**：自动生成工具描述给 LLM
3. **错误处理**：参数错误时返回友好提示

```python
# 生成的工具描述（给 LLM 看）
"""
calculator(x: int, y: int, operation: str) -> str
执行数学计算

Parameters:
- x: 第一个数字 (int)
- y: 第二个数字 (int)
- operation: 操作类型: add, sub, mul, div (str)
"""
```

---

## 15 各 Type Yield 到前端的字段与信息

### 15.1 总览：Type 与前端字段映射

| Type | 核心字段 | 可选字段 | 数据来源 |
|------|---------|---------|---------|
| **start** | `step`, `model`, `provider`, `display_name`, `timestamp` | `session_id`, `task`, `user_message`, `security_check` | Agent 初始化 |
| **thought** | `step`, `content`, `timestamp` | `tool_name`, `tool_params` | LLM 返回解析 |
| **action_tool** | `step`, `execution_status`, `execution_result`, `timestamp` | `error_message`, `retry_count`, `tool_name`, `tool_params` | 工具执行结果 |
| **observation** | `step`, `observation`, `timestamp` | `tool_name`, `tool_params`, `return_direct` | 工具执行结果 |
| **final** | `step`, `response`, `is_finished`, `timestamp` | `thought`, `is_streaming` | LLM 最终回答 |
| **error** | `step`, `error_type`, `error_message`, `timestamp` | `recoverable`, `stack_trace`, `context` | 异常捕获 |
| **chunk** | `content`, `delta`, `timestamp` | `is_final`, `is_reasoning` | LLM 流式输出 |

### 15.2 各 Type 详细字段说明

#### start 类型
```python
# Yield 到前端的完整数据
{
    "type": "start",
    "step": 1,
    "model": "glm-4",                    # LLM 模型名称
    "provider": "zhipu",                 # LLM 提供商
    "display_name": "智谱GLM-4",         # 显示名称
    "timestamp": 1743566400000,          # 毫秒级时间戳
    "session_id": "sess_abc123",         # 会话 ID
    "task": "帮我查找文件",              # 用户任务
    "user_message": "帮我查找/home目录下的所有txt文件",  # 用户原始消息
    "security_check": {                  # 安全检查结果
        "passed": True,
        "risk_level": "low"
    }
}
```

#### thought 类型
```python
# Yield 到前端的完整数据
{
    "type": "thought",
    "step": 2,
    "content": "我需要先查看目录结构，然后才能决定如何整理文件。",  # 推理内容
    "timestamp": 1743566405000,
    "tool_name": "list_directory",       # 如果决定调用工具
    "tool_params": {"path": "/home"}     # 工具参数
}
```

#### action_tool 类型
```python
# Yield 到前端的完整数据
{
    "type": "action_tool",
    "step": 3,
    "execution_status": "success",       # success/error/timeout
    "execution_result": "找到3个文件",    # 执行结果
    "timestamp": 1743566406000,
    "error_message": None,               # 错误信息（status=error时）
    "retry_count": 0,                    # 重试次数
    "tool_name": "list_directory",       # 工具名称
    "tool_params": {"path": "/home"}     # 工具参数
}
```

#### observation 类型
```python
# Yield 到前端的完整数据
{
    "type": "observation",
    "step": 4,
    "observation": "找到3个文件：file1.txt, file2.txt, file3.txt",  # 观察结果
    "timestamp": 1743566407000,
    "tool_name": "list_directory",       # 工具名称（从 thought 复制）
    "tool_params": {"path": "/home"},    # 工具参数（从 thought 复制）
    "return_direct": False               # 是否直接返回
}
```

#### final 类型
```python
# Yield 到前端的完整数据
{
    "type": "final",
    "step": 8,
    "response": "根据搜索结果，/home目录下有以下文件...",  # 最终回答
    "is_finished": True,                 # 业务完成标志
    "timestamp": 1743566415000,
    "thought": "经过多次搜索，我已找到所有相关信息",  # 最终推理
    "is_streaming": False                # 是否流式输出
}
```

#### error 类型
```python
# Yield 到前端的完整数据
{
    "type": "error",
    "step": 5,
    "error_type": "tool_error",          # 错误类型
    "error_message": "工具执行超时，请重试",  # 错误信息
    "timestamp": 1743566410000,
    "recoverable": True,                 # 是否可恢复
    "stack_trace": "...",                # 堆栈跟踪（开发模式）
    "context": {"step": 5, "tool": "search_files"}  # 错误上下文
}
```

#### chunk 类型
```python
# Yield 到前端的完整数据
{
    "type": "chunk",
    "content": "根据搜索结果...",        # 累积内容
    "delta": "文件",                     # 增量内容
    "timestamp": 1743566408000,
    "is_final": False,                   # 是否最后一个 chunk
    "is_reasoning": False                # 是否为推理内容
}
```

---

## 16 各 Type 前端显示方法详解

### 16.1 前端架构概览

**核心组件**：
```
MessageItem.tsx                    # 消息容器
  └── StepRow                      # 单行步骤显示
       ├── start 显示              # 对话开始
       ├── thought 显示            # 思考过程
       ├── action_tool 显示        # 工具执行
       ├── observation 显示        # 观察结果
       ├── final 显示              # 最终回答
       ├── error 显示              # 错误信息
       └── renderToolResult()      # 工具结果视图
            ├── ListDirectoryView  # 目录列表
            ├── ReadFileView       # 文件内容
            ├── WriteFileView      # 文件写入
            ├── SearchFilesView    # 文件搜索
            └── ...
```

**样式系统**（`stepStyles.ts`）：
```typescript
// 每种 type 有独特的颜色方案
const colorSchemes: Record<StepType, ColorScheme> = {
  thought: { bg1: "#fff7e6", border: "#ffd591", text: "#ad4e00", label: "💭 思考" },
  start: { bg1: "#e6f7ff", border: "#91d5ff", text: "#0050b3", label: "🚀 开始" },
  action_tool: { bg1: "#e6f7ff", border: "#69c0ff", text: "#003a8c", label: "⚙️ 执行" },
  observation: { bg1: "#e6ffed", border: "#73d13d", text: "#237804", label: "📋 观察" },
  final: { bg1: "#f6ffed", border: "#b7eb8f", text: "#389e0d", label: "✅ 完成" },
  error: { bg1: "#fff1f0", border: "#ffa39e", text: "#cf1322", label: "❌ 错误" },
  chunk: { bg1: "#f9f0ff", border: "#d3adf7", text: "#722ed1", label: "📝 内容" },
}
```

### 16.2 start 类型前端显示

**显示位置**：`MessageItem.tsx:421-467`

**显示内容**：
```tsx
<div style={getStepStyle("start")}>
  {/* 标题行 */}
  <div style={getStepTitleStyle("start")}>
    🚀 用户消息：{step.user_message || "(无)"}
  </div>
  
  {/* 详细信息行 */}
  <div>
    <span>任务ID：{step.task_id || "无"}</span>
    {step.security_check && (
      <span>安全：{step.security_check.is_safe ? "✅ 通过" : "⚠️ 拦截"}</span>
    )}
  </div>
</div>
```

**视觉效果**：
- 背景：蓝色渐变 `#e6f7ff → #f0f8ff`
- 边框：`#91d5ff`
- 文字：`#0050b3`（深蓝）
- 标签：🚀 开始

**当前问题**：
- ❌ 未显示 `model`、`provider`、`display_name`
- ❌ 未显示 `task` 字段
- ⚠️ 使用 `task_id` 而非 `session_id`

**改进建议**：
```tsx
{/* 添加模型信息 */}
{(step.model || step.provider) && (
  <div>🤖 模型：{step.display_name || step.model} ({step.provider})</div>
)}
{/* 添加任务描述 */}
{step.task && <div>📋 任务：{step.task}</div>}
```

### 16.3 thought 类型前端显示

**显示位置**：`MessageItem.tsx:469-510`

**显示内容**：
```tsx
<div style={getStepStyle("thought")}>
  {/* 推理内容 */}
  <span style={getStepContentStyle("thought", "primary")}>
    {step.reasoning || step.content || ""}
  </span>
  
  {/* 信息区域：下一步、参数 */}
  <div style={{...信息区域背景...}}>
    {(step as any).action_tool && (
      <div>⬇️ 下一步：{(step as any).action_tool}</div>
    )}
    {(step as any).params && (
      <div><JsonHighlight data={(step as any).params} /></div>
    )}
  </div>
</div>
```

**视觉效果**：
- 背景：橙色渐变 `#fff7e6 → #fffbe6`
- 边框：`#ffd591`
- 文字：`#ad4e00`（深橙）
- 标签：💭 思考

**当前问题**：
- ⚠️ 使用 `action_tool`/`params` 而非设计文档的 `tool_name`/`tool_params`
- ✅ 兼容 `reasoning` 和 `content` 字段

**改进建议**：
```tsx
// 统一字段名
{step.tool_name && <div>⬇️ 下一步：{step.tool_name}</div>}
{step.tool_params && <JsonHighlight data={step.tool_params} />}
```

### 16.4 action_tool 类型前端显示

**显示位置**：`MessageItem.tsx:218-308`

**显示内容**：
```tsx
{step.type === "action_tool" && (
  <>
    {/* 工具名称 */}
    {step.action_description || step.tool_name || "执行中..."}
    
    {/* 工具参数（可展开） */}
    {step.tool_params && (
      <div onClick={() => toggleExpand(stepIndex + 1000)}>
        <JsonHighlight data={step.tool_params} />
        <span>{expanded ? "▲ 收起" : "▼ 展开"}</span>
      </div>
    )}
    
    {/* 工具结果视图 */}
    {renderToolResult(step, isExpanded, toggleExpand, stepIndex)}
    
    {/* 状态和摘要 */}
    {(step as any).execution_status && (
      <div>📊 状态：{(step as any).execution_status} | 摘要：{(step as any).summary}</div>
    )}
  </>
)}
```

**`renderToolResult` 分支函数**（`MessageItem.tsx:572-618`）：
```tsx
const renderToolResult = (step, isExpanded, toggleExpand, stepIndex) => {
  const data = step.raw_data?.data || step.raw_data;
  switch (step.tool_name) {
    case "list_directory": return <ListDirectoryView data={data} toolParams={step.tool_params} isExpanded={isExpanded} onToggle={handleToggle} />;
    case "read_file": return <ReadFileView data={data} />;
    case "write_file": return <WriteFileView data={data} />;
    case "delete_file": return <DeleteFileView data={data} />;
    case "move_file": return <MoveFileView data={data} />;
    case "search_files": return <SearchFilesView data={transformedSearchFilesData(data)} />;
    case "search_file_content": return <SearchFileContentView data={transformedSearchFileContentData(data)} />;
    case "generate_report": return <GenerateReportView data={data} isExpanded={isExpanded} onToggle={handleToggle} />;
    default: return <pre>{JSON.stringify(data, null, 2)}</pre>;
  }
};
```

**视觉效果**：
- 背景：蓝色渐变 `#e6f7ff → #f0f5ff`
- 边框：`#69c0ff`
- 文字：`#003a8c`（深蓝）
- 标签：⚙️ 执行

**当前问题**：
- ❌ 未显示 `error_message`
- ❌ 未显示 `retry_count`
- ✅ 工具视图渲染完善（8种工具）

**改进建议**：
```tsx
{/* 添加错误信息显示 */}
{step.execution_status === "error" && step.error_message && (
  <div style={{ color: "#ff4d4f" }}>❌ 错误：{step.error_message}</div>
)}
{/* 添加重试次数 */}
{step.retry_count > 0 && (
  <div>🔄 重试次数：{step.retry_count}</div>
)}
```

### 16.5 observation 类型前端显示

**显示位置**：`MessageItem.tsx:310-419`

**显示内容**：
```tsx
{step.type === "observation" && (
  <>
    {/* 观察内容 */}
    {(step as any).obs_reasoning || step.reasoning || step.content && (
      <div style={getStepStyle("observation")}>
        <span>{(step as any).obs_reasoning || step.reasoning || step.content}</span>
      </div>
    )}
    
    {/* 文件列表（可展开） */}
    {!step.content && step.obs_raw_data?.entries && (
      <div>
        <span onClick={() => toggleExpand(stepIndex)}>
          {isExpanded ? "▼ 收起" : "▶ 展开"} 文件列表 ({entryCount}个)
        </span>
        {isExpanded && obsRawData.entries.map(...)}
      </div>
    )}
    
    {/* 摘要 */}
    {step.obs_summary && <div>📊 {step.obs_summary}</div>}
    
    {/* 下一步/参数/结束标志 */}
    <div>
      {step.obs_action_tool && <div>⬇️ 下一步：{step.obs_action_tool}</div>}
      {step.obs_params && <JsonHighlight data={step.obs_params} />}
      {step.is_finished && <span style={getFinishedBadgeStyle()}>✅ 结束</span>}
    </div>
  </>
)}
```

**视觉效果**：
- 背景：绿色渐变 `#e6ffed → #f5fff5`
- 边框：`#73d13d`
- 文字：`#237804`（深绿）
- 标签：📋 观察

**关键发现**：
- 前端使用 `obs_` 前缀字段（`obs_reasoning`、`obs_raw_data`、`obs_summary` 等）
- 工具视图渲染在 **action_tool** 中，不在 observation 中
- observation 主要显示观察摘要和下一步信息

### 16.6 final 类型前端显示

**显示位置**：`MessageItem.tsx:512-518`

**显示内容**：
```tsx
{step.type === "final" && (
  <div style={getStepStyle("final")}>
    <span style={getStepContentStyle("final", "primary")}>
      {step.content || ""}
    </span>
  </div>
)}
```

**视觉效果**：
- 背景：绿色渐变 `#f6ffed → #f5f5f5`
- 边框：`#b7eb8f`
- 文字：`#389e0d`（深绿）
- 标签：✅ 完成

**当前问题**：
- ❌ 使用 `content` 而非设计文档的 `response`
- ❌ 未显示 `is_finished` 标志
- ❌ 未显示 `thought` 推理
- ❌ 未实现 `is_streaming` 打字机效果

**改进建议**：
```tsx
{step.type === "final" && (
  <div style={getStepStyle("final")}>
    {/* 最终回答内容 */}
    <span>{step.response || step.content || ""}</span>
    {/* 推理过程 */}
    {step.thought && <div>💭 推理：{step.thought}</div>}
    {/* 结束标志 */}
    {step.is_finished && <span style={getFinishedBadgeStyle()}>✅ 结束</span>}
  </div>
)}
```

### 16.7 error 类型前端显示

**显示位置**：`MessageItem.tsx:519-531`

**显示内容**：
```tsx
{step.type === "error" && (
  <ErrorDetail
    errorType={(step as any).error_type}
    errorMessage={step.error_message || (step as any).message}
    errorTimestamp={typeof step.timestamp === 'number' ? new Date(step.timestamp).toISOString() : String(step.timestamp)}
    errorDetails={(step as any).details}
    errorStack={(step as any).stack}
    errorRetryable={(step as any).retryable}
    errorRetryAfter={(step as any).retry_after}
    model={(step as any).model}
    provider={(step as any).provider}
  />
)}
```

**ErrorDetail 组件**：
- 显示错误类型、错误消息、时间戳
- 显示详细信息、堆栈跟踪
- 显示是否可重试、重试等待时间
- 显示模型和提供商信息

**视觉效果**：
- 背景：红色渐变 `#fff1f0 → #fff`
- 边框：`#ffa39e`
- 文字：`#cf1322`（深红）
- 标签：❌ 错误

### 16.8 前端显示方法总结

| Type | 显示位置 | 主要组件 | 颜色方案 | 当前状态 |
|------|---------|---------|---------|---------|
| **start** | StepRow | 内联渲染 | 蓝色系 | ⚠️ 缺失部分字段显示 |
| **thought** | StepRow | 内联渲染 | 橙色系 | ⚠️ 字段名不一致 |
| **action_tool** | StepRow | renderToolResult | 蓝色系 | ⚠️ 缺失错误/重试显示 |
| **observation** | StepRow | 内联渲染 | 绿色系 | ✅ 基本完善 |
| **final** | StepRow | 内联渲染 | 绿色系 | ❌ 字段名不一致 |
| **error** | StepRow | ErrorDetail 组件 | 红色系 | ✅ 功能完善 |
| **chunk** | AI回复区域 | 逐个渲染 | 紫色系 | ✅ 流式显示完善 |

---

**文档结束**
