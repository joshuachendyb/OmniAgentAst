# Chat API 接口分析文档

**创建时间**: 2026-03-03 17:00:00
**编写人**: 小沈

---

## 一、后端接口梳理

### 1.1 接口列表

| 序号 | 接口路径 | 方法 | 用途 | 前端调用处 |
|------|---------|------|------|-----------|
| 1 | `/chat` | POST | 发送对话请求（非流式） | api.ts:157 `sendMessage` |
| 2 | `/chat/stream` | POST | 发送对话请求（流式 SSE） | sse.ts:199 `sendMessage` |
| 3 | `/chat/stream/cancel/{task_id}` | POST | 中断任务 | NewChatContainer.tsx |
| 4 | `/chat/validate` | GET | 验证服务状态 | api.ts:253 |
| 5 | `/chat/switch/{provider}` | POST | 切换提供商 | api.ts:265 |

---

## 二、核心接口详细分析

### 2.1 `/chat` 接口（非流式）

**请求格式**：
```json
POST /api/v1/chat
{
  "messages": [
    {"role": "user", "content": "你好"},
    {"role": "assistant", "content": "你好！有什么可以帮助你的？"},
    {"role": "user", "content": "帮我读取文件 test.txt"}
  ],
  "stream": false,
  "temperature": 0.7,
  "provider": "openai",  // 可选
  "model": "gpt-4"       // 可选
}
```

**响应格式**：
```json
{
  "success": true,
  "content": "这是 AI 的回复内容",
  "model": "gpt-4",
  "provider": "openai",
  "error": null
}
```

**前端调用**：
```typescript
// api.ts:157
sendMessage: async (
  messages: ChatMessage[],
  temperature: number = 0.7
): Promise<ChatResponse> => {
  const response = await api.post<ChatResponse>("/chat", {
    messages,
    stream: false,
    temperature,
  });
  return response.data;
}
```

**后端处理逻辑**：
1. 验证消息列表
2. 检测文件操作意图
3. 如果是文件操作 → 路由到 `handle_file_operation`
4. 否则 → 调用 AI 服务

---

### 2.2 `/chat/stream` 接口（流式 SSE）

**请求格式**：
```json
POST /api/v1/chat/stream
{
  "messages": [
    {"role": "user", "content": "你好"}
  ],
  "stream": true,
  "task_id": "uuid-xxx",  // 可选，用于中断
  "provider": "openai",
  "model": "gpt-4"
}
```

**响应格式**：SSE 流式数据
```
data: {"type": "start", "display_name": "OpenAI (gpt-4)", "task_id": "xxx"}

data: {"type": "thought", "content": "正在分析任务..."}

data: {"type": "action", "step": 1, "content": "检测到文件操作意图..."}

data: {"type": "observation", "step": 1, "content": "安全检测通过"}

data: {"type": "chunk", "content": "这是 AI 回复的片段"}

data: {"type": "final", "content": "完整的 AI 回复内容"}
```

**前端调用**：
```typescript
// sse.ts:199
const sendMessage = useCallback(
  async (content: string) => {
    const response = await fetch(`${config.baseURL}/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        messages: [{ role: "user", content: content }],
        stream: true,
        task_id: taskId || undefined,
      }),
      signal: controller.signal,
    });
    // 处理 SSE 流...
  }
);
```

**后端处理逻辑**：
1. 生成/使用 task_id
2. 发送 start 事件
3. 检测文件操作意图
4. 如果是文件操作 → 使用 FileOperationAgent
5. 否则 → 使用普通 AI 对话
6. 流式返回结果

---

### 2.3 `/chat/stream/cancel/{task_id}` 接口

**用途**：中断正在执行的任务

**前端调用**：
```typescript
// NewChatContainer.tsx:1220
await fetch(`${API_BASE_URL}/chat/stream/cancel/${taskIdToCancel}`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
});
```

---

## 三、接口改造分析

### 3.1 需要改造的接口

| 接口 | 改造范围 | 前端影响 |
|------|---------|---------|
| `/chat` | **需要改造** - 使用新的意图分类器 | **无影响** - 请求/响应格式不变 |
| `/chat/stream` | **需要改造** - 使用新的意图分类器 | **无影响** - 请求/响应格式不变 |
| `/chat/stream/cancel/{task_id}` | 无需改造 | 无影响 |
| `/chat/validate` | 无需改造 | 无影响 |
| `/chat/switch/{provider}` | 无需改造 | 无影响 |

### 3.2 改造策略

**核心原则**：
1. **接口不变**：请求/响应格式完全不变
2. **内部逻辑替换**：只替换意图检测和路由逻辑
3. **向前兼容**：保留原有的 `detect_file_operation_intent` 作为备选

**改造步骤**：

**Step 1**: 复制 `chat.py` 到 `newchat.py`
```bash
cp chat.py newchat.py
```

**Step 2**: 在 `newchat.py` 中修改意图检测逻辑
```python
# 原逻辑
is_file_op, op_type, confidence = detect_file_operation_intent(last_message)
if is_file_op and confidence >= 0.3:
    return await handle_file_operation(last_message, op_type)

# 新逻辑
intent_type, action_type, confidence = classify_intent(last_message)
if intent_type == IntentType.ACTION:
    if action_type == ActionType.FILE_OPERATION:
        return await handle_file_operation_v2(last_message, action_type)
    elif action_type == ActionType.DATABASE_OPERATION:
        # 未来扩展
        pass
```

**Step 3**: 测试新逻辑
- 单元测试验证意图分类
- 集成测试验证接口响应
- 前端回归测试验证功能

**Step 4**: 切换路由（可选）
```python
# router.py
# 原路由
app.include_router(chat.router, prefix="/api/v1", tags=["chat"])

# 新路由（测试通过后）
app.include_router(newchat.router, prefix="/api/v1", tags=["chat"])
```

---

## 四、前端对接说明

### 4.1 前端无需修改

由于接口格式完全不变，前端**无需任何修改**：

```typescript
// 前端调用保持不变
await chatApi.sendMessage(messages);
// 或
await sendStreamMessage(content);
```

### 4.2 未来扩展（可选）

如果未来需要前端感知动作类型，可以在响应中添加可选字段：

```json
{
  "success": true,
  "content": "AI 回复内容",
  "intent_type": "action",      // 新增（可选）
  "action_type": "file_operation", // 新增（可选）
  "confidence": 0.95            // 新增（可选）
}
```

**但这不是必须的**，当前方案前端完全无感知。

---

## 五、总结

### 5.1 接口数量
- **核心接口**: 2个（`/chat` 和 `/chat/stream`）
- **辅助接口**: 3个（cancel、validate、switch）

### 5.2 改造范围
- **需要改造**: 2个核心接口的内部逻辑
- **无需改造**: 3个辅助接口 + 所有前端代码

### 5.3 风险评估
- **接口兼容性**: ✅ 完全兼容，前端无感知
- **数据格式**: ✅ 完全兼容，请求/响应不变
- **功能影响**: ✅ 保留原有逻辑，新逻辑作为增强

### 5.4 建议实施方案
1. 创建 `newchat.py` 副本
2. 在副本上实现新逻辑
3. 充分测试（单元测试 + 集成测试）
4. 选择合适时机切换路由

---

**更新时间**: 2026-03-03 17:00:00
