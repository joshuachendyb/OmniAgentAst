# 错误弹窗与 TaskInfoBar 计时器干扰问题——验证分析报告与解决方案

**版本**：v1.2
**编写人**：小欧
**编写时间**：2026-09-06 18:47:22（v1.0）｜2026-09-06 19:12:04（v1.1）｜2026-09-06 19:26:38（v1.2）
**状态**：R1 已实施并提交；R3 已按总原则定稿（北京老陈 2026-09-06 拍板），**审核稿待北京老陈审核后才动手**
**版本历史**：
- v1.0 2026-09-06 18:47:22 小欧：初版——B1/B3 实证、R1 最小修复、R3 弹窗收敛（A/B）方案
- v1.1 2026-09-06 19:12:04 小欧：R3 改为"后端业务错误 vs 前端连接错误"分道；纠正 v1.0 把两类错误混谈；
  按老陈裁定细化"可恢复错误不替换消息、不清计时"
- v1.2 2026-09-06 19:26:38 小欧：写入北京老陈总原则（前端错误只能弹窗 / 后端错误只进 taskinfo 显示）；
  核实后端 SSE error 事件实达值域=5 种、后端 final 错误本不经 onError；新增全套问题点清单·改动点·边界（审核稿）

---

## 一、问题背景与目标

北京老陈观察：前端页面**偶尔弹出小提示窗（错误提示）**，随后"实时页面出现奇怪情况"——
taskinfo 会话页面底部的任务信息条的那个**计数器（耗时 Ns）** 受干扰，且感觉**自动滚动**也受影响。

目标：用 case 实证"这些现象到底是不是真实 bug、有几种情况会发生"，并给出解决方案。

## 二、调查方法

1. **代码审查**：沿"弹窗（showMessage）→ 错误事件处理链"追出同源副作用，定位所有被该链路波及的
   状态（弹窗 / 消息列表 / waitTimer / liveErrorText / 徽标 badge / 任务列表）。
2. **case 实证**：针对候选问题写 vitest 取证测试，直接断言"当前真实行为"；测试通过 = 现象证实（bug 成立）。
3. 单一 case 单一 bug，结论可复现。

## 三、实证结果：真实 bug 清单

> 取证测试文件：`frontend/src/tests/reality/taskinfo-timer-error-bugs.test.tsx`（2 case）
> 运行：`cd frontend; npx vitest run src/tests/reality/taskinfo-timer-error-bugs.test.tsx`
> 结果：**2/2 全部通过 = 2 项 bug 实证成立**（2026-09-06 18:31 实测）

### 3.1 BUG-B1【真实发生 · 已实证】TaskInfoBar 耗时秒表：错误信号瞬时清零停表、恢复后回跳

| 项 | 内容 |
|---|---|
| 现象 | 任务执行中，"耗时 Ns"正常走表（0→1s）；任一错误信号到达（如模拟 `liveErrorText="工具执行失败"`）→ 耗时**立即清零（1s→0s）并停表**（推进 2s 仍为 0s）；业务恢复后**回跳显示累计值**（0s→4s，跳过了错误停表期） |
| 根因 | TaskInfoBar.tsx:74 秒表 interval 运行条件为 `receiving && info.badge==='running' && !detail`；而错误信号使徽标被拉成 `failed`（useTaskInfo.ts:90/195）→ interval 清理 + `setLiveElapsed(0)` + startRef 复位（TaskInfoBar.tsx:86-88）。恢复后重新锚定 start，跨越了停表期 → 数字跳变 |
| 证据 | case B1 `1→0→4` 时序断言通过 |
| 影响 | 任务中"耗时"显示不可信（停顿/清零/回跳），正是"计数器奇怪"的直接来源 |

### 3.2 BUG-B3【真实发生 · 已实证】一个 SSE 错误事件同源三通道副作用

| 项 | 内容 |
|---|---|
| 现象 | 一次 SSE 错误（case 用 `idle_timeout`）经 `useChatFacade.ts:169-183` 同源双发，**同时**触发：① 顶部弹窗（`handler.ts:740`，idle 为 warning 黄灯）② assistant 占位消息被整条替换成红字错误（useChatCallbacks.ts:525-568）③ 等待计时器被 `clearInterval` 清停、`waitTimerRef` 置 null、`setWaitTime(0)`，且**不重启**（useChatCallbacks.ts:572-577） |
| 根因 | 错误回调把"错误处理"与"任务状态清理"耦合在一起；消息层替换又造成滚动容器高度骤变 |
| 证据 | case B3 三通道断言全部通过 |
| 影响 | 用户观感"一个错 弹窗+列表红字+计时消失"三处同时动、内容高度骤变 → 结合 B1 即"页面奇怪"全貌 |

## 四、候选但未列入"已实证 bug"的项目（如实说明）

| 候选 | 判定 | 说明 |
|---|---|---|
| 自动滚动失效 | **未实证（待 E2E）** | 单测环境 ResizeObserver 为 mock 空实现（setup.ts:19），无法稳定复现滚动。静态分析：弹窗为 fixed 浮层不占文档流、不直接影响滚动容器；滚动观感变化的次要来源是 B3"内容替换→容器高度骤变 / receiving 停止→无新内容"。**建议 E2E 实测确认后再定** |
| 60s 空闲超时自动弹窗+重连 | **设计如此，非回归** | useSSE.ts:625-637 确实会在 60s 无数据时触发 `onError`（本报告 B3 正是用该错误类型实证的弹窗通道）＋ `reconnect()`；HITL 等待期（paused）已有 P1-3 豁免。长 LLM 思考/长工具执行仍可能撞上，严重度待老陈评估 |

## 五、因果链总图（一条错误 → 六处副作用，其中两条已实证）

```
任务执行中，任一 SSE 错误 / 工具错误 / 空闲超时
        │  (useChatFacade.ts:169-183 同源双发)
        ├─► ① 弹窗 toast               (handler.ts:740  warning)      ← B3 [实证]
        ├─► ② assistant 占位被替换成红字 (useChatCallbacks.ts:525)      ← B3 [实证]
        ├─► ③ waitTimer 清停不重启       (useChatCallbacks.ts:572)      ← B3 [实证]
        ├─► ④ liveErrorText → taskinfo位4🛑  (ChatPage.tsx:40)          ← B1 素材
        ├─► ⑤ badge→failed → 秒表清零停表 (useTaskInfo.ts:90→TaskInfoBar.tsx:74)  ← B1 [实证]
        └─► ⑥ refreshTasks 重拉左栏     (ChatPage.tsx:136)              ← 设计行为
```

## 六、解决方案

### 6.1 R1【推荐，最小改动，止损 B1】秒表与徽标解耦

**问题本质**：秒表（"是否在实时走表"）绑定了徽标（"当前任务成败"）这两个**不同维度**的语义。

**修法（直线，符合 KISS-DIRECT）**：
- TaskInfoBar.tsx:73-89 秒表 interval 运行条件去掉 `info.badge === 'running'`，改为
  `receiving && !detail`（只要实时流还在收数据就继续走表；徽标只管显示）。
- `setLiveElapsed(0)` 与 startRef 复位只在"流停止（receiving 变 false）或切入历史（detail）"时发生。
- 效果：错误可恢复后再无 1→0→4 跳变；任务真正结束时（receiving 断开）照常归位。

**影响面**：仅 TaskInfoBar 内部，不碰徽标派生（useTaskInfo 保持现状，避免回归面），改动 ≤10 行。

### 6.2 R3【v1.1 注记：本方案已作废，取代为 6.3 双通道分道】收敛弹窗（旧版 A/B）

- 选项 A：保持现状（可恢复错误也弹 warning）——改动最小。
- 选项 B：工具类可恢复错误**不弹窗**，只保留 taskinfo 位4🛑/红字（错误"详情"留在列表与位4），
  仅终态/致命错误弹窗。涉及 handler.ts 分类与 showMessage 调用点筛选，改动中等。
- 说明：v1.0 判断有误——把"后端业务错误"与"前端连接错误"混在一个弹窗判断里设计（该混淆已由北京老陈指出）。

### 6.3 R3 分道方案【v1.1 定稿，北京老陈 2026-09-06 认可】

#### 6.3.1 错误源全景输入（v1.2 核实，按总原则划分）

**总原则（北京老陈 2026-09-06 拍板）**：前端自己的错误**只能弹窗**提示；后端的错误**只进 taskinfo 那些显示**、不弹窗。

| 通道 | 来源（前端 onError 实达值域） | 语义 | 处理归属 | 是否弹窗 |
|---|---|---|---|---|
| **A1 后端业务 · 可恢复**（任务继续） | SSE error 事件 `error_type`∈{invalid_action, blocked, timeout} | "工具有小波折，任务继续" | 只位4 🛑；**不替换消息、不清 waitTimer** | **不弹窗** |
| **A2 后端业务 · 终态**（任务已 failed） | SSE error 事件 `error_type`∈{empty_response, chunk_buffer_timeout} | "任务以失败收场" | 消息红字 + 位4 + 徽标；waitTimer 清停（任务已结束） | **不弹窗** |
| **B 前端连接错误** | useSSE 空闲超时(:633) / 无任务ID重连失败(:776) / 重连耗尽等 handler 类 | "前端到后端的管道问题" | 前端错误中心 classifyError → showMessage 弹窗 | **弹窗（总原则：只能弹）** |

> **v1.2 核实**：后端 `final` 事件错误（same_tool_loop / recoverable_retry_exhausted / agent_operation_error /
> unknown_response / quota_exceeded / rate_limit / 后端 LLM 空闲超时）一律走 `onComplete` final 分支
> （sseParser.ts:398-475），**不经 onError、本就不弹窗**——不在本次改动范围，仅文档确认。
> 后端 SSE error 事件全集已穷举 = **上述 5 种**（MetaStep(type="error") 源头：react_step.py:364/331、safety_gate.py:82/125、
> sandbox_gate.py:99、react_loop.py:223）。

#### 6.3.2 现状错点（证据）

1. `useChatCallbacks.ts:507` 把两类错误**不加区分**全部丢进 `handleSSEError`（前端错误中心）→ 业务错误也被"弹窗引擎"处理。
2. `classifyError`（handler.ts:894-914）**不识别后端业务 error_type**：白名单仅 empty_response/timeout/network/server 四例，
   blocked / user_rejected / chunk_buffer_timeout / same_tool_loop 等全部兜底 `ErrorType.UNKNOWN` →
   任务中工具被安全拦截（blocked，任务继续）会误弹"发生未知错误"toast。
3. 结果：一个业务错误既走业务通道（②④）,又被误送前端通道弹一次 toast，观感"三通道同时报同一个错"。

#### 6.3.3 修改方法（纯前端 3 文件，不动后端）

1. **types/sse.ts**：`SSEError` 接口加可选字段 `from_backend?: boolean`（错误构造来源标记：后端业务错误=true）。
2. **sseParser.ts** error case（:537 构造 SSEError 处）：业务错误带 `from_backend: true`。
3. **useChatCallbacks.ts** `onError`（:507 附近）：按 `errorObj.from_backend` + `error_type` 三分支——
   - **A1 可恢复业务错误**（from_backend=true 且 error_type∈RECOVERABLE 集合）：**零副作用前端化**——
     不调 handleSSEError（不弹窗）、不替换消息②、不清 waitTimer③；错误信息经 liveErrorText 仅位4🛑④（facade 双发），
     badge 短暂 failed 后由 useTaskInfo `_badgeRecovered` 自愈回 running。
   - **A2 终态业务错误**（from_backend=true 且不在 RECOVERABLE）：跳过 handleSSEError（**仍然不弹窗**），
     保留消息替换② + 位4④ + 徽标 + waitTimer 清停（任务已终止，清计时正确）。
   - **B 前端连接错误**（from_backend 为空/false）：维持现状走 handleSSEError → 弹窗① + 消息红字② + 清计时③。
4. **handler.ts / useSSE.ts 不改**：前端连接错误的弹窗闭环不动；classifyError 不受影响。
5. 位4/liveErrorText 保持双来源都发（业务与连接都属"实时错误"，taskinfo 均应显示）。

#### 6.3.4 影响面与风险

- 界面行为变化：
  - **可恢复业务错误（blocked / timeout / invalid_action）**：不再弹 toast、不再替换播放中的消息、计时不停——
    错误文字持续显示在 taskinfo 位4🛑（直到下次发消息/切会话清除，比 5s toast 更持久且不打断操作）。
  - **终态业务错误（empty_response / chunk_buffer_timeout）**：不再弹 toast；错误改由 ②消息红字 + ④位4🛑 页面内呈现。
  - 前端连接错误（前端空闲超时/重连失败等）行为**不变**，仍弹窗（总原则：前端错误只能弹窗）。
- 后端零改动、零回归面。风险低；由取证 case 锁定三条分支。

#### 6.3.5 验收

- 取证 case（`taskinfo-timer-error-bugs.test.tsx` 扩展）：业务可恢复错误（blocked）→ 弹窗 **不**被调用、
  消息 **不**替换、waitTimer **不清**停；业务终态错误（empty_response）→ 弹窗不调用、消息替换发生；
  前端连接错误（idle_timeout）→ 弹窗被调用（现 B3 即此例，保持绿）。
- `npm run check`、`npx tsc --noEmit` 清 0；相关 reality 取证合集复查。

### 6.4 记录项（本次不动）

- **waitTime 目前无 UI 消费点**（grep 剧本：仅 types/state/hooks 内部流转，无组件显示）→ R2（waitTimer 影响）
  实际影响面≈0，不列入修复；若未来要展示"等待秒数"，需另立任务。
- badge 被实时错误信号污染成 failed（useTaskInfo.ts:90/195）——P6 已用 _badgeRecovered 补偿，
  R1 已绕过对秒表的影响；徽标语义是否重构另行评估，本次不扩展改动。

## 七、错误源全景（v1.2 核实，绝无遗漏）

> 前端 `onError` 是"会弹窗那条链"的唯一入口。以下穷举**所有**进 onError 的错误来源。

### 7.1 后端业务错误（SSE error 事件，MetaStep(type="error")）

穷举全部源头，**共 5 种**，同一构造入口 sseParser.ts:537：

| error_type | 后端发射点 | 任务状态 | 归类 |
|---|---|---|---|
| empty_response | react_step.py:364 + set_failed | 已 FAILED | **A2 终态** |
| chunk_buffer_timeout | react_loop.py:223 + set_failed | 已 FAILED | **A2 终态** |
| invalid_action | handle_action.py:331（tool_name 空） | 循环继续 | **A1 可恢复** |
| blocked | safety_gate.py:82 / sandbox_gate.py:99（安全拦截） | 循环继续 | **A1 可恢复** |
| timeout | safety_gate.py:125（工具确认超时） | 循环继续 | **A1 可恢复** |

### 7.2 后端 final 事件错误（本就不经 onError，无改动）

`final` 分支走 onComplete（sseParser.ts:398-475），不触弹窗链。全部列出以备复核：
same_tool_loop（react_step.py:473-480）、recoverable_retry_exhausted（react_loop.py:170-178/205-213）、
agent_operation_error（agent_runner.py:443/477）、unknown_response（handle_answer.py:104-107）、
LLM 流式错误 quota_exceeded/rate_limit/idle_timeout/client 等（llm_call.py:228 直放行 → handle_answer error 分支
→ FinalStep failed，handle_answer.py:80-92）。

### 7.3 前端连接错误（useSSE / handler 构造，本就走弹窗）

| 来源 | 构造点 | 形态 |
|---|---|---|
| 60s 空闲超时 | useSSE.ts:633 `onError?.('SSE 空闲超时...')` | string → 前端错误 |
| 首次响应未到重连失败 | useSSE.ts:776 handleSSEError(idle_timeout) | 前端错误 |
| 重连耗尽/连接失败 | useSSE.ts:799+ handleSSEError | 前端错误 |

## 八、问题点清单 · 改动点 · 边界（审核稿）

### 8.1 问题点清单（共 14 点，全核实）

| # | 问题点 | 结论 |
|---|---|---|
| Q1 | 后端错误与前端错误如何区分 | SSE error 构造点 sseParser.ts:537 打 `from_backend:true`；其余 onError 来源（useSSE 空闲/重连失败）为空 → 前端连接错误 |
| Q2 | 打标点唯一性 | 是——前端 onError 的数据源仅 sseParser:537 一处 + useSSE 两处字符串/对象构造 |
| Q3 | A1 可恢复错误（invalid_action/blocked/timeout） | 不弹窗、不替换消息、waitTimer/loading 不动，错误仅位4 |
| Q4 | A2 终态错误（empty_response/chunk_buffer_timeout） | 不弹窗；保留消息替换红字 + waitTimer 清停 + 位4 |
| Q5 | 前端连接错误 | 照旧弹窗（总原则"只能弹"），行为零变化 |
| Q6 | 后端 final 错误 | 走 onComplete、不经 onError、本就不弹窗 → 无改动 |
| Q7 | 字符串型错误（useSSE:633 传 string） | from_backend 为空 → 判前端错误 → 弹窗，语义正确 |
| Q8 | 位4/liveErrorText | facade 双发透传不动，两类错误都显示到 taskinfo（符合"后端错误进 taskinfo"） |
| Q9 | badge 短暂 failed | useTaskInfo `_badgeRecovered` 自愈回 running（既有行为，不动） |
| Q10 | waitTimer/loading 语义 | 可恢复错误不动（任务继续）；终态/前端错误清停（任务结束）——与任务状态严格对应 |
| Q11 | B2 被拒工具灰字点名条 | 独立机制（onDenied/deniedEntries），不占 error 通道，不动 |
| Q12 | classifyError / handler.ts | 弹窗引擎原样保留，仅改变"什么进弹窗引擎"的入口判断 |
| Q13 | R1 秒表 | 已修复提交 `a3d7a38a0`，与 R3 正交 |
| Q14 | 旧错误对象兼容 | 无 from_backend 字段 → 默认前端连接错误 → 弹窗（保守不吞错） |

### 8.2 改动点（纯前端 3 文件，后端零改动）

1. **types/sse.ts:89-91** `SSEError` 加可选 `from_backend?: boolean`（已加字段，工作区未提交，待审）。
2. **sseParser.ts:537** 构造 SSEError 加 `from_backend: true`（一行）。注释注明 R3 用途。
3. **useChatCallbacks.ts**：
   - 模块级常量 `RECOVERABLE_SSE_ERROR_TYPES = new Set(['invalid_action', 'blocked', 'timeout'])`。
   - `onError`（:506 起）在 handleSSEError 之前插入分道：A1（from_backend=true 且 ∈RECOVERABLE）→ 清理 3 个 streaming ref 后直接 return；
     A2（from_backend=true 否则）→ `errorResult = { handled: true }` 跳过弹窗引擎，其余终态处理不变；
     B（无标记）→ 现状原样。

### 8.3 边界与禁区

- **不改**：handler.ts、useSSE.ts、useChatFacade.ts、useTaskInfo.ts、TaskInfoBar.ts（R1 已完）、RightViewer、B2 灰字点名。
- **不新增**事件类型、不改后端、不碰 SSE 协议字段语义（from_backend 仅前端内部标记）。
- 不改 B3 已实证的前端 idle_timeout 弹窗行为（那是总原则下"前端错误只能弹窗"的正确示例）。

### 8.4 风险与缓解

| 风险 | 缓解 |
|---|---|
| 后端将来新增 error 事件类型 | 未打标突变 → 走 A2 终态分支（替换+清计时+不弹窗），与"后端错误不弹窗"总原则一致 |
| RECOVERABLE 静态集合未来失配 | 若后端 new error_type 且属可恢复，会按 A2 处理（替换+清计时）——最坏是终态呈现，仍不弹窗，可接受 |
| 可恢复错误位4 + badge 短暂红色 | `_badgeRecovered` 自愈（P6 已裁决），R1 已保证秒表不再受 badge 影响 |

### 8.5 验收（取证 case，本地不 commit）

- **新增 C1** blocked（业务可恢复）→ 断言：handleSSEError 不被调用（不弹窗）、setMessages 不被调用（不替换）、
  waitTimerRef 保持非空（不清计时）。
- **新增 C2** empty_response（业务终态）→ 断言：handleSSEError 不被调用（不弹窗）、setMessages 被调用（替换红字）、
  waitTimer 被清理。
- **保持 B3** idle_timeout（前端连接）→ 弹窗被调用、替换、清计时（现状，总原则正确基线）。
- `npm run check`、`npx tsc --noEmit` 清 0；taskinfo reality 取证 / 引用 TaskInfoBar 单元测试全绿。

## 九、落地步骤与验收

1. 【✅ 已完成】R1 秒表与徽标解耦（6.1）——提交 `a3d7a38a0`（fix）+ `65634c40d`（docs）。
2. 【⏸ 审核后】R3 分道（8.2 三处改动）——北京老陈审核 8 章后放行再实施。提交：
   `fix:error 后端业务错误与前端连接错误分道-R3(后端错误只进taskinfo不弹窗) - 小欧-2026-09-06`。
3. 【⏳ 待批】文档二次提交（本 v1.2 审核稿）→ 审核通过后并入提交。

## 十、附录

- 取证测试：`frontend/src/tests/reality/taskinfo-timer-error-bugs.test.tsx`（本地运行，不 commit）
- 关键证据行号：
  - TaskInfoBar.tsx:74（秒表条件）、:86-88（清零/复位）——R1 已修
  - useTaskInfo.ts:90、:188-196（徽标被错误信号拉 failed）
  - useChatFacade.ts:169-183（同源双发，liveErrorText 透传）
  - useChatCallbacks.ts:507（两类错误混送 handleSSEError，分道改此）、:525-577（消息替换 + waitTimer 清停）
  - handler.ts:731-758（弹窗分类）、:894-914（classifyError 白名单仅 4 例，blocked 兜底 UNKNOWN）
  - sseParser.ts:398-475（final 事件走 onComplete、不经 onError）、:537（SSEError 构造点，打标处）
  - useSSE.ts:633（前端 60s 空闲超时 onError 弹窗）、:776/799+（重连失败 handleSSEError）
  - 后端：react_step.py:364/473、react_loop.py:223/174、123、handle_action.py:331、safety_gate.py:82/125、
    sandbox_gate.py:99、handle_answer.py:80-107、llm_call.py:228、agent_runner.py:443/477