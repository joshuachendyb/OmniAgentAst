# 会话管理API使用文档

**文档版本**：v1.5
**创建时间**：2026-03-01 20:19:41
**更新时间**：2026-03-02 14:50:00
**编写者**：小新第二
**更新者**：小沈
**适用范围**：OmniAgentAs-desk前端会话管理功能

---

## 📋 目录

1. [数据存储说明](#数据存储说明)
2. [接口概览](#接口概览)
3. [接口详情](#接口详情)
4. [核心流程说明](#核心流程说明)
5. [前端使用方式](#前端使用方式)
6. [常见问题](#常见问题)
7. [错误处理](#错误处理)

---

## 核心流程说明

### 流程一：创建会话流程

**触发时机**：用户点击"新建对话"按钮

```
用户点击"新建对话"
   ↓
【第1步】前端调用创建会话API
   sessionApi.createSession()
   ↓
【第2步】后端处理
   2.1 生成UUID作为session_id
   2.2 如果没提供标题，自动生成（如"新会话 2026-03-02 14:30"）
   2.3 插入到chat_sessions表（message_count=0）
   2.4 返回session_id和会话信息
   ↓
【第3步】前端获取session_id
   ↓
【第4步】跳转到聊天页面
   window.history.pushState({}, "", `/?session_id=${session_id}`)
   ↓
完成
```

**涉及的后端API**：
| API | 方法 | 说明 |
|-----|------|------|
| `/api/v1/sessions` | POST | 创建新会话 |

---

### 流程二：发送消息流程

**触发时机**：用户发送消息或AI回复

```
用户输入消息，点击发送
   ↓
【第1步】前端保存用户消息
   await sessionApi.saveMessage(sessionId, {
     role: "user",
     content: "用户消息内容"
   })
   ↓
【第2步】后端处理
   2.1 插入消息到 chat_messages 表
   2.2 更新 chat_sessions.message_count + 1
   2.3 返回 message_count
   ↓
【第3步】调用AI生成回复
   ↓
【第4步】前端保存AI消息
   await sessionApi.saveMessage(sessionId, {
     role: "assistant",
     content: "AI回复内容"
   })
   ↓
【第5步】后端处理（同第2步）
   ↓
完成
```

**涉及的后端API**：
| API | 方法 | 说明 |
|-----|------|------|
| `/api/v1/sessions/{session_id}/messages` | POST | 保存消息 |

**重要**：
- 用户消息和AI消息都调用同一个API
- 只是 role 不同：user / assistant
- message_count 自动+1，不需要单独处理

---

### 流程三：查看历史会话流程

**触发时机**：用户进入历史会话页面

```
用户点击"历史"tab
   ↓
【第1步】前端调用获取会话列表API
   sessionApi.listSessions(page, pageSize, keyword)
   ↓
【第2步】后端处理
   2.1 查询chat_sessions表
   2.2 按创建时间倒序排列
   2.3 返回会话列表（包含message_count）
   ↓
【第3步】前端显示会话列表
   展示：标题、消息数量、更新时间
   ↓
完成
```

**涉及的后端API**：
| API | 方法 | 说明 |
|-----|------|------|
| `/api/v1/sessions` | GET | 获取会话列表 |

---

### 流程四：加载历史消息流程

**触发时机**：用户点击某个历史会话

```
用户点击历史会话中的某一个
   ↓
【第1步】获取URL中的session_id
   ↓
【第2步】前端调用获取消息API
   sessionApi.getSessionMessages(sessionId)
   ↓
【第3步】后端处理
   3.1 查询chat_sessions表获取会话信息
   3.2 查询chat_messages表获取所有消息
   3.3 返回会话详情+消息列表
   ↓
【第4步】前端显示消息列表
   ↓
完成
```

**涉及的后端API**：
| API | 方法 | 说明 |
|-----|------|------|
| `/api/v1/sessions/{session_id}/messages` | GET | 获取会话消息 |

---

### 流程五：修改标题流程

**触发时机**：用户手动修改会话标题

```
用户点击标题，进入编辑状态
   ↓
【第1步】前端获取当前version
   sessionApi.getSessionMessages(sessionId)
   ↓
【第2步】用户输入新标题，点击保存
   ↓
【第3步】前端调用更新API
   sessionApi.updateSession(sessionId, newTitle, version)
   ↓
【第4步】后端处理
   4.1 检查version是否匹配（乐观锁）
   4.2 更新chat_sessions表的title
   4.3 设置title_locked=true
   4.4 记录标题历史到chat_session_title_history表
   4.5 返回更新结果
   ↓
【第5步】前端显示更新结果
   ↓
完成
```

**涉及的后端API**：
| API | 方法 | 说明 |
|-----|------|------|
| `/api/v1/sessions/{session_id}` | GET | 获取会话（含version） |
| `/api/v1/sessions/{session_id}` | PUT | 更新会话标题 |

---

### 流程六：删除会话流程

**触发时机**：用户删除某个会话

```
用户点击删除按钮
   ↓
【第1步】前端确认删除
   ↓
【第2步】前端调用删除API
   sessionApi.deleteSession(sessionId)
   ↓
【第3步】后端处理（软删除）
   3.1 设置chat_sessions表的is_deleted=true
   3.2 返回删除成功
   ↓
【第4步】前端刷新会话列表
   ↓
完成
```

**涉及的后端API**：
| API | 方法 | 说明 |
|-----|------|------|
| `/api/v1/sessions/{session_id}` | DELETE | 删除会话 |

---

## 数据存储说明

### 数据库表结构

| 表名 | 存什么 |
|------|--------|
| `chat_sessions` | 会话基本信息（ID、标题、message_count、创建/更新时间等） |
| `chat_messages` | 消息内容（role、content、timestamp），通过session_id关联会话 |
| `chat_session_title_history` | 标题历史，通过session_id关联会话 |

### 消息数量说明

- **message_count**：消息数量，不是写入的，是自动计算的
- 保存消息时，后端自动执行 `message_count = message_count + 1`
- **不需要** 单独写入消息数量

---

## 接口概览

### 会话数据结构

```typescript
interface Session {
  session_id: string;        // 会话UUID
  title: string;            // 会话标题
  created_at: string;       // 创建时间
  updated_at: string;       // 更新时间
  message_count: number;    // 消息数量（自动计算）
}

interface SessionWithDetails {
  session_id: string;
  title: string;
  title_locked: boolean;     // 标题是否被用户锁定
  title_source: "user" | "auto"; // 标题来源：user=用户手动，auto=自动
  title_updated_at: string;  // 标题最后更新时间
  version: number;           // 乐观锁版本号
  created_at: string;
  updated_at: string;
  message_count: number;
}

interface Message {
  id: number;
  session_id: string;
  role: "user" | "assistant" | "system";  // user=用户，assistant=AI，system=系统
  content: string;
  timestamp: string;
  execution_steps?: any[];
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
- **重要**: 会话ID由后端生成UUID

---

### 2. 获取会话列表
- **URL**: `GET /api/v1/sessions?page=1&page_size=20&keyword=`
- **描述**: 分页获取会话列表
- **参数**:
  - `page`: 页码，默认1
  - `page_size`: 每页数量，默认20，最大100
  - `keyword`: 搜索关键词（可选，按标题搜索）
- **响应**:
  ```json
  {
    "total": 100,
    "page": 1,
    "page_size": 20,
    "sessions": [
      {
        "session_id": "uuid",
        "title": "会话标题",
        "created_at": "2026-03-02T10:00:00Z",
        "updated_at": "2026-03-02T11:00:00Z",
        "message_count": 5
      }
    ]
  }
  ```
- **使用场景**: 历史会话页面列表展示

---

### 3. 获取单个会话（不含消息）
- **URL**: `GET /api/v1/sessions/{session_id}`
- **描述**: 获取单个会话的基本信息（不包含消息内容）
- **路径参数**: `session_id` - 会话ID
- **响应**:
  ```json
  {
    "session_id": "uuid",
    "title": "会话标题",
    "created_at": "2026-03-02T10:00:00Z",
    "updated_at": "2026-03-02T11:00:00Z",
    "message_count": 5
  }
  ```
- **使用场景**: 查看会话详情、获取message_count

---

### 4. 获取会话消息
- **URL**: `GET /api/v1/sessions/{session_id}/messages`
- **描述**: 获取指定会话的所有消息内容
- **路径参数**: `session_id` - 会话ID
- **响应**:
  ```json
  {
    "session_id": "uuid",
    "title": "会话标题",
    "title_locked": false,
    "title_source": "auto",
    "title_updated_at": "2026-03-02T10:00:00Z",
    "version": 1,
    "messages": [
      {
        "id": 1,
        "session_id": "uuid",
        "role": "user",
        "content": "用户消息",
        "timestamp": "2026-03-02T10:00:00Z",
        "execution_steps": null
      },
      {
        "id": 2,
        "session_id": "uuid",
        "role": "assistant",
        "content": "AI回复",
        "timestamp": "2026-03-02T10:00:01Z",
        "execution_steps": null
      }
    ]
  }
  ```
- **使用场景**: 加载历史会话内容到聊天界面

---

### 5. 保存消息到会话
- **URL**: `POST /api/v1/sessions/{session_id}/messages`
- **描述**: 向指定会话添加一条消息（自动更新message_count）
- **路径参数**: `session_id` - 会话ID
- **请求体**:
  ```json
  {
    "role": "user",
    "content": "消息内容"
  }
  ```
- **role参数说明**:
  - `user` - 用户发送的消息
  - `assistant` - AI回复的消息
  - `system` - 系统消息
- **响应**:
  ```json
  {
    "success": true,
    "message_id": 123,
    "message_count": 5,
    "title_updated": false
  }
  ```
- **重要**: 
  - 保存消息后，message_count自动+1
  - 用户消息和AI消息都用这个接口，只是role不同
- **使用场景**: 用户发送消息或AI回复时保存

---

### 6. 更新会话标题
- **URL**: `PUT /api/v1/sessions/{session_id}`
- **描述**: 更新会话标题（乐观锁版本控制）
- **路径参数**: `session_id` - 会话ID
- **请求体**:
  ```json
  {
    "title": "新标题",
    "version": 1
  }
  ```
- **响应**:
  ```json
  {
    "success": true,
    "session_id": "uuid",
    "title": "新标题",
    "title_locked": true,
    "title_source": "user",
    "version": 2,
    "updated_at": "2026-03-02T10:00:00Z"
  }
  ```
- **使用场景**: 用户手动修改会话标题

---

### 7. 删除会话
- **URL**: `DELETE /api/v1/sessions/{session_id}`
- **描述**: 删除指定会话（软删除）
- **路径参数**: `session_id` - 会话ID
- **响应**:
  ```json
  {
    "success": true,
    "message": "会话已删除"
  }
  ```
- **使用场景**: 用户删除会话

---

### 8. 批量获取会话标题
- **URL**: `GET /api/v1/sessions/titles/batch?session_ids=id1,id2,id3`
- **描述**: 一次性获取多个会话的标题信息
- **参数**: `session_ids` - 逗号分隔的会话ID列表
- **响应**:
  ```json
  {
    "sessions": [
      {
        "session_id": "id1",
        "title": "标题1",
        "title_locked": true,
        "title_updated_at": "时间戳",
        "message_count": 5
      }
    ]
  }
  ```
- **使用场景**: 优化多会话标题状态获取性能

---

### 流程七：自动创建会话流程（系统自动创建）

**触发时机**：用户首次发消息时，如果没有会话则自动创建

**触发代码位置**：`frontend/src/components/Chat/NewChatContainer.tsx` 第1220-1235行

```javascript
let currentSessionId = sessionId;
if (!currentSessionId) {
  // 用户第一次发消息时，如果没有会话，自动创建
  const newSession = await sessionApi.createSession(
    inputValue.trim().substring(0, 50)
  );
  currentSessionId = newSession.session_id;
}
```

**前置条件**：
1. 用户首次访问页面（没有URL带session_id）
2. 没有最近会话可以加载
3. 用户直接输入消息点击发送

**完整流程**：
```
用户首次访问页面（无session_id）
   ↓
尝试加载最近会话 → 失败/没有
   ↓
用户输入消息，点击发送
   ↓
【检测到没有sessionId】→ 自动创建新会话
   ↓
后续发送消息流程（同流程二）
```

**与用户主动创建的区别**：
| | 用户主动创建 | 系统自动创建 |
|---|---|---|
| 触发 | 点击"新建对话"按钮 | 首次发消息时无会话 |
| 标题 | 用户输入或自动生成 | 使用消息前50字作为标题 |
| 时机 | 任意时刻 | 只有首次发消息时 |

---

### 流程八：搜索会话流程

**触发时机**：用户在历史页面输入关键词搜索

**触发代码位置**：`frontend/src/pages/History/index.tsx` 第79-85行

```javascript
const loadSessions = async (page: number = 1, searchKeyword?: string) => {
  // ...
  const response = await sessionApi.listSessions(page, pageSize, searchKeyword);
  // ...
};
```

**完整流程**：
```
用户进入历史会话页面
   ↓
用户输入搜索关键词
   ↓
点击搜索/按回车
   ↓
【第1步】前端调用列表API，带keyword参数
   sessionApi.listSessions(1, 20, keyword)
   ↓
【第2步】后端处理
   2.1 查询chat_sessions表
   2.2 使用LIKE模糊匹配标题
   2.3 返回匹配的会话列表
   ↓
【第3步】前端显示搜索结果
   ↓
完成
```

**涉及的后端API**：
| API | 方法 | 说明 |
|-----|------|------|
| `/api/v1/sessions` | GET | 获取会话列表（keyword参数） |

**搜索说明**：
- 只支持按**标题**搜索
- 支持模糊匹配（如输入"测试"会匹配"测试会话1"）
- 搜索结果分页返回

---

## API汇总表

### 读取类API

| 序号 | API | 方法 | 参数 | 返回 | 说明 |
|------|-----|------|------|------|------|
| 1 | `/api/v1/sessions` | GET | page, page_size, keyword | 会话列表 | 获取会话列表（分页+搜索） |
| 2 | `/api/v1/sessions/{session_id}` | GET | session_id(路径) | 会话详情 | 获取单个会话（不含消息） |
| 3 | `/api/v1/sessions/{session_id}/messages` | GET | session_id(路径) | 消息列表 | 获取会话的所有消息 |
| 4 | `/api/v1/sessions/titles/batch` | GET | session_ids(query) | 标题列表 | 批量获取会话标题 |

### 写入类API

| 序号 | API | 方法 | 参数 | 返回 | 说明 |
|------|-----|------|------|------|------|
| 5 | `/api/v1/sessions` | POST | title(body) | 新会话 | 创建新会话 |
| 6 | `/api/v1/sessions/{session_id}/messages` | POST | session_id(路径), role, content(body) | 保存结果 | 保存消息（自动+1 message_count） |
| 7 | `/api/v1/sessions/{session_id}` | PUT | session_id(路径), title, version(body) | 更新结果 | 更新会话标题 |
| 8 | `/api/v1/sessions/{session_id}` | DELETE | session_id(路径) | 删除结果 | 删除会话（软删除） |

---

## 核心要点汇总

### 1. session_id 由后端生成
- 所有会话的 session_id 都是后端用 UUID 生成
- 前端不需要自己生成

### 2. message_count 自动计算
- 保存消息时后端自动 +1
- 不需要单独写入

### 3. role 参数
- `user` - 用户消息
- `assistant` - AI消息
- `system` - 系统消息

### 4. 乐观锁
- 更新标题需要 version 参数
- 版本冲突返回 409

### 5. 软删除
- 删除会话不是真正删除，是设置 is_deleted=true

---

## 前端使用方式

### 1. 创建会话
```typescript
import { sessionApi } from '../services/api';

try {
  const response = await sessionApi.createSession('我的会话');
  console.log('会话创建成功:', response.session_id);
  console.log('消息数量:', response.message_count);  // 初始为0
} catch (error) {
  console.error('创建会话失败:', error);
}
```

### 2. 获取会话列表
```typescript
try {
  const response = await sessionApi.listSessions(1, 20);
  console.log('会话总数:', response.total);
  response.sessions.forEach(session => {
    console.log(session.title, '-', session.message_count, '条消息');
  });
} catch (error) {
  console.error('获取会话列表失败:', error);
}
```

### 3. 获取单个会话详情
```typescript
try {
  const response = await sessionApi.getSession(sessionId);
  console.log('会话标题:', response.title);
  console.log('消息数量:', response.message_count);
} catch (error) {
  console.error('获取会话详情失败:', error);
}
```

### 4. 加载会话消息
```typescript
try {
  const response = await sessionApi.getSessionMessages(sessionId);
  console.log('会话标题:', response.title);
  console.log('消息数量:', response.messages.length);
  response.messages.forEach(msg => {
    console.log(msg.role, ':', msg.content);
  });
} catch (error) {
  console.error('加载会话消息失败:', error);
}
```

### 5. 保存消息（用户发送）
```typescript
try {
  const response = await sessionApi.saveMessage(sessionId, {
    role: 'user',
    content: '用户的消息内容'
  });
  console.log('消息保存成功');
  console.log('当前消息数量:', response.message_count);  // 自动+1
} catch (error) {
  console.error('保存消息失败:', error);
}
```

### 6. 保存消息（AI回复）
```typescript
try {
  // AI回复也是用同一个接口，只是role不同
  const response = await sessionApi.saveMessage(sessionId, {
    role: 'assistant',
    content: 'AI的回复内容'
  });
  console.log('AI消息保存成功');
  console.log('当前消息数量:', response.message_count);
} catch (error) {
  console.error('保存AI消息失败:', error);
}
```

### 7. 更新会话标题
```typescript
try {
  // 先获取会话信息（包含version）
  const sessionInfo = await sessionApi.getSessionMessages(sessionId);
  const version = sessionInfo.version;
  
  const response = await sessionApi.updateSession(sessionId, '新标题', version);
  console.log('会话标题更新成功:', response.title);
} catch (error) {
  if (error.response?.status === 409) {
    console.error('版本冲突，请刷新后重试');
  } else {
    console.error('更新会话标题失败:', error);
  }
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

**更新时间**: 2026-03-02 14:50:00
**版本**: v1.5
**更新者**: 小沈

**更新内容**:
- v1.5: 新增API汇总表、核心要点汇总
- v1.4: 新增流程八：搜索会话流程
- v1.3: 新增流程七：自动创建会话流程
- v1.2: 新增6个核心业务流程说明
- v1.1: 新增数据存储说明章节、新增"获取单个会话"接口、修正role参数、删除过时Q3
- v1.0: 初始版本（小新第二）
