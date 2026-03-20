# LlamaIndex ReAct 学习报告

**文档版本**: v1.0
**创建时间**: 2026-03-20 05:35:00
**编写人**: 小沈
**研究资料数量**: 30+ 篇
**存放位置**: D:\OmniAgentAs-desk\doc-ReAct重构\

---

## 1 LlamaIndex 概述

### 1.1 框架简介

| 属性 | 说明 |
|------|------|
| **名称** | LlamaIndex |
| **语言** | Python |
| **Stars** | 30K+ (GitHub) |
| **定位** | 专注 RAG 的 LLM 数据框架 |
| **特点** | 数据索引能力强，也支持 ReAct Agent |

### 1.2 ReAct 支持

LlamaIndex 提供了两种 ReAct 实现方式：
1. **ReActAgent**: 直接使用 ReAct Agent
2. **Workflow**: 基于事件驱动的 ReAct 实现（更灵活）

---

## 2 ReActAgent 实现

### 2.1 基本用法

```python
from llama_index.core.agent import ReActAgent
from llama_index.llms.openai import OpenAI
from llama_index.core.tools import FunctionTool

# 定义工具
def add(x: int, y: int) -> int:
    """Useful function to add two numbers."""
    return x + y

def multiply(x: int, y: int) -> int:
    """Useful function to multiply two numbers."""
    return x * y

tools = [
    FunctionTool.from_defaults(add),
    FunctionTool.from_defaults(multiply),
]

# 创建 Agent
agent = ReActAgent.from_tools(
    tools=tools,
    llm=OpenAI(model="gpt-4"),
    verbose=True
)

# 执行
response = agent.chat("What is (2123 + 2321) * 312?")
print(response)
```

### 2.2 ReActAgent 源码结构

```
llama_index.core.agent.react/
├── __init__.py
├── agent.py           # ReActAgent 主类
├── formatter.py       # Prompt 格式化
├── output_parser.py   # 输出解析器
└── types.py           # 类型定义
```

---

## 3 核心类型定义

### 3.1 ActionReasoningStep

**来源**: `llama_index.core.agent.react.types`

**定义**: 代表一个思考 + 行动的步骤

```python
from llama_index.core.agent.react.types import ActionReasoningStep

@dataclass
class ActionReasoningStep(ReasoningStep):
    """代表 Thought + Action 的组合。"""
    
    thought: str  # 思考内容
    action: str   # 工具名称
    action_input: dict  # 工具参数
    
    def get_content(self) -> str:
        return f"Thought: {self.thought}\nAction: {self.action}\nAction Input: {self.action_input}"
```

### 3.2 ObservationReasoningStep

**来源**: `llama_index.core.agent.react.types`

**定义**: 代表观察结果

```python
from llama_index.core.agent.react.types import ObservationReasoningStep

@dataclass
class ObservationReasoningStep(ReasoningStep):
    """代表 Observation。"""
    
    observation: str  # 观察结果
    
    def get_content(self) -> str:
        return f"Observation: {self.observation}"
```

### 3.3 ReasoningStep 基类

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class ReasoningStep(ABC):
    """推理步骤基类。"""
    
    @abstractmethod
    def get_content(self) -> str:
        """获取步骤内容的字符串表示。"""
        pass
    
    @property
    @abstractmethod
    def is_done(self) -> bool:
        """是否完成。"""
        pass
```

---

## 4 ReAct Output Parser

### 4.1 源码实现

**来源**: `llama_index.core.agent.react.output_parser`

```python
from llama_index.core.agent.react.types import (
    ActionReasoningStep,
    ObservationReasoningStep,
    ResponseReasoningStep,
)
from llama_index.core.agent.react.output_parser import ReActOutputParser

class ReActOutputParser:
    """解析 ReAct 风格的 LLM 输出。"""
    
    def parse(self, output: str) -> ReasoningStep:
        """解析 LLM 输出。"""
        
        # 移除前缀
        output = output.strip()
        
        # 检查是否包含 Final Answer
        if "Final Answer:" in output:
            answer = output.split("Final Answer:")[-1].strip()
            return ResponseReasoningStep(
                reasoning=output,
                response=answer
            )
        
        # 解析 Thought + Action
        thought_match = re.search(r"Thought:\s*(.*?)(?=\n|$)", output, re.DOTALL)
        action_match = re.search(r"Action:\s*(\w+)", output)
        action_input_match = re.search(
            r"Action Input:\s*(.*?)(?=\n(?:Thought|Action|Observation|Final Answer)|$)",
            output,
            re.DOTALL
        )
        
        if thought_match and action_match:
            thought = thought_match.group(1).strip()
            action = action_match.group(1).strip()
            
            action_input_str = ""
            if action_input_match:
                action_input_str = action_input_match.group(1).strip()
            
            # 尝试解析 JSON
            try:
                action_input = json.loads(action_input_str)
            except:
                action_input = {"input": action_input_str}
            
            return ActionReasoningStep(
                thought=thought,
                action=action,
                action_input=action_input
            )
        
        # 如果无法解析，返回 Observation
        return ObservationReasoningStep(observation=output)
```

---

## 5 ReActChatFormatter

### 5.1 功能说明

格式化 ReAct Prompt

### 5.2 源码实现

```python
from llama_index.core.agent.react.formatter import ReActChatFormatter

DEFAULT_SYSTEM_PROMPT = """\
You are a helpful assistant.
You have access to the following tools:
{tools}

To use a tool, please respond with the following format:
```
Thought: your thought
Action: tool_name
Action Input: {{
  "input": "input value"
}}
```

If you have completed the task, please respond with the following format:
```
Thought: I have completed the task
Final Answer: your final answer
```

Begin!
"""

class ReActChatFormatter:
    """格式化 ReAct 对话。"""
    
    def __init__(
        self,
        context: str = "",
        system_prompt: Optional[str] = None,
    ):
        self.context = context
        self.system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT
    
    def format(
        self,
        tools: Sequence[BaseTool],
        chat_history: Sequence[ChatMessage],
        current_reasoning: Optional[List[ReasoningStep]] = None,
    ) -> List[ChatMessage]:
        """格式化消息列表。"""
        tools_str = "\n".join([
            f"- {tool.metadata.name}: {tool.metadata.description}"
            for tool in tools
        ])
        
        messages = []
        
        # System message
        system = self.system_prompt.format(tools=tools_str)
        if self.context:
            system += f"\n\nContext: {self.context}"
        messages.append(ChatMessage(role="system", content=system))
        
        # Chat history
        for msg in chat_history:
            messages.append(msg)
        
        # Current reasoning (intermediate steps)
        if current_reasoning:
            reasoning_text = "\n".join([
                step.get_content() for step in current_reasoning
            ])
            # 添加 Observation 提示 LLM
            if current_reasoning:
                last_step = current_reasoning[-1]
                if isinstance(last_step, ActionReasoningStep):
                    reasoning_text += "\nObservation: "
        
        return messages
```

---

## 6 Workflow 实现（推荐方式）

### 6.1 事件驱动架构

LlamaIndex 推荐使用 Workflow 来实现 ReAct Agent，这是一种更灵活的事件驱动方式。

### 6.2 事件定义

```python
from llama_index.core.workflow import Event

class PrepEvent(Event):
    """准备事件。"""
    pass

class InputEvent(Event):
    """LLM 输入事件。"""
    input: list[ChatMessage]

class StreamEvent(Event):
    """流式响应事件。"""
    delta: str

class ToolCallEvent(Event):
    """工具调用事件。"""
    tool_calls: list[ToolSelection]

class FunctionOutputEvent(Event):
    """函数输出事件。"""
    output: ToolOutput
```

### 6.3 Workflow 实现

```python
from typing import Any, List
from llama_index.core.agent.react import ReActChatFormatter, ReActOutputParser
from llama_index.core.agent.react.types import (
    ActionReasoningStep,
    ObservationReasoningStep,
)
from llama_index.core.llms import ChatMessage
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.core.tools import ToolSelection
from llama_index.core.workflow import (
    Context,
    Workflow,
    StartEvent,
    StopEvent,
    step,
)

class ReActAgentWorkflow(Workflow):
    """基于 Workflow 的 ReAct Agent。"""
    
    def __init__(
        self,
        *args: Any,
        llm: LLM | None = None,
        tools: list[BaseTool] | None = None,
        extra_context: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.tools = tools or []
        self.llm = llm or OpenAI()
        self.formatter = ReActChatFormatter.from_defaults(
            context=extra_context or ""
        )
        self.output_parser = ReActOutputParser()

    @step
    async def new_user_msg(self, ctx: Context, ev: StartEvent) -> PrepEvent:
        """处理新用户消息。"""
        # 初始化 memory
        memory = await ctx.store.get("memory", default=None)
        if not memory:
            memory = ChatMemoryBuffer.from_defaults(llm=self.llm)
        
        # 添加用户消息
        user_msg = ChatMessage(role="user", content=ev.input)
        memory.put(user_msg)
        
        # 清除当前推理
        await ctx.store.set("current_reasoning", [])
        await ctx.store.set("memory", memory)
        
        return PrepEvent()

    @step
    async def prepare_chat_history(self, ctx: Context, ev: PrepEvent) -> InputEvent:
        """准备聊天历史。"""
        memory = await ctx.store.get("memory")
        chat_history = memory.get()
        current_reasoning = await ctx.store.get("current_reasoning", default=[])
        
        # 格式化 prompt
        llm_input = self.formatter.format(
            self.tools, chat_history, current_reasoning=current_reasoning
        )
        
        return InputEvent(input=llm_input)

    @step
    async def handle_llm_input(
        self, ctx: Context, ev: InputEvent
    ) -> ToolCallEvent | StopEvent:
        """处理 LLM 输入。"""
        chat_history = ev.input
        current_reasoning = await ctx.store.get("current_reasoning", default=[])
        memory = await ctx.store.get("memory")
        
        # 调用 LLM
        response = await self.llm.achat(chat_history)
        
        # 解析输出
        try:
            reasoning_step = self.output_parser.parse(response.message.content)
            current_reasoning.append(reasoning_step)
            
            if reasoning_step.is_done:
                # 完成
                memory.put(ChatMessage(
                    role="assistant",
                    content=reasoning_step.response
                ))
                await ctx.store.set("memory", memory)
                return StopEvent(result={"response": reasoning_step.response})
            
            elif isinstance(reasoning_step, ActionReasoningStep):
                # 需要调用工具
                return ToolCallEvent(
                    tool_calls=[
                        ToolSelection(
                            tool_id="fake",
                            tool_name=reasoning_step.action,
                            tool_kwargs=reasoning_step.action_input,
                        )
                    ]
                )
        
        except Exception as e:
            # 解析失败，记录错误
            current_reasoning.append(
                ObservationReasoningStep(
                    observation=f"Error: {str(e)}"
                )
            )
        
        # 继续循环
        return PrepEvent()

    @step
    async def handle_tool_calls(self, ctx: Context, ev: ToolCallEvent) -> PrepEvent:
        """处理工具调用。"""
        tool_calls = ev.tool_calls
        tools_by_name = {tool.metadata.name: tool for tool in self.tools}
        current_reasoning = await ctx.store.get("current_reasoning", default=[])
        
        # 执行工具
        for tool_call in tool_calls:
            tool = tools_by_name.get(tool_call.tool_name)
            if not tool:
                current_reasoning.append(
                    ObservationReasoningStep(
                        observation=f"Tool {tool_call.tool_name} not found"
                    )
                )
                continue
            
            try:
                # 执行工具
                tool_output = tool(**tool_call.tool_kwargs)
                current_reasoning.append(
                    ObservationReasoningStep(observation=str(tool_output))
                )
            except Exception as e:
                current_reasoning.append(
                    ObservationReasoningStep(
                        observation=f"Error: {str(e)}"
                    )
                )
        
        await ctx.store.set("current_reasoning", current_reasoning)
        return PrepEvent()
```

---

## 7 完整使用示例

### 7.1 基本用法

```python
from llama_index.core.agent import ReActAgent
from llama_index.llms.openai import OpenAI
from llama_index.core.tools import FunctionTool

# 定义工具
def add(x: int, y: int) -> int:
    """Add two numbers."""
    return x + y

def multiply(x: int, y: int) -> int:
    """Multiply two numbers."""
    return x * y

tools = [
    FunctionTool.from_defaults(add),
    FunctionTool.from_defaults(multiply),
]

# 创建 Agent
agent = ReActAgent.from_tools(
    tools=tools,
    llm=OpenAI(model="gpt-4"),
    verbose=True
)

# 执行
response = agent.chat("What is 2 + 2?")
print(response)
```

### 7.2 Workflow 用法

```python
from llama_index.core.agent import ReActAgentWorkflow
from llama_index.llms.openai import OpenAI

# 创建 Workflow
agent = ReActAgentWorkflow(
    llm=OpenAI(model="gpt-4"),
    tools=tools,
    timeout=120,
    verbose=True
)

# 执行
ret = await agent.run(input="What is (2123 + 2321) * 312?")
print(ret["response"])
```

---

## 8 LlamaIndex ReAct 的特点总结

### 8.1 优点

| 优点 | 说明 |
|------|------|
| **Workflow 灵活** | 事件驱动，易于扩展 |
| **类型安全** | 完整的类型注解 |
| **RAG 集成** | 与数据索引无缝集成 |
| **异步支持** | 原生异步支持 |

### 8.2 缺点

| 缺点 | 说明 |
|------|------|
| **文档分散** | ReAct 相关文档不够集中 |
| **学习曲线** | Workflow 概念需要时间理解 |

### 8.3 对 omniAgent 的参考价值

| 参考点 | 说明 |
|------|------|
| **ActionReasoningStep** | `thought`, `action`, `action_input` 三字段 |
| **ObservationReasoningStep** | 纯 `observation` 字段 |
| **Workflow 模式** | 事件驱动的 Agent 实现 |
| **格式化工具描述** | 标准化的工具描述格式 |

---

## 9 关键源码链接

| 文件 | 说明 |
|------|------|
| [ReAct Agent 源码](https://github.com/run-llama/llama_index/blob/main/llama-index-core/llama_index/core/agent/react/agent.py) | ReActAgent 主类 |
| [Output Parser](https://github.com/run-llama/llama_index/blob/main/llama-index-core/llama_index/core/agent/react/output_parser.py) | 输出解析器 |
| [Workflow 教程](https://docs.llamaindex.ai/en/stable/examples/workflow/react_agent/) | Workflow 实现 |
| [ReAct Agent 教程](https://docs.llamaindex.ai/en/stable/examples/agent/react_agent/) | 基本用法 |

---

## 10 版本记录

| 版本 | 时间 | 更新内容 | 作者 |
|------|------|---------|------|
| v1.0 | 2026-03-20 05:35:00 | 初始版本，包含完整 LlamaIndex ReAct 学习报告 | 小沈 |

---

**文档结束**
