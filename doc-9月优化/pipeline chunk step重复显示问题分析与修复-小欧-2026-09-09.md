# pipeline chunk/step 重复显示问题分析与修复

> **文档名称**: pipeline chunk/step 重复显示问题分析与修复-小欧-2026-09-09.md
> **编写人**: 小欧
> **编写时间**: 2026-09-09 23:07:54
> **签名**: 小欧

**版本历史**：
| 版本 | 时间 | 更新信息 | 作者 |
|------|------|---------|------|
| v1.6 | 2026-09-10 05:12:58 | 根因补双流并存(useSSE不abort旧流), chunk分支steps1-3无去重, 修复方案补修订点1(abort旧流)+8(chunk去重) | 小欧 |

**关联文档**:
- [17]任务1任务2问题根因分析报告-小欧-2026-09-09.md
- [18]前端 UI显示缺陷分析之一-小欧-2026-09-09.md
- [19]前端渲染显示缺陷分析之二-小沈-2026-09-09.md
- 前端step冻结丢失显示的实施解决说明-小欧-2026-09-09.md

---

## 一、问题总结

| 维度 | 描述 |
|------|------|
| 现象 | pipeline 执行面板中，chunk（思考/回答片段）和 step 出现重复显示。不仅第一个 thought 的 chunk，中间的 chunk 也频繁发生 |
| 影响范围 | 所有类型（thought/chunk/action/observation/paused/resumed/retrying）的 step 都受影响；chunk 类型还会导致 responseBufferRef/streamingContentRef 翻倍→文本内容翻倍 |
| 频率 | 经常发生，非偶发 |
| 根因 | ① 空闲超时重连不 abort 旧流→新旧双流并存，同一批事件被两条流各处理一次；② `setExecutionSteps` 7处 updater 无去重；③ `final` 分支 line:499 直接赋值 ref 绕过 updater 去重；④ chunk 分支 steps 1-3（responseBufferRef/streamingContentRef）无去重→双流时文本翻倍 |
| 病根位置 | `useSSE.ts:680` 重连不abort旧流 + `sseParser.ts` 7处 updater + final直赋ref + chunk分支steps1-3 |

---

## 二、根因分析

### 2.1 双流并存（主要根因）

空闲超时重连时，旧流未被 abort，新旧两条流同时送达同一批事件：

```
useSSE.ts 重连流程:
1. 空闲超时60s → idle timeout 回调触发 reconnect()        (line:763)
2. reconnect → sendMessageInternal → 创建新 AbortController  (line:680-681)
3. 但旧 controller 未 abort → 旧 reader.read() 仍阻塞等待   (line:769)
4. 新 GET 请求发出 → 新流建立                                (line:692)
5. 旧流恢复交付数据 + 新流也交付同一批数据 → 双流并存
```

双流并存时，每个事件被 processSSEData 处理两次：

| 步骤 | 旧流处理 | 新流处理 | 后果 |
|------|---------|---------|------|
| responseBufferRef.current += chunk | +abc → "abc" | +abc → "abcabc" | **文本翻倍** |
| setCurrentResponse | "abc" | "abcabc" | **UI翻倍** |
| onChunk → streamingRef + message.content | "abc" | "abcabc" | **消息翻倍** |
| setExecutionSteps | 加入 | dedup跳过 | 正确 |
| onStep → message.executionSteps | 加入 | dedup跳过 | 正确 |

### 2.2 两条写入路径的去重不对称

每个 SSE 事件（chunk/thought/action/observation 等）在 sseParser 中走两条写入路径：

**路径A — `setExecutionSteps`（写 `executionSteps` state → pipeline 渲染）**
```
sseParser.ts 各 case:
setExecutionSteps((prev) => {
  const newSteps = [...prev, step];  // ← 直接追加，无任何去重
  handlers.executionStepsRef.current = newSteps;
  saveStepsToStorage?.(newSteps);
  return newSteps;
});
```
→ `executionSteps` state（useSSE.ts:383）
→ RightViewer `liveSteps` prop
→ PipelineRenderer 渲染

**路径B — `onStep`（写 `message.executionSteps` → 消息元数据）**
```
sseParser.ts 各 case:
onStep?.(step);
```
→ useChatCallbacks.ts:161-170 指纹去重（`type|step|preview|content前64`）
→ useChatCallbacks.ts:266 追加到 `message.executionSteps`

**关键缺陷**：路径A无去重，路径B有去重。

| 路径 | 目标 | 去重 | 重复事件行为 |
|------|------|------|------------|
| A: `setExecutionSteps` | `executionSteps` → pipeline | **无** | 直接追加，N次就加N次 |
| B: `onStep` | `message.executionSteps` | 指纹去重 | 重复被跳过 |

同一事件到达两次时：`executionSteps` 包含2份，`message.executionSteps` 只有1份。pipeline 渲染 `executionSteps` → 显示2次。

### 2.3 重连重放机制触发重复

**重连流程**（useSSE.ts:688-691）：
1. SSE 连接断开（空闲超时60s / 网络抖动）
2. 触发 `reconnect()`（useSSE.ts:763）
3. `softClearSteps()`（useSSE.ts:617-620）：**不清空 `executionSteps`**
4. 重连 GET 带 `after_seq=${lastSeqRef.current}`
5. **如果后端某些事件无 `seq` 字段**，`lastSeqRef.current` 不是最新值
6. 后端按旧 `after_seq` 重发已处理事件
7. `setExecutionSteps` 无去重 → 追加 → **pipeline 重复显示**

### 2.4 setExecutionSteps 无去重（次要根因）

7处 `setExecutionSteps` updater 直接 `[...prev, step]` 追加，无任何去重：

```
sseParser.ts 各 case:
setExecutionSteps((prev) => {
  const newSteps = [...prev, step];  // ← 无 has() 检查，直接追加
  handlers.executionStepsRef.current = newSteps;
  saveStepsToStorage?.(newSteps);
  return newSteps;
});
```

→ `executionSteps` state → RightViewer `liveSteps` → PipelineRenderer 渲染

### 2.5 铁证清单

| # | 位置 | 证据 |
|---|------|------|
| 1 | useSSE.ts:680-681 | `const controller = new AbortController(); abortControllerRef.current = controller` — 创建新controller但不abort旧的 |
| 2 | sseParser.ts:401 | `responseBufferRef.current += chunkContent` — 无去重，双流时翻倍 |
| 3 | sseParser.ts:429,381,503,679,830,870 | `const newSteps = [...prev, step]` — 无 has() 检查，直接追加；:256 为 `const next = [...prev, ts]` 同理 |
| 4 | useChatCallbacks.ts:167-169 | `onStep` 指纹去重只保护 `message.executionSteps`，不保护 `executionSteps` |
| 5 | useSSE.ts:617-620 | `softClearSteps` 不清空 `executionSteps`，重连后旧数据保留 |
| 6 | useSSE.ts:837-838 | `onSeq` 只在 `rawData.seq` 存在时更新，后端某事件无 seq 则 `lastSeqRef` 不更新 |
| 7 | sseParser.ts:440,391,512,690,840,880,261 | `onStep?.(step/ts)` 在 `setExecutionSteps` 之后调用，指纹去重无法挽回已追加的 state |
| 8 | sseParser.ts:498-499 | `final` 分支：`const updatedSteps = [...handlers.executionStepsRef.current, step]` 直接赋值 ref，**绕过 `setExecutionSteps` updater**，即使 updater 有去重也无法阻止 ref 被污染 |

---

## 三、修复方案（全部为真实 diff 代码）

### 3.1 设计原则

| 规范 | 遵守 |
|------|------|
| **DRY** | `isStepDuplicate` 单函数复用9处（7处 updater + final直赋ref + chunk分支），不重复写去重逻辑 |
| **KISS-DIRECT** | 指纹检查直接在 updater 内完成，无中间层、无注册表、无抽象 |
| **SLAP** | 去重逻辑与保存逻辑分离，各做各的事 |
| **复用优先** | 复用 `onStep` 已有的指纹格式（`type|step|preview|content前64`），不另造 |
| **禁止backward** | 不兼容旧逻辑，直接替换 |

### 3.2 完整调用链

```
useSSE.ts                                          sseParser.ts
──────────                                         ────────────
① 定义 isStepDuplicate 函数                         ③ 从 handlers 解构 isStepDuplicate
   (line:385-395)                                      (line:125)
        │                                                  │
        ▼                                                  ▼
② 通过 handlers 传给 processSSEData ──传参──▶  ④ 7处 setExecutionSteps updater 内调用
   (line:780, 820)                                      (line:256,381,430,503,679,830,870)
                                                             │
                                                        ⑤ final 分支1处直接 ref 赋值也调用
                                                             (line:499)
                                                             │
                                                        ⑥ chunk 分支 steps 1-3 前加去重
                                                             (line:400-403)
```

### 3.3 文件一：`frontend/src/hooks/useSSE.ts`

#### 修订点1：重连时 abort 旧流（line:680 前插入）

```diff
+      // 2026-09-10 小欧: 重连前abort旧流, 防双流并存导致事件重复处理
+      if (abortControllerRef.current) {
+        abortControllerRef.current.abort();
+      }
       const controller = new AbortController();
       abortControllerRef.current = controller;
```

#### 修订点2：新增 `stepFingerprintRef` + `isStepDuplicate` 函数（line:384 后插入）

```diff
   const [executionSteps, setExecutionSteps] = useState<ExecutionStep[]>([]);
   const executionStepsRef = useRef<ExecutionStep[]>([]);
+  // 2026-09-09 小欧: step指纹去重Set, 防重连重放导致executionSteps重复追加
+  //   指纹格式与onStep一致: type|step|preview|content前64
+  const stepFingerprintRef = useRef<Set<string>>(new Set());
+  // 返回true=重复, false=首次出现; 副作用: 首次出现时自动add到Set
+  const isStepDuplicate = useCallback((step: ExecutionStep, prev: ExecutionStep[]): boolean => {
+    const fp = [step.type, step.step ?? '', step.preview ? 'p' : '', (step.content ?? '').slice(0, 64)].join('|');
+    // 先检查prev(当前state快照), 再检查Set(跨React批处理兜底)
+    if (prev.some(s => [s.type, s.step ?? '', s.preview ? 'p' : '', (s.content ?? '').slice(0, 64)].join('|') === fp)) return true;
+    if (stepFingerprintRef.current.has(fp)) return true;
+    stepFingerprintRef.current.add(fp);
+    return false;
+  }, []);
   const [currentResponse, setCurrentResponse] = useState('');
```

#### 修订点3：`clearSteps` 中清空 fingerprint Set（line:627 后插入）

```diff
   const clearSteps = useCallback(() => {
     setExecutionSteps([]);
     executionStepsRef.current = [];
+    stepFingerprintRef.current.clear();
     setCurrentResponse('');
     responseBufferRef.current = '';
```

#### 修订点4：第一处 `processSSEData` 调用 handlers 新增 `isStepDuplicate`（line:779 后插入）

```diff
               executionStepsRef,
               saveStepsToStorage,
+              isStepDuplicate,
               onStep,
               onChunk,
               onComplete,
```

#### 修订点5：第二处 `processSSEData` 调用 handlers 新增 `isStepDuplicate`（line:819 后插入）

```diff
               executionStepsRef,
               saveStepsToStorage,
+              isStepDuplicate,
               onStep,
               onChunk,
               onComplete,
```

---

### 3.4 文件二：`frontend/src/features/chat/services/sseParser.ts`

#### 修订点6：handlers 类型定义新增 `isStepDuplicate` 字段（line:74 后插入）

```diff
     saveStepsToStorage?: (steps: ExecutionStep[]) => void; // 【小强添加 2026-03-18】保存到 sessionStorage
+    isStepDuplicate?: (step: ExecutionStep, prev: ExecutionStep[]) => boolean; // 2026-09-09 小欧: 指纹去重, 防重连重放
     onStep?: (step: ExecutionStep) => void;
```

#### 修订点7：handlers 解构新增 `isStepDuplicate`（line:124 后插入）

```diff
     saveStepsToStorage,
+    isStepDuplicate,
     onStep,
     onChunk,
```

#### 修订点8：`case 'chunk'` 分支头部加去重，防双流时 responseBufferRef/streamingRef 翻倍（line:396-399 之间插入）

```diff
       case 'chunk': {
+        // 2026-09-10 小欧: chunk分支去重, 防双流并存导致responseBufferRef/streamingRef翻倍(文本翻倍)
+        //   在setExecutionSteps前拦截, 避免responseBufferRef/currentResponse/onChunk被重复执行
+        const _chunkFp = [rawData.type, rawData.step ?? '', rawData.content?.slice(0, 64) ?? ''].join('|');
+        if (handlers.isStepDuplicate?.({ type: 'chunk', step: Number(rawData.step) || 0, content: rawData.content } as ExecutionStep, [])) {
+          break;
+        }
         // 精简日志：chunk不打印，避免日志过多
```

#### 修订点9：`case 'thought-start'` updater 加去重（line:255-256 之间插入）

```diff
         setExecutionSteps((prev) => {
+          // 2026-09-09 小欧: 指纹去重, 防重连重放导致重复追加
+          if (isStepDuplicate?.(ts, prev)) return prev;
           const next = [...prev, ts];
           handlers.executionStepsRef.current = next;
```

#### 修订点10：`case 'thought'` updater 加去重（line:380-381 之间插入）

```diff
         setExecutionSteps((prev) => {
+          // 2026-09-09 小欧: 指纹去重, 防重连重放导致重复追加
+          if (isStepDuplicate?.(step, prev)) return prev;
           const newSteps = [...prev, step];
           handlers.executionStepsRef.current = newSteps;
```

#### 修订点11：`case 'chunk'` updater 加去重（line:429-430 之间插入）

```diff
         setExecutionSteps((prev) => {
+          // 2026-09-09 小欧: 指纹去重, 防重连重放导致重复追加
+          if (isStepDuplicate?.(step, prev)) return prev;
           const newSteps = [...prev, step];
           handlers.executionStepsRef.current = newSteps;
```

#### 修订点12：`case 'final'` 直接 ref 赋值加去重（line:498-499 替换）

```diff
         // 【关键修复 2026-04-13】在回调之前先更新ref，确保onComplete获取完整数据
         // 问题：setExecutionSteps回调是异步的，导致onComplete拿到旧值
         // 解决：先直接更新ref，再调用onComplete
-        const updatedSteps = [...handlers.executionStepsRef.current, step];
-        handlers.executionStepsRef.current = updatedSteps;
+        // 2026-09-09 小欧: 指纹去重, 防重连重放导致ref被污染(此赋值绕过setExecutionSteps updater)
+        if (!isStepDuplicate?.(step, handlers.executionStepsRef.current)) {
+          const updatedSteps = [...handlers.executionStepsRef.current, step];
+          handlers.executionStepsRef.current = updatedSteps;
+        }
```

#### 修订点13：`case 'final'` updater 加去重（line:502-503 之间插入）

```diff
         setExecutionSteps((prev) => {
+          // 2026-09-09 小欧: 指纹去重, 防重连重放导致重复追加
+          if (isStepDuplicate?.(step, prev)) return prev;
           const newSteps = [...prev, step];
```

#### 修订点14：`case 'action'` updater 加去重（line:678-679 之间插入）

```diff
         setExecutionSteps((prev) => {
+          // 2026-09-09 小欧: 指纹去重, 防重连重放导致重复追加
+          if (isStepDuplicate?.(step, prev)) return prev;
           const newSteps = [...prev, step];
           handlers.executionStepsRef.current = newSteps;
```

#### 修订点15：`case 'observation'` updater 加去重（line:829-830 之间插入）

```diff
         setExecutionSteps((prev) => {
+          // 2026-09-09 小欧: 指纹去重, 防重连重放导致重复追加
+          if (isStepDuplicate?.(step, prev)) return prev;
           const newSteps = [...prev, step];
           handlers.executionStepsRef.current = newSteps;
```

#### 修订点16：`case 'paused'/'resumed'/'retrying'` updater 加去重（line:869-870 之间插入）

```diff
         setExecutionSteps((prev) => {
+          // 2026-09-09 小欧: 指纹去重, 防重连重放导致重复追加
+          if (isStepDuplicate?.(step, prev)) return prev;
           const newSteps = [...prev, step];
           handlers.executionStepsRef.current = newSteps;
```

---
## 四、同类问题深挖：真实可测 Bug 清单

### 4.1 bug清单

> 以下均经代码逐行验证，非猜测。标记【TEST】的可用测试复现；【已确认】为代码级缺陷，测试受环境限制。

| # | 严重度 | 文件:行 | 缺陷描述 | 复现方式 | 与本文关系 |
|---|--------|---------|---------|---------|-----------|
| A | 高 | useSSE.ts:599-601 | `manualDisconnect` 的 `setTimeout` 不存句柄、不清理；3秒内组件卸载会回调已卸载组件，快速断/连会叠加多个竞态 timer | 连接后立即 `disconnect(true)`，3秒内切换会话（卸载）→ 日志显示定时器回调在卸载后仍运行【TEST】 | 防抖清理同类缺口 |
| B | 高 | useSSE.ts:744-765, 680-681 | **空闲超时重连只新建 AbortController，不 abort 旧流** → 旧流仍存活，新旧两条流同时送达同一批事件 → 这是重复显示的**真实根因之一**，比 after_seq 重放更常见 | 网络卡顿>60s触发IDLE超时 → 重连GET成功后，旧reader旧流仍在接收 → F12网络面板可见两条流并存【TEST】 | **本文核心问题的加强证据** |
| C | 高 | useSSE.ts:770-810 | 流结束(`done`)时 buffer 残留**不完整JSON帧**，`processSSEData` JSON.parse 抛错仅 console.error，帧静默丢失，无重连无提示 | 代理/限速把最后一个 `data:` 帧截断 → 任务结束但最后一批 chunk 内容丢失【TEST】 | 同类"静默丢数据" |
| D | 中 | sseParser.ts:186 | `step: Number(rawData.step) || 1` 把 `step=0` 强制变 1（`0||1===1`）；meta 事件(paused/retrying 等) step=0 与首个业务步 step=1 撞号 | 后端发 `step=0` 的 paused → 前端生成 step=1 → 与第一个 thought step=1 冲突，stepFilter 分组错乱【TEST】 | 数据完整性 |
| E | 中 | sseParser.ts:498-511 | final 分支先**同步直写 ref**（:498，基于未flush的旧ref），再走 `setExecutionSteps` updater（:502）。若 obs+final 同一网络块到达（updater未flush），:498 的 ref 缺 obs → `onComplete` 的三个参数 `finalStepsWithCurrent`（:517）**缺 observation 步骤** | 构造含 obs 与 final 的多行 SSE 块一次喂入 → onComplete 第三参缺 obs【TEST】 | 与 bug-2 step5/6丢失同根 |
| F | 中 | PipelineRenderer.tsx:131,190-221 | `pendingPreviewToolIdx` 单槽：连续两个 preview（并行多工具）时后一个覆盖前一个；前 preview 的 canonical 到达时错改后一个 tool 段，且前 canonical 落入"无配对"分支重复建段 | 构造 steps=[preview1, preview2, canonical1, canonical2] 喂 `buildSegments` → 段2被canonical1覆盖且出现重复段【TEST】 | 渲染重复同类 |
| G | 中 | useChatCallbacks.ts:530-532 | `onComplete` 先清空 `executionStepsRef.current=[]` 再 `setMessages`(异步)；若同缓冲后续行还有重复 step 走 onStep，指纹Set已 clear，去重失效，message.executionSteps 被重复追加 | 重连重放下 final 后到达的重复行→ 消息步骤重复【TEST】 | 去重生命周期缺口 |
| H | 中 | useSSE.ts:918-996 | `reconnect` useCallback 依赖 `[sendMessageInternal, onError]`（:996），若父级 `onError` 每次渲染新建引用，**已在跑的IDLE定时器仍持有旧 reconnect 闭包**，触发时用旧 onError → 错误上报错对象 | onError 用内联箭头函数 + 重渲染后触发空闲超时【TEST】 | 陈旧闭包 |
| I | 低 | useSSE.ts:490-498 | saveStepsToStorage 防抖300ms：任务完成(final)后300ms内刷新/关页，**尾段步骤未落 sessionStorage**，刷新后恢复缺尾 | final 到达后立刻 F5 → 恢复的步骤少于实际【TEST】 | 防抖副作用 |
| J | 低 | useSSE.ts:726-728 | `!response.body` 时抛错但**未 abort controller**、未清理 `fetchTimeoutRef`（:717-720只在 response.ok 后才清） | 后端返回空body →  fetchTimeout 180s 后仍触发 abort【TEST】 | 资源泄漏 |
### 4.2 bug修改代码diff

