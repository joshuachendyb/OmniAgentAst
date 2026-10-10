# [16] compaction 能力盘点与沙箱杀进程防护 — E2E 验证实录

**创建时间**: 2026-10-08 11:19:17
**编写人**: 小欧
**文档类型**: 编辑型（后续更新在版本历史追加，禁止删除历史版本）
**关联提交**: `3bffa5f3e` / `dcd65dd8e` / `0059f469d` / `927a53a9d`

---

## 一、compaction 包能力盘点

### 1.1 盘点方法与口径

盘点脚本 `backend/tests/probe_compaction_inventory.py`：AST 提取 `app/services/agent/compaction/` 下全部顶层函数（不含类方法），再全仓扫描 `app/**/*.py` 与 `frontend/src/**/*.ts` 的调用点，**排除 compaction 包自身**。

口径说明：**注释/文档提及不算接入**。首版脚本有两处误判，已修正后重出数据：

| 误判 | 原因 | 修正 |
|---|---|---|
| 「已接入 0 个」 | 循环变量解包顺序写反（`(py.name, node.name)` 按 `(fname, mod)` 解包），拿模块名去搜调用点 | 改正解包顺序 |
| `use_tool_summary` / `compress_long_tool_output` 误判为已接入 | 正则匹配到的是注释与 docstring 提及，非真实调用 | 逐个核验真调用行 |

### 1.2 总量结论

**7 个文件 / 20 个顶层函数 / 已接入 4 / 未接入 16**。

已接入的 4 个**全部集中在 `start_step.py`**（即 C4 锚定摘要及其降本编排），与「C3/C5 暂不接入，当前主链只接 C4」的既定裁定一致。

### 1.3 已接入清单（4 个）

| 函数 | 调用点 | 作用 |
|---|---|---|
| `generate_anchored_summary` | `start_step.py:225` | C4 锚定摘要，唯一接入主链的 LLM 环节 |
| `preserve_recent_budget` | `start_step.py:207` | 算保尾 token 预算 |
| `find_tail_start` | `start_step.py:208` | 定位保尾起点（不拆 FC 对） |
| `prune_tool_output_keeping_tail` | `start_step.py:209` | 摘要前降本执行（2026-10-07 新增） |

### 1.4 未接入清单（16 个）

**`assembler.py` — C5 装配线（4 个，文档 `[73]` 已登记待接线）**

| 函数 | 功能 |
|---|---|
| `split_history_window` | 把历史切为 `{old_head 待压缩, tail_part 保尾, absolute_tail_start}` |
| `inject_compressed_summary` | 用摘要 assistant 替换 old_head，装配 `system + 摘要 + tail + 最新 task` |
| `get_new_messages_since` | 取 tail_start 之后的增量块（供 `generate_chunked_summary`） |
| `remove_dangling_tool_calls` | 双向剪孤儿 FC（2026-10-08 刚修好判据空转，**仍未接入**） |

**`prune.py` — C3 剪枝引擎（8 个）**

| 函数 | 功能 | 接入状态 |
|---|---|---|
| `clear_tool_outputs` | 清 tool content 保结构 | **半接入**（被 `prune_tool_output_keeping_tail` 内部调用） |
| `keep_valuable_messages` | 按价值权重保留，预算内先丢低价值 FC 轮 | 未接入 |
| `_value_weight` | 消息语义价值权重（决策 80 / 结果 10…） | 未接入（被上一条调用） |
| `_fc_atomic_units` | FC 原子单元，整组取舍（2026-10-08 新增） | 未接入（被上一条调用） |
| `_msg_cost` | 单条消息 token 口径（2026-10-08 新增） | 未接入（被上一条调用） |
| `_released_tokens` | 释放量估算 | 未接入 |
| `use_tool_summary` | 用工具自带 summary 替换 content | **半接通**（见 1.5） |
| `compress_long_tool_output` | 逐工具观测压缩为一行通用摘要 | 未接入（零调用点） |

**`split_turn.py`（1 个）**：`truncate_oversized_message` — 半轮劈分，单条 tool 超长时压缩其 content

**`summary.py`（2 个）**：`generate_chunked_summary` — C4 降本变体（只喂增量块 + previousSummary 合并）；`_extract_response_content` — 内部取文函数

**`trigger.py`（1 个）**：`should_compact_now` — 动态窗口触发，大窗口（900K）模型下固定比例阈值失效时的消息数兜底

### 1.5 `use_tool_summary` 的真实状态：上游无生产者（非"只差消费端"）

**2026-10-08 11:19 初稿表述有误，此处更正。** 初稿写「`message_builder.py:195/207` 已在 stash `_summary`，只差消费端接上」——扫全仓后发现**上游根本没有任何工具产出 `summary` 字段**：

| 环节 | 状态 |
|---|---|
| 生产侧 `app/tools/**` 走 LLM 的模块 | **零个**产出 `summary` / `_summary` 字段 |
| 缓存侧 `message_builder.add_tool_result` | 已在 stash `_summary`（无值即不写） |
| 消费侧 `use_tool_summary` | 未接入 |

结论：即使接上 `use_tool_summary`，因无数据源也是**空跑**。该项前置条件是「先有工具产出 summary」，故**优先级从 2 下调为待定**（见 1.6）。

### 1.6 LLM 摘要功能的实测覆盖

全仓扫描「走 LLM 流式调用 + 函数名含 summary」，命中**仅 2 处**，都在 `compaction/summary.py`，共用同一取文层 `_extract_response_content`（全仓亦仅这 2 处调用，**无第三方复用点**）：

| 函数 | 走 LLM | 接入主链 | 真实 LLM 实测 |
|---|---|---|---|
| `generate_anchored_summary` | ✅ | ✅ | ✅ 已测（六段 6/6，方案1/方案2 两版） |
| `generate_chunked_summary` | ✅ | ❌ | ✅ **已补测 6/6**，但单次压缩贵 29% 且有质量风险 → **暂不接入**（见 2.5） |

另两条**不调 LLM**（纯规则），勿混为一谈：`compress_long_tool_output`（规则式压成一行，已测但该数据集未触发）、`use_tool_summary`（读工具自带字段，不调 LLM）。

### 1.7 后续接线优先级建议

> **2026-10-10 小欧 复核补注（YAGNI 定性）**：下表把未接入项**排队**是错的处置。
> YAGNI 的含义是「当下不需要就不需要」，不是「当下不需要但先留着」。
> 实测 `keep_valuable_messages` + `_value_weight` + `_fc_atomic_units` + `_msg_cost` + `_released_tokens`
> 五个函数（约 90 行）**互相调用形成自洽闭环、外部零引用**——为修它的判据改了 4 处（§2.4），
> 但**这些修复在生产链路上一次都不会执行**，另有 81 个单测在测这批死代码。
> compaction 包合计 628 行 / 20 函数 / 接入 4，**死代码约 350+ 行**。
> 正确处置是**二选一**：接 C5 就接，不接就删（至多保留 assembler/trigger 到需求明确）。留待接线是沉没成本。

| 序 | 目标 | 理由 |
|---|---|---|
| 1 | `remove_dangling_tool_calls` | 2026-10-08 刚修好且已单测；**任何删除式裁剪都必须先过它**，属安全前置 |
| 2 | `use_tool_summary` | **前置条件未满足**（1.5：上游无 summary 生产者），接了也是空跑；须先有工具产出 summary |
| 3 | `truncate_oversized_message` | 解决「单条超长 tool 撑爆窗口」，比整体裁剪更精准 |
| 4 | C5 三件套 + `generate_chunked_summary` | 长任务多次压缩场景才需要，工作量最大；`generate_chunked_summary` 已完成真实实测（见 2.5），接线风险已降低 |

> 补充：已接入的 `prune_tool_output_keeping_tail` **不删消息、只清 tool content**，FC 配对天然不受影响，
> 故第 1 项规则**当前未被违反**。规则应保留，用于约束未来真正的删除式裁剪。

---

## 二、摘要降本方案实测对比

### 2.1 三方案对照（真实 205 条注入历史，真实 LLM）

| 方案 | feed tok | 节省 | 摘要输出 | 六段 | 工具原文 |
|---|---|---|---|---|---|
| 未降本（全量喂） | 135362 | — | 3432 字符 | 6/6 | 124 条全保 |
| 方案1 全清零 | 83673 | 38% | 1521 字符 | 6/6 | 0 条 |
| **方案2 保尾保留（现行）** | **86472** | **36%** | **2048 字符** | 6/6 | **13 条** |

### 2.2 选定方案2 的依据

只多花 2799 tok（3%），摘要多 527 字符（+35%），且保住最近一轮的 13 条工具原文。质量差异集中在**证据可核对性**：

- 方案2 的 `Critical Context` 含签名与时间戳，`Relevant Files` 每个文件带「验证什么问题」，`Progress` 区分「7 个 Bug 真实但统计数据全假」
- 方案1 因工具原文被清空，只能靠 assistant 决策文本转述，无法写出「文件数 3066 而非 158」这类**可核对的数字**

**裁定口径**：锚定摘要的价值在保真（它要替代 205 条原始历史喂给模型），故宁多付 3% 成本换回证据。

### 2.3 落地形态（零新增算法）

```python
_tail_budget = preserve_recent_budget(max(1, _ctx - COMPACTION_BUFFER))  # split_turn: 算预算
_tail_start  = find_tail_start(_hist, _tail_budget)                      # split_turn: 找边界
_hist, _released = prune_tool_output_keeping_tail(_hist, _tail_start)    # prune: 执行前清后保
```

开关 `tuning.compaction.summary_prune_tool_output`（默认常量 `SUMMARY_PRUNE_TOOL_OUTPUT=True`），置 False 即刻回退全量喂。**没有「全清零」档位**（已被方案2 取代）。

### 2.4 顺带修复的既有缺陷

| 缺陷 | 根因 | 修复 |
|---|---|---|
| provider 400（`tool_calls` 缺配对 tool） | 决策（权重 80，≥70 无条件留）与结果（权重 10，预算内先删）**分条取舍** → 决策留下结果没了 | 新增 `_fc_atomic_units`，FC 对整组取舍 |
| budget 参数形同虚设 | 原判据 `weight>=70` 让 FC 单元永不丢弃，实测 `budget=2000` 却输出 83164 tok（超 41 倍） | 无条件保留收窄到 **system**，其余受预算约束 |
| budget 口径不准 | `len(content)/CHARS_PER_TOKEN` 自算，漏算 `tool_calls` 结构开销（实测决策消息 0 vs 41） | 新增 `_msg_cost` 复用 `MessageBuilder._estimate_tokens` |
| `remove_dangling_tool_calls` tool 侧从未真剪过 | `seen_ids` 取自同一份 messages，「该 id 在 seen_ids」恒真 | tool 侧改比对调用方 id 集合（`assistant.tool_calls`），双向各剪一次 |

---

### 2.5 `generate_chunked_summary` 补测（2026-10-08，含质量风险）

该函数此前是全仓**唯一「存在但零验证」的 LLM 摘要功能**（见 1.6）。本次用同一份真实历史（DB 还原 206 条）+ 同一降本策略（方案2 保尾保留）补测。

**测法**：模拟长任务多次压缩的两段式 —— 段1 `anchored(前150)` → 段2 `chunked(后56, previous_summary=段1)`；与基线 `anchored(全量206)` 对照。

| 指标 | A 基线 `anchored`(全量) | B 段1 `anchored`(前150) | B 段2 `chunked`(后56) |
|---|---|---|---|
| LLM 调用 | 1 次 | 1 次 | 1 次 |
| feed tok（估） | **7220** | 4968 | 4337 |
| 墙钟 | **40.9s** | 34.5s | 60.9s |
| 六段命中 | **6/6** | 6/6 | **6/6** |
| 摘要字符 | 1834 | 4052 | 4387 |

**结论一：单次压缩场景不划算。** 两段式合计 feed 9305 tok，比全量 7220 **多 2085 tok（+29%）**、多 1 次 LLM 调用、慢 2.3 倍 —— 因为要先把前段也摘要一遍。

**结论二：价值在多次压缩。** 第 2、3 次压缩只喂新增块（本例 4337 tok）而非重喂全量（7220 tok），**成本随压缩次数线性增长而非平方**。当前 `start` 压缩是一次性的，故该优势暂用不上。

#### 2.5.1 质量风险：增量版残留旧声称（重要）

对比同一事实在两份摘要中的表述：

| 版本 | 段位 | 内容 |
|---|---|---|
| A 全量 | `Key Decisions` | 已含更正：声称 158 份，**实际 3066 份** |
| B 段2 增量 | `Key Decisions` | **仍写「声称命中 158 份」**（旧声称残留） |
| B 段2 增量 | `Progress` | ✅ 含「完成 3066 份（**更正自声称的 158**）」 |

即：增量合并机制**能正确覆盖前段错误结论**（Progress 已更正），但**同一份摘要内两处口径不一致** —— `Key Decisions` 段留旧值、只在 `Progress` 段更正。全量版无此问题（每次重新生成）。

**由此得出一条硬约束**：将来若接入增量压缩，摘要一致性必须**成对校验** `Key Decisions`（旧声称残留）与 `Progress`（更正记录），**不能只看 Progress**。

#### 2.5.2 接线建议：暂不接入

| 理由 | 说明 |
|---|---|
| 场景不匹配 | 当前 `start` 压缩一次性，增量优势发挥不出来（反而贵 29%） |
| 质量风险未解 | 2.5.1 的旧声称残留需先有校验手段 |
| 已有更省的替代 | 降本已由 `prune_tool_output_keeping_tail`（省 36%）拿到，增量省的是"重算"而非"喂多少" |

### 2.6 待补：p9_03 复验

p9_03 是p9 全量 8 case 中**唯一尚未复验通过**的（前两轮分别挂 agent 杀后端与 429）。换 big-pickle 模型后 p9_08 已通过，p9_03 尚未重跑，见第五章待办第 1 项。

## 三、沙箱安全：agent 杀进程事故与四阶段防护

### 3.1 事故实录（E2E P9-03，2026-10-08 08:40）

```
08:40:16  [Action] step=13 tool=bash  command='Get-Process python | Stop-Process -Force; Write-Output "cleaned"'
08:40:23  [sandbox][exec] 预检开始: tool=bash, 类型=shell
08:40:23  [sandbox][backend] run 启动: command_head='Get-Process python ... Stop-Process -Force'
08:40:23  [sandbox][job] 进程收编入 Job: pid=25244  ← uvicorn 在此死亡
```

用户输入是「查天气 + 处理 E:\test_dir 目录」，与杀进程无关；**杀死后端的是沙箱预检本身**，不是真实工具执行。

### 3.2 根因：预检即真跑

| 操作类型 | 预检方式 | 是否安全 |
|---|---|---|
| 文件操作 | `_replay_file_op_on_replica` 在**影子副本**上重演 | 副作用隔离 |
| **shell** | `backend.run(cmd, 临时工作区)` 在**宿主上原样跑** | 副作用全落宿主 |

JobObject 只设了单进程内存限额（`0x100`），**无 CPU/时间/进程数限制，更不阻止子进程操作宿主**。它在设计上是「清理 + 防失控」机制（`TerminateJobObject` 杀全树），被当成沙箱使用。文件头原注释已自认：*「Job Object 非硬墙，run 前本预扫描是唯一防线」* —— 但该预扫描只覆盖**写文件**。

### 3.3 三层防护为何全失效

| 层 | 失效原因 |
|---|---|
| 受保护 PID 盾牌 | ①`_extract_stop_process_pids` 要求显式 `-Id`，管线/按名杀抽不出 PID → `set() & protected` 恒空；②**线上从未接线** —— 唯一调用点 `tool_safety_checker.py:271` 不传 `protected_pids`，全项目无第二处传值，`if protected_pids:` 整块永不执行；③保护对象是 shell 引擎进程池（实测 `get_all_pids()` 返回 `set()`），**不含后端主进程** |
| 沙箱预扫描 `_scan_command_write_intent` | 词表只有写文件动词（`Remove-Item`/`cp`/`mv`/`Set-Content`/`reg`/重定向）；`Stop-Process` 不在表内，`Get-Process python` 无绝对路径 → 判定为非越界 → 放行 |
| JobObject | 非安全边界，见 3.2 |

实测四种杀进程形态（`check_shell_command_risk` 真实调用）：

| 命令 | 抽出 PID | 判定 |
|---|---|---|
| `Get-Process python \| Stop-Process -Force` | 空 | destructive，**需确认但不拦** |
| `Stop-Process -Id <保护PID> -Force` | {命中} | dangerous，blocked（**仅在传参时**） |
| `taskkill /IM python.exe /F` | 空 | **无风险(None)** —— 词表 `taskkill\s+/f` 要求 `/f` 紧随 |
| `pkill -9 -f python` | 空 | **无风险(None)** —— `\bkill\b` 匹配不到 `pkill` |

### 3.4 设计原则（本次确立）

> **安全靠静态判定，预检只做错误预测。**

把 shell 命令分三类，一次判定、顺序 if/elif，不建类不建注册表：

| 类 | 判据 | 处置 |
|---|---|---|
| A 禁杀 | 杀进程/停服务/改系统 | 静态命中即 `blocked`，**不预检不执行** |
| B 需裁决 | 有副作用但不确定 | 静态命中 → 直接 `needs_ruling` 转 HITL，**不预检** |
| C 可预检 | 只读，或只写工作区 | 才允许进沙箱真跑（无伤） |

> **2026-10-10 小欧 更正：本表是「设计意图」，与已落地代码不一致。**
> 实测 `sandbox/executor.py:244-247`，A/B 两类命中后返回的是 `PreCheckResult(passed=False, needs_ruling=True)`，
> 即 **转 HITL 弹窗，并非 §3.5 所称的 blocked**。故本表的 A 类「静态命中即 blocked」当前**未实现**。
> 二者只能存其一，已在 §3.5 阶段二按实际代码口径注明，**本文档不作事后合理化**。

**双执行问题在三类分流下自然收敛**：A/B 不真跑；C 类预检写的是临时工作区（`workspace.destroy()` 销毁），真实文件只被真机那次写入。故不需要单独立项改执行链，也不需要做「全面静态化」（PS 语法太动态，误伤无穷，违反 YAGNI）。

### 3.5 四阶段止血落地（非「防护体系」，见 §3.7）

> **2026-10-10 小欧 更名**：原标题「四阶段落地」易被读成「防护已建立」。
> 实测四阶段**未消除根因**（预检仍在宿主真跑），只是把绕过面收窄。准确表述是**止血**，不是防护。

| 阶段 | 文件 | 内容 | 对「后端自杀」的实贡献 |
|---|---|---|---|
| 一 | `utils/shell_readonly.py` +62 | `UNCONTAINABLE_VERBS`（8 词表）+ `has_uncontainable_intent` / `extract_kill_target_pids` / `is_process_kill_protected` 三纯函数 | **有效但可绕过**（黑名单，见 §3.7） |
| 二 | `sandbox/executor.py` | `_scan_command_write_intent` 改名 `_scan_command_danger_intent` 并扩职责，命中即转 HITL **而不 run**；旧名零残留不留别名 | 拦住原事故形态；注意是 HITL 非 blocked（见 §3.4 更正） |
| 三 | `safety/tool_safety_checker.py` | 新增 `_protected_pids()`（自身+父进程+shell池）+ 接线，命中即 `blocked=True` 直返 | **对原事故贡献为 0**：事故命令是**按名杀**，抽不出 PID（见 §3.8 实证） |
| 四 | `sandbox/job_object.py` | 补 `KILL_ON_JOB_CLOSE` + `ACTIVE_PROCESS_LIMIT`（默认 64） | **0**（属「防失控」不属「防杀宿主」，非同一抽屉） |

收录标准：`SHELL_DANGEROUS_PATTERNS` 只到 MEDIUM（弹窗后仍进预检）拦不住者才收；HIGH 级（`Stop-Computer`/`Format-Volume`/`shutdown`）预检前已 blocked，收录即重复（DRY）。前后向断言用 `[a-z0-9_-]` 字符类而非 `\b`，避免 `kill` 命中 `killall`/`taskkill` 内部。

### 3.6 已知不完美（如实登记，不假装解决）

> **2026-10-10 小欧 复核补登**：下表原 5 项均为**次要**问题。审计时发现**唯一能复现原事故的形态未被登记**，
> 已补为第 1 项并置顶。原表遗漏它，属**登记失职**而非疏忽淡忘，此处如实记入。

| 项 | 说明 | 严重度 |
|---|---|---|
| **① 静态词表可被绕过（黑名单固有）** | `UNCONTAINABLE_VERBS` 是**黑名单**。**拼接类已于 2026-10-10 修复**（`normalize_for_intent` 折叠 `+` + 去引号，取并集）；**WMI/CIM/`.Kill()` 方法调用/`-EncodedCommand` Base64/中文变形仍 MISS**，详见 §3.7 | **高（已收窄，未清零）** |
| `_protected_pids` 覆盖不全 | `getppid()` 是 reloader 父进程，覆盖不到 `--reload` 派生的 worker 子进程 | 中 |
| ~~③ 保护盾对事故形态无效~~ **已修(2026-10-10)** | 按名杀抽不出 PID。已补名维度 `_protected_process_names` + `extract_kill_target_names`，事故原形现 `blocked` | ~~中~~ 已闭环 |
| `echo "kill"` 误命中 | 引号内裸词亦命中 → 转 HITL 而非直放。与该文件既有「取严」哲学一致 | 低 |
| JobObject 两项限额不阻止杀宿主 | 代码注释已明确该职责由 `shell_readonly` 静态判定承担 | 低（已在 §3.5 标注） |
| **④ 命令双执行（预检+真跑）** | 原表记「仅 C 类存在，已论证无害」——**该论证不成立**：预检只覆盖**静态可判的写动词**，脚本内部行为完全不可见。`python deploy.py` 无写动词、非白名单、危险扫描不命中 → 预检在宿主跑一次（脚本往 `D:\` 写），真机再跑一次（又写一遍）。**对任意脚本类命令双执行是有害的** | **高** |
| 网络外传未收词 | `Invoke-WebRequest`/`curl` POST 误伤面大，**待裁定** | 待裁定 |

---

### 3.7 【致命】词表绕过实证（2026-10-10 小欧 复核补录）

真实调用 `has_uncontainable_intent` 复现：

| 输入 | 判定 | 说明 |
|---|---|---|
| `Get-Process python \| Stop-Process -Force` | HIT | 原事故命令，拦住 ✓ |
| `taskkill /F /IM python.exe` | HIT | §3.3 原「无风险」，已补 ✓ |
| `pkill -9 -f python` | HIT | §3.3 原「无风险」，已补 ✓ |
| `$a='stop'; $b='process'; & $a$b -Id 999` | **MISS** | 字符串拼接 |
| `iex ('Stop'+'Process -Id 5')` | **MISS** | iex + 拼接 |
| `Get-CimInstance Win32_Process \| Invoke-CimMethod -MethodName Terminate` | **MISS** | WMI 绕开词表 |

> **2026-10-10 小欧 复核补注**：上表为 10-08 实测原始记录，**保留不改写**。
> 复核后实测：前两行（拼接类）已由 `normalize_for_intent` 收口为 **HIT**；
> 第三行（WMI）**仍 MISS**。详见本节末「部分修复」补记。

MISS 之后的链路（已逐行核对 `executor.py`）：

```
_scan_command_danger_intent → False（未命中）
_is_readonly_whitelisted     → False（非白名单前缀）
executor.py:264              → backend.run(command, workspace.path) 在宿主真跑
```

**结论：一条与 10-08 事故等价的「后端自杀」命令，可原样穿透全部四阶段。**
触发路径与原事故完全相同（agent 生成一条 bash 命令），故**该事故可以复发**。

#### 3.7.1 根因定性：黑名单路线不可能收敛

§3.4 立论「安全靠静态判定」——**「静态」解决的是确定性（可复现、无 TOCTOU），不是安全性**。
安全控制的第一定律是 **allowlist > denylist**：

- 黑名单 = 默认放行 + 列举危险 → 完备性**不可能**（危险命令空间无限：新工具、新别名、新参数形式、新编码）
- 白名单 = 默认拒绝 + 列举安全 → 完备性**可证**（不在表内即拒）

讽刺之处：项目内 `is_readonly_whitelisted` 的 `READONLY_PREFIXES`（23 项前缀，逐条过安全评审，
还否决了 `git branch`/`ipconfig` 裸前缀）**已经是一个合格的白名单**——**最好的那部分安全设计，
恰是本文档未打算推广的那部分**。C 类事实上已用白名单，A/B 类却仍走黑名单+弹窗。

#### 3.7.2 根因未消除：预检仍在宿主真跑

§3.4 曾论证「不需要单独立项改执行链」。该推理形式为：
**给定「预检必然在宿主真跑」这个前提**，推出「故须精确分类以尽量少真跑」——逻辑自洽，
**但前提本身可改且应当改**。真隔离三方案在本项目均可行：
低权限独立账户 / AppContainer(Restricted Token) / WSL2 容器。
任一落地，§3.7 全部绕过形态**一次性归零，且永久免维护词表**。

> 原否决理由（「PS 语法太动态，全面静态化误伤无穷，违反 YAGNI」）本身即**证明了黑名单路线不收敛**：
> 一条需永久维护、必然被绕过、绕过后果是系统自杀的防线，
> 成本远高于一次性改执行链。此处属**误用 YAGNI 为技术债辩护**，如实记录。

#### 3.7.3 【2026-10-10 小欧 部分修复，审计 P1-1】

上表**拼接类**两行已由 `normalize_for_intent` 收口（折叠 `+` 拼接 + 去引号，判定取原文与归一文并集），实测：

```
HIT | & ('Stop'+'-Process') -Id 5              归一后 → & (Stop-Process) -Id 5
HIT | $v='Stop'+'-Process'; & $v -Id 5         归一后 → $v=Stop-Process; & $v -Id 5
HIT | & ('task'+'kill') /PID 5                 归一后 → & (taskkill) /PID 5
MISS | Get-CimInstance Win32_Process | Invoke-CimMethod -MethodName Terminate   ← 仍漏
```

**但归一只解决「字面量被拆开」这一种手法，属点修复不属线修复。**下述手法**仍然 MISS**：

| 仍 MISS 的手法 | 为何归一救不了 |
|---|---|
| `Get-CimInstance Win32_Process \| Invoke-CimMethod -MethodName Terminate` | 动词是 `Terminate` 方法名，不在词表，需**收词**而非归一 |
| `[Diagnostics.Process]::GetProcesses() \| % { $_.Kill() }` | 同上，`.Kill()` 是方法调用 |
| `powershell -EncodedCommand <Base64>` | 动词藏在 Base64 里，**归一不解码** |
| 中文/全角字符变形 | 需 Unicode NFKC 归一化，本项未做 |

> 故 §3.7「黑名单路线不收敛、事故可复发」的结论**依然成立**，本次仅把绕过面收窄，**未清零**。
> **根治仍只能靠 §3.7.2 的预检真隔离（P0-1）**——那时 ① 整层连同词表与归一都可删除。
> 另需诚实记录：本次修复在**无真隔离的前提下给词表续了命**，属边际收益递减的补丁，
> 不应被读作「沙箱已加固」。

---

### 3.8 保护盾实证：事故形态贡献为 0（2026-10-10 小欧 复核补录）

```
protected-self   = True    Stop-Process -Id <自身>
protected-byName = False   Stop-Process -Name python
```

`extract_kill_target_pids` 三条正则只能抽**显式 PID**（`-Id n` / `/PID n` / `kill [-9] n`）；
事故命令 `Get-Process python | Stop-Process -Force` 是**按名杀**，抽出空集。

> §3.5 阶段三「接线 `_protected_pids()`」修复的是**真 bug**（原 `if protected_pids:` 恒不执行），接线本身正确。
> 但它保护的形态**恰好不是出事的形态**，故在真实事故中贡献为 0。原表把它列为四大成果之一，易高估。

**【2026-10-10 小欧 已修复，审计 P1-3】**

补名维度，按名杀现可拦：

| 改动 | 文件 | 内容 |
|---|---|---|
| 新增 | `utils/shell_readonly.py` | `extract_kill_target_names`（四形态：`-Name` / `Get-Process` 管道 / `taskkill /IM` / `killall`）+ `_name_matches`（去 `.exe`、casefold、`fnmatch` 通配）；`is_process_kill_protected` 增第三参 `protected_names` |
| 新增 | `safety/tool_safety_checker.py` | `_protected_process_names()`——由 `_protected_pids()` 的 PID 经 psutil 反查进程名（进程名解析归 safety 侧，`utils` 保持纯函数不 import tools） |
| 接线 | 同上 | 调用点补传第三个参数 |

实测（真实 `check_before_execute('bash', ...)`）：

```
受保护PID = [13028, 27304]     受保护名 = ['powershell.exe', 'python.exe']

BLOCKED   Get-Process python | Stop-Process -Force    ← P9-03 事故原形, 修复前恒不命中
BLOCKED   Stop-Process -Name python
直放/HITL  Stop-Process -Name node                    ← 不相关进程名不误拦
直放      git status
```

> 只读查询 `Get-Process -Name python`（无杀动词）**不误判为杀**，靠 `has_uncontainable_intent` 前置闸门区分。
> PID 口径与拼接归一（P1-1）口径均未退化。回归 **219 passed**。

---

### 3.9 【更正】§4.4 证据边界（2026-10-10 小欧 复核补录）

§4.4 原述「端到端过 `pre_execute`：`needs_ruling=True`、`stdout_tail`/`stderr_tail` 均为空、
日志无 `run 启动` —— 证明 `backend.run` **从未被调用**」。

**该证据只证明「预检那次没跑」，未证明「真机那次没跑」。**
而 10-08 事故的死因发生在**真机执行**环节，不在预检环节。
叠加 §3.4 更正（A 类实为 HITL 非 blocked），真实链路为：

```
check_before_execute → MEDIUM → 弹窗① ← 用户点「允许」
sandbox_gate        → needs_ruling(risky) → 弹窗② ← 用户点「允许」
真实执行 → 后端死亡
```

两个弹窗挡不住点了两次「允许」的用户，更挡不住 Prompt Injection 把命令包装成无害查询。
`ruling_kind="risky"` 使受信会话**也拿不到豁免**（`sandbox_gate.py:122` 仅对 `unsupported` 豁免）——此点设计正确，特此保留。

---

## 四、E2E 与单测验证实录

### 4.1 p9 全量 8 case（三轮）

| # | case | 第1轮(旧模型) | 第2轮(旧模型) | 第3轮(big-pickle) |
|---|---|---|---|---|
| 01 | empty_input | — | PASS | — |
| 02 | garbled_input | — | PASS | — |
| 03 | ambiguous_intent | **FAIL**（agent 杀后端） | **FAIL**（429） | 待跑 |
| 04 | multi_step | — | PASS | — |
| 05 | file_network | — | PASS | — |
| 06 | whitelist_regression | — | PASS | 改动后复跑 PASS（30.35s） |
| 07 | x2_final_signal | — | PASS | — |
| 08 | link_grouping | **FAIL**（429，任务3） | **FAIL**（429，任务1） | **PASS**（724.2s） |

失败根因除首轮agent 杀后端（已修）外，其余全部为**模型侧限流**：`HTTP 429 / inference exceeds tpm/rpm limit`，与代码无关。

> `run_p9_tests.py` 原清单漏 `test_p9_08_link_grouping`，本次补入；该文件另有一条 `.bak_20261004` 备份，`--collect-only` 核验收集正常（1 用例）。

### 4.2 p9_08 详情（第3轮通过）

| 项 | 值 |
|---|---|
| 结果 | PASSED，724.2s（12:04） |
| 任务数 | **5 个**（T1~T5，非 3 个） |
| SSE 事件 | 10041 |
| LLM 调用 | 28 次 |
| Token | 168670 prompt / 2923 completion / 171593 total |
| 模型 | `provider=opencodeZen, model=big-pickle` |
| 契约断言 | 门2 分组正确、门3 会话隔离、条款4、历史注入生效（任务2 知道 MAGIC-8808）、门5 failed 后仍并入同组 |

耗时 12 分钟属正常量级：5 个任务均为真实多步工具链路（read/write/searchweb/bash）+ 真实 LLM。

附带发现：`model.display_name=-`（空）—— 符合 2026-08-22 改造设计（display_name 不再落库，前端派生），**非缺陷**。

### 4.3 单测数据

| 范围 | 结果 |
|---|---|
| sandbox_executor + sandbox_bugs + shell_guard + compaction | **149 passed** |
| 安全/HITL/信任/沙箱守卫（16 文件） | **194 passed**, 1 warning |
| compaction 独立单测（17 函数/类） | **81 passed** |
| `test_repro_v01936`（迁移到现行契约后） | 16 passed |
| FUNCTIONS.md 条目与代码签名一致性 | 8/8 通过（`inspect.signature` 核对，防僵尸条目） |

### 4.4 JobObject 内核读回验证

不靠日志自证，用 `QueryInformationJobObject` 读回实际生效值：

```
LimitFlags=0x00002108   ← 0x2000 KILL_ON_JOB_CLOSE | 0x0100 内存 | 0x0008 ACTIVE_PROCESS
ActiveProcessLimit=64   ProcessMemoryLimit=2048MB
孙进程测试: GRANDCHILD_REFUSED   ← 限 1 个时内核真实拒绝创建
子进程正常: rc=0 'child-ok'       ← 未误杀正常命令
```

杀进程类命令端到端过 `pre_execute`：`passed=False`、`needs_ruling=True`、`stdout_tail`/`stderr_tail` **均为空**，日志无 `run 启动` —— 证明 `backend.run` **从未被调用**。

### 4.5 提交与文档回写

| Commit | 内容 |
|---|---|
| `3bffa5f3e` | fix:safety/sandbox 杀进程防护四阶段 |
| `dcd65dd8e` | feat:compaction/start_step C4 摘要前降本接线 |
| `0059f469d` | test:test_inject_compact_pipeline（**经北京老陈指令，覆盖「严禁 commit 测试 case」铁规**，已在 commit message 首行标注） |
| `927a53a9d` | docs:FUNCTIONS.md 补登记 v4.9（4 章节 8 函数，含漏登记的 `aclose_stream`） |

---

## 五、遗留待办

> **2026-10-10 小欧 复核重排**：复核发现原 6 项遗漏了**事故可复发**的根因项，故重排。
> 排序= **处置优先级**：1~2 为事故复发防控(P0)，3~11 为 P1 与原 6 项顺延。
> 序号连续无跳号，优先级单列一栏，不再与序号混写。

| 序 | 事项 | 优先级 |
|---|---|---|
| 1 | **预检改真隔离**（低权限独立账户 / AppContainer / WSL2 任一）——落地后 §3.7 全部绕过形态一次性归零，**永久免维护词表** | **P0 根治** |
| 2 | **A 类命中改 `blocked`**（对齐 §3.4 原则，消掉「两次弹窗」假象） | **P0 止血** |
| ~~3~~ **已撤回** | ~~白名单模式推广：不在 `READONLY_PREFIXES` 内 → 不进预检，直接 HITL~~ **2026-10-10 撤回，理由见下方注记；原 3~12 顺延为 3~11** | ~~P0~~ 撤回 |
| 3 | 补 evasion 单测集（拼接/引号/通配/大小写/只读查询不误判）固化进 `sandbox_bugs` 防回归 | P1 |
| 4 | 补 `--reload` worker 子进程进 `_protected_pids`（`getppid()` 覆盖不到派生 worker） | P1 |
| 5 | p9_03 重跑（换 big-pickle 后唯一未复验 case） | 待办 |
| 6 | 网络外传命令是否收词 | **待北京老陈裁定** |
| 7 | 429 限流无退避重试（tpm/rpm 属可重试错误，当前直接判 failed） | 独立问题 |
| 8 | compaction 死代码二选一：接 C5 或删除约 350 行（见 §1.7 补注） | 待办 |
| 9 | 打 tag（需先在 `version.txt` 头部插 commit 汇总） | 待办 |
| 10 | 增量摘要「旧声称残留」的成对校验手段（见 2.5.1） | 待办，与 `[17]` §4.2 呼应 |

#### 撤回记录：原第 3 项「白名单模式推广」（2026-10-10 小欧）

该建议由本次审计提出，复核后**自查判定错误并撤回**，如实留痕不无声删除：

| 项 | 说明 |
|---|---|
| 原建议 | 凡不在 `READONLY_PREFIXES` 只读白名单内的命令，一律不进预检，直接转 HITL |
| **撤回理由一** | 日常命令全不在该白名单内（`python script.py` / `npm run build` / `pytest`），照此执行将导致**几乎每条命令都弹窗**，安全检查沦为骚扰，工作流不可用 |
| **撤回理由二** | **问题问错了**。在「预检跑宿主」前提下，预检的危险不在于「挑错了命令去跑」，而在于「**它在宿主上跑**」——挑谁去跑都一样危险，收紧准入名单解决不了问题 |
| 正确归属 | 本项**只有在第 1 项（预检真隔离）落地后才有意义**：届时跑什么命令都无害，A/B/C 三类分类整套失去意义，本项自动作废 |
| 教训 | **误用局部收紧冒充安全提升**。与 §3.7.2 指出「误用 YAGNI 为技术债辩护」是同一类错误——以调整参数冒充改变前提 |

> 原第 4/5/6 项（命令规范化 / evasion 验证 / 按名匹配）已于 2026-10-10 实施完毕并闭环，
> 逐项实测见 §3.7.3 与 §3.8，详见 v1.3 版本历史。

---

## 版本历史

| version | 时间 | 更新内容 | 作者 |
|--------|------|---------|------|
| v1.0 | 2026-10-08 11:19:17 | 新建。①第一章 compaction 包能力盘点（20 函数/已接入 4/未接入 16，含盘点脚本两处误判修正记录与接线优先级建议）；②第二章摘要降本三方案实测对比与方案2 裁定依据、顺带修复的 4 项既有缺陷；③第三章 agent 杀进程事故实录、根因（预检即真跑）、三层防护失效分析、A/B/C 三类分流设计原则与四阶段落地、5 项已知不完美；④第四章 E2E 三轮实录（p9 全量 8 case + p9_08 详情）、单测数据、内核读回验证、提交与文档回写；⑤第五章遗留待办 5 项 | 小欧 |
| v1.1 | 2026-10-08 11:49:26 | 北京老陈追问"都加全了吗"，自查发现缺口并补齐。①新增 §2.5 `generate_chunked_summary` 补测(此前全仓唯一"存在但零验证"的 LLM 摘要功能): 三列对照表(A 基线 anchored 全量 7220 tok/40.9s/1834 字符/6-6、B 段1 anchored 前150 4968 tok、B 段2 chunked 后56 4337 tok/4387 字符/6-6)、结论一单次压缩合计 9305 tok 比全量贵 29% 故不划算、结论二价值在多次压缩(线性而非平方增长)、§2.5.1 质量风险「增量版 Key Decisions 残留旧声称 158 份而 Progress 已更正 3066 份，同摘要内口径不一致」并给出成对校验硬约束、§2.5.2 暂不接入三条理由; ②新增 §2.6 待补 p9_03 复验说明; ③§1.6 表格 generate_chunked_summary 行由"见 2.5"改为已补测并暂不接入; ④第五章新增待办第 6 项(旧声称残留成对校验手段)。v1.0 保留 | 小欧 |
| v1.2 | 2026-10-10 08:48:19 | 北京老陈指令「评价设计可行性和漏洞、代码逻辑是最佳还是最差」，逐条与实际代码对账并实证复现后修订。**核心结论：四阶段止血有效但未消除根因，原事故可复发。**①§3.4 加更正说明——A 类「静态命中即 blocked」属设计意图, 实测 `executor.py:244-247` 返回 `needs_ruling=True` 转 HITL, 二者只能存其一, 本文档不作事后合理化; ②§3.5 更名「四阶段止血落地(非防护体系)」并新增「对后端自杀的实贡献」列, 阶段三贡献 0、阶段四属防失控非防杀宿主; ③**§3.6 补登漏登记的致命项: 静态词表可被绕过(黑名单固有)**, 置顶并标严重度; ④**新增 §3.7 词表绕过实证**——`$a='stop'; $b='process'; & $a$b` / `iex ('Stop'+'Process')` / `Get-CimInstance Win32_Process Invoke-CimMethod Terminate` 三类实测 MISS, MISS 后经 `executor.py:264` 在宿主真跑, 穿透路径与原事故一致; 含 §3.7.1 黑名单路线不可能收敛(allowlist>denylist, 且项目内 `READONLY_PREFIXES` 已是合格白名单却未推广)、§3.7.2 根因未消除(预检仍在宿主真跑, 原否决理由误用 YAGNI 为技术债辩护); ⑤**新增 §3.8 保护盾实证**——`protected-byName=False`, 阶段三保护的形态恰非出事形态, 真实事故贡献为 0(接线本身仍是对的, 修了真 bug); ⑥**新增 §3.9 更正 §4.4 证据边界**——该证据只证预检没跑, 未证真机没跑, 而事故死因在真机环节, 补记真实两弹窗链路; ⑦§1.7 加 YAGNI 定性补注——compaction 628 行/20 函数/接入 4, 死代码约 350+ 行, 五个函数自闭环外部零引用, 正确处置是二选一而非排队; 并澄清已接入的 `prune_tool_output_keeping_tail` 只清 content 不删消息, 故「删除式裁剪先过 remove_dangling_tool_calls」规则当前未被违反; ⑧第五章按优先级重排, 新增 P0-1 预检改真隔离(根治)/P0-2 A 类改 blocked/P0-3 白名单模式推广 三项事故复发防控, 原 6 项顺延。v1.0/v1.1 全部保留 | 小欧 |
| v1.3 | 2026-10-10 09:03:48 | 北京老陈批准实施审计 P1-1 + P1-3 后同步实录。**P1-1 命令规范化**：`utils/shell_readonly.py` 新增 `normalize_for_intent`（折叠 `+` 字符串拼接 + 去引号，循环至不动点，必收敛），`has_uncontainable_intent`/`extract_kill_target_pids` 取**原文与归一文并集**，`_PID_TARGET_RES` 首条分隔符改 `\W*` 以覆盖 `& ('Stop-Process') -Id n` 括号形态；拼接类绕过 MISS→HIT 收口。**P1-3 按名匹配**：新增 `extract_kill_target_names`（四形态：`-Name`/`Get-Process` 管道/`taskkill /IM`/`killall`）+ `extract_kill_target_names_from_pipeline` + `_name_matches`（去 `.exe`、casefold、`fnmatch` 通配），`is_process_kill_protected` 增第三参 `protected_names`；safety 侧新增 `_protected_process_names()`（由 `_protected_pids()` 经 psutil 反查名，`utils` 保持纯函数不 import tools），调用点接线。**实测**：P9-03 事故原形 `Get-Process python | Stop-Process -Force` 与 `Stop-Process -Name python` 现均 `blocked`（修复前恒不命中），`Stop-Process -Name node` 不误拦，只读查询 `Get-Process -Name python` 不误判为杀（靠 `has_uncontainable_intent` 前置闸门）。**回归 219 passed**（sandbox/shell_guard/hitl 共 15 文件），零退化。**文档**：§3.6 新增「④ 命令双执行」致命项（原「已论证无害」论证被推翻，见 `python deploy.py` 反例）；§3.6 ①③ 两项标注已修并降级；§3.7.3 新增「部分修复」小节，明列 WMI/`.Kill()`/`-EncodedCommand` Base64/中文变形**仍 MISS**，并如实记录「本次是在无真隔离前提下给词表续命，属边际收益递减，不应读作沙箱已加固」；§3.8 补修复后实测；第五章待办 4/5/6 划线闭环。**P0-2（A 类改 blocked）未获批准，未实施**。**同日复核撤回原第 3 项「白名单模式推广」**——日常命令（`python script.py`/`npm run build`/`pytest`）全不在只读白名单内，照此执行将致几乎每条命令弹窗；且在「预检跑宿主」前提下收紧准入名单解决不了问题（危险在于「在宿主上跑」而非「挑错命令」）。该项**只有第 1 项真隔离落地后才有意义**，已划线撤回并新增「撤回记录」小节留痕；第五章序号顺延为 3~11（原 4/5/6 已闭环者移入撤回记录下方说明）。v1.0/v1.1/v1.2 全部保留 | 小欧 |