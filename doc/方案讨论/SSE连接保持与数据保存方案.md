# SSE连接保持与数据保存方案

**创建时间**: 2026-03-16 10:35:00
**版本**: v1.0
**存放位置**: D:\OmniAgentAs-desk\doc\方案讨论\

---

## 一、问题背景

### 1.1 问题描述

在使用SSE流式输出时，如果用户切换应用或刷新页面，最后一条AI消息会丢失，原因是：
- SSE连接断开时，`onComplete` 回调不会触发
- 数据没有保存到数据库

### 1.2 问题场景分析

| 场景 | 原因 | 是否保存 | 是否有办法 |
|------|------|---------|-----------|
| 页面切换 | disconnect断开，onComplete不调用 | ❌ 不保存 | ✅ 有办法（方案2/4） |
| 刷新页面 | 页面销毁，onComplete不调用 | ❌ 不保存 | ✅ 有办法（方案4） |
| 浏览器崩溃 | 任何保存都不触发 | ❌ 不保存 | ✅ 有办法（方案4） |
| 网络断开 | SSE断开，可能不触发onError | ❌ 不保存 | ❌ 没办法 |

---

## 二、解决方案汇总

经过调研和分析，共发现以下6种可能的解决方案：

| 方案 | 页面切换 | 刷新页面 | 浏览器崩溃 | 实现复杂度 |
|------|---------|---------|-----------|-----------|
| **方案1：页面隐藏时保存到数据库** | ✅ | ✅ | ❌ | 低 |
| **方案2：页面隐藏时保持SSE** | ✅ | ❌ | ❌ | 低 |
| **方案3：Service Worker接管SSE** | ⚠️ | ⚠️ | ❌ | 高 |
| **方案4：IndexedDB实时存储** | ✅ | ✅ | ✅ | 中 |
| **方案5：sendBeacon** | ⚠️ | ❌ | ⚠️ | 低 |
| **方案6：页面卸载前保存** | ⚠️ | ❌ | ⚠️ | 低 |

---

## 三、方案详细分析

### 方案1：页面隐藏时保存到数据库

#### 3.1.1 原理

在页面隐藏（visibilitychange）时，主动调用保存接口，将当前已接收的内容保存到数据库。

#### 3.1.2 流程

```
用户切换应用 → visibilitychange (hidden)
  ↓
1. saveState() 保存到 sessionStorage（保持不变）
  ↓
2. saveIncompleteMessageToDB() 保存到数据库 ← 新增
  ↓
3. disconnect() 断开SSE（保持不变）
  ↓
页面恢复时 → 从数据库加载 → 显示完整内容
```

#### 3.1.3 技术实现

**后端修改**：
```python
# messages 表添加 status 字段
status: str = Field(default="complete")  # "complete" | "incomplete"

# saveMessage API 支持 status 参数
async def save_message(session_id: str, message: MessageCreate, status: str = "complete"):
    # 保存时记录状态
```

**前端修改**：
```typescript
// visibilitychange (hidden) 时
if (isReceiving) {
  await sessionApi.saveMessage(sessionId, {
    role: "assistant",
    content: finalResponse,  // 当前已接收的内容
    execution_steps: executionStepsRef.current,
    status: "incomplete",     // 标记为未完成
  });
}
```

#### 3.1.4 优点

- ✅ 刷新页面后能从数据库加载已接收的内容
- ✅ 实现简单，复用现有saveMessage逻辑
- ✅ 兼容性好，所有浏览器支持
- ✅ 即使SSE断开也能保存

#### 3.1.5 缺点

- ❌ 需要后端配合添加status字段
- ❌ 页面切换瞬间正在接收的内容可能丢失（取决于保存时机）
- ❌ 浏览器崩溃场景无法处理

#### 3.1.6 适用场景

- 页面切换
- 刷新页面

---

### 方案2：页面隐藏时保持SSE连接

#### 3.2.1 原理

使用支持后台连接的SSE库，在页面隐藏时不断开SSE连接，让数据在后台继续接收。

#### 3.2.2 技术实现

使用 `@microsoft/fetch-event-source` 库：

```typescript
import { FetchEventSource } from "@microsoft/fetch-event-source";

const eventSource = new FetchEventSource('/api/chat/stream', {
  openWhenHidden: true,  // 页面隐藏时保持连接
  onmessage(event) {
    // 处理接收到的数据
  },
  onerror(error) {
    // 处理错误
  }
});
```

如果使用原生 `EventSource`，需要改用上述库。

#### 3.2.3 优点

- ✅ 页面隐藏时后台继续接收数据
- ✅ 用户返回时内容已完整接收
- ✅ 不需要后端配合
- ✅ 用户体验最好

#### 3.2.4 缺点

- ❌ 移动端浏览器（iOS Safari、Android Chrome）会强制断开后台连接
- ❌ 刷新页面时仍然会断开（页面完全销毁）
- ❌ 消耗更多服务器资源（后台保持连接）

#### 3.2.5 适用场景

- 桌面端标签切换
- 桌面端切换应用（保持后台运行）
- **不适合**：刷新页面、移动端

---

### 方案3：Service Worker接管SSE

#### 3.3.1 原理

使用Service Worker作为中间层，让Service Worker保持与后端的SSE连接，页面与Service Worker通信。

#### 3.3.2 架构

```
┌─────────────┐     SSE      ┌─────────────┐
│   页面A     │◀───────────▶│  Service    │
│  (已关闭)   │             │  Worker     │
└─────────────┘             └─────────────┘
        │                          │
        │ MessageChannel           │ SSE
        ▼                          ▼
┌─────────────┐             ┌─────────────┐
│   页面B     │◀───────────▶│   后端      │
│  (新打开)   │             │   API       │
└─────────────┘             └─────────────┘
```

#### 3.3.3 优点

- ✅ 理论上页面关闭后Service Worker仍能接收数据
- ✅ 可以实现多标签页共享连接

#### 3.3.4 缺点

- ❌ **浏览器限制**：Service Worker会被自动终止（30秒无活动）
- ❌ **SSE限制**：SSE连接无法在Service Worker中保持长连接
- ❌ 实现复杂，需要处理心跳保活
- ❌ 需要额外学习成本
- ❌ 刷新页面时Service Worker也会重启

#### 3.3.5 适用场景

- **不推荐使用**：浏览器和SSE的技术限制导致难以实现

---

### 方案4：IndexedDB实时存储

#### 3.4.1 原理

使用浏览器本地数据库IndexedDB，在每个chunk到达时实时保存，页面恢复时从IndexedDB加载。

#### 3.4.2 技术实现

```typescript
import { openDB } from 'idb';

const dbPromise = openDB('chat-cache', 1, {
  upgrade(db) {
    db.createObjectStore('messages', { keyPath: 'id' });
  }
});

// 每个chunk到达时保存
const saveChunk = async (sessionId: string, chunk: any) => {
  const db = await dbPromise;
  await db.put('messages', {
    sessionId,
    content: chunk.content,
    executionSteps: chunk.executionSteps,
    timestamp: Date.now()
  });
};

// 页面恢复时加载
const loadFromIndexedDB = async (sessionId: string) => {
  const db = await dbPromise;
  return db.get('messages', sessionId);
};
```

#### 3.4.3 优点

- ✅ 实时存储，页面崩溃不丢失任何chunk
- ✅ 不依赖后端API
- ✅ 刷新页面后可恢复

#### 3.4.4 缺点

- ❌ 需要与后端数据库同步（去重、合并逻辑复杂）
- ❌ 实现成本中等（需要引入idb库）
- ❌ 数据冗余（本地和后端各存一份）
- ❌ 清理逻辑复杂（何时删除IndexedDB中的数据）

#### 3.4.5 适用场景

- 对数据完整性要求极高的场景
- **不适合**：当前项目（同步逻辑复杂）

---

### 方案5：sendBeacon

#### 3.5.1 原理

使用`navigator.sendBeacon`在页面卸载时发送数据，浏览器会保证请求发送。

#### 3.5.2 技术实现

```typescript
window.addEventListener('unload', () => {
  navigator.sendBeacon('/api/save-incomplete', JSON.stringify({
    sessionId,
    messages: messagesRef.current,
    executionSteps: executionStepsRef.current
  }));
});
```

#### 3.5.3 优点

- ✅ 页面关闭时保证发送
- ✅ 浏览器原生支持

#### 3.5.4 缺点

- ❌ 只能发送简单数据，不能等待响应
- ❌ 网络可能已断开，发送可能失败
- ❌ **不触发刷新**：刷新页面不触发unload事件
- ❌ 成功率不高（网络断开时仍可能失败）

#### 3.5.5 适用场景

- 作为兜底方案辅助其他方案
- **不适合**：单独使用

---

### 方案6：页面卸载前保存

#### 3.6.1 原理

使用 `beforeunload` 事件在页面卸载前保存当前状态。

#### 3.6.2 技术实现

```typescript
window.addEventListener('beforeunload', (event) => {
  if (isReceiving) {
    // 同步保存（会阻塞页面关闭）
    saveToDatabase();
    event.preventDefault();
    event.returnValue = '';
  }
});
```

#### 3.6.3 优点

- ✅ 页面关闭前一刻保存

#### 3.6.4 缺点

- ❌ 用户体验差（页面关闭延迟）
- ❌ 刷新页面时行为不确定
- ❌ 移动端不支持
- ❌ 现代浏览器可能不保证执行

#### 3.6.5 适用场景

- **不推荐使用**：用户体验太差

---

## 四、方案对比

### 4.1 功能对比

| 方案 | 页面切换 | 刷新页面 | 浏览器崩溃 | 网络断开 |
|------|---------|---------|-----------|---------|
| 方案1：数据库保存 | ✅ | ✅ | ❌ | ❌ |
| 方案2：保持SSE | ✅ | ❌ | ❌ | ❌ |
| 方案3：Service Worker | ⚠️ | ⚠️ | ❌ | ❌ |
| 方案4：IndexedDB | ✅ | ✅ | ✅ | ❌ |
| 方案5：sendBeacon | ⚠️ | ❌ | ⚠️ | ❌ |
| 方案6：beforeunload | ⚠️ | ❌ | ❌ | ❌ |

### 4.2 实现复杂度对比

| 方案 | 复杂度 | 后端配合 | 额外依赖 |
|------|--------|---------|---------|
| 方案1：数据库保存 | 低 | 需要 | 无 |
| 方案2：保持SSE | 低 | 不需要 | 可能需要换库 |
| 方案3：Service Worker | 高 | 不需要 | 无 |
| 方案4：IndexedDB | 中 | 不需要 | idb库 |
| 方案5：sendBeacon | 低 | 需要 | 无 |
| 方案6：beforeunload | 低 | 需要 | 无 |

### 4.3 最佳组合方案（更新）

**根据讨论，确定最佳组合：方案2 + 方案4**

#### 为什么是方案2+4

| 对比项 | 方案1(被否定) | 方案2 | 方案4 | 方案2+4组合 |
|--------|---------------|-------|-------|------------|
| 页面切换(桌面) | ✅ | ✅ | ✅ | ✅ |
| 刷新页面 | ✅ | ❌ | ✅ | ✅ |
| 浏览器崩溃 | ❌ | ❌ | ✅ | ✅ |
| 移动端后台 | ⚠️ | ❌ | ⚠️ | ⚠️ |
| 实现复杂度 | 低 | 低 | 中 | 中 |
| 后端配合 | 需要 | 不需要 | 不需要 | 不需要 |
| 数据完整性 | 一般 | 好 | 最好 | 最好 |

**方案1被否定的原因**：
- 需要后端配合修改数据库结构
- 实现成本反而比方案4高
- 方案4 IndexedDB不需要后端配合

```
┌─────────────────────────────────────────────────────┐
│              最佳组合方案（方案2 + 方案4）           │
├─────────────────────────────────────────────────────┤
│                                                     │
│  场景1：页面切换（桌面端）                          │
│    → 方案2：保持SSE连接                            │
│    → 后台继续接收，用户返回时内容完整               │
│                                                     │
│  场景2：刷新页面                                    │
│    → 方案4：IndexedDB中已有完整数据                │
│    → 刷新后从IndexedDB加载，显示完整内容            │
│                                                     │
│  场景3：浏览器崩溃                                  │
│    → 方案4：IndexedDB实时存储                      │
│    → 每个chunk实时保存，崩溃不丢失                  │
│                                                     │
│  场景4：网络断开                                    │
│    → IndexedDB中已有部分数据                        │
│    → 网络恢复后可继续或重新发送                     │
│                                                     │
└─────────────────────────────────────────────────────┘
```

#### 备选组合：方案2 + 方案5

如果方案4实现复杂，可以用方案5作为简化版：
- 方案2：保持SSE连接（处理页面切换）
- 方案5：sendBeacon（刷新页面兜底）

---

## 五、推荐方案详解

### 5.1 方案2实现步骤（先做）

1. **检查当前SSE库**
   - 位置：搜索 `new EventSource` 或 `FetchEventSource`
   - 如果是原生 `EventSource`，需要改用 `@microsoft/fetch-event-source`

2. **修改连接配置**
   ```typescript
   // sse.ts 中
   const eventSource = new FetchEventSource('/api/chat/stream', {
     openWhenHidden: true,  // 添加此参数
     ...
   });
   ```

3. **测试验证**
   - 桌面端：隐藏标签页，验证SSE是否保持
   - 移动端：确认行为（预期会断开）

### 5.2 方案4实现步骤（后做，主要方案）

使用IndexedDB实时存储，每个chunk到达时保存。

1. **安装idb库**
   ```bash
   pnpm add idb
   ```

2. **创建IndexedDB工具**
   ```typescript
   // utils/indexedDB.ts
   import { openDB, DBSchema } from 'idb';
   
   interface ChatCacheDB extends DBSchema {
     messages: {
       key: string;
       value: {
         sessionId: string;
         messages: any[];
         executionSteps: any[];
         timestamp: number;
       };
     };
   }
   
   const dbPromise = openDB<ChatCacheDB>('chat-cache', 1, {
     upgrade(db) {
       db.createObjectStore('messages', { keyPath: 'sessionId' });
     },
   });
   
   export const saveToIndexedDB = async (sessionId: string, messages: any[], executionSteps: any[]) => {
     const db = await dbPromise;
     await db.put('messages', {
       sessionId,
       messages,
       executionSteps,
       timestamp: Date.now(),
     });
   };
   
   export const loadFromIndexedDB = async (sessionId: string) => {
     const db = await dbPromise;
     return db.get('messages', sessionId);
   };
   
   export const clearFromIndexedDB = async (sessionId: string) => {
     const db = await dbPromise;
     await db.delete('messages', sessionId);
   };
   ```

3. **在SSE回调中实时保存**
   ```typescript
   // sse.ts 或 NewChatContainer.tsx
   import { saveToIndexedDB, loadFromIndexedDB } from '@/utils/indexedDB';
   
   // 每个chunk到达时保存
   const onChunk = (chunk) => {
     // 更新内存
     finalResponseRef.current += chunk.content;
     executionStepsRef.current.push(chunk);
     
     // 实时保存到IndexedDB
     saveToIndexedDB(sessionId, messagesRef.current, executionStepsRef.current);
   };
   ```

4. **页面加载时恢复**
   ```typescript
   // NewChatContainer.tsx
   useEffect(() => {
     const cached = await loadFromIndexedDB(sessionId);
     if (cached) {
       setMessages(cached.messages);
       setExecutionSteps(cached.executionSteps);
     }
   }, [sessionId]);
   ```

5. **AI回复完成时清理**
   ```typescript
   // onComplete 中
   const onComplete = async () => {
     // 保存到后端数据库
     await sessionApi.saveMessage(...);
     
     // 清理IndexedDB
     await clearFromIndexedDB(sessionId);
   };
   ```

---

## 六、待确认问题

1. 当前SSE使用的是什么库？（原生EventSource还是其他）
2. 方案4实现复杂度可以接受吗？
3. 项目是否以桌面端为主？（移动端无法完美支持）

---

## 七、方案1和方案3的详细分析（追加说明）

### 7.1 方案1（页面隐藏时保存到数据库）为什么不推荐

#### 7.1.1 方案1的原理解释

方案1的核心思路是：在页面隐藏时（visibilitychange事件），主动调用保存接口，将当前已接收的内容保存到数据库，并标记为 `status: incomplete`。下次页面恢复或刷新时，从数据库加载这些未完成的消息。

#### 7.1.2 方案1的问题

| 问题 | 详细说明 |
|------|---------|
| **需要后端配合** | 需要修改数据库表结构，添加status字段；需要修改saveMessage API |
| **实现成本不低** | 前后端都需要改，反而比方案4（纯前端）更复杂 |
| **数据覆盖风险** | 如果在保存的瞬间用户刚好切换回来，可能导致数据覆盖 |
| **不完整数据** | 只能保存最后一次保存时的状态，期间新接收的数据会丢失 |

#### 7.1.3 方案1vs方案4对比

| 对比项 | 方案1 | 方案4 |
|--------|-------|-------|
| 后端配合 | 需要 | 不需要 |
| 数据完整性 | 保存时的快照 | 每个chunk实时保存 |
| 实现复杂度 | 低（但需改后端） | 中（纯前端） |
| 崩溃丢失 | 最后一次保存的数据 | 几乎不丢失 |

#### 7.1.4 结论

**方案1不推荐的原因**：虽然看起来简单，但需要后端配合修改，实现成本反而比方案4高，而且数据完整性不如方案4。

---

### 7.2 方案3（Service Worker接管SSE）为什么不用

#### 7.2.1 方案3的原理解释

方案3的核心思路是：使用Service Worker作为中间层，让Service Worker保持与后端的SSE连接，页面与Service Worker通过MessageChannel通信。即使页面关闭，Service Worker仍然可以接收后端推送的数据。

#### 7.2.2 方案3的技术限制

| 限制 | 详细说明 |
|------|---------|
| **Service Worker会被终止** | 浏览器会在30秒无活动后自动终止Service Worker |
| **SSE无法保持** | SSE连接需要持续的网络连接，Service Worker被终止后连接会断开 |
| **实现复杂** | 需要处理心跳保活、连接重建、消息同步等复杂逻辑 |
| **刷新无效** | 刷新页面时Service Worker会重新初始化，之前的连接也会丢失 |

#### 7.2.3 实际效果

即使实现了复杂的保活机制，实际效果也只能做到：
- 延长Service Worker存活时间（从30秒延长到几分钟）
- 但无法完全保持SSE连接
- 刷新页面仍然会断开
- 实现收益比太低

#### 7.2.4 结论

**方案3不用的原因**：技术限制导致无法实现预期效果，实现复杂度高但收益低，不如直接使用方案2+4的组合。

---

## 八、最终推荐

**最佳组合：方案2 + 方案4**

- 方案2：保持SSE连接（处理桌面端页面切换）
- 方案4：IndexedDB实时存储（处理刷新页面、浏览器崩溃）

**备选方案：方案2 + 方案5**

- 如果方案4实现复杂，可以用方案5作为简化版

---

## 九、增强方案分析（小沈方案）

### 9.1 方案背景

小新的推荐方案（方案2+方案4）是非常好的组合，但在实施前，需要分析以下问题：

| 问题 | 说明 |
|------|------|
| 方案2 | 需要将现有SSE库从原生fetch改为@microsoft/fetch-event-source，有一定改造成本 |
| 方案4 | 需要引入idb依赖，增加项目依赖复杂度 |
| 现有saveExecutionSteps | 后端已有saveExecutionSteps API，可以直接复用，不需要额外开发 |

### 9.2 增强方案：方案1简化版（利用现有API）

#### 9.2.1 核心思路

不修改现有SSE库，不引入新依赖，而是利用现有的API实现数据保存：

- **saveExecutionSteps API**：后端已有，可以直接更新消息的execution_steps
- **saveMessage API**：可以保存消息内容

#### 9.2.2 技术实现

```typescript
// NewChatContainer.tsx - visibilitychange处理增强

// 页面隐藏时
if (document.hidden && isReceiving) {
  const currentSessionId = currentSessionIdRef.current || sessionId;
  
  // 1. 保存当前已接收的内容到数据库（增强部分）
  if (currentSessionId && responseBufferRef.current) {
    try {
      // 更新最后一条消息的content
      await sessionApi.saveMessage(currentSessionId, {
        role: "assistant",
        content: responseBufferRef.current,
      });
      
      // 保存execution_steps（利用现有API）
      if (executionStepsRef.current.length > 0) {
        await sessionApi.saveExecutionSteps(
          currentSessionId, 
          executionStepsRef.current
        );
      }
      
      console.log("💾 页面隐藏前保存数据成功");
    } catch (error) {
      console.error("💾 保存数据失败:", error);
    }
  }
  
  // 2. 现有逻辑：保存到sessionStorage
  saveState();
  
  // 3. 现有逻辑：断开SSE
  disconnect();
}
```

#### 9.2.3 优点

| 优点 | 说明 |
|------|------|
| ✅ 不破坏现有功能 | 现有saveMessage逻辑完全不变 |
| ✅ 兼容现有功能 | 利用已有API，不需要后端配合 |
| ✅ 实现简单 | 只需要在前端visibilitychange中添加保存逻辑 |
| ✅ 无新依赖 | 不需要引入idb库，不需要换SSE库 |
| ✅ 增强而非替换 | 是保险机制，不影响正常流程 |

#### 9.2.4 缺点

| 缺点 | 说明 |
|------|------|
| ❌ 数据完整性一般 | 只能保存页面隐藏时的快照，隐藏期间的数据会丢失 |
| ❌ 仍需要方案2 | 页面切换时需要保持SSE连接才能完整接收 |
| ❌ 仍需要方案4 | 浏览器崩溃场景无法处理 |

### 9.3 方案对比（增强版）

| 对比项 | 方案2+4（小新） | 方案1简化版（增强） | 组合方案 |
|--------|-----------------|-------------------|---------|
| 页面切换(桌面) | ✅ | ✅ | ✅ |
| 刷新页面 | ✅ | ✅ | ✅ |
| 浏览器崩溃 | ✅ | ❌ | ✅ |
| 移动端后台 | ⚠️ | ⚠️ | ⚠️ |
| 实现复杂度 | 中 | 低 | 中 |
| 后端配合 | 不需要 | 不需要 | 不需要 |
| 新依赖 | idb库 | 无 | 可选 |
| SSE库改动 | 需要 | 不需要 | 可选 |

### 9.4 推荐最终组合方案

**最佳方案：方案2 + 方案1简化版 + 方案5（兜底）**

#### 职责分工

| 阶段 | 方案 | 动作 | 说明 |
|------|------|------|------|
| 页面隐藏 | **方案2** | 保持SSE连接 | 后台继续接收数据 |
| 页面隐藏 | **方案1简化版** | 保存当前数据到DB | 利用现有API作为保险 |
| 页面卸载 | **方案5** | sendBeacon兜底 | 最后一道防线 |
| 页面恢复 | **现有逻辑** | 从API加载 | 保持不变 |

#### 流程图

```
用户切换/离开页面
      ↓
┌─────────────────────────────────────────┐
│  方案2: 保持SSE连接（后台接收数据）       │
│  方案1简化版: 保存当前数据到DB（保险）     │
│  方案5: sendBeacon兜底（最后防线）        │
└─────────────────────────────────────────┘
      ↓
页面恢复 → 从API加载 → 显示完整内容
```

#### 实施优先级

| 优先级 | 方案 | 理由 |
|--------|------|------|
| 1️⃣ | **方案1简化版** | 改动最小，立即可用，利用现有API |
| 2️⃣ | **方案2** | 解决页面切换数据丢失的核心问题 |
| 3️⃣ | **方案5** | 兜底方案，作为最后一道防线 |
| 4️⃣ | **方案4** | 可选，实现复杂度较高 |

### 9.5 方案1简化版实施步骤

#### 步骤1：检查现有API

确认前端已有以下API可用：
- `sessionApi.saveMessage` - 保存消息
- `sessionApi.saveExecutionSteps` - 更新execution_steps

#### 步骤2：修改visibilitychange处理

在NewChatContainer.tsx的visibilitychange处理中添加保存逻辑：

```typescript
const handleVisibilityChange = () => {
  if (document.hidden) {
    // 【增强】页面隐藏时保存当前流式数据
    if (isReceiving && currentSessionIdRef.current) {
      saveIncompleteData();
    }
    
    // 现有逻辑
    saveState();
    if (isReceiving) {
      disconnect();
    }
  } else {
    // 现有逻辑
    // ...
  }
};
```

#### 步骤3：实现saveIncompleteData函数

```typescript
const saveIncompleteData = async () => {
  const currentSessionId = currentSessionIdRef.current || sessionId;
  if (!currentSessionId || !responseBufferRef.current) return;
  
  try {
    // 保存当前已接收的内容
    await sessionApi.saveMessage(currentSessionId, {
      role: "assistant",
      content: responseBufferRef.current,
    });
    
    // 保存execution_steps
    if (executionStepsRef.current.length > 0) {
      await sessionApi.saveExecutionSteps(
        currentSessionId, 
        executionStepsRef.current
      );
    }
    
    console.log("💾 未完成数据已保存");
  } catch (error) {
    console.error("💾 保存失败:", error);
  }
};
```

#### 步骤4：测试验证

- 测试页面隐藏时数据是否正确保存
- 测试从历史会话进入时数据是否完整加载

---

## 十、方案选择建议

### 10.1 快速上线（改动最小）

**方案1简化版 + 方案2**

- 优点：改动小，利用现有API，不需要新依赖
- 缺点：浏览器崩溃场景无法处理

### 10.2 最佳完整性（推荐）

**方案2 + 方案4**

- 优点：覆盖所有场景，数据完整性最高
- 缺点：需要引入idb依赖，实现复杂度中等

### 10.3 平衡方案（折中）

**方案2 + 方案1简化版 + 方案5**

- 优点：改动适中，多重保险
- 缺点：需要维护多个保存逻辑

---

**更新时间**: 2026-03-16 22:50:00
**版本**: v1.2
**更新人**: 小沈
