# LlamaIndex ReAct 学习报告

**文档版本**: v2.1
**创建时间**: 2026-03-20 05:35:00
**更新时间**: 2026-03-20 13:50:00
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

### 3.1 BaseReasoningStep（实际源码）

**来源**: `llama_index.core.agent.react.types`

**定义**: 推理步骤基类（Pydantic BaseModel）

```python
class BaseReasoningStep(BaseModel):
    """Reasoning step."""

    @abstractmethod
    def get_content(self) -> str:
        """Get content."""

    @property
    @abstractmethod
    def is_done(self) -> bool:
        """Is the reasoning step the last one."""
```

### 3.2 ActionReasoningStep（实际源码）

**来源**: `llama_index.core.agent.react.types`

**定义**: Thought + Action 的组合

```python
class ActionReasoningStep(BaseReasoningStep):
    """Action Reasoning step."""

    thought: str
    action: str
    action_input: Dict

    def get_content(self) -> str:
        return (
            f"Thought: {self.thought}\nAction: {self.action}\n"
            f"Action Input: {self.action_input}"
        )

    @property
    def is_done(self) -> bool:
        return False
```

### 3.3 ObservationReasoningStep（实际源码）

**来源**: `llama_index.core.agent.react.types`

**定义**: 观察结果

```python
class ObservationReasoningStep(BaseReasoningStep):
    """Observation reasoning step."""

    observation: str
    return_direct: bool = False  # 【新增】直接返回标志

    def get_content(self) -> str:
        return f"Observation: {self.observation}"

    @property
    def is_done(self) -> bool:
        return self.return_direct  # 如果 return_direct=True，直接结束
```

### 3.4 ResponseReasoningStep（实际源码）

**来源**: `llama_index.core.agent.react.types`

**定义**: 最终回答步骤

```python
class ResponseReasoningStep(BaseReasoningStep):
    """Response reasoning step."""

    thought: str
    response: str
    is_streaming: bool = False  # 【新增】流式输出标志

    def get_content(self) -> str:
        if self.is_streaming:
            return f"Thought: {self.thought}\nAnswer (Starts With): {self.response} ..."
        else:
            return f"Thought: {self.thought}\nAnswer: {self.response}"

    @property
    def is_done(self) -> bool:
        return True
```

### 3.5 类型对比表

| 类型 | 字段 | is_done | 说明 |
|------|------|---------|------|
| `BaseReasoningStep` | 无 | 抽象 | 基类 |
| `ActionReasoningStep` | `thought`, `action`, `action_input` | False | 需要调用工具 |
| `ObservationReasoningStep` | `observation`, `return_direct` | return_direct | 工具执行结果 |
| `ResponseReasoningStep` | `thought`, `response`, `is_streaming` | True | 最终回答 |

---

## 4 ReAct Output Parser（实际源码）

### 4.1 源码实现

**来源**: `llama_index.core.agent.react.output_parser`

```python
import re
from typing import Tuple
from llama_index.core.agent.react.types import (
    ActionReasoningStep,
    BaseReasoningStep,
    ResponseReasoningStep,
)
from llama_index.core.output_parsers.utils import extract_json_str


def extract_tool_use(input_text: str) -> Tuple[str, str, str]:
    """从 LLM 输出提取工具调用信息"""
    pattern = r"(?:\s*Thought: (.*?)|(.+))\n+Action: ([^\n\(\) ]+).*?\n+Action Input: .*?(\{.*\})"
    
    match = re.search(pattern, input_text, re.DOTALL)
    if not match:
        raise ValueError(f"Could not extract tool use from input text: {input_text}")
    
    thought = (match.group(1) or match.group(2)).strip()
    action = match.group(3).strip()
    action_input = match.group(4).strip()
    return thought, action, action_input


def action_input_parser(json_str: str) -> dict:
    """降级 JSON 解析：将单引号替换为双引号"""
    processed_string = re.sub(r"(?<!\w)\'|\'(?!\w)", '"', json_str)
    pattern = r'"(\w+)":\s*"([^"]*)"'
    matches = re.findall(pattern, processed_string)
    return dict(matches)


def extract_final_response(input_text: str) -> Tuple[str, str]:
    """从 LLM 输出提取最终回答"""
    pattern = r"\s*Thought:(.*?)Answer:(.*?)(?:$)"
    match = re.search(pattern, input_text, re.DOTALL)
    if not match:
        raise ValueError(f"Could not extract final answer from input text: {input_text}")
    thought = match.group(1).strip()
    answer = match.group(2).strip()
    return thought, answer


class ReActOutputParser(BaseOutputParser):
    """ReAct Output parser."""

    def parse(self, output: str, is_streaming: bool = False) -> BaseReasoningStep:
        """
        Parse output from ReAct agent.

        格式1（需要工具）:
            Thought: <thought>
            Action: <action>
            Action Input: <action_input>

        格式2（最终回答）:
            Thought: <thought>
            Answer: <answer>
        """
        thought_match = re.search(r"Thought:", output, re.MULTILINE)
        action_match = re.search(r"Action:", output, re.MULTILINE)
        answer_match = re.search(r"Answer:", output, re.MULTILINE)

        thought_idx = thought_match.start() if thought_match else None
        action_idx = action_match.start() if action_match else None
        answer_idx = answer_match.start() if answer_match else None

        # 都没有匹配 → 直接返回文本作为回答
        if thought_idx is None and action_idx is None and answer_idx is None:
            return ResponseReasoningStep(
                thought="(Implicit) I can answer without any more tools!",
                response=output,
                is_streaming=is_streaming,
            )

        # Action 优先于 Answer
        if (action_idx is not None and answer_idx is not None and action_idx < answer_idx):
            return parse_action_reasoning_step(output)
        elif action_idx is not None and answer_idx is None:
            return parse_action_reasoning_step(output)

        if answer_idx is not None:
            thought, answer = extract_final_response(output)
            return ResponseReasoningStep(
                thought=thought, response=answer, is_streaming=is_streaming
            )

        raise ValueError(f"Could not parse output: {output}")
```

### 4.2 正则表达式详解

**工具调用正则**: `r"(?:\s*Thought: (.*?)|(.+))\n+Action: ([^\n\(\) ]+).*?\n+Action Input: .*?(\{.*\})"`

| 部分 | 含义 |
|------|------|
| `(?:\s*Thought: (.*?)|(.+))` | Thought 内容（可选前缀） |
| `\n+Action: ([^\n\(\) ]+)` | Action 工具名称（不允许空格和括号） |
| `.*?\n+Action Input: ` | Action Input 前缀 |
| `.*?(\{.*\})` | JSON 格式的参数 |

**最终回答正则**: `r"\s*Thought:(.*?)Answer:(.*?)(?:$)"`

### 4.3 JSON 解析策略

```
LLM 输出 Action Input
        │
        ├── dirtyjson.loads(json_str) ── 成功 → 返回 dict
        │
        └── 失败 → action_input_parser(json_str)
                ├── 将单引号替换为双引号
                └── 正则提取 key: value
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

## 9 Thought 类型设计深度分析

### 9.1 标准 ReAct 的 Thought 设计

**原始 ReAct 论文（Yao et al. 2022）**：

```
Thought → Action → Observation → Thought → Action → Observation → ... → Thought → Final Answer
```

**核心特点**：
- Thought 是**独立的推理步骤**
- 每一步都有明确的类型标记
- Thought 不和 Action 绑定

**原论文流程图**：
```
用户问题
    │
    ├── Thought1: "我需要搜索天气信息"
    ├── Action1: search("天气")
    ├── Observation1: "今天晴天 25°C"
    │
    ├── Thought2: "温度适中，不需要带外套"
    ├── Action2: search("外套")
    ├── Observation2: "不需要"
    │
    └── Thought3: "我已经知道了"
        Final Answer: "今天天气很好，不需要带外套"
```

### 9.2 LlamaIndex 的 Thought 设计

**LlamaIndex 的做法**：把 Thought 嵌入到 Action 或 Response 中，没有独立的 Thought 类型。

```
LlamaIndex:
├── ActionReasoningStep = thought + action + action_input   ← Thought 在这里
├── ObservationReasoningStep = observation                   ← 没有 Thought
└── ResponseReasoningStep = thought + response              ← Thought 在这里
```

**实际流程**：
```
current_reasoning = [
    ActionReasoningStep(
        thought="我需要搜索天气",          ← Thought 被塞进了 Action 里
        action="search",
        action_input={"query": "天气"}
    ),
    ObservationReasoningStep(
        observation="今天晴天 25°C"        ← 没有 Thought
    ),
    ResponseReasoningStep(                  ← 没有独立的 Thought 步骤
        thought="天气很好，不需要外套",
        response="今天天气很好，不需要带外套"
    )
]
```

### 9.3 LangChain 的 Thought 设计

**LangChain 的做法**：Thought 作为 LLM 输出的一部分，保存在 `AgentAction.log` 中。

```
LangChain:
├── AgentAction.log = "Thought: I need to search\nAction: search\nAction Input: {...}"
│   │                              ↑
│   └── Thought 在 log 字段里（不单独提取）
│
└── AgentFinish.log = "Thought: I now know\nFinal Answer: ..."
    │                              ↑
    └── Thought 在 log 字段里（不单独提取）
```

**实际流程**：
```
intermediate_steps = [
    (AgentAction(tool="search", tool_input="天气", 
                 log="Thought: I need to search\nAction: search\nAction Input: {...}"),
     "今天晴天 25°C"),
    (AgentAction(tool="search", tool_input="外套", 
                 log="Thought: Based on weather...\nAction: search\nAction Input: {...}"),
     "不需要"),
]
```

### 9.4 对比表

| 对比项 | 标准 ReAct | LlamaIndex | LangChain |
|--------|-----------|-----------|-----------|
| **Thought 类型** | 独立类型 | 无（嵌入字段） | 无（在 log 里） |
| **Action 类型** | 独立类型 | ActionReasoningStep | AgentAction |
| **Observation 类型** | 独立类型 | ObservationReasoningStep | 无（直接存字符串） |
| **Final 类型** | 独立类型 | ResponseReasoningStep | AgentFinish |
| **类型数量** | 4 个 | 3 个 | 2 个 |
| **Thought 提取** | 直接获取 | 从字段提取 | 从 log 解析 |
| **类型判断** | 简单（看 type） | 需看类名 | 需看类型 |

### 9.5 为什么 Thought 独立更好？

**场景：追踪推理过程**

```
// Thought 独立（标准 ReAct）
steps = [
    {type: "thought", content: "我需要搜索天气"},      ← 可以直接获取所有思考
    {type: "action_tool", tool: "search", input: "天气"},
    {type: "observation", content: "晴天 25°C"},
    {type: "thought", content: "天气很好，不需要外套"},  ← 独立的思考
    {type: "final", content: "不需要带外套"},
]

// Thought 嵌入（LlamaIndex）
steps = [
    ActionReasoningStep(thought="我需要搜索天气", action="search", ...),  ← Thought 混在一起
    ObservationReasoningStep(observation="晴天 25°C"),                    ← 没有 Thought
    ResponseReasoningStep(thought="天气很好", response="不需要外套"),     ← Thought 混在一起
]

// 提取所有 Thought：
// 方案A（独立）: [s for s in steps if s.type == "thought"]
// 方案B（嵌入）: [s.thought for s in steps if hasattr(s, 'thought')]  ← 更复杂
```

**场景：前端渲染**

```
// 独立 Thought → 前端可以直接按 type 渲染
if step.type == "thought":
    render("💭 " + step.content)      // 思考气泡
elif step.type == "action_tool":
    render("🔧 " + step.tool_name)    // 工具调用卡片
elif step.type == "observation":
    render("👁 " + step.content)      // 观察结果

// 嵌入 Thought → 需要额外判断
if isinstance(step, ActionReasoningStep):
    render("💭 " + step.thought)      // 先渲染 Thought
    render("🔧 " + step.action)       // 再渲染 Action
elif isinstance(step, ObservationReasoningStep):
    render("👁 " + step.observation)  // 没有 Thought
```

### 9.6 对 omniAgent 的建议

**建议使用独立 Thought 类型**：

| 方案 | 对 omniAgent 的影响 |
|------|-------------------|
| **独立 Thought** | 与现有 `process_thought.py` 一致，前端渲染简单，类型判断直接 |
| **嵌入 Thought** | 需要修改现有 `process_thought.py`，前端需要额外判断 |

**我们的类型设计建议**：

```
我们的 ReasoningStep 类型：
├── thought     → 独立类型（沿用现有 process_thought.py）
├── action_tool → 独立类型
├── observation → 独立类型
├── final       → 独立类型
├── error       → 独立类型
├── incident    → 独立类型（paused/resumed/interrupted/retrying）
└── start       → 独立类型（我们的扩展）
```

---

## 10 关键源码链接

| 文件 | 说明 |
|------|------|
| [ReAct Agent 源码](https://github.com/run-llama/llama_index/blob/main/llama-index-core/llama_index/core/agent/react/agent.py) | ReActAgent 主类 |
| [Output Parser](https://github.com/run-llama/llama_index/blob/main/llama-index-core/llama_index/core/agent/react/output_parser.py) | 输出解析器 |
| [Workflow 教程](https://docs.llamaindex.ai/en/stable/examples/workflow/react_agent/) | Workflow 实现 |
| [ReAct Agent 教程](https://docs.llamaindex.ai/en/stable/examples/agent/react_agent/) | 基本用法 |

---

## 11 版本记录

| 版本 | 时间 | 更新内容 | 作者 |
|------|------|---------|------|
| v1.0 | 2026-03-20 05:35:00 | 初始版本 | 小沈 |
| v2.0 | 2026-03-20 13:45:00 | **深度修正**：基于实际源码修正 ReasoningStep 为 Pydantic BaseModel（非 dataclass）；修正 Output Parser 实际正则表达式（支持 Thought 前缀可选、Action Input JSON 提取）；新增 ResponseReasoningStep（含 is_streaming）、ObservationReasoningStep（含 return_direct）；新增 JSON 解析降级策略（dirtyjson → action_input_parser） | 小沈 |
| v2.1 | 2026-03-20 13:50:00 | **新增第9章：Thought 类型设计深度分析**：标准 ReAct vs LlamaIndex vs LangChain 三种 Thought 设计对比；分析 Thought 独立 vs 嵌入的优缺点；对 omniAgent 的建议（使用独立 Thought 类型） | 小沈 |

---

**文档结束**
