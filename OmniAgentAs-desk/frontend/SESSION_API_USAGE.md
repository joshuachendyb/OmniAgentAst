# 会话管理API使用文档 - 小新第二

**文档版本**：v1.0  
**创建时间**：2026-03-01 20:19:41  
**编写者**：小新第二  
**适用范围**：OmniAgentAs-desk前端会话管理功能

---

## 📋 目录

1. [API概览](#api概览)
2. [接口详情](#接口详情)
3. [前端使用方式](#前端使用方式)
4. [常见问题](#常见问题)
5. [错误处理](#错误处理)

---

## API概览

### 会话数据结构

```typescript
interface Session {
  session_id: string;        // 会话UUID
  title: string;             // 会话标题
  title_locked: boolean;     // 标题是否被用户锁定
  title_source: "user" | "auto"; // 标题来源
  title_updated_at: string;  // 标题最后更新时间
  version: number;           // 乐观锁版本号
  created_at: string;        // 创建时间
  updated_at: string;        // 更新时间
  message_count: number;     // 消息数量
}

interface Message {
  id: number;
  session_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: string;
  execution_steps?: any[];   // 执行步骤（可选）
}
```

---

## 接口详情

### 1. 创建会话
- **URL**: `POST /api/v1/sessions`
- **描述**: 创建一个新的会话
- **请求体**:
  ```json
  {
    "title": "可选的会话标题"
  }
  ```
- **响应**:
  ```json
  {
    "session_id": "会话UUID",
    "title": "会话标题",
    "created_at": "创建时间",
    "updated_at": "更新时间",
    "message_count": 0
  }
  ```
- **使用场景**: 用户点击"新建对话"按钮

### 2. 获取会话列表
- **URL**: `GET /api/v1/sessions?page=1&page_size=20&keyword=`
- **描述**: 分页获取会话列表
- **参数**:
  - `page`: 页码，默认1
  - `page_size`: 每页数量，默认20，最大100
  - `keyword`: 搜索关键词（可选）
- **响应**:
  ```json
  {
    "total": 100,
    "page": 1,
    "page_size": 20,
    "sessions": [Session对象数组]
  }
  ```
- **使用场景**: 历史会话页面列表展示

### 3. 获取会话消息
- **URL**: `GET /api/v1/sessions/{session_id}/messages`
- **描述**: 获取指定会话的所有消息
- **路径参数**: `session_id`
- **响应**:
  ```json
  {
    "session_id": "会话UUID",
    "title": "会话标题",
    "title_locked": false,
    "title_source": "auto",
    "title_updated_at": "标题更新时间",
    "version": 1,
    "messages": [Message对象数组]
  }
  ```
- **使用场景**: 加载历史会话内容到聊天界面

### 4. 保存消息到会话
- **URL**: `POST /api/v1/sessions/{session_id}/messages`
- **描述**: 向指定会话添加一条消息
- **路径参数**: `session_id`
- **请求体**:
  ```json
  {
    "role": "user",
    "content": "消息内容"
  }
  ```
- **响应**:
  ```json
  {
    "success": true,
    "message_id": 123,
    "message_count": 5,
    "title_updated": false
  }
  ```
- **使用场景**: 用户发送消息或AI回复时保存

### 5. 更新会话标题
- **URL**: `PUT /api/v1/sessions/{session_id}`
- **描述**: 更新会话标题（乐观锁版本控制）
- **路径参数**: `session_id`
- **请求体**:
  ```json
  {
    "title": "新标题",
    "version": 1,              // 必须提供版本号
    "updated_by": "user"       // 可选
  }
  ```
- **响应**:
  ```json
  {
    "success": true,
    "title": "新标题",
    "version": 2
  }
  ```
- **使用场景**: 用户手动修改会话标题

### 6. 删除会话
- **URL**: `DELETE /api/v1/sessions/{session_id}`
- **描述**: 软删除指定会话
- **路径参数**: `session_id`
- **响应**:
  ```json
  {
    "success": true,
    "message": "会话删除成功"
  }
  ```
- **使用场景**: 用户删除会话

### 7. 批量获取会话标题状态
- **URL**: `GET /api/v1/sessions/titles/batch?session_ids=id1,id2,id3`
- **描述**: 一次性获取多个会话的标题状态信息
- **参数**: `session_ids` - 逗号分隔的会话ID列表
- **响应**:
  ```json
  {
    "sessions": [
      {
        "session_id": "id1",
        "title": "标题1",
        "title_locked": true,
        "title_updated_at": "时间戳"
      }
    ]
  }
  ```
- **使用场景**: 优化多会话标题状态获取性能

---

## 前端使用方式

### 1. 创建会话
```typescript
import { sessionApi } from '../services/api';

try {
  const response = await sessionApi.createSession('我的会话');
  console.log('会话创建成功:', response.session_id);
} catch (error) {
  console.error('创建会话失败:', error);
}
```

### 2. 获取会话列表
```typescript
try {
  const response = await sessionApi.listSessions(1, 20);
  console.log('会话总数:', response.total);
  console.log('会话列表:', response.sessions);
} catch (error) {
  console.error('获取会话列表失败:', error);
}
```

### 3. 加载会话消息
```typescript
try {
  const response = await sessionApi.getSessionMessages(sessionId);
  console.log('会话标题:', response.title);
  console.log('标题锁定:', response.title_locked);
  console.log('消息数量:', response.messages.length);
} catch (error) {
  console.error('加载会话消息失败:', error);
}
```

### 4. 保存消息
```typescript
try {
  const response = await sessionApi.saveMessage(sessionId, {
    role: 'user',
    content: '用户的消息'
  });
  console.log('消息保存成功:', response);
} catch (error) {
  console.error('保存消息失败:', error);
}
```

### 5. 更新会话标题
```typescript
try {
  // 先获取当前会话信息获取版本号
  const sessionInfo = await sessionApi.getSessionMessages(sessionId);
  const version = sessionInfo.version; // 获取当前版本号
  
  const response = await sessionApi.updateSession(sessionId, '新标题', version);
  console.log('会话标题更新成功:', response);
} catch (error) {
  if (error.response?.status === 409) {
    console.error('版本冲突，请刷新后重试');
  } else {
    console.error('更新会话标题失败:', error);
  }
}
```

### 6. 批量获取标题状态
```typescript
try {
  const response = await sessionApi.getSessionTitlesBatch([sessionId1, sessionId2]);
  console.log('批量标题状态:', response.sessions);
} catch (error) {
  console.error('批量获取标题状态失败:', error);
}
```

---

## 常见问题

### Q1: 执行历史消息在历史会话加载时丢失
**原因**: 后端 `getSessionMessages` 接口返回的消息对象中，`execution_steps` 可能是字符串而不是数组。

**解决方案**: 
```typescript
// 处理执行步骤数据
if (message.execution_steps) {
  // 如果是字符串，解析为JSON
  if (typeof message.execution_steps === 'string') {
    try {
      message.execution_steps = JSON.parse(message.execution_steps);
    } catch (e) {
      console.error('解析执行步骤失败:', e);
      message.execution_steps = [];
    }
  }
}
```

### Q2: 乐观锁版本冲突（HTTP 409错误）
**原因**: 多个用户同时修改会话标题，或前端版本号过旧。

**解决方案**:
- 重新获取会话信息，获取最新版本号
- 重试更新操作

### Q3: 会话创建后标题被覆盖
**原因**: 创建会话后，系统根据第一条消息自动更新标题。

**解决方案**:
- 创建会话后立即锁定标题：调用 `updateSession` 并确保业务逻辑正确处理

---

## 错误处理

| HTTP状态码 | 含义 | 前端处理建议 |
|------------|------|--------------|
| 404 | 会话不存在 | 显示错误信息，引导用户返回会话列表 |
| 409 | 版本冲突 | 提示用户刷新页面，重新获取最新数据 |
| 500 | 服务器内部错误 | 记录错误日志，显示通用错误信息 |
| 400 | 请求参数错误 | 验证用户输入，显示具体错误信息 |

### 前端错误处理示例
```typescript
try {
  const response = await sessionApi.updateSession(sessionId, newTitle, version);
  // 成功处理
} catch (error) {
  if (error.response?.status === 409) {
    // 版本冲突处理
    message.warning('会话已被其他用户修改，请刷新后重试');
  } else if (error.response?.status === 404) {
    // 会话不存在
    message.error('会话不存在，请返回会话列表');
  } else {
    // 其他错误
    message.error('操作失败，请重试');
  }
}
```

---

**更新时间**: 2026-03-01 20:19:41  
**版本**: v1.0