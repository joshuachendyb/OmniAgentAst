# 流式ReAct的type和API重构设计说明书

**编写人**: 小沈
**编写时间**: 2026-03-08 21:50:00
**更新时间**: 2026-03-09 13:02:21
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

### 4.1 原则1：禁止嵌套

**错误** ❌：
```json
{
  "type": "observation",
  "thought": "...",        // 不该在这里
  "action_tool": "...",         // 不该在这里
  "observation": {...}      // 嵌套自己！
}
```

**正确** ✅：
```json
{ "type": "thought", "content": "..." },
{ "type": "action_tool", "name": "list_directory", "input": {...} },
{ "type": "observation", "status": "success", "message": "..." }
```

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

### 5.1.1 安全检查流程（整合自调试笔记11章）

```
用户发送: "删除 C:\Windows\System32"
                ↓
        ┌───────────────────────────────────────┐
        │  阶段1：规则检查（后端自动）            │
        │  check_command_safety()               │
        │  → 拦截明显危险命令（rm -rf /等）      │
        └───────────────────────────────────────┘
                ↓
        ┌───────────────────────────────────────┐
        │  阶段2：LLM推理（第一个Thought）       │
        │  → 分析命令意图，给出智能提示          │
        └───────────────────────────────────────┘
                ↓
        ┌───────────────────────────────────────┐
        │  阶段3：用户确认（可选）               │
        │  → 确认 → 执行                        │
        │  → 取消 → 停止                        │
        └───────────────────────────────────────┘
```

**安全检查三层保障**：

| 层级 | 作用 | 优势 |
|------|------|------|
| **规则检查** | 快速拦截 `rm -rf /`、`format C:` 等 | 毫秒级响应，100%准确 |
| **LLM推理** | 分析命令意图，给出智能提示 | 语义理解，判断更准确 |
| **用户确认** | 危险操作需要用户许可 | 最终安全保障 |

---

### 5.1.2 字段分析

**字段分析**：

| 字段 | 作用 | 必要性 | 合理? |
|------|------|--------|-------|
| display_name | 显示AI名称 | 必要 | ✅ |
| model | AI模型 | 必要 | ✅ |
| provider | AI提供商 | 必要 | ✅ |
| task_id | 任务ID | 必要 | ✅ |
| security_check | 安全检查结果 | 必要 | ✅ 新增 |

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

**输出**：content + is_reasoning + reasoning

**传导**：不传导到下一阶段

**字段分析**：

| 字段 | 作用 | 必要性 | 合理? | 备注 |
|------|------|--------|-------|------|
| content | 回复片段 | 必要 | ✅ | |
| is_reasoning | 是否思考 | 可选 | ✅ | |
| chunk_reasoning | 思考内容 | 可选 | ⚠️ 建议改为chunk_reasoning避免与thought的reasoning混淆 |

**结论**：✅ 保留，字段完整，属于 Type（用于普通对话，ReAct过程不需要）

---

### 5.7 type=error（错误）

**是 Stage 还是 Type？**
- **Type**（错误状态，不参与循环）

**输入**：无

**输出**：code + message + error_type + details

**传导**：不传导到下一阶段

**字段分析**：

| 字段 | 作用 | 必要性 | 合理? |
|------|------|--------|-------|
| code | 错误码 | 必要 | ✅ |
| message | 错误消息 | 必要 | ✅ |
| error_type | 错误类型 | 可选 | ✅ 补充 |
| details | 详细错误信息 | 可选 | ✅ 补充 |
| stack | 堆栈信息 | 可选 | ✅ 补充（仅调试用） |

**结论**：✅ 保留，字段完整，属于 Type

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
| 3 | action_tool | 执行动作 | ✅ 直接相关 |
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

---

### 7.2 thought - LLM思考（Stage）

```json
{
  "type": "thought",
  "content": "用户想要查看桌面文件夹...",
  "action_tool": "list_directory",
  "params": {"path": "C:\\Users\\xxx\\Desktop"}
}
```

---

### 7.3 action_tool - 执行动作（Stage）

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
    "total": 2
  }
}
```

---

### 7.4 observation - 执行结果（Stage）

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

---

### 7.5 final - 最终回复

```json
{
  "type": "final",
  "content": "桌面有文件：github_ping.log, github_trace.log..."
}
```

---

### 7.6 chunk - 流式内容

```json
{
  "type": "chunk",
  "content": "这是回复片段",
  "is_reasoning": false,
  "chunk_reasoning": "用户问你好，我应该礼貌回复"
}
```

---

### 7.7 error - 错误

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

---

### 7.8 status - Agent执行状态（整合自原5.8-5.11）

**状态1：中断**
```json
{
  "type": "status",
  "status_value": "interrupted",
  "message": "任务已被中断"
}
```

**状态2：暂停**
```json
{
  "type": "status",
  "status_value": "paused",
  "message": "任务已暂停"
}
```

**状态3：恢复**
```json
{
  "type": "status",
  "status_value": "resumed",
  "message": "任务已恢复"
}
```

**状态4：重试中**
```json
{
  "type": "status",
  "status_value": "retrying",
  "message": "正在重试..."
}
```

---

## 八、完整时间线示例

### 8.1 普通对话

```
{ "type": "start", "display_name": "OpenAI (gpt-4)", "task_id": "xxx" }
{ "type": "thought", "content": "用户问你好，我应该礼貌回复", "action_tool": "finish", "params": {} }
{ "type": "chunk", "content": "你好" }
{ "type": "chunk", "content": "！" }
{ "type": "final", "content": "你好！有什么可以帮助你的？" }
```

### 8.2 文件操作

```
{ "type": "start", ... }

{ "type": "thought", "content": "用户想要查看桌面文件夹...", "action_tool": "list_directory", "params": {"path": "Desktop"} }
{ "type": "action_tool", "step": 1, "tool_name": "list_directory", "tool_params": {"path": "Desktop"}, "execution_status": "success", "summary": "成功读取目录", "raw_data": {...} }
{ "type": "observation", "execution_status": "success", "summary": "成功", "raw_data": {...}, "content": "已获取内容", "action_tool": "finish", "params": {} }

{ "type": "final", "content": "桌面有文件：..." }
```

---

## 九、前端显示对照

```javascript
switch(step.type) {
  case 'start': 显示AI名称; break;
  case 'thought': 显示💭思考内容; break;
  case 'action_tool': 显示🔧工具名和参数; break;
  case 'observation': 显示📋结果（成功/失败）; break;
  case 'chunk': 流式显示回复内容; break;
  case 'final': 显示最终回复; break;
  case 'error': 显示❌错误信息; break;
  case 'interrupted': 显示⏹️中断信息; break;
}
```

---

**更新时间**: 2026-03-08 23:30:00
**编写人**: 小沈
