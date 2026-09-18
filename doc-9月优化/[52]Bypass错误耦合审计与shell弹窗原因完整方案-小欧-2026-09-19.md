# [52]Bypass错误耦合审计与shell弹窗原因完整方案

| 版本 | 时间 | 作者 | 更新内容 |
|------|------|------|---------|
| v1.1 | 2026-09-19 05:44:23 | 小欧 | 新增第五章：北京老陈"bypass两目的"原则复核——bypass 仅用于倒计时控制（后端到期放行 vs 人工到期拒绝、前端 8s 自动确认 UI），中间业务逻辑须与 bypass 无关；2–8 重定性：#5 拒绝记忆守卫、#6 沙箱跳过网关直放改判为耦合（待拍板），其余维持。 |

**历史版本（保留）：**

| 版本 | 时间 | 作者 | 更新内容 |
|------|------|------|---------|
| v1.0 | 2026-09-19 05:38:43 | 小欧 | 创建本文档。 |

## 一、Bypass 全仓用点审计结论

> 编写人：小欧 2026-09-19 05:38:43
> 背景：shell 弹窗 content 与 bypass 是否有关。核查发现两者本应是正交维度（content＝为什么问，auto_confirm＝问不问），但 checker bypass 分支把开关状态说明塞进原因字段。
> 核查方法：grep 全仓 `auto_confirm|_is_skip_safety|bypass` 非注释行，逐点读代码定性；确认零测试断言 C2 文案（改动无既有断言冲突）。

| # | 位置 | 行为 | 定性 |
|---|---|---|---|
| 1 | `tool_safety_checker.py:189-196` bypass 分支 | `message=C2`（安全开关已绕过，自动确认执行）覆盖真实原因 | ❌ 错误耦合，本次解 |
| 2 | `tool_safety_checker.py:175-177` 白名单外 bypass 直放 | `auto_confirm=True`，message 保留原路径原因 | ✅ 对（P0-02，无人值守定案） |
| 3 | checker 全部分 blocked 分支 | 无视 bypass 无条件拦 | ✅ 对（危险与开关解耦，2026-08-04 定案） |
| 4 | `safety_gate.py:230-239` bypass 区 | expired 也算确认＋授权＋沙箱直通 | ✅ 对（全自动语义） |
| 5 | `safety_gate.py:164` 拒绝记忆 `not _bypass` | bypass 不受记忆约束 | ✅ 对 |
| 6 | `sandbox_gate.py:123-126` bypass 直放 | needs_ruling＋auto_confirm 直接放 | ✅ 对（v1.13 V2 定案） |
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

## 三、完整修改方案（3 处，两文件，未落码）

> 编写人：小欧 2026-09-19 05:38:43

**改动 1（`tool_safety_checker.py:194`）：** bypass＋需确认分支 `message` 去 C2 改空串，开关状态由 `auto_confirm` 表达。`needs=False` 分支的"安全开关已绕过"保留（不进网关，只进日志，审计有用）。

**改动 2（`safety_gate.py:217-219`）：** bypass 时不兜底问句（否则"是否允许执行工具"＋"将自动确认"自相矛盾）。content 为空时前端原因区自动隐藏（[50] §7.4.3 已有逻辑），同批后缀保留。

**改动 3（shell 安检预检，前序方案并入）：** `_get_needs_confirmation` 内对 shell 调一次 `check_shell_command_risk`（延迟导入，无环：该模块仅依赖 re/SafetyResult/logger）：HIGH 提前拦（原来先弹窗、点了确认执行层照样拦，白弹一次）；MEDIUM 的 desc 进弹窗 content；普通命令仍空（诚实）；`protected_pids` 传 None（进程保护仍由执行层兜底，零退化）；`shell_type` 取参默认 ps7（与执行层一致）。bypass 分支在主流程中先于本段返回，bypass 下够不着——bypass shell 内容空隐藏，真 HITL shell 带 desc，互不干扰。

**连带确认：** safety_level 分类不受影响（`elif not _msg` 工具名归属照走）；日志 `logger.info` 原样保留；safety_level tag 正常显示。

## 四、验证计划（落码后执行）

> 编写人：小欧 2026-09-19 05:38:43

1. `py_compile` 三文件。
2. 真跑 checker：bypass 开/关 × shell/路径工具，断言 content 与 auto_confirm 正交（bypass 下 content 空＋auto_confirm True；真 HITL 下 shell MEDIUM 带 desc）。
3. 安全批量回归（21 文件 352 passed 基线集合）。
4. 上报北京老陈。

## 五、Bypass两目的原则复核（2–8 重定性，待拍板）

> 编写人：小欧 2026-09-19 05:44:23
> 北京老陈原则：bypass 只有两个根本目的——①后端倒计时到期放行（人工到期拒绝）②前端倒计时自动确认 UI；与真人工确认的差异仅在此，其余业务逻辑全程与 bypass 无关。
> 按此原则，`auto_confirm` 是倒计时模式信号本身，凡业务分支出现 `if bypass/auto_confirm` 即耦合。

| # | 重定性 | 理由 |
|---|---|---|
| #2 白名单外 bypass 直放 | ✅ 维持正确 | 设 `auto_confirm=True` 即置倒计时模式信号（驱动 8s 公式＋到期放行），message 未覆盖 |
| #3 blocked 无视 bypass | ✅ 维持正确 | 安全线与倒计时无关，不受其影响（反向正确） |
| #4 bypass 区 expired 算确认 | ✅ 维持正确 | expired→放行正是目的①本体；授权＋沙箱直通是"批准"的效果 |
| #5 拒绝记忆 `not _bypass` 守卫 | ❌ 改判耦合 | 记忆管"问不问"，bypass 管"到期算什么"，正交。守卫让 bypass 覆盖记忆。建议**去掉守卫**：曾明确拒绝过的操作，bypass 下直接复用拒绝（问都不问，倒计时无从谈起）。注：与"全自动"直觉冲突，待拍板 |
| #6 沙箱 bypass 跳过网关直放 | ❌ 改判耦合 | 违反原则：应走同一网关 8s 倒计时、到期自动过＋paused/resumed 成对，而不是无声跳过。建议**删直放分支**。代价：bypass 下每次沙箱裁决＋8s（E2E 自动化变慢）；收益：统一＋可见。待拍板 |
| #7 网关 bool 重构 | ✅ 维持正确 | 倒计时机制本体 |
| #8 直调入口仅 auto_confirm 直放 | ✅ 维持正确 | 该路径无倒计时可用，直放是唯一选项 |

> 更新人：小欧 2026-09-19 05:44:23
