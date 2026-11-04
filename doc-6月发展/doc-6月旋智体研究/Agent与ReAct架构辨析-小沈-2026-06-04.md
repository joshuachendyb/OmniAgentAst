# Agent 与 ReAct 架构辨析

**创建时间**: 2026-06-04 06:36:53  
**版本**: v1.0  
**作者**: 小沈  

---

## 一、问题根源：现有架构混淆了"实体"与"模式"

当前 OmniAgentAs-desk 后端的 Agent 系统，在架构层面存在一个根本性设计缺陷——**Agent（智能体）与 ReAct（执行模式）被焊死在一起**。

| 概念 | 本质 | 现有代码的处理 |
|------|------|--------------|
| **Agent** | 智能体容器（实体） | 被当作 ReAct 的壳 |
| **ReAct** | 推理-行动循环（算法） | 被内嵌为 Agent 的核心逻辑 |

**结果是**：`Agent = React`，而不是 `Agent 内含 React 作为策略`。

---

## 二、正确架构：Agent 是容器，ReAct 是可插拔策略

### 2.1 分层关系

```
┌─────────────────────────────────────────────────┐
│                    Agent                          │
│   智能体容器 — 管理状态、资源、生命周期             │
│                                                   │
│  ┌─────────┐  ┌──────────┐  ┌──────────────────┐ │
│  │工具注册表 │  │LLM客户端  │  │  执行策略(Strategy)│ │
│  │         │  │          │  │  (可插拔)         │ │
│  │ ToolReg │  │ llm_cli  │  │  ┌──────────────┐│ │
│  │ istry   │  │ ent      │  │  │ ReActStrategy ││ │
│  │         │  │          │  │  │ PlanExecute   ││ │
│  │         │  │          │  │  │ Reflection    ││ │
│  │         │  │          │  │  │ ...           ││ │
│  │         │  │          │  │  └──────────────┘│ │
│  └─────────┘  └──────────┘  └──────────────────┘ │
│                                                   │
│  统一接口: run(task) → AgentResult                │
└─────────────────────────────────────────────────┘
```

### 2.2 各层职责

#### Agent（容器层）

| 职责 | 说明 |
|------|------|
| **状态管理** | steps（执行步骤）、status（状态）、task_id（任务ID） |
| **资源持有** | tools（工具集）、llm_client（LLM客户端） |
| **外部接口** | `run()` 统一入口，屏蔽内部策略差异 |
| **生命周期** | 任务的创建→执行→完成追踪 |

**核心原则**：Agent **不关心内部如何执行**，执行逻辑全部委托给 Strategy。

#### Strategy（策略层）

| 策略 | 执行模式 | 适用场景 |
|------|---------|---------|
| **ReActStrategy** | 思考→行动→观察→循环 | 需要多步工具调用的任务 |
| **PlanExecuteStrategy** | 先规划→再逐步执行 | 复杂多步骤任务 |
| **ReflectionStrategy** | 执行→反思→改进→再执行 | 质量控制类任务 |
| **DirectStrategy** | 直接 LLM 输出 | 简单问答 |

**核心原则**：Strategy **只接受标准接口** `(llm, tools, task) → result`，与 Agent 解耦。

---

## 三、错误的现状 vs 正确的设计

### 3.1 现有代码（错误的）

```
BaseAgent
  ├── _get_llm_response()    ← 为 ReAct 循环设计
  ├── run_stream()           ← ReAct 循环（焊死在基类）
  ├── _execute_tool()        ← 工具执行
  └── ...子类无法摆脱 ReAct
```

**问题**：
- `run_stream()` 作为 ReAct 循环直接绑在 `BaseAgent` 上
- 抽象方法 `_get_llm_response()` 语义上只为 ReAct 服务
- 想换别的执行模式？做不到——基类已经把 "Agent 就是 ReAct" 写死了

### 3.2 正确设计（应该的）

```
Agent
  ├── run(task)               ← 统一接口
  ├── self.strategy.call()    ← 委托给策略对象
  └── 不包含任何 ReAct 特有逻辑

ReActStrategy(AgentStrategy)
  ├── call(llm, tools, task)  ← 实现 think-act-observe 循环
  └── 不持有 Agent 状态
```

**优势**：
- Agent 可以自由组合不同策略
- Strategy 可以独立测试、独立演进
- 新增策略不需要改 Agent 基类（OCP原则）

---

## 四、关键技术决策

### 4.1 Agent 不应持有 Strategy 的状态

Agent 只关心 Strategy 的**输出结果**，不关心 Strategy 的内部状态。Strategy 内部产生的中间步骤（如 ReAct 的 thought/action/observation）应该通过回调或事件机制传递，而非直接写入 Agent 的状态列表。

### 4.2 Strategy 的标准接口

```python
class AgentStrategy(ABC):
    async def call(
        self,
        llm_client: Any,
        tools: ToolRegistry,
        task: str,
        context: Optional[Dict] = None,
        on_step: Optional[Callable[[Step], None]] = None  # 步骤回调
    ) -> StrategyResult:
        ...
```

### 4.3 步骤回调机制

Strategy 在执行过程中产生的步骤，通过 `on_step` 回调传递给 Agent，Agent 负责持久化记录。这样 Strategy 不需要知道 Agent 的存在。

---

## 五、结论

| 维度 | 现有架构（错误） | 正确架构 |
|------|----------------|---------|
| **Agent 与 React 关系** | Agent = React（焊接） | Agent 含 React（组合） |
| **扩展性** | 只能支持 ReAct | 支持任意执行策略 |
| **测试性** | 需要实例化完整 Agent | Strategy 可独立测试 |
| **OCP 原则** | 违反（改模式要改基类） | 符合（新增策略不修改既有类） |
| **职责清晰度** | 模糊（Agent 什么都做） | 清晰（容器 vs 算法分离） |

**一句话总结**：Agent 是"谁"，Strategy 是"怎么做"。ReAct 只是 Strategy 的一种，Agent 不应该被任何一种 Strategy 绑架。

---

## 版本历史

| 版本 | 时间 | 作者 | 更新内容 |
|------|------|------|---------|
| v1.0 | 2026-06-04 06:36:53 | 小沈 | 初始版本，Agent与ReAct架构辨析 |
