# 保留历史消息的display_name实现方法说明

**创建时间**: 2026-03-04 00:23:52  
**编写人**: 小沈  
**版本**: v1.0

---

## 目录

1. [需求背景](#1-需求背景)
2. [设计思路](#2-设计思路)
3. [架构设计](#3-架构设计)
4. [实现细节](#4-实现细节)
5. [关键代码说明](#5-关键代码说明)
6. [完整使用流程](#6-完整使用流程)
7. [模型切换支持](#7-模型切换支持)
8. [特殊场景处理](#8-特殊场景处理)
9. [总结](#9-总结)

---

## 1. 需求背景

### 1.1 问题提出

在AI助手对话系统中，用户可能会在不同时间使用不同的AI模型（如模型A、模型B、模型C）。为了让用户在查看历史消息时能够知道当时使用的是哪个模型，需要在保存消息时同时记录当时使用的模型显示名称（display_name）。

### 1.2 初始方案的问题

最初的设计思路是让前端在保存消息时传递 `display_name` 参数，但存在以下问题：

1. **多余的来回传递**：后端在发送流式响应时已经知道 `display_name`，不需要前端再传回来
2. **前端逻辑复杂**：前端需要额外存储和传递 `display_name`
3. **不符合架构设计原则**：后端自己知道的信息，应该自己处理

---

## 2. 设计思路

### 2.1 核心设计原则

1. **后端自己知道，自己处理**：后端在流式响应开始时就已经知道 `display_name`，应该自己缓存和使用
2. **使用缓存机制**：用 `session_id` 作为 key，缓存 `display_name`
3. **支持模型切换**：每次新的流式响应都更新缓存，始终保持最新值
4. **对前端透明**：前端不需要知道缓存的存在，只需要传递 `session_id`

### 2.2 关键决策

| 决策项 | 决策结果 | 说明 |
|---------|---------|------|
| 缓存位置 | 后端内存 | 简单高效，不需要持久化 |
| 缓存Key | session_id | 与会话绑定，天然唯一 |
| 更新时机 | 每次start事件 | 确保每次对话都用最新的模型 |
| 获取时机 | 保存AI回复时 | 仅AI回复需要，用户消息不需要 |

---

## 3. 架构设计

### 3.1 整体架构图

```
┌─────────────────────────────────────────────────────────────┐
│                     前端 (Frontend)                          │
├─────────────────────────────────────────────────────────────┤
│  1. 保存用户消息 (saveMessage)                              │
│     - 传递 session_id, role="user", content               │
│                                                             │
│  2. 调用流式接口 (/chat/stream)                            │
│     - 传递 session_id, messages, stream=true              │
│                                                             │
│  3. 接收流式响应 (SSE)                                      │
│     - start事件: display_name, provider, model            │
│     - chunk事件: 内容片段                                   │
│     - final事件: 最终内容                                   │
│                                                             │
│  4. 保存AI回复 (saveMessage)                                │
│     - 传递 session_id, role="assistant", content          │
│     - 不需要传递 display_name！                              │
└─────────────────────────────────────────────────────────────┘
                            ↕
┌─────────────────────────────────────────────────────────────┐
│                     后端 (Backend)                          │
├─────────────────────────────────────────────────────────────┤
│  ┌───────────────────────────────────────────────────────┐  │
│  │  缓存模块 (display_name_cache.py)                   │  │
│  │  - cache_display_name(session_id, display_name)    │  │
│  │  - get_cached_display_name(session_id)             │  │
│  └───────────────────────────────────────────────────────┘  │
│                          ↑↓                               │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  聊天接口 (chat.py)                                 │  │
│  │  - 接收 /chat/stream 请求                          │  │
│  │  - 在start事件时缓存 display_name                 │  │
│  └───────────────────────────────────────────────────────┘  │
│                          ↑↓                               │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  会话接口 (sessions.py)                              │  │
│  │  - 接收 saveMessage 请求                            │  │
│  │  - 从缓存获取 display_name (仅AI回复)              │  │
│  │  - 保存到数据库                                    │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 模块依赖关系

```
display_name_cache.py (共享缓存模块)
    ↑
    ├─ chat.py (在start事件时缓存)
    └─ sessions.py (在saveMessage时获取)
```

---

## 4. 实现细节

### 4.1 缓存模块实现

**文件位置**: `backend/app/utils/display_name_cache.py`

**核心数据结构**:
```python
# 内存缓存，key为session_id，value为display_name
display_name_cache: Dict[str, str] = {}
```

**核心函数**:

1. **cache_display_name(session_id, display_name)**
   - 功能：缓存会话对应的模型显示名称
   - 参数：
     - `session_id`: 会话ID
     - `display_name`: 模型显示名称（如 "OpenAI (GPT-4)"）
   - 行为：覆盖已存在的key，确保总是最新值

2. **get_cached_display_name(session_id)**
   - 功能：从缓存获取会话对应的模型显示名称
   - 参数：`session_id`: 会话ID
   - 返回：缓存的display_name，如果没有则返回None

### 4.2 聊天接口修改

**文件位置**: `backend/app/api/v1/chat.py`

**修改内容**:

1. **ChatRequest模型添加session_id字段**
   ```python
   class ChatRequest(BaseModel):
       messages: List[ChatMessage]
       stream: bool = False
       # ... 其他字段 ...
       session_id: Optional[str] = Field(
           default=None, 
           description="会话ID - 用于缓存display_name"
       )
   ```

2. **在start事件时缓存display_name**
   ```python
   # 在发送start事件之前
   display_name = f"{get_provider_display_name(ai_service.provider)} ({ai_service.model})"
   
   # 如果前端传递了session_id，就缓存
   if request.session_id:
       cache_display_name(request.session_id, display_name)
   
   # 然后发送start事件
   yield f"data: {json.dumps({
       'type': 'start',
       'display_name': display_name,
       # ... 其他字段 ...
   })}\n\n"
   ```

### 4.3 会话接口修改

**文件位置**: `backend/app/api/v1/sessions.py`

**修改内容**:

1. **导入缓存函数**
   ```python
   from app.utils.display_name_cache import get_cached_display_name
   ```

2. **save_message函数从缓存获取display_name**
   ```python
   async def save_message(session_id: str, message: MessageCreate):
       # ... 前面的逻辑 ...
       
       # 从缓存获取display_name（仅AI回复且前端未提供时）
       display_name_to_save = message.display_name
       if message.role == "assistant" and not display_name_to_save:
           display_name_to_save = get_cached_display_name(session_id)
       
       # 插入消息
       cursor.execute(
           'INSERT INTO chat_messages (session_id, role, content, timestamp, display_name) VALUES (?, ?, ?, ?, ?)',
           (session_id, message.role, message.content, utc_time, display_name_to_save)
       )
       
       # ... 后面的逻辑 ...
   ```

### 4.4 前端修改

**文件1**: `frontend/src/utils/sse.ts`

**修改内容**:

1. **sendMessage函数增加sessionId参数**
   ```typescript
   const sendMessage = useCallback(
     async (content: string, sessionId?: string) => {
       // ... 前面的逻辑 ...
       
       const response = await fetch(url, {
         method: "POST",
         headers: { /* ... */ },
         body: JSON.stringify({
           messages: [{ role: "user", content: content }],
           stream: true,
           task_id: taskId || undefined,
           session_id: sessionId || undefined, // 新增：传递sessionId
         }),
         signal: controller.signal,
       });
       
       // ... 后面的逻辑 ...
     },
     []
   );
   ```

**文件2**: `frontend/src/components/Chat/NewChatContainer.tsx`

**修改内容**:

1. **调用sendStreamMessage时传递sessionId**
   ```typescript
   // 发送流式请求 - 传递sessionId用于后端缓存display_name
   sendStreamMessage(userMessage.content, currentSessionIdRef.current || sessionId);
   ```

2. **保存AI回复时不再传递display_name**
   ```typescript
   await sessionApi.saveMessage(currentSessionId, {
     role: "assistant",
     content: fullResponse,
     // 不传递display_name，后端从缓存自动获取
   });
   ```

---

## 5. 关键代码说明

### 5.1 缓存模块完整代码

```python
"""
display_name 缓存模块

用于在保存AI回复时，自动获取当时使用的模型显示名称
支持模型切换：每次新的流式响应都会更新缓存中的最新值

创建时间: 2026-03-03
编写人: 小沈
"""

from typing import Dict, Optional
from app.utils.logger import logger

# ⭐ 缓存机制：存储 session_id 到 display_name 的映射
display_name_cache: Dict[str, str] = {}


def cache_display_name(session_id: str, display_name: str):
    """
    缓存 session_id 对应的 display_name
    
    Args:
        session_id: 会话ID
        display_name: 模型显示名称（如 "OpenAI (GPT-4)"）
    """
    display_name_cache[session_id] = display_name
    logger.debug(f"缓存 display_name: session_id={session_id}, display_name={display_name}")


def get_cached_display_name(session_id: str) -> Optional[str]:
    """
    从缓存中获取 session_id 对应的 display_name
    
    Args:
        session_id: 会话ID
        
    Returns:
        缓存的 display_name，如果没有则返回 None
    """
    display_name = display_name_cache.get(session_id)
    logger.debug(f"获取缓存 display_name: session_id={session_id}, display_name={display_name}")
    return display_name
```

### 5.2 缓存时机关键代码

```python
# chat.py 中
display_name = f"{get_provider_display_name(ai_service.provider)} ({ai_service.model})"

# 如果前端传递了session_id，就缓存
if request.session_id:
    cache_display_name(request.session_id, display_name)

# 然后发送start事件给前端
yield f"data: {json.dumps({
    'type': 'start',
    'display_name': display_name,
    'provider': ai_service.provider,
    'model': ai_service.model,
    'task_id': task_id
})}\n\n"
```

### 5.3 获取缓存关键代码

```python
# sessions.py 中
# 从缓存获取display_name（仅AI回复且前端未提供时）
display_name_to_save = message.display_name
if message.role == "assistant" and not display_name_to_save:
    display_name_to_save = get_cached_display_name(session_id)
    logger.debug(f"从缓存获取 display_name: session_id={session_id}, display_name={display_name_to_save}")

# 插入消息到数据库
cursor.execute(
    'INSERT INTO chat_messages (session_id, role, content, timestamp, display_name) VALUES (?, ?, ?, ?, ?)',
    (session_id, message.role, message.content, utc_time, display_name_to_save)
)
```

---

## 6. 完整使用流程

### 6.1 正常对话流程

```
1. 用户在聊天界面输入消息
   ↓
2. 前端检查是否有session_id
   - 如果没有，先创建新会话，获取session_id
   ↓
3. 前端保存用户消息
   - 调用 saveMessage(session_id, {role: "user", content: "..."})
   ↓
4. 前端调用流式接口
   - 调用 /chat/stream，传递session_id
   ↓
5. 后端处理流式请求
   - 确定使用的模型
   - 生成display_name（如 "OpenAI (GPT-4)"）
   - 用session_id缓存display_name
   - 发送start事件给前端（包含display_name）
   - 发送流式内容
   - 发送final事件
   ↓
6. 前端接收流式响应并显示
   ↓
7. 前端保存AI回复
   - 调用 saveMessage(session_id, {role: "assistant", content: "..."})
   - 不传递display_name！
   ↓
8. 后端处理保存请求
   - 检测到是AI回复
   - 从缓存中获取该session_id对应的display_name
   - 保存到数据库，包含display_name
   ↓
9. 完成！
```

---

## 7. 模型切换支持

### 7.1 切换流程示例

```
第1次对话（使用模型A）
├─ 前端调用 /chat/stream，传递session_id="abc123"
├─ 后端生成display_name="模型A (GPT-4)"
├─ 后端缓存: { "abc123": "模型A (GPT-4)" }
├─ 前端保存AI回复
├─ 后端从缓存获取display_name="模型A (GPT-4)"
└─ 数据库保存: display_name="模型A (GPT-4)"

第2次对话（切换到模型B）
├─ 用户在设置页面切换到模型B
├─ 前端调用 /chat/stream，传递session_id="abc123"
├─ 后端生成display_name="模型B (Claude-3)"
├─ 后端缓存更新: { "abc123": "模型B (Claude-3)" }  ← 覆盖旧值
├─ 前端保存AI回复
├─ 后端从缓存获取display_name="模型B (Claude-3)"
└─ 数据库保存: display_name="模型B (Claude-3)"

第3次对话（切换到模型C）
├─ 前端调用 /chat/stream，传递session_id="abc123"
├─ 后端生成display_name="模型C (Gemini-Pro)"
├─ 后端缓存更新: { "abc123": "模型C (Gemini-Pro)" }  ← 总是最新
├─ 前端保存AI回复
├─ 后端从缓存获取display_name="模型C (Gemini-Pro)"
└─ 数据库保存: display_name="模型C (Gemini-Pro)"
```

### 7.2 为什么这样设计

| 设计点 | 说明 |
|---------|------|
| **覆盖旧值** | 每次新的对话都覆盖缓存，确保用的是最新模型 |
| **会话级别** | 缓存key是session_id，不同会话互不影响 |
| **内存缓存** | 不需要持久化，服务重启后重新对话会重新缓存 |

---

## 8. 特殊场景处理

### 8.1 新会话场景（系统初见）

**场景描述**: 用户第一次使用系统，没有历史会话

**处理流程**:
```
1. 前端显示新会话界面，session_id=null
   ↓
2. 用户输入第一条消息
   ↓
3. 前端先创建新会话
   - 调用 createSession()，获取session_id="xyz789"
   ↓
4. 前端保存用户消息
   - 调用 saveMessage("xyz789", {role: "user", content: "..."})
   ↓
5. 前端调用流式接口
   - 调用 /chat/stream，传递session_id="xyz789"
   ↓
6. 后端缓存display_name
   - 缓存: { "xyz789": "OpenAI (GPT-4)" }
   ↓
7. 前端保存AI回复
   - 不传递display_name
   ↓
8. 后端从缓存获取并保存
   - ✅ 正常工作！
```

### 8.2 缓存未命中场景

**场景描述**: 由于某种原因，缓存中没有该session_id对应的display_name

**处理方式**:
```python
# sessions.py 中
display_name_to_save = message.display_name
if message.role == "assistant" and not display_name_to_save:
    display_name_to_save = get_cached_display_name(session_id)
    # 如果缓存中没有，display_name_to_save就是None
    # 数据库中该字段就是NULL（这是可以接受的）

# 插入消息时，如果display_name_to_save是None
# 数据库中该字段就是NULL，不影响其他功能
```

**为什么可以接受**:
- 这是极端情况（服务重启、缓存清空等）
- 不会导致系统崩溃
- 只是该条历史消息没有模型名称显示
- 用户再次对话时会重新缓存

### 8.3 用户消息不需要display_name

**设计原则**: 只有AI回复才需要记录display_name

| 消息类型 | 是否需要display_name | 说明 |
|---------|-------------------|------|
| user消息 | ❌ 不需要 | 用户发的消息，不涉及AI模型 |
| assistant消息 | ✅ 需要 | AI回复，需要记录用了哪个模型 |
| system消息 | ❌ 不需要 | 系统提示，不涉及AI模型 |

---

## 9. 总结

### 9.1 核心优势

1. **架构清晰**
   - 共享缓存模块，职责单一
   - chat.py负责缓存，sessions.py负责获取
   - 符合单一职责原则

2. **对前端透明**
   - 前端只需要传递session_id
   - 不需要知道缓存的存在
   - 不需要额外存储display_name

3. **完美支持模型切换**
   - 每次新的对话都更新缓存
   - 总是使用最新的模型名称
   - 不同会话互不影响

4. **符合设计原则**
   - 后端自己知道的信息，自己处理
   - 不需要多余的来回传递
   - 代码简洁高效

### 9.2 文件修改清单

| 文件 | 修改类型 | 说明 |
|------|---------|------|
| `backend/app/utils/display_name_cache.py` | 新增 | 共享缓存模块 |
| `backend/app/api/v1/chat.py` | 修改 | ChatRequest添加session_id，start事件时缓存 |
| `backend/app/api/v1/sessions.py` | 修改 | 导入缓存函数，saveMessage时获取 |
| `frontend/src/utils/sse.ts` | 修改 | sendMessage增加sessionId参数 |
| `frontend/src/components/Chat/NewChatContainer.tsx` | 修改 | 调用时传递sessionId，不传递display_name |

### 9.3 Git提交信息

```
commit 6ca1085
Author: 小沈
Date:   2026-03-03 23:55:00

    feat: display_name缓存机制 - 后端自己保存display_name，无需前端传递

    修改内容:
    1. 新增共享缓存模块 display_name_cache.py
    2. chat.py: ChatRequest添加session_id字段，start事件时缓存
    3. sessions.py: 从缓存获取display_name（仅AI回复）
    4. sse.ts: sendMessage增加sessionId参数
    5. NewChatContainer.tsx: 传递sessionId，不传递display_name

    特点:
    - 后端自己知道display_name，不需要前端来回传递
    - 完美支持模型切换（每次对话更新缓存）
    - 对前端透明，只需要传递session_id
```

---

**文档完成时间**: 2026-03-04 00:23:52  
**编写人**: 小沈  
**版本**: v1.0
