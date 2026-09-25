# is_valid 字段接口说明文档

**创建时间**: 2026-03-03 15:45:00
**编写人**: 小沈
**接收人**: 小新

---

## 一、背景说明

为区分有效会话（真实用户创建的）和无效会话（测试代码创建的），新增 `is_valid` 字段。

---

## 二、接口变更

### 1. 创建会话 POST /sessions

**请求参数**：
```json
{
  "title": "会话标题（可选）"
}
```
**说明**：创建会话时默认 `is_valid=FALSE`，无需前端传递

---

### 2. 查询会话列表 GET /sessions

**响应字段**：
```json
{
  "sessions": [
    {
      "session_id": "xxx",
      "title": "会话标题",
      "message_count": 5,
      "is_valid": true,  // ✅ 新增字段：是否为有效会话
      "created_at": "2026-03-03T10:00:00Z",
      "updated_at": "2026-03-03T12:00:00Z"
    }
  ]
}
```

**过滤参数（可选）**：
- `?is_valid=true` - 只返回有效会话
- `?is_valid=false` - 只返回无效会话
- 不传 - 返回所有会话

---

### 3. 获取会话消息 GET /sessions/{session_id}/messages

**响应字段**：
```json
{
  "session_id": "xxx",
  "title": "会话标题",
  "is_valid": true,  // ✅ 新增字段：是否为有效会话
  "title_locked": false,
  "title_source": "user",
  "title_updated_at": "2026-03-03T10:00:00Z",
  "version": 1,
  "messages": [...]
}
```

---

## 三、逻辑说明

| 操作 | is_valid 值 | 说明 |
|------|------------|------|
| 创建会话 | FALSE | 默认无效 |
| 首次保存消息后 | **自动变为 TRUE** | 后端自动设置 |
| 后续保存消息 | 保持 TRUE | 不变 |

**后端自动管理**：前端无需关心 `is_valid` 的设置，后端会在首次保存消息时自动将会话标记为有效。

---

## 四、前端使用建议

### 4.1 显示会话列表时

```tsx
// 根据 is_valid 显示不同样式
{session.is_valid ? (
  <NormalSessionIcon />
) : (
  <GraySessionIcon title="无效会话" />
)}
```

### 4.2 过滤功能（可选）

```tsx
// 过滤显示有效会话
const validSessions = sessions.filter(s => s.is_valid);

// 过滤显示无效会话  
const invalidSessions = sessions.filter(s => !s.is_valid);
```

### 4.3 获取当前会话信息

```tsx
// 响应数据已包含 is_valid 字段
const { is_valid } = sessionData;
console.log('当前会话是否有效:', is_valid);
```

---

## 五、测试验证

### 测试1：创建会话后 is_valid 应为 FALSE
```bash
POST /sessions
# 返回 is_valid: false
```

### 测试2：保存消息后 is_valid 应变为 TRUE
```bash
POST /sessions/{id}/messages
# 保存消息后
GET /sessions/{id}/messages
# 返回 is_valid: true
```

---

## 六、注意事项

1. **后端自动管理**：前端不需要设置 `is_valid` 字段，后端会自动处理
2. **只读字段**：前端只需读取 `is_valid` 字段进行展示或过滤
3. **兼容现有逻辑**：消息保存逻辑不变，只增加了有效性标记

---

**更新时间**: 2026-03-03 15:45:00
