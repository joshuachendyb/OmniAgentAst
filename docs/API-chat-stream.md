# 聊天流式接口

**接口**: `POST /api/v1/chat/stream`

**编写人**: 小沈
**时间**: 2026-03-13 16:30:00

---

## 请求

```json
{
  "messages": [{"role": "user", "content": "你好"}],
  "stream": true
}
```

## 响应 (SSE) - 按顺序

| 序号 | type | 说明 |
|------|------|------|
| 1 | start | 任务开始 + 安全检查 |
| 2 | thought | 思考 (LLM分析任务) |
| 3 | action_tool | 工具调用 |
| 4 | observation | 观察结果 (工具执行结果反馈给LLM) |
| 5 | chunk | 内容片段 (is_reasoning=true=思考, false=回答) |
| 6 | final | 完成 |
| 7 | error | 错误 |
| 8 | incident | 执行状态 (interrupted/paused/resumed/retrying) |

---

## incident 类型（type=incident 时使用）

### 完整字段（共5个字段）

| 字段 | 类型 | 必填 | 说明 | 如何使用 |
|------|------|------|------|---------|
| type | string | ✅ 必填 | 固定值: `incident`，用于区分消息类型 | 前端根据 type 判断这是 incident 类型消息 |
| incident_value | string | ✅ 必填 | 状态值: interrupted/paused/resumed/retrying | 前端根据 incident_value 判断具体状态，执行对应逻辑 |
| message | string | ✅ 必填 | 用户友好的状态描述 | 直接显示给用户，或记录日志 |
| timestamp | string | ✅ 必填 | 时间戳 (YYYY-MM-DD HH:MM:SS) | 记录事件时间，用于日志追踪 |
| wait_time | int | ⚠️ 仅 retrying | 重试等待秒数 | 前端显示倒计时进度条 |

### incident_value 枚举

| incident_value | 说明 | 触发场景 | 前端处理逻辑 |
|----------------|------|---------|-------------|
| interrupted | 任务中断 | 用户点击取消按钮 / 客户端断开连接 | 停止 SSE 连接，显示"任务已取消" |
| paused | 任务暂停 | 检测到危险操作，需用户确认 | 弹出确认对话框，等待用户点击"继续"或"取消" |
| resumed | 任务恢复 | 用户点击"继续"按钮确认 | 关闭确认对话框，继续显示 AI 响应 |
| retrying | 请求重试中 | LLM 请求超时，自动重试 | 显示重试进度条，倒计时 wait_time 秒后继续 |

### 完整示例

**interrupted（中断）**
```json
{
  "type": "incident",
  "incident_value": "interrupted",
  "message": "任务已被中断",
  "timestamp": "2026-03-13 15:30:00"
}
```

**paused（暂停）**
```json
{
  "type": "incident",
  "incident_value": "paused",
  "message": "检测到危险操作，需要用户确认",
  "timestamp": "2026-03-13 15:30:00"
}
```

**resumed（恢复）**
```json
{
  "type": "incident",
  "incident_value": "resumed",
  "message": "任务已恢复",
  "timestamp": "2026-03-13 15:30:00"
}
```

**retrying（重试）**
```json
{
  "type": "incident",
  "incident_value": "retrying",
  "message": "请求超时，正在重试 (1/3)...",
  "wait_time": 2,
  "timestamp": "2026-03-13 15:30:00"
}
```

---

## error 类型（type=error 时使用）

### 完整字段（共11个字段）

| 字段 | 类型 | 必填 | 说明 | 如何使用 |
|------|------|------|------|---------|
| type | string | ✅ 必填 | 固定值: `error`，用于区分消息类型 | 前端根据 type 判断这是 error 类型消息 |
| error_type | string | ✅ 必填 | 错误类型 (见下表) | 前端根据 error_type 判断错误种类，显示对应提示 |
| message | string | ✅ 必填 | 用户友好的错误信息 | 直接显示给用户 |
| code | string | ✅ 必填 | 错误码 (如 TIMEOUT, SECURITY_BLOCKED) | 用于代码判断，做特定处理 |
| timestamp | string | ✅ 必填 | 时间戳 (YYYY-MM-DD HH:MM:SS) | 记录错误时间，用于日志追踪 |
| model | string | ❌ 可选 | 模型名称 | 显示错误来源时使用 |
| provider | string | ❌ 可选 | 提供商名称 | 显示错误来源时使用 |
| details | string | ❌ 可选 | 详细错误信息 | 调试时查看，不显示给用户 |
| stack | string | ❌ 可选 | 堆栈信息 | 仅调试用，不显示给用户 |
| retryable | bool | ❌ 可选 | 是否可重试 | true 时前端可显示"重试"按钮 |
| retry_after | int | ❌ 可选 | 重试等待秒数 | 前端显示倒计时 |

### error_type 枚举（代码中的实际值）

| error_type | 说明 | 触发场景 | code值 | retryable |
|------------|------|---------|--------|----------|
| network | 网络相关错误 | TimeoutError / ConnectionError / HTTPError | TIMEOUT / CONNECTION_ERROR / HTTP_ERROR | true |
| validation | 参数校验错误 | ValueError | VALIDATION_ERROR | false |
| file_system | 文件系统错误 | "not found" / "不存在" | NOT_FOUND | false |
| security | 权限不足错误 | "permission" / "权限" | PERMISSION_DENIED | false |
| security_error | 安全拦截错误 | 危险操作被安全检测拦截（待用户确认） | SECURITY_BLOCKED | false |
| agent | Agent执行错误 | Agent执行过程中返回的错误 | AGENT_ERROR | false |
| unknown | 未知错误 | 其他未捕获的异常 | UNKNOWN_ERROR | true |

### code 枚举（代码中的实际值）

| code | 说明 | 触发场景 |
|------|------|---------|
| TIMEOUT | 超时 | TimeoutError |
| CONNECTION_ERROR | 连接错误 | ConnectionError |
| HTTP_ERROR | HTTP错误 | HTTPError |
| VALIDATION_ERROR | 验证错误 | ValueError |
| NOT_FOUND | 资源不存在 | "not found" / "不存在" |
| PERMISSION_DENIED | 权限不足 | "permission" / "权限" |
| SECURITY_BLOCKED | 安全拦截 | 危险操作被安全检测拦截 |
| AGENT_ERROR | Agent错误 | Agent执行异常 |
| UNKNOWN_ERROR | 未知错误 | 其他未分类错误 |

### 完整示例

**network（超时）**
```json
{
  "type": "error",
  "error_type": "network",
  "message": "请求超时，请重试",
  "code": "TIMEOUT",
  "model": "gpt-4",
  "provider": "opencode",
  "retryable": true,
  "retry_after": 5,
  "timestamp": "2026-03-13 15:30:00"
}
```

**network（连接失败）**
```json
{
  "type": "error",
  "error_type": "network",
  "message": "网络连接失败，请检查网络",
  "code": "CONNECTION_ERROR",
  "provider": "opencode",
  "retryable": true,
  "retry_after": 10,
  "timestamp": "2026-03-13 15:30:00"
}
```

**security_error（安全拦截 - 待确认）**
```json
{
  "type": "error",
  "error_type": "security_error",
  "message": "危险操作需确认: rm -rf /",
  "code": "SECURITY_BLOCKED",
  "retryable": false,
  "timestamp": "2026-03-13 15:30:00"
}
```

**security（权限不足）**
```json
{
  "type": "error",
  "error_type": "security",
  "message": "权限不足，无法执行操作",
  "code": "PERMISSION_DENIED",
  "retryable": false,
  "timestamp": "2026-03-13 15:30:00"
}
```

**validation（参数错误）**
```json
{
  "type": "error",
  "error_type": "validation",
  "message": "参数值错误，请检查输入",
  "code": "VALIDATION_ERROR",
  "retryable": false,
  "timestamp": "2026-03-13 15:30:00"
}
```

**file_system（文件不存在）**
```json
{
  "type": "error",
  "error_type": "file_system",
  "message": "文件或资源不存在",
  "code": "NOT_FOUND",
  "retryable": false,
  "timestamp": "2026-03-13 15:30:00"
}
```

**agent（Agent执行错误）**
```json
{
  "type": "error",
  "error_type": "agent",
  "message": "Agent执行异常",
  "code": "AGENT_ERROR",
  "retryable": false,
  "timestamp": "2026-03-13 15:30:00"
}
```

**unknown（未知错误）**
```json
{
  "type": "error",
  "error_type": "unknown",
  "message": "AI 处理异常，请稍后重试",
  "code": "UNKNOWN_ERROR",
  "retryable": true,
  "retry_after": 5,
  "timestamp": "2026-03-13 15:30:00"
}
```

---

## 任务控制接口

### 1. 取消任务接口

**接口**: `POST /api/v1/chat/stream/cancel/{task_id}`

**参数**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| task_id | string | ✅ | 任务ID（URL路径参数） |
| session_id | string | ❌ | 会话ID（查询参数，用于阻止5分钟内重连） |

**请求示例**:
```bash
# 不带session_id（基础功能）
curl -X POST http://localhost:8000/api/v1/chat/stream/cancel/task_123

# 带session_id（阻止重连，推荐）
curl -X POST "http://localhost:8000/api/v1/chat/stream/cancel/task_123?session_id=session_abc"
```

**响应**:
```json
{
  "success": true,
  "message": "任务 task_123 已中断"
}
```

**功能说明**:
- 标记任务为中断状态
- 强制关闭HTTP连接，立即终止LLM调用
- 如果传入session_id，会记录中断状态，5分钟内禁止同一会话重连
- 向后兼容：不传session_id也能工作

---

### 2. 暂停任务接口

**接口**: `POST /api/v1/chat/stream/pause/{task_id}`

**参数**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| task_id | string | ✅ | 任务ID（URL路径参数） |
| session_id | string | ❌ | 会话ID（查询参数） |

**请求示例**:
```bash
curl -X POST "http://localhost:8000/api/v1/chat/stream/pause/task_123?session_id=session_abc"
```

**响应**:
```json
{
  "success": true,
  "message": "任务 task_123 已暂停"
}
```

**功能说明**:
- 暂停任务的执行（但后端继续处理，数据暂存缓冲区）
- 前端停止显示AI响应

---

### 3. 恢复任务接口

**接口**: `POST /api/v1/chat/stream/resume/{task_id}`

**参数**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| task_id | string | ✅ | 任务ID（URL路径参数） |
| session_id | string | ❌ | 会话ID（查询参数） |

**请求示例**:
```bash
curl -X POST "http://localhost:8000/api/v1/chat/stream/resume/task_123?session_id=session_abc"
```

**响应**:
```json
{
  "success": true,
  "message": "任务 task_123 已继续"
}
```

**功能说明**:
- 恢复暂停的任务
- 前端恢复显示暂存的数据

---

## 错误响应

任务控制接口的错误响应：

```json
{
  "success": false,
  "message": "任务 task_123 不存在"
}
```

---

**编写人**: 小沈
**更新时间**: 2026-03-14 10:00:00
