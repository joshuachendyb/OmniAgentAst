# ReAct后端问题清单1001

**创建时间**: 2026-03-10 06:47:15
**存放位置**: D:\2bktest\MDview\OmniAgentAs-desk\
**编写人**: 小查

---

## 1 问题清单汇总

| 序号 | 问题类型 | 严重程度 | 后端位置 | 设计文档章节 |
|------|---------|---------|----------|-------------|
| 1 | start缺少security_check | 🔴 P0 | chat.py:700-710 | 9.4.1 |
| 2 | action_tool的type值错误 | 🔴 P0 | chat.py:752,839 | 9.4.3 |
| 3 | action_tool缺少字段 | 🔴 P1 | chat.py:838-847 | 9.4.3 |
| 4 | observation缺少字段 | 🔴 P1 | chat.py:851-860 | 9.4.4 |
| 5 | status未整合 | 🟡 P2 | 全局 | 6.2, 9.4.8 |
| 6 | error字段名错误 | 🔴 P1 | chat.py:770,873 | 9.4.7 |

---

## 2 问题1：start缺少security_check字段

### 2.1 问题描述

**设计文档要求(9.4.1)**：
- 必须字段：display_name, model, provider, task_id, **security_check**
- security_check必须包含：is_safe, risk_level, risk, blocked

**后端实际代码**：
- 仅有：display_name, model, provider, task_id
- **缺少：security_check**

### 2.2 问题位置

`backend/app/api/v1/chat.py` 第700-710行

### 2.3 设计要求示例

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

### 2.4 修复建议

在start_data中添加security_check字段，从安全检查模块获取结果后填充。

---

## 3 问题2：action_tool的type值错误

### 3.1 问题描述

**设计文档要求(9.4.3)**：
- type值应为："action_tool"

**后端实际代码**：
- type值为："action"

### 3.2 问题位置

`backend/app/api/v1/chat.py` 第752行、第839行

### 3.3 错误代码

```python
# chat.py 752行
action1_data = {'type': 'action', ...}  # ❌ 应该是 'action_tool'

# chat.py 839行
action_data = {'type': 'action', ...}  # ❌ 应该是 'action_tool'
```

### 3.4 修复建议

将所有 `'type': 'action'` 修改为 `'type': 'action_tool'`

---

## 4 问题3：action_tool缺少字段

### 4.1 问题描述

**设计文档要求(9.4.3)**：
- 必须字段：step, tool_name, tool_params, execution_status, summary, **raw_data**, **action_retry_count**

**后端实际代码**：
- 仅有：step, tool_name, tool_params, execution_status, summary
- **缺少：raw_data, action_retry_count**

### 4.2 问题位置

`backend/app/api/v1/chat.py` 第838-847行

### 4.3 设计要求示例

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
      {"name": "file2.txt", "type": "file", "size": 2048}
    ],
    "total": 3
  },
  "action_retry_count": 0
}
```

### 4.4 修复建议

从agent.run_stream()获取的event中提取raw_data和action_retry_count字段，添加到返回数据中。

---

## 5 问题4：observation缺少字段

### 5.1 问题描述

**设计文档要求(9.4.4)**：
- 必须字段：step, execution_status, summary, **raw_data**, content, reasoning, action_tool, params, **is_finished**

**后端实际代码**：
- 仅有：step, execution_status, summary, content, reasoning, action_tool, params
- **缺少：raw_data, is_finished**

### 5.2 问题位置

`backend/app/api/v1/chat.py` 第851-860行

### 5.3 设计要求示例

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

### 5.4 修复建议

从agent.run_stream()获取的event中提取raw_data和is_finished字段，添加到返回数据中。

---

## 6 问题5：status未整合

### 6.1 问题描述

**设计文档要求(6.2, 9.4.8)**：
- 统一使用 type="status" + status_value字段
- status_value取值：interrupted, paused, resumed, retrying

**后端实际代码**：
- 分散使用：type="interrupted", type="paused", type="resumed", type="retrying"

### 6.2 问题位置

`backend/app/api/v1/chat.py` 全局多处

### 6.3 修复建议

将所有中断、暂停、恢复、重试的type值统一为"status"，添加status_value字段区分具体状态。

---

## 7 问题6：error字段名错误

### 7.1 问题描述

**设计文档要求(9.4.7)**：
- 必须字段：**message**（不是error_message）
- 可选字段：error_type, details, stack, retryable, retry_after

**后端实际代码**：
- 使用了：**error_message**（错误名称）

### 7.2 问题位置

`backend/app/api/v1/chat.py` 第770行、第873行

### 7.3 错误代码

```python
# chat.py 770行
error_data = {'type': 'error', 'error_message': f'危险操作需确认: {risk}'}

# chat.py 873行
error_data = {
    'type': 'error',
    'error_type': error_type,
    'error_message': error_message  # ❌ 应该是 'message'
}
```

### 7.4 修复建议

将所有 'error_message' 字段改为 'message'

---

## 8 问题7-10：前端代码修复（基于设计文档要求）

### 8.1 前端问题汇总

| 序号 | 问题类型 | 严重程度 | 前端位置 | 设计文档章节 |
|------|---------|---------|----------|-------------|
| 7 | start缺少security_check处理 | 🟡 P2 | sse.ts:535-553 | 9.4.1 |
| 8 | observation缺少raw_data映射 | 🟡 P2 | sse.ts:600-610 | 9.4.4 |
| 9 | error字段兼容 | 🟡 P2 | sse.ts:650-670 | 9.4.7 |
| 10 | action类型兼容 | 🟢 P3 | sse.ts:578 | 9.4.3 |
| 11 | thought字段映射错误 | 🔴 P1 | sse.ts:562-573 | 9.4.2 |

### 8.2 前端修复记录

#### 8.2.1 修复7：start类型添加security_check处理

**问题**：前端sse.ts未处理security_check字段

**修复位置**：`frontend/src/utils/sse.ts` case "start"

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

#### 8.2.2 修复8：observation类型添加raw_data映射

**问题**：前端sse.ts未映射raw_data和is_finished字段

**修复位置**：`frontend/src/utils/sse.ts` case "observation"

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

#### 8.2.3 修复9：error类型字段兼容

**问题**：前端sse.ts使用error_message，设计文档要求使用message

**修复位置**：`frontend/src/utils/sse.ts` case "error"

**修复内容**：
```typescript
// 同时支持message和error_message（兼容旧版）
const errorMsg = rawData.message || rawData.error_message || "未知错误";
step.content = errorMsg;
step.error_message = errorMsg;
```

#### 8.2.4 修复10：action类型兼容处理

**问题**：后端可能发送type="action"或type="action_tool"

**修复位置**：`frontend/src/utils/sse.ts` case "action"

**修复内容**：
```typescript
// 同时兼容旧版"action"类型
case "action":
case "action_tool": {
  // 处理逻辑...
}
```

### 8.2.5 修复11：thought类型字段映射（新增）

**问题**：前端sse.ts使用thinking_prompt填充content，设计文档要求使用content字段

**修复位置**：`frontend/src/utils/sse.ts` case "thought"

**修复前**：
```typescript
step.content = step.thinking_prompt || "";  // ❌ 使用错误字段
```

**修复后**：
```typescript
step.content = rawData.content || rawData.thinking_prompt || "";
step.reasoning = rawData.reasoning || "";  // ✅ 添加reasoning字段
```

**设计文档要求**：
```json
{
  "type": "thought",
  "step": 1,
  "content": "用户想要查看桌面文件夹...",
  "reasoning": "用户提到了'查看'和'文件夹'",
  "action_tool": "list_directory",
  "params": {}
}
```

---

## 9 待后端修复问题（需要后端配合）

| 序号 | 问题 | 后端位置 | 设计要求 |
|------|------|----------|---------|
| 1 | start缺少security_check | chat.py:700-710 | 添加security_check字段 |
| 2 | action_tool的type值错误 | chat.py:752,839 | type改为action_tool |
| 3 | action_tool缺少字段 | chat.py:838-847 | 添加raw_data, action_retry_count |
| 4 | observation缺少字段 | chat.py:851-860 | 添加raw_data, is_finished |
| 5 | status未整合 | 全局 | 统一使用type=status |
| 6 | error字段名错误 | chat.py:770,873 | error_message改为message |

---

**更新时间**: 2026-03-10 06:52:40
**编写人**: 小查
