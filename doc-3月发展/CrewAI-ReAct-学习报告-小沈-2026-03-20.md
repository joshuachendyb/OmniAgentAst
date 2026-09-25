# CrewAI ReAct 学习报告

**文档版本**: v1.0
**创建时间**: 2026-03-20 05:40:00
**编写人**: 小沈
**研究资料数量**: 30+ 篇
**存放位置**: D:\OmniAgentAs-desk\doc-ReAct重构\

---

## 1 CrewAI 概述

### 1.1 框架简介

| 属性 | 说明 |
|------|------|
| **名称** | CrewAI |
| **语言** | Python |
| **Stars** | 46K+ (GitHub) |
| **定位** | 多 Agent 协作框架 |
| **特点** | Role-Based 设计，支持任务委派 |

### 1.2 ReAct 支持

CrewAI 基于 LangChain 构建，底层使用 ReAct 模式。但 CrewAI 专注于多 Agent 协作，其 ReAct 实现与 LangChain 有细微差别。

---

## 2 核心概念

### 2.1 Agent

**定义**: 自主 Agent，包含 role、goal、backstory

```python
from crewai import Agent

agent = Agent(
    role="Researcher",
    goal="Find the latest AI news",
    backstory="You are an expert researcher...",
    tools=[search_tool, calculator_tool],
    verbose=True
)
```

**Agent 字段说明**:

| 字段 | 类型 | 说明 |
|------|------|------|
| `role` | `str` | Agent 的角色 |
| `goal` | `str` | Agent 的目标 |
| `backstory` | `str` | Agent 的背景故事 |
| `tools` | `List[Tool]` | Agent 可用的工具 |
| `verbose` | `bool` | 是否输出详细日志 |

### 2.2 Task

**定义**: 任务，包含描述和预期输出

```python
from crewai import Task

task = Task(
    description="Research the latest AI developments",
    agent=researcher_agent,
    expected_output="A summary of the latest AI news"
)
```

### 2.3 Crew

**定义**: Agent 团队，管理多个 Agent 和任务

```python
from crewai import Crew

crew = Crew(
    agents=[researcher_agent, writer_agent],
    tasks=[research_task, write_task],
    process="sequential"  # 或 "hierarchical"
)
```

---

## 3 ReAct 实现机制

### 3.1 CrewAI 不直接暴露 ReAct

**重要发现**: CrewAI 封装了 ReAct，不直接暴露 Thought/Action/Observation 格式。

**底层实现**:

```
CrewAI 架构:
┌─────────────────────────────────────────────┐
│                    Crew                       │
│  ┌─────────────┐  ┌─────────────┐            │
│  │   Agent A   │  │   Agent B   │            │
│  │  (Role A)  │  │  (Role B)  │            │
│  └──────┬──────┘  └──────┬──────┘            │
│         │                │                   │
│         ▼                ▼                   │
│  ┌─────────────────────────────────────┐     │
│  │       LangChain ReAct Agent         │     │
│  │  (内部使用 Thought/Action/Obs)      │     │
│  └─────────────────────────────────────┘     │
└─────────────────────────────────────────────┘
```

### 3.2 内部 ReAct Prompt

CrewAI 内部使用的 ReAct Prompt 格式：

```
You are a {role}.

Your goal is: {goal}

Your backstory: {backstory}

You have access to the following tools:
{tools}

To use a tool, use the following format:
```
<start_of_thought>
Thought: your thought
Action: tool_name
Action Input: {{
  "param1": "value1"
}}
<end_of_thought>
```

When you have completed the task, use the format:
```
<start_of_thought>
Final Answer: your final answer
<end_of_thought>
```
```

---

## 4 CrewAI Agent 的 ReAct 流程

### 4.1 流程图

```
User Input
    │
    ▼
┌─────────────────────────────────────────────┐
│           CrewAI Agent                       │
│                                              │
│  1. 角色/目标/工具 → 构建 Prompt            │
│  2. 调用 LLM                                │
│  3. 解析 Output (内部使用 ReAct Parser)       │
│  4. 如果是 Action → 执行工具 → Observation    │
│  5. Observation → 更新 Prompt → 继续         │
│  6. 如果是 Final Answer → 返回结果           │
└─────────────────────────────────────────────┘
    │
    ▼
Response
```

### 4.2 关键区别

| 特性 | LangChain | CrewAI |
|------|-----------|--------|
| **ReAct 格式** | 显式 | 隐式 |
| **Agent 定义** | 手动配置 | Role-Based |
| **多 Agent** | 自行实现 | 内置支持 |
| **任务委派** | 不支持 | 支持 |

---

## 5 CrewAI 代码示例

### 5.1 基本用法

```python
from crewai import Agent, Crew, Task
from crewai.tools import SerplyDevTool, CalculatorTool

# 定义工具
search_tool = SerplyDevTool()
calculator_tool = CalculatorTool()

# 定义 Agent
researcher = Agent(
    role="Research Analyst",
    goal="Research the latest developments in AI",
    backstory="You are an expert AI researcher...",
    tools=[search_tool],
    verbose=True
)

writer = Agent(
    role="Tech Writer",
    goal="Write clear summaries of AI developments",
    backstory="You are a skilled technical writer...",
    verbose=True
)

# 定义任务
research_task = Task(
    description="Research the latest AI news",
    agent=researcher,
    expected_output="A summary of the latest AI developments"
)

write_task = Task(
    description="Write a summary based on the research",
    agent=writer,
    expected_output="A clear summary of the AI developments"
)

# 创建 Crew
crew = Crew(
    agents=[researcher, writer],
    tasks=[research_task, write_task],
    process="sequential"
)

# 执行
result = crew.kickoff()
print(result)
```

### 5.2 Hierarchical Process

```python
from crewai import Crew, Process

# 创建带 Manager 的 Crew
crew = Crew(
    agents=[specialist1, specialist2, specialist3],
    tasks=[task1, task2, task3],
    process=Process.hierarchical,
    manager_agent=manager  # 可选的自定义 Manager
)
```

---

## 6 CrewAI 的 ReAct 特点

### 6.1 优点

| 优点 | 说明 |
|------|------|
| **多 Agent 原生** | 内置多 Agent 协作 |
| **Role-Based** | 易于定义 Agent 角色 |
| **任务委派** | Agent 可以委派任务 |
| **简化开发** | 不需要手动实现 ReAct Loop |

### 6.2 缺点

| 缺点 | 说明 |
|------|------|
| **ReAct 不可见** | 内部封装，难以定制 |
| **灵活性降低** | 难以修改底层 ReAct 逻辑 |
| **调试困难** | 黑盒实现 |

### 6.3 对 omniAgent 的参考价值

| 参考点 | 说明 |
|------|------|
| **Role-Based 设计** | Agent 应该有明确的角色定义 |
| **多 Agent 架构** | Crew 模式可以参考 |
| **任务委派机制** | Agent 之间可以互相调用 |

---

## 7 CrewAI vs LangChain ReAct

### 7.1 对比表

| 方面 | LangChain | CrewAI |
|------|-----------|--------|
| **抽象层级** | 低（接近底层） | 高（封装较多） |
| **ReAct 控制** | 完全可控 | 内部封装 |
| **多 Agent** | 自行实现 | 内置支持 |
| **学习曲线** | 陡峭 | 较平缓 |
| **适用场景** | 需要精细控制 | 快速构建多 Agent |

### 7.2 选择建议

- **需要精细控制 ReAct**: 使用 LangChain
- **快速构建多 Agent**: 使用 CrewAI
- **混合需求**: 使用 LangChain + 自定义多 Agent 架构

---

## 8 关键资源链接

| 资源 | 说明 |
|------|------|
| [CrewAI GitHub](https://github.com/crewAIInc/crewAI) | 官方仓库 |
| [CrewAI 文档](https://docs.crewai.com/) | 官方文档 |
| [CrewAI Examples](https://github.com/crewAIInc/crewAI-examples) | 示例代码 |
| [CrewAI 快速开始](https://docs.crewai.com/quickstart) | 入门教程 |

---

## 9 版本记录

| 版本 | 时间 | 更新内容 | 作者 |
|------|------|---------|------|
| v1.0 | 2026-03-20 05:40:00 | 初始版本，包含完整 CrewAI 学习报告 | 小沈 |

---

**文档结束**
