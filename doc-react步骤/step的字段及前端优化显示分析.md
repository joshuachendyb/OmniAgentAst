# React步骤字段及前端优化显示分析

**创建时间**: 2026-03-30 19:36:31
**版本**: v1.0
**编写人**: 小沈
**分析范围**: 后端base_react.py + 前端MessageItem.tsx

---

## 一、ReAct模式标准语义

ReAct (Reasoning + Acting) 模式的核心流程：

```
用户输入
    ↓
[Thought] LLM分析问题 → 输出思考过程 + 决定下一步动作
    ↓
[Action] 执行工具 → 返回执行状态和结果
    ↓
[Observation] LLM观察结果 → 基于结果继续思考或结束
    ↓
[Final] 最终回复
```

**各步骤用户价值**：
- **thought**：让用户知道AI在想什么，分析了什么
- **action_tool**：让用户知道AI执行了什么操作
- **observation**：让用户知道操作结果如何，AI如何基于结果继续
- **final**：最终回答

---

## 二、后端各步骤类型字段定义

### 1. start 步骤

**发送位置**：chat_router.py → start_step.py (第52-67行)

| 序号 | 字段 | 类型 | 说明 |
|------|------|------|------|
| 1 | type | string | "start" |
| 2 | step | number | 步骤编号 |
| 3 | timestamp | number | 时间戳 |
| 4 | display_name | string | 模型显示名称 |
| 5 | provider | string | 提供商 |
| 6 | model | string | 模型名 |
| 7 | task_id | string | 任务ID |
| 8 | user_message | string | 用户消息(截取40字) |
| 9 | security_check | object | 安全检查结果 |

### 2. thought 步骤

**发送位置**：base_react.py (第190-198行)

| 序号 | 字段 | 类型 | 说明 |
|------|------|------|------|
| 1 | type | string | "thought" |
| 2 | step | number | 步骤编号 |
| 3 | timestamp | number | 时间戳 |
| 4 | content | string | LLM思考内容 |
| 5 | reasoning | string | 推理过程 |
| 6 | **action_tool** | string | 下一步要调用的工具 ⭐ |
| 7 | **params** | object | 工具参数 ⭐ |

### 3. action_tool 步骤

**发送位置**：base_react.py (第214-225行)

| 序号 | 字段 | 类型 | 说明 |
|------|------|------|------|
| 1 | type | string | "action_tool" |
| 2 | step | number | 步骤编号 |
| 3 | timestamp | number | 时间戳 |
| 4 | content | string | 工具名称 |
| 5 | tool_name | string | 工具名称 |
| 6 | tool_params | object | 工具参数 |
| 7 | **execution_status** | string | 执行状态(success/error) ⭐ |
| 8 | **summary** | string | 执行摘要 ⭐ |
| 9 | raw_data | object | 原始执行结果 |
| 10 | **action_retry_count** | number | 重试次数 ⭐ |

### 4. observation 步骤

**发送位置**：base_react.py (第267-279行)

| 序号 | 字段 | 类型 | 说明 |
|------|------|------|------|
| 1 | type | string | "observation" |
| 2 | step | number | 步骤编号 |
| 3 | timestamp | number | 时间戳 |
| 4 | **obs_execution_status** | string | 工具执行状态 ⭐ |
| 5 | **obs_summary** | string | 执行摘要 ⭐ |
| 6 | obs_raw_data | object | 原始数据 |
| 7 | content | string | LLM基于结果的下一步思考 |
| 8 | obs_reasoning | string | 推理过程 |
| 9 | action_tool | string | 下一步动作 |
| 10 | params | object | 参数 |
| 11 | is_finished | boolean | 是否结束 |

### 5. final 步骤

**发送位置**：base_react.py (第202-206, 285-289行)

| 序号 | 字段 | 类型 | 说明 |
|------|------|------|------|
| 1 | type | string | "final" |
| 2 | timestamp | number | 时间戳 |
| 3 | content | string | 最终回复内容 |

---

## 三、前端字段使用情况分析

---

### 1. thought 步骤

| 序号 | 字段 | 前端是否使用 | 新的使用建议 |
|------|------|-------------|--------------|
| 1 | type | ✓ | - |
| 2 | step | ✓ | 保留 |
| 3 | timestamp | ✅ | 显示时间 |
| 4 | content | ✓ | - |
| 5 | reasoning | ✓ | - |
| 6 | action_tool | ✅ | 显示下一步要调用的工具名称 |
| 7 | params | ✅ | 显示工具参数摘要 |

---

### 2. action_tool 步骤

| 序号 | 字段 | 前端是否使用 | 新的使用建议 |
|------|------|-------------|--------------|
| 1 | type | ✓ | - |
| 2 | content | ✓ | - |
| 3 | step | ✓ | 保留 |
| 4 | timestamp | ✅ | 显示时间 |
| 5 | tool_name | ✓ | - |
| 6 | tool_params | ✓ | - |
| 7 | execution_status | ✅ | 显示执行状态(success/error) |
| 8 | summary | ✓ | - |
| 9 | raw_data | ✓ | - |
| 10 | action_retry_count | ✅ | 显示重试次数 |

---

### 3. observation 步骤

| 序号 | 字段 | 前端是否使用 | 新的使用建议 |
|------|------|-------------|--------------|
| 1 | type | ✓ | - |
| 2 | step | ✓ | 保留 |
| 3 | timestamp | ✅ | 显示时间 |
| 4 | obs_execution_status | ✅ | 显示执行状态 |
| 5 | obs_summary | ✓ | - |
| 6 | obs_raw_data | ✓ | 同时显示content和raw_data，不再二选一 |
| 7 | content | ✓ | 同时显示content和raw_data，不再二选一 |
| 8 | obs_reasoning | ✓ | - |
| 9 | action_tool | ✅ | 显示下一步动作 |
| 10 | params | ✅ | 显示参数 |
| 11 | is_finished | ✅ | 显示是否结束 |

---

### 4. final 步骤

| 序号 | 字段 | 前端是否使用 | 新的使用建议 |
|------|------|-------------|--------------|
| 1 | type | ✓ | - |
| 2 | timestamp | ✅ | 显示时间 |
| 3 | content | ✓ | - |

---

## 四、字段精简说明（ReAct标准）

### 1. action_tool 步骤 - 保留字段

| 字段 | 说明 |
|------|------|
| type | 步骤类型标识 |
| step | 步骤编号 |
| timestamp | 时间戳 |
| tool_name | 工具名称 |
| tool_params | 工具参数 |
| execution_status | 执行状态(success/error) |
| summary | 执行摘要 |
| raw_data | 原始执行结果 |

### 2. action_tool 步骤 - 删除字段

| 字段 | 说明 | 删除理由 |
|------|------|---------|
| action_retry_count | 重试次数 | 47条数据全为0，无重试机制 |
| content | 工具名称 |
### 3. observation 步骤 - 保留字段

| 字段 | 说明 | 证据 |
|------|------|------|
| type | 步骤类型标识 | 代码第268行 |
| step | 步骤编号 | 代码第269行 |
| timestamp | 时间戳 | 代码第270行 |
| is_finished | 是否结束 | 代码第278行，数据库47/47有数据 |
| content | LLM下一步思考 | 代码第274行，数据库47/47有数据 |
| obs_action_tool | 下一步工具 | 37/47 | 保留 |
| obs_params | 工具参数 | 31/47 | 保留 |


### 4. observation 步骤 - 可删除字段（数据库验证）

| 字段 | 说明 | 数据库验证 | 结论 |
|------|------|-----------|------|
| obs_execution_status | 执行状态 | 47/47 | 删除（与action.execution_status重复） |
| obs_summary | 执行摘要 | 0/47 | 删除 |
| obs_raw_data | 原始数据 | 0/47 | 删除 |
| obs_reasoning | 推理过程 | 0/47 | 删除 |
前端使用情况：

obs_raw_data（366-417行）：只有当没有content时才显示 → 用于显示文件列表
obs_summary（409-413行）：只有当没有content时才显示 → 用于显示摘要
### 6. ReAct标准说明

```
标准ReAct结构：
Action(tool_name + params + result) → Observation(result) → 重复 → Final Answer

Observation只包含执行结果，不需要复制Action的任何字段
```

---

## 五、前后端字段对比问题表

| 步骤类型 | 后端字段数 | 前端缺失字段 |
|---------|-----------|-------------|
| **thought** | 7 | timestamp, action_tool, params |
| **action_tool** | 10 | timestamp, execution_status |
| **observation** | 11 | timestamp, action_tool, params, is_finished |
| **final** | 3 | timestamp |



---

## 六、前端优化建议

### 1. thought 步骤优化

**第三章分析出的未使用字段**：
| 字段 | 当前状态 | 优化建议 |
|------|---------|---------|
| timestamp | 未使用 | 显示该步骤的时间 |
| action_tool | 未使用 | 显示下一步要调用的工具名称 |
| params | 未使用 | 显示工具参数摘要 |

**当前显示**：
```
步骤{step} 💭 分析：{reasoning或content}
```

**优化后显示**：
```
步骤{step} 💭 分析：{reasoning或content} ⏰ {timestamp}
          ⬇️ 下一步：{action_tool}
             参数：{params关键字段摘要}
```

**示例**：
```
步骤1 💭 我需要读取这个文件的内容来确定下一步操作 13:25:30
       ⬇️ 下一步：read_file
          参数：{"path": "/home/user/test.txt"}
```

---

### 2. action_tool 步骤优化

**第三章分析出的未使用字段**：
| 字段 | 当前状态 | 优化建议 |
|------|---------|---------|
| timestamp | 未使用 | 显示该步骤的时间 |
| execution_status | 未使用 | 显示执行状态(success/error) |

**当前显示**：
```
步骤{step} ⚙️ 执行：{tool_name}
          📦 结果：{raw_data渲染}
```

**优化后显示**：
```
步骤{step} ⚙️ 执行：{tool_name} ⏰ {timestamp}
          📦 结果：{raw_data渲染}
          📊 状态：{success/error} | 摘要：{summary}
     
```

**示例**：
```
步骤2 ⚙️ 执行：read_file 13:25:31
      📦 结果：[文件内容...]
      📊 状态：success | 摘要：成功读取文件，共1024字节
     ```

---

### 3. observation 步骤优化

**第三章分析出的未使用字段**：
| 字段 | 当前状态 | 优化建议 |
|------|---------|---------|
| timestamp | 未使用 | 显示该步骤的时间 |
| action_tool | 未使用 | 显示下一步动作 |
| params | 未使用 | 显示参数 |
| is_finished | 未使用 | 显示是否结束 |

**当前问题**：content和obs_raw_data是二选一显示，应该同时显示

**当前显示**：
```
步骤{step} 🔍 检查：{content}
         ```

**优化后显示**：
```
步骤{step} 🔍 观察结果：{content} ⏰ {timestamp}
             ⬇️ 下一步：{obs_action_tool}
             参数：{obs_params}
             ✅ 结束（仅当is_finished=true时显示）
```

**示例**：
```
步骤3 🔍 观察结果：文件读取成功，包含了所需信息 13:25:32
        ⬇️ 下一步：search_files
        参数：{"keyword": "error"}
        ✅ 结束
```

---

### 4. final 步骤优化

**第三章分析出的未使用字段**：
| 字段 | 当前状态 | 优化建议 |
|------|---------|---------|
| timestamp | 未使用 | 显示该步骤的时间 |

**当前显示**：
```
✅ 总结：{content}
```

**优化后显示**：
```
✅ 总结：{content} ⏰ {timestamp}
```

**示例**：
```
✅ 总结：已完成所有文件分析，共发现3个错误。 13:25:35
```



---

## 七、总结

| 步骤类型 | 当前最大问题 | 改进优先级 |
|---------|------------|----------|
| **thought** | 看不到下一步动作(action_tool) | 高 |
| **action_tool** | 看不到执行状态(execution_status) | 高 |
| **observation** | 看不到执行状态，且content/raw_data显示逻辑错误 | 高 |
| **final** | ✅ 显示合理 | - |

**核心改进原则**：让用户清楚了解AI的推理过程(thought) → 执行了什么(action) → 结果如何(observation) → 最终回复(final)

---

**更新时间**: 2026-03-30 21:30:00
**版本**: v1.3
**更新说明**: 
- 新增第四章：字段精简说明（ReAct标准）
- 明确action_tool保留字段和删除字段
- 明确observation保留字段和删除字段
- 修正章节编号（五→六，六→七）
