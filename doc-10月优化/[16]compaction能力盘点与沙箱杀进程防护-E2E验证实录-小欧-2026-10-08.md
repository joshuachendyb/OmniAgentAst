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

| 序 | 目标 | 理由 |
|---|---|---|
| 1 | `remove_dangling_tool_calls` | 2026-10-08 刚修好且已单测；**任何删除式裁剪都必须先过它**，属安全前置 |
| 2 | `use_tool_summary` | **前置条件未满足**（1.5：上游无 summary 生产者），接了也是空跑；须先有工具产出 summary |
| 3 | `truncate_oversized_message` | 解决「单条超长 tool 撑爆窗口」，比整体裁剪更精准 |
| 4 | C5 三件套 + `generate_chunked_summary` | 长任务多次压缩场景才需要，工作量最大；`generate_chunked_summary` 已完成真实实测（见 2.5），接线风险已降低 |

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

**双执行问题在三类分流下自然收敛**：A/B 不真跑；C 类预检写的是临时工作区（`workspace.destroy()` 销毁），真实文件只被真机那次写入。故不需要单独立项改执行链，也不需要做「全面静态化」（PS 语法太动态，误伤无穷，违反 YAGNI）。

### 3.5 四阶段落地

| 阶段 | 文件 | 内容 |
|---|---|---|
| 一 | `utils/shell_readonly.py` +62 | `UNCONTAINABLE_VERBS`（8 词表）+ `has_uncontainable_intent` / `extract_kill_target_pids` / `is_process_kill_protected` 三纯函数 |
| 二 | `sandbox/executor.py` | `_scan_command_write_intent` 改名 `_scan_command_danger_intent` 并扩职责，命中即转 HITL **而不 run**；旧名零残留不留别名 |
| 三 | `safety/tool_safety_checker.py` | 新增 `_protected_pids()`（自身+父进程+shell池）+ 接线，命中即 `blocked=True` 直返 |
| 四 | `sandbox/job_object.py` | 补 `KILL_ON_JOB_CLOSE` + `ACTIVE_PROCESS_LIMIT`（默认 64） |

收录标准：`SHELL_DANGEROUS_PATTERNS` 只到 MEDIUM（弹窗后仍进预检）拦不住者才收；HIGH 级（`Stop-Computer`/`Format-Volume`/`shutdown`）预检前已 blocked，收录即重复（DRY）。前后向断言用 `[a-z0-9_-]` 字符类而非 `\b`，避免 `kill` 命中 `killall`/`taskkill` 内部。

### 3.6 已知不完美（如实登记，不假装解决）

| 项 | 说明 |
|---|---|
| `_protected_pids` 覆盖不全 | `getppid()` 是 reloader 父进程，覆盖不到 `--reload` 派生的 worker 子进程，**待办** |
| `echo "kill"` 误命中 | 引号内裸词亦命中 → 转 HITL 而非直放。与该文件既有「取严」哲学一致（漏放是真机执行，误拒只是多弹一次窗） |
| JobObject 两项限额不阻止杀宿主 | 代码注释已明确该职责由 `shell_readonly` 静态判定承担 |
| 命令双执行 | 仅 C 类仍存在（预检+真跑），已论证无害，不动 |
| 网络外传未收词 | `Invoke-WebRequest`/`curl` POST 误伤面大，**待裁定** |

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

| 序 | 事项 | 性质 |
|---|---|---|
| 1 | p9_03 重跑（换 big-pickle 后唯一未复验 case） | 待办 |
| 2 | `_protected_pids` 覆盖 `--reload` worker 子进程 | 安全待办 |
| 3 | 网络外传命令是否收词 | **待北京老陈裁定** |
| 4 | 429 限流无退避重试（tpm/rpm 属可重试错误，当前直接判 failed） | 独立问题，不在本次范围 |
| 5 | 打 tag（需先在 `version.txt` 头部插 commit 汇总） | 待办 |
| 6 | 增量摘要「旧声称残留」的成对校验手段（见 2.5.1） | 待办，与 `[17]` §4.2 呼应 |

---

## 版本历史

| version | 时间 | 更新内容 | 作者 |
|--------|------|---------|------|
| v1.0 | 2026-10-08 11:19:17 | 新建。①第一章 compaction 包能力盘点（20 函数/已接入 4/未接入 16，含盘点脚本两处误判修正记录与接线优先级建议）；②第二章摘要降本三方案实测对比与方案2 裁定依据、顺带修复的 4 项既有缺陷；③第三章 agent 杀进程事故实录、根因（预检即真跑）、三层防护失效分析、A/B/C 三类分流设计原则与四阶段落地、5 项已知不完美；④第四章 E2E 三轮实录（p9 全量 8 case + p9_08 详情）、单测数据、内核读回验证、提交与文档回写；⑤第五章遗留待办 5 项 | 小欧 |
| v1.1 | 2026-10-08 11:49:26 | 北京老陈追问"都加全了吗"，自查发现缺口并补齐。①新增 §2.5 `generate_chunked_summary` 补测(此前全仓唯一"存在但零验证"的 LLM 摘要功能): 三列对照表(A 基线 anchored 全量 7220 tok/40.9s/1834 字符/6-6、B 段1 anchored 前150 4968 tok、B 段2 chunked 后56 4337 tok/4387 字符/6-6)、结论一单次压缩合计 9305 tok 比全量贵 29% 故不划算、结论二价值在多次压缩(线性而非平方增长)、§2.5.1 质量风险「增量版 Key Decisions 残留旧声称 158 份而 Progress 已更正 3066 份，同摘要内口径不一致」并给出成对校验硬约束、§2.5.2 暂不接入三条理由; ②新增 §2.6 待补 p9_03 复验说明; ③§1.6 表格 generate_chunked_summary 行由"见 2.5"改为已补测并暂不接入; ④第五章新增待办第 6 项(旧声称残留成对校验手段)。v1.0 保留 | 小欧 |