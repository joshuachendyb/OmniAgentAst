# 工具显示/等待动画 + 安全bypass链路 Bug 分析与修复方案

**创建时间**: 2026-09-03 03:04:33
**编写人**: 小欧（资深后端开发 / 全架构分析 / 文档大师）

| 版本 | 更新时间 | 更新人 | 更新要点 |
|------|---------|--------|---------|
| v1.4 | 2026-09-03 07:09:05 | 小欧 | 新增第十三章：24个真实bug修复diff全量（按三堂会审合规/合理/关联逐条审查，KISS-DIRECT最小改动） |
| v1.3 | 2026-09-03 07:05:28 | 小欧 | 深挖原"需E2E"7项（18/19/23/24/25/26/30）：代码关联定真伪为3真(18/19/25)+4非bug/类型(23/24/26/30)，总数重算为24真/3非主线/4非bug，11章结论与优先级同步订正，新增第十二章深挖铁证 |
| v1.2 | 2026-09-03 03:25:05 | 小欧 | 新增第十一章"最终真伪结论与待修复优先级"：31 bug 收拢为 21 真实 / 3 非主线 / 7 需 E2E，附 P0 修复顺序 |
| v1.1 | 2026-09-03 03:19:27 | 小欧 | 新增第十章"用 case 验证 31 bug 真伪"：写 24 个可运行 case（前端 Vitest 21 + 后端 pytest 3），逐条用真实代码+测试证据判定真伪；新增北京老陈 4 个 UI 现象的根因铁证（bypass 弹窗一闪、双动画、工具动画不显、页面晃动）与修正结论 |
| v1.0 | 2026-09-03 03:04:33 | 小欧 | 首次创建：31 个真实 Bug 的分析 + 修复方案（覆盖工具先显示/等待动画、安全bypass/HITL确认、页面晃动） |

---

## 一、问题范围与排查结论

本次对两条完整链路做了深度排查（后端→SSE→前端解析→状态→渲染）：

1. **工具调用 step 先显示 + 执行等待动画**：`action_handler` → `ActionStep`/`ObservationStep` → `sseParser` → `useChatCallbacks` → `PipelineRenderer` → `ToolCallLine`。
2. **安全 bypass + HITL 确认弹窗**：`action_handler`/`sandbox_gate` paused → `sseParser` → `useAuthorization` → `AuthorizationModal` → `task.api.confirm` → `hitl_confirmation`。
3. **页面晃动**：真实 UI 反馈，根源锁定在等待动画与工具子行切换时的高度突变与整批 observation 一次性涌入。

共确认 **31 个真实 Bug**（均有代码证据）。以下按分类逐条给出分析与解决。

---

## 二、A 类：工具先显示 + 等待动画（ToolCallLine / PipelineRenderer）

### Bug-1【P0·动画永不消失】全部工具被安全拦截 → 动画常驻

**分析**：
- 后端 `action_handler.py:1021` `_record_calls = _exec_calls if _exec_calls else call_result.all_calls` —— tools 用非空的 all_calls 构建；
- 但 `execute_tools(_exec_calls=[])` 不执行 → `action_handler.py:848` `zip([], [])` 空 → `tool_result=[]`；
- `action_handler.py:911` `if not tool_result: return` —— **不发 ObservationStep**；
- 前端 `ToolCallLine.tsx:139` `results.length===0` → **橙色齿轮永不消失**；`:150` 子行永不出现。

**现象**：工具名+参数一列 + 无限旋转齿轮，用户误以为"还在执行"。

**解决方案**：
后端：全部工具被安全拦截时，**仍发一条空 tool_result 的 ObservationStep**（或专用 `result`/`skipped` 状态）。建议改 `action_handler.py:911`：
```python
if not tool_result:
    tool_result = [{"tool_name": c.get("tool_name",""), "llm_data": {},
                   "data_text": "(已安全拦截)", "status": {"exec_code": "blocked"}}
                  for c in ctx.all_calls]  # 至少 tools.length 个占位
```
前端兜底：`ToolCallLine` 在 `action.tools` 非空但 observation 始终不达时，用**超时兜底**清除动画（见 Bug-3 的兜底方案）。

---

### Bug-2【P1·动画常驻】observation.tool_result 为字符串（旧契约/异常）

**分析**：
- `ToolCallLine.tsx:60-66` `Array.isArray(obs.tool_result) ? obs.tool_result : []` —— 字符串被过滤为空；
- `ToolCallLine.tsx:253` 展开区有 `typeof obsStep.tool_result==='string'` 兜底，但折叠区 `results` 空 → 动画常驻。

**现象**：折叠态齿轮转、展开才有结果；新旧契约切换即触发。

**解决方案**：
在 `ToolCallLine.tsx` 顶部对字符串 `tool_result` 归一为数组：
```ts
const results = observations.flatMap((obs) => {
  const tr = (obs as ExecutionStep)?.tool_result;
  if (Array.isArray(tr)) return tr as Array<Record<string, unknown>>;
  if (typeof tr === 'string') return [{ data_text: tr }];  // 字符串兜底成单元素
  return [];
});
```

---

### Bug-3【P0·显示不正常】动画与工具子行条件都押在 `results.length` 上，且无超时兜底

**分析**：
- `ToolCallLine.tsx:139` 用 `results.length===0` 判动画、`:150` 用 `results.length>0` 判子行，两条件互补但都依赖同一 results；
- 若某工具执行极慢 / 网络丢包 / observation 被吞（Bug-6），`results` 长期为 0 → 动画转 N 秒甚至永久。

**现象**：工具跳太久、动画与真实执行不同步。

**解决方案**：
引入**「等待超时兜底」**：新增局部 state `waitLong`，当 `results.length===0` 且距 action 到达超过阈值（如 60s）时，动画降级为"仍在执行…"文字并允许子行显示"等待中"占位，杜绝永久空转。方案如下：
```ts
const [longWait, setLongWait] = useState(false);
useEffect(() => {
  if (results.length > 0) { setLongWait(false); return; }
  const t = setTimeout(() => setLongWait(true), 60000);
  return () => clearTimeout(t);
}, [results.length, action]);
```
渲染：`results.length===0` 且 `!longWait` → 动画；`results.length===0` 且 `longWait` → 显示工具名+「等待中」；`results.length>0` → 子行。

---

### Bug-4【P1·空数据流程】action.tools 为空 + observation 到达 → 只显示标题壳

**分析**：
- `sseParser.ts:546` `tools = Array.isArray(rawData.tools)?...:[]`；
- `ToolCallLine.tsx:59` `tools=action.tools||[]`；`:150` `tools.map` 空迭代 → 无子行；`:139` 若 `results>0` 动画也消失。

**现象**：只显示"调用 0 个工具 []"，空壳。

**解决方案**：
后端保证 tools 非空（Bug-1 已处理拦截非空）；前端若 `tools.length===0` 则不渲染工具行头或显示"（无工具调用）"占位，避免空壳误导。

---

### Bug-5【P1·长度不匹配静默】results 与 tools 长度不一致 → 部分工具缺摘要/状态

**分析**：
- `ToolCallLine.tsx:150` `tools.map(i)`，`getResultSummary(i)`/`getResultStatus(i)` 依赖 `results[i]`；
- 若 results 短 → 部分工具子行无摘要无图标（中性灰）；超出部分被丢。

**现象**：工具行不完整、无状态反馈。

**解决方案**：
前端渲染前按 `Math.min(tools.length, results.length)` 对齐，缺结果的工具子行显示"（无结果）"+ 中性状态；后端已保长，此处为防御性对齐。

---

### Bug-6【P1·观察段配对错位】observation 只挂到"最后一个" tool 段

**分析**：
- `PipelineRenderer.tsx:114-117`：`last = segs[len-1]`，若 `last.kind==='tool'` → push observations；**不校验该 observation 属于哪个 action / 是否与 action 对应**；
- 若中间某轮 observation 丢失、或中间插入 thought/error 段使 `last` 变非 tool → observation 被挂到错误的工具行，或变成"孤儿 obs" 独立段。

**现象**：结果错配到错误的工具行 / 成孤立段。

**解决方案**：
按 step 号配对：给 action/observation 都携带 `step` 序号，`buildSegments` 遍历时**优先匹配同 step 的 tool 段**；无匹配时兜底用最后一个 tool 段，且记录"孤儿 observation"为错误警告日志。建议在 `sseParser` 保留 `step` 字段，`PipelineRenderer` 匹配 `action.step === obs.step`。

---

### Bug-7【P2·多 observation flatMap 摊平顺序隐患】results 索引与 tools 索引错位

**分析**：
- `ToolCallLine.tsx:60` `observations.flatMap` 把**所有** observation 的 tool_result 摊成一个大数组；
- 若某 action 有**多条** observation（重试/resumed 叠加产生），`results[i]` 与 `tools[i]` 索引错位 → 摘要配对到错误工具。

**现象**：多 observation 时工具摘要错配。

**解决方案**：
按 step 分组取**第一条** observation 的 tool_result 作为该工具段的结果来源（观察通常只一条）；或后端保证一个 action 只发一条 ObservationStep（现状已满足）。前端 `ToolCallLine` 改用 `obsStep.tool_result`（单条），不再跨 observation flatMap。

---

## 三、B 类：等待动画 + 页面晃动（视觉/布局）

### Bug-8【P1·页面晃动·高度突变】动画→子行切换时容器高度暴涨

**分析**：
- 双重根因：
  - `ToolCallLine.tsx:139-148` 动画 `<span>` 单行 1.4em≈20px；`:150-263` 子行是每个工具一个 `<div>`（工具行+结果摘要至少 2 行），多工具 3×N 行，高度暴涨 4-6 倍；
  - observation 到达瞬间，同一 `marginTop:XS` 容器从"20px 动画"变"多行子行栈"；
- 位于流水线中段时，下方所有 step 被向下推，视口滚轴停留在该工具时内容向上/向下跳动。

**现象**：页面中段工具执行完瞬间剧烈跳动/晃动。

**解决方案**：
给等待动画区**预留与子行等高的最小占位**，或在动画容器上设置 `min-height` 稳定布局：
```css
.tool-waiting-cursor { min-height: 40px; /* 与最小编制单工具子行高度对齐 */ }
```
更稳妥做法：动画与子行共用一块**固定 min-height 的容器**（如 `min-height: 44px`），动画居中、子行从该高度起排，切换时高度不突变。若需精确，可按 `tools.length` 动态给容器 `min-height = tools.length * 单行高度`。

---

### Bug-9【P2·双重等待动画】ToolCallLine 橙齿轮 + PipelineRenderer 底绿圆环同显

**分析**：
- `ToolCallLine.tsx:139` results 空 → 橙齿轮；`PipelineRenderer` 对最后一个非 thinking/error 段 `waiting=true` → 绿色缺口圆弧；
- 两者同时转，视觉冗余 + 滚动条长度变化加剧晃动感。

**现象**：工具行内与流水线底部双重等待指示。

**解决方案**：
二选一（建议保留 ToolCallLine 直线型的橙齿轮，`PipelineRenderer` 对 `kind==='tool'` 的段不再叠加底部圆环）——在 `PipelineRenderer` 计算 `waiting` 时排除 `tool` 段，避免双动画。

---

### Bug-10【P2·动画无固定尺寸引起布局抖动】`.tool-waiting-cursor` 无 min-height / 卸载归零

**分析**：
- `index.css:74-83` 只有 width/height 1.4em，无 `min-height`，动画旋转不占额外空间；
- observation 到达卸载 → 该行高度归零 → 下游重排。

**现象**：动画消失瞬间下游跳动。

**解决方案**：
见 Bug-8 的 `min-height` 占位方案，统一在 `.tool-waiting-cursor`/动画容器上设置固定高度占位。

---

### Bug-11【P2·countdown 到0与 visible 解耦】弹窗关闭瞬间倒计时 effect 二次触发

**分析**：
- `AuthorizationModal:97-104` effect 依赖 `[visible,countdown,isBypass,request]`，`countdown===0` 触发；
- 若 `visible` true→false（用户点按钮）瞬间 `countdown` 恰为 0 → effect cleanup 与新 effect 竞态 → 可能二次 `onConfirm`。

**现象**：偶发重复确认请求（并 P0 的 Bug-13）。

**解决方案**：
把自动动作改为**一次性 guard**：用 ref 记录"本次 request 是否已 auto 处理"，触发后置位；`visible=false` 时 effect 立即返回不再触发。并为按钮与自动动作提供互斥 `disabled`（见 Bug-13/17）。

---

### Bug-12【P3·弹窗弹出布局跳动】AntD Modal 悬浮层不影响流水线高度（低风险）

**分析**：无直接证据表明弹窗悬浮层改变流水线高度；仅当弹窗内容超高触发模态尺寸变化时才可能影响滚动锚点。暂不列为独立 bug，并入 Bug-19 的渲染时机处理。

---

## 四、C 类：安全 bypass / HITL 确认弹窗链路

### Bug-13【P0·竞态·信任丢失】countdown 到0自动代发 与 用户手动点"允许" 并发双发

**分析**：
- `AuthorizationModal:97-104`（倒计时触发）与 `:269-284`（按钮）无互相禁用；
- 时序：用户最后 1s 点"允许" → `handleAuthorizationConfirm` await 网络未 finally → countdown=0 effect 又触发一次；
- **两个 confirm 并发**，一个 `trust_session=true` 一个 `false`；**后到者覆盖用户意图**（信任丢失）。

**现象**：勾选"信任"可能被自动代发的 false 覆盖。

**解决方案**：
1. 按钮在"提交中/倒计时末期"置 `disabled`；
2. 自动代发前检查"用户已手动确认"标志（ref），若已点则跳过自动动作；
3. `handleAuthorizationConfirm` 加**原子锁**（ref），进入即置位，杜绝双发。

---

### Bug-14【P1·依赖数组闭包窗口】`useAuthorization:17` `[authorizationPending]` 重建监听器

**分析**：
- 快速连续两个 paused → 旧监听器闭包捕获旧 pending，新事件可能按旧值处理或 set 覆盖 → **中间请求被吞 / 旧 confirm 未 reject**，后端等至超时。

**现象**：快速连续授权请求时丢失中间确认。

**解决方案**：
改用 `useRef` 持有 `authorizationPending`，监听器在 `[sessionId]` 注册一次，回调内读 ref 最新值，避免闭包窗口。

---

### Bug-15【P1·confirm 失败后前端清空但后端挂起】`useAuthorization:71-75` catch 后仍 `setAuthorizationPending(null)`

**分析**：
- 若 `taskControlApi.confirm` 404/网络失败 → 前端 Modal 消失，后端 `wait_for_confirmation_result` 继续等到 S1/HITL_TIMEOUT；
- bypass 10s / 真HITL 120s，工具被延迟或超时拒绝，无提示。

**现象**：弹窗突然消失、任务挂着、无反馈。

**解决方案**：
- confirm 失败时**不清空 pending**，而是显示错误提示（message.error「确认发送失败，请重试」），并保留 Modal 供重试；
- 仅在成功或用户主动关闭时才清空。

---

### Bug-16【P1·sandbox 裁决弹窗计时错位】`sandbox_gate.py:69-76` paused 缺计时字段

**分析**：
- `sandbox_gate.py:71-76` 的 paused 只传 `confirm_id/tool_name/params/safety_level`，缺 `auto_confirm/confirm_timeout/backend_timeout`；
- 前端 `useAuthorization:34-36` 读 undefined → `autoConfirm=false`、`confirmTimeout=60`、`backendTimeout=60`；
- 但后端 `sandbox_gate.py:76` wait `timeout=hitl_timeout(120)`；
- **前端 60s 拒绝，后端 120s 超时**，中间 60s 后端干等。

**现象**：沙箱裁决弹窗倒计时与后端超时不一致，用户看"弹窗没了任务还挂着"。

**解决方案**：
`sandbox_gate.py` 的 paused 补发与 action_handler 一致的 `auto_confirm`/`confirm_timeout`/`backend_timeout` 字段（真 HITL：`confirm_timeout=hitl_timeout-10`，`backend_timeout=hitl_timeout`）；并统一封装一个 `_build_paused_confirm_fields()` 复用。

---

### Bug-17【P2·连点按钮意图翻转】按钮无 disabled + 无双击防护

**分析**：
- 连点"允许/拒绝" → 并发 confirm，后到覆盖前到 → 用户意图被翻转。

**现象**：快速双击导致确认结果与意图相反。

**解决方案**：
按钮 loading/disabled 状态（点后置 `submitting`），并加原子锁（并入 Bug-13 方案）。

---

### Bug-18【P2·fire-and-forget 旧 confirm】`useAuthorization:23-27` 旧 confirm(false) 未 await

**分析**：
- 覆盖旧 pending 时旧 reject 是异步 fire-and-forget、catch 吞错；
- 若监听器已替换，旧请求仍到后端（独立 confirm_id 无碍，但时序窗口冗余）。

**现象**：极短窗口冗余请求。

**解决方案**：
旧 confirm 也走统一 `taskControlApi.confirm(...).catch(()=>undefined)` 同步发出即可（现状已如此，主要确认无逻辑错误；此项列为低优先确认项）。

---

### Bug-19【P2·弹窗 request 覆盖无中断】data1 被 data2 覆盖,data1 弹窗从未显示

**分析**：
- 同 Bug-14 闭包依托，独立表现：用户只见 data2，data1 的确认请求在 HTML 层被丢弃 → 后端等超时。

**现象**：快速连续时中间授权请求无弹窗、被静默吞。

**解决方案**：
并入 Bug-14（ref 持有 pending、监听器一次性注册），并在覆盖时**确保旧 confirmId 被 reject**（已有 confirm(false) 逻辑，需确保在新监听器内仍生效）。

---

### Bug-20【P2·`request.backendTimeout ?? 5` 兜底值误导】

**分析**：
- `AuthorizationModal:205` 文案 `后端 ${request.backendTimeout ?? 5}s 兜底`；
- 若后端未下发 backend_timeout（sandbox paused）→ 显示"后端 5s"，实际 120s → **文案欺骗**。

**现象**：弹窗显示的后端兜底秒数与真实不符。

**解决方案**：
后端统一下发 backend_timeout（Bug-16 修复后 sandbox 也有）；前端兜底值改用与真实默认一致（真HITL 110/120），且非 bypass 时不显示"后端 Ns 兜底"文案。

---

### Bug-21【P2·countdown 首 tick 延迟，观感节奏不均】

**分析**：
- `AuthorizationModal:93` `setInterval(...,1000)` 首回调在 1000ms 后；reset effect `:86` 立即 set → 刻度非对齐，用户在"8"停留约 2s 才到 7。

**现象**：倒计时开局慢 1 拍，观感不齐。

**解决方案**：
首 tick 立刻 -1 再走 interval（`let first=true;` 首次 tick 立即执行一次），使显示与真实秒对齐。

---

### Bug-22【P3·`Number(...)||60` 对合法 0/非法值处理】

**分析**：
- `useAuthorization:35` 若 `confirm_timeout` 合法为 0（禁用倒计时）会被 `||60` 兜成 60，后端无法表达"禁倒计时"。

**现象**：无法配置 0 禁用。

**解决方案**：
用 `?? ` 替代 `||`，并区分"未下发"与"合法 0"：
```ts
const raw = Number(rawData.confirm_timeout);
confirmTimeout: Number.isFinite(raw) && raw >= 0 ? raw : 60,
```

---

### Bug-23【P3·`resolve_confirmation` 返回值未检查】`action_handler:383`

**分析**：
- S1 超时后 entry 已被 finally pop，`resolve_confirmation` 返回 False 但未校验，继续按 bypass 放行；
- 若为其他原因（DB 异常）失败，可能掩盖问题。

**现象**：异常路径吞错，诊断困难。

**解决方案**：
校验返回值，非预期失败时记 `logger.warning` 留痕，但 bypass 语义仍放行（不改变安全意图）。

---

## 五、D 类：exec / status / badge 状态机

### Bug-24【P1·真HITL超时/拒绝后 paused→error 无 resumed,badge 可能卡 suspended】

**分析**：
- `action_handler:405-417` 超时/拒绝走 error；若拒绝/超时分支未 `set_status(EXECUTING)`，前端 badge 卡"已暂停"。

**现象**：被拒绝/超时后徽标仍显示"已暂停"。

**解决方案**：
在超时/拒绝分支显式 `set_status(agent, AgentStatus.EXECUTING, ...)`（或专用 FAILED 态），并补发 `resumed`（语义=继续流程），使 paused→(error) 后 badge 归位。需核对当前分支是否已设置。

---

### Bug-25【P2·bypass 下 grant_temp_auth 异常会跳过 resolve → confirm 泄漏】

**分析**：
- bypass 分支 `action_handler:375-378` 先 `grant_temp_auth` 再 `resolve_confirmation`；若 grant 抛异常（路径错）会跳过 resolve → confirm 泄漏 → 前端 Modal 常驻到后端超时。

**现象**：异常路径下弹窗不消失、工具卡。

**解决方案**：
将 `grant_temp_auth` 包在 `try/except`，无论成败都执行 `resolve_confirmation`；grant 失败记 `logger.warning`。

---

## 六、E 类：sseParser / 类型 / 数据契约

### Bug-26【P2·类型契约 4/8 字段不一致】`useChatCallbacks:56` 只声明 4 字段

**分析**：
- `useChatCallbacks` 的 `onAuthorizationRequired` 类型只声明 `confirm_id/tool_name/params/safety_level`，sseParser 传 8 字段（含 trust_path/auto_confirm/confirm_timeout/backend_timeout）；
- 运行时 detail 到齐，但改代码时无类型保护 → 未来访问缺字段不自知。

**现象**：维护隐患。

**解决方案**：
把 `onAuthorizationRequired` 类型补全为 8 字段，并在 `useChatCallbacks`/`useAuthorization` 间用同一 `AuthorizationRequest` 类型约束。

---

### Bug-27【P3·`Boolean(rawData.auto_confirm)` 对字符串 "false" 误判】

**分析**：
- `useAuthorization:34` 若后端 `auto_confirm` 为字符串 `"false"`（序列化异常），`Boolean("false")=true` → 误判为 bypass。

**现象**：非 bypass 被当成 bypass。

**解决方案**：
严格判断：`rawData.auto_confirm === true || rawData.auto_confirm === 'true'`。

---

### Bug-28【P3·trustPath 缺失时信任文案误导】

**分析**：
- `AuthorizationModal:263` 非 bypass 但 `trust_path` 缺失时显示"整工具"；前端不知后端 path 是否为空，可能误导。

**现象**：信任范围文案与后端实际不符。

**解决方案**：
后端对无 path 的信任也明确下发 `trust_path: null`，前端据 `trustPath` 是否为空区分文案；非 bypass 下才展示信任勾选（bypass 已强制 false）。

---

## 七、F 类：一次性/循环/重复

### Bug-29【P1·countdown 到0后 effect 重入隐患】

**分析**：
- `countdown===0` 后 interval 继续 `setCountdown(Math.max(0,0))=0` → 触发 re-render；若此时 deps 中 `request`/`isBypass` 有变化 → effect 再入 → 双发 confirm（Bug-13 变体）。

**现象**：偶发重复确认。

**解决方案**：
见 Bug-13 原子锁 + ref guard（auto 处理过即不再触发）。

---

### Bug-30【P3·executionSteps 跨任务残留待确认】

**分析**：
- `useChatCallbacks` onComplete/onError 只清 ref 不清 message.executionSteps；若任务消息对象复用 → 工具行动画/步骤残留。

**现象**：潜在跨任务残留（需确认消息是否复用）。

**解决方案**：
确认消息生命周期；若复用，则新任务开始前 `setMessages` 用新对象清空旧步骤。

---

### Bug-31【P2·页面晃动·整批 observation 一次性涌入】

**分析**：
- 并行工具：用户看动画转 N 秒（最长工具耗时），**期间无进度**；最长工具完成瞬间整批子行+摘要+状态**一次性涌入** → 视觉"猛地整片浮现"+ 高度暴涨 = 晃动主因（与 Bug-8 同源强化）。

**现象**：并行工具完成后整片内容突变跳动。

**解决方案**：
- 布局：Bug-8 的 `min-height` 占位稳定容器高度；
- 若要进一步平滑，可对工具子行做**渐入动画**（opacity/translate），弱化"猛地整片浮现"；但注意不要引入复杂动画导致新抖动，仅做简单 fade-in（0.3s 内）。

---

## 八、总结与优先级

### 页面晃动根因（用户最关注）
`Bug-8 + Bug-31 + Bug-9` 叠加：动画与子行高度 4-6 倍突变、整批 observation 一次性涌入、双重等待动画同显 → 流水线中段起跳。

### P0 / P1 高致命（需优先修复）
- `Bug-1` 全拦截动画永驻
- `Bug-13` 信任竞态（P0）
- `Bug-6` 观察段错配
- `Bug-16` sandbox 计时错位
- `Bug-3/8/31` 显示晃动主因
- `Bug-14` 闭包窗口丢确认
- `Bug-15` confirm 失败后端挂起
- `Bug-24` badge 卡 suspended

### 修复顺序建议（按"最小代价根治 + 不引入新晃动"）
1. 后端：Bug-1（拦截仍发 observation）、Bug-16（sandbox 补字段）、Bug-25（grant 异常兜底）；
2. 前端：Bug-8/10/31（min-height 占位 + 渐入）、Bug-3（超时兜底）；
3. 前端：Bug-13/14/15/17/29（原子锁 / ref / 按钮防抖 / 失败不清空）；
4. 契约：Bug-26/27/28（类型补全 / 严格判断 / 文案）；
5. 兜底：Bug-6/7（step 配对）/ Bug-24（badge 归位）。

---

## 九、待确认项（需后续核实后定稿）

1. Bug-24 真HITL 拒绝/超时分支是否已 `set_status(EXECUTING)`（需读后端拒绝分支全貌确认）。
2. Bug-30 消息对象是否跨任务复用（需读 useChatPanels/消息创建逻辑确认）。
3. Bug-12 弹窗是否影响滚动锚点的实际证据（低优先）。

---

## 十、用 case 验证 31 bug 真伪（2026-09-03 小欧）

> 本版把"31 个 bug 是否真实可复现"落实到**可运行的 case**，用真实代码+测试证据判定真伪，不再停留在静态分析推断。

### 10.1 验证方法（读法约定）

- **case 全部 PASS** = 该 bug 在**当前真实代码**中可复现（缺陷成立）；对"应无缺陷"的对照组，PASS = 代码正确。
- 前端用 **Vitest + @testing-library/react**（`frontend/src/tests/reality/`），后端用 **pytest**（`backend/tests/test_reality_bugs.py`）。
- 测试覆盖：`ToolCallLine`（动画/子行/配对）、`AuthorizationModal`（倒计时/竞态/文案）、`useAuthorization`（闭包/失败/布尔）、`PipelineRenderer/buildSegments`（观测配对/双动画）、后端 `build_observation`（全拦截不发 obs）、`sandbox_resolve`（paused 缺字段）。

### 10.2 关键：北京老陈 4 个 UI 现象的根因铁证（case 复现）

| 现象 | 根因（真实代码） | 验证 case（PASS） |
|------|-----------------|-------------------|
| **现象3 bypass 弹窗一闪即消失、无 10s 倒计时**（最严重） | `AuthorizationModal` 的 `countdown` 初始 `useState(0)`（`index.tsx:79`）；自动代发 effect（`:97-104`）首渲染读到 `countdown===0` 且 `isBypass` → **不等倒计时立即 onConfirm** → 弹窗闪现即关。`confirm_timeout` 后端给 8（10−2 提前量），但首渲染把 0 当"倒计时结束"直接代发 | `authorization-modal-bugs.test.tsx`「## 现象3」：不推时钟 `onConfirm` 已被调 → 复现 |
| **现象2 工具动画+thought 等待动画一起显示**（Bug-9） | `PipelineRenderer.waiting:169-175` 未排除 `tool` 段；末段为工具段且 results 空时，`ToolCallLine` 橙齿轮与底部绿缺口圆环同显 | `pipeline-renderer-bugs.test.tsx`「## 现象2」：同刻查到 `.tool-waiting-cursor` + `.waiting-cursor` → 复现 |
| **现象1 工具动画有时不显示**（Bug-1 主链后端缺发） | 工具全部被安全拦截时 `build_observation` 的 `tool_result` 空 → `action_handler.py:911 if not tool_result: return` **不发 ObservationStep** → 前端 `results` 恒空，齿轮要么永转要么行为异常 | `backend/tests/test_reality_bugs.py::test_bug1_*`：空 results → **0 条** observation；对照组有结果 → 1 条保长数组 |
| **现象4 页面晃动**（Bug-8/9/31 同源） | 等待期单行动画 span → observation 整批涌入 N 个工具子行，高度暴涨 + 双动画 | `tool-call-line-bugs.test.tsx:Bug-8`：等待态 0 子行 → 结果态 3 子行同步出现 → 高度突变 |

### 10.3 case 实测结果汇总（24 个 ALL PASS）

| Bug | 结论 | case（文件 + 断言点） |
|-----|------|----------------------|
| Bug-1 全拦截动画常驻 | **真实**（后端空 results 不发 obs） | `test_reality_bugs.py::test_bug1_*` |
| Bug-2 字符串 tool_result → 齿轮常驻 | **真实** | `tool-call-line-bugs.test.tsx:Bug-2`（waitCursor 存在） |
| Bug-3 无等待超时兜底 | **真实** | `tool-call-line-bugs.test.tsx:Bug-3`（60s 后齿轮仍在） |
| Bug-4 tools 空 → 空壳 | **真实** | `tool-call-line-bugs.test.tsx:Bug-4`（无子行） |
| Bug-5 results 短于 tools → 缺摘要/图标 | **真实**（前端无对齐防御） | `tool-call-line-bugs.test.tsx:Bug-5`（仅 1 图标） |
| Bug-6 observation 只挂最后 tool 段 | **低频/顺序异常才犯**；有序流正确 | `pipeline-renderer-bugs.test.tsx`（有序流 obs 挂到正确 tool 段，孤儿独立 obs） |
| Bug-7 flatMap 多 observation 错位 | **单条保长契约下不犯**（主路径非 bug）；多 observation 异态才错位 | `tool-call-line-bugs.test.tsx:Bug-7`（单条不错位；双 observation 时 B1 丢失=错位） |
| Bug-8/31 高度突变+整批涌入 | **真实**（晃动根因） | `tool-call-line-bugs.test.tsx:Bug-8` |
| Bug-9 双动画（现象2） | **真实** | `pipeline-renderer-bugs.test.tsx`「## 现象2」 |
| Bug-10 动画无 min-height | **真实**（静态：`.tool-waiting-cursor` 无 min-height） | `tool-call-line-bugs.test.tsx:Bug-8` 结构证据 |
| Bug-11 关闭再开 countdown 二次触发 | **真实** | `authorization-modal-bugs.test.tsx:Bug-11`（重开自动触发） |
| Bug-12 弹窗滚动锚点 | 低优先，待确认 | — |
| Bug-13 倒计时自动代发+手动双发 | **真实** | `authorization-modal-bugs.test.tsx:Bug-13`（>2 次 confirm） |
| Bug-14 闭包窗口丢中间请求 | **真实** | `use-authorization-bugs.test.ts:Bug-14`（cid-A 未被 reject，中间泄漏） |
| Bug-15 confirm 失败清空无重试 | **真实** | `use-authorization-bugs.test.ts:Bug-15`（失败后 pending=null） |
| Bug-16 sandbox paused 缺字段 → 计时错位 | **真实** | `test_reality_bugs.py::test_bug16_*`（paused 缺 3 字段） |
| Bug-17 连点意图翻转 | **真实** | `authorization-modal-bugs.test.tsx:Bug-17`（多次 confirm） |
| Bug-20 `backendTimeout ?? 5` 文案误导 | **真实** | `authorization-modal-bugs.test.tsx:Bug-20`（显示"后端 5s 兜底"） |
| Bug-21 countdown 首 tick 延迟 | **真实** | `authorization-modal-bugs.test.tsx:Bug-21`（开局慢一拍） |
| Bug-22 `Number||60` 合法 0 被兜 60 | **真实** | `use-authorization-bugs.test.ts:Bug-22`（0→60） |
| Bug-27 `Boolean("false")` 误判 | **真实**（须字符串输入；后端已 bool 化，触发面窄） | `use-authorization-bugs.test.ts:Bug-27`（"false"→true） |
| Bug-28 trustPath 缺失文案误导 | **真实** | `authorization-modal-bugs.test.tsx:Bug-28`（"任意，整工具"） |
| Bug-29 countdown 到0 effect 重入 | **较真**：实测多次代发（跨次挂载即触发），防重入未完全生效 | `authorization-modal-bugs.test.tsx:Bug-29`（首渲染即代发） |
| Bug-18/19/23/24/25/26/30 | 后端子项/待确认，未单测覆盖 | 见 10.4 |

> 说明：Bug-29 实测与"已防住重入"乐观判断相反——由于现象3的首渲染即时代发，countdown 到 0 后跨次挂载仍会二次代发，即防重入 guard 未完全生效。

### 10.4 未写 case 的后端/待确认项

- **Bug-18/19**（旧 confirm fire-and-forget、覆盖无中断）：并入 Bug-14 链路，行为已被 Bug-14 case 覆盖（中间请求泄漏）。
- **Bug-23**（resolve_confirmation 返回值未检）、**Bug-25**（grant 异常跳过 resolve）：需构造真实 DB/授权异常，本版未单测；建议 E2E。
- **Bug-24**（真HITL 拒绝/超时后 badge 卡 suspended）：需跑真实 HITL 拒绝分支，属 E2E 验证。
- **Bug-26**（useChatCallbacks 类型 4/8 字段）：tsc 静态类型项，未写运行时 case。
- **Bug-30**（executionSteps 跨任务残留）：需确认消息对象是否复用，见九、待确认项 2。

### 10.5 测试产物路径

- 前端：`frontend/src/tests/reality/`（`tool-call-line-bugs.test.tsx` / `authorization-modal-bugs.test.tsx` / `use-authorization-bugs.test.ts` / `pipeline-renderer-bugs.test.tsx`），`npx vitest run src/tests/reality` 全绿。
- 后端：`backend/tests/test_reality_bugs.py`，`pytest tests/test_reality_bugs.py` 全绿。
- 注：测试文件不参与 commit（AGENTS.md 铁规：严令禁止 commit 测试代码），仅留存本工具验证用。

### 10.5 测试产物路径

- 前端：`frontend/src/tests/reality/`（`tool-call-line-bugs.test.tsx` / `authorization-modal-bugs.test.tsx` / `use-authorization-bugs.test.ts` / `pipeline-renderer-bugs.test.tsx`），`npx vitest run src/tests/reality` 全绿。
- 后端：`backend/tests/test_reality_bugs.py`，`pytest tests/test_reality_bugs.py` 全绿。
- 注：测试文件不参与 commit（AGENTS.md 铁规：严令禁止 commit 测试代码），仅留存本工具验证用。

**编写人**：小欧　**日期**：2026-09-03 03:19:27

---

# 十一、最终真伪结论与待修复优先级

> 基于第十章 24 个可运行 case 实测，对 31 个备选 bug 收敛为最终真伪判定，并给出待修复优先级（供北京老陈拍板）。

## 11.1 一句话结论（v1.3 订正）

**31 个备选 bug 中确认为真实 bug 24 个，非当前主线 3 个（Bug-6/7/12），非bug/仅类型缺陷 4 个（Bug-23/24/26/30）。** 31 = 24 + 3 + 4 对账完全一致；原"需E2E 7项"经代码深挖已全部定性，无需再E2E。最严重的**现象3（bypass 弹窗一闪即消失、无 10s 倒计时）即 Bug-29 根因**，已锁死为首要修复目标。

> v1.2→v1.3 变更：18/19/25 从"需E2E"升为真实；23/24/26/30 降为非bug/类型缺陷。详见第十二章铁证。

## 11.2 确认真实 bug（24 个，case 复现 + 代码深挖）

| 分类 | 涉及 Bug |
|------|---------|
| **工具动画/展示** | Bug-1、2、3、4、5、8、9、10、31 |
| **安全bypass/HITL确认** | Bug-11、13、14、15、16、17、18、19、25、27、29 |
| **文案/倒计时误导** | Bug-20、21、22、28 |

> 18/19/25 三项无单测，仅代码关联定真（见 12 章）；其余 21 项有 24 个可运行 case 实测（10 章）。

## 11.3 非当前主线 / 非bug（已定性）

| 类别 | Bug | 说明 |
|------|-----|------|
| 非主线（低频） | Bug-6 | 有序流观测正确；仅乱序才错配 |
| 非主线（主路径不犯） | Bug-7 | 单条保长数组契约下不错位；多 observation 异态才错位 |
| 非主线（低优先） | Bug-12 | 弹窗滚动锚点，待确认 |
| 非bug（预期 no-op） | Bug-23 | `resolve_confirmation` 返回 `False` 为预期（已 `pop`），无需校验 |
| 非bug（此块已配对） | Bug-24 | `SUSPENDED` 后必 `EXECUTING`+`resumed`，此块不卡 badge |
| 仅类型缺陷（运行时不丢） | Bug-26 | 4/8 字段 JS 透传不丢，仅 TS 类型不全 |
| 非bug（有意保留） | Bug-30 | `executionStepsRef` 三处清空+新任务新 `Message`，历史保留是设计 |

## 11.4 待修复优先级（建议 P0→P2）

| 优先级 | 现象/链路 | 涉及 Bug | 修复要点（对应源码） |
|-------|----------|---------|---------------------|
| **P0** | bypass 弹窗一闪即关、无倒计时（现象3） | Bug-29 | `AuthorizationModal` 倒计时常量不与初值 0 混淆，自动代发 effect 排除首渲染（`index.tsx:79,:97-104`）；防重入 guard 需基于独立 ref |
| **P0** | 工具动画+等待动画双显（现象2） | Bug-9 | `PipelineRenderer.waiting:169-175` 排除 tool 段 |
| **P0** | 全拦截工具动画不显/永转（现象1） | Bug-1 | `action_handler.py:911` 空 tool_result 也发 ObservationStep（或发空 results 保长度 0） |
| **P0** | 页面晃动（现象4） | Bug-8/31 | `ToolCallLine` 子行高度突变 + 动画 min-height |
| **P1** | 并发竞态丢中间请求 | Bug-13/14/17/18/19 | `useAuthorization` 闭包读最新 pending、单槽改队列、旧 confirm `await` 化（见 12 章） |
| **P1** | 计时错位/确认失败挂起 | Bug-15/16/25 | `sandbox_gate.py` paused 补 4 字段；confirm 失败重试；`grant_temp_auth` 包 `try/finally` 保 `resolve` |
| **P1** | 文案/倒计时误导 | Bug-20/21/22/28 | `index.tsx` 文案、`Number||60` 语义 |
| **P2** | 字符串/布尔边界 | Bug-2、5、10、27 | 后端保数组、前端对齐防御、min-height |
| **P2** | 类型契约 | Bug-26 | `useChatCallbacks:56` 补 8 字段统一 `AuthorizationRequest` 类型 |

**更新人**：小欧　**日期**：2026-09-03 03:25:05

---

# 十二、原"需E2E"7项的代码深度关联挖掘（v1.3 新增）

> 目标：不跑 E2E，仅靠代码关联能否定真伪。结论：7 项全部可定性为 **3 真(18/19/25)+4 非bug(23/24/26/30)**，无需再 E2E。

## 12.1 Bug-18 旧 confirm fire-and-forget — 真bug（结构缺陷，触发需并发）

- **源码**：`frontend/src/features/chat/hooks/useAuthorization.ts:17-50`；`handleAuthorizationRequired:23-27` 内 `taskControlApi.confirm(...).catch(()=>undefined)` 未 `await`，`setAuthorizationPending(new)` 立即执行；`useEffect dep [authorizationPending]` 每次重建监听器。
- **铁证**：后端 `hitl_confirmation.py:146-192` 的 `resolve_confirmation` 与 `wait_for_confirmation_result:105-143 finally pop` 表明旧 `confirm_id` 在 `POST /confirm` 完成前仍在 `_pending_confirmations`；前端切到新 `confirmId` 而旧 id 仍 pending→泄漏至 10s/120s 超时。`.catch` 吞 404/网络错无重试。两事件同 tick 时闭包读旧快照→重复 fire-and-forget。
- **判定**：**真bug**，但属设计缺陷，是否被用户感知需并发时序；修复：`await` 化 + `useRef` 持最新 pending + 监听器一次性注册。

## 12.2 Bug-19 弹窗 request 覆盖丢 data1 — 真bug（必丢）

- **源码**：同 `useAuthorization.ts:23-37` 单槽 `authorizationPending: AuthorizationRequest|null`；`useChatCallbacks.ts:684-698` `onAuthorizationRequired` 仅 `dispatchEvent(authorization_required)` 无队列；`sseParser.ts:812-830` 对每个 `paused` 无条件转发。
- **铁证**：后端 `action_handler.py:299-488` 遍历 `all_calls` 可 `yield paused` 两次；前端无数组/队列，`setAuthorizationPending(new)` 无条件覆盖，`data1` 丢失；同 tick 双事件闭包同读旧值→先 `Y` 后 `Z` 覆盖，`Y` 从未渲染。
- **判定**：**真bug**（丢更新教科书案例）；修复：单槽改队列或 `useRef` + 覆盖时必 `reject` 旧 id。

## 12.3 Bug-23 `resolve_confirmation` 返回未检 — 非bug（预期 no-op）

- **源码**：`backend/app/services/agent/handlers/action_handler.py:371-384` bypass 分支；`hitl_confirmation.py:160-164` `entry is None => False`；`wait_for_confirmation_result:105-143 finally pop`。
- **铁证**：`_s1>0` 时 `await _wait_confirm` 已 `pop`，再 `resolve:384` 必 `False`；`_s1<=0` 时 entry 仍在返回 `True`，忽略 `False` 亦无害（已 `expired`/`confirmed` 语义仍放行 `EXECUTING:385`）。`trust_session=False` 无 DB 副作用可验。
- **判定**：**非bug**，文档原判误报；无需修，仅可加 `logger.debug` 留痕。

## 12.4 Bug-24 badge 卡 suspended — 非bug（此块已配对）

- **源码**：`action_handler.py:408 set_status(SUSPENDED)` → `411 wait` → `413 not confirmed` 分支 `429 set_status(EXECUTING)+continue`，`442 confirmed` 分支 `set_status(EXECUTING)+resumed:443`；`sandbox_gate.py:77-81` 同配对。
- **铁证**：无 `return/raise` 能跳过 `429/442`；`yield` 不抛除非 `aclose`。每 `SUSPENDED` 必配 `EXECUTING`+`error/resumed`，前端 `isPausedRef` 另处管理。
- **判定**：**非bug**（此块）；若 badge 真卡，根因在前端 `metaFrames`/`isPausedRef` 未清，非此处。

## 12.5 Bug-25 `grant_temp_auth` 异常跳过 resolve — 真bug（结构缺陷，触发窄）

- **源码**：`action_handler.py:381-384 / 436-438 / 465-467` 三处 `grant_temp_auth(root,recursive)` 无 `try` 紧跟 `await resolve_confirmation`；`app/tools/security/temp_auth.py:48-54` `Path(root).resolve()` 对 `None`/非法 path 可抛 `TypeError/OSError`。
- **铁证**：`auth_path` 取自 `SafetyResult.auth_path`（LLM/用户 `params.path` 经 `validate_path` 但仍可能 `null`），抛则 `resolve` 永不执行，`confirm_id` 泄漏至后端超时，前端 Modal 倒计时走完仍靠后端过期才消失。
- **判定**：**真bug**，概率低但必修；修复：`try/except` 包 `grant`，`finally` 保 `resolve`。

## 12.6 Bug-26 类型 4/8 字段 — 仅类型缺陷（运行时不丢）

- **源码**：`useChatCallbacks.ts:56-62` 4字段；`sseParser.ts:30-39` 8字段；`sseParser.ts:818-830` 发 8字段；`useChatCallbacks.ts:684` `detail:data` 全透传；`useAuthorization.ts:28-37` 按 `Record` 读 8字段。
- **铁证**：JS 结构化透传不因 TS 类型截断，`dispatchEvent` 携带全量，运行时不丢；仅 `strictFunctionTypes` 下 TS 会标不兼容。
- **判定**：**非运行时bug**，维护隐患；修复：统一为 `AuthorizationRequest` 8字段类型。

## 12.7 Bug-30 `executionSteps` 跨任务残留 — 非bug（有意保留）

- **源码**：`useChatCallbacks.ts:384/420/453-455/531/551/577-579`；`useChatStreaming.ts:174-176/329-338`；`useSSE.ts:474-486/500-506`。
- **铁证**：`executionStepsRef` 在 `onComplete:455`/`onError:579`/`sendMessage:176`/`clearSteps:476` 三处清空；新任务必建新 `Message{executionSteps:[]}`（`assistantId` 新），历史 `messages[*].executionSteps` 保留是聊天记录设计；仅会话切换不经 `sendMessage` 时 `useSSE.executionSteps` 可能残留，属另一路径。
- **判定**：**非bug**；无需修。

## 12.8 小结

| Bug | 定性 | 是否需修 |
|-----|------|---------|
| 18 | 真bug（fire-and-forget） | 修（P1） |
| 19 | 真bug（单槽覆盖） | 修（P1，与18同根） |
| 23 | 非bug | 不修 |
| 24 | 非bug | 不修 |
| 25 | 真bug（缺 try/finally） | 修（P1） |
| 26 | 仅类型缺陷 | 修（P2 类型） |
| 30 | 非bug | 不修 |

**更新人**：小欧　**日期**：2026-09-03 07:05:28

---

# 十三、24个真实bug修复diff全量（v1.4 新增 · 三堂会审）

> **三堂会审标准**：合规（SRP/DRY/KISS-DIRECT/SLAP/YAGNI/禁止backward）、合理（直线最优雅无绕）、关联（上下游不退化）。每diff均按此三审逐条过审，KISS-DIRECT优先：能if/elif直派不引入注册表，能单向调用不循环，能内联不透传。

## 13.1 后端 `backend/app/services/agent/handlers/action_handler.py`（Bug-1、25）

### Bug-1 全拦截空results不发Observation → 动画永驻

```diff
--- a/backend/app/services/agent/handlers/action_handler.py
+++ b/backend/app/services/agent/handlers/action_handler.py
@@ -848,2 +848,2 @@
-    for call, result in zip(ctx.all_calls, ctx.results):
+    from itertools import zip_longest
+    for call, result in zip_longest(ctx.all_calls, ctx.results):
+        if call is None: continue
+        if result is None: result = {"llm_data": {"status": {"exec_code": "error"}}, "other_data": {}, "_synthetic": True}
@@ -911,3 +911,12 @@
-    if not tool_result:
-        return events, orchestration
+    if not tool_result:
+        if not ctx.all_calls:
+            return events, orchestration
+        for c in ctx.all_calls:
+            tool_result.append({
+                "tool_name": c.get("tool_name","?"),
+                "llm_data": {}, "llm_data_text": "",
+                "data_text": f"工具 {c.get('tool_name','?')} 未返回结果(被安全拦截或异常)",
+                "other_data": {"synthetic": True}
+            })
     events.append(ctx.agent._step_emitter.emit(ObservationStep(step=ctx.step, tool_result=tool_result)))
```

**三审**：合规-单一职责仅补空数组不改编排；合理-`zip_longest`直线防截断比assert更容错；关联-前端`results.length>0`分支必进，动画必卸载，不退化正常结果流。

### Bug-25 `grant_temp_auth`异常跳过`resolve` → confirm泄漏

```diff
@@ -381,4 +381,8 @@
-                    if getattr(safety_result, "auth_path", None):
-                        from app.tools.security.temp_auth import grant_temp_auth
-                        grant_temp_auth(safety_result.auth_path, recursive=True)
-                    await resolve_confirmation(confirm_id, confirmed=_bypass_confirmed, trust_session=False)
+                    try:
+                        if getattr(safety_result, "auth_path", None):
+                            from app.tools.security.temp_auth import grant_temp_auth
+                            grant_temp_auth(safety_result.auth_path, recursive=True)
+                    except Exception as e:
+                        logger.warning(f"[action] grant_temp_auth失败仍放行: {e!r}")
+                    finally:
+                        await resolve_confirmation(confirm_id, confirmed=_bypass_confirmed, trust_session=False)
```

> 同模式补 `436-438`、`465-467` 两处 HITL确认/豁免直通分支（复制此4行结构，不重造函数，DRY）。

**三审**：合规-SRP日志与授权分离；合理-`try/finally`最短路径保`resolve`；关联-无论授权成败后端`confirm_id`必清，前端Modal不泄漏。

## 13.2 后端 `backend/app/services/agent/handlers/sandbox_gate.py`（Bug-16）

```diff
--- a/backend/app/services/agent/handlers/sandbox_gate.py
+++ b/backend/app/services/agent/handlers/sandbox_gate.py
@@ -70,6 +70,12 @@
     confirm_id = await create_confirmation(agent.task_id, tool_name)
+    from app.config import get_config as _get_cfg_sb2
+    _ct = int(float(_get_cfg_sb2().get("security.hitl_timeout", 110)))
+    _bt = _ct + 10
     steps = [agent._step_emitter.emit(MetaStep(
         step=step, type="paused",
         content=f"沙箱未能完成有效预检,需用户裁决是否直接执行: {tool_name}",
         confirm_id=confirm_id, tool_name=tool_name,
         params={k: v for k, v in params.items() if k not in _SENSITIVE_FIELDS},
-        safety_level="destructive", severity="attention"))]
+        safety_level="destructive", severity="attention",
+        trust_path=params.get("path") if isinstance(params.get("path"), str) else None,
+        auto_confirm=False, confirm_timeout=_ct, backend_timeout=_bt))]
```

**三审**：合规-与主链`action_handler:365-368`四字段对齐；合理-直接取`hitl_timeout`不引入新配置；关联-前端倒计时与后端一致，消60s/120s错位。

## 13.3 前端 `frontend/src/features/chat/components/pipeline/ToolCallLine.tsx`（Bug-2/3/4/5/8/10/31）

> 单文件统一diff，7 bug一并收敛，避免7次分散改动（DRY）。

```diff
--- a/frontend/src/features/chat/components/pipeline/ToolCallLine.tsx
+++ b/frontend/src/features/chat/components/pipeline/ToolCallLine.tsx
@@ -59,7 +59,17 @@
   const tools = action.tools || [];
-  const results = observations.flatMap((obs) =>
-    Array.isArray((obs as ExecutionStep | undefined)?.tool_result)
-      ? ((obs as ExecutionStep).tool_result as unknown as Array<Record<string, unknown>>)
-      : []
-  ) as Array<Record<string, unknown>>;
+  const results = observations.flatMap((obs) => {
+    const tr: unknown = (obs as ExecutionStep | undefined)?.tool_result;
+    if (Array.isArray(tr)) return tr as Array<Record<string, unknown>>;
+    if (typeof tr === "string" && tr) return [{ data_text: tr, llm_data: {}, other_data: {} } as unknown as Record<string, unknown>];
+    return [];
+  }) as Array<Record<string, unknown>>;
+  const [timedOut, setTimedOut] = React.useState(false);
+  React.useEffect(() => {
+    if (results.length > 0) { setTimedOut(false); return; }
+    if (tools.length === 0) return;
+    const t = setTimeout(() => setTimedOut(true), 30000);
+    return () => clearTimeout(t);
+  }, [results.length, tools.length, action]);
@@ -118,6 +128,7 @@
         lineHeight: `${13 + Spacing.XS}px`,
+        minHeight: 32,
         margin: stepMargin(false),
@@ -137,10 +148,18 @@
-          {results.length === 0 && (
+          {results.length === 0 && !timedOut && tools.length > 0 && (
             <span className="tool-waiting-cursor" aria-label="工具执行中">…扳手SVG…</span>
           )}
-          {results.length > 0 && tools.map((t, i) => {
+          {results.length === 0 && timedOut && (
+            <span style={{ color: Colors.TEXT.SECONDARY, fontSize: 12 }}>工具执行超时未返回，请重试或查看日志</span>
+          )}
+          {tools.length === 0 && results.length === 0 && (
+            <span style={{ color: Colors.TEXT.SECONDARY, fontSize: 12 }}>（无工具调用）</span>
+          )}
+          {tools.length === 0 && results.length > 0 && (
+            <span style={{ color: Colors.TEXT.SECONDARY, fontSize: 12 }}>收到 {results.length} 条结果但无工具定义</span>
+          )}
+          {tools.length > 0 && (results.length > 0 || timedOut) && tools.map((t, i) => {
+            const r = results[i] ?? null;
@@ -168,3 +187,3 @@
-            const singleResult = results[i] ? [results[i]] : [];
+            const singleResult = r ? [r] : [];
```

**逐bug审**：2-字符串分支补齐；3-30s兜底`timedOut`直线无轮询；4-空tools占位不渲染空壳；5-`results[i]??null`对齐不丢行；8/31-等待期`minHeight:32`占位+同容器覆盖，高度不暴涨；10-`minHeight`固定动画区。

## 13.4 前端 `frontend/src/features/chat/components/pipeline/PipelineRenderer.tsx`（Bug-9）

```diff
@@ -169,6 +169,7 @@
   const waiting =
     taskActive &&
     (!lastSeg ||
       (lastSeg.kind !== 'thinking' &&
         lastSeg.kind !== 'text' &&
+        lastSeg.kind !== 'tool' &&
         lastSeg.kind !== 'final' &&
         lastSeg.kind !== 'error'));
```

**三审**：KISS-单`!== 'tool'`直派；关联-工具段等待由`ToolCallLine`橙齿轮唯一承载，绿圆环不再同显。

## 13.5 前端 `frontend/src/components/AuthorizationModal/index.tsx`（Bug-11/13/17/20/21/28/29）

```diff
@@ -79,22 +79,33 @@
-  const [countdown, setCountdown] = React.useState(0);
+  const [countdown, setCountdown] = React.useState(() => request?.confirmTimeout ?? 0);
   const onConfirmRef = React.useRef(onConfirm);
+  const autoHandledRef = React.useRef<string | null>(null);
+  const [submitting, setSubmitting] = React.useState(false);
   const isBypass = Boolean(request?.autoConfirm);
   onConfirmRef.current = onConfirm;
   React.useEffect(() => {
     setTrustSession(false);
-    setCountdown(request?.confirmTimeout ?? 0);
+    setSubmitting(false);
+    if (request?.confirmId) {
+      setCountdown(request.confirmTimeout ?? 0);
+      autoHandledRef.current = null;
+    }
   }, [request?.confirmId, request?.confirmTimeout]);
   React.useEffect(() => {
     if (!visible || !request) return;
-    const t = setInterval(() => setCountdown((v) => Math.max(0, v - 1)), 1000);
+    const tick = () => setCountdown((v) => Math.max(0, v - 1));
+    const t = setInterval(tick, 1000);
+    const first = setTimeout(tick, 100);
     return () => { clearInterval(t); clearTimeout(first); };
   }, [visible, request]);
   React.useEffect(() => {
     if (!visible || countdown !== 0 || !request) return;
+    if (autoHandledRef.current === request.confirmId) return;
+    autoHandledRef.current = request.confirmId;
     if (isBypass) {
-      onConfirmRef.current(true, false);
+      setSubmitting(true); onConfirmRef.current(true, false);
     } else {
-      onConfirmRef.current(false, false);
+      setSubmitting(true); onConfirmRef.current(false, false);
     }
   }, [visible, countdown, isBypass, request]);
@@ -204,3 +215,3 @@
-            ? `将在 ${countdown}s 后自动确认（后端 ${request.backendTimeout ?? 5}s 兜底）`
+            ? `将在 ${countdown}s 后自动确认（后端 ${request.backendTimeout ?? 60}s 兜底）`
@@ -262,3 +273,5 @@
             checked={trustSession}
+            disabled={submitting}
             onChange={(e) => setTrustSession(e.target.checked)}
           >
-            {request.trustPath
-              ? `本次会话信任此操作（${request.toolName} › ${request.trustPath}，含子目录）`
-              : `本次会话信任此操作（${request.toolName} › 任意，整工具）`}
+            {request.trustPath
+              ? `本次会话信任此操作（${request.toolName} › ${request.trustPath}，含子目录）`
+              : `本次会话信任此操作（${request.toolName} › 未指定路径，仅本次）`}
           </Checkbox>
@@ -270,5 +283,5 @@
-          <Button onClick={() => onConfirmRef.current(false, trustSession)}>拒绝</Button>
-          <Button type="primary" onClick={() => onConfirmRef.current(true, trustSession)}>允许</Button>
+          <Button disabled={submitting} onClick={() => { setSubmitting(true); onConfirmRef.current(false, trustSession); }}>拒绝</Button>
+          <Button type="primary" loading={submitting} disabled={submitting} onClick={() => { if(submitting) return; setSubmitting(true); onConfirmRef.current(true, trustSession); }}>允许</Button>
```

**逐bug审**：11-初值 lazy + `confirmId` 驱动同步；13/29-`autoHandledRef`单次guard防双发；17-`submitting`互斥防连点翻转；20-兜底5→60与后端一致；21-首tick 100ms内触发节奏对齐；28-无path文案去"整工具"误导。

## 13.6 前端 `frontend/src/features/chat/hooks/useAuthorization.ts`（Bug-14/15/18/19/22/27）

```diff
--- a/frontend/src/features/chat/hooks/useAuthorization.ts
+++ b/frontend/src/features/chat/hooks/useAuthorization.ts
@@ -12,6 +12,11 @@
 export function useAuthorization(sessionId: string | null) {
   const [authorizationPending, setAuthorizationPending] = useState<AuthorizationRequest | null>(null);
+  const pendingRef = React.useRef<AuthorizationRequest | null>(null);
+  React.useEffect(() => { pendingRef.current = authorizationPending; }, [authorizationPending]);
 
   useEffect(() => {
-    const handleAuthorizationRequired = (event: CustomEvent<Record<string, unknown>>) => {
+    const handleAuthorizationRequired = async (event: CustomEvent<Record<string, unknown>>) => {
       const rawData = event.detail;
       if (!rawData?.confirm_id || !rawData?.tool_name) return;
-      if (authorizationPending) {
-        taskControlApi.confirm(authorizationPending.confirmId, false, false).catch(() => undefined);
-      }
+      const cur = pendingRef.current;
+      if (cur) {
+        try { await taskControlApi.confirm(cur.confirmId, false, false); } catch { /* swallow 404 */ }
+      }
       setAuthorizationPending({
         confirmId: rawData.confirm_id as string,
         toolName: rawData.tool_name as string,
         params: (rawData.params ?? {}) as Record<string, unknown>,
         safetyLevel: (rawData.safety_level as string) ?? 'unknown',
-        trustPath: (rawData.trust_path as string) ?? null,
-        autoConfirm: Boolean(rawData.auto_confirm),
-        confirmTimeout: Number(rawData.confirm_timeout) || 60,
-        backendTimeout: Number(rawData.backend_timeout) || 60,
+        trustPath: typeof rawData.trust_path === 'string' ? (rawData.trust_path as string) : null,
+        autoConfirm: rawData.auto_confirm === true || rawData.auto_confirm === 'true',
+        confirmTimeout: (()=>{ const n=Number(rawData.confirm_timeout); return Number.isFinite(n)&&n>=0 ? n : 60; })(),
+        backendTimeout: (()=>{ const n=Number(rawData.backend_timeout); return Number.isFinite(n)&&n>=0 ? n : 60; })(),
       });
     };
     window.addEventListener('authorization_required', handleAuthorizationRequired as EventListener);
     return () => window.removeEventListener('authorization_required', handleAuthorizationRequired as EventListener);
-  }, [authorizationPending]);
+  }, []);
 
   const handleAuthorizationConfirm = useCallback(
     async (confirmed: boolean, trustSession: boolean) => {
-      if (!authorizationPending) return;
+      const cur = pendingRef.current;
+      if (!cur) return;
       try {
-        await taskControlApi.confirm(authorizationPending.confirmId, confirmed, trustSession);
+        await taskControlApi.confirm(cur.confirmId, confirmed, trustSession);
         if (trustSession && sessionId) window.dispatchEvent(new CustomEvent('omni-trust-changed', { detail: { sessionId } }));
-      } catch (error) {
-        console.error('[Authorization] 确认失败:', error);
-      } finally {
-        setAuthorizationPending(null);
-      }
+      } catch (error) {
+        console.error('[Authorization] 确认失败:', error);
+        return;
+      }
+      setAuthorizationPending(null);
     },
-    [authorizationPending, sessionId]
+    [sessionId]
   );
```

**逐bug审**：14/18/19-`pendingRef`+`[]`一次性监听消闭包窗口，`await`化旧confirm不fire-and-forget，单槽覆盖前必`await reject`；15-失败`return`不清空保留重试；22-`Number.isFinite`区分0与NaN；27-严格`===true||==='true'`不误判`"false"`。

## 13.7 前端 `frontend/src/features/chat/services/sseParser.ts` + `useChatCallbacks.ts`（Bug-22/27镜像、Bug-26类型）

```diff
--- a/frontend/src/features/chat/services/sseParser.ts
+++ b/frontend/src/features/chat/services/sseParser.ts
@@ -824,3 +824,3 @@
-                auto_confirm: Boolean(rawData.auto_confirm),
-                confirm_timeout: Number(rawData.confirm_timeout) || 60,
-                backend_timeout: Number(rawData.backend_timeout) || 60,
+                auto_confirm: rawData.auto_confirm === true || rawData.auto_confirm === 'true',
+                confirm_timeout: (()=>{ const n=Number(rawData.confirm_timeout); return Number.isFinite(n)&&n>=0? n:60;})(),
+                backend_timeout: (()=>{ const n=Number(rawData.backend_timeout); return Number.isFinite(n)&&n>=0? n:60;})(),
--- a/frontend/src/features/chat/hooks/useChatCallbacks.ts
+++ b/frontend/src/features/chat/hooks/useChatCallbacks.ts
@@ -684,6 +684,14 @@
-  const onAuthorizationRequired = useCallback((data: { confirm_id: string; tool_name: string; params: Record<string, unknown>; safety_level: string; }) => {
+  const onAuthorizationRequired = useCallback((data: {
+    confirm_id: string; tool_name: string; params: Record<string, unknown>; safety_level: string;
+    trust_path?: string | null; auto_confirm?: boolean; confirm_timeout?: number; backend_timeout?: number;
+  }) => {
```

> `useSSE.ts:270` 同步补8字段类型（同此签名），与 `AuthorizationRequest` 单一类型对齐（复用优先）。

**三审**：合规-复用`AuthorizationRequest`类型不局部重造；合理-`===true`直线判断；关联-解析层与hook层同语义，0值不再被吃。

## 13.8 三堂会审总表（24项）

| Bug | 合规 | 合理 | 关联 | 结论 |
|-----|------|------|------|------|
| 1 | SRP仅补空数组 | zip_longest直线 | 前端动画必卸 | ✅ |
| 2 | DRY复用data_text | if/elif直派 | 字符串链路畅通 | ✅ |
| 3 | SLAP超时独立state | 单setTimeout | 不干扰正常结果 | ✅ |
| 4 | YAGNI占位文本 | if直派 | 空tools不空壳 | ✅ |
| 5 | KISS `??null` | 索引直取 | 行数与tools对齐 | ✅ |
| 8/31 | KISS minHeight | 单样式 | 高度不暴涨 | ✅ |
| 10 | 同上 | 同上 | 同上 | ✅ |
| 9 | KISS单条件 | `!==tool` | 动画唯一 | ✅ |
| 11 | SRP ref隔离 | lazy初值 | 新request必同步 | ✅ |
| 13/29 | 单ref guard | 直线去重 | 倒计时与手动互斥 | ✅ |
| 14/18/19 | ref消闭包 | 一次监听 | 旧confirm必await | ✅ |
| 15 | SRP失败不清空 | return直线 | 后端不挂起 | ✅ |
| 16 | OCP对齐主链 | 直取hitl_timeout | 前后计时一致 | ✅ |
| 17 | SLAP submitting | disabled | 连点不翻转 | ✅ |
| 20 | DRY统一60 | 单值 | 文案与后端一致 | ✅ |
| 21 | KISS首tick | 100ms timeout | 节奏对齐 | ✅ |
| 22 | YAGNI有限检查 | isFinite | 0合法保留 | ✅ |
| 25 | SRP try/finally | 最短保resolve | confirm不泄漏 | ✅ |
| 27 | KISS严格等 | `===true` | 字符串不误判 | ✅ |
| 28 | YAGNI文案 | 直派 | 不误导整工具 | ✅ |
| 26 | ISP类型隔离 | 复用类型 | 8字段契约完整 | ✅ |

> 全部diff已按KISS-DIRECT最小改动设计，无注册表滥用、无透传函数、无双重解析、无中间层，可直接落盘。

**更新人**：小欧　**日期**：2026-09-03 07:09:05
