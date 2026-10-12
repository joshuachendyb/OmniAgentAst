# [27] observation.content 字段启用设计方案

创建时间：2026-10-12 11:28:58
更新时间：2026-10-12 14:32:10
版本：v2.0
编写人：小欧

版本历史

| 版本 | 时间 | 编写人 | 修改说明 |
|---|---|---|---|
| v1.0 | 2026-10-12 11:28:58 | 小欧 | 新建（北京老陈令：启用 observation.content 字段，供前端 UI 渲染） |
| v2.0 | 2026-10-12 14:32:10 | 小欧 | 第三章整章重写：并入 65 工具/6107 次调用的参数实测基线；参数规整升级为"通用规则+特殊规则+长度分级"；剔除 `metrics`；删除二态 `ok`，`exec_code` 改三态；补真源约定与 8 条防御 |

---

## 一、需求与设计目标

### 1.1 需求内容与渲染显示需求

北京老陈 2026-10-12 指令：`observation` 类型的 step，其 `content` 字段当前从未被使用，现要求启用该字段。

约束（用户明确指定）：

| 编号 | 约束 | 说明 |
|---|---|---|
| R1 | 不改 summary 字段 | `llm_data.summary` 维持现状，不动它 |
| R2 | 一个工具一行 | 单工具 observation 产出 1 行；多工具 observation 产出 N 行，每行一个工具 |
| R3 | 行内必须是结构化字段，不是一句话 | ⚠️ 2026-10-12 修正（小欧曾误解为"拼一句摘要"）。每行内含 tool / exec_code / params 等离散字段，前端可逐字段取用，禁止"把内容拼成一句话" |
| R4 | 参数按工具分类规整，不是全量也不是统一截断 | ⚠️ 2026-10-12 修正（小欧曾设计为"统一截断加省略号"，用户明确否定）。见 3.5 |
| R5 | 长参数按长度判断 | ⚠️ 2026-10-12 修正。小欧曾设计为"截断成 `…`"，用户明确要求不做截断。最终规则见 3.5.4（按参数性质分级，而非一刀切） |
| R6 | 已知单工具与多工具两种形态 | 方案须同时覆盖 |
| R7 | 先落后端，前端后跟 | 2026-10-12 确认实施顺序 |

前端渲染需求（期望效果）：

```
┌ 执行动作 ──────────────────────────────────┐
│ ▶ 1/2  bash        成功   2.8s             │
│      命令: Invoke-RestMethod -Uri https://… │
│ ▶ 2/2  timenow     成功   0.0s             │
│      （无参）                                │
└────────────────────────────────────────────┘
```

即：每个工具一行，行为"图标/名称/状态徽标/耗时"，参数区只留核心参数；失败行追加 `detail`（失败详情）。

### 1.2 本方案要回答的问题

| 问题 | 答案位置 |
|---|---|
| `content` 现在是什么？为什么没人用？ | 第二章 |
| 参数从 `tool_result` 的哪个字段取？怎么筛？ | 3.3 / 3.5 |
| content 装什么结构？前端怎么渲染？ | 3.4 / 3.8 |
| 改哪些文件？有没有副作用？ | 3.7~3.11 |

---

## 二、现状分析

### 2.1 实测数据（近 4000 条真实 step）

| step 类型 | 总数 | `content` 为空 | `content` 有值 |
|---|---|---|---|
| observation | 768 | 768（100%） | 0 |
| action | 767 | 767（100%） | 0 |
| stats | 927 | 927（100%） | 0 |
| final_stats | 141 | 141（100%） | 0 |
| thought | 785 | 305 | 480 |
| history_context | 314 | 210 | 104 |
| start / final / merged | 298 | 0 | 298 |

结论：`observation` 的 `content` 是 100% 空串，从未写入过任何值。 而 `thought` / `start` / `final` 等类型都正常有值 —— 说明这不是"字段设计缺失"，而是 observation 这一路从未接入。

### 2.2 `content` 为何恒空（后端证据）

| 位置 | 事实 |
|---|---|
| `backend/app/services/agent/steps/observation_step.py:27-28` | `get_content()` 硬编码 `return ""` |
| `backend/app/services/agent/steps/base.py:85` | 基类 `to_dict()` 无条件输出 `"content": ""` |
| `backend/app/services/agent/observation_builder.py:153` | 构造 `ObservationStep(step=..., tool_result=...)`，根本没传 content |

### 2.3 `content` 为何没人用（前端证据）

| 位置 | 事实 |
|---|---|
| `frontend/src/features/chat/services/sseParser.ts:904` | 唯一正式载体是 `step.tool_result = tr`（整数组原样挂上） |
| `sseParser.ts:911-912` | 2026-10-04 明确删除了 `step.content = step.summary` 的写法 |
| `ToolCallLine.tsx:459-461` | 两处 `content` 兜底已删，注释确认 |
| `ToolResultRenderer/index.tsx` | 只认 `step.tool_result[0]`，读 summary / detail / hint / metrics / timestamp / duration_ms |

### 2.4 `content` 是否影响 LLM（关键安全性确认）

结论：不影响。 LLM 上下文读的是 `data_text`，不是 `content`。

| 消费方 | 位置 | 读哪个字段 |
|---|---|---|
| 运行时喂 LLM | `observation_builder.py:112,116` | `obs_text`（与 data_text 同源变量） |
| 会话回放 | `backend/app/services/chat/history_loader.py:159-175` | `el["data_text"]` |

结论：`content` 不参与任何 LLM 上下文构建，content 投影为纯新增展示层。

### 2.5 序列化链路（content 是否会被丢弃）

| 环节 | 结论 |
|---|---|
| `ReasoningStep.to_dict()` → `_extra_fields()` | 全量透传 |
| `sse_formatter.py:37-52` `base.update(data)` | 无字段白名单，不丢 |
| `storage.py:312-318` 落库 | 整份 `step_json` 写入，不截断 |
| `storage.py:321-330` `_strip_thought_content` | 只剥 thought 的 content，observation 原样保留 |

### 2.6 `tool_result[]` 现有元素结构（构建 content 的原料）

后端 `observation_builder.py:129-134` 拼装：

```python
{"tool_name": call.tool_name, "llm_data": result.llm_data,
 "data_text": obs_text, "other_data": result.other_data}
```

实测真实样本（单工具 / 多工具各一）：

| 字段 | 子字段 | 实测值示例 |
|---|---|---|
| `tool_name` | — | `bash` / `timenow` |
| `llm_data` | `action.tool` | `bash` |
| | `action.tool_zh` | `执行` / `获取时间` |
| | `action.params` | `{command, shell_type, timeout}` / `{}` |
| | `status.exec_code` | `success` |
| | `status.message` | `执行成功` |
| | `status.detail` / `hint` | 失败时才有内容 |
| | `duration_ms` | `2819` / `0` |
| | `metrics` | `{exit_code, output_len}` / `{}` |
| | `summary` | 长文本（按 R1 不动它） |
| `other_data` | `retry_count` | `0` |
| `data_text` | — | 长文本（喂 LLM 用，本方案不依赖） |

元素级自包含，下标对齐 `action.tools[i]` —— 这正是构建 content 的理想原料。

### 2.7 现状小结

| 维度 | 现状 |
|---|---|
| 后端写入 | 恒 `""`，未接入 |
| 前端读取 | 零读取 |
| LLM 消费 | 读 data_text，不读 content |
| 落库/序列化 | 全量透传，不丢字段 |
| 结论 | `content` 是跨层契约里的死字段，四条链路（生成/解析/渲染/LLM 上下文）全部绕开它。现在启用它，等于新增一条"摘要视图"链路，不动任何既有链路。 |

---

## 三、实施方案

### 3.1 总体思路与硬约束

> 用现有 `tool_result[]` 元素，投影出一份"每工具一条"的结构化数据，写入 `observation.content`。

| 原则 | 说明 |
|---|---|
| 只增不改 | 新增 content 投影；`tool_result` / `data_text` / `summary` 全部保持原样 |
| 下游零风险 | LLM 不读 content，既有前端不读 content，故本改动对既有链路完全无副作用 |
| 幂等 | 纯函数投影，同输入同输出，不改任何外部状态 |
| 真源唯一 🔴 | `tool_result[]` 是唯一真源；`content` 是其只读投影，任何链路禁止回写 content，否则两处数据必然漂移 |
| LLM 隔离 🔴 | `content` 严禁进入 LLM 上下文；须加单测锁死"content 不得喂 LLM" |
| 内容纪律 | 不含 `summary`（R1）、不含 `data_text`（长文本），保持"简明扼要" |

### 3.2 决策台账（已裁定，本章其余小节均按此执行）

| # | 议题 | 裁定 | 时间 |
|---|---|---|---|
| D1 | content 存储形态 | JSON 数组字符串入 `content`（字段类型仍是 `str`，不动 ExecutionStep 契约）；数组元素为结构化字段对象，非一句话 | 2026-10-12 |
| D2 | 参数处理方式 | 通用规则 + 特殊规则 + 长度分级三层规整（3.5），不做统一截断 | 2026-10-12 |
| D3 | 实施顺序 | 先落后端，前端渲染后跟；前端「有 content 渲染、无则不渲染」 | 2026-10-12 |
| D4 | `message` 是否保留 | 保留。取自 `status.message`，成功时虽短但零成本，失败时是有效信息 | 2026-10-12 |
| D5 | content 体积上限 | 2KB。超限时按顺序剔除 `params` 值，状态/耗时/detail 永不受影响 | 2026-10-12 |
| D6 | 路径参数键名分叉 | 不改名不改写：当前 schema 只有 path 与 dest 两种真实路径键，各按原样保留（曾拟统一归一为单一键名并自造新词，均已废：北京老陈裁定 content 不得出现系统不存在的键名） | 2026-10-12 |
| D7 | 超长主体参数如何处理 | 按性质分级（3.5.4）：命令/代码正文类取首行；标识类（path/url/query/pattern）超 50 整个丢弃。不用统一截断，也不一律丢 | 2026-10-12 |

### 3.3 数据来源与实测基线

#### 3.3.1 取值来源（唯一，无二源）

| content 字段 | 取自 `tool_result[i]` 的路径 |
|---|---|
| `tool` | `llm_data.action.tool`（回退 `tool_name`） |
| `tool_zh` | `llm_data.action.tool_zh` |
| `exec_code` | `llm_data.status.exec_code` |
| `message` | `llm_data.status.message` |
| `params` | `llm_data.action.params`（经 3.5 三层规整） |
| `duration_ms` | `llm_data.duration_ms` |
| `detail` | `llm_data.status.detail` |

#### 3.3.2 现状基线（参数实测样本，仅供理解参数形态）

抽样 `chat_task_steps` 中出现频次最高的工具，用于理解各参数的实际形态与长度分布：

| 工具 | 出现 | 实测参数键 | 参数个数分布 |
|---|---|---|---|
| `bash` | 1531 | `command`(1531) `shell_type`(1531) `timeout`(1531) `cwd`(191) | 3 个:1340 / 4 个:191 |
| `read` | 1168 | `path`(1168) `limit`(501) `offset`(308) `tail`(11) | 1 个:647 / 2 个:222 / 3 个:299 |
| `write` | 908 | `path`(907) `append`(906) `encoding`(892) `content`(1) | 2 个:2 / 3 个:892 |
| `searchweb` | 909 | `query`(909) `num_results`(909) | 2 个:909 |
| `edit` | 342 | `path`(342) `old_string`(342) `ignore_case`(342) `new_string`(340) `mode`(42) | 3 个:2 / 4 个:298 / 5 个:42 |
| `fetchpage` | 271 | `url`(271) `extract_format`(271) `js_render`(271) `timeout`(271) `prompt`(208) | 4 个:63 / 5 个:208 |
| `listdir` | 178 | `path`(178) `sort_by`(178) `include_hidden`(178) `offset`(15) | 3 个:163 / 4 个:15 |
| `grep` | 156 | `pattern`(156) `path`(156) `ignore_case`(155) `context`(50) `glob`(29) | 3~5 个 |

注：本表仅作参数形态参考；取/丢的权威依据是 3.5.6 明细表（当前注册表 schema），两者不冲突时以 3.5.6 为准。

#### 3.3.3 由此归纳出的三条事实

| # | 事实 | 证据 |
|---|---|---|
| F1 | LLM 几乎总是把 schema 默认值一并填满 | `bash` 1531/1531 次都带 `shell_type`+`timeout`；`edit` 342/342 次都带 `ignore_case`；`delete` 37/37 次都带 `recursive`+`force` |
| F2 | 每个工具只有 1~2 个真正的主体参数 | `command` / `query` / `pattern` / `url` / `content` / `old_string`+`new_string` |
| F3 | 路径参数键名分叉 | `delete` 用 `source`，其余文件类一律用 `path` |

### 3.4 content 结构定义（最终 7 字段）

存储形态：`content` 字段类型仍是 `str`（不改 ExecutionStep 契约，避免波及其他 step 类型），内容为一个 JSON 数组字符串。

```jsonc
[
  {
    "tool": "bash",                  // 工具名（机器可读）
    "tool_zh": "执行",               // 中文名（UI 直接显示，省前端映射）
    "exec_code": "success",          // 三态: success / warning / error（前端直接映射三色）
    "message": "执行成功",            // 结果短句
    "params": { "command": "Invoke-RestMethod -Uri 'https://wttr.in/?format=j1'" },
    "duration_ms": 2819,             // 耗时（为 0 时前端不显示）
    "detail": ""                    // 失败详情（成功时为空串）
  },
  { "tool": "timenow", "tool_zh": "获取时间", "exec_code": "success", "params": {}, "duration_ms": 0, "detail": "" }
]
```

字段集审计结论（逐字段审"是否必要/是否可稳定渲染"）：

| 字段 | 判定 | 说明 |
|---|---|---|
| `tool` | ✅ 保留 | 机器可读工具名，供前端直接显示；`action.tool` 缺失时回退 `tool_name`。一个工具一条，不存在配对或去重需求 |
| `tool_zh` | ✅ 保留 | 后端已有（`action.tool_zh`），前端零映射表 |
| `exec_code` | ✅ 保留（三态） | `success` 成功 / `warning` 有产出但降级 / `error` 失败。前端直接映射三色，无派生层 |
| `message` | ✅ 保留 | 取自 `status.message`，成功时虽短但零成本，失败时是有效信息 |
| `params` | ✅ 保留 | 核心参数是本字段存在的主要理由，按 3.5 规整 |
| `duration_ms` | ✅ 保留 | 实测存在 `0`（如 `timenow`），前端按 `>0` 决定是否显示，避免 "0.0s" |
| `detail` | ✅ 保留 | 失败原因，失败行必须显示 |

存储形态的代价（明示，供后续复议）：JSON 数组字符串落到 `step_json` 里是转义后的一长串（人肉查库可读性差）、且需一次 `dumps`。这是"不动 ExecutionStep 类型契约"换来的代价，已按"用起 content 字段"的要求选定；若将来允许改类型，直接存对象数组可消除该代价。

### 3.5 参数规整规则（D2 核心）

#### 3.5.1 参数三分类（以 3.5.6 明细表为唯一真源）

| 类别 | 实测实例 | 处置 |
|---|---|---|
| 主体参数（每工具 1~2 个） | `command` `query` `pattern` `url` `sql` `operations` `table_name` `sheet_name` | 进 content |
| 框架默认开关（无信息量） | `shell_type` `encoding` `ignore_case` `overwrite` `preserve_metadata` `extract_format` `js_render` `proxy` `success_codes` `append_mode` | 丢 |
| 正文长文本（超长易炸） | `content` `slides` `table_data` `old_string` `new_string` | 丢（edit 的 old/new 另按 3.5.3 转行数） |
| 路径参数 | `path` `dest` | 进 content，按真实键名原样保留（D6） |
| 用户主动选择（行为/范围/目标定位） | `timeout` `limit` `offset` `tail` `mode` `sort_by` `sheet_name` `include_hidden` `recursive` `force` `num_results` `page` `pages` `slide` `max_depth` `dry_run` `password` `connection_string` `allowed_domains` `blocked_domains` `top_n` `table_name` | 进 content |

同名参数统一待遇（北京老陈 2026-10-12 裁定）：同一参数名在所有工具中取舍一致，不因工具而异；改表即改本节，二者不得脱节。

#### 3.5.2 通用规则（以 3.5.6 表为准，无需逐工具登记）

> 保留「主体参数 + 路径参数 + 用户主动选择」，丢弃「框架默认开关 + 正文长文本」；路径参数按真实键名原样保留，不改名不合并。

| 收益 | 说明 |
|---|---|
| 新工具免登记 | 63 个注册工具全部符合该规律，新工具不登记也基本正确 |
| 消除默认值噪声 | 对应实测事实 F1（LLM 总把默认值填满） |

框架默认开关名单（3.5.6 表中丢列的全部即此集合）：
```
shell_type, encoding, ignore_case, overwrite, preserve_metadata,
extract_format, js_render, proxy, success_codes, append_mode
```

> 该名单与 3.5.6 表的丢列一一对应，改表即改本节，二者不得脱节。

#### 3.5.3 特殊规则（仅 4 类工具）

| 工具/参数 | 特例规则 | 理由 |
|---|---|---|
| edit | old_string / new_string 转行数：两者原文不进 content，改用 difflib 对两段按行做差异，输出 lines_added（增加行数）与 lines_removed（减少行数）；path 与 mode 照常保留 | 两者原文实测 93% 超长，按长度规则会被整项丢弃等于白丢；行数增减恒定不超长，且保住"改了多少"这一核心信息 |
| write | content 不进 content；append、encoding、path 照常保留 | content 是超长正文，最长实测 37177 字符 |
| 路径参数 | 不做任何改名，`path` 与 `dest` 各按真实键名原样保留 | 北京老陈 2026-10-12 裁定：content 只用系统真实存在的键名，不发明新词 |
| 无参工具（timenow、timer_list、mouse_position 等） | params 输出 {} | 当前 schema 确实无参数 |

#### 3.5.4 长度分级规则（D7）

实测打脸了"统一 50 阈值"：若一律丢弃，绝大多数工具参数全空：

| 工具 | 值超 50 字符占比 | 最长实测 |
|---|---|---|
| `bash` | 1380/1531 = 90% | `command` 16157 |
| `edit` | 317/342 = 93% | `old_string` 80+ |
| `read` | 277/1168 = 24% | `path` 112 |
| `searchweb` | 348/909 = 38% | `query` 136 |
| `write` | 117/908 = 13% | `content` 37177 |
| `listdir` / `tree` | < 2% | — |

分级规则：

| 参数性质 | 判定 | 处置 |
|---|---|---|
| 命令正文类（`command` `sql` `query` `prompt`） | 多行长文本，首行几乎总能说明在干什么 | 取首行；首行仍超 50 则整项丢弃 |
| 标识类（`path` `dest` `url` `pattern` `host` `method`） | 单行短标识，超长即无意义 | 超 50 即整项丢弃（键值对消失，不写 null、不写 `…`） |
| 已列入 3.5.2 丢列的参数 | 框架默认开关与正文长文本 | 直接丢弃，不做长度判定 |

> 禁止统一截断：不使用 `…`、不切尾巴。超限即整个参数值不要（`R5` + D7）。

#### 3.5.5 未登记工具的兜底

| 场景 | 行为 |
|---|---|
| 新增工具（不在 3.5.6 表内） | 按 3.5.2 通用规则归类；若归类后保留列为空 → `params` 输出 `{}` |
| 静默丢弃的补救 🔴 | 用户看到"没有参数"时无法分辨是"工具本就无参"还是"归类遗漏"。硬性要求：保留列为空时打一条 debug 级日志（含 tool 名），使归类遗漏可被日志发现 |

#### 3.5.6 tool的取params的明细表

参数键取自当前注册表 schema（tool_registry.get_tool(x).input_schema），非历史采样；工具清单以 tool_registry 为准，共 63 个。

| 工具 | 当前 schema 参数键 | 取（保留，进 content） | 丢（过滤） |
|---|---|---|---|
| —— FILE —— | | | |
| copy | dest, overwrite, path, preserve_metadata, recursive | dest, path, recursive | overwrite, preserve_metadata |
| delete | force, path, recursive | force, path, recursive | （无） |
| edit | encoding, ignore_case, mode, new_string, old_string, path | mode, path, lines_added, lines_removed | encoding, ignore_case, new_string, old_string |
| find | ignore_case, offset, path, pattern, type | path, pattern, type | ignore_case, offset |
| grep | context, glob, ignore_case, path, pattern | glob, path, pattern | context, ignore_case |
| listdir | include_hidden, offset, path, sort_by | include_hidden, offset, path | sort_by |
| move | dest, overwrite, path | dest, path | overwrite |
| read | encoding, limit, offset, path, tail | limit, offset, path, tail | encoding |
| rename | dest, overwrite, path | dest, path | overwrite |
| tree | include_hidden, max_depth, path, sort_by | include_hidden, max_depth, path, sort_by | （无） |
| write | append, content, encoding, path | append, encoding, path | content |
| —— DOCUMENT —— | | | |
| compress | dest, exclude_patterns, format, overwrite, password, path, timeout | dest, password, timeout, format, path | exclude_patterns, overwrite |
| extract | dest, overwrite, password, path | dest, password, path | overwrite |
| read_docx | limit, offset, path, tail | limit, path | offset, tail |
| read_pdf | page, pages, path | page, pages, path | （无） |
| read_pptx | path, slide | path, slide | （无） |
| read_xlsx | path, sheet_name | path, sheet_name | （无） |
| readmedia | path | path | （无） |
| write_docx | content, path, table_data, title | path, title | content, table_data |
| write_pdf | content, path, table_data, title | path, title | content, table_data |
| write_pptx | path, slides | path | slides |
| write_xlsx | append_mode, data, path, sheet_name | path, sheet_name | append_mode, data |
| —— FUNDAMENTAL —— | | | |
| bash | command, cwd, shell_type, success_codes, timeout | command, timeout, cwd | shell_type, success_codes |
| fetchpage | extract_format, js_render, prompt, proxy, timeout, url | prompt, timeout, url | extract_format, js_render, proxy |
| notify | duration, message, title | duration, message, title | （无） |
| searchtool | query | query | （无） |
| searchweb | allowed_domains, blocked_domains, num_results, proxy, query | allowed_domains, blocked_domains, num_results, query | proxy |
| timenow | （无参工具） | （无） | （无） |
| —— NETWORK —— | | | |
| download | dest, headers, proxy, timeout, url | dest, timeout, url | headers, proxy |
| httpget | body, headers, method, proxy, timeout, url | method, timeout, url | body, headers, proxy |
| ping_port | count, host, mode, port, timeout | count, timeout, host, mode, port | （无） |
| —— DATAANALYSIS —— | | | |
| analyze_data | data, group_by, operations, path, sort_by, top_n | group_by, operations, path, sort_by, top_n | data |
| execute_sql | confirm_ddl, connection_string, connection_type, dry_run, path, sql, timeout | confirm_ddl, connection_string, dry_run, timeout, connection_type, path, sql | （无） |
| filter_data | conditions, data, path, select_columns, sort_by, top_n | path, select_columns, sort_by | conditions, data, top_n |
| generate_chart | chart_type, data, dest, title, x_label, y_label | chart_type, data, dest, title, x_label, y_label | （无） |
| get_db_schema | connection_string, connection_type, path, table_name | connection_string, connection_type, path, table_name | （无） |
| query_sql | connection_string, connection_type, limit, path, sql, timeout | connection_string, connection_type, timeout, limit, path, sql | （无） |
| —— DESKTOP —— | | | |
| clipboard_control | action, content | action | content |
| keyboard_control | action, text_or_keys | action, text_or_keys | （无） |
| mouse_click | button, clicks, x, y | button, clicks, x, y | （无） |
| mouse_move | x, y | x, y | （无） |
| mouse_position | （无参工具） | （无） | （无） |
| mouse_scroll | amount, direction | amount, direction | （无） |
| screen_capture | dest, display, region | dest, region | display |
| set_window_state | action, window_title | action, window_title | （无） |
| window_focus | window_title | window_title | （无） |
| window_info | filter_title, include_minimized | filter_title | include_minimized |
| window_resize | height, width, window_title | height, width, window_title | （无） |
| —— SYSTEM —— | | | |
| create_task | command, interval, schedule, task_name | schedule, task_name | command, interval |
| delete_task | task_name | task_name | （无） |
| event_log | level, log_name, max_events, source, time_range | level, log_name, max_events | source, time_range |
| list_tasks | state, task_name | state, task_name | （无） |
| sysinfo | info_type | info_type | （无） |
| which | all_paths, command | command | all_paths |
| —— TIMER —— | | | |
| calendar | name, year | name, year | （无） |
| timeadd | delta, start, unit | delta, start, unit | （无） |
| timediff | end, start | end, start | （无） |
| timer_clear | timer_id | timer_id | （无） |
| timer_list | （无参工具） | （无） | （无） |
| timer_set | callback, delay | callback, delay | （无） |
| —— WIN_REGISTRY —— | | | |
| registry_delete | hive, path, recursive, value_name | path | hive, recursive, value_name |
| registry_read | hive, output_format, path, value_name | path, value_name | hive, output_format |
| registry_write | hive, path, value, value_name, value_type | path, value_name | hive, value, value_type |

取列（保留列）依北京老陈逐行裁定；其余参数由小欧按统一口径补定：保留用户/Agent 主动做的选择与目标定位参数，丢弃正文长文本、框架默认开关、安全凭据与网络代理。落地时不得改动。

全部参数均已裁定，无待定项。
### 3.6 字段投影规则

| 目标字段 | 来源 | 规则 |
|---|---|---|
| `tool` | `action.tool` | 原样，缺失回退 `tool_name` |
| `tool_zh` | `action.tool_zh` | 缺失时回落 `tool` |
| `exec_code` | `status.exec_code` | 原样三态 |
| `message` | `status.message` | 原样 |
| `params` | `action.params` | 经 3.5 三层规整 |
| `duration_ms` | `llm_data.duration_ms` | 原样，非数值则 0 |
| `detail` | `status.detail` | 原样（成功时空串） |

> ⚠️ 全字段兜底是硬性要求 🔴：`llm_data` 由各工具自行产出，结构不保证完整（可能缺 `status` 或 `action`）。故投影链上每一层必须 `.get()` 逐级兜底并给默认值，任一环节缺失只允许该字段变成默认值，严禁因结构不完整抛异常拖垮整条 observation。

### 3.7 后端改动（4 处）

#### 3.7.1 投影函数规整伪代码

以下为设计伪代码，落地时按此逐条翻译（不写成代码前不动实现）：

```text
输入: params = llm_data.action.params（dict，可能为 None 或非 dict）
      tool  = llm_data.action.tool（缺失回退 tool_result[i].tool_name）
输出: 规整后的 params（dict）

常量（以 3.5.6 明细表的当前 schema 为唯一真源，逐键对应，不得臆造）:

  DROP_KEYS  = {shell_type, encoding, ignore_case, overwrite, preserve_metadata,
                extract_format, js_render, proxy, success_codes, append_mode,
                content, slides, table_data, data, body, headers,
                old_string, new_string}
      判据: 3.5.6 表丢列的全部参数（框架默认开关 + 正文长文本）
  BODY_KEYS  = {command, sql, query, prompt}
      判据: 命令正文类多行长文本, 取首行
  KEEP_MAX   = 50      # 取值长度上限, 超限整项丢弃, 不截断(D7)
  TOTAL_MAX  = 2048    # content 序列化后总长上限（D5）
  edit 特例: old_string / new_string 不进 content, 改用 difflib 按行差异
             产出 lines_added / lines_removed（3.5.3）

函数 规整参数(params, tool):
    若 params 非 dict: 返回 {}
    out = {}

    对 params 的每个 (k, v):
        若 k 在 DROP_KEYS:             跳过        # 3.5.2 框架默认开关+正文
        若 v 是 list 或 dict:          跳过        # 只保留标量（3.5.1）
        k2 = k   # 不改名(D6), 保留真实键名

        若 k2 在 BODY_KEYS:                        # 命令正文类
            s = 转字符串(v).取首行(遇换行即止)
            若 长度(s) > KEEP_MAX: 跳过             # 整项丢弃，不截断（D7）
            否则: out[k2] = s
            继续

        # 其余保留类统一按长度判定
        若 长度(转字符串(v)) > KEEP_MAX: 跳过       # 超限整项丢弃（D7）
        否则: out[k2] = v

    若 tool == "edit":                               # 3.5.3 特例
        删除 out["old_string"] 与 out["new_string"]  # 原文不进 content
        若 原始 params 里有 old_string 与 new_string:
            用 difflib 按行对比二者:
                out["lines_added"]   = 新增行数
                out["lines_removed"] = 删除行数
        否则:
            写 debug 日志（tool=edit，缺 old/new 原文）

若 out 为空:
写 debug 日志（tool 名 + 原始键列表）        # 3.5.5 静默丢弃补救
返回 out

函数 兜底总量(items):                                # content 序列化后调用
    s = 序列化(items)
    当 长度(s) > TOTAL_MAX 且 仍有元素带 params:
        剔掉最后一个元素的 params 值
        s = 重新序列化(items)
    返回 s
```

伪代码对应的规则落点：

| 伪代码片段 | 对应规则 |
|---|---|
| `DROP_KEYS` 跳过 | 3.5.2 通用规则（丢列全部参数） |
| 不改名，保留真实键名 | D6 路径键名分叉 |
| `BODY_KEYS` 取首行 / 超限丢弃 | D7 长度分级 |
| 其余保留类按长度判定 | D7 长度分级 |
| 非标量跳过 | 3.5.1 参数三分类 |
| edit 转 lines_added / lines_removed | 3.5.3 特殊规则 |
| out 为空时 debug 日志 | 3.5.5 未登记兜底 |
| `兜底总量` | D5 体积上限 |

#### 3.7.2 后端改动清单

| # | 文件 | 改动 |
|---|---|---|
| B1 | `backend/app/tools/toolhelper/observation_summary.py`（新增） | 纯函数 `build_observation_content(tool_result: list) -> str`：按 3.4/3.5/3.6 投影并序列化为 JSON 数组字符串。内含：噪声名单常量、参数三分类、长度分级、edit 行数增减（difflib）、write/clipboard 正文丢弃、路径键名原样保留（D6）、2KB 兜底（D5）、debug 兜底日志（3.5.5）、逐元素 try/except 降级为占位项。空数组返回 "[]" |
| B2 | `backend/app/services/agent/steps/observation_step.py:12-37` | `__init__` 增可选参数 `content: str = ""`；`get_content()` 返回该值；`_extra_fields()` 原逻辑不变 |
| B3 | `backend/app/services/agent/observation_builder.py:153` | 构造 `ObservationStep` 时传入 `content=build_observation_content(tool_result)` |
| B4 | `backend/app/services/agent/react_step.py:572-575` | LLM 输出截断补偿路径同样补传，保证两条 emit 路径 content 一致，避免同类型 step 有空有非空 |

### 3.8 前端改动（2 处）

| # | 文件 | 改动 |
|---|---|---|
| F1 | `frontend/src/features/chat/services/sseParser.ts:901-912` | observation 分支在 `step.tool_result = tr` 之后，对 `rawData.content` 做 `JSON.parse`（`try/catch` 兜底，失败留空不抛错），结果存入 `step.contentItems`（对象数组）。解析只在此入口做一次，组件直接消费数组，不重复 parse。类型 `ExecutionStep` 增 `contentItems` |
| F2 | `frontend/src/features/chat/components/pipeline/ToolCallLine.tsx` | 新增 content 驱动的「工具执行明细」渲染块：对 `step.contentItems` 逐元素渲染一行一个工具 |

F2 渲染契约：

| 项 | 规则 |
|---|---|
| 行数 | 一个 tool 一行，行数 == `contentItems.length`（单工具 1 行、多工具 N 行，同构无分支） |
| 行内字段 | 各自独立摆位：`tool_zh`/`tool`（名称）+ `exec_code`（三态徽标）+ `duration_ms`（>0 才显示）+ `params`（逐键 `键: 值`）；不是一句话拼接 |
| 失败行 | 追加 `detail`（失败详情），同在 content 内，无需回查 tool_result |
| 无 content 时 | `contentItems` 为空 → 该渲染块不渲染 |
| 与现有渲染的关系 | 新增块，不改动现有子行的渲染逻辑；两者数据源与职责独立，互不依赖 |

### 3.9 风险与防御

| # | 风险 | 防御 |
|---|---|---|
| 1 | 通用 content 渲染器把 JSON 原文显示出来 | 核查 `kind:'obs'` 分支是否经通用正文渲染器；若有则 F1 只存不渲染，由 F2 独占消费 |
| 2 | content 里的 JSON 误流入 LLM 上下文 🔴 | 真源约定 + 单测锁死"content 不进上下文" |
| 3 | 统一阈值导致 90% bash 参数全空 🔴 | 已用长度分级（D7 / 3.5.4）取代：命令正文取首行 |
| 5 | 漏登记的工具参数静默消失 🔴 | 分类未命中打 debug 日志（3.5.5） |
| 6 | `llm_data` 结构不完整导致投影抛异常 🔴 | 全 `.get()` 逐级兜底 + 单元素 try/except 降级（3.6 末） |
| 7 | 新增渲染块与现有子行信息重复，观感冗余 | 两者职责不同（动作结果 vs 逐工具执行概况）；落地后由北京老陈实看观感再定去留（3.13 L4） |
| 8 | content 体积膨胀 | 2KB 上限（D5），超限剔 `params` |

### 3.10 验收标准

| # | 验收项 | 判定 |
|---|---|---|
| A1 | 新跑一轮对话后，查库 observation 的 `content` 非空 | ✅ |
| A2 | `JSON.parse(content)` 成功且为数组 | ✅ |
| A3 | 数组长度 == `tool_result` 长度（单工具=1，多工具=N） | ✅ |
| A4 | 每个元素含 tool / exec_code / params / message 四要素 | ✅ |
| A5 | 失败工具的 `detail` 正确带出 | ✅ |
| A6 | `contentItems` 为空时该渲染块不渲染 | ✅ |
| A7 | LLM 回复质量无变化（content 不进上下文） | ✅ |
| A8 | 前端 `npm run check:full` 通过 | ✅ |
| A9 | 构造 `llm_data` 缺 `status`/`action` 的假工具 → content 仍产出且不抛异常 | ✅ |
| A10 | 未登记工具 → 参数为空但日志可见 | ✅ |
| A11 | bash 行能显示首行命令（验证长度分级生效，非空 params） | ✅ |
| A12 | edit 行输出 lines_added / lines_removed，且不含 old_string / new_string 原文 | ✅ |
| A13 | 超大 content（并行多工具）被 2KB 兜底削到限内 | ✅ |
| A14 | `copy` 的 `dest` 与 `path` 均以真实键名出现在 content 中，未被改名或合并 | ✅ |

### 3.11 改动文件清单

| 文件 | 类型 | 预估 |
|---|---|---|
| `backend/app/tools/toolhelper/observation_summary.py` | 新增 | ~130 |
| `backend/app/services/agent/steps/observation_step.py` | 改 | ~6 |
| `backend/app/services/agent/observation_builder.py` | 改 | ~4 |
| `backend/app/services/agent/react_step.py` | 改 | ~2 |
| `frontend/src/features/chat/services/sseParser.ts` | 改 | ~8（含类型加 `contentItems`） |
| `frontend/src/features/chat/components/pipeline/ToolCallLine.tsx` | 改 | ~40 |

### 3.12 实施顺序

```
1. B1（纯函数投影，可单测，不动线上）
2. B2 + B3 + B4  → 后端查库验收 A1~A5、A9~A14
3. F1（只存不渲染）→ 确认 JSON 完整到达前端
4. 核查 3.9 风险 1
5. F2（渲染块）      → A6 / A8
6. 真实对话全链路验收 + A7
```

### 3.13 待定项与遗留（落地时须先结清）

| # | 事项 | 说明 |
|---|---|---|
| L1 | 恒定噪声名单补全 | 须对照 `app/tools/` 全部工具 schema 复核补全（3.5.2） |
| L2 | 长度阈值最终值 | 正文类首行阈值与标识类阈值（现取 50）落地时按真实观感微调 |
| L3 | 通用 content 渲染器核查 | 确认 `kind:'obs'` 分支是否会把 JSON 原文显示出来（3.9 风险 1） |
| L4 | 新增渲染块与现有子行的观感取舍 | 落地后由北京老陈实看界面，再定是否保留/精简现有子行 |

---

编写人：小欧
编写时间：2026-10-12 14:32:10