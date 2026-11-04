# ReAct前端问题清单2301

**创建时间**: 2026-03-10 07:16:14
**存放位置**: D:\2bktest\MDview\OmniAgentAs-desk\
**编写人**: 小查、小新

---

## 1 问题清单汇总

| 序号 | 问题类型 | 严重程度 | 前端位置 | 设计文档章节 |
|------|---------|---------|----------|-------------|
| 1 | start缺少security_check处理 | 🟡 P2 | sse.ts:535-553 | 9.4.1 |
| 2 | observation缺少raw_data映射 | 🟡 P2 | sse.ts:600-610 | 9.4.4 |
| 3 | error字段兼容 | 🟡 P2 | sse.ts:650-670 | 9.4.7 |
| 4 | action类型兼容 | 🟢 P3 | sse.ts:578 | 9.4.3 |
| 5 | thought字段映射错误 | 🔴 P1 | sse.ts:562-573 | 9.4.2 |

---

## 2 问题1：start缺少security_check处理

### 2.1 问题描述

**设计文档要求(9.4.1)**：
- start类型应包含security_check字段
- security_check包含：is_safe, risk_level, risk, blocked

**前端当前实现**：
- 未处理security_check字段

### 2.2 问题位置

`frontend/src/utils/sse.ts` case "start" 第535-553行

### 2.3 修复记录

**修复时间**: 2026-03-10（小查）
**修复内容**：
```typescript
// 添加security_check字段处理
raw_data: rawData.security_check ? {
  is_safe: rawData.security_check.is_safe,
  risk_level: rawData.security_check.risk_level,
  risk: rawData.security_check.risk,
  blocked: rawData.security_check.blocked,
} : undefined,
```

### 2.4 设计要求示例

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

## 3 问题2：observation缺少raw_data映射

### 3.1 问题描述

**设计文档要求(9.4.4)**：
- 必须字段：step, execution_status, summary, raw_data, content, reasoning, action_tool, params, is_finished

**前端当前实现**：
- 未映射raw_data和is_finished字段

### 3.2 问题位置

`frontend/src/utils/sse.ts` case "observation" 第600-610行

### 3.3 修复记录

**修复时间**: 2026-03-10（小查）
**修复内容**：
```typescript
step.is_finished = rawData.is_finished ?? false;
step.raw_data = rawData.raw_data ?? null;
step.execution_status = rawData.execution_status ?? 'success';
step.summary = rawData.summary ?? '';
step.content = rawData.content ?? '';
step.reasoning = rawData.reasoning ?? '';
step.action_tool = rawData.action_tool ?? '';
step.params = rawData.params ?? {};
```

### 3.4 设计要求示例

```json
{
  "type": "observation",
  "step": 1,
  "execution_status": "success",
  "summary": "成功读取目录",
  "raw_data": {"entries": ["file1.txt", "file2.txt"]},
  "content": "已获取目录内容",
  "reasoning": "文件列表已完整获取",
  "action_tool": "finish",
  "params": {},
  "is_finished": true
}
```

---

## 4 问题3：error字段兼容

### 4.1 问题描述

**设计文档要求(9.4.7)**：
- 必须字段：message（不是error_message）
- 可选字段：code, error_type, details, stack, retryable, retry_after

**前端当前实现**：
- 使用error_message字段

### 4.2 问题位置

`frontend/src/utils/sse.ts` case "error" 第650-670行

### 4.3 修复记录

**修复时间**: 2026-03-10（小查）
**修复内容**：
```typescript
// 同时支持message和error_message（兼容旧版）
const errorMsg = rawData.message || rawData.error_message || "未知错误";
step.content = errorMsg;
step.error_message = errorMsg;
```

### 4.4 设计要求示例

```json
{
  "type": "error",
  "code": "TIMEOUT",
  "message": "请求超时，请重试",
  "error_type": "network",
  "retryable": true,
  "retry_after": 5
}
```

---

## 5 问题4：action类型兼容

### 5.1 问题描述

**设计文档要求(9.4.3)**：
- type值应为："action_tool"

**前端当前实现**：
- 只处理action_tool，未兼容旧版"action"

### 5.2 问题位置

`frontend/src/utils/sse.ts` case "action_tool" 第578行

### 5.3 修复记录

**修复时间**: 2026-03-10（小查）
**修复内容**：
```typescript
// 同时兼容旧版"action"类型
case "action":
case "action_tool": {
  // 处理逻辑...
}
```

---

## 6 问题5：thought字段映射错误

### 6.1 问题描述

**设计文档要求(9.4.2)**：
- 必须字段：step, content, reasoning, action_tool, params

**前端当前实现**：
- 使用thinking_prompt填充content
- 缺少reasoning字段映射

### 6.2 问题位置

`frontend/src/utils/sse.ts` case "thought" 第562-573行

### 6.3 修复记录

**修复时间**: 2026-03-10（小新）
**修复前**：
```typescript
step.content = step.thinking_prompt || "";
```

**修复后**：
```typescript
step.content = rawData.content || rawData.thinking_prompt || "";
step.reasoning = rawData.reasoning || "";
```

### 6.4 设计要求示例

```json
{
  "type": "thought",
  "step": 1,
  "content": "用户想要查看桌面文件夹...",
  "reasoning": "用户提到了'查看'和'文件夹'",
  "action_tool": "list_directory",
  "params": {"path": "..."}
}
```

---

## 7 问题6：测试用例兼容性问题

### 7.1 问题描述

**问题**：测试用例使用旧字段导致测试失败
- ExecutionPanel.test.tsx 使用 `type: 'action'`
- MessageItem.test.tsx 使用 `tool`, `params`, `content` 旧字段

### 7.2 问题位置

- `frontend/src/tests/components/ExecutionPanel.test.tsx`
- `frontend/src/tests/components/MessageItem.test.tsx`
- `frontend/src/components/Chat/ExecutionPanel.tsx`
- `frontend/src/components/Chat/MessageItem.tsx`

### 7.3 修复记录

**修复时间**: 2026-03-10（小查）

**修复内容**：

1. **ExecutionPanel.tsx**：添加对旧类型 `action` 的兼容处理
```typescript
case "action_tool":
case "action":  // 兼容旧类型
```

2. **MessageItem.tsx**：添加对旧字段的兼容处理
```typescript
// 颜色和标签映射添加旧类型
colorMap.action = "#1890ff"
labelMap.action = "工具"

// StepRow 添加 action 类型处理
(step.type === "action_tool" || step.type === "action")

// 兼容旧字段 tool/params
step.action || step.tool || "执行中..."
step.tool_params || step.params

// 兼容旧字段 content
step.thinking_prompt || step.content || ""

// hasExecution 判断添加 action
step.type === "action_tool" || step.type === "action" || step.type === "observation"

// 分组逻辑添加 action
step.type === "action_tool" || step.type === "action"
```

3. **测试用例修复**：
```typescript
// MessageItem.test.tsx 修复字段
{
  type: 'thought' as const,
  thinking_prompt: 'Thinking...',  // 改为 thinking_prompt
}
{
  type: 'action' as const,
  action: 'read_file',  // 改为 action
  action_input: {},     // 改为 action_input
}
```

---

**更新时间**: 2026-03-10 07:50:00
**编写人**: 小查、小新
