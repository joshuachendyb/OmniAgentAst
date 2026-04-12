# 执行步骤 Step 编号优化说明

**创建时间**: 2026-03-18 09:30:00  
**编写人**: 小沈  
**适用**: 前端开发 - 小强

---

## 一、问题背景

### 1.1 原有问题

在之前的实现中，execution_steps 的 step 字段存在以下问题：

| 问题类型 | 具体表现 |
|---------|---------|
| **字段缺失** | start、error、incident、final 步骤没有 step 字段 |
| **编号重置** | 每个 agent 循环中，thought/action_tool/observation 都从 step=1 开始 |
| **不连续** | 无法通过 step 编号判断步骤的先后顺序 |

### 1.2 数据示例（旧）

```json
[
  {"type": "start", "step": "MISSING"},
  {"type": "thought", "step": 1},
  {"type": "action_tool", "step": 2},
  {"type": "observation", "step": 3},
  {"type": "thought", "step": 1},    // ❌ 重置为1
  {"type": "action_tool", "step": 1}, // ❌ 重置为1
  {"type": "observation", "step": 1}, // ❌ 重置为1
  {"type": "final", "step": "MISSING"}
]
```

---

## 二、后端修改内容

### 2.1 修改的函数

| 函数名 | 修改内容 |
|--------|---------|
| `create_incident_data()` | 添加 `step` 参数 |
| `create_error_response()` | 添加 `step` 参数 |
| `generate()` 函数内部 | 所有 error/incident 调用都传入 step |

### 2.2 新的数据格式

修改后，每个步骤都有连续的 step 编号：

```json
[
  {"type": "start", "step": 1},
  {"type": "thought", "step": 2},
  {"type": "action_tool", "step": 3},
  {"type": "observation", "step": 4},
  {"type": "thought", "step": 5},    // ✅ 继续递增
  {"type": "action_tool", "step": 6}, // ✅ 继续递增
  {"type": "observation", "step": 7}, // ✅ 继续递增
  {"type": "final", "step": 8}
]
```

### 2.3 编号规则

| 步骤类型 | step 编号 | 说明 |
|---------|----------|------|
| start | 1 | 对话开始 |
| thought | 2,5,9... | 思考步骤（递增） |
| action_tool | 3,6,10... | 工具调用（递增） |
| observation | 4,7,11... | 观察结果（递增） |
| chunk | 无 | 流式中间结果，不需要编号 |
| final | 最后 | 最终回复 |
| error | 错误发生时 | 错误步骤 |
| incident | 事件发生时 | 中断/暂停/恢复事件 |

---

## 三、好处

### 3.1 对前端显示

1. **步骤清晰** - 用户可以看到完整的执行顺序（步骤1、步骤2...）
2. **便于调试** - 开发时可以快速定位是哪个步骤出现问题
3. **状态追踪** - 知道当前进行到哪一步

### 3.2 对数据导出

1. **数据完整** - 导出的 JSON 包含所有 step 编号
2. **便于分析** - 可以按 step 顺序分析整个执行过程
3. **问题定位** - 如果出错，可以直接通过 step 定位问题步骤

### 3.3 对前后端对齐

1. **数据一致性** - 前后端使用相同的 step 编号
2. **可追溯** - 每个步骤都有唯一编号，方便追踪

---

## 四、前端需要修改的地方

### 4.1 MessageItem 组件显示 step

**文件**: `frontend/src/pages/chat/components/MessageItem.tsx`

**修改内容**: 在渲染 execution_steps 时，显示 step 编号

**示例**:
```tsx
// 之前
{step.type === 'thought' && (
  <div className="thought">
    <span>思考中...</span>
  </div>
)}

// 之后
{step.type === 'thought' && (
  <div className="thought">
    <span className="step-badge">步骤 {step.step}</span>
    <span>思考中...</span>
  </div>
)}
```

### 4.2 导出逻辑检查

**文件**: `frontend/src/services/chatService.ts` 或相关导出模块

**检查内容**: 确认导出 JSON 时保留 step 字段（后端已保存，前端只需不过滤即可）

---

## 五、验证方法

### 5.1 后端验证

创建新对话后，检查数据库：

```bash
curl -s "http://127.0.0.1:8000/api/v1/sessions/{session_id}/messages"
```

确认 execution_steps 中每个步骤都有 step 字段，且编号连续递增。

### 5.2 前端验证

1. 发起新对话
2. 观察消息气泡是否显示步骤编号
3. 导出消息，检查 JSON 中 step 字段是否存在

---

## 六、注意事项

1. **chunk 类型不需要 step** - chunk 是流式输出的中间结果，设计上不需要编号
2. **旧对话数据不变** - 已存在的对话数据不会更新，只有新对话才会使用新格式
3. **向后兼容** - 如果 step 字段不存在，前端应有默认处理

---

**更新时间**: 2026-03-18 09:30:00
