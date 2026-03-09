# 流式ReAct的type和API重构设计说明书

**编写人**: 小沈
**编写时间**: 2026-03-08 21:50:00
**更新时间**: 2026-03-09 14:20:00
**存放位置**: D:\2bktest\MDview\OmniAgentAs-desk\doc\

---

## 一、ReAct原理正确理解

### 1.1 ReAct核心概念（标准流程）

ReAct (Reasoning + Acting) 循环的三个核心要素：

| 要素 | 英文 | 说明 |
|------|------|------|
| **思考** | Thought | LLM 分析任务，决定下一步做什么 |
| **行动** | Action | LLM 决定使用什么工具 |
| **观察** | Observation | 工具执行结果，返回给 LLM |

**循环迭代（核心）**
   每轮严格按顺序执行：Thought → Action → Observation
---

**ReAct 标准流程**：

1. **任务初始化**
   - 接收自然语言形式的任务目标
   - 加载少量示例（Few-shot）和可用工具列表
   - 初始化上下文记忆
2. **Thought（推理）应包含**：
   - 当前进展：任务做到哪一步了
   - 缺失信息：还需要什么
   - 下一步行动：要做什么
   - 预期结果：期望得到什么
   - 示例："需先查明天深圳→海南的晚间航班，调用航班查询工具"

3. **Action（行动）格式**：
   - 标准化指令
   - 示例：`search["深圳到海南 明晚航班"]`
   - 或：`list_directory{"path": "C:\\Users"}`

4. **Observation（观察）**：
   - 工具返回的客观反馈
   - 搜索结果、计算值、文件内容等
   - 作为下一轮推理的输入

5. **任务终止**：
   - 任务完成（已获取所需信息）
   - 或达到最大迭代次数

---

### 1.2 正确的时间顺序

```
┌─────────────────────────────────────────────────────────────┐
│  第 N 轮 ReAct 循环                                         │
│                                                              │
│  1. Thought: "用户想要查看桌面文件夹..."                    │
│     ↓                                                        │
│  2. Action: "list_directory", params={"path": "..."}    │
│     ↓                                                        │
│  3. Observation: 执行结果（成功/失败）                       │
│     ↓                                                        │
│  → 把结果发给 LLM，让它继续思考 → 第 N+1 轮                  │
└─────────────────────────────────────────────────────────────┘
```

### 1.3 时间线对比（重要）

**当前实现（批量模式-有问题）**：
```
chat.py: result = await agent.run()
                ↑
                │  阻塞等待！
                │
        agent.py: while循环执行完所有轮次
                      ↓
        return result (所有steps已经完成)
                ↓
chat.py: for step in result.steps:
           yield step_data  ←才开始一个个发送
                ↓
前端收到所有数据 ← 等全部执行完才一次性收到
```

**正确的实时流程（流式模式）**：
```
每轮循环结束后:
  → 立即 yield 发送 thought
  → 立即 yield 发送 action + observation
  → 然后继续下一轮循环
  
前端实时收到每一步
```

### 1.4 关键原则

- **三者独立**：Thought、Action、Observation 是三个独立的步骤，不能嵌套
- **时间顺序**：按顺序发生，不能嵌套
- **各司其职**：每个步骤只做一件事
- **实时推送**：每轮循环完成后立即发送，不用等全部完成

### 1.5 相关代码文件

| 文件 | 路径 | 作用 |
|------|------|------|
| chat.py | `backend/app/api/v1/chat.py` | API入口，编排流程 |
| agent.py | `backend/app/services/file_operations/agent.py` | ReAct Agent，执行文件操作 |
| tools.py | `backend/app/services/file_operations/tools.py` | 文件操作工具集 |

---

## 二、已发现的代码问题

### 2.1 实时显示问题

| 问题 | 位置 | 说明 |
|------|------|------|
| agent.run() 阻塞 | agent.py:373 | 等所有循环执行完才返回 |
| 推送时机错误 | chat.py:780 | for循环发送，不是实时 |

### 2.2 数据结构问题

| 问题 | 位置 | 说明 |
|------|------|------|
| **嵌套错误** | observation 内部包含 thought/action_tool | 逻辑混乱，违反独立原则 |
| 冗余字段 | result vs observation.result | 重复存储 |
| 历史遗留 | contentStart/contentEnd | 无用字段 |

### 2.3 硬编码问题

| 问题 | 位置 | 说明 |
|------|------|------|
| 第一个 thought 硬编码 | chat.py:697-702 | "正在分析任务..." |
| 第一个 action_tool 硬编码 | chat.py:721-723 | "检测到文件操作意图..." |

---

## 三、当前type统计

### 3.1 统计结果：11个type

| 序号 | type | 说明 |
|------|------|------|
| 1 | start | 任务开始 |
| 2 | thought | 思考 |
| 3 | action_tool | 执行动作 |
| 4 | observation | 执行结果 |
| 5 | chunk | 流式内容片段 |
| 6 | final | 最终回复 |
| 7 | error | 错误 |
| 8 | interrupted | 中断 |
| 9 | paused | 暂停 |
| 10 | resumed | 恢复 |
| 11 | retrying | 重试 |

---

### 3.2 当前代码中的字段设置

#### type=start（当前）

```json
{
  "type": "start",
  "display_name": "OpenAI (gpt-4)",
  "model": "gpt-4",
  "provider": "openai",
  "task_id": "abc123"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| display_name | string | AI显示名称 |
| model | string | AI模型 |
| provider | string | AI提供商 |
| task_id | string | 任务ID |

---

#### type=thought（当前）

```json
{
  "type": "thought",
  "content": "正在分析任务..."
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| content | string | 思考内容 |

---

#### type=action_tool（当前）

```json
{
  "type": "action_tool",
  "step": 1,
  "action_tool_description": "检测到文件操作意图..."
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| step | number | 步骤序号 |
| action_tool_description | string | 动作描述文本（问题：不是真正的action_tool） |

---

#### type=observation（当前-有问题）

```json
{
  "type": "observation",
  "step": 3,
  "thought": "用户想要查看桌面文件夹...",
  "action_tool": "list_directory",
  "observation": {
    "success": false,
    "error": "Action 'list_directory' failed...",
    "result": null,
    "retry_count": 3
  },
  "result": "❌ Action 'list_directory' failed..."
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| step | number | 步骤序号 |
| thought | string | LLM思考（问题：嵌套，不该在这里） |
| action_tool | string | 执行的动作（问题：嵌套，不该在这里） |
| observation | object | 原始结果（问题：嵌套自己） |
| observation.success | boolean | 执行是否成功 |
| observation.error | string | 错误信息 |
| observation.result | any | 执行结果 |
| observation.retry_count | number | 重试次数 |
| result | string | 格式化后的文本（问题：冗余） |

---

#### type=chunk（当前）

```json
{
  "type": "chunk",
  "content": "这是回复片段",
  "model": "gpt-4",
  "provider": "openai",
  "is_reasoning": false,
  "reasoning": ""
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| content | string | 回复片段 |
| model | string | AI模型 |
| provider | string | AI提供商 |
| is_reasoning | boolean | 是否在思考 |
| reasoning | string | 思考内容 |

---

#### type=final（当前）

```json
{
  "type": "final",
  "content": "完整的回复内容",
  "model": "gpt-4",
  "provider": "openai",
  "display_name": "OpenAI (gpt-4)"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| content | string | 完整回复 |
| model | string | AI模型 |
| provider | string | AI提供商 |
| display_name | string | AI显示名称 |

---

#### type=error（当前）

```json
{
  "type": "error",
  "error_type": "TimeoutError",
  "content": "请求超时"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| error_type | string | 错误类型（问题：应改为code） |
| content | string | 错误信息（问题：应改为message） |

---

#### type=interrupted（当前）

```json
{
  "type": "interrupted",
  "content": "任务已被中断"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| content | string | 中断消息（问题：应改为message） |

---

#### type=paused（当前）

```json
{
  "type": "paused",
  "message": "任务已暂停"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| message | string | 暂停消息 |

---

#### type=resumed（当前）

```json
{
  "type": "resumed",
  "message": "任务已恢复"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| message | string | 恢复消息 |

---

#### type=retrying（当前）

```json
{
  "type": "retrying",
  "message": "正在重试..."
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| message | string | 重试消息 |

---

## 四、type设计原则（必须遵守）

### 4.1 原则1：各阶段信息独立表达

**核心说明**：
- 每个type只表达**当前阶段**的信息，不重复表达其他阶段的内容
- 不同阶段之间是**时间序列**关系（按顺序传递），不是"嵌套"关系
- Observation阶段包含"上一轮Action结果"和"LLM新决策"是**时间顺序上的连续**，不是嵌套

**错误示例（真正嵌套）** ❌：
```json
{
  "type": "observation",
  "thought": "...",        // 重复表达上一轮thought的内容！
  "action_tool": "...",   // 重复表达上一轮action_tool的内容！
  "observation": {...}     // 嵌套自己！
}
```

**正确示例（时间序列）** ✅：
```json
{ "type": "thought", "content": "...", "action_tool": "list_directory", "params": {...} }
{ "type": "action_tool", "tool_name": "list_directory", "execution_status": "success", "summary": "..." }
{ "type": "observation", "execution_status": "success", "summary": "...", "content": "...", "action_tool": "read_file" }
```
> **说明**：observation中同时包含execution_status（上一轮action_tool的结果）和content/action_tool（LLM的新决策），这是**时间上的连续传递**，不是嵌套。当前阶段既携带上一阶段的结果，又包含自己的输出，这是ReAct循环的标准模式。

### 4.2 原则2：type名称不能出现在字段名

**错误** ❌：
```json
{ "type": "thought", "thought_content": "..." }  // thought 重复
```

**正确** ✅：
```json
{ "type": "thought", "content": "..." }
```

### 4.3 原则3：字段完整准确

每个type必须有完整的字段，不能多也不能少。

### 4.4 原则4：三个核心stage深入分析

#### 4.4.1 完整数据流图

```
用户输入
    ↓
┌─────────────────────────────────────────────────────────────────┐
│                         第 N 轮 ReAct 循环                         │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Stage 1: Thought（思考）                                │   │
│  │  输入：用户输入 或 上一轮 Observation 结果                │   │
│  │  处理：调用 LLM                                          │   │
│  │  输出：LLM 返回 thought + action_tool + params          │   │
│  └─────────────────────────────────────────────────────────┘   │
│                           ↓                                     │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Stage 2: Action（执行动作）                             │   │
│  │  输入：LLM 返回的 action_tool + params                 │   │
│  │  处理：Agent 解析 → 调用本地 action_tool → 执行获得结果         │   │
│  │  输出：action_tool 执行结果 → observation                      │   │
│  └─────────────────────────────────────────────────────────┘   │
│                           ↓                                     │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Stage 3: Observation（观察结果）                        │   │
│  │  输入：Action 的执行结果                                 │   │
│  │  处理：调用 LLM（让 LLM 基于结果继续推理）               │   │
│  │  输出：LLM 返回新的 thought                              │   │
│  └─────────────────────────────────────────────────────────┘   │
│                           ↓                                     │
│                        第 N+1 轮                                │
└─────────────────────────────────────────────────────────────────┘
```

#### 4.4.2 每个 Stage 的详细特征

**Stage 1: Thought（思考）**

| 特征 | 分析 |
|------|------|
| **输入信息来源** | 第1次：用户输入；后续轮次：上一轮 Observation 的结果 |
| **谁来处理** | 调用 LLM |
| **处理后结果** | LLM 返回的完整响应，包含：thought（思考）、action_tool（要执行的工具）、params（工具参数） |
| **结果存储位置** | conversation_history（作为 assistant 消息） |
| **传导到下一阶段** | LLM 返回的 action_tool + params 传给 Action |

---

**Stage 2: Action（执行动作）**

| 特征 | 分析 |
|------|------|
| **输入信息来源** | Thought 阶段 LLM 返回的 action_tool + params |
| **谁来处理** | 本地 Agent 解析 action_tool 名称 → 找到对应的 action_tool → 调用执行 |
| **处理后结果** | action_tool 执行的结果（成功/失败/数据） |
| **结果存储位置** | observation（包含 success/error/result/data） |
| **传导到下一阶段** | 执行结果作为 observation 传给 Observation |

---

**Stage 3: Observation（观察结果）**

| 特征 | 分析 |
|------|------|
| **输入信息来源** | Action 阶段 action_tool 的执行结果 |
| **谁来处理** | 调用 LLM（让 LLM 基于执行结果继续推理） |
| **处理后结果** | LLM 返回新的 thought（基于结果的分析） |
| **结果存储位置** | conversation_history（作为 user 消息，格式化为文本） |
| **传导到下一阶段** | 新的 thought 作为下一轮的输入，开始第 N+1 轮循环 |

---

#### 4.4.3 字段设计原则

根据以上分析，三个核心 stage 的字段应该这样设计：

**Thought 阶段（输入→LLM，输出包含 action_tool）**：

| 字段类型 | 字段名 | 说明 |
|----------|--------|------|
| **输入字段** | - | 来自 conversation_history |
| **输出字段** | content | LLM 生成的思考内容 |
| **输出字段** | action_tool | LLM 决定要执行的工具名 |
| **输出字段** | params | 工具参数 |

**Action 阶段（输入 action_tool，输出 observation）**：

| 字段类型 | 字段名 | 说明 |
|----------|--------|------|
| **输入字段** | name | 要执行的工具名（来自 LLM） |
| **输入字段** | input | 工具参数（来自 LLM） |
| **输出字段** | status | 执行状态：success / error / warning |
| **输出字段** | message | 可读的执行结果描述 |
| **输出字段** | data | 原始数据（如文件列表等） |

**Observation 阶段（输入 action_tool 结果→LLM，输出新的 thought）**：

| 字段类型 | 字段名 | 说明 |
|----------|--------|------|
| **输入字段** | status | 来自 Action 的执行状态 |
| **输入字段** | message | 来自 Action 的执行结果 |
| **输入字段** | data | 来自 Action 的原始数据 |
| **输出字段** | content | LLM 基于结果生成的新思考 |
| **输出字段** | action_tool | LLM 决定的下一步工具（可选） |
| **输出字段** | params | 工具参数（可选） |

---

#### 4.4.4 当前问题

当前代码中 observation 嵌套了 thought 和 action_tool，这是错误的！

**错误原因**：
- observation 是 Action 阶段的**输出结果**
- 不应该包含 Thought 阶段的 thought
- 也不应该重复包含 Action 阶段的 action_tool

**正确结构**：
- Thought：输出 content（给 LLM 继续用）+ action_tool + params
- Action：输出 status + message + data（作为 observation）
- Observation：输入是 observation，输出是新的 content（给 LLM）

---

#### 4.5 Stage vs Type 总结

| Stage/Type | 输入 | 输出 | 传导 |
|------------|------|------|------|
| **Stage** | | | |
| thought | 用户输入/Observation结果 | content + action_tool + params | → Action |
| action_tool | action_tool + params | status + message + data | → Observation |
| observation | status + message + data | content + action_tool + params | → 下一轮Thought |
| final | 循环结束结果 | content | 结束 |
| **Type** | | | |
| start | - | display_name/model/provider/task_id | - |
| chunk | - | content | - |
| error | - | code + message | - |
| interrupted | - | message | - |
| paused | - | message | - |
| resumed | - | message | - |
| retrying | - | message | - |

---

## 五、每个type完整分析

**基于第4章的分析框架，每个type需要回答**：
1. 是 Stage 还是 Type？
2. 输入来源是什么？（谁给的）
3. 输出到哪里？（给谁用）
4. 传导到下一阶段的是什么？
5. 字段是否合理必要？

---

### 5.1 type=start（任务开始 + 安全检查）

**是 Stage 还是 Type？**
- **Type**（初始化阶段，不是循环的一部分）

**包含两个子阶段**：

| 子阶段 | 说明 | 执行时机 |
|--------|------|---------|
| 初始化 | 设置AI模型、任务ID等 | 开始时 |
| 安全检查 | 规则检查用户输入是否安全 | 初始化后，调用Agent前 |

**输入**：无（任务开始）

**输出**：display_name, model, provider, task_id, security_check

**传导**：安全检查通过后 → 进入ReAct循环

---

### 5.1.0 安全检查时机说明

**问题**：安全检查是在软件逻辑中执行，还是在用户输入后与文件操作判断合并？

**分析**：

根据调试笔记11章的设计，安全检查应该在**用户输入后、ReAct循环开始前**执行，具体位置在：

```
用户发送消息 → 安全检查（规则检查） → 文件操作意图检测 → LLM推理
                          ↓                        ↓
                    拦截危险命令              分析命令意图
```

**理由**：
1. **规则检查**：快速拦截明显危险命令（如 `rm -rf /`），在调用LLM之前完成
2. **文件操作检测**：识别用户意图是否为文件操作（非文件操作走普通对话）
3. **LLM推理**：如果识别为文件操作，进入ReAct循环

**安全检查三层执行顺序**：

| 顺序 | 检查 | 位置 | 作用 |
|------|------|------|------|
| 1 | 规则检查 | 用户输入后立即执行 | 快速拦截危险命令 |
| 2 | 文件操作检测 | 规则检查后 | 判断走文件操作还是普通对话 |
| 3 | LLM推理 | 进入ReAct后 | 分析命令意图，给出风险提示 |

---

### 5.1.1 安全检查流程

```
用户发送: "删除 C:\Windows\System32"
                ↓
        ┌───────────────────────────────────────┐
        │  阶段1：规则检查（后端自动）            │
        │  check_command_safety()               │
        │  → 危险命令：拦截并提示错误           │← 直接终止，不进入下阶段
        │  → 安全命令：进入阶段2                │
        └───────────────────────────────────────┘
                ↓ 安全
        ┌───────────────────────────────────────┐
        │  阶段2：LLM推理（第一个Thought）       │
        │  → 分析命令意图，给出智能提示          │
        │  → 如有风险，给出警告提示              │
        └───────────────────────────────────────┘
                ↓
        ┌───────────────────────────────────────┐
        │  阶段3：用户确认（必须有）             │
        │  → 确认 → 继续执行                   │
        │  → 停止 → 终止任务                   │
        │  → 更改命令 → 重新开始整个流程 🔄     │
        └───────────────────────────────────────┘
```

**注意**：选择"更改命令"后，**重新开始整个流程**，包括：
1. 重新进行规则检查
2. 重新进行文件操作检测
3. 重新进行LLM推理

---

**安全检查三层保障**：

| 层级 | 作用 | 用户选择 |
|------|------|---------|
| **规则检查** | 快速拦截 `rm -rf /`、`format C:` 等 | 自动拦截，无需用户选择 |
| **LLM推理** | 分析命令意图，给出智能提示 | 识别风险，给出警告 |
| **用户确认** | 危险操作必须用户许可 | 确认→继续 / 停止→终止 / 更改→重新开始整个流程 |

---

### 5.1.2 字段分析

**字段分析**：

| 字段 | 作用 | 必要性 | 说明 |
|------|------|--------|------|
| display_name | 显示AI名称 | 必要 | 如 "OpenAI (gpt-4)" |
| model | AI模型 | 必要 | 如 "gpt-4"、"gpt-4o" |
| provider | AI提供商 | 必要 | 如 "openai"、"anthropic" |
| task_id | 会话/请求ID | 必要 | 唯一标识一次用户请求，用于追踪调试 |
| security_check | 安全检查结果 | 必要 | 本次请求的安全检查结果 |

**security_check 字段结构**：

| 字段 | 作用 | 必要性 | 说明 |
|------|------|--------|------|
| is_safe | 是否安全 | 必要 | true=安全，false=危险 |
| risk_level | 风险等级 | 可选 | low/medium/high/critical |
| risk | 风险描述 | 可选 | 具体风险说明 |
| blocked | 是否被拦截 | 可选 | true=已拦截，不执行LLM |

**结论**：✅ 保留，整合security_check后字段完整

---

### 5.1.3 JSON示例

**安全检查通过**：
```json
{
  "type": "start",
  "display_name": "OpenAI (gpt-4)",
  "model": "gpt-4",
  "provider": "openai",
  "task_id": "abc123",
  "security_check": {
    "is_safe": true,
    "risk_level": null,
    "risk": null,
    "blocked": false
  }
}
```

**安全检查拦截（危险命令）**：
```json
{
  "type": "start",
  "display_name": "OpenAI (gpt-4)",
  "model": "gpt-4",
  "provider": "openai",
  "task_id": "abc123",
  "security_check": {
    "is_safe": false,
    "risk_level": "critical",
    "risk": "检测到危险命令：rm -rf /",
    "blocked": true
  }
}
```

**安全检查通过但有警告**：
```json
{
  "type": "start",
  "display_name": "OpenAI (gpt-4)",
  "model": "gpt-4",
  "provider": "openai",
  "task_id": "abc123",
  "security_check": {
    "is_safe": true,
    "risk_level": "medium",
    "risk": "检测到删除操作，请确认",
    "blocked": false
  }
}
```

---

### 5.2 type=thought（LLM思考）

**是 Stage 还是 Type？**
- **Stage**（ReAct循环第1阶段）

**输入来源及结构**：

| 轮次 | 输入来源 | 输入结构 |
|------|----------|----------|
| **第1轮** | 用户消息 | `message.content`（用户输入的原始文本） |
| **后续轮次** | conversation_history | 包含：用户初始输入 + 历轮observation格式化文本 |

**具体输入结构**（给LLM的消息格式）：
```json
[
  {"role": "system", "content": "你是一个文件操作助手..."},
  {"role": "user", "content": "帮我查看桌面文件"},
  {"role": "assistant", "content": "好的，我来帮你..."},
  {"role": "user", "content": "Observation: 成功读取目录，文件列表：..."},
  ...
]
```

**处理**：调用LLM

**输出（LLM返回）**：content + action_tool + params

**传导**：action_tool + params 传给 Action阶段

**字段分析**：

| 字段 | 作用 | 必要性 | 合理? | 属于 |
|------|------|--------|-------|-------|
| content | LLM的思考内容 | 必要 | ✅ | 输出 |
| reasoning | LLM的推理过程 | 可选 | ✅ | 输出 |
| action_tool | 工具名称 | 必要 | ✅ | 输出（传导到Action） |
| params | 工具参数 | 必要 | ✅ | 输出（传导到Action） |

**结论**：✅ 保留，字段完整，属于 Stage

### 5.2.1 thought阶段的输入结构

thought阶段的输入给LLM的格式：

**第1轮 - 用户初始输入**：
```json
{
  "role": "user",
  "content": "帮我查看桌面文件夹"
}
```

**第N轮（N>1）- Observation结果反馈**：
```json
{
  "role": "user", 
  "content": "Observation: 成功读取目录，文件列表：['file1.txt', 'file2.txt']"
}
```

| 轮次 | role | content格式 | 说明 |
|------|------|-------------|------|
| 第1轮 | user | 用户的原始输入 | 用户的自然语言任务 |
| 第N轮 | user | `Observation: {status} - {message}` | 格式化后的action执行结果 |
| 字段 | 类型 | 说明 |
|------|------|------|
| role | string | 固定为 "user" |
| content | string | 格式化文本，格式：`Observation: {status} - {message}` |

**格式化多轮重复情况下的Observation结果作为输入thought的输入的信息规则**：
```
Observation: {status} - {message}
```

| status | message示例 |
|--------|-------------|
| success | 成功读取目录，文件列表：[...] |
| error | 操作失败，错误原因：... |
| warning | 操作有警告，警告信息：...

**完整消息列表示例**：
```json
[
  {"role": "system", "content": "你是一个文件操作助手..."},
  {"role": "user", "content": "帮我查看桌面文件"},        // 第1轮用户输入
  {"role": "assistant", "content": "好的，我来帮你..."},  // LLM的思考
  {"role": "user", "content": "Observation: 成功 - 读取到5个文件"},  // 第2轮反馈
  {"role": "assistant", "content": "已获取文件列表..."}, // LLM的思考
  ...
]
```
### 5.2.2 LLM反馈后thought的JSON结构

LLM返回给thought阶段的完整JSON结构（包含思考结果和下一步行动）：

**场景1：需要继续执行工具**
```json
{
  "content": "用户想要查看桌面文件夹，我需要先列出桌面目录的内容",
  "action_tool": "list_directory",
  "params": {
    "path": "C:\\Users\\xxx\\Desktop"
  }
}
```

**场景2：任务完成，直接回复用户**
```json
{
  "content": "已获取桌面文件列表，现在整理成用户可读的格式",
  "action_tool": "finish",
  "params": {}
}
```

**场景3：需要执行多个步骤**
```json
{
  "content": "用户想保存一个文本文件到桌面，我先检查目录是否存在",
  "action_tool": "list_directory",
  "params": {
    "path": "C:\\Users\\xxx\\Desktop"
  }
}
```

| 字段 | 类型 | 说明 | 必要性 |
|------|------|------|--------|
| content | string | LLM的思考内容，说明当前分析和下一步意图 | 必要 |
| action_tool | string | 要执行的工具名称，如 list_directory, read_file, finish 等 | 必要 |
| params | object | 工具执行的参数，如 {path: "..."} | 必要（可为空对象） |

**action_tool的取值范围**：

| action_tool | 说明 | params示例 |
|-------------|------|------------|
| list_directory | 列出目录内容 | {"path": "C:\\Users\\xxx\\Desktop"} |
| read_file | 读取文件内容 | {"path": "C:\\Users\\xxx\\test.txt"} |
| write_file | 写入文件内容 | {"path": "...", "content": "..."} |
| create_directory | 创建目录 | {"path": "C:\\Users\\xxx\\new_folder"} |
| delete_file | 删除文件 | {"path": "..."} |
| move_file | 移动文件 | {"source": "...", "destination": "..."} |
| copy_file | 复制文件 | {"source": "...", "destination": "..."} |
| finish | 完成任务，回复用户 | {} |

**JSON结构完整示例（多轮对话）**：
```json
// 第1轮 - LLM返回
{
  "content": "用户想要查看桌面文件夹，我需要先列出桌面目录的内容",
  "action_tool": "list_directory",
  "params": {"path": "C:\\Users\\xxx\\Desktop"}
}

// 第2轮 - LLM返回（基于observation结果）
{
  "content": "已成功获取桌面文件列表，共5个文件，现在整理成列表回复用户",
  "action_tool": "finish",
  "params": {}
}
```
### 5.3 type=action_tool（执行动作）

**是 Stage 还是 Type？**
- **Stage**（ReAct循环第2阶段）

**输入**：name + params（来自Thought阶段）

**处理**：Agent解析 → 调用本地工具 → 执行获得结果

**输出**：execution_status + summary + raw_data

**传导**：execution_status + summary + raw_data 作为Observation的输入

**字段分析**：

| 字段 | 作用 | 必要性 | 合理? | 属于 |
|------|------|--------|-------|-------|
| step | 步骤序号 | 必要 | ✅ | 辅助 |
| tool_name | 工具名称 | 必要 | ✅ | 输入 |
| tool_params | 工具参数 | 必要 | ✅ | 输入 |
| execution_status | 执行状态 | 必要 | ✅ | 输出 |
| summary | 结果描述 | 必要 | ✅ | 输出 |
| raw_data | 原始数据 | 可选 | ✅ | 输出 |
| action_retry_count | 重试次数 | 可选 | ✅ | 输出 |

**结论**：✅ 保留，字段完整，属于 Stage

---

### 5.3.1 action_tool阶段的输入结构

action_tool阶段的输入来自Thought阶段，由Agent解析后执行：

**输入结构**：
```json
{
  "tool_name": "list_directory",
  "tool_params": {
    "path": "C:\\Users\\xxx\\Desktop"
  }
}
```

| 字段 | 类型 | 来源 | 说明 |
|------|------|------|------|
| tool_name | string | Thought阶段LLM返回的action_tool | 要执行的工具名称 |
| tool_params | object | Thought阶段LLM返回的params | 工具执行参数 |

---

### 5.3.2 action_tool阶段处理流程

Agent收到name + params后的处理流程：

```
Agent收到 name + params
    ↓
1. 解析name → 找到对应的工具函数
2. 校验params → 检查必填参数是否存在
3. 调用工具函数 → 执行具体操作
4. 捕获执行结果 → 成功/失败/异常
5. 组装输出 → execution_status + summary + raw_data
```

---

### 5.3.3 action_tool阶段的输出JSON结构

action_tool阶段执行完成后，输出给Observation阶段的JSON结构：

**场景1：执行成功**
```json
{
  "type": "action_tool",
  "step": 1,
  "tool_name": "list_directory",
  "tool_params": {"path": "C:\\Users\\xxx\\Desktop"},
  "execution_status": "success",
  "summary": "成功读取目录，文件列表：['file1.txt', 'file2.txt', 'folder1']",
  "raw_data": {
    "entries": [
      {"name": "file1.txt", "type": "file", "size": 1024},
      {"name": "file2.txt", "type": "file", "size": 2048},
      {"name": "folder1", "type": "directory"}
    ],
    "total": 3
  }
}
```

**场景2：执行失败（重试后仍失败）**
```json
{
  "type": "action_tool",
  "step": 1,
  "tool_name": "read_file",
  "tool_params": {"path": "C:\\Users\\xxx\\notexist.txt"},
  "execution_status": "error",
  "summary": "读取文件失败，错误原因：文件不存在",
  "raw_data": null,
  "action_retry_count": 3
}
```

**场景3：执行有警告**
```json
{
  "type": "action_tool",
  "step": 1,
  "tool_name": "write_file",
  "tool_params": {"path": "C:\\Users\\xxx\\test.txt", "content": "..."},
  "execution_status": "warning",
  "summary": "文件写入成功，但编码已自动转换为UTF-8",
  "raw_data": {
    "path": "C:\\Users\\xxx\\test.txt",
    "encoding": "utf-8",
    "original_encoding": "gbk"
  }
}
```

---

### 5.3.4 字段详细说明

#### 1. execution_status（执行状态）

**作用**：表示工具执行的整体状态

**取值范围**：

| 值 | 说明 | 场景 |
|---|------|------|
| success | 执行成功 | 正常完成操作 |
| error | 执行失败 | 操作异常或失败 |
| warning | 执行有警告 | 操作完成但有需要注意的情况 |

#### 2. summary（结果描述）

**作用**：人类可读的执行结果摘要，用于显示给用户

**生成规则**：

| execution_status | summary格式 | 示例 |
|-----------------|-------------|------|
| success | `{操作}成功，{结果描述}` | "成功读取目录，文件列表：[...]" |
| error | `{操作}失败，错误原因：{错误信息}` | "读取文件失败，错误原因：文件不存在" |
| warning | `{操作}成功，但{警告信息}` | "文件写入成功，但编码已自动转换为UTF-8" |

#### 3. raw_data（原始数据）

**作用**：机器可读的结构化数据，供后续处理使用

**包含内容**：

| 工具类型 | raw_data内容 |
|----------|-------------|
| list_directory | 目录条目列表、文件数量、文件属性 |
| read_file | 文件内容、编码、行数 |
| write_file | 写入后的文件信息 |
| create_directory | 创建的目录信息 |
| delete_file | 删除操作的结果 |
| move_file | 移动后的路径信息 |
| copy_file | 复制后的路径信息 |

**raw_data为null的情况**：
- execution_status为error时
- 操作不返回数据时

#### 4. action_retry_count（重试次数）

**作用**：记录工具执行失败后的重试次数

**规则**：

| 场景 | action_retry_count值 |
|------|---------------------|
| 首次执行成功 | 0或不返回 |
| 执行1次后成功 | 1 |
| 执行2次后成功 | 2 |
| 执行3次后仍失败 | 3 |

**使用场景**：
- 当工具执行失败时，Agent会自动重试
- action_retry_count记录了重试的次数
- LLM可以根据action_retry_count决定是否继续重试或放弃

---

### 5.3.5 各工具的raw_data结构

| 工具名称 | raw_data结构 |
|----------|-------------|
| list_directory | `{"entries": [...], "total": number}` |
| read_file | `{"content": string, "encoding": string, "lines": number}` |
| write_file | `{"path": string, "size": number, "encoding": string}` |
| create_directory | `{"path": string, "created": boolean}` |
| delete_file | `{"path": string, "deleted": boolean}` |
| move_file | `{"source": string, "destination": string, "moved": boolean}` |
| copy_file | `{"source": string, "destination": string, "copied": boolean}` |

---

### 5.3.6 与7.3章节的字段名称对照

**设计文档字段名 vs 7.3示例字段名**：

| 设计文档字段名 | 7.3示例字段名 | 说明 |
|---------------|--------------|------|
| tool_name | tool_name | ✅ 一致 |
| tool_params | tool_params | ✅ 一致 |
| execution_status | execution_status | ✅ 一致 |
| summary | summary | ✅ 一致 |
| raw_data | raw_data | ✅ 一致 |
| action_retry_count | action_retry_count | ✅ 一致 |

**统一后的7.3示例**：
```json
{
  "type": "action_tool",
  "step": 1,
  "tool_name": "list_directory",
  "tool_params": {"path": "C:\\Users\\xxx\\Desktop"},
  "execution_status": "success",
  "summary": "成功读取目录",
  "raw_data": {"entries": ["file1.txt", "file2.txt"]}
}
```

---

### 5.4 type=observation（对Action执行结果提请LLM判断是否完成loop还是继续loop）

**是 Stage 还是 Type？**
- **Stage**（ReAct循环第3阶段）

**输入**：execution_status + summary + raw_data（来自action_tool阶段）

**处理**：调用LLM（让LLM基于结果继续推理）

**输出（LLM返回）**：content + reasoning + action_tool + params + is_finished

**传导**：content + action_tool + params 传给下一轮Thought阶段

**字段分析**：

| 字段 | 作用 | 必要性 | 合理? | 属于 |
|------|------|--------|-------|-------|
| step | 步骤序号 | 必要 | ✅ | 辅助 |
| execution_status | 执行状态 | 必要 | ✅ | 输入（来自action_tool） |
| summary | 结果描述 | 必要 | ✅ | 输入（来自action_tool） |
| raw_data | 原始数据 | 可选 | ✅ | 输入（来自action_tool） |
| content | LLM的思考内容 | 必要 | ✅ | 输出 |
| reasoning | LLM的推理过程 | 可选 | ✅ | 输出 |
| action_tool | 下一个工具 | 必要 | ✅ | 输出 |
| params | 下一个参数 | 必要 | ✅ | 输出 |
| is_finished | 是否完成任务 | 必要 | ✅ | 输出 |

**结论**：✅ 保留，属于 Stage（同时包含输入和输出两部分）

---

### 5.4.1 observation阶段的输入结构

observation阶段的输入来自action_tool阶段的输出，即action_tool执行完成后返回的结果：

**输入结构**：
```json
{
  "execution_status": "success",
  "summary": "成功读取目录，文件列表：['file1.txt', 'file2.txt']",
  "raw_data": {
    "entries": [
      {"name": "file1.txt", "type": "file", "size": 1024},
      {"name": "file2.txt", "type": "file", "size": 2048}
    ],
    "total": 2
  }
}
```

| 字段 | 类型 | 来源 | 说明 |
|------|------|------|------|
| execution_status | string | action_tool阶段输出 | 执行状态：success/error/warning |
| summary | string | action_tool阶段输出 | 人类可读的结果描述 |
| raw_data | object | action_tool阶段输出 | 机器可读的结构化数据 |

---

### 5.4.2 observation阶段处理流程

observation阶段是ReAct循环的关键连接点，它将action_tool的执行结果反馈给LLM，让LLM决定下一步做什么：

```
action_tool执行完成 → 收到 execution_status + summary + raw_data
    ↓
1. 格式化输入 → 将execution_status/summary/raw_data格式化为文本
2. 构建消息 → 构造给LLM的消息格式
3. 调用LLM → 让LLM基于执行结果继续推理
4. 解析输出 → LLM返回的content + action_tool + params
5. 传导结果 → 将action_tool + params传给下一轮action_tool阶段
```

---

### 5.4.3 observation阶段的输入格式化规则

在将action_tool的输出发送给LLM之前，需要先格式化输入：

**格式化公式**：
```
Observation: {execution_status} - {summary}
```

**具体示例**：

| action_tool执行结果 | 格式化后的输入 |
|--------------------|---------------|
| success | `Observation: success - 成功读取目录，文件列表：[file1.txt, file2.txt]` |
| error | `Observation: error - 读取文件失败，错误原因：文件不存在` |
| warning | `Observation: warning - 文件写入成功，但编码已自动转换为UTF-8` |

**格式化后的完整消息列表示例**：
```json
[
  {"role": "system", "content": "你是一个文件操作助手..."},
  {"role": "user", "content": "帮我查看桌面文件"},        // 第1轮用户输入
  {"role": "assistant", "content": "用户想要查看桌面文件夹..."}, // LLM的思考
  {"role": "user", "content": "Observation: success - 成功读取目录，文件列表：[file1.txt, file2.txt]"},  // action_tool执行结果
  ...
]
```

---

### 5.4.4 observation阶段的LLM反馈JSON结构

LLM收到格式化后的Observation输入后，返回的JSON结构（包含输入和输出两部分）：

**场景1：action_tool执行成功，LLM决定继续执行下一个工具**
```json
{
  "type": "observation",
  "step": 1,
  "execution_status": "success",
  "summary": "成功读取目录",
  "raw_data": {"entries": ["file1.txt", "file2.txt"]},
  "content": "已成功获取桌面文件列表，现在需要读取第一个文件的内容",
  "reasoning": "用户想要查看文件内容，列表中有file1.txt和file2.txt，先读取第一个文件",
  "action_tool": "read_file",
  "params": {"path": "C:\\Users\\xxx\\Desktop\\file1.txt"},
  "is_finished": false
}
```

**场景2：action_tool执行成功，LLM决定结束任务**
```json
{
  "type": "observation",
  "step": 1,
  "execution_status": "success",
  "summary": "成功读取目录",
  "raw_data": {"entries": ["file1.txt", "file2.txt"]},
  "content": "已获取桌面文件列表，共2个文件，现在整理成列表回复用户",
  "reasoning": "文件列表已完整获取，可以回复用户，无需继续操作",
  "action_tool": "finish",
  "params": {},
  "is_finished": true
}
```

**场景3：action_tool执行失败，LLM决定重试**
```json
{
  "type": "observation",
  "step": 1,
  "execution_status": "error",
  "summary": "读取文件失败，错误原因：文件不存在",
  "raw_data": null,
  "content": "文件不存在，需要先确认文件路径是否正确，尝试列出目录查看可用文件",
  "reasoning": "文件读取失败，可能是路径问题，先列出目录确认文件是否存在",
  "action_tool": "list_directory",
  "params": {"path": "C:\\Users\\xxx\\Desktop"},
  "is_finished": false
}
```

**场景4：action_tool执行失败，LLM决定结束任务（无法恢复）**
```json
{
  "type": "observation",
  "step": 1,
  "execution_status": "error",
  "summary": "删除文件失败，错误原因：权限不足",
  "raw_data": null,
  "content": "由于权限不足，无法删除该文件，需要告知用户权限问题",
  "reasoning": "权限错误无法通过重试解决，只能告知用户并结束任务",
  "action_tool": "finish",
  "params": {},
  "is_finished": true
}
```

**场景5：action_tool有警告，LLM继续执行**
```json
{
  "type": "observation",
  "step": 1,
  "execution_status": "warning",
  "summary": "文件写入成功，但编码已自动转换为UTF-8",
  "raw_data": {"path": "C:\\Users\\xxx\\test.txt", "encoding": "utf-8"},
  "content": "文件已成功写入，虽然编码有变化但不影响内容，现在回复用户",
  "action_tool": "finish",
  "params": {}
}
```

---

### 5.4.5 字段详细说明

#### 1. step（步骤序号）

**作用**：标识当前是第几轮循环

**规则**：
- 从1开始计数
- 每执行一轮action_tool，step + 1

#### 2. execution_status（执行状态）

**作用**：来自action_tool阶段的执行状态

**取值**：

| 值 | 来源 | 说明 |
|---|------|------|
| success | action_tool输出 | 执行成功 |
| error | action_tool输出 | 执行失败 |
| warning | action_tool输出 | 执行有警告 |

#### 3. summary（结果描述）

**作用**：来自action_tool阶段的人类可读结果描述

**内容**：直接使用action_tool阶段返回的summary字段

#### 4. raw_data（原始数据）

**作用**：来自action_tool阶段的机器可读数据

**内容**：直接使用action_tool阶段返回的raw_data字段，可能为null

#### 5. content（LLM的新思考）

**作用**：LLM基于action_tool执行结果生成的新思考

**生成规则**：

| execution_status | content内容方向 |
|-----------------|----------------|
| success | 基于成功结果，下一步要做什么 |
| error | 分析错误原因，如何恢复或替代 |
| warning | 处理警告信息，是否有影响 |

#### 6. action_tool（下一个工具）

**作用**：LLM决定的下一步要执行的工具

**取值范围**：

| action_tool | 说明 | 使用场景 |
|-------------|------|---------|
| finish | 完成任务 | 结果已完整，可以回复用户 |
| list_directory | 列出目录 | 需要查看更多文件 |
| read_file | 读取文件 | 需要获取文件内容 |
| write_file | 写入文件 | 需要保存内容 |
| create_directory | 创建目录 | 需要创建新目录 |
| delete_file | 删除文件 | 需要删除文件 |
| move_file | 移动文件 | 需要移动文件位置 |
| copy_file | 复制文件 | 需要复制文件 |
| 其他工具 | 自定义工具 | 根据系统可用工具决定 |

#### 7. params（下一个参数）

**作用**：action_tool要执行的参数

**规则**：
- 与action_tool配套使用
- 如果action_tool是finish，params为空对象{}

#### 8. reasoning（LLM的推理过程）

**作用**：LLM的推理过程，说明为什么会做出当前的决策

**生成场景**：

| 场景 | reasoning示例 |
|------|--------------|
| 继续执行工具 | "用户想要查看文件内容，列表中有file1.txt和file2.txt，先读取第一个文件" |
| 结束任务 | "文件列表已完整获取，可以回复用户，无需继续操作" |
| 错误重试 | "文件读取失败，可能是路径问题，先列出目录确认文件是否存在" |
| 错误结束 | "权限错误无法通过重试解决，只能告知用户并结束任务" |

**重要性**：
- 帮助理解LLM的决策过程
- 便于调试和优化
- 可用于日志记录和分析

#### 9. is_finished（是否完成任务）

**作用**：明确表示当前轮次是否应该结束任务

**取值**：

| 值 | 说明 | 触发条件 |
|---|------|---------|
| true | 任务完成 | action_tool = finish |
| false | 继续执行 | action_tool ≠ finish |

**判断逻辑**：
```
if action_tool == "finish":
    is_finished = true
else:
    is_finished = false
```

**与action_tool的关系**：
- is_finished = true 时，action_tool 必须是 "finish"
- is_finished = false 时，action_tool 不能是 "finish"

---

### 5.4.6 observation阶段完整时间线示例

**示例：查看桌面文件并读取第一个文件**

```
第1轮循环：
  Thought: "用户想要查看桌面文件夹..."
          action_tool: list_directory
          params: {path: "Desktop"}
  
  action_tool: execution_status=success, summary="成功读取目录", raw_data={entries: [file1.txt, file2.txt]}
  
  Observation: LLM收到 "Observation: success - 成功读取目录"
              content: "已获取文件列表，第一个文件是file1.txt，需要读取内容"
              action_tool: read_file
              params: {path: "Desktop/file1.txt"}

第2轮循环：
  Thought: LLM收到 "Observation: success - 已读取文件内容"
          content: "文件内容已获取，现在整理成可读格式回复用户"
          action_tool: finish
          params: {}

  action_tool: execution_status=success, summary="成功读取文件", raw_data={content: "文件内容..."}
  
  Observation: LLM收到 "Observation: success - 成功读取文件"
              content: "任务完成"
              action_tool: finish
              params: {}

  Final: 任务完成
```

---

### 5.4.7 与7.4章节的字段名称对照

**当前5.4字段 vs 7.4示例字段**：

| 5.4字段名 | 7.4示例字段名 | 说明 |
|----------|--------------|------|
| execution_status | execution_status | ✅ 一致 |
| summary | summary | ✅ 一致 |
| raw_data | raw_data | ✅ 一致 |
| content | content | ✅ 一致 |
| reasoning | reasoning | ✅ 一致（新增） |
| action_tool | action_tool | ✅ 一致 |
| params | params | ✅ 一致 |
| is_finished | is_finished | ✅ 一致（新增） |

**7.4完整示例**：
```json
{
  "type": "observation",
  "step": 1,
  "execution_status": "success",
  "summary": "成功读取目录",
  "raw_data": {"entries": ["file1.txt", "file2.txt"]},
  "content": "已获取目录内容，现在整理成列表回复用户",
  "reasoning": "文件列表已完整获取，可以回复用户，无需继续操作",
  "action_tool": "finish",
  "params": {},
  "is_finished": true
}
```
{
  "type": "observation",
  "step": 1,
  "execution_status": "success",
  "summary": "成功读取目录",
  "raw_data": {"entries": ["file1.txt", "file2.txt"]},
  "content": "已获取目录内容，现在整理成列表回复用户",
  "action_tool": "finish",
  "params": {}
}
```

---

### 5.5 type=final（最终回复）

**是 Stage 还是 Type？**
- **Stage**（ReAct循环结束后的最终输出）

**输入**：ReAct循环结束后的结果

**处理**：整理最终回复（不需要再调用LLM）

**输出**：content

**传导**：无（结束）

**字段分析**：

| 字段 | 作用 | 必要性 | 合理? |
|------|------|--------|-------|
| content | 完整回复 | 必要 | ✅ |

**结论**：✅ 保留，字段完整，属于 Stage

---

### 5.6 type=chunk（流式内容）

**是 Stage 还是 Type？**
- **Type**（流式输出，不参与 ReAct 循环）

**与什么有关系？**

| 关联 | 说明 |
|------|------|
| **LLM 流式输出** | LLM 生成回复时是逐 token 生成的 |
| **前端显示** | 实现"打字机效果"，让用户看到正在输出 |

**为什么需要？**

| 原因 | 说明 |
|------|------|
| **用户体验** | 用户不用等待完整回复，看到逐字输出 |
| **响应更快** | 及时显示，不用等 LLM 生成完整内容 |
| **打字机效果** | 模拟人类打字，给用户更好的交互感 |

**什么情况下使用？**

| 场景 | 使用 | 说明 |
|------|------|-------|
| **普通对话** | ✅ 使用 | AI 生成文本时逐块返回 |
| **ReAct 文件操作** | ❌ 不使用 | 只有 thought/action_tool/observation，最后直接 final |

**解决什么问题？**

- 解决用户等待时间过长的问题
- 提供实时反馈
- 增强交互体验

**与 ReAct 的关系**：
- **chunk 是 ReAct 循环之外的辅助 type**
- ReAct 过程中不需要 chunk
- chunk 只用于普通对话的流式显示

**流式接口 vs 非流式接口**：

| 接口类型 | 是否需要 chunk | 说明 |
|----------|----------------|------|
| **流式接口** | ✅ 需要 | LLM 逐块返回，用 chunk 逐块显示 |
| **非流式接口** | ❌ 不需要 | LLM 一次性返回完整内容，直接显示 |

```
流式接口：
  LLM → chunk1 → chunk2 → chunk3 → final
                 ↓           ↓        ↓
              前端显示    前端显示   前端显示

非流式接口：
  LLM → 直接返回完整内容 → 前端一次性显示
```

**chunk 是专门解决流式接口的输出显示问题**，用于普通对话场景。

**输入**：无（直接来自 LLM 流式响应）

**输出**：content + is_reasoning + chunk_reasoning

**传导**：不传导到下一阶段

**字段分析**：

| 字段 | 作用 | 必要性 | 合理? | 备注 |
|------|------|--------|-------|------|
| content | 回复片段 | 必要 | ✅ | |
| is_reasoning | 是否思考 | 可选 | ✅ | |
| chunk_reasoning | 思考内容 | 可选 | ✅ 已统一为chunk_reasoning，避免与thought的reasoning混淆 |

**结论**：✅ 保留，字段完整，属于 Type（用于普通对话，ReAct过程不需要）

---

### 5.7 type=error（错误）

**是 Stage 还是 Type？**
- **Type**（错误状态，不参与循环）

**输入**：无

**输出**：code + message + error_type + details + retryable

**传导**：不传导到下一阶段

**字段分析**：

| 字段 | 作用 | 必要性 | 合理? |
|------|------|--------|-------|
| code | 错误码 | 必要 | ✅ |
| message | 错误消息 | 必要 | ✅ |
| error_type | 错误类型 | 可选 | ✅ 补充 |
| details | 详细错误信息 | 可选 | ✅ 补充 |
| stack | 堆栈信息 | 可选 | ✅ 补充（仅调试用） |
| retryable | 是否可重试 | 可选 | ✅ 新增，告诉前端是否可重试 |
| retry_after | 重试等待秒数 | 可选 | ✅ 新增，配合retryable使用 |

**错误分类设计**：

```json
// 可重试错误（临时性问题，如网络抖动）
{
  "type": "error",
  "code": "NETWORK_TIMEOUT",
  "message": "网络请求超时",
  "error_type": "network",
  "retryable": true,
  "retry_after": 5
}

// 不可重试错误（永久性问题，如文件不存在）
{
  "type": "error",
  "code": "FILE_NOT_FOUND",
  "message": "文件不存在",
  "error_type": "file_system",
  "retryable": false
}
```

**retryable取值**：

| 值 | 说明 | 典型场景 |
|----|------|---------|
| true | 可重试 | 网络超时、服务不可用、临时性错误 |
| false | 不可重试 | 文件不存在、权限不足、参数错误 |

**结论**：✅ 保留，字段完整，属于 Type，新增retryable字段支持错误分类

---

### 5.8 type=status 说明

**分析**：interrupted、paused、resumed、retrying 都是Agent内部执行状态，与LLM无直接关系。

**整合方案**：整合为一个统一的 **type=status** 类型，用 `status_value` 字段区分具体状态。

**整合后的字段设计**：

| 字段 | 作用 | 必要性 | 合理? |
|------|------|--------|-------|
| status_value | 具体状态值 | 必要 | ✅ |
| message | 状态消息 | 必要 | ✅ |

**status_value取值**：

| 值 | 说明 | 对应原type |
|---|------|-----------|
| interrupted | 任务中断 | 5.8 |
| paused | 任务暂停 | 5.9 |
| resumed | 任务恢复 | 5.10 |
| retrying | 任务重试中 | 5.11 |

**结论**：✅ 整合为一个统一的status类型

---

## 六、type整合总结

### 6.1 整合后的type列表

| 序号 | type | 说明 | 与LLM关系 |
|------|------|------|----------|
| 1 | start | 任务开始（含安全检查） | 初始化+安全检查 |
| 2 | thought | LLM推理 | ✅ 直接相关 |
| 3 | action_tool | 执行动作 | 输入来自LLM，本地执行 |
| 4 | observation | 执行结果判断 | ✅ 直接相关 |
| 5 | final | 最终回复 | ✅ 直接相关 |
| 6 | chunk | 流式内容片段 | ✅ 直接相关（LLM输出） |
| 7 | error | 错误状态 | Agent相关 |
| 8 | status | Agent执行状态 | Agent相关 |

### 6.2 整合说明

| 原type | 整合后 | 说明 |
|--------|--------|------|
| interrupted | status | ✅ 整合 |
| paused | status | ✅ 整合 |
| resumed | status | ✅ 整合 |
| retrying | status | ✅ 整合 |

### 6.3 整合后的status字段

```json
{
  "type": "status",
  "status_value": "paused",
  "message": "任务已暂停"
}
```

| status_value | 说明 |
|-------------|------|
| interrupted | 任务被中断 |
| paused | 任务暂停中 |
| resumed | 任务已恢复 |
| retrying | 任务重试中 |

---

## 七、各type详细设计

### 7.1 start - 任务开始（含安全检查）

**说明**：任务初始化阶段，不是ReAct循环的一部分。包含初始化和安全检查两个子阶段。

**JSON示例**：
```json
{
  "type": "start",
  "display_name": "OpenAI (gpt-4)",
  "model": "gpt-4",
  "provider": "openai",
  "task_id": "abc123",
  "security_check": {
    "is_safe": true,
    "risk_level": null,
    "risk": null,
    "blocked": false
  }
}
```

**字段说明**：

| 字段 | 类型 | 必要性 | 说明 |
|------|------|--------|------|
| type | string | 固定值 | 固定为 "start" |
| display_name | string | 必要 | AI显示名称，如 "OpenAI (gpt-4)" |
| model | string | 必要 | AI模型，如 "gpt-4"、"gpt-4o" |
| provider | string | 必要 | AI提供商，如 "openai"、"anthropic" |
| task_id | string | 必要 | 唯一标识一次用户请求，用于追踪调试 |
| security_check | object | 必要 | 本次请求的安全检查结果 |

**security_check 字段说明**：

| 字段 | 类型 | 必要性 | 说明 |
|------|------|--------|------|
| is_safe | boolean | 必要 | true=安全，false=危险 |
| risk_level | string/null | 可选 | low/medium/high/critical，无风险时为null |
| risk | string/null | 可选 | 风险描述，无风险时为null |
| blocked | boolean | 必要 | true=已拦截，不执行LLM |

**处理流程**：
```
用户发送消息 → 安全检查（规则检查） → 文件操作意图检测 → 进入ReAct循环
```

---

### 7.2 thought - LLM思考（Stage）

**说明**：ReAct循环第1阶段。输入是用户输入或上一轮Observation结果，输出是LLM返回的content + action_tool + params。

**JSON示例**：
```json
{
  "type": "thought",
  "step": 1,
  "content": "用户想要查看桌面文件夹...",
  "reasoning": "用户提到了'查看'和'文件夹'，这是目录列表操作",
  "action_tool": "list_directory",
  "params": {"path": "C:\\Users\\xxx\\Desktop"}
}
```

**字段说明**：

| 字段 | 类型 | 必要性 | 说明 |
|------|------|--------|------|
| type | string | 固定值 | 固定为 "thought" |
| step | number | 必要 | 当前是第几轮ReAct循环，从1开始 |
| content | string | 必要 | LLM的思考内容，说明当前分析和下一步意图 |
| reasoning | string | 可选 | LLM的推理过程，说明为什么会做此决策 |
| action_tool | string | 必要 | 要执行的工具名称，如 list_directory、finish |
| params | object | 必要 | 工具执行的参数，可为空对象{} |

**输入来源**：

| 轮次 | 输入来源 | 输入格式 |
|------|----------|----------|
| 第1轮 | 用户消息 | role=user, content=用户原始输入 |
| 后续轮次 | conversation_history | role=user, content=`Observation: {status} - {message}` |

**处理流程**：
```
输入（用户消息或Observation结果） → 构建消息列表 → 调用LLM → 解析LLM返回 → 输出content+action_tool+params
```

**传导**：action_tool + params 传给 Action阶段

---

### 7.3 action_tool - 执行动作（Stage）

**说明**：ReAct循环第2阶段。输入是Thought阶段的tool_name + tool_params，输出是execution_status + summary + raw_data。

**JSON示例**：
```json
{
  "type": "action_tool",
  "step": 1,
  "tool_name": "list_directory",
  "tool_params": {"path": "C:\\Users\\xxx\\Desktop"},
  "execution_status": "success",
  "summary": "成功读取目录，文件列表：['file1.txt', 'file2.txt']",
  "raw_data": {
    "entries": [
      {"name": "file1.txt", "type": "file", "size": 1024},
      {"name": "file2.txt", "type": "file", "size": 2048}
    ],
    "total": 100000,
    "has_more": true,
    "next_page_token": "abc123"
  }
}
```

**分页支持说明**：

当返回数据量较大时（如列出目录有100000个文件），使用分页避免前端卡死：

```json
{
  "raw_data": {
    "entries": [
      {"name": "file1.txt", ...},
      ...  // 只返回前 100 个
    ],
    "total": 100000,           // 总共 100000 个
    "has_more": true,          // 还有更多
    "next_page_token": "abc123"  // 下一页令牌
  }
}
```

**raw_data分页字段**：

| 字段 | 类型 | 必要性 | 说明 |
|------|------|--------|------|
| entries | array | 必要 | 数据条目数组 |
| total | number | 可选 | 总数据量（当启用分页时返回） |
| has_more | boolean | 可选 | 是否有更多数据 |
| next_page_token | string | 可选 | 下一页令牌，用于获取下一批数据 |

**前端处理分页**：

1. 首次请求：后端返回前100条 + has_more=true + next_page_token
2. 用户滚动到底部：前端用next_page_token请求下一页
3. 直到has_more=false，表示数据全部加载完成

**字段说明**：

| 字段 | 类型 | 必要性 | 说明 |
|------|------|--------|------|
| type | string | 固定值 | 固定为 "action_tool" |
| step | number | 必要 | 步骤序号，从1开始计数 |
| tool_name | string | 必要 | 工具名称，来自Thought阶段 |
| tool_params | object | 必要 | 工具参数，来自Thought阶段 |
| execution_status | string | 必要 | 执行状态：success/error/warning |
| summary | string | 必要 | 人类可读的执行结果摘要 |
| raw_data | object/null | 可选 | 机器可读的结构化数据 |
| action_retry_count | number | 可选 | 重试次数，0=首次执行 |

**execution_status 取值**：

| 值 | 说明 | 场景 |
|---|------|------|
| success | 执行成功 | 正常完成操作 |
| error | 执行失败 | 操作异常或失败 |
| warning | 执行有警告 | 操作完成但有需要注意的情况 |

**各工具的raw_data结构**：

| 工具名称 | raw_data结构 |
|----------|-------------|
| list_directory | `{"entries": [...], "total": number, "has_more": bool, "next_page_token": string}` |
| read_file | `{"content": string, "encoding": string, "lines": number}` |
| write_file | `{"path": string, "size": number, "encoding": string}` |
| create_directory | `{"path": string, "created": boolean}` |
| delete_file | `{"path": string, "deleted": boolean}` |
| move_file | `{"source": string, "destination": string, "moved": boolean}` |
| copy_file | `{"source": string, "destination": string, "copied": boolean}` |

> **说明**：list_directory 工具支持分页，当数据量超过单次返回限制时，返回 `has_more: true` 和 `next_page_token`，前端可循环请求获取完整数据。

**处理流程**：
```
tool_name + tool_params → 解析工具名称 → 校验参数 → 调用工具函数 → 捕获执行结果 → 组装输出
```

**传导**：execution_status + summary + raw_data 作为Observation的输入

---

### 7.4 observation - 执行结果（Stage）

**说明**：ReAct循环第3阶段。输入是action_tool的执行结果，输出是LLM返回的content + reasoning + action_tool + params + is_finished。同时包含输入和输出两部分。

**JSON示例**：
```json
{
  "type": "observation",
  "step": 1,
  "execution_status": "success",
  "summary": "成功读取目录",
  "raw_data": {"entries": ["file1.txt", "file2.txt"]},
  "content": "已获取目录内容，现在整理成列表回复用户",
  "action_tool": "finish",
  "params": {}
}
```

**字段说明**：

| 字段 | 类型 | 必要性 | 说明 |
|------|------|--------|------|
| type | string | 固定值 | 固定为 "observation" |
| step | number | 必要 | 步骤序号，与action_tool对应 |
| execution_status | string | 必要 | 执行状态，来自action_tool输出 |
| summary | string | 必要 | 结果描述，来自action_tool输出 |
| raw_data | object/null | 可选 | 原始数据，来自action_tool输出 |
| content | string | 必要 | LLM基于结果生成的新思考 |
| reasoning | string | 可选 | LLM的推理过程，说明为什么做此决策 |
| action_tool | string | 必要 | LLM决定的下一步工具 |
| params | object | 必要 | 工具参数 |
| is_finished | boolean | 必要 | 是否完成任务：true=结束，false=继续 |

**输入格式化规则**：
```
Observation: {execution_status} - {summary}
```

**action_tool 取值范围**：

| action_tool | 说明 |
|-------------|------|
| finish | 完成任务 |
| list_directory | 列出目录 |
| read_file | 读取文件 |
| write_file | 写入文件 |
| create_directory | 创建目录 |
| delete_file | 删除文件 |
| move_file | 移动文件 |
| copy_file | 复制文件 |

**is_finished 判断逻辑**：
```
if action_tool == "finish": is_finished = true
else: is_finished = false
```

**处理流程**：
```
action_tool执行结果 → 格式化输入 → 构建消息 → 调用LLM → 解析LLM返回 → 传导到下一轮Thought
```

**传导**：content + action_tool + params 传给下一轮Thought阶段

---

### 7.5 final - 最终回复

**说明**：ReAct循环结束后的最终输出。不需要再调用LLM，直接整理最终回复给用户。

**JSON示例**：
```json
{
  "type": "final",
  "content": "桌面有文件：github_ping.log, github_trace.log..."
}
```

**字段说明**：

| 字段 | 类型 | 必要性 | 说明 |
|------|------|--------|------|
| type | string | 固定值 | 固定为 "final" |
| content | string | 必要 | 完整回复内容 |

**触发条件**：
- LLM在observation阶段返回 action_tool = "finish"
- 任务执行失败，需要告知用户错误信息
- 达到最大迭代次数

**处理流程**：
```
ReAct循环结束 → 整理最终回复 → 输出final → 任务结束
```

---

### 7.6 chunk - 流式内容

**说明**：LLM流式输出时的内容片段。不参与ReAct循环，专门用于普通对话场景的流式显示。

**JSON示例**：
```json
{
  "type": "chunk",
  "content": "这是回复片段",
  "is_reasoning": false,
  "chunk_reasoning": "用户问你好，我应该礼貌回复"
}
```

**字段说明**：

| 字段 | 类型 | 必要性 | 说明 |
|------|------|--------|------|
| type | string | 固定值 | 固定为 "chunk" |
| content | string | 必要 | 回复片段内容 |
| is_reasoning | boolean | 可选 | 是否在思考阶段 |
| chunk_reasoning | string | 可选 | 思考内容（避免与thought的reasoning混淆） |

**使用场景**：

| 场景 | 是否使用chunk | 说明 |
|------|---------------|------|
| 普通对话 | ✅ 使用 | AI生成文本时逐块返回 |
| ReAct文件操作 | ❌ 不使用 | 只有thought/action_tool/observation，最后直接final |

**与ReAct的关系**：
- chunk是ReAct循环之外的辅助type
- ReAct过程中不需要chunk
- chunk只用于普通对话的流式显示

**流式接口 vs 非流式接口**：

| 接口类型 | 是否需要chunk |
|----------|---------------|
| 流式接口 | ✅ 需要 |
| 非流式接口 | ❌ 不需要 |

---

### 7.7 error - 错误

**说明**：错误状态，不参与循环。用于报告系统错误、安全拦截等。

**JSON示例**：
```json
{
  "type": "error",
  "code": "TIMEOUT",
  "message": "请求超时，请重试",
  "error_type": "network",
  "details": "连接远程服务器超时",
  "stack": "Traceback (most recent call last):\n  File \"...\""
}
```

**字段说明**：

| 字段 | 类型 | 必要性 | 说明 |
|------|------|--------|------|
| type | string | 固定值 | 固定为 "error" |
| code | string | 必要 | 错误码，如 TIMEOUT、NOT_FOUND、SECURITY_BLOCKED |
| message | string | 必要 | 用户可读的错误消息 |
| error_type | string | 可选 | 错误类型，如 network、file_system、validation |
| details | string | 可选 | 详细错误信息 |
| stack | string | 可选 | 堆栈信息（仅用于调试） |

**code 取值建议**：

| code | 说明 |
|------|------|
| TIMEOUT | 请求超时 |
| NOT_FOUND | 资源不存在 |
| PERMISSION_DENIED | 权限不足 |
| SECURITY_BLOCKED | 安全拦截 |
| VALIDATION_ERROR | 参数验证错误 |
| INTERNAL_ERROR | 内部错误 |

**触发场景**：
- 安全规则拦截危险命令
- LLM调用超时
- 文件操作失败
- 参数验证错误

---

### 7.8 status - Agent执行状态（整合自原5.8-5.11）

**说明**：Agent内部执行状态，与LLM无直接关系。整合了interrupted、paused、resumed、retrying四个状态。

**JSON示例**：

| 状态 | JSON |
|------|------|
| 中断 | `{"type": "status", "status_value": "interrupted", "message": "任务已被中断"}` |
| 暂停 | `{"type": "status", "status_value": "paused", "message": "任务已暂停"}` |
| 恢复 | `{"type": "status", "status_value": "resumed", "message": "任务已恢复"}` |
| 重试中 | `{"type": "status", "status_value": "retrying", "message": "正在重试..."}` |

**字段说明**：

| 字段 | 类型 | 必要性 | 说明 |
|------|------|--------|------|
| type | string | 固定值 | 固定为 "status" |
| status_value | string | 必要 | 具体状态值：interrupted/paused/resumed/retrying |
| message | string | 必要 | 状态消息，人类可读 |

**status_value 取值说明**：

| 值 | 说明 | 触发场景 |
|---|------|----------|
| interrupted | 任务中断 | 用户主动中断、安全拦截、达到最大迭代 |
| paused | 任务暂停 | 等待用户确认、等待资源 |
| resumed | 任务恢复 | 用户确认后继续、资源可用 |
| retrying | 任务重试 | 工具执行失败自动重试 |

**状态流转关系**：
```
running → paused → resumed → running
running → interrupted → 结束
running → retrying → running
```

---

### 7.9 完整时间线示例

#### 7.9.1 普通对话时间线

```
用户发送: "你好"
    ↓
{ "type": "start", "display_name": "OpenAI (gpt-4)", "task_id": "xxx", ... }
    ↓
{ "type": "thought", "content": "用户问你好，我应该礼貌回复", "action_tool": "finish", "params": {} }
    ↓
{ "type": "chunk", "content": "你" }
{ "type": "chunk", "content": "好" }
{ "type": "chunk", "content": "！" }
    ↓
{ "type": "final", "content": "你好！有什么可以帮助你的？" }
    ↓
任务结束
```

**JSON流示例**：
```json
{ "type": "start", "display_name": "OpenAI (gpt-4)", "task_id": "abc123", "security_check": {...} }
{ "type": "thought", "content": "用户问你好，我应该礼貌回复", "action_tool": "finish", "params": {} }
{ "type": "chunk", "content": "你", "is_reasoning": false }
{ "type": "chunk", "content": "好", "is_reasoning": false }
{ "type": "chunk", "content": "！", "is_reasoning": false }
{ "type": "final", "content": "你好！有什么可以帮助你的？" }
```

---

#### 7.9.2 文件操作时间线

```
用户发送: "帮我查看桌面文件夹"
    ↓
{ "type": "start", ... }
    ↓
{ "type": "thought", "content": "用户想要查看桌面文件夹，我需要先列出桌面目录的内容", 
  "action_tool": "list_directory", "params": {"path": "Desktop"} }
    ↓
{ "type": "action_tool", "step": 1, "tool_name": "list_directory", 
  "tool_params": {"path": "Desktop"}, "execution_status": "success", 
  "summary": "成功读取目录", "raw_data": {...} }
    ↓
{ "type": "observation", "step": 1, "execution_status": "success", 
  "summary": "成功读取目录", "raw_data": {...}, 
  "content": "已获取目录内容，现在整理成列表回复用户",
  "action_tool": "finish", "params": {} }
    ↓
{ "type": "final", "content": "桌面有文件：github_ping.log, github_trace.log..." }
    ↓
任务结束
```

**JSON流示例**：
```json
{ "type": "start", "display_name": "OpenAI (gpt-4)", "task_id": "abc123", "security_check": {...} }
{ "type": "thought", "content": "用户想要查看桌面文件夹，我需要先列出桌面目录的内容", "action_tool": "list_directory", "params": {"path": "Desktop"} }
{ "type": "action_tool", "step": 1, "tool_name": "list_directory", "tool_params": {"path": "Desktop"}, "execution_status": "success", "summary": "成功读取目录，文件列表：['file1.txt', 'file2.txt', 'folder1']", "raw_data": {"entries": [...], "total": 3} }
{ "type": "observation", "step": 1, "execution_status": "success", "summary": "成功读取目录", "raw_data": {"entries": [...], "total": 3}, "content": "已获取目录内容，现在整理成列表回复用户", "action_tool": "finish", "params": {} }
{ "type": "final", "content": "桌面有文件：file1.txt, file2.txt, folder1" }
```

---

#### 7.9.3 多轮文件操作时间线

```
用户发送: "帮我查看桌面，然后读取第一个文件"
    ↓
{ "type": "start", ... }
    ↓
【第1轮循环】
{ "type": "thought", "content": "用户想要查看桌面文件夹，我需要先列出桌面目录的内容", 
  "action_tool": "list_directory", "params": {"path": "Desktop"} }
    ↓
{ "type": "action_tool", "step": 1, "tool_name": "list_directory", 
  "tool_params": {"path": "Desktop"}, "execution_status": "success", 
  "summary": "成功读取目录", "raw_data": {"entries": ["file1.txt", "file2.txt"], "total": 2} }
    ↓
{ "type": "observation", "step": 1, "execution_status": "success", 
  "summary": "成功读取目录", "raw_data": {...}, 
  "content": "已获取桌面文件列表，第一个文件是file1.txt，现在需要读取它的内容",
  "action_tool": "read_file", "params": {"path": "Desktop/file1.txt"} }
    ↓
【第2轮循环】
{ "type": "thought", "content": "已获取文件列表，现在读取第一个文件的内容", 
  "action_tool": "read_file", "params": {"path": "Desktop/file1.txt"} }
    ↓
{ "type": "action_tool", "step": 2, "tool_name": "read_file", 
  "tool_params": {"path": "Desktop/file1.txt"}, "execution_status": "success", 
  "summary": "成功读取文件", "raw_data": {"content": "文件内容...", "lines": 10} }
    ↓
{ "type": "observation", "step": 2, "execution_status": "success", 
  "summary": "成功读取文件", "raw_data": {...}, 
  "content": "已获取文件内容，现在整理成可读格式回复用户",
  "action_tool": "finish", "params": {} }
    ↓
{ "type": "final", "content": "桌面有两个文件：file1.txt 和 file2.txt。第一个文件 file1.txt 的内容是：..." }
    ↓
任务结束
```

---

#### 7.9.4 错误处理时间线

```
用户发送: "帮我读取不存在的文件"
    ↓
{ "type": "start", ... }
    ↓
{ "type": "thought", "content": "用户想要读取文件，我先尝试读取指定路径", 
  "action_tool": "read_file", "params": {"path": "Desktop/notexist.txt"} }
    ↓
{ "type": "action_tool", "step": 1, "tool_name": "read_file", 
  "tool_params": {"path": "Desktop/notexist.txt"}, "execution_status": "error", 
  "summary": "读取文件失败，错误原因：文件不存在", "raw_data": null, "action_retry_count": 0 }
    ↓
{ "type": "observation", "step": 1, "execution_status": "error", 
  "summary": "读取文件失败，错误原因：文件不存在", "raw_data": null,
  "content": "文件不存在，需要先确认文件路径是否正确",
  "action_tool": "finish", "params": {}, "is_finished": true }
    ↓
{ "type": "final", "content": "读取文件失败：文件不存在。请检查文件路径是否正确。" }
    ↓
任务结束（失败）
```

---

#### 7.9.5 带安全检查的时间线

```
用户发送: "删除 C:\Windows\System32"
    ↓
{ "type": "start", "security_check": {...} }
    ↓
【安全检查阶段】
{ "type": "status", "status_value": "interrupted", "message": "危险命令已拦截：检测到系统关键目录操作" }
    ↓
{ "type": "error", "code": "SECURITY_BLOCKED", "message": "检测到危险命令，已被安全规则拦截" }
    ↓
任务结束
```

---

#### 7.9.6 带用户确认的时间线

```
用户发送: "删除桌面上的 test.txt"
    ↓
{ "type": "start", ... }
    ↓
{ "type": "thought", "content": "用户想要删除文件，我需要先确认文件是否存在", 
  "action_tool": "list_directory", "params": {"path": "Desktop"} }
    ↓
{ "type": "action_tool", ... }
    ↓
{ "type": "observation", ... "content": "检测到删除操作，需要用户确认", 
  "action_tool": "finish", ... }
    ↓
{ "type": "status", "status_value": "paused", "message": "等待用户确认：确定要删除 test.txt 吗？" }
    ↓
【用户点击"确认"】
{ "type": "status", "status_value": "resumed", "message": "用户已确认，继续执行" }
    ↓
【继续执行删除操作】
...
```

---

## 八、后端代码重构升级详细说明

**编写人**: 小沈
**编写时间**: 2026-03-09 14:11:11

---

### 8.1 重构目标概述

本次后端代码重构的核心目标是：**实现真正的实时流式推送，遵守ReAct循环的三个独立阶段原则，消除硬编码和嵌套错误**。

#### 8.1.1 需要重构的文件清单

| 序号 | 文件路径 | 作用 | 重构优先级 |
|------|---------|------|-----------|
| 1 | `backend/app/api/v1/chat.py` | API入口，SSE流式响应 | 🔴 高 |
| 2 | `backend/app/services/file_operations/agent.py` | ReAct Agent核心逻辑 | 🔴 高 |
| 3 | `backend/app/services/file_operations/adapter.py` | 参数类型适配器 | 🟡 中 |
| 4 | `backend/app/services/file_operations/tools.py` | 文件操作工具集 | 🟡 中 |
| 5 | `backend/app/services/file_operations/safety.py` | 安全检查模块 | 🟡 中 |

---

### 8.2 chat.py 重构详细说明

#### 8.2.1 当前问题诊断

| 问题编号 | 问题描述 | 位置 | 影响 |
|---------|---------|------|------|
| P8-001 | 第一个thought硬编码 | chat.py:697-702 | 违反ReAct原则，LLM推理被跳过 |
| P8-002 | 第一个action_tool硬编码 | chat.py:721-723 | 违反ReAct原则 |
| P8-003 | 推送时机错误（批量模式） | chat.py:780 | 等所有轮次执行完才推送，非实时 |
| P8-004 | observation嵌套thought/action_tool | chat.py:observation字段 | 数据结构混乱 |
| P8-005 | 错误响应字段不一致 | create_error_response函数 | error_type/error_message命名混乱 |

#### 8.2.2 重构方案

##### 8.2.2.1 移除硬编码，实现真正的LLM推理

**当前代码（错误）**：
```python
# ❌ 硬编码的第一个thought
first_thought = "正在分析任务..."
yield f"data: {json.dumps({'type': 'thought', 'content': first_thought})}\n\n"

# ❌ 硬编码的第一个action_tool  
first_action = "检测到文件操作意图..."
yield f"data: {json.dumps({'type': 'action_tool', 'action_tool_description': first_action})}\n\n"
```

**重构后代码（正确）**：
```python
# ✅ 正确流程：调用LLM获取第一个thought
# 1. 构建消息列表（用户输入）
messages = [
    {"role": "system", "content": system_prompt},
    {"role": "user", "content": user_input}
]

# 2. 调用LLM
llm_response = await llm_service.chat(messages)

# 3. 解析LLM返回的JSON
parsed = json.loads(llm_response)
thought_content = parsed.get("content")
action_tool = parsed.get("action_tool")
params = parsed.get("params", {})

# 4. 实时推送thought
yield f"data: {json.dumps({'type': 'thought', 'content': thought_content, 'action_tool': action_tool, 'params': params})}\n\n"

# 5. 执行action_tool
# ... 执行代码 ...

# 6. 实时推送action_tool结果
yield f"data: {json.dumps({'type': 'action_tool', 'step': 1, 'tool_name': action_tool, 'tool_params': params, 'execution_status': 'success', 'summary': '...'})}\n\n"
```

##### 8.2.2.2 实现真正的实时流式推送

**当前代码（错误）**：
```python
# ❌ 批量模式：等所有轮次执行完才推送
result = await agent.run()  # 阻塞等待所有轮次完成

for step in result.steps:   # 然后才一个个推送
    yield f"data: {json.dumps(step)}\n\n"
```

**重构后代码（正确）**：
```python
# ✅ 实时模式：每轮循环完成后立即推送
async for event in agent.run_stream():
    # event可能是：
    # - {"type": "thought", "content": "...", "action_tool": "...", "params": {...}}
    # - {"type": "action_tool", "step": 1, "tool_name": "...", "execution_status": "success", ...}
    # - {"type": "observation", "step": 1, ...}
    yield f"data: {json.dumps(event)}\n\n"
```

##### 8.2.2.3 统一错误响应格式

**重构后的错误响应格式**：
```python
def create_error_response(
    error_type: str,
    message: str,
    code: str = "INTERNAL_ERROR",
    details: Optional[str] = None,
    stack: Optional[str] = None
) -> str:
    """
    统一的错误响应格式
    
    字段说明：
    - type: 固定为 "error"
    - code: 错误码（如 TIMEOUT, NOT_FOUND, SECURITY_BLOCKED）
    - message: 用户可读的错误消息
    - error_type: 错误类型（如 network, file_system, validation）
    - details: 详细错误信息（可选）
    - stack: 堆栈信息（可选，仅用于调试）
    """
    response = {
        'type': 'error',
        'code': code,
        'message': message,
        'error_type': error_type
    }
    if details:
        response['details'] = details
    if stack:
        response['stack'] = stack
    return f"data: {json.dumps(response)}\n\n"
```

---

#### 8.2.2.4 其他需要修改的辅助函数

根据调试分析，以下辅助函数也需要配合新的数据结构进行修改：

##### C2 get_user_friendly_error 函数修改

**作用**：将错误转换为用户友好的格式

**需要配合修改**：
- 新的错误格式使用 `code` 和 `message` 字段
- 需要适配新的 `error_type` 分类

```python
def get_user_friendly_error(error: Exception) -> Dict[str, Any]:
    """
    将系统错误转换为用户友好的错误格式
    
    Returns:
        {
            "code": "FILE_NOT_FOUND",
            "message": "用户可读的错误消息",
            "error_type": "file_system"
        }
    """
    # 根据错误类型映射到新的错误格式
    pass
```

##### C3 check_and_yield_if_interrupted 函数修改

**作用**：检查任务是否被中断，配合新的status类型

**需要配合修改**：
- 使用新的 `type: "status", status_value: "interrupted"` 格式

##### C4 check_and_yield_if_paused 函数修改

**作用**：检查任务是否暂停，配合新的status类型

**需要配合修改**：
- 使用新的 `type: "status", status_value: "paused"` 格式

##### C5 simplify_observation 函数修改

**作用**：简化观察结果，配合新的observation格式

**需要配合修改**：
- 新的observation格式包含：`content`, `reasoning`, `action_tool`, `params`, `is_finished`

##### C6 detect_file_operation_intent 函数修改

**作用**：检测文件操作意图

**需要配合修改**：
- 更新返回格式以适配新的数据结构

##### C7 extract_file_path 函数修改

**作用**：从用户输入中提取文件路径

**需要配合修改**：
- 可能需要增强以支持更多路径格式

##### C8 cancel_stream_task 函数修改

**作用**：取消正在进行的流式任务

**需要配合修改**：
- 取消时发送 `type: "status", status_value: "interrupted"`

##### C9 pause_stream_task 函数修改

**作用**：暂停流式任务

**需要配合修改**：
- 暂停时发送 `type: "status", status_value: "paused"`

##### C10 resume_stream_task 函数修改

**作用**：恢复暂停的任务

**需要配合修改**：
- 恢复时发送 `type: "status", status_value: "resumed"`

##### C11 handle_file_operation 函数修改

**作用**：处理文件操作请求

**需要配合修改**：
- 更新返回格式以包含 `execution_status` 字段

---

### 8.3 agent.py 重构详细说明

#### 8.3.1 当前问题诊断

| 问题编号 | 问题描述 | 位置 | 影响 |
|---------|---------|------|------|
| P8-006 | Step类字段不完整 | agent.py:Step类 | 缺少reasoning、is_finished等字段 |
| P8-007 | 阻塞式执行 | agent.run()方法 | 没有实现异步流式输出 |
| P8-008 | 缺少安全检查集成 | agent.run() | 安全检查没有在Agent中体现 |
| P8-009 | action_tool命名不一致 | 多个位置 | 有时用action有时用tool_name |

#### 8.3.2 重构方案

##### 8.3.2.1 重新设计Step类

**当前代码（不完整）**：
```python
@dataclass
class Step:
    step_number: int
    thought: str
    action: str
    action_input: Dict[str, Any]
    observation: Optional[Dict[str, Any]] = None
```

**重构后代码（完整）**：
```python
@dataclass
class ThoughtStep:
    """Thought阶段的数据结构"""
    step_number: int
    content: str                              # LLM的思考内容
    reasoning: Optional[str] = None           # LLM的推理过程（可选）
    action_tool: str = ""                     # 要执行的工具名称
    params: Dict[str, Any] = field(default_factory=dict)  # 工具参数


@dataclass
class ActionToolStep:
    """Action阶段的数据结构"""
    step_number: int
    tool_name: str                            # 工具名称（统一命名）
    tool_params: Dict[str, Any] = field(default_factory=dict)  # 工具参数
    execution_status: str = "success"         # 执行状态：success/error/warning
    summary: str = ""                         # 人类可读的结果描述
    raw_data: Optional[Dict[str, Any]] = None # 机器可读的结构化数据
    action_retry_count: int = 0               # 重试次数


@dataclass
class ObservationStep:
    """Observation阶段的数据结构"""
    step_number: int
    # 输入部分（来自action_tool阶段）
    execution_status: str
    summary: str
    raw_data: Optional[Dict[str, Any]]
    # 输出部分（LLM返回的新决策）
    content: str                              # LLM基于结果的新思考
    reasoning: Optional[str] = None           # LLM的推理过程
    action_tool: str = ""                     # 下一个要执行的工具
    params: Dict[str, Any] = field(default_factory=dict)  # 工具参数
    is_finished: bool = False                # 是否完成任务
```

##### 8.3.2.2 实现异步流式输出

**新增run_stream方法**：
```python
async def run_stream(self, user_input: str, max_steps: int = 10):
    """
    异步流式执行Agent，每轮循环完成后立即yield输出
    
    Args:
        user_input: 用户输入
        max_steps: 最大迭代次数
    
    Yields:
        各个阶段的输出字典
    """
    # 第1步：构建初始消息列表
    messages = self._build_messages(user_input)
    
    step_count = 0
    
    while step_count < max_steps:
        # ========== Thought阶段 ==========
        # 调用LLM获取思考
        llm_response = await self.llm_service.chat(messages)
        parsed = json.loads(llm_response)
        
        thought_content = parsed.get("content", "")
        reasoning = parsed.get("reasoning")
        action_tool = parsed.get("action_tool", "finish")
        params = parsed.get("params", {})
        
        # 立即yield thought
        yield {
            "type": "thought",
            "step": step_count + 1,
            "content": thought_content,
            "reasoning": reasoning,
            "action_tool": action_tool,
            "params": params
        }
        
        # 判断是否结束
        if action_tool == "finish":
            break
        
        # ========== Action阶段 ==========
        execution_result = await self._execute_tool(action_tool, params)
        
        # 立即yield action_tool结果
        yield {
            "type": "action_tool",
            "step": step_count + 1,
            "tool_name": action_tool,
            "tool_params": params,
            "execution_status": execution_result["status"],
            "summary": execution_result["summary"],
            "raw_data": execution_result.get("data"),
            "action_retry_count": execution_result.get("retry_count", 0)
        }
        
        # ========== Observation阶段 ==========
        # 将action结果格式化为输入
        observation_text = f"Observation: {execution_result['status']} - {execution_result['summary']}"
        messages.append({"role": "user", "content": observation_text})
        
        # 调用LLM获取下一个决策
        llm_response = await self.llm_service.chat(messages)
        parsed = json.loads(llm_response)
        
        # 立即yield observation
        yield {
            "type": "observation",
            "step": step_count + 1,
            "execution_status": execution_result["status"],
            "summary": execution_result["summary"],
            "raw_data": execution_result.get("data"),
            "content": parsed.get("content", ""),
            "reasoning": parsed.get("reasoning"),
            "action_tool": parsed.get("action_tool", "finish"),
            "params": parsed.get("params", {}),
            "is_finished": parsed.get("action_tool") == "finish"
        }
        
        # 更新消息历史
        messages.append({"role": "assistant", "content": thought_content})
        
        # 判断是否结束
        if parsed.get("action_tool") == "finish":
            break
            
        step_count += 1
    
    # 任务结束，yield final
    yield {
        "type": "final",
        "content": parsed.get("content", "任务已完成")
    }
```

##### 8.3.2.3 集成安全检查

**新增安全检查集成**：
```python
async def run_stream(self, user_input: str, max_steps: int = 10):
    """
    异步流式执行Agent（带安全检查）
    """
    # ========== 安全检查阶段 ==========
    from app.services.shell_security import check_command_safety
    
    safety_result = await check_command_safety(user_input)
    
    # 如果被拦截，立即返回错误
    if safety_result.get("blocked", False):
        yield {
            "type": "error",
            "code": "SECURITY_BLOCKED",
            "message": safety_result.get("risk", "危险命令已拦截"),
            "error_type": "security",
            "details": f"risk_level: {safety_result.get('risk_level')}"
        }
        return
    
    # 如果有警告但未拦截，yield警告信息
    if safety_result.get("risk_level") in ["medium", "high"]:
        yield {
            "type": "start",
            # ... 其他字段 ...
            "security_check": safety_result
        }
        # 继续执行，但需要用户确认（这里简化处理）
    
    # 继续正常的ReAct循环...
    async for event in self._run_react_loop(user_input, max_steps):
        yield event
```

---

#### 8.3.2.4 其他需要修改的类和函数

根据调试分析，以下类和函数也需要配合新的数据结构进行修改：

##### A5 ToolParser.parse_response 方法修改

**作用**：解析LLM返回的响应

**需要配合修改**：
- 支持新的字段名：`action_tool`（原 `action`）和 `params`（原 `action_input`）
- 返回格式需要包含 `content`, `reasoning`, `action_tool`, `params`

##### A6 ToolParser._extract_from_text 方法修改

**作用**：从文本中提取工具调用信息

**需要配合修改**：
- 支持从新的JSON格式中提取字段

##### A7 ToolExecutor 类修改

**作用**：工具执行器

**需要配合修改**：
- 更新返回格式，添加 `execution_status` 字段
- 支持 `success`/`error`/`warning` 三种状态

##### A8 FileOperationAgent.run 方法

**作用**：现有的阻塞式运行方法

**需要配合修改**：
- 标记为废弃或保留作为兼容
- 建议使用新的 `run_stream` 方法

##### A9 _execute_with_retry 方法修改

**作用**：带重试机制的执行

**需要配合修改**：
- 配合新的错误分类（`retryable` 字段）
- 更新重试逻辑

##### A10 _format_observation 方法修改

**作用**：格式化观察结果

**需要配合修改**：
- 配合新的 `observation` 格式
- 包含 `execution_status`, `summary`, `raw_data`, `content`, `reasoning`, `action_tool`, `params`, `is_finished`

---

### 8.4 adapter.py 重构详细说明

#### 8.4.1 当前状态

adapter.py 当前的实现已经比较完善，主要完成了：
- `messages_to_dict_list`: Message对象转字典
- `dict_list_to_messages`: 字典转Message对象
- `convert_chat_history`: 通用转换函数

#### 8.4.2 需要扩展的功能

##### 8.4.2.1 新增字段转换函数

根据新的type设计，需要新增以下转换函数：

```python
def observation_to_llm_input(observation_step: Dict[str, Any]) -> str:
    """
    将observation阶段的结果格式化为LLM的输入
    
    格式化公式：Observation: {execution_status} - {summary}
    
    Args:
        observation_step: action_tool阶段的执行结果
        
    Returns:
        格式化后的字符串
    """
    status = observation_step.get("execution_status", "unknown")
    summary = observation_step.get("summary", "")
    return f"Observation: {status} - {summary}"


def thought_to_message(thought_step: Dict[str, Any]) -> Dict[str, str]:
    """
    将thought阶段转换为对话消息格式
    
    Args:
        thought_step: thought阶段的输出
        
    Returns:
        字典格式的消息 {"role": "assistant", "content": "..."}
    """
    return {
        "role": "assistant",
        "content": thought_step.get("content", "")
    }
```

#### 8.4.3 遗漏的修改点（调试分析补充）

根据调试分析，以下函数也需要配合新的type格式进行适配：

##### P3 messages_to_dict_list 函数修改

**作用**：将Message对象列表转换为字典列表

**需要配合修改**：
- 适配新的type格式（如 `action_tool` 字段）
- 确保转换后的格式与新的数据结构兼容

##### P4 dict_list_to_messages 函数修改

**作用**：将字典列表转换为Message对象列表

**需要配合修改**：
- 适配新的type格式
- 正确解析 `action_tool`, `params` 等新字段

##### P5 convert_chat_history 函数修改

**作用**：通用聊天历史转换函数

**需要配合修改**：
- 适配新格式的通用转换逻辑

---

### 8.5 tools.py 重构详细说明

#### 8.5.1 当前问题诊断

| 问题编号 | 问题描述 | 影响 |
|---------|---------|------|
| P8-010 | 返回格式不统一 | 不同工具返回格式不一致 |
| P8-011 | 缺少execution_status字段 | 前端无法判断执行结果 |

#### 8.5.2 统一工具返回格式

**重构后统一返回格式**：
```python
def execute_tool(tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    统一的工具执行返回格式
    
    Returns:
        {
            "status": "success" | "error" | "warning",
            "summary": "人类可读的结果描述",
            "data": {...} | null,
            "retry_count": 0
        }
    """
    # 执行具体工具
    try:
        result = _dispatch_tool(tool_name, params)
        
        # 成功
        return {
            "status": "success",
            "summary": _generate_summary(tool_name, result),
            "data": result,
            "retry_count": 0
        }
    except Warning as w:
        # 有警告但成功
        return {
            "status": "warning",
            "summary": str(w),
            "data": result,
            "retry_count": 0
        }
    except Exception as e:
        # 执行失败
        return {
            "status": "error",
            "summary": f"执行失败：{str(e)}",
            "data": None,
            "retry_count": 0
        }
```

#### 8.5.3 遗漏的修改点（调试分析补充）

根据调试分析，以下工具方法也需要配合新的返回格式进行修改：

##### T2 FileTools.read_file 函数修改

**作用**：读取文件内容

**需要配合修改**：
- 添加 `execution_status` 字段
- 返回格式统一为：`{status, summary, data, retry_count}`

##### T3 FileTools.write_file 函数修改

**作用**：写入文件内容

**需要配合修改**：
- 添加 `execution_status` 字段

##### T4 FileTools.list_directory 函数修改

**作用**：列出目录内容

**需要配合修改**：
- 添加 `execution_status` 字段
- 添加分页支持（`has_more`, `next_page_token`）

##### T5 FileTools.delete_file 函数修改

**作用**：删除文件

**需要配合修改**：
- 添加 `execution_status` 字段

##### T6 FileTools.move_file 函数修改

**作用**：移动文件

**需要配合修改**：
- 添加 `execution_status` 字段

##### T7 FileTools.search_files 函数修改

**作用**：搜索文件

**需要配合修改**：
- 添加 `execution_status` 字段

##### T8 FileTools.generate_report 函数修改

**作用**：生成报告

**需要配合修改**：
- 添加 `execution_status` 字段

##### T9 register_tool 函数修改

**作用**：注册工具

**需要配合修改**：
- 确保返回格式统一

##### T10 get_tool 函数修改

**作用**：获取工具

**需要配合修改**：
- 可能需要更新以支持新的工具格式

##### T11 list_directory_with_pagination 函数新增

**作用**：支持分页的目录列表

**功能说明**：
- 返回分页数据，包含 has_more 和 next_page_token
- 支持通过 page_token 请求下一页
- 支持自定义 page_size

```python
def list_directory_with_pagination(path: str, page_token: str = None, page_size: int = PAGE_SIZE) -> Dict[str, Any]:
    """
    支持分页的目录列表
    
    Returns:
        {
            "entries": [...],        # 当前页的数据
            "total": 100000,         # 总数量
            "has_more": true,        # 是否有更多
            "next_page_token": "xxx" # 下一页令牌
        }
    """
    # 获取所有条目
    all_entries = scan_directory(path)
    total = len(all_entries)
    
    # 计算分页
    start_idx = 0
    if page_token:
        start_idx = decode_page_token(page_token)
    
    end_idx = min(start_idx + page_size, total)
    page_entries = all_entries[start_idx:end_idx]
    
    # 生成结果
    result = {
        "entries": page_entries,
        "total": total,
        "has_more": end_idx < total
    }
    
    if result["has_more"]:
        result["next_page_token"] = encode_page_token(end_idx)
    
    return result
```

##### T12 encode_page_token 函数新增

**作用**：编码页码令牌

```python
def encode_page_token(offset: int) -> str:
    """编码页码令牌"""
    return base64.b64encode(str(offset).encode()).decode()
```

##### T13 decode_page_token 函数新增

**作用**：解码页码令牌

```python
def decode_page_token(token: str) -> int:
    """解码页码令牌"""
    try:
        return int(base64.b64decode(token.encode()).decode())
    except:
        return 0
```

##### T14 _generate_summary 函数新增

**作用**：生成人类可读的结果摘要

```python
def _generate_summary(tool_name: str, result: Any) -> str:
    """生成结果摘要"""
    if tool_name == "list_directory":
        entries = result.get("entries", [])
        return f"成功读取目录，共 {len(entries)} 个项目"
    elif tool_name == "read_file":
        content = result.get("content", "")
        return f"成功读取文件，内容长度：{len(content)} 字符"
    elif tool_name == "write_file":
        return "文件写入成功"
    # ... 其他工具的摘要生成逻辑
    return "操作完成"
```

---

### 8.6 safety.py 重构详细说明

#### 8.6.1 当前状态

safety.py 已经实现了基本的安全检查功能。

#### 8.6.2 需要扩展的功能

##### 8.6.2.1 增强安全检查结果格式

```python
async def check_command_safety(command: str) -> Dict[str, Any]:
    """
    检查命令安全性
    
    Returns:
        {
            "is_safe": bool,           # 是否安全
            "risk_level": str | null,  # low/medium/high/critical
            "risk": str | null,        # 风险描述
            "blocked": bool,            # 是否被拦截
            "rule_matched": str | null # 匹配的规则名称
        }
    """
    # ... 现有逻辑 ...
    
    # 扩展返回格式
    return {
        "is_safe": is_safe,
        "risk_level": risk_level,
        "risk": risk_description,
        "blocked": blocked,
        "rule_matched": matched_rule
    }
```

---

### 8.6.3 错误分类与重试机制实现（新增）

#### 8.6.3.1 错误分类设计

根据错误性质分为**可重试**和**不可重试**两类：

```python
class ErrorCategory:
    """错误分类枚举"""
    # 可重试错误（临时性问题）
    NETWORK_TIMEOUT = "NETWORK_TIMEOUT"        # 网络超时
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"  # 服务不可用
    RATE_LIMIT = "RATE_LIMIT"                  # 速率限制
    
    # 不可重试错误（永久性问题）
    FILE_NOT_FOUND = "FILE_NOT_FOUND"          # 文件不存在
    PERMISSION_DENIED = "PERMISSION_DENIED"    # 权限不足
    INVALID_PARAMS = "INVALID_PARAMS"           # 参数错误
    UNKNOWN_TOOL = "UNKNOWN_TOOL"              # 未知工具
```

#### 8.6.3.2 错误响应格式

```python
def create_error_response(error: Exception, context: Dict = None) -> Dict[str, Any]:
    """
    创建错误响应，包含retryable字段
    
    Returns:
        {
            "type": "error",
            "code": "ERROR_CODE",
            "message": "错误消息",
            "error_type": "error_type分类",
            "retryable": true/false,
            "retry_after": 5  # 仅当retryable=true时
        }
    """
    error_code, error_type, retryable, retry_after = classify_error(error)
    
    response = {
        "type": "error",
        "code": error_code,
        "message": str(error),
        "error_type": error_type,
        "retryable": retryable
    }
    
    if retryable and retry_after:
        response["retry_after"] = retry_after
    
    return response


def classify_error(error: Exception) -> Tuple[str, str, bool, int]:
    """
    分类错误，返回 (code, type, retryable, retry_after)
    """
    error_msg = str(error).lower()
    
    # 可重试错误
    if isinstance(error, TimeoutError) or "timeout" in error_msg:
        return ("NETWORK_TIMEOUT", "network", True, 5)
    if "connection" in error_msg or "unavailable" in error_msg:
        return ("SERVICE_UNAVAILABLE", "network", True, 10)
    if "429" in error_msg or "rate limit" in error_msg:
        return ("RATE_LIMIT", "network", True, 30)
    
    # 不可重试错误
    if "not found" in error_msg or "不存在" in error_msg:
        return ("FILE_NOT_FOUND", "file_system", False, 0)
    if "permission" in error_msg or "权限" in error_msg:
        return ("PERMISSION_DENIED", "security", False, 0)
    if "invalid" in error_msg or "参数" in error_msg:
        return ("INVALID_PARAMS", "validation", False, 0)
    
    # 默认未知错误
    return ("UNKNOWN_ERROR", "unknown", False, 0)
```

#### 8.6.3.3 前端错误处理示例

```python
# chat.py 中处理错误
try:
    result = await agent.run_stream(user_input)
except Exception as e:
    error_response = create_error_response(e)
    yield f"data: {json.dumps(error_response)}\n\n"
```

---

### 8.6.4 分页支持实现（新增，实际在tools.py中实现）

> **说明**：分页功能实现位于 `tools.py` 中的 `list_directory_with_pagination` 函数，此处仅列出设计要点。

#### 8.6.4.1 分页配置

```python
# 分页配置常量
PAGE_SIZE = 100  # 每页返回数量
MAX_PAGE_SIZE = 500  # 最大单页数量
```

#### 8.6.4.2 list_directory 分页实现

```python
def list_directory_with_pagination(path: str, page_token: str = None, page_size: int = PAGE_SIZE) -> Dict[str, Any]:
    """
    支持分页的目录列表
    
    Returns:
        {
            "entries": [...],        # 当前页的数据
            "total": 100000,         # 总数量
            "has_more": true,        # 是否有更多
            "next_page_token": "xxx" # 下一页令牌
        }
    """
    # 获取所有条目
    all_entries = scan_directory(path)
    total = len(all_entries)
    
    # 计算分页
    start_idx = 0
    if page_token:
        start_idx = decode_page_token(page_token)
    
    end_idx = min(start_idx + page_size, total)
    page_entries = all_entries[start_idx:end_idx]
    
    # 生成结果
    result = {
        "entries": page_entries,
        "total": total,
        "has_more": end_idx < total
    }
    
    if result["has_more"]:
        result["next_page_token"] = encode_page_token(end_idx)
    
    return result


def encode_page_token(offset: int) -> str:
    """编码页码令牌"""
    return base64.b64encode(str(offset).encode()).decode()


def decode_page_token(token: str) -> int:
    """解码页码令牌"""
    try:
        return int(base64.b64decode(token.encode()).decode())
    except:
        return 0
```

#### 8.6.4.3 action_tool 返回分页数据

```python
# 在 execute_tool 中返回分页数据
if tool_name == "list_directory":
    path = params.get("path", ".")
    page_token = params.get("page_token")
    page_size = params.get("page_size", PAGE_SIZE)
    
    result = list_directory_with_pagination(path, page_token, page_size)
    
    return {
        "status": "success",
        "summary": f"成功读取目录，共 {result['total']} 个项目",
        "data": result,
        "retry_count": 0
    }
```

#### 8.6.5 遗漏的修改点（调试分析补充）

根据调试分析，以下SafetyChecker类的方法也需要配合新的返回格式进行修改：

##### S2 SafetyChecker.check 方法修改

**作用**：综合安全检查方法

**需要配合修改**：
- 返回完整的安全检查对象：`is_safe`, `risk_level`, `risk`, `blocked`
- 确保字段名称与新的API设计一致

##### S3 SafetyChecker.get_risk_level 方法修改

**作用**：获取风险等级

**需要配合修改**：
- 更新返回格式以包含完整的风险信息

##### S4 SafetyChecker.is_safe 方法修改

**作用**：判断是否安全

**需要配合修改**：
- 更新判断逻辑以支持新的风险分类

---

### 8.7 重构后的文件结构

#### 8.7.1 重构后的目录结构

```
backend/app/
├── api/v1/
│   └── chat.py                    # 【重构】API入口
└── services/file_operations/
    ├── agent.py                   # 【重构】ReAct Agent核心
    ├── adapter.py                  # 【扩展】参数适配器
    ├── tools.py                   # 【重构】工具集
    └── safety.py                  # 【扩展】安全检查
```

#### 8.7.2 新增/修改的函数清单

| 文件 | 函数/类 | 操作 | 说明 |
|------|---------|------|------|
| chat.py | create_error_response | 修改 | 统一错误响应格式（包含retryable字段） |
| chat.py | check_and_yield_if_interrupted | 修改 | 集成新的status类型 |
| chat.py | check_and_yield_if_paused | 修改 | 集成新的status类型 |
| chat.py | check_and_yield_if_retrying | 新增 | 集成新的status类型（重试中） |
| chat.py | chat_endpoint | 重构 | 移除硬编码，实现实时流式 |
| chat.py | get_user_friendly_error | 修改 | 适配新的错误格式 |
| chat.py | cancel_stream_task | 修改 | 发送status=interrupted |
| chat.py | pause_stream_task | 修改 | 发送status=paused |
| chat.py | resume_stream_task | 修改 | 发送status=resumed |
| agent.py | ThoughtStep | 新增 | Thought阶段数据结构 |
| agent.py | ActionToolStep | 新增 | Action阶段数据结构 |
| agent.py | ObservationStep | 新增 | Observation阶段数据结构 |
| agent.py | run_stream | 新增 | 异步流式输出方法 |
| agent.py | _run_react_loop | 新增 | ReAct循环内部方法 |
| agent.py | _execute_tool | 新增 | 工具执行内部方法 |
| agent.py | ToolParser.parse_response | 修改 | 适配新字段名 |
| agent.py | ToolExecutor | 修改 | 添加execution_status字段 |
| agent.py | _execute_with_retry | 修改 | 适配retryable错误分类 |
| agent.py | _format_observation | 修改 | 适配新observation格式 |
| adapter.py | messages_to_dict_list | 修改 | 适配新type格式 |
| adapter.py | dict_list_to_messages | 修改 | 适配新type格式 |
| adapter.py | convert_chat_history | 修改 | 通用转换适配 |
| adapter.py | observation_to_llm_input | 新增 | observation格式化 |
| adapter.py | thought_to_message | 新增 | thought转消息格式 |
| tools.py | execute_tool | 修改 | 统一返回格式 |
| tools.py | _dispatch_tool | 新增 | 工具分发内部方法 |
| tools.py | _generate_summary | 新增 | 生成结果摘要 |
| tools.py | FileTools.read_file | 修改 | 添加execution_status |
| tools.py | FileTools.write_file | 修改 | 添加execution_status |
| tools.py | FileTools.list_directory | 修改 | 添加execution_status和分页 |
| tools.py | list_directory_with_pagination | 新增 | 分页支持实现 |
| tools.py | encode_page_token | 新增 | 页码令牌编码 |
| tools.py | decode_page_token | 新增 | 页码令牌解码 |
| safety.py | check_command_safety | 修改 | 增强返回格式 |
| safety.py | SafetyChecker.check | 修改 | 适配新返回格式 |
| safety.py | classify_error | 新增 | 错误分类函数 |
| safety.py | create_error_response | 新增 | 创建错误响应（含retryable） |

---

### 8.8 重构验证检查清单

完成重构后，必须验证以下各项：

#### 8.8.1 功能验证

- [ ] 第一个thought不再硬编码，由LLM生成
- [ ] 第一个action_tool不再硬编码，由LLM生成
- [ ] 推送时机改为实时（每轮循环完成后立即推送）
- [ ] observation不再嵌套thought/action_tool
- [ ] 错误响应格式统一（type/code/message/error_type）

#### 8.8.2 数据结构验证

- [ ] thought类型包含：content, reasoning(可选), action_tool, params
- [ ] action_tool类型包含：step, tool_name, tool_params, execution_status, summary, raw_data(可选), action_retry_count(可选)
- [ ] observation类型包含：step, execution_status, summary, raw_data(可选), content, reasoning(可选), action_tool, params, is_finished
- [ ] error类型包含：type, code, message, error_type, retryable, retry_after(可选), details(可选), stack(可选)
- [ ] status类型包含：type, status_value, message

#### 8.8.3 流程验证

- [ ] ReAct循环顺序正确：Thought → Action → Observation → (下一轮)Thought
- [ ] 每轮循环结束后立即推送，不需要等全部完成
- [ ] 安全检查在ReAct循环开始前执行
- [ ] 用户确认流程正确：paused → 用户确认 → resumed

---

**更新时间**: 2026-03-09 14:11:11
**编写人**: 小沈

---

## 九、流式API接口详细使用说明

**编写人**: 小沈
**编写时间**: 2026-03-09 14:15:00

---

### 9.1 API接口概述

#### 9.1.1 接口基本信息

| 项目 | 说明 |
|------|------|
| **接口地址** | `/api/v1/chat` |
| **请求方法** | `POST` |
| **响应类型** | `SSE (Server-Sent Events)` |
| **Content-Type** | `text/event-stream` |

#### 9.1.2 请求头要求

```
Content-Type: application/json
Accept: text/event-stream
```

---

### 9.2 请求格式详解

#### 9.2.1 请求参数结构

```json
{
  "messages": [
    {
      "role": "user",
      "content": "帮我查看桌面文件夹"
    }
  ],
  "stream": true,
  "temperature": 0.7,
  "provider": "openai",
  "model": "gpt-4",
  "task_id": "可选的任务ID",
  "session_id": "可选的会话ID"
}
```

#### 9.2.2 字段详细说明

| 字段 | 类型 | 必要性 | 说明 |
|------|------|--------|------|
| messages | array | **必要** | 消息列表，当前只支持单条用户消息 |
| messages[].role | string | **必要** | 固定为 "user" |
| messages[].content | string | **必要** | 用户输入的自然语言 |
| stream | boolean | 可选 | 是否流式返回，固定为 true |
| temperature | float | 可选 | 温度参数，范围 0-2，默认 0.7 |
| provider | string | 可选 | AI提供商，不指定则使用默认 |
| model | string | 可选 | AI模型，不指定则使用默认 |
| task_id | string | 可选 | 任务ID，用于追踪调试 |
| session_id | string | 可选 | 会话ID，用于缓存display_name |

---

### 9.3 SSE响应格式详解

#### 9.3.1 SSE基本格式

```
data: {"type": "...", ...}

```

**重要说明**：
1. 每个数据块以 `data: ` 开头
2. 数据必须是有效的JSON字符串
3. 数据块之间用空行分隔（两个换行符）
4. 前端需要使用 `EventSource` 或 `fetch` + `ReadableStream` 接收

#### 9.3.2 type类型一览表

| type值 | 含义 | 出现时机 |
|--------|------|---------|
| start | 任务开始 | 任务初始化时 |
| thought | LLM思考 | ReAct第1阶段 |
| action_tool | 执行动作 | ReAct第2阶段 |
| observation | 执行结果判断 | ReAct第3阶段 |
| chunk | 流式内容片段 | 普通对话流式输出 |
| final | 最终回复 | 任务完成时 |
| error | 错误 | 发生错误时 |
| status | 执行状态 | 状态变化时 |

---

### 9.4 每种type的详细响应格式

#### 9.4.1 type=start（任务开始）

**发送时机**：后端接收到请求，开始处理时

**响应示例**：
```json
{
  "type": "start",
  "display_name": "OpenAI (gpt-4)",
  "model": "gpt-4",
  "provider": "openai",
  "task_id": "abc123",
  "security_check": {
    "is_safe": true,
    "risk_level": null,
    "risk": null,
    "blocked": false
  }
}
```

**字段说明**：

| 字段 | 类型 | 说明 |
|------|------|------|
| type | string | 固定值 "start" |
| display_name | string | AI显示名称，如 "OpenAI (gpt-4)" |
| model | string | 实际使用的AI模型 |
| provider | string | AI提供商 |
| task_id | string | 任务唯一标识 |
| security_check | object | 安全检查结果 |
| security_check.is_safe | boolean | 是否安全：true=安全，false=危险 |
| security_check.risk_level | string/null | 风险等级：low/medium/high/critical，无风险时为null |
| security_check.risk | string/null | 风险描述，无风险时为null |
| security_check.blocked | boolean | 是否被拦截：true=已拦截，不执行LLM |

**前端处理**：
```javascript
if (data.type === 'start') {
  console.log(`任务开始: ${data.task_id}`);
  console.log(`AI: ${data.display_name}`);
  // 显示安全检查状态
  if (data.security_check.is_safe === false) {
    // 显示危险警告
    showWarning(data.security_check.risk);
  }
}
```

---

#### 9.4.2 type=thought（LLM思考）

**发送时机**：LLM返回推理结果时（ReAct循环第1阶段）

**响应示例**：
```json
{
  "type": "thought",
  "step": 1,
  "content": "用户想要查看桌面文件夹，我需要先列出桌面目录的内容",
  "reasoning": "用户提到了'查看'和'文件夹'，这是一个目录列表操作",
  "action_tool": "list_directory",
  "params": {
    "path": "C:\\Users\\xxx\\Desktop"
  }
}
```

**字段说明**：

| 字段 | 类型 | 说明 |
|------|------|------|
| type | string | 固定值 "thought" |
| step | number | 当前是第几轮ReAct循环，从1开始 |
| content | string | LLM的思考内容，说明当前分析 |
| reasoning | string/null | LLM的推理过程（可选），说明为什么做此决策 |
| action_tool | string | LLM决定要执行的工具名称 |
| params | object | 工具执行的参数 |

**action_tool取值范围**：

| action_tool | 说明 | params示例 |
|-------------|------|-----------|
| list_directory | 列出目录 | {"path": "..."} |
| read_file | 读取文件 | {"path": "..."} |
| write_file | 写入文件 | {"path": "...", "content": "..."} |
| create_directory | 创建目录 | {"path": "..."} |
| delete_file | 删除文件 | {"path": "..."} |
| move_file | 移动文件 | {"source": "...", "destination": "..."} |
| copy_file | 复制文件 | {"source": "...", "destination": "..."} |
| finish | 完成任务 | {} |

**前端处理**：
```javascript
if (data.type === 'thought') {
  // 显示思考中...
  showThinking(data.content);
  // 显示即将执行的工具
  showNextAction(data.action_tool, data.params);
}
```

---

#### 9.4.3 type=action_tool（执行动作）

**发送时机**：工具执行完成后（ReAct循环第2阶段）

**响应示例**：
```json
{
  "type": "action_tool",
  "step": 1,
  "tool_name": "list_directory",
  "tool_params": {
    "path": "C:\\Users\\xxx\\Desktop"
  },
  "execution_status": "success",
  "summary": "成功读取目录，文件列表：['file1.txt', 'file2.txt', 'folder1']",
  "raw_data": {
    "entries": [
      {"name": "file1.txt", "type": "file", "size": 1024},
      {"name": "file2.txt", "type": "file", "size": 2048},
      {"name": "folder1", "type": "directory"}
    ],
    "total": 3
  },
  "action_retry_count": 0
}
```

**字段说明**：

| 字段 | 类型 | 说明 |
|------|------|------|
| type | string | 固定值 "action_tool" |
| step | number | 步骤序号，与对应的thought对应 |
| tool_name | string | 执行的工具名称 |
| tool_params | object | 工具执行的参数 |
| execution_status | string | 执行状态：success/error/warning |
| summary | string | 人类可读的执行结果摘要 |
| raw_data | object/null | 机器可读的结构化数据，执行失败时为null |
| action_retry_count | number | 重试次数，0=首次执行 |

**分页数据示例（新增）**：

当数据量较大时（如列出100000个文件），返回分页数据：

```json
{
  "type": "action_tool",
  "step": 1,
  "tool_name": "list_directory",
  "tool_params": {
    "path": "D:\\"
  },
  "execution_status": "success",
  "summary": "成功读取目录，共 100000 个项目",
  "raw_data": {
    "entries": [
      {"name": "file1.txt", "type": "file", "size": 1024},
      {"name": "file2.txt", "type": "file", "size": 2048}
    ],
    "total": 100000,
    "has_more": true,
    "next_page_token": "MTAw"
  },
  "action_retry_count": 0
}
```

**分页字段说明**：

| 字段 | 类型 | 说明 |
|------|------|------|
| total | number | 总数据量 |
| has_more | boolean | 是否有更多数据 |
| next_page_token | string | 下一页令牌，用于请求下一页 |

**前端分页处理**：

```javascript
if (data.raw_data && data.raw_data.has_more) {
  // 用户滚动到底部时请求下一页
  const nextPage = await fetchNextPage(data.raw_data.next_page_token);
  appendEntries(nextPage.raw_data.entries);
}
```

**execution_status取值**：

| 值 | 说明 | 场景 |
|----|------|------|
| success | 执行成功 | 正常完成操作 |
| error | 执行失败 | 操作异常或失败 |
| warning | 执行有警告 | 操作完成但有需要注意的情况 |

**前端处理**：
```javascript
if (data.type === 'action_tool') {
  // 显示工具执行状态
  if (data.execution_status === 'success') {
    showSuccess(data.summary);
    // 可以解析raw_data获取详细数据
  } else if (data.execution_status === 'error') {
    showError(data.summary);
  } else if (data.execution_status === 'warning') {
    showWarning(data.summary);
  }
}
```

---

#### 9.4.4 type=observation（执行结果判断）

**发送时机**：LLM根据action_tool执行结果做出下一步决策时（ReAct循环第3阶段）

**响应示例**：
```json
{
  "type": "observation",
  "step": 1,
  "execution_status": "success",
  "summary": "成功读取目录",
  "raw_data": {
    "entries": [
      {"name": "file1.txt", "type": "file"},
      {"name": "file2.txt", "type": "file"}
    ]
  },
  "content": "已获取目录内容，第一个文件是file1.txt，现在需要读取它的内容",
  "reasoning": "用户想要查看文件内容，列表中有file1.txt和file2.txt，先读取第一个",
  "action_tool": "read_file",
  "params": {
    "path": "C:\\Users\\xxx\\Desktop\\file1.txt"
  },
  "is_finished": false
}
```

**字段说明**：

| 字段 | 类型 | 说明 |
|------|------|------|
| type | string | 固定值 "observation" |
| step | number | 步骤序号，与action_tool对应 |
| execution_status | string | 来自action_tool的执行状态 |
| summary | string | 来自action_tool的结果描述 |
| raw_data | object/null | 来自action_tool的原始数据 |
| content | string | LLM基于结果的新思考 |
| reasoning | string/null | LLM的推理过程（可选） |
| action_tool | string | LLM决定的下一步工具 |
| params | object | 工具参数 |
| is_finished | boolean | 是否完成任务：true=结束，false=继续 |

**前端处理**：
```javascript
if (data.type === 'observation') {
  // 显示结果分析
  showAnalysis(data.content);
  
  // 判断是否结束
  if (data.is_finished === true) {
    // 任务即将完成，等待final
    console.log("任务即将完成");
  } else {
    // 继续执行下一个工具
    showNextAction(data.action_tool, data.params);
  }
}
```

---

#### 9.4.5 type=chunk（流式内容片段）

**发送时机**：LLM流式输出回复时（仅用于普通对话，ReAct过程不使用）

**响应示例**：
```json
{
  "type": "chunk",
  "content": "你",
  "is_reasoning": false,
  "chunk_reasoning": null
}
```

**字段说明**：

| 字段 | 类型 | 说明 |
|------|------|------|
| type | string | 固定值 "chunk" |
| content | string | 回复片段内容 |
| is_reasoning | boolean | 是否在思考阶段 |
| chunk_reasoning | string/null | 思考内容（可选） |

**使用场景说明**：

| 场景 | 是否发送chunk | 说明 |
|------|---------------|------|
| 普通对话 | ✅ 发送 | AI生成文本时逐块返回，实现打字机效果 |
| ReAct文件操作 | ❌ 不发送 | 只有thought/action_tool/observation，最后直接final |

**前端处理**：
```javascript
if (data.type === 'chunk') {
  // 追加内容到显示区域（实现打字机效果）
  appendToMessage(data.content);
}
```

---

#### 9.4.6 type=final（最终回复）

**发送时机**：任务完成时

**响应示例**：
```json
{
  "type": "final",
  "content": "桌面有3个文件：file1.txt、file2.txt、folder1。"
}
```

**字段说明**：

| 字段 | 类型 | 说明 |
|------|------|------|
| type | string | 固定值 "final" |
| content | string | 完整回复内容 |

**触发条件**：
- LLM在observation阶段返回 action_tool = "finish"
- 任务执行失败，需要告知用户错误信息
- 达到最大迭代次数

**前端处理**：
```javascript
if (data.type === 'final') {
  // 显示最终回复
  showFinalMessage(data.content);
  // 任务结束
  console.log("任务完成");
}
```

---

#### 9.4.7 type=error（错误）

**发送时机**：发生错误时

**响应示例**：
```json
{
  "type": "error",
  "code": "TIMEOUT",
  "message": "请求超时，请重试",
  "error_type": "network",
  "details": "连接远程服务器超时",
  "stack": "Traceback (most recent call last):\n  File..."
}
```

**字段说明**：

| 字段 | 类型 | 说明 |
|------|------|------|
| type | string | 固定值 "error" |
| code | string | 错误码 |
| message | string | 用户可读的错误消息 |
| error_type | string/null | 错误类型：network/file_system/validation/security |
| details | string/null | 详细错误信息 |
| stack | string/null | 堆栈信息（仅用于调试） |

**code取值建议**：

| code | 说明 |
|------|------|
| TIMEOUT | 请求超时 |
| NOT_FOUND | 资源不存在 |
| PERMISSION_DENIED | 权限不足 |
| SECURITY_BLOCKED | 安全拦截 |
| VALIDATION_ERROR | 参数验证错误 |
| INTERNAL_ERROR | 内部错误 |

**retryable字段（新增）**：

```json
// 可重试错误
{
  "type": "error",
  "code": "NETWORK_TIMEOUT",
  "message": "网络请求超时",
  "error_type": "network",
  "retryable": true,
  "retry_after": 5
}

// 不可重试错误
{
  "type": "error",
  "code": "FILE_NOT_FOUND",
  "message": "文件不存在",
  "error_type": "file_system",
  "retryable": false
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| retryable | boolean | 是否可重试 |
| retry_after | number | 重试等待秒数（仅retryable=true时） |

**retryable取值**：

| 值 | 说明 | 典型场景 |
|----|------|---------|
| true | 可重试 | 网络超时、服务不可用 |
| false | 不可重试 | 文件不存在、权限不足、参数错误 |

**前端处理**：
```javascript
if (data.type === 'error') {
  // 显示错误信息
  showError(data.message);
  // 记录错误码（用于调试）
  console.error(`Error ${data.code}: ${data.error_type}`);
}
```

---

#### 9.4.8 type=status（执行状态）

**发送时机**：Agent内部执行状态变化时

**响应示例**：
```json
{
  "type": "status",
  "status_value": "paused",
  "message": "等待用户确认：确定要删除 test.txt 吗？"
}
```

**字段说明**：

| 字段 | 类型 | 说明 |
|------|------|------|
| type | string | 固定值 "status" |
| status_value | string | 具体状态值 |
| message | string | 状态消息 |

**status_value取值说明**：

| status_value | 说明 | 触发场景 |
|--------------|------|----------|
| interrupted | 任务中断 | 用户主动中断、安全拦截、达到最大迭代 |
| paused | 任务暂停 | 等待用户确认、等待资源 |
| resumed | 任务恢复 | 用户确认后继续、资源可用 |
| retrying | 任务重试 | 工具执行失败自动重试 |

**状态流转关系**：

```
running → paused → resumed → running
running → interrupted → 结束
running → retrying → running
```

**前端处理**：
```javascript
if (data.type === 'status') {
  switch (data.status_value) {
    case 'interrupted':
      showInterrupted(data.message);
      break;
    case 'paused':
      showPaused(data.message);
      // 显示确认按钮
      showConfirmButton();
      break;
    case 'resumed':
      showResumed(data.message);
      break;
    case 'retrying':
      showRetrying(data.message);
      break;
  }
}
```

---

### 9.5 完整交互流程示例

#### 9.5.1 普通对话流程

```
客户端发送: POST /api/v1/chat
           {"messages": [{"role": "user", "content": "你好"}], "stream": true}

服务端返回:
data: {"type": "start", "display_name": "OpenAI (gpt-4)", "task_id": "abc123", ...}

data: {"type": "thought", "step": 1, "content": "用户问你好，我应该礼貌回复", "action_tool": "finish", "params": {}}

data: {"type": "chunk", "content": "你", "is_reasoning": false}
data: {"type": "chunk", "content": "好", "is_reasoning": false}
data: {"type": "chunk", "content": "！", "is_reasoning": false}

data: {"type": "final", "content": "你好！有什么可以帮助你的？"}
```

#### 9.5.2 文件操作流程（单轮）

```
客户端发送: POST /api/v1/chat
           {"messages": [{"role": "user", "content": "帮我查看桌面"}], "stream": true}

服务端返回:
data: {"type": "start", ...}

data: {"type": "thought", "step": 1, "content": "用户想要查看桌面文件夹...", 
       "action_tool": "list_directory", "params": {"path": "Desktop"}}

data: {"type": "action_tool", "step": 1, "tool_name": "list_directory", 
       "tool_params": {"path": "Desktop"}, "execution_status": "success", 
       "summary": "成功读取目录", "raw_data": {...}}

data: {"type": "observation", "step": 1, "execution_status": "success", 
       "summary": "成功读取目录", "content": "已获取目录内容，现在整理成列表回复用户",
       "action_tool": "finish", "params": {}, "is_finished": true}

data: {"type": "final", "content": "桌面有3个文件：file1.txt, file2.txt, folder1"}
```

#### 9.5.3 文件操作流程（多轮）

```
客户端发送: POST /api/v1/chat
           {"messages": [{"role": "user", "content": "帮我查看桌面，然后读取第一个文件"}], "stream": true}

服务端返回:
data: {"type": "start", ...}

【第1轮循环】
data: {"type": "thought", "step": 1, ..., "action_tool": "list_directory", "params": {"path": "Desktop"}}
data: {"type": "action_tool", "step": 1, ..., "execution_status": "success", ...}
data: {"type": "observation", "step": 1, ..., "action_tool": "read_file", "params": {"path": "Desktop/file1.txt"}, "is_finished": false}

【第2轮循环】
data: {"type": "thought", "step": 2, ..., "action_tool": "read_file", "params": {"path": "Desktop/file1.txt"}}
data: {"type": "action_tool", "step": 2, ..., "execution_status": "success", ...}
data: {"type": "observation", "step": 2, ..., "action_tool": "finish", "params": {}, "is_finished": true}

data: {"type": "final", "content": "桌面有2个文件：file1.txt和file2.txt。第一个文件file1.txt的内容是：..."}
```

#### 9.5.4 错误处理流程

```
客户端发送: POST /api/v1/chat
           {"messages": [{"role": "user", "content": "读取不存在的文件"}], "stream": true}

服务端返回:
data: {"type": "start", ...}

data: {"type": "thought", ..., "action_tool": "read_file", ...}
data: {"type": "action_tool", ..., "execution_status": "error", "summary": "读取文件失败：文件不存在"}
data: {"type": "observation", ..., "execution_status": "error", "action_tool": "finish", "is_finished": true}

data: {"type": "final", "content": "读取文件失败：文件不存在。请检查文件路径是否正确。"}
```

#### 9.5.5 安全拦截流程

```
客户端发送: POST /api/v1/chat
           {"messages": [{"role": "user", "content": "删除 C:\\Windows\\System32"}], "stream": true}

服务端返回:
data: {"type": "start", "security_check": {"is_safe": false, "risk_level": "critical", "risk": "检测到系统关键目录操作", "blocked": true}}

data: {"type": "error", "code": "SECURITY_BLOCKED", "message": "检测到危险命令，已被安全规则拦截", "error_type": "security"}
```

#### 9.5.6 用户确认流程

```
【任务执行到需要确认时】
data: {"type": "observation", ..., "content": "检测到删除操作，需要用户确认", "action_tool": "finish", ...}

data: {"type": "status", "status_value": "paused", "message": "等待用户确认：确定要删除 test.txt 吗？"}

【用户点击确认后】
客户端发送: POST /api/v1/chat/confirm
           {"task_id": "abc123", "confirmed": true}

服务端返回:
data: {"type": "status", "status_value": "resumed", "message": "用户已确认，继续执行"}

【继续执行删除操作】
...
```

---

### 9.6 前端接收处理代码示例

#### 9.6.1 使用fetch + ReadableStream

```javascript
async function sendMessage(messages) {
  const response = await fetch('/api/v1/chat', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      messages: messages,
      stream: true
    })
  });

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    
    // 处理SSE数据块
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = JSON.parse(line.slice(6));
        handleServerEvent(data);
      }
    }
  }
}

function handleServerEvent(data) {
  switch (data.type) {
    case 'start':
      handleStart(data);
      break;
    case 'thought':
      handleThought(data);
      break;
    case 'action_tool':
      handleActionTool(data);
      break;
    case 'observation':
      handleObservation(data);
      break;
    case 'chunk':
      handleChunk(data);
      break;
    case 'final':
      handleFinal(data);
      break;
    case 'error':
      handleError(data);
      break;
    case 'status':
      handleStatus(data);
      break;
  }
}
```

#### 9.6.2 使用EventSource（仅GET请求，不适用本API）

**注意**：EventSource只支持GET请求，不适用于POST请求的流式API。上述fetch示例是正确的方式。

---

### 9.7 错误响应码处理

| HTTP状态码 | 说明 | 前端处理 |
|-----------|------|---------|
| 200 | 正常响应 | 解析SSE流 |
| 400 | 请求参数错误 | 显示错误信息 |
| 401 | 未认证 | 跳转登录 |
| 403 | 无权限 | 显示权限不足 |
| 500 | 服务器内部错误 | 显示服务器错误 |
| 503 | 服务不可用 | 显示服务暂不可用 |

---

**更新时间**: 2026-03-09 14:15:00
**编写人**: 小沈

---

### 9.8 遗漏的API接口（调试分析补充）

根据调试分析，以下API接口需要在设计文档中补充说明：

#### 9.8.1 任务控制API

用于在流式任务执行过程中进行控制（取消、暂停、恢复）：

##### 取消任务 API

| 项目 | 说明 |
|------|------|
| **接口地址** | `/api/v1/chat/stream/cancel/{task_id}` |
| **请求方法** | `POST` |
| **请求参数** | task_id（路径参数）：任务ID |
| **响应格式** | JSON |

**请求示例**：
```bash
curl -X POST http://localhost:8000/api/v1/chat/stream/cancel/abc123
```

**响应示例**：
```json
{
  "type": "status",
  "status_value": "interrupted",
  "message": "任务已被用户取消"
}
```

##### 暂停任务 API

| 项目 | 说明 |
|------|------|
| **接口地址** | `/api/v1/chat/stream/pause/{task_id}` |
| **请求方法** | `POST` |
| **请求参数** | task_id（路径参数）：任务ID |
| **响应格式** | JSON |

##### 恢复任务 API

| 项目 | 说明 |
|------|------|
| **接口地址** | `/api/v1/chat/stream/resume/{task_id}` |
| **请求方法** | `POST` |
| **请求参数** | task_id（路径参数）：任务ID |
| **响应格式** | JSON |

---

#### 9.8.2 用户确认接口

用于在任务暂停（等待用户确认）后，用户进行确认或拒绝：

| 项目 | 说明 |
|------|------|
| **接口地址** | `/api/v1/chat/confirm` |
| **请求方法** | `POST` |
| **Content-Type** | `application/json` |

**请求参数**：

| 字段 | 类型 | 必要性 | 说明 |
|------|------|--------|------|
| task_id | string | **必要** | 任务ID |
| confirmed | boolean | **必要** | 用户选择：true=确认执行，false=拒绝执行 |
| modified_command | string | 可选 | 如果用户选择修改命令，传入新命令 |

**请求示例**：
```json
{
  "task_id": "abc123",
  "confirmed": true
}
```

**响应示例**：
```json
{
  "type": "status",
  "status_value": "resumed",
  "message": "用户已确认，继续执行"
}
```

---

#### 9.8.3 分页数据请求接口

用于请求大型目录列表的分页数据：

| 项目 | 说明 |
|------|------|
| **接口地址** | `/api/v1/chat/stream/next-page` |
| **请求方法** | `POST` |
| **Content-Type** | `application/json` |

**请求参数**：

| 字段 | 类型 | 必要性 | 说明 |
|------|------|--------|------|
| task_id | string | **必要** | 原始任务ID |
| next_page_token | string | **必要** | 从action_tool响应中获取的令牌 |

**请求示例**：
```json
{
  "task_id": "abc123",
  "next_page_token": "MTAw"
}
```

**响应示例**：
```json
{
  "type": "action_tool",
  "step": 1,
  "tool_name": "list_directory",
  "execution_status": "success",
  "raw_data": {
    "entries": [...],
    "total": 100000,
    "has_more": true,
    "next_page_token": "MjAw"
  }
}
```

---

## 十、前端配合升级修改说明

**编写人**: 小沈
**编写时间**: 2026-03-09 14:20:00

---

### 10.1 前端修改概述

本次前端修改的核心目标是：**适配新的流式API响应格式，正确处理所有type类型，实现实时流式显示**。

#### 10.1.1 需要修改的文件清单

| 序号 | 文件路径 | 作用 | 修改优先级 |
|------|---------|------|-----------|
| 1 | `frontend/src/components/Chat/MessageItem.tsx` | 消息显示组件 | 🔴 高 |
| 2 | `frontend/src/hooks/useChat.ts` | 聊天Hook | 🔴 高 |
| 3 | `frontend/src/services/api.ts` | API调用服务 | 🟡 中 |
| 4 | `frontend/src/types/chat.ts` | 类型定义 | 🔴 高 |
| 5 | `frontend/src/components/Chat/ChatInput.tsx` | 输入组件 | 🟡 中 |

---

### 10.1.2 与后端重构配套的修改点（调试分析补充）

根据调试笔记第6章分析，由于第5-9章的后端重构，前端需要相应更新以下修改点：

#### 10.1.2.1 类型定义遗漏（3处）

| 序号 | 遗漏项 | 说明 | 重要性 |
|------|--------|------|--------|
| F1 | 新建 `types/chat.ts` | 实际文件不存在，需要新建 | 🔴 高 |
| F2 | 类型名称统一 | 设计文档定义 `ThoughtMessage` 等，实际使用 `ExecutionStep` | 🔴 高 |
| F3 | action_tool类型映射 | 需要支持 `action_tool` 到 `action` 的映射 | 🔴 高 |

#### 10.1.2.2 API端点问题（2处）

| 序号 | 遗漏项 | 说明 | 重要性 |
|------|--------|------|--------|
| F4 | API端点确认 | 设计文档用 `/api/v1/chat`，实际用 `/api/v1/chat/stream` | 🔴 高 |
| F5 | 端点差异处理 | 需要说明如何处理端点差异 | 🟡 中 |

#### 10.1.2.3 字段名称映射（4处）

由于后端重构使用了新字段名，需要在前端添加映射层：

| 序号 | 字段 | 设计文档（目标） | 当前代码（现状） | 解决方案 |
|------|------|-----------------|-----------------|---------|
| F6 | 类型名 | `action_tool` | `action` | 需映射 |
| F7 | 参数字段 | `params` | `action_input` | 需映射 |
| F8 | 工具名字段 | `tool_name` | `action` | 需映射 |
| F9 | 工具参数 | `tool_params` | `action_input` | 需映射 |

**字段映射实现示例**：
```typescript
// 在 api.ts 中添加适配层
function mapBackendResponse(data: any): any {
  // action_tool → action
  if (data.action_tool !== undefined && data.action === undefined) {
    data.action = data.action_tool;
  }
  // params → action_input
  if (data.params !== undefined && data.action_input === undefined) {
    data.action_input = data.params;
  }
  // tool_name → action
  if (data.tool_name !== undefined && data.action === undefined) {
    data.action = data.tool_name;
  }
  // tool_params → action_input
  if (data.tool_params !== undefined && data.action_input === undefined) {
    data.action_input = data.tool_params;
  }
  return data;
}
```

#### 10.1.2.4 缺失文件处理（2处）

| 序号 | 遗漏项 | 说明 | 重要性 |
|------|--------|------|--------|
| F10 | `hooks/useChat.ts` | 文件不存在 | 🔴 高 |
| F11 | SSE逻辑位置 | 现有逻辑在 `utils/sse.ts` 的 `useSSE` hook中 | - |

#### 10.1.2.5 消息处理遗漏（4处）

| 序号 | 遗漏项 | 设计文档处理 | 实际代码处理 | 状态 |
|------|--------|-------------|-------------|------|
| F12 | start类型 | 需要处理 | 当前未处理 | ❌ 遗漏 |
| F13 | chunk类型 | 需要处理 | sse.ts已处理 | ⚠️ 部分 |
| F14 | status类型 | 需要处理 | sse.ts已处理 | ⚠️ 部分 |
| F15 | action_tool | 需映射为action | 当前直接使用action | ❌ 不一致 |

#### 10.1.2.6 修改优先级

**第一优先级（必须修改）**：
- F1: 新建 `types/chat.ts`
- F3-F9: 字段映射层实现
- F12: 添加start类型处理
- F15: action_tool到action的映射

**第二优先级（建议修改）**：
- F2: 类型名称统一
- F4-F5: API端点确认
- F10: useChat.ts或确认现有hook

**第三优先级（可选）**：
- F11: 现有sse.ts逻辑优化
- F13-F14: chunk/status处理优化

---

### 10.2 类型定义修改

#### 10.2.1 新增TypeScript类型定义

**文件**: `frontend/src/types/chat.ts`

```typescript
// ============================================================
// 流式API响应类型定义
// ============================================================

// 安全检查结果
export interface SecurityCheck {
  is_safe: boolean;
  risk_level: 'low' | 'medium' | 'high' | 'critical' | null;
  risk: string | null;
  blocked: boolean;
}

// start类型
export interface StartMessage {
  type: 'start';
  display_name: string;
  model: string;
  provider: string;
  task_id: string;
  security_check: SecurityCheck;
}

// thought类型
export interface ThoughtMessage {
  type: 'thought';
  step: number;
  content: string;
  reasoning?: string;
  action_tool: string;
  params: Record<string, any>;
}

// action_tool类型
export interface ActionToolMessage {
  type: 'action_tool';
  step: number;
  tool_name: string;
  tool_params: Record<string, any>;
  execution_status: 'success' | 'error' | 'warning';
  summary: string;
  raw_data?: Record<string, any> | null;
  action_retry_count: number;
}

// observation类型
export interface ObservationMessage {
  type: 'observation';
  step: number;
  execution_status: 'success' | 'error' | 'warning';
  summary: string;
  raw_data?: Record<string, any> | null;
  content: string;
  reasoning?: string;
  action_tool: string;
  params: Record<string, any>;
  is_finished: boolean;
}

// chunk类型
export interface ChunkMessage {
  type: 'chunk';
  content: string;
  is_reasoning: boolean;
  chunk_reasoning?: string;
}

// final类型
export interface FinalMessage {
  type: 'final';
  content: string;
}

// error类型
export interface ErrorMessage {
  type: 'error';
  code: string;
  message: string;
  error_type?: string;
  details?: string;
  stack?: string;
}

// status类型
export type StatusValue = 'interrupted' | 'paused' | 'resumed' | 'retrying';

export interface StatusMessage {
  type: 'status';
  status_value: StatusValue;
  message: string;
}

// 联合类型 - 所有可能的响应类型
export type StreamMessage = 
  | StartMessage 
  | ThoughtMessage 
  | ActionToolMessage 
  | ObservationMessage 
  | ChunkMessage 
  | FinalMessage 
  | ErrorMessage 
  | StatusMessage;
```

---

### 10.3 API调用服务修改

#### 10.3.1 修改fetch调用方式

**文件**: `frontend/src/services/api.ts`

```typescript
/**
 * 发送聊天消息（流式）
 * @param messages 消息列表
 * @param onMessage 消息回调
 * @returns void
 */
export async function sendChatMessage(
  messages: ChatMessage[],
  onMessage: (message: StreamMessage) => void
): Promise<void> {
  const response = await fetch('/api/v1/chat', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      messages: messages,
      stream: true
    })
  });

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error('Response body is not readable');
  }

  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      
      // 处理SSE数据块
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6)) as StreamMessage;
            onMessage(data);
          } catch (e) {
            console.error('Failed to parse message:', e);
          }
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}
```

---

### 10.4 消息Hook修改

#### 10.4.1 修改useChat Hook

**文件**: `frontend/src/hooks/useChat.ts`

```typescript
import { useState, useCallback } from 'react';
import { StreamMessage, ChatMessage } from '../types/chat';
import { sendChatMessage } from '../services/api';

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [currentStep, setCurrentStep] = useState<StreamMessage | null>(null);

  const sendMessage = useCallback(async (content: string) => {
    const userMessage: ChatMessage = { role: 'user', content };
    const newMessages = [...messages, userMessage];
    
    setMessages(newMessages);
    setIsLoading(true);
    setCurrentStep(null);

    try {
      await sendChatMessage(newMessages, (streamMessage) => {
        // 处理每种类型的消息
        switch (streamMessage.type) {
          case 'start':
            handleStartMessage(streamMessage);
            break;
          case 'thought':
            handleThoughtMessage(streamMessage);
            break;
          case 'action_tool':
            handleActionToolMessage(streamMessage);
            break;
          case 'observation':
            handleObservationMessage(streamMessage);
            break;
          case 'chunk':
            handleChunkMessage(streamMessage);
            break;
          case 'final':
            handleFinalMessage(streamMessage);
            break;
          case 'error':
            handleErrorMessage(streamMessage);
            break;
          case 'status':
            handleStatusMessage(streamMessage);
            break;
        }
        
        setCurrentStep(streamMessage);
      });
    } catch (error) {
      console.error('Chat error:', error);
    } finally {
      setIsLoading(false);
    }
  }, [messages]);

  // ... 各种处理函数
  const handleStartMessage = (msg: StreamMessage) => {
    // 处理start类型
  };
  
  const handleThoughtMessage = (msg: StreamMessage) => {
    // 处理thought类型
  };
  
  // ... 其他处理函数

  return {
    messages,
    sendMessage,
    isLoading,
    currentStep
  };
}
```

---

### 10.5 消息显示组件修改

#### 10.5.1 修改MessageItem组件

**文件**: `frontend/src/components/Chat/MessageItem.tsx`

```typescript
import React from 'react';
import { StreamMessage } from '../../types/chat';

interface MessageItemProps {
  message: StreamMessage;
}

export const MessageItem: React.FC<MessageItemProps> = ({ message }) => {
  switch (message.type) {
    case 'start':
      return <StartDisplay message={message} />;
    case 'thought':
      return <ThoughtDisplay message={message} />;
    case 'action_tool':
      return <ActionToolDisplay message={message} />;
    case 'observation':
      return <ObservationDisplay message={message} />;
    case 'chunk':
      return <ChunkDisplay message={message} />;
    case 'final':
      return <FinalDisplay message={message} />;
    case 'error':
      return <ErrorDisplay message={message} />;
    case 'status':
      return <StatusDisplay message={message} />;
    default:
      return null;
  }
};

// 各类型显示组件
const StartDisplay: React.FC<{ message: any }> = ({ message }) => {
  return (
    <div className="message-start">
      <div className="ai-name">{message.display_name}</div>
      {message.security_check && (
        <div className={`security-badge ${message.security_check.is_safe ? 'safe' : 'danger'}`}>
          {message.security_check.is_safe ? '安全检查通过' : '危险：' + message.security_check.risk}
        </div>
      )}
    </div>
  );
};

const ThoughtDisplay: React.FC<{ message: any }> = ({ message }) => {
  return (
    <div className="message-thought">
      <div className="thought-icon">💭</div>
      <div className="thought-content">
        <div className="content">{message.content}</div>
        {message.reasoning && (
          <div className="reasoning">推理过程：{message.reasoning}</div>
        )}
        <div className="next-action">
          下一步：{message.action_tool}
          {message.params && JSON.stringify(message.params)}
        </div>
      </div>
    </div>
  );
};

const ActionToolDisplay: React.FC<{ message: any }> = ({ message }) => {
  const statusClass = message.execution_status;
  const hasMore = message.raw_data?.has_more;
  
  const handleLoadMore = () => {
    if (hasMore && message.raw_data?.next_page_token) {
      // 请求下一页数据
      console.log(`请求下一页: ${message.raw_data.next_page_token}`);
    }
  };
  
  return (
    <div className={`message-action-tool ${statusClass}`}>
      <div className="tool-icon">🔧</div>
      <div className="tool-info">
        <div className="tool-name">步骤{message.step}: {message.tool_name}</div>
        <div className="tool-status">{message.execution_status}</div>
        <div className="tool-summary">{message.summary}</div>
        {message.action_retry_count > 0 && (
          <div className="retry-count">重试次数：{message.action_retry_count}</div>
        )}
        {hasMore && (
          <div className="pagination-info">
            <span className="total-count">共 {message.raw_data.total} 个项目</span>
            <span className="has-more">还有更多</span>
            <button onClick={handleLoadMore} className="load-more-button">加载更多</button>
          </div>
        )}
      </div>
    </div>
  );
};

const ObservationDisplay: React.FC<{ message: any }> = ({ message }) => {
  return (
    <div className="message-observation">
      <div className="observation-icon">📋</div>
      <div className="observation-content">
        <div className="result-status">执行结果：{message.execution_status}</div>
        <div className="content">{message.content}</div>
        {message.reasoning && (
          <div className="reasoning">推理：{message.reasoning}</div>
        )}
        {message.is_finished ? (
          <div className="finished">任务即将完成</div>
        ) : (
          <div className="next-action">
            继续执行：{message.action_tool}
          </div>
        )}
      </div>
    </div>
  );
};

const ChunkDisplay: React.FC<{ message: any }> = ({ message }) => {
  return (
    <div className="message-chunk">
      {message.content}
    </div>
  );
};

const FinalDisplay: React.FC<{ message: any }> = ({ message }) => {
  return (
    <div className="message-final">
      <div className="final-icon">✅</div>
      <div className="final-content">{message.content}</div>
    </div>
  );
};

const ErrorDisplay: React.FC<{ message: any }> = ({ message }) => {
  const canRetry = message.retryable === true;
  
  const handleRetry = () => {
    if (canRetry && message.retry_after) {
      // 显示倒计时后重试
      console.log(`将在 ${message.retry_after} 秒后重试...`);
    }
  };
  
  return (
    <div className="message-error">
      <div className="error-icon">❌</div>
      <div className="error-content">
        <div className="error-message">{message.message}</div>
        <div className="error-code">错误码：{message.code}</div>
        {message.details && <div className="error-details">{message.details}</div>}
        {canRetry ? (
          <div className="retry-info">
            <span className="retryable-badge">可重试</span>
            {message.retry_after && (
              <span className="retry-after">等待 {message.retry_after} 秒后可重试</span>
            )}
            <button onClick={handleRetry} className="retry-button">重试</button>
          </div>
        ) : (
          <div className="non-retryable-info">
            <span className="non-retryable-badge">不可重试</span>
          </div>
        )}
      </div>
    </div>
  );
};

const StatusDisplay: React.FC<{ message: any }> = ({ message }) => {
  const statusConfig = {
    interrupted: { icon: '⏹️', className: 'interrupted' },
    paused: { icon: '⏸️', className: 'paused' },
    resumed: { icon: '▶️', className: 'resumed' },
    retrying: { icon: '🔄', className: 'retrying' }
  };
  
  const config = statusConfig[message.status_value];
  
  return (
    <div className={`message-status ${config.className}`}>
      <div className="status-icon">{config.icon}</div>
      <div className="status-message">{message.message}</div>
    </div>
  );
};
```

---

### 10.6 用户确认流程

#### 10.6.1 处理paused状态

当收到 `type: 'status', status_value: 'paused'` 时，前端需要显示确认对话框：

```typescript
const handleStatusMessage = (message: any) => {
  if (message.status_value === 'paused') {
    // 显示确认对话框
    showConfirmDialog(message.message);
  } else if (message.status_value === 'resumed') {
    // 隐藏确认对话框，继续显示
    hideConfirmDialog();
  } else if (message.status_value === 'interrupted') {
    // 显示中断信息
    showInterruptedMessage(message.message);
  } else if (message.status_value === 'retrying') {
    // 显示重试信息
    showRetryingMessage(message.message);
  }
};

function showConfirmDialog(message: string) {
  // 显示带有"确认"和"取消"按钮的对话框
  // 用户点击后调用确认API
}
```

---

### 10.7 样式修改

#### 10.7.1 新增CSS样式

```css
/* 消息类型样式 */

/* start类型 */
.message-start {
  padding: 10px;
  background: #f5f5f5;
  border-radius: 8px;
  margin-bottom: 10px;
}

.message-start .security-badge {
  display: inline-block;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
  margin-top: 8px;
}

.message-start .security-badge.safe {
  background: #4caf50;
  color: white;
}

.message-start .security-badge.danger {
  background: #f44336;
  color: white;
}

/* thought类型 */
.message-thought {
  display: flex;
  gap: 10px;
  padding: 10px;
  background: #e3f2fd;
  border-radius: 8px;
  margin-bottom: 10px;
}

.message-thought .reasoning {
  font-size: 12px;
  color: #666;
  margin-top: 4px;
}

/* action_tool类型 */
.message-action-tool {
  display: flex;
  gap: 10px;
  padding: 10px;
  border-radius: 8px;
  margin-bottom: 10px;
}

.message-action-tool.success {
  background: #e8f5e9;
}

.message-action-tool.error {
  background: #ffebee;
}

.message-action-tool.warning {
  background: #fff3e0;
}

/* observation类型 */
.message-observation {
  display: flex;
  gap: 10px;
  padding: 10px;
  background: #f3e5f5;
  border-radius: 8px;
  margin-bottom: 10px;
}

/* status类型 */
.message-status {
  display: flex;
  gap: 10px;
  padding: 10px;
  border-radius: 8px;
  margin-bottom: 10px;
}

.message-status.paused {
  background: #fff8e1;
}

.message-status.interrupted {
  background: #ffebee;
}

.message-status.resumed {
  background: #e8f5e9;
}

.message-status.retrying {
  background: #e3f2fd;
}
```

---

### 10.8 前端修改验证检查清单

完成修改后，必须验证以下各项：

#### 10.8.1 功能验证

- [ ] 能够正确接收并解析 start 类型
- [ ] 能够正确接收并解析 thought 类型
- [ ] 能够正确接收并解析 action_tool 类型
- [ ] 能够正确接收并解析 observation 类型
- [ ] 能够正确接收并解析 chunk 类型（打字机效果）
- [ ] 能够正确接收并解析 final 类型
- [ ] 能够正确接收并解析 error 类型
- [ ] 能够正确接收并解析 status 类型

#### 10.8.2 交互验证

- [ ] 实时流式显示正常（不等待全部完成）
- [ ] 用户确认对话框正确显示
- [ ] 错误信息正确显示
- [ ] 安全警告正确显示

#### 10.8.3 样式验证

- [ ] 各类型消息样式正确
- [ ] 执行状态颜色正确（success=绿，error=红，warning=橙）
- [ ] 状态类型样式正确

---

### 10.9 常见问题处理

#### 10.9.1 SSE数据解析问题

**问题**：有时会收到不完整的JSON

**解决方案**：使用buffer缓存，参考上面的`sendChatMessage`函数实现

#### 10.9.2 chunk和final同时出现的问题

**问题**：chunk和final会同时出现吗？

**答案**：
- ReAct文件操作：只出现final，不出现chunk
- 普通对话：先出现多个chunk，最后出现final

#### 10.9.3 状态丢失问题

**问题**：刷新页面后状态丢失

**解决方案**：
- 保存task_id到localStorage
- 刷新后通过task_id恢复会话状态

---

**更新时间**: 2026-03-09 16:55:00
**编写人**: 小沈
