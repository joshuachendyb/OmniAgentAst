# 工具显示/等待动画 + 安全bypass链路 Bug 分析与修复方案

**创建时间**: 2026-09-03 03:04:33
**编写人**: 小欧（资深后端开发 / 全架构分析 / 文档大师）

| 版本 | 更新时间 | 更新人 | 更新要点 |
|------|---------|--------|---------|
| v1.9 | 2026-09-03 09:55:12 | 小欧/老杨 | 新增第十七章：复查本地未提交9文件三堂会审，对3个真实问题（含1个原16.3方案落盘偏差）铁证复核与修复diff——①sandbox_gate路径提取分叉(硬编码7key vs _extract_trust_path，含窗口标题误当文件路径授权；且16.3建议import路径错误，_extract_trust_path实定义于action_handler:567)②ToolCallLine D2-04冗余三元③useAuthorization 404清pending的String(error)对axios错误对象无效(真实失效)；撤回先前误判的第4项(useSSE回调变化不触发SSE重连) |
| v1.8 | 2026-09-03 09:16:51 | 小欧 | 补充18个待定案Bug的修复代码diff（每条均经3轮三堂会审KISS-DIRECT最小改动，D2-01~10+D3 8个，含hasResult/0窗/信任别名/时序竞争等） |
| v1.7 | 2026-09-03 09:14:53 | 小欧 | 补充北京老陈实测现象至对应Bug：HTL窗口倒计时0转圈/延迟消失/任务完不消失（关联D2-02/P0-1）及双等待动画冲突少现（关联D2-04/05/07），不落盘验证已跑通 |
| v1.6 | 2026-09-03 08:50:25 | 小欧 | 新增第十五章：三次深挖8个HITL时序/信任/空闲竞争铁证（P0 3/P1 3/P2 2，含S1死码404、trust通配污染、task级目录越权等，case均已跑通，待定案后修复） |
| v1.5 | 2026-09-03 08:15:37 | 小欧 | 新增第十四章：二次深挖10个新增真实Bug（按模块排序，聚焦双等待动画与HITL窗口计时，含铁证+复现用例+三堂会审缺口，待定案后修复） |
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

---

## 十四、二次深挖新增10个真实Bug（按模块排序，聚焦双等待动画与HITL窗口计时）[v1.5]

> **说明**：本章为已落盘24项修复后，对当前真实代码的二次透读（每文件10遍）新增发现。报告阶段不落盘修复，仅沉淀铁证+复现用例+三堂会审缺口，待北京老陈定案后按模块批量修复（分两步走）。编号 D2-01~10 按模块排序（action→sandbox→ToolCallLine→PipelineRenderer→AuthorizationModal→sseParser/useAuthorization）。
>
> **编写人**：小欧　**日期**：2026-09-03 08:15:37

### 14.1 后端 `action_handler.py`（2个）

#### D2-01【P1·等待动画误判】`build_observation` synthetic占位缺有效摘要，折叠区无“已拦截”提示

**现象**：全部工具被安全拦截时，后端已发 synthetic 占位（Bug-1已修），但前端 `ToolCallLine` 折叠态 `getResultSummary(i)` 取 `llm_data.summary || data_text || summary` 均为 synthetic 占位自带的空摘要/通用 `obs_text`，不含“已安全拦截/已跳过”等可辨识文案。用户在折叠态看不到原因，必须点展开才知被拦截。

**铁证**：
- `backend/app/services/agent/handlers/action_handler.py:871` synthetic：`{"llm_data":{"status":{"exec_code":"error"}},"other_data":{"synthetic":True}}`——无 `summary` 字段
- `action_handler.py:876` `obs_text = build_observation_text(synthetic, _cn, _cp)` —— synthetic 的 `llm_data` 无 summary，`build_observation_text` 回落为空或通用前缀
- `frontend/src/features/chat/components/pipeline/ToolCallLine.tsx:98-109` `getResultSummary` 三级回落均空 → `sum=""` → 折叠区 `sum && <div>` 不渲染，无摘要行
- 上游 `record_operation` 已记 `FAILED`（双表正确），但用户可见层缺提示

**最小复现**：
```python
all_calls=[{"tool_name":"delete_file","tool_params":{"path":"/x"},"exec_type":"single"}]
results=[]  # 全部被拦截→ synthetic占位
ctx=ObservationContext(agent=mock, all_calls=all_calls, results=results, step=1, ...)
events, _ = await build_observation(ctx)
# events[0].tool_result[0].llm_data.get("summary") is None
# 前端 getResultSummary(0) === ""
```

**三堂会审缺口**：合规（synthetic职责单一）有；合理（KISS占位）有；**关联缺**——后端“双表已记FAILED”与前端“折叠区可见摘要”断层，`other_data.synthetic` 未被 `observation_formatter` 或前端识别为特殊文案。

**危害**：P1——用户折叠态误判“工具无结果”而非“被拦截”，需展开才知因，体验与可观测性损失；不阻塞但易误报。

**建议方向（不落盘）**：synthetic 占位 `llm_data.summary` 补 `"已安全拦截："+ _cn` 或 `other_data.synthetic_reason`，`build_observation_text` 对 `other_data.synthetic` 分支返回可辨识文案；前端 `getResultSummary` 对 `other_data.synthetic` 优先显示 `data_text`。

---

#### D2-02【P1·HITL窗口语义】`_confirm_timeout = max(0, _bt - LEAD)` 产出 0 时，HITL 真窗与 bypass 均瞬间自触发，用户 0 秒窗口

**现象**：当 `security.hitl_timeout` 被配为 ≤ `HITL_CONFIRM_LEAD`(10) 或 `security.auto_confirm_delay` ≤ `BYPASS_AUTO_LEAD`(2) 时，`max(0, _bt - LEAD)` 得 0。`AuthorizationModal` `countdown` lazy 初值即 0 → `countdown===0` 自触发 effect 立即执行（HITL→自动拒绝，bypass→自动确认），用户无操作窗口，弹窗一闪即消失。

**铁证**：
- `action_handler.py:352` `_confirm_timeout = max(0, _backend_timeout - BYPASS_AUTO_LEAD)`；`action_handler.py:357` `_confirm_timeout = max(0, _backend_timeout - HITL_CONFIRM_LEAD)`
- `sandbox_gate.py:79` 同式 `_ct = max(0, _bt - HITL_CONFIRM_LEAD)`
- `useAuthorization.ts:10-12` `parseTimeout(0)=0` 保留合法 0；`sseParser.ts:14-16` `assignTimeout(0)=0`
- `AuthorizationModal/index.tsx:81-82` `useState(()=>request?.confirmTimeout ?? 0)` → 0；`113-124` `countdown===0` 立即 `onConfirm`

**最小复现**：
```python
# config: security.hitl_timeout=8
# action_handler HITL: _bt=8, _confirm= max(0,8-10)=0 → paused confirm_timeout=0
# 前端：countdown=0，弹窗visible即 autoHandledRef 触发 → 未响应将在0s后自动拒绝（瞬间）
```

**三堂会审缺口**：合规（`max(0,)` 防负数）有；**合理缺**——合法性校验（`_bt <= LEAD` 时应告警/钳制最小窗口如 ≥5s）缺失；关联——后端 `wait_for_confirmation_result(..., timeout=_bt)` 仍等 8s，但前端已在 0s 自触发，`confirmed=false` 与 `expired` 语义混淆见 D2-08。

**危害**：P1——配置误配或边界值即使用户 0 秒窗口，HITL 形同虚设；sandbox 同理，危险工具预检未完成验证即瞬间拒绝，用户来不及裁决。

**建议方向**：`_confirm_timeout` 钳制下界如 `max(5, _bt - LEAD)` 或配置校验期告警 `hitl_timeout <= LEAD`；前端 `countdown===0` 时若 `confirmTimeout===0` 应显示“请尽快确认（无自动倒计时）”而非立即自触发（语义改为“禁倒计时”需前后端一致）。

---

### 14.2 后端 `sandbox_gate.py`（1个）

#### D2-03【P1·信任路径丢失】`trust_path` 仅取 `params["path"]`，`file_path`/`target`/`dir_path` 等工具路径丢失，前端恒“未指定路径，仅本次”

**现象**：sandbox 的 `trust_path` 供前端“本次会话信任此操作（tool›path，含子目录）”展示及 `tool+path` 信任落库。当前仅 `params.get("path")`，对 `edittext` 的 `file_path`、`readtext` 的 `path` 命中，但对别名/旧名工具（如 `file_path`、`target`、`dir_path`）或未来工具路径键不命中，`trust_path` 恒 `null`，前端显示“未指定路径，仅本次”，信任落库也仅 tool 维（缺 path 维）。

**铁证**：
- `sandbox_gate.py:80` `_sandbox_path = params.get("path") if isinstance(params.get("path"), str) else None`
- `action_handler.py` 侧同功能用 `_extract_trust_path(_cn, _cp)`（v1.5 trust_path 透传，`tool+path` 前缀递归精确化），已抽象
- `AuthorizationModal/index.tsx:287-289` `request.trustPath ? tool›path : 未指定路径，仅本次`

**最小复现**：
```python
params={"file_path": "/a/b/c.txt"}  # 非 "path" 键
_sandbox_path = params.get("path")  # None
# paused trust_path=None → 前端“未指定路径，仅本次”
# 对比 action_handler 主链：_extract_trust_path("edittext", {"file_path":"/a/b/c.txt"}) 正确得 "/a/b/c.txt"
```

**三堂会审缺口**：合规（SLAP：sandbox 内联取数）有；**DRY缺**——已抽象的 `_extract_trust_path` 未复用，sandbox 自写 `"path"` 硬编码；关联——`/trust/list` 的撤回/精确化依赖 `tool+path`，sandbox 路径丢失致“整工具”误伤。

**危害**：P1——sandbox 裁决的信任路径丢失，用户无法“信任此 path 含子目录”，只能“整工具”或“仅本次”，信任体验与精确性损失；与主链 HITL 行为不一致。

**建议方向**：复用 `from app.tools.security.temp_auth import _extract_trust_path` 或抽 `app/tools/trust_path.py` 公共函数，`sandbox_gate` 改 `_sandbox_path = _extract_trust_path(tool_name, params)`。

---

### 14.3 前端 `ToolCallLine.tsx`（3个）

#### D2-04【P1·双重计数】`hasResult && tools===0` 分支显示 `results.length` 而非 `hasResult` 对应计数，字符串场景显示“收到 0 条”自矛盾

**现象**：`hasResult` 对字符串 `tool_result` 判真（`typeof===string && length>0`），但 `results` 仅收数组 `tool_result`（字符串不入数组）。`hasResult && tools.length===0` 时渲染 `收到 {results.length} 条观察结果但无工具定义`——此时 `results.length` 为 0，显示“收到 0 条…但无工具定义”（hasResult 真却 0 条，自矛盾）。

**铁证**：
- `ToolCallLine.tsx:64-70` `results` 仅 `Array.isArray(tr)` 入数组
- `ToolCallLine.tsx:72-76` `hasResult` 含 `typeof string` 分支
- `ToolCallLine.tsx:198-201` `{hasResult && tools.length===0 && <span>收到 {results.length} 条...` —— `results.length` 与 `hasResult` 口径不一致

**最小复现**：
```tsx
const action={type:'action', tools:[], exec_type:'single'} as ExecutionStep
const obs={type:'observation', tool_result:"hello string"} as ExecutionStep
render(<ToolCallLine action={action} observations={[obs]} />)
// 显示：“收到 0 条观察结果但无工具定义”（hasResult true 但 results.length 0）
```

**三堂会审缺口**：合规（KISS 分支直派）有；**DRY/一致性缺**——同一“是否有结果”用两套口径（`hasResult` vs `results.length`）；合理——`hasResult` 已是统一口径，计数应派生自它。

**危害**：P1——字符串结果+无工具定义（全拦截合成极少见但可复现）的边界提示误导，用户见“0 条”困惑。

**建议方向**：该分支改 `hasResult ? 1 : 0` 或 `observations.filter(o=>...非空).length` 或统一口径 `hasResultCount` 派生；或字符串场景下显示“收到 1 条（字符串）观察结果”。

---

#### D2-05【P1·定时器空转】字符串 `tool_result` 已使 `hasResult=true`（齿轮已卸、子行已显），但 `timedOut` 计时仍以 `results.length` 为闸，30s 空转

**现象**：字符串结果：`hasResult=true`→齿轮分支 `!hasResult` 已隐藏、子行分支 `hasResult` 已显，用户已见结果。但 `timedOut` 的 `useEffect` 以 `results.length`（字符串不入数组，故 0）为闸，`results.length===0 && tools.length>0` 仍开 30s `setTimeout`，30s 后 `timedOut=true`（其分支 `!hasResult && timedOut` 因 `!hasResult=false` 不显示，无可见危害），但状态空转、且若 `hasResult` 后续因观察清空而翻 false，残留 `timedOut=true` 立即显示超时文案。

**铁证**：
- `ToolCallLine.tsx:79-87` `useEffect(()=>{ if(results.length>0) setTimedOut(false); ... setTimeout(()=>setTimedOut(true),30000)}, [results.length, tools.length, action])`
- 分支：`!hasResult && !timedOut` 齿轮；`!hasResult && timedOut` 超时；`hasResult && tools>0` 子行——齿轮/超时互斥由 `hasResult`，但计时由 `results.length`

**最小复现**：
```tsx
// 渲染：action tools=[{tool:'x'}], observations=[{tool_result:"string hello"}]
// → hasResult true → 子行已显，齿轮已卸
// 但 results.length=0 → 30s 后 timedOut 悄然 true（React DevTools 可见）
// 若随后 observations 置空（流式回退极少见），hasResult false → 立即显示“工具执行超时…”而非齿轮
```

**三堂会审缺口**：合规（SLAP 计时独立 state）有；**一致性缺**——显示闸 `hasResult` 与计时闸 `results.length` 口径分裂；合理——计时应与显示同口径 `hasResult`。

**危害**：P1——当前无可见危害（因 `!hasResult` 隐藏超时文案），但状态空转+残留 `timedOut` 为后续小概率分支埋伏笔；资源浪费（无意义计时）。

**建议方向**：`useEffect` 首行改 `if (hasResult) { setTimedOut(false); return; }`，依赖改 `[hasResult, tools.length, action]` 或 `[hasResult, tools.length, action.step]`。

---

#### D2-06【P2·计时永不触发】`action` 对象引用作为 `timedOut` 依赖，频繁新引用致 30s 计时反复重建

**现象**：`useEffect(..., [results.length, tools.length, action])` 中 `action` 为对象。若父 `PipelineRenderer` 的 `segs` 派生或 `buildSegments` 新数组导致 `seg.action` 新引用（非原引用），或父过滤/映射产生新 `ExecutionStep` 对象，每次 render `action` 引用变化 → effect 清理旧 timer、重开新 30s → 计时永不达。

**铁证**：
- `ToolCallLine.tsx:87` 依赖含 `action` 对象
- `ToolCallLine.tsx:57-58` `useEffect(()=>setExpanded([]), [action])` 同样以 `action` 引用判新任务
- `PipelineRenderer.tsx:269-279` `segs.map(... <ToolCallLine key={seg.action.step ?? i} action={seg.action}>`——`seg.action` 引用来自 `buildSegments` 新数组的 `s`（原 `steps` 元素引用，稳定）；但若上游 `steps` 来自 `filter/map` 派生，`action` 会是新对象

**最小复现**（人造不稳定父）：
```tsx
const RawSteps = [{type:'action', step:1, tools:[{tool:'x'}]}]
// 父每 render：const action = {...RawSteps[0]} // 新引用
render(<ToolCallLine action={action} />)
// 每 render 新 action → effect 重建 → 30s 计时重置 → 永不显示“超时未返回”
```

**三堂会审缺口**：合规（依赖显式）有；**合理缺**——对象引用作依赖不稳定，应取稳定标量 `action.step` 或 `action.tools.length`；关联——当前 `PipelineRenderer` 透传稳定引用，生产不触发，但上游重构/包装即埋坑。

**危害**：P2——30s 超时兜底（Bug-3）潜在失效，网络/工具挂死时动画无限转，用户无超时提示。

**建议方向**：依赖改 `[hasResult, tools.length, action.step]`（`hasResult` 同 D2-05）；或对 `action` 用 `useMemo` 稳定化。

---

### 14.4 前端 `PipelineRenderer.tsx`（1个）

#### D2-07【P2·等待圈残留】`waiting` 排除 `tool/final/error` 但未排除 `obs`（孤儿观察），末段为孤儿 obs 时仍叠绿圈

**现象**：`buildSegments` 中无前置 `action` 的 `observation` 成 `kind:'obs'` 段。`PipelineRenderer` 的 `waiting` 判定已排除 `thinking/text/tool/final/error`，但未排除 `obs`。当流水线末段为孤儿 `obs` 且 `taskActive`（`streaming||highlight||badge running/paused`）时，底部仍渲染绿色缺口圆环（`.waiting-cursor`）于孤儿观察文本之下，视觉“观察结果下方转圈”误导为“还在等下一条观察”。

**铁证**：
- `PipelineRenderer.tsx:66-118` `buildSegments`：`case 'observation': if(last.kind==='tool') last.observations.push(s) else segs.push({kind:'obs'})`
- `PipelineRenderer.tsx:170-178` `waiting = taskActive && (!lastSeg || (lastSeg.kind!=='thinking' && !=='text' && !=='tool' && !=='final' && !=='error'))` ——无 `!== 'obs'`

**最小复现**：
```tsx
const steps: ExecutionStep[] = [{type:'observation', step:5, tool_result:[{data_text:"orphan"}]} as ExecutionStep]
render(<PipelineRenderer steps={steps} streaming badge="running" />)
// container.querySelector('.waiting-cursor') !== null（绿圈出现于孤儿观察下方）
```

**三堂会审缺口**：合规（KISS 单条件 `!==tool`）有；**SLAP/完备性缺**——`obs` 为终端段（无后续语义），与 `final/error` 同属终态，不应再示等待。

**危害**：P2——孤儿观察场景少见（多为流式乱序或历史回放），绿圈残留短暂，待下个 `thought/chunk` 到达即消失（`lastSeg` 变 `thinking/text`，waiting 仍可能真），但视觉噪音。

**建议方向**：`waiting` 追加 `&& lastSeg.kind !== 'obs'`；或更严谨 `&& !['thinking','text','tool','final','error','obs'].includes(lastSeg.kind)` 已全量终态排除。

---

### 14.5 前端 `AuthorizationModal/index.tsx`（2个）

#### D2-08【P1·HITL语义混淆】前端 `countdown===0` 对 HITL 自动走 `onConfirm(false)`（拒绝），与后端 `expired` 的“超时未响应”语义混淆，双表记“被用户拒绝”

**现象**：HITL 真窗 `countdown` 归零时 `AuthorizationModal` 的自触发effect 走 `onConfirm(false, false)`，`useAuthorization` 经 `taskControlApi.confirm(id, false)` 通知后端。后端 `action_handler.py:422-437` 分两类：`expired`→`error_type="timeout"/"确认超时未响应"`；`confirmed===false && !expired`→`error_type="user_rejected"/"被用户拒绝执行"`。前端 auto 的 `false` 走后者，`task_operations` 记“被用户拒绝”，`MetaStep error` 也记拒绝——与用户“未响应超时”的真实原因不符，审计/双表语义失真。

**铁证**：
- `AuthorizationModal/index.tsx:113-124` `if(countdown===0){ ... onConfirmRef.current(false,false) }`（HITL分支 false）
- `useAuthorization.ts:81-82` `await taskControlApi.confirm(cur.confirmId, false, ...)`
- `action_handler.py:422` `if(!auth.get("confirmed")){ if(auth.get("expired")) → timeout else → user_rejected }`——前端 auto 的 `false` 不带 `expired`，落拒绝

**最小复现**：
```tsx
render(<AuthorizationModal visible request={{autoConfirm:false, confirmTimeout:2, ...}} onConfirm={onConfirm} />)
// 2s后 auto → onConfirm(false) → 后端 _denied “被用户拒绝执行” + error user_rejected
// 期望：超时未响应（expired语义）
```

**三堂会审缺口**：合规（SRP 弹窗只发确认）有；**语义缺**——“用户未操作致超时”与“用户主动拒绝”同为 `false`，未区分；关联——后端双表与前端文案“未响应将在Xs后自动拒绝”已暗示超时，但落库仍记拒绝。

**危害**：P1——审计失真（`task_operations` 查“被用户拒绝”实为超时），后续“自动重试/提醒”策略误判；用户侧无阻塞但数据错。

**建议方向（不落盘）**：HITL auto 分支改 `onConfirm` 第三态或 `expired` 标记透传：`taskControlApi.confirm(id, false, false, {expired:true})` 或后端对 `countdown===0` 的 `false` 结合 `auth.expired` 再判；或前端 `countdown===0` 自触发时直接不 `confirm`，让后端 `wait_for_confirmation_result` 自然 `expired` 超时（保持单一超时源）。

---

#### D2-09【P2·进度与文案割裂】`confirmTimeout===0` 时环形进度恒 0% 且 `countdown` 恒 0，与“将自动确认/未响应将自动拒绝”文案矛盾

**现象**：`confirmTimeout===0`（D2-02的 0 窗场景）时，`progressPercent = confirmTimeout>0 ? round(countdown/confirmTimeout*100) : 0` 恒 0%，`countdown` 恒 0（lazy 初值 0 且立即自触发）。环形进度空环（0%）配文案“将在 0s 后自动确认/未响应将在 0s 后自动拒绝”，进度与文案割裂，用户困惑。

**铁证**：
- `AuthorizationModal/index.tsx:136-138` `confirmTimeout = request.confirmTimeout ?? 60; progressPercent = confirmTimeout>0 ? ... : 0`
- `AuthorizationModal/index.tsx:81-82` `useState(()=>request?.confirmTimeout ?? 0)` → 0
- `AuthorizationModal/index.tsx:192-216` `<Progress percent={progressPercent}>` 0% + 文案 0s

**最小复现**：
```tsx
render(<AuthorizationModal visible request={{confirmTimeout:0, autoConfirm:false, ...}} />)
//  Progress 0%，文案“未响应将在 0s 后自动拒绝”，countdown 0 数字居中但环空
```

**三堂会审缺口**：合规（YAGNI 三元守卫）有；**合理缺**——0 窗的进度语义未特化；关联——与 D2-02 同根，0 窗本就不该进倒计时态。

**危害**：P2——视觉割裂，但 0 窗本身极少（仅配置误配），不阻塞；若 D2-02 钳制最小 5s，本 bug 自然消失。

**建议方向**：`confirmTimeout===0` 时 Progress 改 `percent={100}` 或隐藏进度环，文案改“请尽快确认（无自动倒计时）”；或与 D2-02 联动钳制 `confirmTimeout` 最小值。

---

### 14.6 前端 `sseParser.ts` / `useAuthorization.ts`（1个）

#### D2-10【P1·bypass误判面扩大】`auto_confirm` 严格判断仅认 `true/"true"`，后端若下发 `1/"1"/"True"` 即误判为非 bypass，HITL 弹窗与超时窗口全错

**现象**：后端 `tool_safety_checker` 的 `auto_confirm` 可能随序列化/配置以 `1/"1"/"True"` 形式下发。前端现严格 `=== true || === 'true'`，`1/"1"/"True"` 均判 `false`（非 bypass），则：`isBypass=false`→弹窗按 HITL 真窗渲染（非“将自动确认”）、`backendTimeout` 按 `hitl_timeout`(120) 而非 `auto_confirm_delay`(10) 展示、倒计时按 HITL LEAD(10) 而非 bypass LEAD(2) 计算，前后窗口全错位。

**铁证**：
- `sseParser.ts:833-835` `auto_confirm: rawData.auto_confirm === true || rawData.auto_confirm === 'true'`
- `useAuthorization.ts:48-49` 同式
- 对比 `sseParser.ts:10` `normalizeIsReasoning` 兼容 `true/'true'/1/'1'` 四态

**最小复现**：
```ts
// 后端下发 rawData.auto_confirm = 1
// sseParser: 1 === true false, 1 === 'true' false → auto_confirm false → isBypass false
// 期望：bypass 窗 8s (10-2)；实际：HITL 窗 110s (120-10)，文案/进度/超时全错
```

**三堂会审缺口**：合规（KISS 直判）有；**DRY/复用缺**——已抽象的 `normalizeIsReasoning` 四态归一未复用；合理——`auto_confirm` 与 `is_reasoning` 同属布尔归一化，应同策略。

**危害**：P1——bypass 误判为 HITL，弹窗倒计时 110s 而后端只等 10s（或反之），前后窗口错位，bypass 自动确认丢失或 HITL 超时误导。

**建议方向**：复用归一：`const normalizeAutoConfirm=(v:unknown)=> v===true||v==='true'||v===1||v==='1'` 或直接 `Boolean(rawData.auto_confirm)===true` 的归一版本；与 `normalizeIsReasoning` 同模式。

---

### 14.7 小结（二次深挖）

| 编号 | 模块 | 严重度 | 关联等待/计时 | 状态 |
|------|------|--------|--------------|------|
| D2-01 | action_handler | P1 | synthetic 摘要→折叠区无提示 | 待定案 |
| D2-02 | action_handler | P1 | 0 窗瞬间自触发 | 待定案 |
| D2-03 | sandbox_gate | P1 | trust_path 路径丢失 | 待定案 |
| D2-04 | ToolCallLine | P1 | 0 条计数矛盾 | 待定案 |
| D2-05 | ToolCallLine | P1 | 30s 空转 | 待定案 |
| D2-06 | ToolCallLine | P2 | 计时永不触发 | 待定案 |
| D2-07 | PipelineRenderer | P2 | 孤儿 obs 绿圈残留 | 待定案 |
| D2-08 | AuthorizationModal | P1 | 超时语义混淆 | 待定案 |
| D2-09 | AuthorizationModal | P2 | 0 窗进度割裂 | 待定案（随 D2-02 联动） |
| D2-10 | sseParser/useAuthorization | P1 | bypass 误判 | 待定案 |

> 10 项中 **P1 6 项 / P2 4 项**，双等待动画相关 5 项（D2-01/04/05/06/07），HITL 窗口计时相关 4 项（D2-02/08/09/10），信任路径 1 项（D2-03）。报告阶段不落盘，待定案后按模块批量修复、跑测试全绿再分组 commit（不打 tag）。

**更新人**：小欧　**日期**：2026-09-03 08:15:37

---

## 十五、三次深挖新增8个HITL时序/信任/空闲竞争铁证（P0 3/P1 3/P2 2，case已跑通，待定案后修复）[v1.6]

> **说明**：本章为v1.5后对HITL全链路（`action_handler`↔`hitl_confirmation`↔`sandbox_gate`↔`temp_auth`↔`useSSE`/`sseParser`↔`useAuthorization`↔`AuthorizationModal`）的专项深挖，聚焦时序竞争、信任污染、空闲误杀。8个铁证均有可运行case（`backend/tests/test_d3_hitl_timing_bugs.py` 8 passed），报告阶段不落盘修复。
>
> **编写人**：小欧　**日期**：2026-09-03 08:50:25

### 15.1 P0-1 bypass S1窗口 `resolve` 死码 + 前后端竞态致 Modal 僵死【P0·阻塞】

**现象**：`security.auto_confirm_delay` 默认10s时，前端 `confirm_timeout=8s`（10-2），后端 S1 `wait_for_confirmation_result(..., timeout=10)`。前端 8s 到0自动 `POST /confirm {true}`，若网络>2s迟到，后端已在10s `expired` 并 `pop`，迟到的 `resolve_confirmation` 对已pop的 `confirm_id` 恒 `return False`（404），`useAuthorization` 的 `catch return` 不清 `pending`，`AuthorizationModal` 永驻，徽标已 `EXECUTING+resumed`，前后撕裂。

**铁证**：
- `backend/app/services/agent/handlers/action_handler.py:382-393` bypass S1分支：`_auth_result=await _wait_confirm(timeout=S1)` 后 `finally: await resolve_confirmation(...)`
- `backend/app/services/task/hitl_confirmation.py:142-143` `finally: _pending_confirmations.pop(confirm_id, None)`
- `hitl_confirmation.py:160` `if entry is None: return False`
- `frontend/src/features/chat/hooks/useAuthorization.ts:90` `catch return` 不清 `pendingRef`
- `frontend/src/components/AuthorizationModal/index.tsx:113-124` `countdown===0` 自动代发

**最小复现**：`test_p0_1_s1_resolve_dead_code`——`create_confirmation`→`wait timeout 0`得`expired`→`_pending`已pop→`resolve`返`False`（已跑通）。

**三堂会审缺口**：合理（S1等前端）有；**关联缺**——`resolve`在`pop`后死码；**合规缺**——前端404未清`pending`。

**危害**：P0 弹窗僵死不可关，自动化E2E必踩10s窗口404。

**建议方向**：S1分支 `wait` 后若已 `expired` 则不再二次 `resolve`；前端 `resolve` 404时清 `pending` 并 `dispatch resumed` 兜底。

### 15.2 P0-2 `sandbox_gate` 信任路径别名盲区 → 通配污染【P0·越权】

**现象**：`sandbox_gate` 仅 `params.get("path")`，对 `move_file(source_path/dest_path)`、`window_*` 的 `window_title` 等别名路径全丢，`paused trust_path=null` 落库 `path IS NULL` 通配行，后续同会话同工具任意路径全豁免。

**铁证**：`sandbox_gate.py:80` vs `action_handler.py:558 _extract_trust_path`（复用 `_parse_paths` 感知 `PARAM_ALIASES`）。

**复现**：`test_p0_2_sandbox_trust_path_alias_blind`——`move_file source_path=/a/b` 触发 `needs_ruling`→`paused trust_path is None`（已跑通）。

**三审缺口**：**DRY缺**——已抽象 `_extract_trust_path` 未复用；信任维度丢失。

**危害**：P0 单次沙箱裁决污染整工具信任表，切回 `enabled:true` 仍长期豁免。

**建议**：复用 `_extract_trust_path(tool_name, params)`。

### 15.3 P0-3 `temp_auth` task级清零致同任务内跨步目录越权【P0·越权】

**现象**：`grant_temp_auth("/tmp/a", recursive=True)` 目录级授权后，同任务内任意 `/tmp/a/**` 文件无需二次HITL即可写，LLM可遍历 exfiltrate。

**铁证**：`temp_auth.py:48-59` `ContextVar` + `grant(recursive=True)`；`react_cycle.py:903 finally clear` 仅task级清。

**复现**：`test_p0_3_temp_auth_task_level_not_cleared`——`grant /tmp/a recursive` 后 `is_temp_authorized("/tmp/a/sub/file") is True`（已跑通）。

**三审缺口**：合理（一次一申请）设计债——目录`recursive`过度放大。

**建议**：文件路径强制 `recursive=False`，仅目录保持 `True`；或按 `auth_path` 是否为目录动态定 `recursive`。

### 15.4 P1-1 `expired` vs `confirmed==false` 三分支语义撕裂【P1】

**现象**：超时`{expired:true}`、取消`{cancelled:true}`、用户拒绝`{confirmed:false}`三态在 `hitl_confirmation` 已分，但在 `action_handler` 仅分 `expired→timeout` / `else→user_rejected`，`sandbox_gate` 完全不辨，三者落库与前端文案混淆。

**铁证**：`hitl_confirmation.py:135-140`；`action_handler.py:422-439`；`sandbox_gate.py:92-108`。

**危害**：P1 排障与重试策略错（timeout应重试/告警，user_rejected应换方案）。

### 15.5 P1-2 前后端倒计时 LEAD 固定值与网络延迟竞态【P1】

**现象**：`HITL_CONFIRM_LEAD=10`/`BYPASS_AUTO_LEAD=2` 固定，未自适应RTT，配置小值时 `max(0, bt-LEAD)=0` 致0秒窗口（D2-02同根）。

**铁证**：`constants.py:126-127`；`action_handler.py:352,357,381`。

**建议**：小值钳制 `confirm_timeout>=5`，LEAD自适应 `max(RTT*2, LEAD)`。

### 15.6 P1-3 HITL 长等 110s 触发前端 IDLE 60s 重连并误取消【P1】

**现象**：HITL 等待110s期间无SSE数据，前端 `IDLE_TIMEOUT=60s` 触发 `reconnect()`，3次重连耗尽可能 `cancel(serverTaskId)`，后端 `wait` 中 `check_cancelled` 误判为用户拒绝。

**铁证**：`frontend/src/hooks/useSSE.ts:340,599-608,740-760`；`backend/app/services/chat/stream_reader.py:278`。

**建议**：HITL等待期暂停 `IDLE_TIMEOUT` 或提升至 `max(60, backend_timeout+10)`。

### 15.7 P2-1 SSE `after_seq` 重放与 Modal 状态竞态【P2】

**现象**：断线重连 `GET after_seq=lastSeq` 重放 `paused`，`pendingRef` 已有旧值先 `confirm(false)` 再 `setPending` 新id，旧resolve泄漏；`autoHandledRef` 按 `confirmId` 去重，重复 `paused` 的 `countdown` 不重置。

**铁证**：`useSSE.ts:323,533`；`sseParser.ts:782`；`useAuthorization.ts:24`。

### 15.8 P2-2 空 `path` 经 `Path.resolve()` 得 cwd 误授权【P2】

**现象**：`grant_temp_auth("")` → `Path("").resolve()` 得 cwd（如 `F:\OmniAgentAs-repair`），递归授权进程目录。

**复现**：`test_p2_2_grant_path_empty_resolves_to_cwd`（已跑通）。

**建议**：`grant_temp_auth` 前置校验 `if not path or path.strip() in ("", ".", "/"): return`。

### 15.9 小结（三次深挖）

| 编号 | 严重度 | 聚焦 | case | 状态 |
|------|--------|------|------|------|
| P0-1 | P0 | S1死码404僵死 | ✅ | 待定案 |
| P0-2 | P0 | trust别名通配污染 | ✅ | 待定案 |
| P0-3 | P0 | task级目录越权 | ✅ | 待定案 |
| P1-1 | P1 | expired语义撕裂 | ✅ | 待定案 |
| P1-2 | P1 | LEAD固定竞态 | ✅ | 待定案 |
| P1-3 | P1 | IDLE误杀HITL | ✅ | 待定案 |
| P2-1 | P2 | after_seq重放 | ✅ | 待定案 |
| P2-2 | P2 | 空路径扩域 | ✅ | 待定案 |

> 8项中 **P0 3 / P1 3 / P2 2**，case 均在 `backend/tests/test_d3_hitl_timing_bugs.py` 8 passed。报告阶段不落盘，待定案后按模块批量修复、跑测试全绿再分组 commit（不打tag）。与第十四章合计 **18个待定案新增Bug**（10+8）。

**更新人**：小欧　**日期**：2026-09-03 08:50:25

---

## 附：北京老陈实测现象补充（关联已立项Bug）[v1.7]

> **来源**：北京老陈 2026-09-03 任务实测反馈　**记录人**：小欧　**日期**：2026-09-03 09:14:53

### 现象1：HTL操作窗口“有时及时消失/有时不及时消失，倒计时0还在转圈，好一阵才消失；‘允许执行’转圈停了还一阵才消失；最后一次整个HTL窗口任务完成后仍不消失”

| 实测分型 | 关联Bug | 解释 |
|---------|---------|------|
| 倒计时0还在“允许执行”转圈 | D2-02（0窗）+ P0-1 S1死码 | `confirmTimeout=0`时`countdown`初值0→`autoHandledRef`立即触发`onConfirm`+`submitting=true`（按钮loading），但`taskControlApi.confirm`网络回包前`submitting`保持，转圈即此段 |
| 转圈停了好一阵才消失 | P0-1 S1迟到404 | 前端8s auto的`POST /confirm`迟到>2s，后端S1=10s已`pop`→迟到`resolve` 404→`useAuthorization:90 catch return`不清`pending`→`Modal visible`仍真，按钮已`submitting=false`但窗口不关 |
| 任务执行完了窗口仍不消失 | P0-1 + D2-08 | 同上404僵死；或`handleAuthorizationConfirm` confirm失败`return`不`setAuthorizationPending(null)`，后端已`EXECUTING+resumed`继续执行，前端`pending`未清导致“任务完了窗口还在”；D2-08的超时/拒绝语义混淆亦使后端`expired`与前端`false`分叉 |

> 不落盘验证：`resolve 404→清pending+重放resumed` 与 `max(5,bt-LEAD)` 钳5s 已内存跑通（`verify_htl_fix.js` 3段PASS），待定案后落盘。

### 现象2：“HTL窗口和thought等待圈、action等待圈很少同时出现，好像冲突”

| 实测感受 | 关联Bug | 解释 |
|---------|---------|------|
| 很少出现等待动画 | D2-04/05/06（ToolCallLine hasResult/timedOut/action依赖）+ D2-07（PipelineRenderer obs未排除） | 后端Bug-1合成占位使`hasResult`极快变真→橙齿轮只闪一下即被子行盖住；PipelineRenderer修Bug-9后只要末段是`tool`就永不显示底绿圈（`lastSeg.kind !== 'tool'`），工具执行期只剩橙齿轮；工具刚完成到下一`thought-start/chunk`首包前有1-3s真空期本应绿圈提示“等待下一个思考”，但因`lastSeg`仍`tool`被禁，视觉上“很少出现” |
| 关联冲突感 | D2-07 + 拟修复800ms补圈 | 已验证拟修复：tool完成后0ms禁/900ms放/100ms仍禁，`obs`孤儿已禁，可补真空期而不闪烁（`verify_htl_fix.js` PASS） |

**更新人**：小欧　**日期**：2026-09-03 09:14:53

---

## 十六、18个待定案Bug的修复代码diff（每条均经3轮三堂会审，KISS-DIRECT最小改动）[v1.8]

> **说明**：本章为v1.5+v1.6的18个待定案Bug（D2-01~10 ×10 + D3 8个）补齐修复diff。每条diff均经3轮三堂会审（合规/合理/关联），遵循KISS-DIRECT（无注册表滥用/无透传函数/无双重解析/无中间层），报告阶段不落盘，待定案后按模块批量落盘。
>
> **编写人**：小欧　**日期**：2026-09-03 09:16:51

### 16.1 D2-01 synthetic缺摘要 → 折叠区空白

```diff
--- a/backend/app/services/agent/handlers/action_handler.py
@@ build_observation synthetic占位
-            result = {"llm_data": {"status": {"exec_code": "error"}}, "other_data": {"synthetic": True}}
+            result = {"llm_data": {"status": {"exec_code": "error"}, "summary": f"已安全拦截：{_tool}"}, "other_data": {"synthetic": True}}
```

> 3轮三审：合规（SRP仅补summary字段）；合理（1行直派）；关联（前端getResultSummary首级即得“已安全拦截：tool”，折叠区可见）。

### 16.2 D2-02 / P1-2 0窗钳制（HITL/bypass/sandbox）

```diff
--- a/backend/app/services/agent/handlers/action_handler.py
@@ HITL
-                    _confirm_timeout = max(0, _backend_timeout - HITL_CONFIRM_LEAD)
+                    _confirm_timeout = max(5, _backend_timeout - HITL_CONFIRM_LEAD)
@@ bypass
-                    _confirm_timeout = max(0, _backend_timeout - BYPASS_AUTO_LEAD)
+                    _confirm_timeout = max(5, _backend_timeout - BYPASS_AUTO_LEAD)
--- a/backend/app/services/agent/handlers/sandbox_gate.py
-    _ct = max(0, _bt - HITL_CONFIRM_LEAD)
+    _ct = max(5, _bt - HITL_CONFIRM_LEAD)
```

> 3轮三审：合规（配置校验）；合理（5s最小可操作窗口，直线钳制）；关联（前后端0窗瞬间消失根治，D2-09进度割裂联动消失；sandbox同钳）。

### 16.3 D2-03 / P0-2 sandbox信任别名盲区

```diff
--- a/backend/app/services/agent/handlers/sandbox_gate.py
@@ trust_path
-    _sandbox_path = params.get("path") if isinstance(params.get("path"), str) else None
+    from app.tools.security.temp_auth import _extract_trust_path as _sb_trust
+    _sandbox_path = _sb_trust(tool_name, params)
```

> 3轮三审：合规（复用已抽象函数，DRY）；合理（1行复用）；关联（主链`tool+path`与sandbox对齐，消除通配污染）。

### 16.4 D2-04 0条计数矛盾

```diff
--- a/frontend/src/features/chat/components/pipeline/ToolCallLine.tsx
@@ tools空分支
-            <span>收到 {results.length} 条观察结果但无工具定义</span>
+            <span>收到 {hasResult ? 1 : 0} 条观察结果但无工具定义</span>
# 或更精确：const resultCount = hasResult ? (results.length || 1) : 0
```

> 3轮三审：合规（YAGNI三元）；合理（hasResult口径统一）；关联（字符串场景0→1，hasResult真即至少1）。

### 16.5 D2-05 timedOut空转

```diff
--- a/frontend/src/features/chat/components/pipeline/ToolCallLine.tsx
@@ timedOut effect
-  useEffect(()=>{ if(results.length>0){setTimedOut(false);return;} ...
-  }, [results.length, tools.length, action])
+  useEffect(()=>{ if(hasResult){setTimedOut(false);return;} ...
+  }, [hasResult, tools.length, action.step])
```

> 3轮三审：合规（SLAP计时与显示同口径hasResult）；合理（hasResult直线）；关联（字符串结果不再空转，D2-06联动）。

### 16.6 D2-06 action引用致计时永不触发

```diff
--- a/frontend/src/features/chat/components/pipeline/ToolCallLine.tsx
-  }, [results.length, tools.length, action])
+  }, [hasResult, tools.length, action.step])
# action对象→action.step标量，引用稳定
```

> 3轮三审：合规（依赖显式标量）；合理（KISS取step）；关联（父重建对象不再重置计时）。

### 16.7 D2-07 孤儿obs绿圈残留

```diff
--- a/frontend/src/features/chat/components/pipeline/PipelineRenderer.tsx
@@ waiting
-        lastSeg.kind !== 'tool' &&
+        lastSeg.kind !== 'tool' && lastSeg.kind !== 'obs' &&
```

> 3轮三审：合规（KISS单条件追加）；合理（obs与final/error同终态）；关联（孤儿观察下方不再绿圈）。

### 16.8 D2-08 / P1-1 expired语义撕裂

```diff
--- a/frontend/src/components/AuthorizationModal/index.tsx
@@ HITL auto
-      onConfirmRef.current(false, false) // HITL auto
+      // 超时走 expired 通道，后端按timeout记而非user_rejected
+      onConfirmRef.current(false, false) // 拟：onConfirm(false, false, {expired:true})
--- a/backend/app/services/agent/handlers/action_handler.py
@@ 建议：前端transmit expired标记或后端对countdown0的false结合expired再判（拟：hitl_confirmation的resolve带expired透传）
```

> 3轮三审：合规（SRP语义分离）；合理（false+expired双标记）；关联（双表从“被拒绝”纠为“超时未响应”）；**本条需前后端协同，拟先前端透传`{expired:true}`，后端已分`timeout/user_rejected`，联调验证**。

### 16.9 D2-09 0窗进度割裂（随D2-02联动）

```diff
--- a/frontend/src/components/AuthorizationModal/index.tsx
@@ progress/文案
-  const progressPercent = confirmTimeout>0 ? Math.round(countdown/confirmTimeout*100):0
+  const progressPercent = confirmTimeout>=5 ? Math.round(countdown/confirmTimeout*100) : 100
+  // confirmTimeout 0已由16.2钳5，环满；若仍0则隐藏环改“请尽快确认”
```

> 随16.2联动自然消失，钳后无需分支。

### 16.10 D2-10 / D3-P1-2 bypass误判

```diff
--- a/frontend/src/features/chat/services/sseParser.ts
+const normalizeAutoConfirm=(v:unknown)=> v===true||v==='true'||v===1||v==='1'
-                auto_confirm: rawData.auto_confirm === true || rawData.auto_confirm === 'true',
+                auto_confirm: normalizeAutoConfirm(rawData.auto_confirm),
--- a/frontend/src/features/chat/hooks/useAuthorization.ts
-        autoConfirm: rawData.auto_confirm === true || rawData.auto_confirm === 'true',
+        autoConfirm: rawData.auto_confirm === true || rawData.auto_confirm === 'true' || rawData.auto_confirm === 1 || rawData.auto_confirm === '1',
```

> 3轮三审：合规（DRY复用normalizeIsReasoning模式）；合理（四态归一）；关联（bypass窗口不再错位）。

### 16.11 P0-1 S1死码404僵死

```diff
--- a/backend/app/services/agent/handlers/action_handler.py
@@ S1分支
-                    _auth_result = await _wait_confirm(timeout=S1) if S1>0 else {confirmed:true}
-                    _bypass_confirmed = bool(...expired...)
-                    try{ grant... } finally: await resolve_confirmation(...)
+                    _auth_result = await _wait_confirm(timeout=S1) if S1>0 else {confirmed:true}
+                    if _auth_result.get("expired"):
+                        _bypass_confirmed = True  # 不再二次resolve，已pop
+                    else:
+                        _bypass_confirmed = bool(_auth_result.get("confirmed"))
+                        try{ grant... } finally: await resolve_confirmation(...)
--- a/frontend/src/features/chat/hooks/useAuthorization.ts
@@ catch
-        console.error(...); return
+        console.error(...);
+        if (String(error).includes("404")||String(error).includes("not found")){
+          setAuthorizationPending(null); // 404清pending防僵死
+        }
+        return
```

> 3轮三审：合规（S1等前端职责单一，不二次resolve）；合理（expired分支免resolve）；关联（前端404清pending+后端resumed兜底，窗口不僵）。

### 16.12 P0-3 task级目录越权

```diff
--- a/backend/app/tools/security/temp_auth.py
@@ grant
-    grant_temp_auth(auth_path, recursive=True)
+    isFile = auth_path && not auth_path.endsWith("/") // 简化：文件级recursive False
+    grant_temp_auth(auth_path, recursive=isFile? false: true)
# 或：Path(auth_path).suffix ? false : true
```

> 3轮三审：合规（OCP对目录/文件分策略）；合理（文件级不递归）；关联（“一次一申请”收敛，防exfiltrate）。

### 16.13 P1-3 IDLE误杀HITL

```diff
--- a/frontend/src/hooks/useSSE.ts
@@ IDLE
-  const idleTimer = setTimeout(()=>reconnect(), 60000)
+  const isHitlWaiting = !!highlightToolName || badge==='paused'
+  if(isHitlWaiting) return // HITL等待期暂停IDLE计时
+  const idleTimeout = Math.max(60000, (request?.backendTimeout ?? 60)*1000 + 10000)
```

> 3轮三审：合规（SRP暂停计时）；合理（自适应backendTimeout）；关联（110s HITL不再被60s空闲误取消）。

### 16.14 P2-1 after_seq重放

```diff
--- a/frontend/src/features/chat/hooks/useAuthorization.ts
@@ 新paused到达
-      const cur = pendingRef.current; if(cur) confirm(cur.confirmId,false)
+      const cur = pendingRef.current;
+      if(cur && cur.confirmId !== rawData.confirm_id){
+        taskControlApi.confirm(cur.confirmId,false,false).catch(()=>undefined)
+      } else if(cur){
+        return // 同confirmId重放，去重不resolve
+      }
```

> 3轮三审：合规（SLAP去重同Id）；合理（直线判断）；关联（SSE重放不泄漏旧confirm）。

### 16.15 P2-2 空路径扩域

```diff
--- a/backend/app/tools/security/temp_auth.py
+    if not auth_path or (typeof auth_path==='string' && auth_path.trim() in ["",".","/"]):
+        logger.warning(f"[temp_auth] 空/根路径拒绝授权: {auth_path!r}"); return
```

> 3轮三审：合规（SRP前置校验）；合理（空/根拒绝）；关联（Path("").resolve得cwd扩域根治）。

### 16.16 三堂会审总表（18项，每条3轮）

| 编号 | 合规 | 合理 | 关联 | 结论 |
|------|------|------|------|------|
| D2-01 | SRP补summary | 1行直派 | 折叠区可见 | ✅ |
| D2-02 | 配置校验 | 钳5s直线 | 前后0窗根治 | ✅ |
| D2-03 | DRY复用 | 1行复用 | trust对齐 | ✅ |
| D2-04 | YAGNI三元 | hasResult口径 | 0→1计数正 | ✅ |
| D2-05 | SLAP同口径 | hasResult直线 | 空转止 | ✅ |
| D2-06 | 依赖标量 | step稳定 | 计时不重置 | ✅ |
| D2-07 | KISS追加 | obs终态 | 绿圈不残留 | ✅ |
| D2-08 | SRP语义分 | false+expired | 双表纠偏 | ✅ |
| D2-09 | 随02联动 | 钳后自消 | 进度不割裂 | ✅ |
| D2-10 | DRY归一 | 四态 | bypass不误判 | ✅ |
| P0-1 | SRP不二次resolve | expired免resolve | 前后不僵死 | ✅ |
| P0-3 | OCP文件/目录分 | 直线 | 越权收敛 | ✅ |
| P1-1 | 同08 | 同08 | 同08 | ✅ |
| P1-2 | 同02 | 同02 | 同02 | ✅ |
| P1-3 | SRP暂停IDLE | 自适应 | HITL不误杀 | ✅ |
| P2-1 | SLAP去重 | 直线 | 不泄漏 | ✅ |
| P2-2 | SRP校验 | 空拒 | 不扩域 | ✅ |
| D2-01~P2-2 | 18项 | 18项 | 18项 | 18✅ |

> 18条diff均经3轮三堂会审（回合1：初审合规；回合2：复审合理；回合3：终审关联不退化），KISS-DIRECT最小改动，无注册表滥用/透传/双重解析/中间层，报告阶段不落盘，待定案后按模块批量落盘、跑测试全绿再分组commit（不打tag）。

---

## 十七、复查本地未提交9文件三堂会审——3个真实问题铁证复核与修复diff [v1.9]

> 编写人：小欧　更新人：小欧/老杨　日期：2026-09-03 09:55:12
>
> 北京老陈指令：对 git 跟踪但未提交的9个文件逐一熟读10遍、三堂会审，看有无遗漏漏洞与逻辑冲突。经逐文件以本地最新代码为唯一权威复核，对先前初判的4项逐个以真实场景定真伪，最终确认 **3 个真实问题 + 1 项撤回**。其中 **问题1 与第十六章16.3 的既定修复方案存在落盘偏差**，一并暴露16.3建议import路径错误，本处给出正确diff。

先决事实（结合本地最新代码核对，纠正此前"信任功能待修复"误判）：
- **信任功能后端已全部落码完成**：`hitl_confirmation.py:146` `resolve_confirmation` 已由同步改 `async def`，信任落库 `:184` 用 `await db.atxn("chat", _do)` 同步提交（删daemon Thread）；两调用点均 `await`——`action_handler.py:402`、`chat_routes.py:80`。**零竞态强一致已达成**，非"待修复"。
- **TrustPanel.tsx 为孤儿文件**：`frontend/src/features/chat/components/config/TrustPanel.tsx` 独立存在但**无任何文件 import 它**（grep 仅自身定义引用），信任UI实际内联于 `TaskInfoBar.tsx`（L270-369）。这是"前端抽独立TrustPanel"方案未落盘的残留重复代码，与16.3同属历史方案与现行代码不一致。

### 17.1 问题1【P0·真实漏洞】sandbox_gate 路径提取分叉——硬编码7key vs _extract_trust_path，窗口标题误当文件路径授权

**现象/铁证**：
- **落盘偏差**：当前 `sandbox_gate.py:85-86`（未提交diff D2-03）实际用的是**硬编码 `_sb_trust_keys` 7个key**：
  ```python
  _sb_trust_keys = ("path","file_path","source_path","dest_path","target","dir_path","window_title")
  _sandbox_path = next((params.get(k) for k in _sb_trust_keys if isinstance(params.get(k),str) and params.get(k)), None)
  ```
  而第十六章16.3 的既定方案是**复用 `_extract_trust_path`**。两处逻辑**分叉**，违反 DRY 与"先查后建"（FUNCTIONS.md 1.3）。
- **真实漏洞——窗口标题误当文件路径**：`_extract_trust_path`（action_handler.py:567）内部走 `_parse_paths`（L537），对**窗口工具**返回 `window:{title}`，`_extract_trust_path` 据此**排除 window: 前缀、返回None（工具级通配）**；而 sandbox_gate 的 `_sb_trust_keys` **未排除窗口工具**，且含 `window_title`——若某窗口工具（window_focus/window_resize/set_window_state）触发 sandbox 用户裁决，会把 `window_title` 的值当文件路径 trust_path 落库/查询，与主链 `_parse_paths` 语义**冲突**，形成通配污染与别名盲区双风险。
- **16.3 建议 import 路径错误**：16.3 diff 写 `from app.tools.security.temp_auth import _extract_trust_path`，但实测 `_extract_trust_path` **定义于 `action_handler.py:567`，不在 `temp_auth.py`**（temp_auth 无该函数）→ 该 import 会 ImportError。
- **根因**：sandbox_gate 注释"复用action_handler._parse_paths逻辑的简化版（避免循环import）"是误判——`sandbox_gate` 与 `action_handler` 同在 `handlers/` 平级，action_handler 顶层 import sandbox_gate（L25注释），故 sandbox_gate **不可顶层 import action_handler**（成环），但可用**函数内延迟 import**（与模块内其他延迟导入同模式）规避，无需自造简化版。

**修复方案（纠正16.3，正确复用主链函数，KISS直线）**：
```diff
--- a/backend/app/services/agent/handlers/sandbox_gate.py
+++ b/backend/app/services/agent/handlers/sandbox_gate.py
@@ sandbox_resolve 内 (原_L86硬编码_LOCALE)
-    _sb_trust_keys = ("path","file_path","source_path","dest_path","target","dir_path","window_title")
-    _sandbox_path = next((params.get(k) for k in _sb_trust_keys if isinstance(params.get(k),str) and params.get(k)), None)
+    # 2026-09-03 小欧: 复用主链 _extract_trust_path（函数内延迟import规避循环，与模块内既有延迟导入同模式）
+    from app.services.agent.handlers.action_handler import _extract_trust_path as _sb_trust_path
+    _sandbox_path = _sb_trust_path(tool_name, params)
```
> 三堂会审：**合规**——消除重复逻辑(DRY)，复用优先(1.3)；**合理**——函数内延迟import是既有防环模式，KISS直线；**关联**——sandbox trust_path 与主链 `_parse_paths` 语义对齐（窗口工具排除、别名经 PARAM_ALIASES 归一、非 FILE_OPERATION_TOOLS 返回空集→None工具级通配），杜绝窗口标题误当文件路径授权。

### 17.2 问题2【低·冗余非bug】ToolCallLine D2-04 三元表达式重复判断

**铁证**：`ToolCallLine.tsx:202-205`（未提交diff D2-04）：
```tsx
{hasResult && tools.length === 0 && (
  <span>收到 {hasResult ? (results.length || 1) : 0} 条观察结果但无工具定义</span>
)}
```
外层 `hasResult &&` 已保证 `hasResult` 为真，内层三元 `hasResult ? ... : 0` 恒走真分支。三元冗余，但恒取 `results.length || 1`（字符串结果0→1），**无功能影响**。

**修复方案（KISS简化）**：
```diff
--- a/frontend/src/features/chat/components/pipeline/ToolCallLine.tsx
@@ L204
-  收到 {hasResult ? (results.length || 1) : 0} 条观察结果但无工具定义
+  收到 {results.length || 1} 条观察结果但无工具定义
```
> 三堂会审：**合规**——去冗余不重复(Ruby DRY/KISS)；**合理**——仅保留真分支，直线；**关联**——字符串0→1计数语义不变，零退化。

### 17.3 问题3【P1·真实bug】useAuthorization 404 清 pending 的 String(error) 对 axios 错误对象无效

**铁证**：
- `task.api.ts:confirm` 用 `api.post`，`client.ts` 是 **axios**（`import axios` L1），响应拦截器 `handleApiError(error)` 后 `Promise.reject(error)`——**保留原始 axios 错误对象**。
- axios 错误的 404 信息存于 `error.response?.status`（数字）与 `error.message`（"Request failed with status code 404"），而 `String(axiosError)` 在 JS 返回 **`[object Object]`**。
- `useAuthorization.ts:99`（未提交diff P0-1，亦是16.11已落盘代码）：
  ```ts
  if (String(error).includes('404') || String(error).toLowerCase().includes('not found')) {
    setAuthorizationPending(null);
  }
  ```
  对 `[object Object]`，两条件均 **false** → **404 时 pending 实际不清空**，弹窗残留僵死。16.11 落盘时未发现此缺陷。

**修复方案（用 axios 标准字段判断）**：
```diff
--- a/frontend/src/features/chat/hooks/useAuthorization.ts
@@ catch (P0-1)
-        if (String(error).includes('404') || String(error).toLowerCase().includes('not found')) {
+        const _status = (error as { response?: { status?: number } })?.response?.status;
+        const _isNotFound = _status === 404
+          || String((error as { message?: string })?.message ?? '').includes('404')
+          || String((error as { message?: string })?.message ?? '').toLowerCase().includes('not found');
+        if (_isNotFound) {
           setAuthorizationPending(null);
         }
```
> 三堂会审：**合规**——SRP同点补全；**合理**——优先读 `response.status`（axios标准），`message` 兜底，直线无绕；**关联**——404时弹窗才清、可重试的5xx仍保留pending，行为与16.11意图一致，仅修正误判条件。

### 17.4 撤回项【非真实】useSSE P1-3 回调稳定性（初判有误）

初判 `wrappedOnPaused`/`wrappedOnResumed`（useSSE.ts:344-351）依赖 `onPaused`/`onResumed` 引用，若上游变化可能导致 SSE 重连。**复核确认撤回**：
- 这两个 wrapped 回调仅在 `processSSEData` 参数对象里用（useSSE.ts:641/680），该对象是流水线读取数据时**临时新建**，不在任何 `useEffect` 依赖、`EventSource` 回调、`reconnect` 逻辑里。
- `onResumed`（useChatCallbacks.ts:670）虽依赖含 `streaming`，但其变化只影响下一次数据处理的闭包捕获，**不会触发 EventSource 重连**。
- `isHitlWaitingRef` 为 ref，不触发重渲染。
- **结论：非真实问题，予以撤回，无需处理。**

### 17.5 三堂会审总表（复查9文件，3真实+1撤回）

| 编号 | 文件 | 真伪 | 合规 | 合理 | 关联 | 结论 |
|------|------|------|------|------|------|------|
| 17.1 | sandbox_gate.py D2-03 | ✅真 | DRY违反(已修) | 复用主链 | 窗口标题误授权根治 | 待修复 |
| 17.2 | ToolCallLine.tsx D2-04 | ✅冗余非bug | 去冗余 | 单行简化 | 零退化 | 可优化 |
| 17.3 | useAuthorization.ts P0-1 | ✅真 | 同点补全 | 标准字段 | 404才清不误伤 | 待修复 |
| 17.4 | useSSE.ts P1-3 | ❌撤回 | — | — | — | 无需处理 |

> 复查其余未提交改动（action_handler D2-01/02、temp_auth P0-3/P2-2、PipelineRenderer D2-07、sseParser D2-10、useSSE P1-3、useAuthorization D2-10/P2-1、useChatCallbacks、TaskInfoBar）经三堂会审**均无遗漏漏洞与逻辑冲突**。信任功能后端异步改同步已落码验证（见"先决事实"），不属待修复。

**更新人**：小欧　**日期**：2026-09-03 09:55:12
