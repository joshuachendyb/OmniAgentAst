# ReAct Loop 字段级数据流调研报告

**文档版本**: v1.0  
**创建时间**: 2026-03-19 23:22:06  
**编写人**: 小沈  
**参考资料**: LangChain ReAct Agent 官方实现

---

## 一、核心数据结构（LangChain 源码）

### 1.1 AgentAction（LLM 输出的 Action）

```python
class AgentAction:
    tool: str           # 工具名称
    tool_input: str|dict # 工具参数
    log: str            # LLM 的完整思考过程（包含 Thought + Action + Action Input）
```

### 1.2 中间步骤存储

```python
# 中间步骤 = (AgentAction, observation) 的元组列表
intermediate_steps: List[Tuple[AgentAction, str]]
#                ↑ 第一项：AgentAction
#                      ↓ 第二项：observation（工具执行结果，纯字符串）
```

### 1.3 Scratchpad 格式化函数（LangChain 源码）

```python
def format_log_to_str(
    intermediate_steps: List[Tuple[AgentAction, str]],
    observation_prefix: str = "Observation: ",
    llm_prefix: str = "Thought: ",
) -> str:
    thoughts = ""
    for action, observation in intermediate_steps:
        thoughts += action.log                          # 追加 AgentAction.log
        thoughts += f"\n{observation_prefix}{observation}\n{llm_prefix}"
    return thoughts
```

**格式化输出示例**：
```
Thought: I need to find the length of DOG
Action: get_text_length
Action Input: "DOG"
Observation: 3
Thought: 
```

---

## 二、完整的 ReAct Loop 数据流（字段级）

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           ReAct Loop 数据流图                               │
└─────────────────────────────────────────────────────────────────────────────┘

  ╔══════════════════════════════════════════════════════════════════╗
  ║                    第 N 轮 Loop（N ≥ 1）                        ║
  ╚══════════════════════════════════════════════════════════════════╝

  ┌─────────────────────────────────────────────────────────────────┐
  │ ① LLM 输入 (Prompt)                                            │
  │                                                                 │
  │   Question: 用户问题                                             │
  │   Tools: 可用工具列表                                           │
  │   agent_scratchpad: format_log_to_str(intermediate_steps)        │
  │                                                                 │
  │   【第1轮时】agent_scratchpad = ""（空字符串）                   │
  │   【第N轮时】agent_scratchpad = 前(N-1)轮的 Thought+Action+     │
  │                        Observation 格式化文本                     │
  └─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │ ② LLM 输出 (Response)                                           │
  │                                                                 │
  │   【由 LLM 根据 prompt + scratchpad 生成】                        │
  │                                                                 │
  │   AgentAction = {                                               │
  │       tool: "get_text_length",        ← 工具名称                │
  │       tool_input: "DOG",              ← 工具参数                │
  │       log: "Thought: I need to find the length of DOG\n"        │
  │            "Action: get_text_length\n"                          │
  │            "Action Input: \"DOG\""                               │
  │   }                                                             │
  │                                                                 │
  │   【重要】log 字段 = LLM 的完整思考过程（包含 Thought + Action）  │
  └─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │ ③ 工具执行 (Tool Execution)                                     │
  │                                                                 │
  │   observation = tool.func(tool_input)                          │
  │               = get_text_length("DOG")                          │
  │               = 3                                              │
  │                                                                 │
  │   【重要】observation = 工具执行结果（纯字符串）                  │
  │   【重要】observation 不经过任何判断，直接传递给下一轮            │
  └─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │ ④ 中间步骤存储                                                  │
  │                                                                 │
  │   intermediate_steps.append((AgentAction, observation))          │
  │                                                                 │
  │   【第N轮后】intermediate_steps = [                              │
  │       (AgentAction_1, "3"),     ← 第1轮                        │
  │       (AgentAction_2, "..."),   ← 第2轮                        │
  │       ...                                                      │
  │       (AgentAction_N, "..."),   ← 第N轮                        │
  │   ]                                                            │
  └─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │ ⑤ 进入下一轮 Loop                                               │
  │                                                                 │
  │   agent_scratchpad = format_log_to_str(intermediate_steps)       │
  │                                                                 │
  │   格式化后的 scratchpad 包含前N轮的完整历史：                      │
  │   ------------------------------------------------------------  │
  │   Thought: I need to find the length of DOG                     │
  │   Action: get_text_length                                       │
  │   Action Input: "DOG"                                          │
  │   Observation: 3                                               │
  │   Thought: ...（第2轮思考）                                     │
  │   Action: ...                                                  │
  │   Action Input: ...                                             │
  │   Observation: ...                                            │
  │   Thought: ...（第N轮思考）                                     │
  │   ------------------------------------------------------------  │
  │                                                                 │
  │   【回到①】LLM 基于 scratchpad 生成下一轮响应                    │
  └─────────────────────────────────────────────────────────────────┘


  ╔══════════════════════════════════════════════════════════════════╗
  ║                    退出 Loop（action = finish）                  ║
  ╚══════════════════════════════════════════════════════════════════╝

  当 LLM 输出 action = "finish" 时：
  
  AgentFinish = {
      return_values: {"output": "LLM 生成的最终答案"},
      log: "Thought: I now know the final answer\nFinal Answer: ..."
  }

  【重要】最终答案是 LLM 基于所有 Observation 生成的，不是代码生成的
```

---

## 三、各阶段字段汇总

### 3.1 Thought/Action 阶段（LLM 输出）

**对应 LangChain 数据结构**: `AgentAction`

| 字段名 | 类型 | 说明 | 来源 |
|--------|------|------|------|
| **tool** | string | 工具名称（action） | LLM 输出 |
| **tool_input** | string\|dict | 工具参数（action_input） | LLM 输出 |
| **log** | string | LLM 完整思考过程（包含 Thought + Action + Action Input） | LLM 输出 |

**log 字段的内部结构**：
```
Thought: LLM 思考的内容（我要做什么）
Action: 工具名称
Action Input: 工具参数
```

### 3.2 Observation 阶段（工具执行结果）

| 字段名 | 类型 | 说明 | 来源 |
|--------|------|------|------|
| **observation** | string | 工具执行结果（纯字符串） | 工具执行返回 |

**注意**：observation 不经过任何判断，直接进入下一轮 scratchpad

### 3.3 Scratchpad（LLM 上下文）

**对应 LangChain 函数**: `format_log_to_str(intermediate_steps)`

| 输入 | 输出 |
|------|------|
| `List[Tuple[AgentAction, str]]` | 格式化字符串 |

**格式化规则**：
```
action_1.log + "\nObservation: " + observation_1 + "\nThought: " +
action_2.log + "\nObservation: " + observation_2 + "\nThought: " +
...
```

---

## 四、完整代码示例（LangChain 源码）

```python
from langchain.agents.format_scratchpad import format_log_to_str
from langchain.schema import AgentAction, AgentFinish

# 中间步骤列表
intermediate_steps = []

# 第1轮
agent_step = agent.invoke({
    "input": "What is the length of DOG?",
    "agent_scratchpad": intermediate_steps  # 第1轮为空
})

if isinstance(agent_step, AgentAction):
    # 提取 LLM 输出的 Action 信息
    tool_name = agent_step.tool           # 例: "get_text_length"
    tool_input = agent_step.tool_input   # 例: "DOG"
    
    # 执行工具，获取 Observation
    observation = tool.func(str(tool_input))  # 例: 3
    
    # 保存到中间步骤
    intermediate_steps.append((agent_step, str(observation)))

# 第2轮（带历史）
agent_step = agent.invoke({
    "input": "What is the length of DOG?",
    "agent_scratchpad": intermediate_steps  # 包含第1轮的历史
})
```

---

## 五、关键结论

### 5.1 各阶段职责

| 阶段 | 职责 | 谁负责 |
|------|------|--------|
| **Thought/Action** | LLM 思考并决定下一步行动 | LLM |
| **Action 执行** | 执行 LLM 决定的工具 | 代码（Agent） |
| **Observation** | 返回工具执行结果 | 工具 |
| **判断是否完成** | 基于所有历史决定是否结束 | LLM |

### 5.2 数据流向

```
Thought/Action (LLM输出)
    ↓ tool + tool_input + log
工具执行
    ↓ observation (纯字符串)
intermediate_steps.append((AgentAction, observation))
    ↓
format_log_to_str(intermediate_steps)
    ↓
agent_scratchpad（格式化文本）
    ↓
LLM 基于 scratchpad 生成下一轮 Thought/Action
```

### 5.3 重要特性

1. **Observation 不判断**：observation 只是工具执行结果，不经过任何判断
2. **唯一决策者 = LLM**：所有决策（下一步做什么、是否完成）都由 LLM 决定
3. **Scratchpad 累积**：每一轮的 Thought + Action + Observation 都累积在 scratchpad 中

---

## 六、参考资料

| 资料 | 说明 |
|------|------|
| [LangChain AgentAction 源码](https://reference.langchain.com/python/langchain-core/agents/AgentAction) | AgentAction 字段定义 |
| [LangChain format_log_to_str 源码](https://reference.langchain.com/python/langchain-classic/agents/format_scratchpad/log/format_log_to_str) | Scratchpad 格式化函数 |
| [LangChain ReAct Prompt 模板](https://github.com/langchain-ai/langchain-hub/blob/master/slots/prompts/hwchase17/react/prompt.yaml) | ReAct 标准 Prompt |
| [Papakobina/Langchain-React-Agent](https://github.com/Papakobina/Langchain-React-Agent/blob/main/react-langchain/main.py) | 完整可运行示例 |

---

**文档结束**
