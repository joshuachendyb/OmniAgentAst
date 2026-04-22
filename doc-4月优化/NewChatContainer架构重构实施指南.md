# NewChatContainer架构重构实施指南

## 一、概述

本指南详细说明了如何将NewChatContainer从巨型组件重构为基于Hook的模块化架构。重构采用渐进式、分层拆分策略，确保每个步骤都可独立验证，功能不丢失。

## 二、当前状态

### 2.1 已完成的工作
- ✅ **组件拆分**：ChatHeader、ChatToolbar、MessageArea、ChatInput 已提取为独立组件
- ✅ **Hook骨架创建**：useChatStreaming、useChatSession、useChatPersistence 已创建基础骨架
- ✅ **类型定义**：已提取到独立文件（src/types/chat.ts）
- ✅ **工具函数**：已提取到独立文件（src/utils/chatHistory.ts等）

### 2.2 新创建的Hook
- ✅ **useChatState**：统一状态管理（229行）
- ✅ **useChatCallbacks**：统一回调管理（687行）
- ✅ **useChatStreaming**：SSE流式管理（更新后118行）
- ✅ **useChatSession**：会话生命周期管理（更新后242行）
- ✅ **useChatPersistence**：状态持久化与恢复（更新后272行）

## 三、重构原则

### 3.1 核心原则
1. **渐进式拆分**：每次只迁移一小部分，确保功能正常
2. **独立验证**：每个步骤完成后立即验证
3. **功能无损**：确保所有原有功能正常工作
4. **性能优化**：减少不必要的重渲染，保持性能

### 3.2 架构设计
```
NewChatContainer (编排器，~200行)
├── useChatState (状态管理层)
├── useChatCallbacks (回调管理层)
├── useChatStreaming (SSE流式层)
├── useChatSession (会话管理层)
├── useChatPersistence (持久化层)
└── UI Components (渲染层)
```

## 四、详细实施步骤

### Phase 1: 准备阶段（1天）

#### Task 1.1: 备份原始文件
```bash
# 备份原始NewChatContainer
cp src/components/Chat/NewChatContainer.tsx src/components/Chat/NewChatContainer.backup.tsx

# 创建重构分支
git checkout -b refactor/newchatcontainer-hooks
```

#### Task 1.2: 创建Hook文件结构
```
src/hooks/chat/
├── useChatState.ts          # 统一状态管理
├── useChatCallbacks.ts      # 统一回调管理
├── useChatStreaming.ts      # SSE流式管理（更新现有）
├── useChatSession.ts        # 会话管理（更新现有）
└── useChatPersistence.ts    # 持久化管理（更新现有）
```

#### Task 1.3: 设置测试环境
```bash
# 安装测试依赖（如果尚未安装）
npm install --save-dev @testing-library/react @testing-library/jest-dom

# 创建测试文件
mkdir -p src/hooks/chat/__tests__
touch src/hooks/chat/__tests__/useChatState.test.ts
touch src/hooks/chat/__tests__/useChatCallbacks.test.ts
```

### Phase 2: 迁移状态到useChatState（2天）

#### Task 2.1: 创建useChatState Hook
```typescript
// 已创建：src/hooks/chat/useChatState.ts
// 包含所有24个useState和15个useRef
```

**验证步骤**：
1. 编译通过：`npm run build`
2. 类型检查：`npx tsc --noEmit`
3. 导入测试：在NewChatContainer中导入但不使用

#### Task 2.2: 逐步替换状态定义
```typescript
// 在NewChatContainer.tsx中
import { useChatState } from '../../hooks/chat/useChatState';

const NewChatContainer: React.FC = () => {
  // 替换所有useState和useRef
  const chatState = useChatState();
  
  // 解构使用
  const {
    messages, setMessages,
    loading, setLoading,
    // ... 其他状态
  } = chatState;
  
  // 删除原有的useState和useRef定义
};
```

**验证步骤**：
1. 替换状态定义，编译通过
2. 运行应用，测试基本功能
3. 发送消息、接收消息功能正常
4. 会话管理功能正常

### Phase 3: 拆分 SSE 回调（~200行）（2天）

**目标**：将 onStep/onChunk/onComplete 移入 useChatStreaming

#### Task 3.1: 创建useChatCallbacks Hook
```typescript
// 已创建：src/hooks/chat/useChatCallbacks.ts
// 包含所有SSE回调：onStep, onChunk, onComplete, onError, onPaused, onResumed
// 注意：这些回调定义在useChatCallbacks，但由useChatStreaming使用
```

**验证步骤**：
1. 编译通过，类型检查
2. 在NewChatContainer中导入但不使用
3. 确保所有回调函数依赖正确

#### Task 3.2: 将SSE回调集成到useChatStreaming
```typescript
// 在NewChatContainer.tsx中
import { useChatCallbacks } from '../../hooks/chat/useChatCallbacks';

const NewChatContainer: React.FC = () => {
  const chatState = useChatState();
  const chatCallbacks = useChatCallbacks(chatState);
  
  // 将回调传入useChatStreaming
  const chatStreaming = useChatStreaming(
    chatState,
    chatCallbacks,  // 传入回调
    { baseURL: API_BASE_URL, sessionId: chatState.sessionId }
  );
};
```

**验证步骤**：
1. SSE回调移入useChatStreaming，编译通过
2. 测试SSE连接和消息发送
3. 验证流式功能正常
4. 测试暂停/恢复功能

### Phase 4: 完善useChatStreaming Hook（2天）

#### Task 4.1: 完善SSE Hook
```typescript
// 更新：src/hooks/chat/useChatStreaming.ts
// 集成useSSE，提供完整的SSE功能接口
```

**验证步骤**：
1. 更新Hook实现，编译通过
2. 在NewChatContainer中替换原有的useSSE调用
3. 测试SSE连接和消息发送
4. 验证流式功能正常

#### Task 4.2: 集成到NewChatContainer
```typescript
const chatStreaming = useChatStreaming(
  chatState,
  chatCallbacks,
  { baseURL: API_BASE_URL, sessionId: chatState.sessionId }
);
```

### Phase 5: 拆分会话管理（~200行）（1天）

**目标**：loadSession/saveState 移入 useChatSession

#### Task 5.1: 完善会话管理Hook
```typescript
// 更新：src/hooks/chat/useChatSession.ts
// 包含会话加载（loadSession）、保存（saveState）、创建、清空、标题更新等功能
```

**验证步骤**：
1. 更新Hook实现，编译通过
2. 在NewChatContainer中替换会话相关逻辑
3. 测试新建会话、加载会话、清空对话功能
4. 验证标题编辑和版本控制功能

#### Task 5.2: 集成到NewChatContainer
```typescript
const chatSession = useChatSession(chatState);
```

### Phase 6: 完善useChatPersistence Hook（1天）

#### Task 6.1: 完善持久化Hook
```typescript
// 更新：src/hooks/chat/useChatPersistence.ts
// 包含防抖保存、页面可见性处理、状态恢复等功能
```

**验证步骤**：
1. 更新Hook实现，编译通过
2. 在NewChatContainer中替换持久化逻辑
3. 测试页面刷新恢复功能
4. 测试页面切换保存功能
5. 验证sessionStorage数据正确性

#### Task 6.2: 集成到NewChatContainer
```typescript
const chatPersistence = useChatPersistence(chatState, chatStreaming);
```

### Phase 7: 重构NewChatContainer（2天）

> **小强补充 - 2026-04-22**  
> Phase 7是整个重构的最后一步，需要将NewChatContainer从1538行减少到约200行，成为纯编排器。

#### Phase 7 模块划分总览

| 模块 | 函数名 | 行号范围 | 目标迁移位置 | 优先级 |
|------|--------|----------|--------------|--------|
| **7.1** | `executeStreamSend` | 1062-1161 | `useChatStreaming` | P1 |
| **7.2** | `handleInterrupt` | 1187-1305 | `useChatTaskControl` (新建) | P1 |
| **7.3** | `handleTogglePause` | 1310-1345 | `useChatTaskControl` (合并) | P1 |
| **7.4** | `checkNetworkConnection` | 678-694 | `utils/chatNetwork.ts` | P2 |
| **7.5** | `ensureTitlePersisted` + `debouncedSaveTitle` | 702-829 | 清理/复用 `useChatSession.updateSessionTitle` | P2 |
| **7.6** | `loadSession` useEffect | 835-1060 | `useChatSession` | P2 |
| **7.7** | 最终清理 | 全部 | NewChatContainer.tsx (~200行) | P3 |

---

## Phase 7 各模块处理规范

### 标准5步流程（每个模块必须遵守）

```
Step X.1: 分析依赖
    ↓ 分析函数调用的所有API、状态、Refs、回调
Step X.2: 设计方案
    ↓ 制定迁移到目标Hook的详细方案
Step X.3: 确认方案
    ↓ 向用户确认方案后执行（必须等用户同意）
Step X.4: 实施迁移
    ↓ 实际执行迁移代码（先备份）
Step X.5: 验证功能
    ↓ 编译+测试验证功能正常
```

---

## 模块 7.1: executeStreamSend 迁移到 useChatStreaming

### Step 7.1.1: 分析依赖

**函数位置**: NewChatContainer.tsx 第1062-1161行

**调用关系分析**:
```
executeStreamSend(userMessage: Message)
├── setLoading(true)
├── setWaitTime(0), setIsRetrying(false)
├── waitTimerRef (setInterval)
├── clearSteps()
├── getClientInfo()  ← 需要迁移
├── sessionApi.saveMessage()  ← 需要迁移
├── replyUserMessageIdRef
├── setMessages (更新用户消息ID)
├── sendStreamMessage()  ← 已在useChatStreaming
└── 创建 assistantMessage
```

**使用的状态**:
- `currentSessionIdRef.current`
- `sessionId`
- `loading`, `setLoading`
- `waitTime`, `setWaitTime`
- `isRetrying`, `setIsRetrying`
- `messages`, `setMessages`
- `waitTimerRef`

**使用的Refs**:
- `currentSessionIdRef`
- `replyUserMessageIdRef`
- `waitTimerRef`
- `executionStepsRef` (clearSteps)

**严重注意事项**:
- ⚠️ `getClientInfo()` 获取客户端信息，必须随 `sessionApi.saveMessage` 一起迁移
- ⚠️ `sendStreamMessage` 已在 `useChatStreaming`，不能重复迁移
- ⚠️ 需要保留对 `sendStreamMessage` 的调用，但消息构建逻辑可以内部化
- ⚠️ `waitTimerRef` 的 setInterval 逻辑需要确保清理

### Step 7.1.2: 设计方案

**推荐方案**: 在 `useChatStreaming` 中添加 `executeStreamSend` 方法

```typescript
// useChatStreaming.ts 新增方法
const executeStreamSend = useCallback(async (userMessage: Message, options: {
  sessionId: string | null;
  setLoading: (v: boolean) => void;
  setWaitTime: (v: number) => void;
  setIsRetrying: (v: boolean) => void;
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>;
  replyUserMessageIdRef: React.MutableRefObject<number | null>;
  currentSessionIdRef: React.MutableRefObject<string | null>;
  waitTimerRef: React.MutableRefObject<NodeJS.Timeout | null>;
  // ... 其他需要的依赖
}) => {
  // 实现迁移的逻辑
}, [getClientInfo, sessionApi, sendStreamMessage]);
```

### Step 7.1.3: 确认方案

（待分析完成后向用户确认）

### Step 7.1.4: 实施迁移

（确认后执行）

### Step 7.1.5: 验证功能

（迁移后验证）

---

## 模块 7.2: handleInterrupt 创建 useChatTaskControl

### Step 7.2.1: 分析依赖

**函数位置**: NewChatContainer.tsx 第1187-1305行

**调用关系分析**:
```
handleInterrupt()
├── interruptInProgressRef (防重复点击)
├── serverTaskId
├── taskControlApi.cancel()  ← 核心依赖
├── waitForInterruptEvent()  ← 内部函数，也需迁移
├── showTaskControlInfo()
├── setLoading(false)
├── setIsPaused(false)
├── setIsReceiving(false)
├── waitTimerRef (clearInterval)
├── disconnect(true, true, callback)  ← 已在useChatStreaming
├── hasReceivedInterruptEventRef
├── showTaskResultMessage()
├── showTaskControlMessage()
└── interruptInProgressRef = false
```

**严重注意事项**:
- ⚠️ `waitForInterruptEvent` 是内部辅助函数，必须和 `handleInterrupt` 一起迁移
- ⚠️ `interruptInProgressRef` 用于防重复点击，这个机制必须保留
- ⚠️ `disconnect` 来自 `useChatStreaming`，需要通过参数传入
- ⚠️ `hasReceivedInterruptEventRef` 是外部Ref，需要正确传递
- ⚠️ 中断流程复杂，包含智能等待策略，不能破坏

### Step 7.2.2: 设计方案

**推荐方案**: 创建新的 `useChatTaskControl` Hook

```typescript
// src/hooks/chat/useChatTaskControl.ts
export const useChatTaskControl = (options: {
  chatState: ReturnType<typeof useChatState>;
  chatStreaming: ReturnType<typeof useChatStreaming>;
}) => {
  // handleInterrupt
  // handleTogglePause
  // waitForInterruptEvent (内部)
};
```

### Step 7.2.3-7.2.5: 确认后实施和验证

（待续）

---

## 模块 7.3: handleTogglePause 合并到 useChatTaskControl

### Step 7.3.1: 分析依赖

**函数位置**: NewChatContainer.tsx 第1310-1345行

**调用关系分析**:
```
handleTogglePause()
├── serverTaskId
├── taskControlApi.pause() / resume()  ← 核心依赖
├── isPaused (状态)
├── setIsPaused
├── isPausedRef
├── showNoActiveTaskWarning()
├── showTaskResultMessage()
└── handleError()
```

**严重注意事项**:
- ⚠️ 与 `handleInterrupt` 使用相同的 `taskControlApi`，应该合并到同一个Hook
- ⚠️ `handleTogglePause` 逻辑相对简单，但需要准确的状态判断

### Step 7.3.2-7.3.5: 确认后实施和验证

（待续）

---

## 模块 7.4: checkNetworkConnection 移入 utils

### Step 7.4.1: 分析依赖

**函数位置**: NewChatContainer.tsx 第678-694行

**函数内容**:
```typescript
const checkNetworkConnection = async (): Promise<boolean> => {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 3000);
  try {
    const response = await fetch(`${API_BASE_URL}/health`, {
      method: "GET",
      signal: controller.signal,
    });
    clearTimeout(timeoutId);
    return response.ok;
  } catch (error) {
    clearTimeout(timeoutId);
    console.warn("网络连接检查失败:", error);
    return false;
  }
};
```

**依赖**:
- `API_BASE_URL` (从 `../../services/api` 导入)

**严重注意事项**:
- ⚠️ 这是纯工具函数，没有任何状态依赖，可以直接移入 utils
- ⚠️ 只需要迁移函数本身，不需要创建Hook
- ⚠️ 建议放在 `utils/chatNetwork.ts` 或 `utils/network.ts`

### Step 7.4.2: 设计方案

**推荐方案**: 创建 `utils/network.ts`

```typescript
// src/utils/network.ts
export const checkNetworkConnection = async (apiBaseUrl: string): Promise<boolean> => {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 3000);
  try {
    const response = await fetch(`${apiBaseUrl}/health`, {
      method: "GET",
      signal: controller.signal,
    });
    clearTimeout(timeoutId);
    return response.ok;
  } catch (error) {
    clearTimeout(timeoutId);
    console.warn("网络连接检查失败:", error);
    return false;
  }
};
```

### Step 7.4.3-7.4.5: 确认后实施和验证

（待续）

---

## 模块 7.5: ensureTitlePersisted + debouncedSaveTitle 清理

### Step 7.5.1: 分析依赖

**函数位置**: 
- `ensureTitlePersisted`: 第702-821行
- `debouncedSaveTitle`: 第824-829行

**函数功能分析**:
```
ensureTitlePersisted(sessionId, title)
├── lastSavedTitle (防抖检查)
├── saveStatus (防抖检查)
├── retryCount
├── sessionApi.updateSession()  ← 核心
├── setSaveStatus
├── setIsSavingTitle
├── setSessionVersion
├── setLastSavedTitle
├── saveState()  ← 来自chatPersistence
├── setLastSaveTime
├── handleApiError()
├── showConflictError()
├── sessionApi.getSessionMessages()  ← 同步最新数据
├── setSessionTitle
├── setTitleLocked
└── showInfo() / showRetryWarning() / showSaveError()

debouncedSaveTitle
└── debounce(ensureTitlePersisted, 1000)
```

**与 useChatSession.updateSessionTitle 的关系**:
- `useChatSession` 已有 `updateSessionTitle` 方法
- 需要对比功能，确认是否完全覆盖

**严重注意事项**:
- ⚠️ `ensureTitlePersisted` 包含完整的重试机制和版本冲突处理
- ⚠️ `useChatSession.updateSessionTitle` 是否已经提供相同功能？
- ⚠️ 如果已覆盖，则删除这两个函数；如果没有，则增强 `updateSessionTitle`
- ⚠️ `debouncedSaveTitle` 使用 `debounce` 包装，必须确保防抖逻辑正确

### Step 7.5.2: 设计方案

（需要先对比 `useChatSession.updateSessionTitle` 的实现）

### Step 7.5.3-7.5.5: 确认后实施和验证

（待续）

---

## 模块 7.6: loadSession useEffect 迁移到 useChatSession

### Step 7.6.1: 分析依赖

**函数位置**: NewChatContainer.tsx 第835-1060行（useEffect）

**功能分析**:
```
loadSession useEffect
├── searchParams.get("session_id")
├── performance.getEntriesByType("navigation")  ← 检测强制刷新
├── sessionStorage.removeItem(STORAGE_KEY)  ← 强制刷新时
├── sessionId (URL参数)
├── setSessionJumpLoading
├── message.loading()
├── retryCount
├── isLoadingHistoryRef
├── loadHistoryMessages()  ← 来自chatHistory utils
├── setMessages
├── setSessionId
├── setSessionTitle
├── setSessionVersion
├── setTitleLocked
├── setIsRenderingMessages
├── setIsMessageListLoading
└── 大量sessionStorage读写逻辑
```

**严重注意事项**:
- ⚠️ 这是最复杂的useEffect，包含会话加载、恢复、状态同步等
- ⚠️ 与 `useChatPersistence` 功能有重叠（sessionStorage读写）
- ⚠️ 需要仔细分析哪些在 `useChatPersistence` 中已处理
- ⚠️ URL参数检测和强制刷新处理是特殊逻辑

### Step 7.6.2: 设计方案

（需要详细分析后制定）

### Step 7.6.3-7.6.5: 确认后实施和验证

（待续）

---

## 模块 7.7: 最终清理

### Step 7.7.1: 检查未使用导入

**检查项**:
- [ ] 所有从 `../../services/api` 导入的是否还在使用？
- [ ] 所有从 `../../utils/*` 导入的是否还在使用？
- [ ] 所有从 `../../hooks/chat/*` 导入的是否还在使用？
- [ ] 是否有未使用的 React API 导入？

### Step 7.7.2: 清理开发注释

**清理项**:
- [ ] 删除所有 `【xxx修复】` 类型的注释
- [ ] 删除所有 `【小x修复】` 类型的注释
- [ ] 删除所有 `# ====` 分隔线注释（如果不再需要）
- [ ] 保留必要的功能分组注释

### Step 7.7.3: 验证构建

```bash
npm run build
```

### Step 7.7.4: 验证功能

按照"五、验证清单"逐项验证

### Step 7.7.5: 提交代码

```bash
git add .
git commit -m "refactor: Phase 7完成 - NewChatContainer重构为纯编排器 - 小强-2026-04-22"
git tag v0.9.9  # 或下一个版本号
```

---

## Phase 7 严重注意事项（必须遵守）

> 🚨 **以下事项绝对不能漏，否则会导致功能缺失或严重Bug**

### 1. executeStreamSend 迁移注意事项
- ❌ 不能遗漏 `getClientInfo()` 的调用
- ❌ 不能遗漏 `sessionApi.saveMessage()` 的调用
- ❌ 不能破坏 `sendStreamMessage` 的调用链
- ❌ 必须保留 `waitTimerRef` 的清理逻辑

### 2. handleInterrupt 迁移注意事项
- ❌ 不能遗漏 `waitForInterruptEvent()` 智能等待逻辑
- ❌ 不能删除 `interruptInProgressRef` 防重复机制
- ❌ 必须正确处理 `hasReceivedInterruptEventRef`
- ❌ 中断后的状态同步必须完整

### 3. handleTogglePause 迁移注意事项
- ❌ 不能遗漏 `serverTaskId` 的检查
- ❌ 暂停和恢复的状态更新必须对称
- ❌ 错误处理必须完善

### 4. checkNetworkConnection 迁移注意事项
- ✅ 相对简单，但必须确保 API_BASE_URL 正确传递
- ✅ 3秒超时逻辑必须保留

### 5. ensureTitlePersisted 清理注意事项
- ⚠️ 必须先确认 `useChatSession.updateSessionTitle` 的功能覆盖范围
- ⚠️ 如果删除，必须确保 `updateSessionTitle` 完全替代
- ⚠️ `debouncedSaveTitle` 的防抖逻辑（1000ms）必须保留

### 6. loadSession 迁移注意事项
- ❌ 这是最复杂的部分，不能遗漏任何功能
- ❌ URL参数处理逻辑必须保留
- ❌ 强制刷新检测必须保留
- ❌ sessionStorage 恢复逻辑必须保留
- ❌ 与 `useChatPersistence` 的功能重叠需要理清

### 7. 最终清理注意事项
- ❌ 不能删除正在使用的导入
- ❌ 不能删除仍然需要的功能代码
- ❌ 验证清单必须逐项通过

---

## 五、验证清单

### 5.1 构建验证
- [ ] TypeScript编译无错误
- [ ] ESLint检查无警告
- [ ] 生产构建成功

### 5.2 功能验证
- [ ] 新建会话功能正常
- [ ] 发送消息功能正常
- [ ] 接收消息（流式）功能正常
- [ ] 中断功能正常
- [ ] 暂停/恢复功能正常
- [ ] 标题编辑功能正常
- [ ] 标题锁定功能正常
- [ ] 自动滚动功能正常
- [ ] 页面刷新后消息恢复
- [ ] SessionStorage持久化正常

### 5.3 性能验证
- [ ] 输入框输入不触发消息列表重渲染
- [ ] 滚动流畅无卡顿
- [ ] 内存使用正常

## 六、风险控制措施

### 6.1 代码版本控制
1. **每个Task创建独立分支**
   ```
   git checkout -b feature/use-chat-state
   git checkout -b feature/use-chat-callbacks
   git checkout -b feature/use-chat-streaming
   ```

2. **提交点标记**
   - 每个Hook创建完成后提交
   - 每个Hook集成完成后提交
   - 每个验证通过后提交

### 6.2 回滚策略
1. **保留原始文件备份**
   ```bash
   cp NewChatContainer.tsx NewChatContainer.backup.tsx
   ```

2. **快速回滚命令**
   ```bash
   # 如果验证失败
   git checkout -- NewChatContainer.tsx
   # 或
   cp NewChatContainer.backup.tsx NewChatContainer.tsx
   ```

### 6.3 测试策略
1. **单元测试**：为每个Hook编写单元测试
2. **集成测试**：测试Hook组合功能
3. **E2E测试**：完整用户流程测试

## 七、关键依赖关系

### 7.1 Hook依赖关系
```
useChatState (基础)
    ↓
useChatCallbacks (依赖useChatState)
    ↓
useChatStreaming (依赖useChatState + useChatCallbacks)
    ↑
useChatSession (依赖useChatState)
    ↑
useChatPersistence (依赖useChatState + useChatStreaming)
```

### 7.2 实施顺序
1. **useChatState** → 2. **useChatCallbacks** → 3. **useChatStreaming** → 4. **useChatSession** → 5. **useChatPersistence**

## 八、常见问题与解决方案

### 8.1 闭包问题
**问题**：回调函数捕获过时状态
**解决方案**：
- 所有回调使用 `useCallback` 并正确指定依赖
- 通过Refs访问最新状态
- 使用 `useEffect` 同步Refs和状态

### 8.2 状态同步问题
**问题**：多个Hook之间状态不一致
**解决方案**：
- `useChatState` 作为单一数据源
- 其他Hook通过参数接收状态
- 使用 `useEffect` 同步依赖状态

### 8.3 性能问题
**问题**：不必要的重渲染
**解决方案**：
- 使用 `React.memo` 包装子组件
- 使用 `useMemo` 缓存计算结果
- 状态拆分，避免大对象更新

## 九、实施时间安排

### Phase 1: 准备阶段（1天）
- 分析现有代码结构
- 创建Hook骨架文件
- 设置测试环境

### Phase 2: 状态迁移（2天）
- 创建useChatState Hook
- 迁移状态定义
- 验证状态同步

### Phase 3: 回调迁移（2天）
- 创建useChatCallbacks Hook
- 迁移SSE回调函数
- 验证回调功能

### Phase 4: SSE迁移（2天）
- 完善useChatStreaming Hook
- 迁移SSE配置
- 验证流式功能

### Phase 5: 会话迁移（1天）
- 完善useChatSession Hook
- 迁移会话逻辑
- 验证会话功能

### Phase 6: 持久化迁移（1天）
- 完善useChatPersistence Hook
- 迁移持久化逻辑
- 验证持久化功能

### Phase 7: 整合测试（2天）
- 整合所有Hook
- 运行完整测试
- 性能优化

**总计：约11个工作日**

## 十、成功标准

### 10.1 代码质量
- [ ] 主组件代码从2400+行减少到400行以内
- [ ] 每个Hook职责单一，不超过300行
- [ ] 类型定义完整，无any类型
- [ ] 测试覆盖率 > 80%

### 10.2 性能指标
- [ ] 输入响应时间 < 100ms
- [ ] 消息列表渲染时间 < 50ms
- [ ] 内存使用稳定，无泄漏
- [ ] 首次加载时间优化

### 10.3 可维护性
- [ ] 每个Hook可独立测试
- [ ] 文档完整，有使用示例
- [ ] 错误处理完善
- [ ] 日志记录清晰

## 十一、附录

### 11.1 文件结构
```
src/
├── components/
│   └── Chat/
│       ├── NewChatContainer.tsx          # 重构后主组件（~400行）
│       ├── NewChatContainer.backup.tsx   # 原始备份
│       ├── ChatHeader.tsx                # 已拆分
│       ├── ChatToolbar.tsx               # 已拆分
│       ├── MessageArea.tsx               # 已拆分
│       └── ChatInput.tsx                 # 已拆分
├── hooks/
│   └── chat/
│       ├── useChatState.ts              # 统一状态管理
│       ├── useChatCallbacks.ts          # 统一回调管理
│       ├── useChatStreaming.ts          # SSE流式管理
│       ├── useChatSession.ts            # 会话生命周期管理
│       └── useChatPersistence.ts        # 状态持久化与恢复
└── __tests__/
    └── hooks/
        └── chat/
            ├── useChatState.test.ts
            ├── useChatCallbacks.test.ts
            ├── useChatStreaming.test.ts
            ├── useChatSession.test.ts
            └── useChatPersistence.test.ts
```

### 11.2 测试用例示例
```typescript
// useChatState.test.ts
describe('useChatState', () => {
  it('应该初始化所有状态', () => {
    const { result } = renderHook(() => useChatState());
    
    expect(result.current.messages).toEqual([]);
    expect(result.current.sessionId).toBeNull();
    expect(result.current.isPaused).toBe(false);
    // ... 其他状态断言
  });
  
  it('应该同步Refs和状态', () => {
    const { result } = renderHook(() => useChatState());
    
    act(() => {
      result.current.setMessages([{ id: '1', role: 'user', content: 'test', timestamp: new Date() }]);
    });
    
    expect(result.current.messagesRef.current).toHaveLength(1);
  });
});
```

### 11.3 回滚检查点
1. **Phase 2完成后**：状态管理功能正常
2. **Phase 3完成后**：SSE回调功能正常
3. **Phase 4完成后**：流式功能正常
4. **Phase 5完成后**：会话管理功能正常
5. **Phase 6完成后**：持久化功能正常
6. **Phase 7完成后**：完整集成测试通过

---

**编写人**：小强（资深前端开发）  
**日期**：2026-04-21  
**版本**：v1.0