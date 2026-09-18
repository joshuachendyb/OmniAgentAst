# [52]Bypass错误耦合审计与shell弹窗原因完整方案

| 版本 | 时间 | 作者 | 更新内容 |
|------|------|------|---------|
| v1.6 | 2026-09-19 06:26:06 | 小欧 | 十遍一致性核查：修正后端代码位置数 14→13、总数 19→18；五章 #5/#6 去掉"待拍板"。 |

**历史版本（保留）：**

| 版本 | 时间 | 作者 | 更新内容 |
|------|------|------|---------|
| v1.5 | 2026-09-19 06:21:16 | 小欧 | 一章标题加"概念分组"并补展开说明，八章标题同步修正。 |
| v1.4 | 2026-09-19 06:15:36 | 小欧 | 三章扩为 5 处；五章标已拍板；新增八章全仓逐行终审。 |
| v1.3 | 2026-09-19 06:02:18 | 小欧 | 新增第七章：十遍复核记录（P1–P10）。 |
| v1.2 | 2026-09-19 05:54:22 | 小欧 | 新增第六章：维持正确五处的 bypass 必要性论证。 |
| v1.1 | 2026-09-19 05:44:23 | 小欧 | 新增第五章：两目的原则复核，#5/#6 改判耦合（待拍板）。 |
| v1.0 | 2026-09-19 05:38:43 | 小欧 | 创建本文档。 |

## 一、Bypass 全仓用点审计结论（概念分组，11 组）

> 编写人：小欧 2026-09-19 05:38:43
> 更新人：小欧 2026-09-19 06:21:16（v1.5 标题加"概念分组"，补展开说明）
> 背景：shell 弹窗 content 与 bypass 是否有关。核查发现两者本应是正交维度（content＝为什么问，auto_confirm＝问不问），但 checker bypass 分支把开关状态说明塞进原因字段。
> 核查方法：grep 全仓 `auto_confirm|_is_skip_safety|bypass` 非注释行，逐点读代码定性；确认零测试断言 C2 文案（改动无既有断言冲突）。
> **展开关系：** 本章按业务概念分组（11 组），展开为 18 个独立代码位置（后端 13＋前端 5，含 1 个中性读取），详见第八章逐行审计表。

| # | 位置 | 行为 | 定性 |
|---|---|---|---|
| 1 | `tool_safety_checker.py:189-196` bypass 分支 | `message=C2`（安全开关已绕过，自动确认执行）覆盖真实原因 | ❌ 错误耦合，本次解 |
| 2 | `tool_safety_checker.py:175-177` 白名单外 bypass 直放 | `auto_confirm=True`，message 保留原路径原因 | ✅ 对（P0-02，无人值守定案） |
| 3 | checker 全部分 blocked 分支 | 无视 bypass 无条件拦 | ✅ 对（危险与开关解耦，2026-08-04 定案） |
| 4 | `safety_gate.py:230-239` bypass 区 | expired 也算确认＋授权＋沙箱直通 | ✅ 对（全自动语义） |
| 5 | `safety_gate.py:164` 拒绝记忆 `not _bypass` | bypass 不受记忆约束 | ❌ 改判耦合，已拍板（见第三章改动 3 / 第五章） |
| 6 | `sandbox_gate.py:123-126` bypass 直放 | needs_ruling＋auto_confirm 直接放 | ❌ 改判耦合，已拍板（见第三章改动 4 / 第五章） |
| 7 | `hitl_gateway.py` bool 重构 | 超时/文案/resumed 全走 `auto_confirm` | ✅ 对（HITL 相关 92 passed） |
| 8 | `tool_facade.py:132` | 无前端时仅 auto_confirm 直放 | ✅ 对 |
| 9 | 前端 bypass | 蓝框＋8s 自确认＋禁用勾选＋强制 trustSession=false | ✅ 对（5.4 防污染） |
| 10 | `_is_skip_safety` vs `skip_confirmation` | 开关 vs 会话信任分离 | ✅ 对 |
| 11 | trusted＋risky 仍弹 | 3.3 定案 | ✅ 对（非 bypass 范畴） |

## 二、错误耦合详解（#1）

> 编写人：小欧 2026-09-19 05:38:43

1. C2 文案：`安全开关已绕过，自动确认执行`（[50] C2，`tool_safety_checker.py:194`）。
2. 触发：`security.enabled=false` ＋工具需确认。此时**所有**需确认工具的 message 被一律改写为 C2，真实原因（路径越权/风险 desc）被吞。
3. 后果：bypass 提示窗显示的永远是这一句。外来"去 bypass 写死 content"改动只解了 `safety_gate` 一半（不再改写），checker 的 C2 源头还在。
4. 判定：开关状态应只由 `auto_confirm=True` 表达（前端蓝框＋"将自动确认"标题已讲清），不应占据原因字段。

## 三、完整修改方案（5 处，三文件）

> 编写人：小欧 2026-09-19 05:38:43
> 更新人：小欧 2026-09-19 06:15:36（v1.4 扩为 5 处，北京老陈已拍板）

| 改动 | 文件 | 行 | 状态 | 操作 |
|------|------|---|------|------|
| 1 | `tool_safety_checker.py` | 194-196 | ✅ 已实施 | bypass＋需确认分支 `message=""`（去 C2） |
| 2 | `safety_gate.py` | 217 | ❌ 待实施 | bypass 时不兜底问句：`_content = (_msg or ("" if _bypass else f"是否允许执行工具: {_cn}")) + _suffix` |
| 3 | `safety_gate.py` | 164 | ❌ 待实施 | 去掉 `not _bypass` 记忆守卫：`if _group_key in _rej_cache:` 无条件复用拒绝 |
| 4 | `sandbox_gate.py` | 123-127 | ❌ 待实施 | 删 bypass 直放分支（3 行）；`run_sandbox_gate` 去掉 `main_confirmed` 参数，内部一律 `auto_confirm=False` 走网关 8s 到期自动过 |
| 5 | `_get_needs_confirmation` 内 | — | ❌ 待实施 | shell 预检：延迟导入 `check_shell_command_risk`；HIGH 提前拦（直接 return）；MEDIUM desc 进 content；普通仍空；`protected_pids=None`，`shell_type` 默认 ps7 |

**改动 4 详细逻辑：** 当前 `sandbox_gate:123` `auto_confirm=True` 时直接 `return True, []` 跳过网关。修正后：删此 3 行；`run_sandbox_gate` 签名去掉 `main_confirmed` 参数；内部一律 `auto_confirm=False`（走网关 8s 倒计时→到期自动过→`_bypass_confirmed=True`→`run_sandbox_gate(agent, step, call, tool_name, params, safety_result, denied, main_confirmed=True)` 直放）。效果：bypass 下沙箱每次都走网关 8 秒倒计时（统一可见），不再无声跳过。

**连带确认：** safety_level 分类不受影响（`elif not _msg` 工具名归属照走）；日志 `logger.info` 原样保留；safety_level tag 正常显示。

## 四、验证计划（落码后执行）

> 编写人：小欧 2026-09-19 05:38:43
> 更新人：小欧 2026-09-19 06:15:36（v1.4 扩展至 5 处）

1. `py_compile` 三文件（checker / safety_gate / sandbox_gate）。
2. 改动 1 验证：真跑 checker bypass 开/关 × shell/路径工具，断言 bypass 下 `message=""`＋`auto_confirm=True`，真 HITL 下 shell MEDIUM 带 desc。
3. 改动 2 验证：bypass 窗 content 区不渲染（空串前端自动隐藏），"是否允许执行工具"不出现。
4. 改动 3 验证：曾拒绝过的工具，bypass 下仍直接复用拒绝（不弹 8 秒窗）。
5. 改动 4 验证：bypass 下沙箱走网关 8 秒倒计时→到期自动过→直放（不再无声跳过）。
6. 改动 5 验证：shell HIGH 提前拦（不弹窗）；MEDIUM 弹窗 content 带 desc；普通命令弹窗 content 为空。
7. 安全批量回归（21 文件 352 passed 基线集合）。
8. 上报北京老陈。

## 五、Bypass两目的原则复核（2–8 重定性）— 已拍板

> 编写人：小欧 2026-09-19 05:44:23
> 更新人：小欧 2026-09-19 06:15:36（v1.4 标记已拍板，北京老陈确认 3 个违规点修正方案）
> 北京老陈原则：bypass 只有两个根本目的——①后端倒计时到期放行（人工到期拒绝）②前端倒计时自动确认 UI；与真人工确认的差异仅在此，其余业务逻辑全程与 bypass 无关。
> 按此原则，`auto_confirm` 是倒计时模式信号本身，凡业务分支出现 `if bypass/auto_confirm` 即耦合。

| # | 重定性 | 理由 |
|---|---|---|
| #2 白名单外 bypass 直放 | ✅ 维持正确 | 设 `auto_confirm=True` 即置倒计时模式信号（驱动 8s 公式＋到期放行），message 未覆盖 |
| #3 blocked 无视 bypass | ✅ 维持正确 | 安全线与倒计时无关，不受其影响（反向正确） |
| #4 bypass 区 expired 算确认 | ✅ 维持正确 | expired→放行正是目的①本体；授权＋沙箱直通是"批准"的效果 |
| #5 拒绝记忆 `not _bypass` 守卫 | ❌ 改判耦合 | 记忆管"问不问"，bypass 管"到期算什么"，正交。守卫让 bypass 覆盖记忆。**去掉守卫**：曾明确拒绝过的操作，bypass 下直接复用拒绝（问都不问，倒计时无从谈起）。 |
| #6 沙箱 bypass 跳过网关直放 | ❌ 改判耦合 | 违反原则：应走同一网关 8s 倒计时、到期自动过＋paused/resumed 成对，而不是无声跳过。**删直放分支**。代价：bypass 下每次沙箱裁决＋8s（E2E 自动化变慢）；收益：统一＋可见。 |
| #7 网关 bool 重构 | ✅ 维持正确 | 倒计时机制本体 |
| #8 直调入口仅 auto_confirm 直放 | ✅ 维持正确 | 该路径无倒计时可用，直放是唯一选项 |

## 六、维持正确的五处为何必须用 bypass（逐条论证）

> 编写人：小欧 2026-09-19 05:54:22
> 判定标准只有一条：该处是否只决定"走哪套倒计时／到期算什么"，而不决定业务去向。
> 业务去向（拦／放／授／审）只由 blocked、requires_confirmation、sandbox、拒绝记忆、信任决定，与开关无关。

### 6.1 #2 白名单外设 `auto_confirm=True`——选倒计时，无业务分支

`tool_safety_checker.py:175-177` 只干一件事：把旗子置 True，message 路径原因、`auth_path`、`sandbox_required` 原样不动。下游读到旗子→网关走 bypass 公式（8 秒）→前端蓝窗→到期自动过。

反证：删掉这一行，白名单外写在无人值守下走真 HITL（110 秒窗等人）→超时→rejected→E2E 任务失败（即 P0-02 事故本身）。且 8 秒窗照弹（目的②前端自动确认 UI），不是静默偷放。

### 6.2 #3 blocked 无视 bypass——对的原因恰是"没用"

安全线判定"拦不拦"，倒计时决定"到期算什么"，两者正交。若 blocked 也看开关——开关一关连 `rm -rf /` 都不拦——才是灾难。`_check_known_risks` 在 `_is_skip_safety` 之前执行，顺序即表态。

### 6.3 #4 bypass 区 `expired` 算确认——目的①本体

`safety_gate.py:230-231` `_bypass_confirmed = confirmed or expired`：网关等到 `backend_timeout` 无人裁决回 expired，bypass 下计为批准——即"倒计时到期放行"逐字落实，真 HITL 同一位置是"到期拒绝"，差异仅此一行。块内 `grant_temp_auth` 与沙箱直通是"批准之后的效果"，与真 HITL 确认分支同构。整洁项备注：`if _bypass:` 与确认分支代码重复，可合并为 `approved` 后共用下游，语义已对，不必单立项。

### 6.4 #7 网关 bool——倒计时机制本体，无业务

`_resolve_timeouts(auto_confirm)` 只做公式二选一（120/110 vs 10/8）；resumed 条件 `(auto_confirm and expired)` 是目的①；paused 帧透传 `auto_confirm` 是给前端选 UI（目的②）。三处全是计时器刻度。

### 6.5 #8 直调入口——倒计时目的在无计时器路径下的唯一映射

`tool_facade.py:132` 路径没有 SSE、没有前端，倒计时无从跑起。`requires + auto_confirm → 直接执行`是目的①的退化形态（delay＝0 的到期放行）。唯一替代方案"一律报错需确认"会让关了开关的自动化 API 全灭，架空开关语义，故此处不是业务特判。

### 6.6 结论

#2/#4/#7 是倒计时控制本身（选哪套表、到期算什么、前端显哪套 UI）；#8 是其退化映射；#3 是"正确地没用"。五处都不决定业务去向。

## 七、十遍复核记录（P1–P10，北京老陈令三思三省）

> 编写人：小欧 2026-09-19 06:02:18
> 令：所有点都三思三省、复核 10 遍、是否确实正确、有无分析不彻底、有无遗漏。
> 法：现代码逐点重读＋真跑验证（非纸面推演），每遍只核一项、逐项对照本文档结论。

| 遍 | 复核内容 | 结论 | 证据 |
|---|---|---|---|
| P1 | C2 文案全仓残留 | ✅ 零逻辑残留，仅 4 处历史注释（checker:54,65 / safety_gate:40,52） | grep 全仓（app+tests+e2etests） |
| P2 | bypass 内容现状 | ⚠️ 缺口：改动1 已实施（`checker:194` message=""）；**改动2 未实施**——`safety_gate:217` `_msg or "是否允许执行工具"` 在 bypass 下仍兜底问句，"是否允许"＋"将自动确认"自相矛盾 live 中 | 读码 +200 行实读 |
| P3 | 毛病1（SELECT 免确认）改写后存活 | ✅ SELECT→False / INSERT→True | 真跑 `check_before_execute('execute_sql')` |
| P4 | bypass 分类（改动1 后） | ✅ msg 空走 `elif not _msg` 工具名归属，safety_level tag 正常 | 真跑 bypass shell：`msg='' auto=True needs=True` |
| P5 | 记忆＋网关＋拒绝全套回归 | ✅ 139 passed | `pytest` 9 文件 |
| P6 | refusal_key／记忆键读写点 | ✅ 全在（safety_gate:161-165 / sandbox:105-109） | 逐段读码 |
| P7 | 测试断言 C2 | ✅ 零断言（单元＋e2e 均无"安全开关已绕过，自动确认执行"） | grep tests+e2etests |
| P8 | 遗漏点猎杀（handle_action 活逻辑 / e2e 引用） | ✅ 无（handle_action 无 bypass 活逻辑，e2e 无文案引用） | grep 全面扫描 |
| P9 | [52] 行号 vs 现代码 | ✅ 全对（checker:194 / safety_gate:164,217 / sandbox:123 / facade:132） | 逐行比对 |
| P10 | 前端隐藏逻辑＋§6.3.2 改动 | ✅ 全活（content 空隐藏 256 行、勾选框 327 行、图标 281 行） | read index.tsx |

**复核结论：** 分析正确无方向性错误；[52] 全点行号、定性、方案均与代码一致；**唯一活缺口＝改动2 未实施**（错误耦合主战场 #1 已清除，但 bypass 窗兜底问句残留，待补两行）。

> 更新人：小欧 2026-09-19 06:02:18

## 八、全仓逐行终审（18 个代码位置，后端 13＋前端 5）

> 编写人：小欧 2026-09-19 06:15:36
> 令：bypass 只影响倒计时结果判断（到期放行 vs 拒绝）和倒计时数字（8s vs 110s），所有业务流程判断不与 bypass 相关。逐行过全仓 18 个代码位置（排除定义/注释/trust）。

**后端：**

| # | 位置 | 行为 | 定性 |
|---|---|---|---|
| 1 | `tool_safety_checker.py:175-176` | 白名单外设 `auto_confirm=True` | ✅ 选倒计时模式 |
| 2 | `tool_safety_checker.py:189-200` | bypass 分支 message="" | ✅ 倒计时信号（改动1 已实施） |
| 3 | `hitl_gateway.py:74-89` | `_resolve_timeouts` 公式二选一 | ✅ 倒计时数字 |
| 4 | `hitl_gateway.py:99-105` | 读取＋透传 auto_confirm 给前端 | ✅ 倒计时信号给 UI |
| 5 | `hitl_gateway.py:120` | `auto_confirm and expired → confirmed` | ✅ 到期放行（目的①） |
| 6 | `safety_gate.py:158` | 读取 `_bypass` | 中性（不决定去向） |
| 7 | `safety_gate.py:222` | `auto_confirm=_bypass` 传网关 | ✅ 倒计时模式 |
| 8 | `safety_gate.py:230-231` | `confirmed or expired` | ✅ 到期放行（目的①） |
| 9 | `sandbox_gate.py:148` | `auto_confirm=False` 硬编码 | ✅ 不受 bypass 影响 |
| 10 | `tool_facade.py:132` | 无前端直放 | ✅ 倒计时退化映射（delay=0） |

**违规点（3 处）：**

| # | 位置 | 违规性质 | 修正方案（第三章改动编号） |
|---|---|---|---|
| ❌A | `safety_gate.py:164` | `not _bypass` 记忆守卫——bypass 覆盖拒绝记忆，记忆管"问不问"与倒计时正交 | 改动 3：去掉守卫 |
| ❌B | `safety_gate.py:217` | `_msg or 兜底问句`——bypass 下"是否允许执行"＋"将自动确认"自相矛盾 | 改动 2：bypass 不兜底 |
| ❌C | `sandbox_gate.py:123-127` | `auto_confirm` → 直接 return 跳过网关——不走倒计时，无声放行 | 改动 4：删直放分支 |

**前端（全部合规，无违规）：**

| 位置 | 行为 | 定性 |
|---|---|---|
| `index.tsx:177-178` | `isBypass ? onConfirm(true)` | ✅ 到期放行（目的①） |
| `index.tsx:219-229` | 图标＋标题切换 | ✅ UI 区分（目的②） |
| `index.tsx:261-262` | 颜色方案蓝 vs 黄 | ✅ UI 区分 |
| `index.tsx:331` | 禁用勾选框 | ✅ 防污染 |
| `index.tsx:335-337` | tooltip 说明 | ✅ UI 信息 |

**结论：** 后端 13 个代码位置中 9 处合规（选倒计时/到期放行/退化映射）＋1 处中性（读取信号）＋3 处违规（已拍板修正）；前端 5 处全部是 UI 层无违规。bypass 整个表面共 18 个代码位置（对应第一章 11 个概念组），无其他文件引用（`handle_action.py`/`task_state.py`/`stream_orchestrator.py` 均无 bypass 活逻辑）。

> 更新人：小欧 2026-09-19 06:21:16
