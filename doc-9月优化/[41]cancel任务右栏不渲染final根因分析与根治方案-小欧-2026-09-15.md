# [41] cancel任务右栏不渲染final根因分析与根治方案

**文档类型**: 分析设计（编辑型）
**文件名**: [41]cancel任务右栏不渲染final根因分析与根治方案-小欧-2026-09-15.md
**创建时间**: 2026-09-15 06:31:43

## 版本历史

| 版本 | 更新时间 | 更新人 | 修改简介 |
|------|---------|--------|---------|
| v1.0 | 2026-09-15 06:31:43 | 小欧 | 创建：cancel任务右栏不渲染final根因分析＋根治方案（产帧权前移＋SSE通道完整） |
| v1.1 | 2026-09-15 06:44:34 | 小欧 | 三思三省重大修订：废除"受理点产帧B1-B4"方案（帧序错乱，违反final最后事件不变式）；根治改为纯前端"对齐正常路径"（删3s赌注＋删强制断连），后端零改动。本文档于 06:44:34 定稿 |
| v1.2 | 2026-09-15 08:26:35 | 小欧 | 撤销v1.1删除动作盘点三漏洞＋选项B决策：G1残留finally无条件复位令S6闸提前失效（晚到帧仍污染）；G2 onComplete A5守卫时序·选项B经F3在onStep复位后自然放行零额外改动；G3取消失败/无taskId路径复位缺失须显式兜底；G4极端终态帧永不达须executeSend起点兜底复位。修改点F1-F4，本文档于 08:26:35 二次定稿 |
| v1.3 | 2026-09-15 13:35:02 | 小欧 | 撤撤选项A、采信选项B＝现状零改动：左栏消息条取消文案显示维持现状（现码已在此写取消文案，更像error，零删除）；后端零改动重申（cancel_terminal_text恒非空，取消终态与error同链路帧序天然正确）；仅保留右侧根治 F1-F5（删病根断连＋复位点唯一化＋executeSend兜底）。本次文档修订于 13:35:02 定稿 |

## 〇、v1.1 三思三省结论（重大修订声明）

v1.0 的根治方案（B1-B4 产帧权前移）经三思三省被**否决**，理由（代码级证据）：

| # | 三省质疑 | 结论（证据） |
|---|---------|-------------|
| 1 | 受理点产帧时 agent 循环可能仍在跑工具 | 工具结束后 `_process_single_step` 仍会 emit observation/action（react_loop.py:232-233）经 `_publish` 排在 final **之后** → event_log 变 [..., final, observation, ...] |
| 2 | 是否破坏"final 为最后事件"不变式 | 破坏。DB 由 agent_runner.py:402 按 `list(buffer.event_log)` 顺序落库，帧序一旦错乱，DB step 序号与前端步骤序全乱 |
| 3 | 与既有选型是否冲突 | 冲突。react_loop.py:190-200 明示选方案B（循环粒度取消，不打断流式中途），正是为避免打断在飞工具/LLM；受理产帧=变相方案A，被明确否决 |
| 4 | 后端产帧序是否本已正确 | 正确。D/C 路径 final 必为循环顶检出后 emit+break 的最后动作，顺序天然为 [业务帧..., final] |
| 5 | 真正病根在前端还是后端 | 前端。正常/error 路径从不强制断连，SSE 保持，final 必达；唯 cancel 独有"3s 等待赌注 + 超时强制 disconnect" |

**修订后根治 = 纯前端"对齐正常路径"**：删掉取消独有的 3s 赌注与强制断连，让 `final+cancelled` 像正常终态一样经既有 SSE→sseParser→快照→渲染链路自然到达。后端零改动，不新增任何机制（复用 final 同步冲刷/快照 effect/终态渲染/hasFinalStats 全部既有环节）。

### 〇.5 四项缺口核查与选项A/B决策（v1.2 三思三省二次复核，代码级证据闭环）

v1.1 定稿后在撤回删除动作的逐环三思三省中，又揪出 4 项**代码级缺口**（G1-G4），并在"取消失败文案写不写左栏消息条"上与北京老陈当面拍板选项A/B。v1.2 定 选项B，v1.3 撤选项A、采信选项B＝现状零改动（左栏维持现码取消文案显示、后端零改动）。逐项落证如下：

| # | 缺口 | 代码证据 | 影响 | 本文档处置 |
|---|------|---------|------|-----------|
| G1 | `cancelInProgressRef` 复位点与 S6 闸时序冲突 | v1.1 主旨是"收到取消终态帧处（onStep isCancelEvent 分支）复位闸再自然放行"。但 `useChatTaskControl.ts:282-285` **handleCancel 的 finally 仍无条件 `cancelInProgressRef.current=false`**——取消 API 毫秒返回后闸即刻解，S6 拒绝闸（useChatCallbacks.ts:205-212）在取消窗口期**提前失效**，晚到 observation/action 帧仍被放行进右栏 → v1.1 的 S6 闸形同虚设 | 取消后晚到业务帧仍污染右栏（冻结复现） | **选项B 附带**：删除 handleCancel finally 的无条件复位（:284），改由"收到取消终态帧处"唯一复位（于 §4.4-### 4.4 补 F4'） |
| G2 | onComplete A5 守卫与"左栏消息条写不写取消文案"二选一 | `useChatCallbacks.ts:367` A5：`if (cancelInProgressRef.current) return` —— 取消窗口期 onComplete 被 A5 早退，**左栏消息条不写 final 文案**（只剩右栏取消终态）；若想左栏也写"任务已取消"，需 A5 放行且由 onComplete 正常完成路径写入 | 取消后左栏消息条是否显示取消终态文案，此前无明确定论 | **定 选项B**：左栏消息条也写"任务已取消"文案——经 G1 复位点改为"收到取消终态帧处"后，onComplete A5 读到 `cancelInProgressRef=false` 自然放行 → 走 `cancel_terminal_text`（恒非空，task_runtime.py:76-93）→ 正常 setMessages 写文案。**零额外 onComplete 改动，选项B 由 F3 复位点前移天然达成**。（v1.3 补注：撤选项A、采信选项B＝现状零改动，左栏维持现码显示，后端零改动） |
| G3 | 取消失败/无 taskId 路径复位缺失 | v1.1 F4 未覆盖 `handleCancel` 无 taskId 分支 / 取消失败 catch 分支（useChatTaskControl.ts:257-281）——这些路径不产取消终态帧，闸永不复位 → S6 永锁 → 新消息全被过滤 | 取消失败后前端永久冻结 | F4' 兜底：无 taskId/失败分支显式 `cancelInProgressRef.current=false`（§4.4 补 F4'） |
| G4 | executeSend 新消息起点兜底复位缺失 | SSE 极端异常下取消终态帧永不达（见 §七 风险表"后端取消终态自然发射延迟窗口"）→ 闸永不复位 | 极端取消终态帧丢失时闸永锁、新任务卡死 | **F5（v1.2）**：`executeSend`（useChatStreaming.ts:368 前）新消息起点复位 `cancelInProgressRef=false`，对"取消终态帧永不达"兜底，确保新消息必达（§4.4 补 F5） |

**修正后根治 = v1.1 三处（F1-F3）＋ v1.2 补两处（F4' 复位点唯一化迁址＋F5 executeSend 起点兜底）＋ 选项B＝现状零改动（左栏消息条现码已写取消文案，零后端、零 onComplete、零删除）**：撤选项A、后端零改动、前端顺应既有链路的三思三省删除纪律不变。

---

## 一、问题现象

实时任务点击"取消"后，后端已正确下发 `final(outcome=cancelled)` 终态帧（且 DB 落库成功、左侧任务条取消徽标正常），但**右栏 step 面板在"取消前最后一步"处冻结**，始终不出现取消终态（"! 取消来源: user_requested"橘红条），面板表现为永久停在执行中状态，必须刷新或切换会话才恢复。

正常完成任务 / 失败任务均正常渲染终态，唯独"用户取消"异常。

## 二、链路契约（先立规再定案）

取消失败/取消终态的唯一权威信号（铁律）：

- 后端取消终态 = `type=final + outcome=cancelled`，无独立 `cancelled` 事件（4.4.1，前端 `case 'cancelled'` 已删，2026-09-07）。
- 终态帧字段：`final.to_dict()` 含 `type/outcome/response/cancel_source/error_type/error_message/seq/...`（2026-09-14 已删 `content` 改 `response`，前端 sseParser final 分支只读 `response`）。
- 前端渲染终态的唯一前提 = `executionSteps` 里**出现一条 golden 的 `final` 帧** → `hasFinal=true` → `isCurrentLive=false` → PipelineRenderer 平铺终态段。
- 后端每次任务结束（含取消）必发 `final_stats`（agent_runner finally，DB落库信号，[33] B16），取消必然有 `final_stats`。

## 三、根因逐环剖析（代码级证据）

### 3.1 前端取消时序（useChatTaskControl.ts）

`handleCancel`（:198-289）真实执行序：

```
callCancelApi(taskId, sessionId)      # REST POST /cancel，后端受理
→ waitForCancelOrTimeout()            # = Promise.race[ waitForCancelEvent(3000,200), timeout(5000) ]
→ resetUiFlags()                       # 清 loading/paused/receiving（不碰 steps）
→ disconnect(true, true)               # :227 强制断连 SSE = AbortController.abort()
→ showTaskResultMessage('cancel', ...)
```

关键死代码事实（:180-186）：`waitForCancelEvent(3000,200)` 3 秒轮询 `hasReceivedCancelEventRef`，**必然先于 5 秒硬超时 resolve**（3s < 5s）。所以实际"取消确认等待窗口"只有 **3 秒**，5s 超时分支永不触发 —— 死代码。

### 3.2 跨层时序对决（病根）

| 环节 | 耗时特征 |
|------|---------|
| 前端 cancel API 请求→后端受理 | 毫秒级（REST 独立于 SSE） |
| 后端受理→**终态帧发射** | **依赖 agent 循环进度**（不可控，数秒级） |
| 前端 3s 等待窗口 | 固定 3 秒 |

后端终态发射为何不可控？`cancel_task`（task_runtime.py:95-122）受理时只做三件事：

1. `set_cancelled(...)` 写 cancelled 标志；
2. `agent._cancel_source = source` 写回来源；
3. `ai_service.cancel()` 关闭 LLM HTTP 连接。

随后**立即返回**，**不产任何终态帧**。真正的 `final(outcome=cancelled)` 要在"agent 循环自然推进到取消检出点"时才发：

- **D 路径**（react_loop.py:203-219）：循环顶 `check_cancelled()` 命中才 `final` emit。若当前 LLM 长生成 / 工具长执行，检出延迟 = 该步剩余耗时（数十秒级）。
- **C 路径**（handle_answer.py:100-130）：LLM 流被打断抛 `err_type=="cancelled"` 才 `final` emit，仅当取消发生在 LLM 流期间才走此路。

于是：**3 秒（前端硬等） < 后端终态发射延迟（不可控） → 前端必然先走过窗口。**

### 3.3 强制断连掐死唯一通道（直接丢帧点）

3 秒到点后 `disconnect(true, true)`（useChatTaskControl.ts:227）：

- `force=true` → `manualDisconnect=true`（禁止自动重连）；
- 内部 `abortController.abort()` 掐断 SSE 连接；
- useSSE catch 分支按 `intentionalAbort` **静默短路**（useSSE.ts:661-724）——连接已死，后续帧无从接收。

后端晚到的 `final+cancelled` 帧写入已死连接，永远进不了 `sseParser` → `executionSteps` 无 final。

> 这正解释了"为何独 cancel 异常、正常/error 正常"：正常/error 路径前端**从不强制断连**，SSE 链路完好，final 必达；唯 cancel 路径存在"3s 窗口 + 强断连"这个独有动作组合。

### 3.4 冻结公式（症状触发器，已验证）

无 final → `hasFinal=false` → 视图态推导 `isCurrentLive = activeTaskId===serverTaskId && (hasFinal ? false : 有业务步骤) = true`（恒 live）→

- `RightViewer`（:348）REST 兜底 effect 首行 `if (!activeTaskId || isCurrentLive) return` 被挡，**自愈失效**；
- `PipelineRenderer`（:355）`if (streaming) return null` 恒真，**终态段永不渲染**（:360-383 的取消橘红条只在 replay 模式出）；
- 面板冻结在执行轮。

### 3.5 根因结论（一句话）

> **前端取消流程用"3s 短等待 + 超时强制 disconnect"来赌后端终态帧，而后端终态帧的发射却绑定 agent 循环进度（不可控）——3s 必输，断连又掐死了唯一承载终态帧的 SSE 通道，终态帧被丢，前端因 `if (streaming) return null` 永不渲染 final 而冻结。**

本质：**取消终态帧的到达依赖了时序赌注（前端等待 vs 后端循环进度），赌输即丢帧**。

## 四、根治方案（v1.1：纯前端对齐正常路径，后端零改动，零新增机制）

### 4.1 总体设计（KISS-DIRECT：把取消路径改造成与正常路径逐字节同构）

正常完成/失败任务为何从不丢 final？——**前端从不主动掐断 SSE**。取消路径的病根恰是其独有的"3s 等待赌注 + 超时强制 disconnect"。根治 = 删掉这两个独有动作，使取消后的链路与正常终态路径**完全一致**：

```
（修改前·取消）
callCancelApi → waitForCancelOrTimeout(3s赌注) → disconnect(true,true)(掐流) → [final此后到达，丢]

（修改后·取消=正常路径）
callCancelApi → resetUiFlags(即时反馈) → 不断连、不等待，SSE 保持
→ 后端循环顶/LLM流终态(final+cancelled)经既有 SSE 链路自然到达
→ sseParser 同步冲刷入 executionSteps(type=final,outcome=cancelled)
→ hasFinal=true → isCurrentLive=false → 快照 effect 定格 settledSteps → 终态渲染
→ final_stats → done → SSE 自然关闭
```

关键点：**修改后取消链路每一步都复用正常终态路径的既有机制**（sseParser 同步冲刷 sseParser.ts:528-531、快照 effect RightViewer.tsx:254-264、终态三段渲染 PipelineRenderer.tsx:360-383、hasFinalStats→onSettledRefresh RightViewer.tsx:425-430），后端 D/C 两路径产帧序天然正确（final 为循环顶检出后 emit+break 的最后动作），DB/前端/SSE 落点全不变。

### 4.2 前端修改（三处，全部是"删除独有错误动作 + 补齐一个复位点"）

**4.2.1 删除死代码（useChatTaskControl.ts）**：

- 删 `waitForCancelEvent`（:128-150）—— 3s 轮询，正是"时序赌注"本体；
- 删 `waitForCancelOrTimeout`（:180-186）—— 内含 5s 硬超时；因 3s 轮询必然先 resolve，5s 分支本就是死代码（小强 2026-08-28 #15 引入的"防永久挂起"兜底，实际从未生效且制造了 3s 赌注）。

**4.2.2 `handleCancel` 成功路径删强制断连（:198-289）**：

```
修改前：callCancelApi → await waitForCancelOrTimeout() → disconnect(true, true, 复位hasReceivedCancelEventRef) → showTaskResultMessage
修改后：callCancelApi → resetUiFlags（保留，即时 UI 反馈）→ showTaskResultMessage（'cancel', result.message）
       取消确认由 SSE 自然流到达的 final+cancelled 承载，前端不再主动 disconnect。
```

- resetUiFlags（:213/:157）保留——取消点击即刻清 loading/paused/receiving，用户立即得到反馈；
- 删除 :219 `await waitForCancelOrTimeout()`、:227 `disconnect(true, true, callback)`；
- `hasReceivedCancelEventRef` 复位不再依赖 disconnect 回调，改由收到终态帧处自然管理（见 4.2.3）。

**4.2.3 补一个复位点：`cancelInProgressRef` 复位时机对齐"收到取消终态帧"**：

`cancelInProgressRef` 是取消期间过滤非取消帧的闸（S6，useChatCallbacks.ts:197-212：取消中只放行 `final+outcome=cancelled`）。原实现依赖 handleCancel 的 `disconnect`/finally 复位（:284）。

修改后断连动作删除，复位点改到**收到取消终态帧处**（useChatCallbacks.ts onStep `isCancelEvent` 分支 :197-201）：

```
isCancelEvent(true) → hasReceivedCancelEventRef.current = true
                     → cancelInProgressRef.current = false   # 新增: 闸解得, 后续帧(观察/后续任务)自然放行
```

同步需保证：收到 `final+cancelled` 后 SSE 仍继续收到 final_stats→done→onComplete（既有复位清闸逻辑不变，onComplete 会清 cancelInProgressRef 依赖的上下文，行为自然）。

### 4.3 为什么这是根治而非临时方案（对照审查）

| 对照项 | 临时方案（自愈兜底/回填/REST补拉） | 本根治方案（v1.1） |
|--------|----------------------------------|-------------------|
| 对病根动作 | 不动"3s赌注+强断连"，绕道事后补救 | 直接删除病根动作（赌注＋断连都不存在了） |
| 机制数量 | 新增回填/定时器/旁路 REST 机制（YAGNI 违例） | 零新增机制，取消路径逐字节对齐正常路径（复用既有全部环节） |
| 时序语义 | 仍依赖赌局，赌输靠补救 | 零赌注：final 沿 SSE 自然必达（与正常终态同构） |
| 回归风险 | 新机制引入新 bug 面 | 后端零改动、前端删码为主，回归面最小 |
| 失败兜底 | 临时补丁互相嵌套 | 既有机制兜底保持：useSSE idle 60s 超时+重连续传拿回缓冲帧（useSSE.ts:551/877-894）、REST 兜底 effect（RightViewer:348）不改 |

### 4.4 修改点清单（v1.2 = F1-F3 既有 ＋ F4' 复位点唯一化迁址 ＋ F5 executeSend 起点兜底，全部前端，无后端改动）

| # | 文件:行号 | 改法 | 验证 |
|---|-----------|------|------|
| F1 | `frontend/src/features/chat/hooks/useChatTaskControl.ts` :128-150/:180-186 | 删除 `waitForCancelEvent` / `waitForCancelOrTimeout`（连同 :291 依赖项引用） | `npm run check` 无未用引用/TS 报错 |
| F2 | 同文件 `handleCancel` :219-230 | 删除 `await waitForCancelOrTimeout()` 与 `disconnect(true,true, callback)`（成功路径不再掐流） | E2E：取消后 ≤5s 右栏渲染「取消来源: user_requested」 |
| F3 | `frontend/src/features/chat/hooks/useChatCallbacks.ts` :197-212 | `isCancelEvent` 分支补 `cancelInProgressRef.current = false`（拒绝闸在收到取消终态后解） | E2E：取消后新发消息正常（无 S6 残留卡死）；取消后晚到 observation 帧不被污染 |
| F4' | `useChatTaskControl.ts` `handleCancel` finally :284 删**无条件**复位；取消失败/无 taskId 分支（:257-281）显式 `cancelInProgressRef.current=false` | **复位点唯一化**（G1+G3）：成功取消路径的闸复位只发生在"收到取消终态帧处"（F3 的 isCancelEvent 分支），`finally` 不再提前复位 → S6 闸在取消窗口期真实有效，晚到帧被拒（G1 闭环）；取消失败/无 taskId 路径显式兜底复位，防 S6 永锁（G3 闭环） | E2E：取消后右栏只渲染到取消终态，晚到 observation 不再污染；取消失败后新消息不卡死 |
| F5 | `frontend/src/features/chat/hooks/useChatStreaming.ts` `executeSend` 起点 :368 前 | 新消息起点兜底 `cancelInProgressRef.current=false` | **极端终态帧兜底**（G4）：SSE 极端异常下取消终态帧永不达时，新消息起点强制复位 → 闸永锁/新任务卡死不可能发生 | E2E：极端断流后新发消息必达；`npm run check` 无未用 ref 报错 |

> 说明①`hasReceivedCancelEventRef`（useChatTaskControl.ts:229/:267）相关复位：F2 删除 disconnect 回调复位后，其初始状态与 onComplete 复位行为沿用既有逻辑，不再由 cancel 主动管理（语义退化为"曾收到取消终态"的信号灯）。
> 说明②**选项B＝现状零改动（左栏消息条现码已写取消文案，撤选项A）**：由 F4' 将 `cancelInProgressRef` 复位点唯一化迁址到"收到取消终态帧处"后，`handleCancel` 的 finally 不再提前复位 → 取消窗口期 S6 闸有效拒绝晚到业务帧（G1），同时 onComplete 的 A5 守卫（useChatCallbacks.ts:367 `if (cancelInProgressRef.current) return`）读到 **false**（闸已在 onStep 复位）→ 自然放行 → 走 `cancel_terminal_text`（恒非空，task_runtime.py:76-93）→ 左栏消息条正常写取消文案。**零额外 onComplete 改动**（G2 闭环）。v1.3 采信选项B＝现状零改动、撤选项A（左栏维持现码显示，后端零改动）。

### 4.5 后端明确零改动（登记在案，防止回归误改）

| 后端环节 | 为何不动 |
|---------|---------|
| `task_runtime.cancel_task` :95-122 | 受理即置标志+断LLM连接+立即返回——**正确**，终态由 agent 循环自然收尾，本就没问题 |
| react_loop D/C 路径产帧 | 产帧序 [业务帧..., final] **天然正确**；受理点插帧反而打乱顺序 |
| agent_runner 扫描落库（:400-452） | 按 event_log 序落库不变式保持 |
| SSE/重连/兜底 | 既有 idle 60s+重连续传+REST 兜底全部保持，不做任何增强 |

## 五、非根因排查记录（逐项排除，防回归误判）

| # | 排查点 | 结论（代码证据） |
|---|--------|-----------------|
| 1 | sseParser 是否吞 final | 否。final 分支同步冲刷 `executionStepsRef`+`setExecutionSteps`（sseParser.ts:528-531），帧若到达必入库 |
| 2 | S12 rAF 延迟 flush 是否陈旧覆盖 | 否。`flushPendingSteps` append 后双写 ref+state，无陈旧覆盖（useSSE.ts:467-482） |
| 3 | 快照 effect 是否漏记 | 否。`executionStepsRef` 空时回退 liveSteps（RightViewer.tsx:254-264），但前提是步骤里真有 final |
| 4 | disconnect 是否清 serverTaskId / steps | 否。`disconnect` 不清 serverTaskId，clearSteps 有独立调用点（useSSE.ts:661-724） |
| 5 | resetUiFlags 是否误清 steps | 否。只清 loading/paused/receiving（useChatTaskControl.ts:157） |
| 6 | activeTaskId 是否渲染期闪烁复位 | 否。cancel 期间稳定（useTaskSelection 哨兵机制） |
| 7 | stepFilter 是否过滤 final | 否。META_STEP_TYPES 不含 final/error |
| 8 | 后端是否漏发取消 final_stats | 否。agent_runner finally 恒发（取消也发），DB 取消徽标正常即证（[33] B16） |
| 9 | 后端 C/D 路径本身是否故障 | 否。慢工具/慢 LLM 下终态可达数秒，是"延迟"非"丢失"——问题在前端 3s 就断连 |
| 10 | 取消 API 是否失败 | 否。REST 独立于 SSE 毫秒级返回成功（task_runtime.py:95-122） |

## 六、验证方案（三堂会审齐过再合入）

1. **静态**：前端 `npm run check`（存量 5 warning 不新增）；确认无 `waitForCancelEvent`/`waitForCancelOrTimeout` 残留引用与未用 ref 报错。
2. **E2E（真实后端＋真实 LLM，按 e2etests 手册 v2.8 执行）**：
   - 工具执行中取消（长工具任务取中取消）→ 断言右栏出现「取消来源: user_requested」终态段，**取消动作后 ≤5s 内渲染**；
   - **选项B＝现状零改动（v1.3 撤选项A）**：同一取消后 → 断言**左栏消息条现码已写取消文案**（A5 经 F4' 复位点唯一化达成，零 onComplete、零后端改动、零删除）；
   - LLM 流中取消 → 断言终态为 CANCELLED（C 路径既有逻辑，无双 final）；
   - 取消后立即新发消息 → 断言取消终态保留、新任务正常、无旧锁残留（F3）；
   - 取消失败/无 taskId → 断言闸已复位、新消息正常（F4' 兜底·G3）；
   - 极端断流（取消终态帧永不达）后新发消息 → 断言新任务必达、不遭 S6 永锁（F5 executeSend 起点兜底·G4）；
   - 取消后 DB `chat_task_steps` 恰 1 条 `outcome=cancelled`（后端零改动下既有双发防护仍验证）。
3. **回归**：正常完成/失败任务终态渲染不退化（前端 F1-F5 不触及其它路径）；暂停/恢复、断连重连回归不受影响。

## 七、风险与回退

| 风险 | 说明 | 化解/回退 |
|------|------|-----------|
| 后端取消终态自然发射延迟窗口 | D/C 终态需 agent 循环下一轮检出，慢工具下可达数秒 | 既有 idle 60s + after_seq 续传重连拿回缓冲帧（useSSE.ts:551/877-894）；REST tasks 兜底 effect 保持（RightViewer:348）；[41] 目标是消除"前端截断导致的永久冻结"，不追求毫秒级即时返回 |
| 删除 `disconnect(true,true)` 后取消流依赖 SSE | 极端异常（后端流中断且不重连）下 UI 悬停 | 与正常任务同样的既有兜底（idle/重连/进度轮询），无特殊化；SSE 关闭时 isReceiving=false 触发生成结论回填 |
| `cancelInProgressRef` 复位迁址遗漏 | 取消终态帧被 S6 拒绝闸过滤掉导致闸不释放 | F3 复位点与 isCancelEvent 判定同处执行，帧必经处理；E2E 取消后新发消息验证 |
| 回归 | 前端删码影响其它路径 | F1 删死代码（无调用）、F2 只删 cancel 独有动作（正常/失败路径不经过）、F3 单点补一行；三处互不影响非取消路径 |
| 回退 | 整体撤销 | `git revert` 单个提交（F1-F3 一提交），纯前端无牵涉后端 |

## 八、关联文档与契约来源

- [28] final三态字段验证与前端渲染契约方案 2026-09-12：cancelled 构造契约（L66-83）、settledSteps 渲染前提 streaming=false（L93）、sseParser 字段全解析（L116）。
- [33] 左侧任务列表回复区数据来源分析 2026-09-13：B16 final_stats=DB 信号、R3 final.response 写任务条。
- [31] X2 终态长短信号分离改造方案 2026-09-12：completed 短信号、failed/cancelled 完整条。
- [12] 连接中断自动取消任务 2026-09-08：断连重连耗尽自动取消源 client_disconnect_timeout。
- 10大编码规范（小沈 2026-09-15 三思三省复核）：v1.1 遵循 SRP（删码即整改，无新增职责）、DRY（取消路径复用正常终态既有机制，零重复）、KISS-DIRECT（删除"赌注+断连"绕路动作，与正常路径直线同构）、不得backward（后端零改动、删死代码，不保留新老双机制）。

---

**编写人**: 小欧
**更新时间**: 2026-09-15 13:52:00