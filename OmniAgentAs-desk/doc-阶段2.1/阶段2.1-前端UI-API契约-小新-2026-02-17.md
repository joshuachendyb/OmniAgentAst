# API契约文档 - 阶段2.1

**制定人**: 小新  
**制定时间**: 2026-02-17 23:35:00  
**版本**: v1.0  
**用途**: 前后端开发约定，Mock数据参考

---

## 1. 配置管理接口

### 1.1 获取配置
```
GET /api/v1/config
```

**响应**:
```json
{
  "ai_provider": "zhipuai",
  "ai_model": "glm-4.7-flash",
  "api_key_configured": true,
  "theme": "light",
  "language": "zh-CN"
}
```

**字段说明**:
| 字段 | 类型 | 说明 |
|------|------|------|
| ai_provider | string | 当前AI提供商: zhipuai/opencode |
| ai_model | string | 当前模型名称 |
| api_key_configured | boolean | API Key是否已配置（脱敏） |
| theme | string | 主题: light/dark |
| language | string | 语言: zh-CN/en |

---

### 1.2 更新配置
```
PUT /api/v1/config
```

**请求**:
```json
{
  "ai_provider": "zhipuai",
  "zhipu_api_key": "sk-xxxxxxxx",
  "opencode_api_key": "",
  "theme": "light"
}
```

**响应**:
```json
{
  "success": true,
  "message": "配置已更新"
}
```

---

### 1.3 验证配置
```
POST /api/v1/config/validate
```

**请求**:
```json
{
  "provider": "zhipuai",
  "api_key": "sk-xxxxxxxx"
}
```

**响应**:
```json
{
  "valid": true,
  "message": "API Key有效",
  "model": "glm-4.7-flash"
}
```

**错误响应**:
```json
{
  "valid": false,
  "message": "API Key无效: 认证失败"
}
```

---

## 2. 会话管理接口

### 2.1 创建会话
```
POST /api/v1/sessions
```

**响应**:
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "新会话",
  "created_at": "2026-02-17T23:35:00Z"
}
```

---

### 2.2 获取会话列表
```
GET /api/v1/sessions?page=1&page_size=20&keyword=xxx
```

**响应**:
```json
{
  "total": 100,
  "page": 1,
  "page_size": 20,
  "sessions": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "title": "整理下载文件夹",
      "created_at": "2026-02-17T10:00:00Z",
      "updated_at": "2026-02-17T11:30:00Z",
      "message_count": 15
    }
  ]
}
```

---

### 2.3 获取会话消息
```
GET /api/v1/sessions/{session_id}/messages
```

**响应**:
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "messages": [
    {
      "id": 1,
      "role": "user",
      "content": "帮我整理下载文件夹",
      "timestamp": "2026-02-17T10:00:00Z",
      "execution_steps": null
    },
    {
      "id": 2,
      "role": "assistant",
      "content": "好的，我发现下载文件夹有15个文件...",
      "timestamp": "2026-02-17T10:00:05Z",
      "execution_steps": [
        {
          "type": "thought",
          "content": "我需要先查看下载文件夹的内容",
          "timestamp": 1708201200000
        },
        {
          "type": "action",
          "tool": "list_directory",
          "params": {"path": "/Users/xxx/Downloads"},
          "result": "15个文件",
          "timestamp": 1708201205000
        }
      ]
    }
  ]
}
```

---

### 2.4 删除会话
```
DELETE /api/v1/sessions/{session_id}
```

**响应**:
```json
{
  "success": true,
  "message": "会话已删除"
}
```

---

## 3. 安全接口

### 3.1 检查命令安全性
```
POST /api/v1/security/check
```

**请求**:
```json
{
  "command": "rm -rf /"
}
```

**响应**:
```json
{
  "safe": false,
  "risk": "检测到危险命令: rm -rf /",
  "suggestion": "该操作将删除系统所有文件"
}
```

**安全命令响应**:
```json
{
  "safe": true,
  "risk": "",
  "suggestion": ""
}
```

---

## 4. 流式执行过程接口

### 4.1 获取执行过程（流式）
```
GET /api/v1/chat/execution/{session_id}/stream
```

**响应**: SSE (Server-Sent Events)

```
event: step
data: {"type": "thought", "content": "正在分析任务...", "timestamp": 1708201200000}

event: step
data: {"type": "action", "tool": "list_directory", "params": {"path": "/Users/xxx/Downloads"}, "timestamp": 1708201201000}

event: step
data: {"type": "observation", "result": "15个文件", "timestamp": 1708201202000}

event: complete
data: {"type": "final", "content": "任务完成", "timestamp": 1708201205000}
```

**事件类型**:
| 类型 | 说明 |
|------|------|
| thought | AI思考过程 |
| action | 工具调用 |
| observation | 工具执行结果 |
| error | 执行错误 |
| final | 最终结果 |
| complete | 流结束 |

---

## 5. TypeScript类型定义

```typescript
// types/api.ts

// 配置
export interface Config {
  ai_provider: 'zhipuai' | 'opencode';
  ai_model: string;
  api_key_configured: boolean;
  theme: 'light' | 'dark';
  language: string;
}

// 会话
export interface Session {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
}

// 消息
export interface Message {
  id: number;
  session_id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  execution_steps?: ExecutionStep[];
}

// 执行步骤
export interface ExecutionStep {
  type: 'thought' | 'action' | 'observation' | 'error' | 'final';
  content?: string;
  tool?: string;
  params?: Record<string, any>;
  result?: any;
  timestamp: number;
}

// 安全检查
export interface SecurityCheck {
  safe: boolean;
  risk: string;
  suggestion: string;
}
```

---

## 6. Mock数据

### 6.1 会话列表Mock
```typescript
export const mockSessions: Session[] = [
  {
    id: '550e8400-e29b-41d4-a716-446655440000',
    title: '整理下载文件夹',
    created_at: '2026-02-17T10:00:00Z',
    updated_at: '2026-02-17T11:30:00Z',
    message_count: 15
  },
  {
    id: '550e8400-e29b-41d4-a716-446655440001',
    title: '截图当前窗口',
    created_at: '2026-02-16T15:00:00Z',
    updated_at: '2026-02-16T15:05:00Z',
    message_count: 8
  }
];
```

### 6.2 执行步骤Mock
```typescript
export const mockExecutionSteps: ExecutionStep[] = [
  {
    type: 'thought',
    content: '我需要先查看下载文件夹的内容',
    timestamp: Date.now()
  },
  {
    type: 'action',
    tool: 'list_directory',
    params: { path: '/Users/xxx/Downloads' },
    timestamp: Date.now() + 1000
  },
  {
    type: 'observation',
    result: '15个文件（5个压缩包、8个文档、2个安装包）',
    timestamp: Date.now() + 2000
  },
  {
    type: 'thought',
    content: '我应该创建3个文件夹来分类存放',
    timestamp: Date.now() + 3000
  },
  {
    type: 'action',
    tool: 'create_directory',
    params: { names: ['压缩包', '文档', '安装包'] },
    timestamp: Date.now() + 4000
  },
  {
    type: 'final',
    content: '已创建3个文件夹，请确认是否移动文件',
    timestamp: Date.now() + 5000
  }
];
```

---

**文档状态**: 已定稿（Day 1上午）  
**后端开发人员**: 小沈  
**前端开发人员**: 小新

---

**变更记录**:
| 版本 | 时间 | 修改人 | 变更内容 |
|------|------|--------|----------|
| v1.0 | 2026-02-17 23:35:00 | 小新 | 初始版本，定义全部API契约 |
