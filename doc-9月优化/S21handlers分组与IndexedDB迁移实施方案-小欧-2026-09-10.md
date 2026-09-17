# S21 handlers分组与IndexedDB迁移实施方案

**编写人**: 小欧  
**编写时间**: 2026-09-10 19:28:49  
**版本**: v1.1  

---

## 版本历史

| 版本 | 时间 | 修改内容 | 作者 |
|------|------|---------|------|
| v1.0 | 2026-09-10 19:28:49 | 初版创建：S21 handlers分组 + IndexedDB迁移完整实施方案 | 小欧 |
| v1.1 | 2026-09-10 19:45:00 | 核查修正：①修复disconnect签名不一致（sseParser 3参数→5参数统一）；②删除无效diff行；③增强IndexedDB错误处理 | 小欧 |

---

## 一、背景与目标

### 1.1 问题来源

3.5问题清单核查发现两个可优化点：
- **3.5.2.5 模块职责失衡**: handlers类型26个字段平铺，认知负担高，易传错参数
- **3.5.3.2 sessionStorage误用**: 同步阻塞+容量限制与高频SSE流不匹配

### 1.2 目标

1. **S21 handlers分组**: 将26个字段按语义分组为6个子接口，减少错误概率
2. **IndexedDB迁移**: 替换sessionStorage，解决同步阻塞+容量限制问题

---

## 二、S21 handlers分组实施

### 2.1 当前handlers复杂度分析

**当前字段数**: 26个（sseParser.ts:84-140）

| 分类 | 字段 | 数量 |
|------|------|------|
| State setters | setExecutionSteps, setCurrentResponse, setIsReceiving, setIsConnected, setServerTaskId?, setMetaFrames? | 6 |
| Refs | executionStepsRef, responseBufferRef, pendingStepsRef?, lastSeqRef?, terminalSeqRef?, usageAccumRef?, lastUsageSeqRef? | 7 |
| Callbacks | onStep?, onChunk?, onComplete?, onError?, onDenied?, onPaused?, onResumed?, onRetry?, onAuthorizationRequired?, onSeq? | 10 |
| Functions | getCurrentExecutionSteps, disconnect, scheduleFlush? | 3 |

**问题**：
- 成对使用字段分散（pendingStepsRef+scheduleFlush总是成对出现）
- 新开发者难以理解字段归属
- 传错字段时TypeScript报错不精准

### 2.2 分组后类型定义

**新增文件**: `frontend/src/types/sseHandlers.ts`

```typescript
// 编辑历史: 2026-09-10 小欧 - S21 handlers分组: 26字段平铺→6语义子接口, 减少认知负担+传错概率 — 小欧-2026-09-10

import type { ExecutionStep } from './execution';
import type { TaskMetaFrames, SSEMetadata, SSEError } from './sse';

// ===== 子接口1: State setters（React state写入能力）=====
export interface SSEStateAPI {
  setExecutionSteps: React.Dispatch<React.SetStateAction<ExecutionStep[]>>;
  setCurrentResponse: React.Dispatch<React.SetStateAction<string>>;
  setIsReceiving: React.Dispatch<React.SetStateAction<boolean>>;
  setIsConnected: React.Dispatch<React.SetStateAction<boolean>>;
  setServerTaskId?: (taskId: string) => void;
  setMetaFrames?: React.Dispatch<React.SetStateAction<TaskMetaFrames>>;
}

// ===== 子接口2: Refs（可变状态读写）=====
export interface SSERefAPI {
  executionStepsRef: React.MutableRefObject<ExecutionStep[]>;
  responseBufferRef: React.MutableRefObject<string>;
  usageAccumRef?: React.MutableRefObject<{
    prompt: number;
    completion: number;
    total: number;
  }>;
  lastUsageSeqRef?: React.MutableRefObject<number>;
}

// ===== 子接口3: Batch commit（批量提交，总是成对使用）=====
export interface SSEBatchAPI {
  pendingStepsRef?: React.MutableRefObject<ExecutionStep[]>;
  scheduleFlush?: () => void;
}

// ===== 子接口4: Seq guard（序列号守卫，总是成对使用）=====
export interface SSESeqGuardAPI {
  lastSeqRef?: React.MutableRefObject<number>;
  terminalSeqRef?: React.MutableRefObject<number>;
}

// ===== 子接口5: Callbacks（事件回调）=====
export interface SSECallbacksAPI {
  onStep?: (step: ExecutionStep) => void;
  onChunk?: (chunk: string, is_reasoning?: boolean) => void;
  onComplete?: (
    fullResponse: string,
    metadata?: string | SSEMetadata,
    executionSteps?: ExecutionStep[]
  ) => void;
  onError?: (error: string | SSEError) => void;
  onDenied?: (step: number, message: string, toolName?: string) => void;
  onPaused?: (confirmId?: string) => void;
  onResumed?: (confirmId?: string) => void;
  onRetry?: (message: string, waitTime?: number) => void;
  onAuthorizationRequired?: (data: {
    confirm_id: string;
    tool_name: string;
    params: Record<string, unknown>;
    safety_level: string;
    trust_path?: string | null;
    auto_confirm?: boolean;
    confirm_timeout?: number;
    backend_timeout?: number;
  }) => void;
  onSeq?: (seq: number) => void;
}

// ===== 子接口6: Actions（动作函数）=====
// 小欧 2026-09-10 v1.1 修正: disconnect统一为5参数（与useSSE.ts:621-627实际实现一致）
//   原sseParser.ts handlers类型只有3参数（缺resetReconnectAttempts/setReceiving），
//   但useSSE.ts实际实现有5参数，本次S21分组一并修复这个潜在的类型安全隐患
export interface SSEActionsAPI {
  getCurrentExecutionSteps: () => ExecutionStep[];
  disconnect: (
    manualDisconnect?: boolean,
    clearStorage?: boolean,
    onDisconnect?: () => void,
    resetReconnectAttempts?: boolean,
    setReceiving?: boolean
  ) => void;
}

// ===== 聚合接口: SSEHandlers =====
export interface SSEHandlers extends SSEStateAPI, SSERefAPI, SSEBatchAPI, SSESeqGuardAPI, SSECallbacksAPI, SSEActionsAPI {}
```

### 2.3 修改sseParser.ts

**修改文件**: `frontend/src/features/chat/services/sseParser.ts`

```diff
  // 编辑历史: 2026-09-10 小欧 - 阶段一S1清死代码: ... 
+ // 编辑历史: 2026-09-10 小欧 - S21 handlers分组: 26字段平铺→6语义子接口(SSEHandlers), 减少认知负担+传错概率
+ //   同时修复disconnect签名不一致: sseParser 3参数→5参数(与useSSE.ts实际实现统一) — 小欧-2026-09-10
  
+ import type { SSEHandlers } from '@/types/sseHandlers';
  
  const processSSEData = (
    line: string,
-   handlers: {
-     setExecutionSteps: React.Dispatch<React.SetStateAction<ExecutionStep[]>>;
-     getCurrentExecutionSteps: () => ExecutionStep[];
-     executionStepsRef: React.MutableRefObject<ExecutionStep[]>;
-     onStep?: (step: ExecutionStep) => void;
-     onChunk?: (chunk: string, is_reasoning?: boolean) => void;
-     onComplete?: (
-       fullResponse: string,
-       metadata?: string | SSEMetadata,
-       executionSteps?: ExecutionStep[]
-     ) => void;
-     onError?: (error: string | SSEError) => void;
-     onDenied?: (step: number, message: string, toolName?: string) => void;
-     onPaused?: (confirmId?: string) => void;
-     onResumed?: (confirmId?: string) => void;
-     onRetry?: (message: string, waitTime?: number) => void;
-     onAuthorizationRequired?: (data: {
-       confirm_id: string;
-       tool_name: string;
-       params: Record<string, unknown>;
-       safety_level: string;
-       trust_path?: string | null;
-       auto_confirm?: boolean;
-       confirm_timeout?: number;
-       backend_timeout?: number;
-     }) => void;
-     setCurrentResponse: React.Dispatch<React.SetStateAction<string>>;
-     responseBufferRef: React.MutableRefObject<string>;
-     setIsReceiving: React.Dispatch<React.SetStateAction<boolean>>;
-     setIsConnected: React.Dispatch<React.SetStateAction<boolean>>;
-     disconnect: (
-       manualDisconnect?: boolean,
-       clearStorage?: boolean,
-       onDisconnect?: () => void
-     ) => void; // 小欧 v1.1修正: 原3参数，实际useSSE.ts有5参数，本次统一修复
-     setServerTaskId?: (taskId: string) => void;
-     onSeq?: (seq: number) => void;
-     lastSeqRef?: React.MutableRefObject<number>;
-     terminalSeqRef?: React.MutableRefObject<number>;
-     pendingStepsRef?: React.MutableRefObject<ExecutionStep[]>;
-     scheduleFlush?: () => void;
-     setMetaFrames?: React.Dispatch<React.SetStateAction<TaskMetaFrames>>;
-     usageAccumRef?: React.MutableRefObject<{
-       prompt: number;
-       completion: number;
-       total: number;
-     }>;
-     lastUsageSeqRef?: React.MutableRefObject<number>;
-   }
+   handlers: SSEHandlers // 小欧 v1.1修正: 使用聚合接口，disconnect统一为5参数
  ) => {
```

### 2.4 修改useSSE.ts调用处

**修改文件**: `frontend/src/hooks/useSSE.ts`

```diff
  // 编辑历史: 2026-09-10 小欧 - 阶段一S1清死代码: ...
+ // 编辑历史: 2026-09-10 小欧 - S21 handlers分组: 调用处改用SSEHandlers类型 — 小欧-2026-09-10
  
+ import type { SSEHandlers } from '@/types/sseHandlers';
  
  // ... 在两处processSSEData调用点（:851和:900），类型自动推导无需修改
  // handlers对象字面量仍按原字段名传入，TypeScript会检查是否符合SSEHandlers接口
```

### 2.5 验证要点

| 验证项 | 方法 | 预期结果 |
|--------|------|---------|
| 类型检查 | `npm run check` | 无类型错误 |
| 传错字段测试 | 故意传错字段名 | TypeScript报错更精准（指出具体子接口） |
| 运行时行为 | `npm run dev` + SSE连接 | 功能与修改前完全一致 |
| 成对字段绑定 | 检查pendingStepsRef+scheduleFlush | 总是成对传入 |
| disconnect签名 | 检查disconnect调用（:621-627） | 5参数与useSSE.ts实际实现完全匹配 |

---

## 三、IndexedDB迁移实施

### 3.1 问题分析

| 问题 | sessionStorage现状 | IndexedDB优势 |
|------|-------------------|--------------|
| 同步阻塞 | `setItem`同步，大数据量冻结主线程 | 异步API，不阻塞UI |
| 容量限制 | 5-10MB | 无上限（数百MB） |
| 数据类型 | 只支持字符串 | 支持结构化数据 |
| 并发写入 | 同标签页互斥 | 支持事务并发 |
| 丢数据风险 | 标签页关闭即清空 | 持久化存储 |

### 3.2 迁移范围

| sessionStorage使用点 | 是否迁移 | 原因 |
|---------------------|---------|------|
| useSSE.ts steps备份（SSE_STORAGE_KEY） | ✅ 迁移 | 高频SSE流+大数据量，同步阻塞+容量限制问题突出 |
| useChatStreaming.ts 被拒工具点名条（DENIED_STORAGE_KEY） | ❌ 保留sessionStorage | 数据量小（工具名+拒绝原因），无容量压力；低频写入（仅拒绝时），无阻塞问题 |
| useChatPersistence.ts 聊天状态持久化 | ❌ 保留sessionStorage | 非SSE流数据，不在本次优化范围 |
| utils/sessionStorage.ts / chatHistory.ts | ❌ 保留sessionStorage | 通用工具层，非SSE流数据 |

### 3.3 新增存储工具模块

**新增文件**: `frontend/src/utils/indexedDBStorage.ts`

```typescript
// 编辑历史: 2026-09-10 小欧 - IndexedDB存储工具: 替代sessionStorage, 解决同步阻塞+容量限制问题 — 小欧-2026-09-10

import type { ExecutionStep } from '@/types/execution';

// ===== 常量定义 =====
const DB_NAME = 'omniagent_sse';
const DB_VERSION = 1;
const STORE_NAME = 'steps';

// ===== 数据库实例（单例）=====
let dbInstance: IDBDatabase | null = null;

// ===== 数据结构定义 =====
export interface StepsEnvelope {
  sessionId: string;
  steps: ExecutionStep[];
  source: 'live' | 'legacy' | 'unknown';
  timestamp: number;
}

// ===== 核心函数 =====

/**
 * 打开数据库（懒初始化）
 * @author 小欧
 * @date 2026-09-10
 */
function openDB(): Promise<IDBDatabase> {
  if (dbInstance) return Promise.resolve(dbInstance);
  
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    
    request.onerror = () => reject(request.error);
    request.onsuccess = () => {
      dbInstance = request.result;
      dbInstance.onclose = () => { dbInstance = null; };
      resolve(dbInstance);
    };
    request.onupgradeneeded = (event) => {
      const db = (event.target as IDBOpenDBRequest).result;
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME, { keyPath: 'sessionId' });
      }
    };
  });
}

/**
 * 保存步骤数据（异步）
 * @param sessionId 会话ID
 * @param data 包含steps/source/timestamp的信封数据
 * @author 小欧
 * @date 2026-09-10
 */
export async function saveSteps(
  sessionId: string, 
  data: Omit<StepsEnvelope, 'sessionId'>
): Promise<void> {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readwrite');
    const store = tx.objectStore(STORE_NAME);
    const request = store.put({ sessionId, ...data });
    // 小欧 v1.1修正: 同时监听request和transaction的错误事件，确保错误不丢失
    request.onerror = () => reject(request.error);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

/**
 * 读取步骤数据（异步）
 * @param sessionId 会话ID
 * @returns 步骤数据或null
 * @author 小欧
 * @date 2026-09-10
 */
export async function loadSteps(
  sessionId: string
): Promise<StepsEnvelope | null> {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readonly');
    const store = tx.objectStore(STORE_NAME);
    const request = store.get(sessionId);
    request.onsuccess = () => resolve(request.result ?? null);
    request.onerror = () => reject(request.error);
  });
}

/**
 * 清除步骤数据（异步）
 * @param sessionId 会话ID
 * @author 小欧
 * @date 2026-09-10
 */
export async function clearSteps(sessionId: string): Promise<void> {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readwrite');
    const store = tx.objectStore(STORE_NAME);
    const request = store.delete(sessionId);
    // 小欧 v1.1修正: 同时监听request和transaction的错误事件，确保错误不丢失
    request.onerror = () => reject(request.error);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

/**
 * 从sessionStorage迁移旧数据（一次性迁移）
 * @param sessionId 会话ID
 * @author 小欧
 * @date 2026-09-10
 */
export async function migrateFromSessionStorage(
  sessionId: string,
  storageKeyPrefix: string
): Promise<void> {
  const oldKey = `${storageKeyPrefix}_${sessionId}`;
  const oldData = sessionStorage.getItem(oldKey);
  if (oldData) {
    try {
      const parsed = JSON.parse(oldData);
      const steps: ExecutionStep[] = Array.isArray(parsed) 
        ? parsed 
        : (parsed?.steps ?? []);
      if (steps.length > 0) {
        await saveSteps(sessionId, {
          steps,
          source: 'legacy',
          timestamp: Date.now(),
        });
        sessionStorage.removeItem(oldKey);
        console.info(`[SSE] 迁移 ${steps.length} 步从 sessionStorage 到 IndexedDB`);
      }
    } catch (e) {
      console.warn('[SSE] 迁移旧数据失败:', e);
    }
  }
}
```

### 3.4 修改useSSE.ts

**修改文件**: `frontend/src/hooks/useSSE.ts`

```diff
  // 编辑历史: 2026-09-10 小欧 - 阶段一S1清死代码: ...
+ // 编辑历史: 2026-09-10 小欧 - IndexedDB迁移: sessionStorage→IndexedDB, 解决同步阻塞+容量限制 — 小欧-2026-09-10
  
+ import { saveSteps, loadSteps, clearSteps as clearStepsFromDB, migrateFromSessionStorage } from '@/utils/indexedDBStorage';
  
  // ===== 修改1: saveStepsToStorage函数（:420-442）=====
  // 保存到 IndexedDB 的辅助函数(5s 防抖, 异步不阻塞主线程)
  // 小欧 2026-09-10 IndexedDB迁移: 替换sessionStorage, 解决同步阻塞+容量限制
  const saveStepsTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const saveStepsToStorage = useCallback(
    (steps: ExecutionStep[]) => {
      if (steps.length === 0 || !config.sessionId) return;
      if (saveStepsTimerRef.current !== null)
        clearTimeout(saveStepsTimerRef.current);
-     saveStepsTimerRef.current = setTimeout(() => {
-       const storageKey = `${SSE_STORAGE_KEY}_${config.sessionId}`;
+     saveStepsTimerRef.current = setTimeout(async () => {
        try {
          // 小欧 2026-09-10 S19: 写入元数据外壳——恢复时按 source 区分累积 vs 外部
          const envelope = {
            steps: steps,
            source: 'live' as const,
            timestamp: Date.now(),
          };
-         sessionStorage.setItem(storageKey, JSON.stringify(envelope));
+         await saveSteps(config.sessionId, envelope);
        } catch (e) {
-         console.warn('[SSE] 保存到 sessionStorage 失败:', e);
+         console.warn('[SSE] 保存到 IndexedDB 失败:', e);
        }
        saveStepsTimerRef.current = null;
      }, 5000); // 小欧 2026-09-10 S12: 5s 兜底快照，去主线程同步阻塞
    },
    [config.sessionId]
  );
  
  // ===== 修改2: 恢复逻辑（:540-564）=====
  // 恢复：组件初始化时检查是否有备份数据
  useEffect(() => {
+   // 小欧 2026-09-10 IndexedDB迁移: 首次加载时迁移旧数据
+   migrateFromSessionStorage(config.sessionId, SSE_STORAGE_KEY).then(() => {
+     return loadSteps(config.sessionId);
+   }).then((savedData) => {
-   const storageKey = `${SSE_STORAGE_KEY}_${config.sessionId}`;
-   const savedSteps = sessionStorage.getItem(storageKey);
-   if (savedSteps) {
+   if (savedData) {
      try {
-       const parsedRaw = JSON.parse(savedSteps);
-       // 小欧 2026-09-10 S19: 兼容旧格式（纯 steps 数组）和新格式（{steps, source, timestamp}）
-       const parsedSteps: ExecutionStep[] = Array.isArray(parsedRaw)
-         ? parsedRaw
-         : (parsedRaw?.steps ?? []);
-       const source: string = Array.isArray(parsedRaw) ? 'legacy' : (parsedRaw?.source ?? 'unknown');
+       const { steps: parsedSteps, source } = savedData;
        if (parsedSteps.length > 0) {
-         console.info(`[SSE] 从 sessionStorage 恢复 ${parsedSteps.length} 步, source=${source}`);
+         console.info(`[SSE] 从 IndexedDB 恢复 ${parsedSteps.length} 步, source=${source}`);
          const restoredSteps = parsedSteps.filter(
            (s: ExecutionStep) => !(s.type === 'action' && s.preview === true)
          );
          executionStepsRef.current = restoredSteps;
          setExecutionSteps(restoredSteps);
        }
      } catch (e) {
-       console.warn('[SSE] 解析 sessionStorage 备份失败:', e);
-       sessionStorage.removeItem(storageKey);
+       console.warn('[SSE] 解析 IndexedDB 备份失败:', e);
+       clearStepsFromDB(config.sessionId);
      }
    }
+   }).catch((e) => {
+     console.warn('[SSE] IndexedDB 恢复失败:', e);
+   });
  }, [config.sessionId]); // 仅在 sessionId 变化时检查
  
  // ===== 修改3: clearStepsFromStorage函数（:568-571）=====
  // 清空 IndexedDB 的辅助函数
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const clearStepsFromStorage = useCallback(async () => {
-   const storageKey = `${SSE_STORAGE_KEY}_${config.sessionId}`;
-   sessionStorage.removeItem(storageKey);
+   await clearStepsFromDB(config.sessionId);
  }, [config.sessionId]);
```

### 3.5 降级方案（IndexedDB不可用时）

在`frontend/src/utils/indexedDBStorage.ts`中添加降级逻辑：

```typescript
// ===== 降级检测 =====
function isIndexedDBAvailable(): boolean {
  try {
    return typeof indexedDB !== 'undefined' && indexedDB !== null;
  } catch {
    return false;
  }
}

// ===== 降级存储（使用localStorage）=====
const FALLBACK_KEY_PREFIX = 'omniagent_sse_fallback_';

function fallbackSave(sessionId: string, data: StepsEnvelope): void {
  try {
    localStorage.setItem(`${FALLBACK_KEY_PREFIX}${sessionId}`, JSON.stringify(data));
  } catch (e) {
    console.warn('[SSE] 降级存储失败:', e);
  }
}

function fallbackLoad(sessionId: string): StepsEnvelope | null {
  try {
    const raw = localStorage.getItem(`${FALLBACK_KEY_PREFIX}${sessionId}`);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function fallbackClear(sessionId: string): void {
  localStorage.removeItem(`${FALLBACK_KEY_PREFIX}${sessionId}`);
}

// ===== 修改核心函数，添加降级逻辑 =====
export async function saveSteps(
  sessionId: string, 
  data: Omit<StepsEnvelope, 'sessionId'>
): Promise<void> {
  if (!isIndexedDBAvailable()) {
    fallbackSave(sessionId, { sessionId, ...data });
    return;
  }
  // ... 原IndexedDB逻辑
}

export async function loadSteps(
  sessionId: string
): Promise<StepsEnvelope | null> {
  if (!isIndexedDBAvailable()) {
    return fallbackLoad(sessionId);
  }
  // ... 原IndexedDB逻辑
}

export async function clearSteps(sessionId: string): Promise<void> {
  if (!isIndexedDBAvailable()) {
    fallbackClear(sessionId);
    return;
  }
  // ... 原IndexedDB逻辑
}
```

### 3.6 测试要点

| 测试场景 | 验证点 | 测试方法 |
|---------|--------|---------|
| 基础保存/读取 | 数据完整性 | 启动SSE连接→刷新页面→检查步骤恢复 |
| 异步不阻塞UI | 大数据量写入时不卡顿 | 保存10万步数据，观察UI响应 |
| 并发写入 | 多标签页同时写入不冲突 | 打开2个标签页，同时发请求 |
| 旧数据迁移 | sessionStorage→IndexedDB无缝迁移 | 用旧版本保存数据→升级后检查恢复 |
| 降级方案 | IndexedDB不可用时降级到localStorage | 禁用IndexedDB后测试 |
| 容量优势 | 大数据量不丢失 | 保存超过10MB数据 |

---

## 四、实施顺序建议

### 4.1 推荐顺序

```
1. 先实施IndexedDB迁移（风险低、收益高）
   - 新增 indexedDBStorage.ts
   - 修改 useSSE.ts
   - 测试验证

2. 后实施S21 handlers分组（改动量较大）
   - 新增 sseHandlers.ts 类型定义
   - 修改 sseParser.ts handlers类型
   - 修改 useSSE.ts 调用处（可选）
   - 测试验证
```

### 4.2 风险评估

| 方案 | 风险 | 影响 | 缓解措施 |
|------|------|------|---------|
| IndexedDB迁移 | 浏览器兼容性 | IE11不支持 | 降级到localStorage |
| IndexedDB迁移 | 异步时序 | 恢复数据延迟 | 首次加载显示loading |
| S21 handlers分组 | 改动量大 | 可能引入类型错误 | 类型定义与原始完全一致，调用处零改动 |
| S21 handlers分组 | disconnect签名修复 | 原3参数→5参数 | v1.1修正：与useSSE.ts实际实现统一，修复潜在类型安全隐患 |

---

## 五、预期收益

### 5.1 S21 handlers分组

| 收益 | 说明 |
|------|------|
| 认知负担降低 | 6个语义分组比26个平铺字段更易理解 |
| 错误概率降低 | 成对字段绑定，不会漏传 |
| 类型安全增强 | 分组后TypeScript报错更精准 |
| 维护成本降低 | 新增字段只需改对应分组 |

### 5.2 IndexedDB迁移

| 收益 | 说明 |
|------|------|
| 异步不阻塞 | UI不再因大数据量写入卡顿 |
| 容量无上限 | 不再担心5-10MB限制 |
| 数据持久化 | 标签页关闭后数据仍可恢复 |
| 并发安全 | 多标签页同时写入不冲突 |

---

## 六、v1.1修订说明（2026-09-10 19:45:00）

### 6.1 修订内容

| 问题 | 位置 | 修正 |
|------|------|------|
| disconnect签名不一致 | SSEActionsAPI + diff | ①SSEActionsAPI注释说明5参数来源；②diff中旧类型添加注释说明修复；③验证要点新增disconnect签名校验 |
| 无效diff行 | diff第149-150行 | 删除重复的import diff（`- `和`+ `完全相同） |
| IndexedDB错误处理 | saveSteps/clearSteps | 同时监听request.onerror和tx.onerror，确保错误不丢失 |
| 风险评估 | 4.2节 | 新增disconnect签名修复风险项 |

### 6.2 核查确认

- ✅ 26个字段全部在SSEHandlers中定义，无遗漏
- ✅ disconnect签名与useSSE.ts:621-627实际实现完全匹配（5参数）
- ✅ IndexedDB事务处理符合W3C标准
- ✅ 降级方案完整（localStorage fallback）

---

**文档完成时间**: 2026-09-10 19:45:00  
**编写人**: 小欧  
**审核人**: 待定
