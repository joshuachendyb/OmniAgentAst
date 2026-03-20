# ReAct Loop 字段级详细设计文档

**文档版本**: v1.0
**创建时间**: 2026-03-20 05:07:12
**编写人**: 小沈
**存放位置**: D:\OmniAgentAs-desk\doc-ReAct重构\

---

## 1 背景与目标

### 1.1 背景

当前实现中存在不符合标准 ReAct 的错误设计：

- 使用 `action1`/`action2`/`action3` 等多 action 类型
- 使用 `observation1`/`observation2` 等多 observation 类型
- 实现逻辑：action1 → action2 → action3 → observation1（错误）

### 1.2 目标

- 重构为标准 ReAct Loop
- 每个 type（start/thought/action_tool 等）独立文件
- 符合 LangChain AgentAction/AgentFinish 字段规范
- 删除所有错误的多 action/observation 类型

---

## 2 标准 ReAct Loop 的 type 定义

根据 LangChain ReAct 实现，每个 LLM 响应只会产生两种结果：

| type | 触发条件 | 触发后行为 |
|------|---------|-----------|
| **thought** | LLM 输出需要继续推理 | 追加 thought，进入下一轮 LLM |
| **action_tool** | LLM 输出调用工具 | 执行工具，将结果转为 **observation**，进入下一轮 LLM |
| **observation** | 工具执行结果自动产生 | **不触发 LLM**，追加到 steps 后直接进入下一轮 LLM |

> **注意**：ReAct 标准流程中 **没有 action1/action2/action3** 这种多 action 模式，所有 action 都是 `action(工具名, 参数)` 格式，由 LLM 一次输出一个工具调用。

---

## 3 字段映射：LangChain → omniAgent

| LangChain 概念 | omniAgent type | omniAgent 字段 |
|---------------|----------------|----------------|
| `AgentAction.tool` | action_tool | `action_tool.name` |
| `AgentAction.tool_input` | action_tool | `action_tool.params` |
| `AgentAction.log` | thought | `thought.content` |
| `AgentFinish.return_values.output` | final | `final.content` |
| `observation` (str) | observation | `observation.content` |
| `intermediate_steps` | (内部状态) | `executionSteps[]` |
| `format_log_to_str()` | (内部逻辑) | 用于渲染展示 |

---

## 4 各 type 字段定义

### 4.1 thought

**来源**：LLM 输出中 `Thought:` 部分（STOP SEQUENCE 截断后）
**触发**：每轮 LLM 输出以 `Thought:` 开头时

| 字段 | 类型 | 说明 |
|------|------|------|
| `type` | `"thought"` | 固定值 |
| `content` | `string` | LLM 的思考内容（不含 "Thought:" 前缀） |
| `timestamp` | `number` | 客户端生成的时间戳（毫秒） |

**生成时机**：SSE 解析时，从 LLM 文本中提取 `Thought:` 后内容

### 4.2 action_tool

**来源**：LLM 输出中 `Action:` 部分（STOP SEQUENCE 截断后）
**触发**：每轮 LLM 输出包含 `Action:` 时
**说明**：一次 LLM 输出只产生一个 action_tool（标准 ReAct 不支持多 action）

| 字段 | 类型 | 说明 |
|------|------|------|
| `type` | `"action_tool"` | 固定值 |
| `name` | `string` | 工具名称（来自 LLM 的 Action: 后第一个词） |
| `params` | `Record<string, any>` | 工具参数（来自 Action: 后 JSON 或键值对） |
| `timestamp` | `number` | 客户端生成的时间戳（毫秒） |

**生成时机**：SSE 解析时，解析 `Action: tool_name` + `Action Input: {...}` 格式

### 4.3 observation

**来源**：工具执行结果
**触发**：action_tool 执行完成后自动产生
**特点**：**不触发 LLM**，追加后直接进入下一轮 LLM

| 字段 | 类型 | 说明 |
|------|------|------|
| `type` | `"observation"` | 固定值 |
| `content` | `string` | 工具执行结果的文本描述 |
| `timestamp` | `number` | 客户端生成的时间戳（毫秒） |

**生成时机**：工具执行完成后，后端将结果转为文本，追加为 observation

### 4.4 final

**来源**：LLM 输出中 `Final Answer:` 部分
**触发**：LLM 认为任务完成时
**说明**：ReAct 退出点，进入 final 后 Loop 结束

| 字段 | 类型 | 说明 |
|------|------|------|
| `type` | `"final"` | 固定值 |
| `content` | `string` | LLM 的最终回答 |
| `timestamp` | `number` | 客户端生成的时间戳（毫秒） |

**生成时机**：SSE 解析时，提取 `Final Answer:` 后内容，Loop 结束

### 4.5 chunk（保留）

| 字段 | 类型 | 说明 |
|------|------|------|
| `type` | `"chunk"` | 固定值 |
| `content` | `string` | 流式输出的中间文本片段 |

**说明**：仅用于前端渲染，字段构成与现有实现一致

---

## 5 错误逻辑：action1-action2-observation1 模式

### 5.1 问题描述

**当前实现中存在** `action1`/`action2`/`action3`/`observation1` 类型，这是 **不符合标准 ReAct 的错误设计**

### 5.2 标准 ReAct 要求

- 一次 LLM 输出只能产生 **一个** action
- 工具执行结果统一为 `observation`
- **不存在** `action1`/`action2`/`observation1` 等类型

### 5.3 正确做法

- 删除所有 `action1`/`action2`/`action3`/`observation1` 类型
- 统一使用 `action_tool` + `observation` 模式

---

## 6 内部状态管理

### 6.1 intermediate_steps（内部数组）

```python
type IntermediateStep = [AgentAction, string]; // [action_tool, observation]

# 等价于 omniAgent 的 executionSteps 中：
# [action_tool 块, observation 块] 的配对关系
```

### 6.2 scratchpad（内部变量）

**用途**：用于渲染展示，记录完整的思考过程

```python
# LangChain 实现：format_log_to_str(intermediate_steps)
# 输出格式：
"""
Thought: 我需要先读取文件内容
Action: read_file
Action Input: {"path": "/tmp/test.txt"}
Observation: 文件内容是 "Hello World"
Thought: 文件已读取，现在我需要处理内容
Action: process_text
Action Input: {"text": "Hello World", "uppercase": true}
Observation: 处理结果是 "HELLO WORLD"
"""
```

---

## 7 实现方案：按 type 分文件架构

### 7.1 目录结构

```
backend/app/services/file_operations/
├── agent.py              # Agent 主循环（核心调度）
├── types/
│   ├── __init__.py
│   ├── base.py           # BaseStep 基类
│   ├── thought.py        # ThoughtStep
│   ├── action_tool.py    # ActionToolStep
│   ├── observation.py    # ObservationStep
│   ├── final.py          # FinalStep
│   └── chunk.py          # ChunkStep
├── parser/
│   ├── __init__.py
│   ├── base.py           # BaseParser 基类
│   ├── react_parser.py   # ReAct 输出解析器
│   └── output_parser.py  # LLM 输出解析（Thought/Action/Action Input/Final Answer）
├── executor/
│   ├── __init__.py
│   ├── base.py           # BaseExecutor 基类
│   └── tool_executor.py # 工具执行器
└── utils/
    ├── __init__.py
    ├── format_scratchpad.py  # format_log_to_str 实现
    └── trim_steps.py         # trim_intermediate_steps 实现
```

### 7.2 各模块职责

#### 7.2.1 types/ - 类型定义

每个 type 对应一个数据类：

```python
# types/thought.py
from dataclasses import dataclass, field
from typing import Optional
import time

@dataclass
class ThoughtStep:
    type: str = "thought"
    content: str = ""
    timestamp: int = field(default_factory=lambda: int(time.time() * 1000))
    
    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "content": self.content,
            "timestamp": self.timestamp
        }

# types/action_tool.py
@dataclass
class ActionToolStep:
    type: str = "action_tool"
    name: str = ""
    params: dict = field(default_factory=dict)
    timestamp: int = field(default_factory=lambda: int(time.time() * 1000))
    
    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "name": self.name,
            "params": self.params,
            "timestamp": self.timestamp
        }

# types/observation.py
@dataclass
class ObservationStep:
    type: str = "observation"
    content: str = ""
    timestamp: int = field(default_factory=lambda: int(time.time() * 1000))
    
    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "content": self.content,
            "timestamp": self.timestamp
        }

# types/final.py
@dataclass
class FinalStep:
    type: str = "final"
    content: str = ""
    timestamp: int = field(default_factory=lambda: int(time.time() * 1000))
    
    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "content": self.content,
            "timestamp": self.timestamp
        }
```

#### 7.2.2 parser/output_parser.py - LLM 输出解析

**核心逻辑**：从 LLM 原始输出中解析出 Thought/Action/Final Answer

```python
# 解析模式（参考 LangChain）
import re

THOUGHT_PATTERN = r"Thought:\s*(.*?)(?=\n(?:Action|Observation|Final Answer|$))"
ACTION_PATTERN = r"Action:\s*(\w+)"
ACTION_INPUT_PATTERN = r"Action Input:\s*(.*?)(?=\n(?:Thought|Observation|Final Answer|$))"
FINAL_ANSWER_PATTERN = r"Final Answer:\s*(.*)"

class ReActOutputParser:
    """
    解析 LLM 的 ReAct 格式输出
    参考 LangChain ReAct Single Input Output Parser
    """
    
    def parse(self, text: str) -> dict:
        # 优先匹配 Final Answer
        final_match = re.search(FINAL_ANSWER_PATTERN, text, re.DOTALL)
        if final_match:
            return {
                "type": "final",
                "content": final_match.group(1).strip()
            }
        
        # 匹配 Thought
        thought_match = re.search(THOUGHT_PATTERN, text, re.DOTALL)
        if thought_match:
            return {
                "type": "thought",
                "content": thought_match.group(1).strip()
            }
        
        # 匹配 Action + Action Input
        action_match = re.search(ACTION_PATTERN, text)
        if action_match:
            action_input_match = re.search(ACTION_INPUT_PATTERN, text, re.DOTALL)
            params_str = action_input_match.group(1).strip() if action_input_match else "{}"
            
            # 解析 JSON 参数
            try:
                params = json.loads(params_str)
            except json.JSONDecodeError:
                params = {}
            
            return {
                "type": "action_tool",
                "name": action_match.group(1).strip(),
                "params": params
            }
        
        # 无法解析，返回为 thought
        return {
            "type": "thought",
            "content": text
        }
```

**Stop Sequence 配置**：
```python
# 告诉 LLM 在输出 Action Input 后停止，不要继续输出 Observation
stop_sequence = ["\nObservation:"]
```

#### 7.2.3 executor/tool_executor.py - 工具执行

```python
from typing import Any, Dict

class ToolExecutor:
    """
    工具执行器
    """
    
    def __init__(self):
        self.tools: Dict[str, Any] = {}
    
    def register_tool(self, name: str, tool: Any):
        """注册工具"""
        self.tools[name] = tool
    
    async def execute(self, name: str, params: dict) -> str:
        """
        执行工具，返回 observation 文本
        
        Args:
            name: 工具名称
            params: 工具参数
            
        Returns:
            工具执行结果的文本描述
        """
        if name not in self.tools:
            return f"Error: Tool '{name}' not found"
        
        tool = self.tools[name]
        
        try:
            result = await tool.execute(**params)
            return str(result)
        except Exception as e:
            return f"Error executing tool '{name}': {str(e)}"
```

#### 7.2.4 utils/format_scratchpad.py - 渲染格式化

```python
import json
from typing import List

def format_scratchpad(steps: List[dict]) -> str:
    """
    将 executionSteps 格式化为可读文本，用于渲染展示
    参考 LangChain format_log_to_str 实现
    
    Args:
        steps: executionSteps 列表
        
    Returns:
        格式化的文本，可用于渲染展示
    """
    lines = []
    
    for step in steps:
        step_type = step.get("type", "")
        
        if step_type == "thought":
            lines.append(f"Thought: {step.get('content', '')}")
        
        elif step_type == "action_tool":
            name = step.get("name", "")
            params = step.get("params", {})
            params_str = json.dumps(params, ensure_ascii=False)
            lines.append(f"Action: {name}")
            lines.append(f"Action Input: {params_str}")
        
        elif step_type == "observation":
            content = step.get("content", "")
            lines.append(f"Observation: {content}")
    
    return "\n".join(lines)
```

#### 7.2.5 utils/trim_steps.py - 上下文管理

```python
from typing import List

def trim_intermediate_steps(steps: List[dict], max_steps: int = 20) -> List[dict]:
    """
    防止 context overflow，保留最近 N 步
    参考 LangChain 实现
    
    Args:
        steps: executionSteps 列表
        max_steps: 最大保留的 (action_tool + observation) 对数量
        
    Returns:
        裁剪后的 steps 列表
    """
    # 每个 action_tool 后面会跟着一个 observation
    # 所以实际的 step 对数 = len(steps) / 2
    if len(steps) <= max_steps * 2:
        return steps
    
    # 保留最近的 (action_tool + observation) 对
    recent_steps = steps[-max_steps * 2:]
    return recent_steps
```

#### 7.2.6 agent.py - 核心循环

```python
import time
import json
from typing import List, Optional, Callable, Any

from .types.thought import ThoughtStep
from .types.action_tool import ActionToolStep
from .types.observation import ObservationStep
from .types.final import FinalStep
from .parser.output_parser import ReActOutputParser
from .executor.tool_executor import ToolExecutor
from .utils.format_scratchpad import format_scratchpad
from .utils.trim_steps import trim_intermediate_steps


class FileOperationAgent:
    """
    标准 ReAct Loop 实现
    参考 LangChain ReAct Agent
    """
    
    def __init__(self, llm: Any, tools: List[Any], callbacks: Optional[List] = None):
        self.llm = llm
        self.tools = {tool.name: tool for tool in tools}
        self.callbacks = callbacks or []
        self.parser = ReActOutputParser()
        self.executor = ToolExecutor()
        
        # 注册工具到执行器
        for tool in tools:
            self.executor.register_tool(tool.name, tool)
    
    async def run(self, task: str) -> List[dict]:
        """
        运行标准 ReAct Loop
        
        Args:
            task: 用户输入的任务
            
        Returns:
            executionSteps 列表
        """
        execution_steps: List[dict] = []
        
        # 1. 构建初始 prompt
        prompt = self._build_prompt(task, execution_steps)
        
        # 2. ReAct Loop
        max_iterations = 50
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            
            # 2.1 调用 LLM（使用 stop sequence 防止幻觉）
            response = await self.llm.invoke(
                prompt,
                stop=["\nObservation:"]
            )
            
            # 2.2 解析输出
            parsed = self.parser.parse(response.content)
            
            if parsed["type"] == "thought":
                # 追加 thought，继续循环
                thought = ThoughtStep(content=parsed["content"])
                execution_steps.append(thought.to_dict())
                
                # 更新 prompt
                prompt += f"\nThought: {parsed['content']}"
            
            elif parsed["type"] == "action_tool":
                # 追加 action_tool
                action = ActionToolStep(
                    name=parsed["name"],
                    params=parsed["params"]
                )
                execution_steps.append(action.to_dict())
                
                # 2.3 执行工具
                observation_content = await self.executor.execute(
                    parsed["name"],
                    parsed["params"]
                )
                
                # 2.4 追加 observation（不触发 LLM）
                observation = ObservationStep(content=observation_content)
                execution_steps.append(observation.to_dict())
                
                # 2.5 裁剪过长的中间步骤（防止 context overflow）
                execution_steps = trim_intermediate_steps(execution_steps)
                
                # 2.6 更新 prompt，继续循环
                params_str = json.dumps(parsed["params"], ensure_ascii=False)
                prompt += f"\nAction: {parsed['name']}\nAction Input: {params_str}\nObservation: {observation_content}"
            
            elif parsed["type"] == "final":
                # 追加 final，Loop 结束
                final = FinalStep(content=parsed["content"])
                execution_steps.append(final.to_dict())
                break
        
        return execution_steps
    
    def _build_prompt(self, task: str, steps: List[dict]) -> str:
        """
        构建 ReAct Prompt
        """
        # 基础 prompt 模板
        base_prompt = f"""你是一个智能助手，可以使用工具来完成任务。

## 可用工具

"""
        # 添加工具描述
        for name, tool in self.tools.items():
            base_prompt += f"- **{name}**: {getattr(tool, 'description', '')}\n"
        
        # 添加历史步骤（如果有）
        if steps:
            base_prompt += "\n## 历史操作\n"
            base_prompt += format_scratchpad(steps)
            base_prompt += "\n\n请继续思考并决定下一步操作："
        else:
            base_prompt += f"\n## 任务\n{task}\n\n请按以下格式输出你的思考和行动：\n\nThought: 你的思考\nAction: 工具名称\nAction Input: {{"参数名": "参数值"}}\n\n或者完成时输出：\n\nThought: 最终回答\nFinal Answer: 你的最终回答"
        
        return base_prompt
```

---

## 8 数据流图（完整）

```
用户输入: "帮我读取 /tmp/test.txt 并处理内容"
              │
              ▼
        ┌─────────────────┐
        │   build_prompt  │
        │  (ReAct Prompt) │
        └────────┬────────┘
                 │
                 ▼
        ┌─────────────────┐
        │    LLM 调用     │◄───────────────────────┐
        │  stop=["\\nOb"] │                        │
        └────────┬────────┘                        │
                 │                                  │
                 ▼                                  │
        ┌─────────────────┐                        │
        │  parse_output   │                        │
        └────────┬────────┘                        │
                 │                                  │
       ┌────────┼────────┐                        │
       │        │        │                        │
       ▼        ▼        ▼                        │
    thought  action    final                      │
       │        │        │                        │
       ▼        ▼        ▼                        │
    追加 step  解析      追加 final ──► Loop 结束  │
       │     name/                                   │
       │     params                                  │
       │        │                                    │
       │        ▼                                    │
       │  ┌─────────────┐                           │
       │  │execute_tool │                           │
       │  └──────┬──────┘                           │
       │         │                                   │
       │         ▼                                   │
       │  observation                                │
       │  (str result)                              │
       │         │                                   │
       │         ▼                                   │
       │  追加 observation                          │
       │  (不触发 LLM)                              │
       │         │                                   │
       └─────────┴──────────────────────────────────┘
                 │
                 ▼
         更新 prompt
         继续 Loop
```

---

## 9 当前项目实施进度对照

> **补充时间**: 2026-03-20 08:50:00
> **补充人**: 小健
> **说明**: 基于小健对文档的评审意见，补充当前项目实际实现与文档建议的对照

### 9.1 当前项目实际目录结构

根据实际代码实现，目录结构已更新：

```
backend/app/api/v1/
├── types/                          # ✅ 已按type分文件
│   ├── __init__.py
│   ├── process_start.py         ✅ 已完成 - 包含LLM意图分析
│   ├── process_thought.py      ✅ 已完成 - Thought2版本带LLM
│   ├── process_action.py        ✅ 已完成 - 工具执行
│   ├── process_observation.py   ✅ 已完成 - 带summary字段
│   ├── process_final.py         ✅ 已完成 - 最终回答
│   ├── process_error.py         ✅ 已完成 - 错误处理
│   └── process_incident.py      ✅ 已完成 - 状态事件
├── adapters/
│   ├── __init__.py
│   └── sse_adapter.py          ⏳ 待实现
└── chat_stream.py               主流程
```

### 9.2 当前项目实际字段定义

#### 9.2.1 thought（实际）

```python
{
    "type": "thought",
    "step": 1,                    # 步骤序号（项目扩展）
    "timestamp": 1710892800000,   # 时间戳（项目扩展）
    "content": "思考内容",        # 思考文本
    "reasoning": "推理过程",      # 推理内容（项目特有）
    "action_tool": "list_directory",  # LLM选择的工具（项目特有）
    "params": {"dir_path": "..."}     # LLM生成的参数（项目特有）
}
```

**与文档差异**：
- 多了 `step` - 步骤序号
- 多了 `reasoning` - 推理传导
- 多了 `action_tool`/`params` - LLM决策信息

#### 9.2.2 action_tool（实际）

```python
{
    "type": "action_tool",
    "step": 1,
    "timestamp": 1710892800000,
    "name": "list_directory",         # 工具名称
    "params": {"dir_path": "..."}    # 工具参数
}
```

#### 9.2.3 observation（实际）

```python
{
    "type": "observation",
    "step": 2,
    "timestamp": 1710892801000,
    "content": "原始结果...",        # 原始结果
    "summary": "摘要..."            # 长结果摘要（项目特有）
}
```

**与文档差异**：
- 多了 `step` - 步骤序号
- 多了 `summary` - 长结果摘要

### 9.3 额外的 type（项目特有）

| type | 说明 | 状态 |
|------|------|------|
| **start** | 任务开始 | ✅ 已实现 |
| **thought** | 思考过程（带LLM） | ✅ 已实现 |
| **action_tool** | 工具执行 | ✅ 已实现 |
| **observation** | 执行结果（带summary） | ✅ 已实现 |
| **final** | 最终回答 | ✅ 已实现 |
| **chunk** | 流式中间输出 | ✅ 已实现 |
| **error** | 错误信息 | ✅ 已实现 |
| **incident** | 状态事件 | ✅ 已实现 |

### 9.4 术语对照表

| 文档术语 | 项目实际 | 说明 |
|---------|---------|------|
| `action` | `action_tool` | 项目使用更明确的命名 |
| `action_input` | `params` | 项目使用 params 更直观 |
| 无 | `reasoning` | 项目特有的推理传导字段 |
| 无 | `summary` | observation长结果摘要 |
| 无 | `step` | 步骤序号，便于追踪 |
| 无 | `start/chunk/error/incident` | 项目扩展的type |

### 9.5 实施进度总览

| 模块 | 文档设计 | 当前实现 | 状态 | 文件 |
|------|---------|---------|------|------|
| start | 未设计 | ✅ 完成 | LLM意图分析 | `process_start.py` |
| thought | 基础版 | ✅ 完成 | Thought2版本 | `process_thought.py` |
| action_tool | 基础版 | ✅ 完成 | 标准实现 | `process_action.py` |
| observation | 基础版 | ✅ 完成 | 带summary | `process_observation.py` |
| final | 基础版 | ✅ 完成 | 标准实现 | `process_final.py` |
| chunk | 未设计 | ✅ 完成 | 流式中间 | `sse.ts` |
| error | 未设计 | ✅ 完成 | 错误码体系 | `process_error.py` |
| incident | 未设计 | ✅ 完成 | 状态事件 | `process_incident.py` |
| Output Parser | 正则解析 | ⏳ 待增强 | 当前较弱 | - |
| trim_steps | 文档设计 | ⏳ 待实现 | 上下文裁剪 | - |

---

## 10 与现有实现的对比

| 项目 | 旧实现（错误） | 新设计（正确） | 当前状态 |
|------|---------------|---------------|---------|
| action 类型 | action1/action2/action3 | 统一 action_tool | ✅ 已修正 |
| observation 类型 | observation1/observation2 | 统一 observation | ✅ 已修正 |
| 多 action 逻辑 | action1→action2→action3→obs1 | 不支持（错误模式） | ✅ 已修正 |
| 标准 ReAct | ❌ 不符合 | ✅ 符合 | ✅ 已符合 |
| 字段命名 | 业务命名 | LangChain 标准命名 | ✅ 已对齐 |
| 额外type | 无 | start/chunk/error/incident | ✅ 项目扩展 |

---

## 10 删除/重构清单

| 文件/代码 | 操作 |
|----------|------|
| `three_operation.py` | **删除**（包含错误逻辑） |
| `action1.py` | **删除** |
| `observation1.py` | **删除** |
| agent.py 中的 action1/action2 逻辑 | **重构**为 action_tool |
| agent.py 中的 obs1 逻辑 | **重构**为 observation |

---

## 11 验证标准

1. **LLM 输出解析**：能正确从 LLM 输出中提取 Thought/Action/Action Input/Final Answer
2. **工具执行**：action_tool 执行后能正确产生 observation
3. **Loop 退出**：收到 Final Answer 后 Loop 正确结束
4. **数据完整性**：每轮 executionSteps 包含正确的 type 序列
5. **上下文管理**：trim_steps 能正确裁剪过长的中间步骤

---

## 13 下一步行动项

| 优先级 | 建议项 | 当前状态 | 实施难度 |
|-------|-------|---------|---------|
| P0 | 统一字段命名与文档一致 | 部分不一致 | 低 |
| P1 | 增强Output Parser | 当前较弱 | 中 |
| P2 | 上下文裁剪(trim_steps) | 未实现 | 高 |
| P3 | scratchpad格式化 | 未实现 | 中 |

---

## 14 参考文档

| 文档 | 说明 |
|------|------|
| `doc/流式ReAct的type和API重构设计说明书.md` | 当前项目完整设计 |
| `doc-ReAct重构/ReAct-框架对比与实现方法总结-小沈-2026-03-20.md` | 框架对比总结 |
| `doc-ReAct重构/LLM工具调用参数命名规范-实现说明文档.md` | 工具参数规范 |

---

## 15 版本记录

| 版本 | 时间 | 更新内容 | 作者 |
|------|------|---------|------|
| v1.0 | 2026-03-20 05:07:12 | 初始版本，包含完整字段级数据流设计 | 小沈 |
| v1.1 | 2026-03-20 08:50:00 | 补充当前项目实施进度、实际字段定义、术语对照、实施进度总览 | 小健 |

---

**文档结束**
