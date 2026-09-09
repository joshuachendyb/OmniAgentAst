# pipeline chunk/step 重复显示问题分析与修复

> **文档名称**: pipeline chunk/step 重复显示问题分析与修复-小欧-2026-09-09.md
> **编写人**: 小欧
> **编写时间**: 2026-09-09 23:07:54
> **签名**: 小欧

**版本历史**：
| 版本 | 时间 | 更新信息 | 作者 |
|------|------|---------|------|
| v1.0 | 2026-09-09 23:07:54 | 初版：chunk/step重复显示根因分析+修复diff | 小欧 |
| v1.1 | 2026-09-09 23:11:30 | 补充second漏洞：final分支line499直接ref赋值绕过去重+8处全覆盖清单 | 小欧 |
| v1.2 | 2026-09-09 23:16:42 | 重写第三章：加完整调用链图(定义→传递→使用)，拆分6个子章节按执行顺序排列 | 小欧 |
| v1.3 | 2026-09-09 23:18:18 | 全部修订点替换为真实diff代码，删除所有伪代码和示意图 | 小欧 |
| v1.4 | 2026-09-09 23:20:05 | 恢复v1.2调用链图，放置在3.2节，标注真实行号 | 小欧 |

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
| 影响范围 | 所有类型（thought/chunk/action/observation/paused/resumed/retrying）的 step 都受影响 |
| 频率 | 经常发生，非偶发 |
| 根因 | ① `setExecutionSteps` 7处 updater 无去重，重连重放时同一 step 被重复追加；② `final` 分支 line:499 直接赋值 `executionStepsRef.current` 绕过 updater 去重 |
| 病根位置 | `sseParser.ts` 7处 `setExecutionSteps` updater + final分支1处直接ref赋值 + `useSSE.ts` 缺少 fingerprint 去重 |

---

## 二、根因分析

### 2.1 两条写入路径的去重不对称

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

### 2.2 重连重放机制触发重复

**重连流程**（useSSE.ts:688-691）：
1. SSE 连接断开（空闲超时60s / 网络抖动）
2. 触发 `reconnect()`（useSSE.ts:763）
3. `softClearSteps()`（useSSE.ts:617-620）：**不清空 `executionSteps`**
4. 重连 GET 带 `after_seq=${lastSeqRef.current}`
5. **如果后端某些事件无 `seq` 字段**，`lastSeqRef.current` 不是最新值
6. 后端按旧 `after_seq` 重发已处理事件
7. `setExecutionSteps` 无去重 → 追加 → **pipeline 重复显示**

### 2.3 铁证清单

| # | 位置 | 证据 |
|---|------|------|
| 1 | sseParser.ts:430,381,503,679,830,870,256 | `const newSteps = [...prev, step]` — 无 has() 检查，直接追加 |
| 2 | useChatCallbacks.ts:167-169 | `onStep` 指纹去重只保护 `message.executionSteps`，不保护 `executionSteps` |
| 3 | useSSE.ts:617-620 | `softClearSteps` 不清空 `executionSteps`，重连后旧数据保留 |
| 4 | useSSE.ts:837-838 | `onSeq` 只在 `rawData.seq` 存在时更新，后端某事件无 seq 则 `lastSeqRef` 不更新 |
| 5 | sseParser.ts:440,391,512,695,840,880 | `onStep?.(step)` 在 `setExecutionSteps` 之后调用，指纹去重无法挽回已追加的 state |
| 6 | sseParser.ts:498-499 | `final` 分支：`const updatedSteps = [...handlers.executionStepsRef.current, step]` 直接赋值 ref，**绕过 `setExecutionSteps` updater**，即使 updater 有去重也无法阻止 ref 被污染 |

---

## 三、修复方案（全部为真实 diff 代码）

### 3.1 设计原则

| 规范 | 遵守 |
|------|------|
| **DRY** | 抽取公共 `isStepDuplicate` 函数，8处复用（7处 updater + 1处 final 直赋 ref），不重复写去重逻辑 |
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
```

### 3.3 文件一：`frontend/src/hooks/useSSE.ts`

#### 修订点1：新增 `stepFingerprintRef` + `isStepDuplicate` 函数（line:384 后插入）

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

#### 修订点2：`clearSteps` 中清空 fingerprint Set（line:627 后插入）

```diff
   const clearSteps = useCallback(() => {
     setExecutionSteps([]);
     executionStepsRef.current = [];
+    stepFingerprintRef.current.clear();
     setCurrentResponse('');
     responseBufferRef.current = '';
```

#### 修订点3：第一处 `processSSEData` 调用 handlers 新增 `isStepDuplicate`（line:779 后插入）

```diff
               executionStepsRef,
               saveStepsToStorage,
+              isStepDuplicate,
               onStep,
               onChunk,
               onComplete,
```

#### 修订点4：第二处 `processSSEData` 调用 handlers 新增 `isStepDuplicate`（line:819 后插入）

```diff
               executionStepsRef,
               saveStepsToStorage,
+              isStepDuplicate,
               onStep,
               onChunk,
               onComplete,
```

---

### 3.3 文件二：`frontend/src/features/chat/services/sseParser.ts`

#### 修订点5：handlers 类型定义新增 `isStepDuplicate` 字段（line:74 后插入）

```diff
     saveStepsToStorage?: (steps: ExecutionStep[]) => void; // 【小强添加 2026-03-18】保存到 sessionStorage
+    isStepDuplicate?: (step: ExecutionStep, prev: ExecutionStep[]) => boolean; // 2026-09-09 小欧: 指纹去重, 防重连重放
     onStep?: (step: ExecutionStep) => void;
```

#### 修订点6：handlers 解构新增 `isStepDuplicate`（line:124 后插入）

```diff
     saveStepsToStorage,
+    isStepDuplicate,
     onStep,
     onChunk,
```

#### 修订点7：`case 'thought-start'` updater 加去重（line:255-256 之间插入）

```diff
         setExecutionSteps((prev) => {
+          // 2026-09-09 小欧: 指纹去重, 防重连重放导致重复追加
+          if (isStepDuplicate?.(ts, prev)) return prev;
           const next = [...prev, ts];
           handlers.executionStepsRef.current = next;
```

#### 修订点8：`case 'thought'` updater 加去重（line:380-381 之间插入）

```diff
         setExecutionSteps((prev) => {
+          // 2026-09-09 小欧: 指纹去重, 防重连重放导致重复追加
+          if (isStepDuplicate?.(step, prev)) return prev;
           const newSteps = [...prev, step];
           handlers.executionStepsRef.current = newSteps;
```

#### 修订点9：`case 'chunk'` updater 加去重（line:429-430 之间插入）

```diff
         setExecutionSteps((prev) => {
+          // 2026-09-09 小欧: 指纹去重, 防重连重放导致重复追加
+          if (isStepDuplicate?.(step, prev)) return prev;
           const newSteps = [...prev, step];
           handlers.executionStepsRef.current = newSteps;
```

#### 修订点10：`case 'final'` 直接 ref 赋值加去重（line:498-499 替换）

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

#### 修订点11：`case 'final'` updater 加去重（line:502-503 之间插入）

```diff
         setExecutionSteps((prev) => {
+          // 2026-09-09 小欧: 指纹去重, 防重连重放导致重复追加
+          if (isStepDuplicate?.(step, prev)) return prev;
           const newSteps = [...prev, step];
```

#### 修订点12：`case 'action'` updater 加去重（line:678-679 之间插入）

```diff
         setExecutionSteps((prev) => {
+          // 2026-09-09 小欧: 指纹去重, 防重连重放导致重复追加
+          if (isStepDuplicate?.(step, prev)) return prev;
           const newSteps = [...prev, step];
           handlers.executionStepsRef.current = newSteps;
```

#### 修订点13：`case 'observation'` updater 加去重（line:829-830 之间插入）

```diff
         setExecutionSteps((prev) => {
+          // 2026-09-09 小欧: 指纹去重, 防重连重放导致重复追加
+          if (isStepDuplicate?.(step, prev)) return prev;
           const newSteps = [...prev, step];
           handlers.executionStepsRef.current = newSteps;
```

#### 修订点14：`case 'paused'/'resumed'/'retrying'` updater 加去重（line:869-870 之间插入）

```diff
         setExecutionSteps((prev) => {
+          // 2026-09-09 小欧: 指纹去重, 防重连重放导致重复追加
+          if (isStepDuplicate?.(step, prev)) return prev;
           const newSteps = [...prev, step];
           handlers.executionStepsRef.current = newSteps;
```

---

## 四、编辑历史

| 日期 | 署名 | 修改目的和逻辑说明 |
|------|------|-------------------|
| 2026-09-09 | 小欧 | 初版：chunk/step重复显示根因分析+修复diff |
| 2026-09-09 | 小欧 | v1.1: 补充second漏洞final分支line499直接ref赋值绕过去重+8处全覆盖清单 |
| 2026-09-09 | 小欧 | v1.2: 重写第三章加完整调用链图拆分6子章节按执行顺序排列 |
| 2026-09-09 | 小欧 | v1.3: 全部修订点替换为真实diff代码, 删除所有伪代码和示意图, 14个修订点逐一标注行号 |
| 2026-09-09 | 小欧 | v1.4: 恢复v1.2调用链图放3.2节标注真实行号 |
