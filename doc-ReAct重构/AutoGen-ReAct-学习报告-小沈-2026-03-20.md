# AutoGen ReAct 学习报告

**文档版本**: v1.0
**创建时间**: 2026-03-20 05:45:00
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
| **特点** | 支持人机协作，代码执行 |

### 1.2 ReAct 支持

AutoGen 支持 ReAct 模式，通过 `autogen-agentchat` 包实现。

---

## 2 核心概念

### 2.1 ConversableAgent

**定义**: 可对话的 Agent 基类

```python
from autogen import ConversableAgent

agent = ConversableAgent(
    name="assistant",
    system_message="You are a helpful assistant.",
    llm_config={"config_list": config_list}
)
```

### 2.2 AssistantAgent

**定义**: 助手 Agent，用于执行任务

```python
from autogen import AssistantAgent

assistant = AssistantAgent(
    name="assistant",
    system_message="You are a helpful assistant.",
    llm_config={"config_list": config_list}
)
```

### 2.3 UserProxyAgent

**定义**: 用户代理 Agent，用于执行代码和获取用户输入

```python
from autogen import UserProxyAgent

user_proxy = UserProxyAgent(
    name="user",
    human_input_mode="NEVER",  # NEVER / APPROVAL / TERMINATE
    max_consecutive_auto_reply=10,
    code_execution_config={"executor": code_executor}
)
```

---

## 3 AutoGen ReAct 实现

### 3.1 ReAct Prompt 格式

AutoGen 使用与 LangChain 相似的 ReAct Prompt：

```
Answer the following questions as best you can. You have access to tools provided.

Use the following format:

Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take
Action Input: the input to the action
Observation: the result of the action
... (this process can repeat multiple times)

Thought: I now know the final answer
Final Answer: the final answer to the original input question

Begin!

Question: {input}
```

### 3.2 ReAct 示例代码

**来源**: [AutoGen 官方文档](https://microsoft.github.io/autogen/0.2/docs/topics/prompting-and-reasoning/react/)

```python
import os
from typing import Annotated
from tavily import TavilyClient
from autogen import AssistantAgent, UserProxyAgent, config_list_from_json, register_function
from autogen.cache import Cache

# 配置 LLM
config_list = [
    {"model": "gpt-4", "api_key": os.environ["OPENAI_API_KEY"]},
]

# 定义工具
tavily = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])

def search_tool(query: Annotated[str, "The search query"]) -> Annotated[str, "The search results"]:
    return tavily.get_search_context(query=query, search_depth="advanced")

# ReAct Prompt
ReAct_prompt = """Answer the following questions as best you can. You have access to tools provided.

Use the following format:

Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take
Action Input: the input to the action
Observation: the result of the action
... (this process can repeat multiple times)

Thought: I now know the final answer
Final Answer: the final answer to the original input question

Begin!

Question: {input}"""

# 定义 ReAct prompt message
def react_prompt_message(sender, recipient, context):
    return ReAct_prompt.format(input=context["question"])

# 创建 Agents
user_proxy = UserProxyAgent(
    name="User",
    is_termination_msg=lambda x: x.get("content", "") and x.get("content", "").rstrip().endswith("TERMINATE"),
    human_input_mode="ALWAYS",
    max_consecutive_auto_reply=10,
    code_execution_config={"executor": code_executor},
)

assistant = AssistantAgent(
    name="Assistant",
    system_message="Only use the tools you have been provided with. Reply TERMINATE when the task is done.",
    llm_config={"config_list": config_list, "cache_seed": None},
)

# 注册工具
register_function(
    search_tool,
    caller=assistant,
    executor=user_proxy,
    name="search_tool",
    description="Search the web for the given query",
)

# 执行
with Cache.disk(cache_seed=43) as cache:
    user_proxy.initiate_chat(
        assistant,
        message=react_prompt_message,
        question="What is the result of super bowl 2024?",
        cache=cache,
    )
```

---

## 4 AutoGen ReAct 执行流程

### 4.1 流程图

```
┌─────────────────────────────────────────────┐
│          AutoGen ReAct 执行流程              │
└─────────────────────────────────────────────┘

UserProxyAgent                     AssistantAgent
     │                                   │
     │  ── ReAct Prompt ────────────────►│
     │                                   │
     │                                   │── LLM 生成
     │                                   │   Thought
     │                                   │   Action: search_tool
     │                                   │   Action Input: {...}
     │◄──────────────────────────────────│
     │                                   │
     │  ── 执行 search_tool ────────────►│ (UserProxy 执行)
     │                                   │
     │◄── Observation: 搜索结果 ─────────│
     │                                   │
     │  ── Observation ─────────────────►│
     │                                   │
     │        ... (重复循环) ...          │
     │                                   │
     │                                   │── Final Answer
     │◄──────────────────────────────────│
```

### 4.2 关键组件

| 组件 | 说明 |
|------|------|
| `ConversableAgent` | 可对话 Agent 基类 |
| `AssistantAgent` | 助手 Agent，生成 ReAct 输出 |
| `UserProxyAgent` | 用户代理，执行工具 |
| `register_function` | 注册工具到 Agent |
| `Cache` | LLM 响应缓存 |

---

## 5 AutoGen 工具注册机制

### 5.1 register_function

**功能**: 将函数注册为 Agent 可用的工具

```python
register_function(
    search_tool,              # 函数对象
    caller=assistant,         # 调用方 Agent
    executor=user_proxy,        # 执行方 Agent
    name="search_tool",        # 工具名称
    description="..."          # 工具描述
)
```

### 5.2 执行流程

```
1. AssistantAgent 生成: "Action: search_tool, Action Input: {...}"
2. AutoGen 解析出工具名和参数
3. UserProxyAgent 接收请求
4. UserProxyAgent 执行工具
5. 返回 Observation 给 AssistantAgent
6. 继续循环
```

---

## 6 AutoGen 的独特功能

### 6.1 Teachable Agent (Memory)

AutoGen 支持让 Agent 学习并记忆：

```python
from autogen.agentchat.contrib.capabilities import teachability

teachability = teachability.Teachability(
    verbosity=0,
    reset_db=True,
    path_to_db_dir="./tmp/notebook/teachability_db",
    recall_threshold=1.5,
)

teachability.add_to_agent(assistant)
```

### 6.2 Human-in-the-Loop

```python
user_proxy = UserProxyAgent(
    name="user",
    human_input_mode="APPROVAL",  # 需要用户批准
    max_consecutive_auto_reply=10,
)
```

---

## 7 AutoGen ReAct 的特点总结

### 7.1 优点

| 优点 | 说明 |
|------|------|
| **代码执行** | 内置代码执行能力 |
| **多语言** | Python / C# / TypeScript |
| **人机协作** | 支持 Human-in-the-Loop |
| **微软支持** | 稳定性和长期维护 |

### 7.2 缺点

| 缺点 | 说明 |
|------|------|
| **复杂度高** | 配置项较多 |
| **资源消耗** | 多个 Agent 运行开销大 |

### 7.3 对 omniAgent 的参考价值

| 参考点 | 说明 |
|------|------|
| **工具注册机制** | `register_function` 模式 |
| **多 Agent 通信** | Agent 间消息传递 |
| **Human-in-Loop** | 用户干预机制 |
| **Memory 模块** | Agent 记忆能力 |

---

## 8 关键资源链接

| 资源 | 说明 |
|------|------|
| [AutoGen GitHub](https://github.com/microsoft/autogen) | 官方仓库 |
| [AutoGen 文档](https://microsoft.github.io/autogen/stable/) | 官方文档 |
| [ReAct 教程](https://microsoft.github.io/autogen/0.2/docs/topics/prompting-and-reasoning/react/) | ReAct 实现 |
| [AutoGen 示例](https://github.com/microsoft/autogen/tree/main/samples) | 示例代码 |

---

## 9 版本记录

| 版本 | 时间 | 更新内容 | 作者 |
|------|------|---------|------|
| v1.0 | 2026-03-20 05:45:00 | 初始版本，包含完整 AutoGen ReAct 学习报告 | 小沈 |

---

**文档结束**
