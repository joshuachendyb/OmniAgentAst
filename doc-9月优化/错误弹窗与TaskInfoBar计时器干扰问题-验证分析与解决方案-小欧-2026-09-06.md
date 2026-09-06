# 错误弹窗与 TaskInfoBar 计时器干扰问题——验证分析报告与解决方案

**版本**：v1.0
**编写人**：小欧
**编写时间**：2026-09-06 18:47:22
**状态**：实证完成（vitest case 全部通过=bug 证实），方案待北京老陈裁定

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

### 6.2 R3【待老陈裁定 UI 语义】弹窗收敛

- 选项 A：保持现状（可恢复错误也弹 warning）——改动最小。
- 选项 B：工具类可恢复错误**不弹窗**，只保留 taskinfo 位4🛑/红字（错误"详情"留在列表与位4），
  仅终态/致命错误弹窗。涉及 handler.ts 分类与 showMessage 调用点筛选，改动中等。
- 说明：这属于"什么时候该打扰用户"的产品语义，**建议老陈拍板后再动**。

### 6.3 记录项（本次不动）

- **waitTime 目前无 UI 消费点**（grep 剧本：仅 types/state/hooks 内部流转，无组件显示）→ R2（waitTimer 影响）
  实际影响面≈0，不列入修复；若未来要展示"等待秒数"，需另立任务。
- badge 被实时错误信号污染成 failed（useTaskInfo.ts:90/195）——P6 已用 _badgeRecovered 补偿，
  R1 已绕过对秒表的影响；徽标语义是否重构另行评估，本次不扩展改动。

## 七、落地步骤与验收

1. 老陈裁定：R1 是否执行、R3 选 A 还是 B。
2. 执行 R1 修复（分提交：`fix:TaskInfoBar 秒表与徽标解耦...`，前后端独立提交格式）。
3. 验收：翻转 B1 取证断言为"期望正确行为"→ 修复后应转绿；`npm run check`、`npx tsc --noEmit` 清 0；
   相关 reality 取证合集复查。
4. 若 R3 选 B，另立小提交并补弹窗过滤取证 case。

## 八、附录

- 取证测试：`frontend/src/tests/reality/taskinfo-timer-error-bugs.test.tsx`（本地运行，不 commit）
- 关键证据行号：
  - TaskInfoBar.tsx:74（秒表条件）、:86-88（清零/复位）
  - useTaskInfo.ts:90、:188-196（徽标被错误信号拉 failed）
  - useChatFacade.ts:169-183（同源双发）
  - useChatCallbacks.ts:525-577（消息替换 + waitTimer 清停）
  - handler.ts:731-758（弹窗分类，warning/critical/info）
  - useSSE.ts:625-637（60s 空闲超时 onError+reconnect）