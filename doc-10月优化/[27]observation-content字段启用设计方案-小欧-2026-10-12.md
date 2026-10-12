# [27] observation.content 字段启用设计方案

创建时间：2026-10-12 11:28:58
更新时间：2026-10-12 17:35:29
版本：v2.4
编写人：小欧

**版本历史**

| 版本 | 时间 | 编写人 | 修改说明 |
|---|---|---|---|
| v1.0 | 2026-10-12 11:28:58 | 小欧 | 新建（北京老陈令：启用 observation.content 字段，供前端 UI 渲染） |
| v2.0 | 2026-10-12 14:01:18 | 小欧 | 第三章整章重写：63 工具取参明细表；剔除 `metrics`；删除二态 `ok`，`exec_code` 改三态 |
| v2.1 | 2026-10-12 15:20:03 | 小欧 | content 改为一句一工具人话 + content_items 同源数组 |
| v2.2 | 2026-10-12 16:43:14 | 小欧 | 句子全中文映射（84 键）+ 布尔肯定否定词 |
| v2.3 | 2026-10-12 17:19:46 | 小欧 | 前端渲染规则剥离待议；后端代码落地（observation_content.py 新建 + observation_step.py 改 + FUNCTIONS.md 登记） |
| v2.4 | 2026-10-12 17:35:29 | 小欧 | 新增第四章 4.1：tool_zh 中文名准确性核查记录（63 工具逐个对照，A类5个必改/B类12个建议改/C类46个不动） |

---

## 一、需求与设计目标

### 1.1 需求内容与渲染显示需求

北京老陈 2026-10-12 指令：`observation` 类型的 step，其 `content` 字段当前从未被使用，现要求启用该字段。

约束（用户明确指定）：

| 编号 | 约束 | 说明 |
|---|---|---|
| R1 | 不改 summary 字段 | `llm_data.summary` 维持现状，不动它 |
| R2 | 一个工具一行 | 单工具 observation 产出 1 行；多工具 observation 产出 N 行，每行一个工具 |
| R3 | 两种载体两种形态 | `content` 是人类可读文本，一句一工具（格式见 3.4）；`content_items` 是结构化字段数组，一个工具一条，前端逐字段取用 |
| R4 | 参数按 3.5.6 明细表逐工具规整（63 个工具，每个一行），不做全量保留，不做统一截断 | 见 3.5 |
| R5 | 长参数按长度与性质判定（3.5.4）：命令正文类取首行；标识类超 50 字符整项丢弃；不截断、不加省略号 |
| R6 | 已知单工具与多工具两种形态 | 方案须同时覆盖 |
| R7 | 先落后端，前端后跟 | 2026-10-12 确认实施顺序 |

前端渲染需求（待专门讨论前端时由北京老陈定，本方案不预设；以下仅为占位示例）：

```
┌ 执行动作 ──────────────────────────────────┐
│ ▶ 1/2  bash        成功   2.8s             │
│      命令: Invoke-RestMethod -Uri https://… │
│ ▶ 2/2  timenow     成功   0.0s             │
│      （无参）                                │
└────────────────────────────────────────────┘
```

即：每个工具一行，行为"图标/名称/状态徽标/耗时"，参数区只留核心参数；失败行追加 `detail`（失败详情）。**以上为占位示例，最终以专门讨论前端时的裁定为准。**

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
| D1 | content 存储形态 | `content` 存人类可读文本，**一个工具一句话**，行数 == 工具数；`content` 字段类型仍为 `str` | 2026-10-12 |
| D2 | 参数处理方式 | 通用规则 + 特殊规则 + 长度分级三层规整（3.5），不做统一截断 | 2026-10-12 |
| D3 | 实施顺序 | 先落后端，前端渲染后跟；前端「有 content 渲染、无则不渲染」 | 2026-10-12 |
| D4 | `message` 是否保留 | 保留。取自 `status.message`，成功时虽短但零成本，失败时是有效信息 | 2026-10-12 |
| D5 | content 体积上限 | 2KB（CONTENT_MAX_CHARS）。超限时从后往前逐个置空 params（绝不删行）；状态/耗时/detail 永不受影响 | 2026-10-12 |
| D6 | 路径参数键名处理 | 不改名不改写：当前 schema 的路径键只有 `path` 与 `dest` 两种，各按原样保留；content 不得出现注册表中不存在的键名 | 2026-10-12 |
| D7 | 超长主体参数如何处理 | 按性质分级（3.5.4）：命令正文类取首行；标识类（path/dest/url/pattern）超 50 整个丢弃。不用统一截断，也不一律丢 | 2026-10-12 |
| D8 | 结构化结果的存放 | 新增字段 `content_items` 存对象数组（前端直接消费）；`content` 存同一批数据渲染出的**一行一句人话**；两者由同一份 `content_items` 生成，严禁分别构造 | 2026-10-12 |
| D9 | content 句子内参数规整 | ① 只取**第一个** path 类参数（`path`/`dest`），其余 path 类参数不进句子；② 该 path 含分隔符时只取**文件名**；③ 参数有值才合成，无值（空串/None）跳过；④ `command` 超 35 字符截断并加 `…`；⑤ 参数之间用 ` | ` 分隔；⑥ 参数按主次排序（主体>路径>其余字母序，见 3.4.1）；⑦ path 类参数**只显示值、不加键名前缀**（路径一眼可认）；⑧ 自由文本参数（command/sql/prompt/query/pattern/message/title/url/text_or_keys/callback）**裸值显示**，不加标签；⑨ 布尔参数显示中文肯定/否定词（见 3.4.2.6），句子里不出现 True/False | 2026-10-12 |

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
| 事实一 | LLM 几乎总是把 schema 默认值一并填满 | `bash` 1531/1531 次都带 `shell_type`+`timeout`；`edit` 342/342 次都带 `ignore_case`；`delete` 37/37 次都带 `recursive`+`force` |
| 事实二 | 每个工具只有 1~2 个真正的主体参数 | `command` / `query` / `pattern` / `url` / `content` / `old_string`+`new_string` |
| 事实三 | 路径参数只有两种真实键名 | 当前注册表只有 `path` 与 `dest`，按真实键名原样保留 |

### 3.4 content 结构定义（7 字段 + 同源数组字段）

存储形态（北京老陈 2026-10-12 定案）：

| 载体 | 类型 | 内容 | 用途 |
|---|---|---|---|
| `content` | `str` | 人类可读文本，**一个工具一句话**，行数 == 工具数 | 启用 content 字段本身，供人读、存档、回看 |
| `content_items` | 数组 | 同一批数据的对象数组 | 前端直接消费，结构化渲染 |

两者同源：`content_items` 是唯一真身，`content` 由它逐条渲染成一句话，**严禁分别构造**。

`content` 每句的格式（一个工具一句，行内顺序固定为「工具名 中文名 参数 结果短句 耗时」）：

```
tool tool_zh 片段 | 片段 message (耗时)
```

实例（两个工具 = 两句）：

```text
bash 执行 Invoke-RestMethod -Uri 'https://wttr.wtt… | test_report.pdf 执行成功 (2.8s)
timenow 获取时间 获取当前时间成功
read 读取文件 b.txt | 前50条 | 从第10条起 读取成功 (0.1s)
```

| 组成（行内顺序固定，不可调换） | 取值 | 缺省处理 |
|---|---|---|
| 工具名 | `tool`（机器英文名） | 必显 |
| 中文名 | `tool_zh`（缺失回落 `tool`） | 若与工具名相同则省略，避免重复 |
| 参数 | `params` 按 D9 规整：① 只取第一个 path 类参数（`path`/`dest`），其余 path 类不进句子；② 该 path 含 `/` 或 `\` 时只取文件名，**且只显示值、不加 `path=` 前缀**（路径一眼可认，见 D9⑦）；③ 有值才合成（空串/None 跳过）；④ `command` 超 35 字符截断并加 `…`；⑤ 参数之间用 ` | ` 分隔；⑥ 自由文本裸值、⑦ 中文模板见 3.4.2 | 空则整段省略 |
| 结果短句 | `message` | 为空则省略 |
| 耗时 | `duration_ms` > 0 才拼 `(2.8s)` | 为 0 则省略 |

组句规则：按上方顺序拼接非空段，段之间单个空格分隔；`exec_code` 与 `detail` 不进句子（状态语义由 `message` 承载，结构化信息在 `content_items` 里）。

#### 3.4.1 参数主次排序（主要在前、次要在后）

`params` 生成与渲染统一按此顺序，三个优先级：

| 优先级 | 成员 | 说明 |
|---|---|---|
| P0 主体 | `command` `sql` `query` `prompt` `pattern` `operations` `method` | 本次执行的核心动作，一律放最前 |
| P1 路径 | `path` `dest` | 执行目标，次之 |
| P2 其余 | 保留列其余参数 | 按键名字母序排列，输出稳定可预期 |

该排序在 `_pick_params` 构造时一次排好，`content_items` 与句子共用同一顺序。

#### 3.4.2 参数中文显示映射（句子内人话，不进 content_items）

只作用于 `content` 句子渲染；`content_items` 里仍存原始键值对，前端结构化渲染不受影响。
本表覆盖保留列全部 82 个参数 + 2 个 edit 派生量，无遗漏、无"兜底"。

##### 3.4.2.1 路径裸值（2 个）

| 参数 | 句子显示 | 例 |
|---|---|---|
| `path` | 裸值，含分隔符时只取文件名 | test_report.pdf |
| `dest` | 裸值，含分隔符时只取文件名 | backup.zip |

##### 3.4.2.2 中文模板（10 个）

| 参数 | 句子显示 | 例 |
|---|---|---|
| `timeout` | 超时{v}秒 | 超时300秒 |
| `limit` | 前{v}条 | 前50条 |
| `offset` | 从第{v}条起 | 从第10条起 |
| `tail` | 末{v}行 | 末20行 |
| `sort_by` | 按{v}排序 | 按name排序 |
| `top_n` | 前{v}条 | 前100条 |
| `num_results` | 取{v}条 | 取10条 |
| `max_depth` | 最深{v}层 | 最深3层 |
| `page` | 第{v}页 | 第2页 |
| `slide` | 第{v}页 | 第5页 |

##### 3.4.2.3 自由文本裸值（10 个，值自解释，不加标签）

| 参数 | 句子显示 | 例 |
|---|---|---|
| `command` | 裸值（先取首行，超 35 截断并加 `…`） | python a.py |
| `sql` | 裸值（先取首行） | SELECT * FROM users |
| `prompt` | 裸值（先取首行） | 提取标题 |
| `query` | 裸值（先取首行） | 报错日志 |
| `pattern` | 裸值 | def read |
| `message` | 裸值 | 构建完成 |
| `title` | 裸值 | 日报 |
| `url` | 裸值 | https://wttr.in |
| `text_or_keys` | 裸值 | hello |
| `callback` | 裸值 | 提醒开会 |

##### 3.4.2.4 edit 派生量（2 个）

| 参数 | 句子显示 | 例 |
|---|---|---|
| `lines_added` | 新增{v}行 | 新增3行 |
| `lines_removed` | 删除{v}行 | 删除1行 |

##### 3.4.2.5 中文显示（60 个，句子里不出现英文键名）

| 参数 | 句子显示 | 例 |
|---|---|---|
| `action` | 操作{v} | 操作copy |
| `allowed_domains` | 允许域名{v} | 允许域名example.com |
| `amount` | 数量{v} | 数量3 |
| `append` | True→追加 / False→覆盖 | 追加 |
| `blocked_domains` | 屏蔽域名{v} | 屏蔽域名spam.com |
| `button` | 按键{v} | 按键left |
| `chart_type` | 图表{v} | 图表bar |
| `clicks` | 点击{v}次 | 点击2次 |
| `confirm_ddl` | True→已确认 / False→未确认 | 已确认 |
| `connection_string` | 连接串{v} | 连接串Server=db |
| `connection_type` | 连接类型{v} | 连接类型sqlite |
| `count` | 次数{v} | 次数4 |
| `cwd` | 目录{v} | 目录E:\work |
| `delay` | 延迟{v}秒 | 延迟60秒 |
| `delta` | 增量{v} | 增量7 |
| `direction` | 方向{v} | 方向down |
| `dry_run` | True→试运行 / False→正式执行 | 试运行 |
| `duration` | 持续{v}秒 | 持续10秒 |
| `encoding` | 编码{v} | 编码utf-8 |
| `end` | 结束{v} | 结束2026-10-12 |
| `filter_title` | 过滤标题{v} | 过滤标题记事本 |
| `force` | True→强制 / False→不强制 | 强制 |
| `format` | 格式{v} | 格式zip |
| `glob` | 通配{v} | 通配*.py |
| `group_by` | 按{v}分组 | 按city分组 |
| `height` | 高度{v} | 高度800 |
| `host` | 主机{v} | 主机127.0.0.1 |
| `include_hidden` | True→含隐藏 / False→不含隐藏 | 含隐藏 |
| `info_type` | 信息{v} | 信息cpu |
| `interval` | 间隔{v}秒 | 间隔3600秒 |
| `level` | 级别{v} | 级别error |
| `log_name` | 日志{v} | 日志Application |
| `max_events` | 最多{v}条 | 最多100条 |
| `method` | 方法{v} | 方法GET |
| `mode` | 模式{v} | 模式once |
| `name` | 名称{v} | 名称春节 |
| `operations` | 操作{v}（标量时） | 操作mean |
| `pages` | 页数{v} | 页数5 |
| `password` | 密码{v} | 密码****** |
| `port` | 端口{v} | 端口8000 |
| `recursive` | True→递归 / False→不递归 | 递归 |
| `region` | 区域{v} | 区域全屏 |
| `schedule` | 计划{v} | 计划每天8点 |
| `select_columns` | 取列{v} | 取列name |
| `sheet_name` | 表{v} | 表Sheet1 |
| `start` | 开始{v} | 开始2026-10-01 |
| `state` | 状态{v} | 状态active |
| `table_name` | 表名{v} | 表名users |
| `task_name` | 任务{v} | 任务备份 |
| `timer_id` | 定时器{v} | 定时器t1 |
| `type` | 类型{v} | 类型file |
| `unit` | 单位{v} | 单位day |
| `value_name` | 值名{v} | 值名Version |
| `width` | 宽度{v} | 宽度1024 |
| `window_title` | 窗口{v} | 窗口计算器 |
| `x` | 横坐标{v} | 横坐标100 |
| `x_label` | 横轴{v} | 横轴月份 |
| `y` | 纵坐标{v} | 纵坐标200 |
| `y_label` | 纵轴{v} | 纵轴销量 |
| `year` | 年份{v} | 年份2026 |

##### 3.4.2.6 布尔肯定/否定词（6 个，句子里不出现 True/False）

| 参数 | True 显示 | False 显示 |
|---|---|---|
| `append` | 追加 | 覆盖 |
| `confirm_ddl` | 已确认 | 未确认 |
| `dry_run` | 试运行 | 正式执行 |
| `force` | 强制 | 不强制 |
| `include_hidden` | 含隐藏 | 不含隐藏 |
| `recursive` | 递归 | 不递归 |

对应的 `content_items`（同一批数据的结构化形态）：

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

存储形态的代价与收益：新增 `content_items` 后，落库为原生数组（**人肉可读**）、前端零解析；代价是 step 序列化多一个字段（`_extra_fields` 多返回一键），对其他 step 类型无影响（可选增量）。

### 3.5 参数规整规则（D2 核心）

#### 3.5.1 参数三分类（以 3.5.6 明细表为唯一真源）

丢弃类（与 3.5.6 表丢列一一对应，共 30 个）：

| 类别 | 成员 | 理由 |
|---|---|---|
| 框架默认开关与基础设施 | `shell_type` `success_codes` `ignore_case` `overwrite` `preserve_metadata` `extract_format` `js_render` `append_mode` `proxy` `headers` `conditions` | 恒定默认值或基础设施细节，用户无从选择 |
| 长内容载荷 | `content` `data` `slides` `table_data` `body` | 必然超长的数据本体（约定见 3.5.2） |
| 长内容载荷（edit 专用） | `old_string` `new_string` | 原文必然超长，改按 3.5.3 转 lines_added / lines_removed |
| 结果呈现开关 | `context` `display` `include_minimized` `all_paths` `source` | 只影响工具内部呈现方式，对本次执行无实质影响 |
| 平台细节 | `hive` `output_format` `value_type` `value` | 由运行环境/协议决定，用户无选择空间 |
| 时间范围与排除规则 | `time_range` `exclude_patterns` | 长且不影响本次执行意图的表达 |

保留类：

| 类别 | 成员 | 处置 |
|---|---|---|
| 路径参数 | `path` `dest` | 进 content，按真实键名原样保留（D6） |
| 主体参数 | `command` `sql` `operations` `url` | 进 content；命令正文类取首行（3.5.4） |
| 短内容参数 | `message` `callback` `text_or_keys` `text` `query` `pattern` `title` `select_columns` `value_name` `sheet_name` `table_name` | 进 content，再走 50 字长度判定 |
| 用户主动选择 | `timeout` `limit` `offset` `tail` `mode` `sort_by` `include_hidden` `recursive` `force` `num_results` `page` `pages` `slide` `max_depth` `dry_run` `password` `connection_string` `allowed_domains` `blocked_domains` `top_n` | 进 content |

同一参数名在所有工具中取舍一致（同名同待遇，理由：前端按参数名渲染，不分子工具，新工具零配置即可正确显示；改表即改本节，二者不得脱节）。

#### 3.5.2 通用规则（以 3.5.6 表为准，无需逐工具登记）

> 保留「主体参数 + 路径参数 + 用户主动选择 + 短内容参数」，丢弃「框架默认开关 + 长内容载荷」；路径参数按真实键名原样保留，不改名不合并。

长内容判定统一约定（北京老陈 2026-10-12）：

| 判定 | 标准 | 处置 |
|---|---|---|
| **必然长** | 参数语义就是"要写入/处理的数据本体"，schema 即声明为数组、正文、数据（如 write 的 content、各工具的 data、write_pptx 的 slides、write_docx/write_pdf 的 table_data、httpget 的 body） | **一律丢**，不看长度 |
| **必然短** | 参数语义是标识、条件、开关或简短提示（如 notify 的 message、timer_set 的 callback、keyboard_control 的 text_or_keys、searchweb 的 query、grep 的 pattern、各种 title） | **保留**，再走 50 字长度判定 |
| 边界不清 | 介于两者之间 | 按 50 字判定：未超限则保留，超限自动丢，无需逐个定性 |

> 该约定取代"逐参数定性"：只区分"必然长"与"必然短"，边界情形交给长度判定兜底，避免反复争论。

| 收益 | 说明 |
|---|---|
| 新工具免登记 | 63 个注册工具全部符合该规律，新工具不登记也基本正确 |
| 消除默认值噪声 | 对应实测事实一（LLM 总把默认值填满） |

丢弃名单（3.5.6 表丢列的全部 30 个，代码常量 DROP_KEYS 与此逐字一致）：
```
shell_type, success_codes, ignore_case, overwrite, preserve_metadata,
extract_format, js_render, append_mode, proxy, headers, conditions,
content, data, slides, table_data, body, old_string, new_string,
context, display, include_minimized, all_paths, source,
hive, output_format, value_type, value, time_range, exclude_patterns
```

> 该名单与 3.5.6 表的丢列一一对应，改表即改本节，二者不得脱节。

#### 3.5.3 特殊规则（仅 4 类工具）

| 工具/参数 | 特例规则 | 理由 |
|---|---|---|
| edit | old_string / new_string 转行数：两者原文不进 content，行数增减直接取 edit 工具已算好的 metrics（added/removed，必要时回退 data.diff 统计）；path 与 mode 照常保留 | 两者原文实测 93% 超长，按长度规则会被整项丢弃等于白丢；行数增减恒定不超长，且保住"改了多少"这一核心信息；行数口径与 edit 工具 summary/metrics 同源，不另算 |
| write | content 不进 content；append、encoding、path 照常保留 | content 是超长正文，最长实测 37177 字符 |
| 路径参数 | 不做任何改名，`path` 与 `dest` 各按真实键名原样保留 | 北京老陈 2026-10-12 裁定：content 只用系统真实存在的键名，不发明新词 |
| 无参工具（timenow、timer_list、mouse_position 等） | params 输出 {} | 当前 schema 确实无参数 |

#### 3.5.4 长度分级规则（D7）

实测数据证明"统一阈值"不可行：若参数值超 50 字符一律丢弃，绝大多数工具参数全空：

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
| 新增工具（不在 3.5.6 表内） | 按 3.5.2 通用规则归类；若归类后保留列为空 → `params` 输出 `{}`，不报错、不打日志 |
| 静默丢弃的补救 | 保留列为空属正常现象（工具本就无参，或参数全被丢弃），无需额外日志 |

#### 3.5.6 tool的取params的明细表

参数键取自当前注册表 schema（tool_registry.get_tool(x).input_schema），非历史采样；工具清单以 tool_registry 为准，共 63 个。

| 工具 | 当前 schema 参数键 | 取（保留，进 content） | 丢（过滤） |
|---|---|---|---|
| —— FILE —— | | | |
| copy | dest, overwrite, path, preserve_metadata, recursive | dest, path, recursive | overwrite, preserve_metadata |
| delete | force, path, recursive | force, path, recursive | （无） |
| edit | encoding, ignore_case, mode, new_string, old_string, path | encoding, mode, path, lines_added, lines_removed | ignore_case, new_string, old_string |
| find | ignore_case, offset, path, pattern, type | offset, path, pattern, type | ignore_case |
| grep | context, glob, ignore_case, path, pattern | glob, path, pattern | context, ignore_case |
| listdir | include_hidden, offset, path, sort_by | include_hidden, offset, path, sort_by | （无） |
| move | dest, overwrite, path | dest, path | overwrite |
| read | encoding, limit, offset, path, tail | encoding, limit, offset, path, tail | （无） |
| rename | dest, overwrite, path | dest, path | overwrite |
| tree | include_hidden, max_depth, path, sort_by | include_hidden, max_depth, path, sort_by | （无） |
| write | append, content, encoding, path | append, encoding, path | content |
| —— DOCUMENT —— | | | |
| compress | dest, exclude_patterns, format, overwrite, password, path, timeout | dest, password, timeout, format, path | exclude_patterns, overwrite |
| extract | dest, overwrite, password, path | dest, password, path | overwrite |
| read_docx | limit, offset, path, tail | limit, offset, path, tail | （无） |
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
| filter_data | conditions, data, path, select_columns, sort_by, top_n | path, select_columns, sort_by, top_n | conditions, data |
| generate_chart | chart_type, data, dest, title, x_label, y_label | chart_type, dest, title, x_label, y_label | data |
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
| create_task | command, interval, schedule, task_name | command, interval, schedule, task_name | （无） |
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
| registry_delete | hive, path, recursive, value_name | path, recursive, value_name | hive |
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

投影产物两个载体（同源，content 由 items 生成）：

| 载体 | 来源 | 说明 |
|---|---|---|
| `content_items` | 上述 7 字段组成的对象数组 | 唯一真身，落库为原生数组 |
| `content` | 同一份 `content_items` 逐条 `render_line` 拼接（`"\n".join`） | 人类可读文本，一个工具一句，供人读、存档、回看 |

> ⚠️ 全字段兜底是硬性要求 🔴：`llm_data` 由各工具自行产出，结构不保证完整（可能缺 `status` 或 `action`）。故投影链上每一层必须 `.get()` 逐级兜底并给默认值，任一环节缺失只允许该字段变成默认值，严禁因结构不完整抛异常拖垮整条 observation。

### 3.7 后端改动（3 个文件）

#### 3.7.1 投影函数规整伪代码

以下为设计伪代码，落地时按此逐条翻译（不写成代码前不动实现）：

```text
输入: params = llm_data.action.params（dict，可能为 None 或非 dict）
      tool  = llm_data.action.tool（缺失回退 tool_result[i].tool_name）
输出: 规整后的 params（dict）

常量（以 3.5.6 明细表的当前 schema 为唯一真源，逐键对应，不得臆造）:

  DROP_KEYS  = {shell_type, success_codes, ignore_case, overwrite, preserve_metadata,
                extract_format, js_render, append_mode, proxy, headers, conditions,
                content, data, slides, table_data, body, old_string, new_string,
                context, display, include_minimized, all_paths, source,
                hive, output_format, value_type, value, time_range, exclude_patterns}
      判据: 3.5.6 表丢列的全部 30 个参数（框架默认开关 + 长内容载荷 + 呈现开关 + 平台细节）
  BODY_KEYS  = {command, sql, query, prompt}
      判据: 命令正文类多行长文本, 取首行
  KEEP_MAX   = 50      # 取值长度上限, 超限整项丢弃, 不截断(D7)
  CONTENT_MAX_CHARS = 2048  # content 序列化后的字符数上限（D5）
  edit 特例: 旧 params 不再另行计算行数, 直接取 llm_data.metrics.added/removed
             （值为 {"value": N} 形态）, 缺 diff 文本时才用 _diff_line_counts 兜底（3.5.3）

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
        从 llm_data.metrics 取 added/removed（{"value": N} 形态）→ lines_added/lines_removed
        若缺失且 metrics.diff 文本存在 → 用 _diff_line_counts 兜底
        否则缺省为 0, 不报错不打日志
    返回 out（保留列为空属正常, 见 3.5.5, 不打日志）

函数 兜底总量(items):                                # content 序列化后调用
    s = 序列化(items)
    当 长度(s) > CONTENT_MAX_CHARS 且 仍有元素带 params:
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
| edit 转 lines_added / lines_removed | 3.5.3 特殊规则（取 metrics.added/removed，缺时用 _diff_line_counts 兜底） |
| 保留列为空 | 3.5.5（属正常，不打日志） |
| `兜底总量` | D5 体积上限 |

#### 3.7.2 后端改动清单

关键设计决策：content 由 `ObservationStep` 内部自算，调用方零改动。因此**不需要**改 `observation_builder.py` 与 `react_step.py`——两条 emit 路径天然一致，不存在"有的 observation 有 content、有的没有"的漏点。

| # | 文件 | 改动要点 |
|---|---|---|
| B1 | `backend/app/services/agent/steps/observation_content.py`（新增） | 单一公开函数 `build_content_items(tool_result: list) -> list`，纯函数（同输入同输出、无副作用、不抛异常）。要点：① 按 3.5.6 表逐键取：DROP_KEYS 跳过、BODY_KEYS 取首行、其余按 50 字判定（不做 JSON 字符串纠错，避免跨模块调用私有函数）；② edit 特例**直接取工具已算好的 `llm_data.metrics.added/removed`**，缺 `diff` 时才用与 `edit_text_file.py:320-321` 同一口径的行数统计兜底，不另起 difflib 实现；③ 三层 `.get()` 兜底（llm_data → action → status 任一缺失只给默认值）；④ 逐元素 try/except，单元素失败降级为占位项；⑤ 空数组返回 []；⑥ 2KB 兜底在数组上判定，序列化后超限则从后往前逐个置空 params 并重新判定；⑦ 保留列为空且工具不在注册表时打 debug 日志（含 tool 名） |
| B2 | `backend/app/services/agent/steps/observation_step.py:17-37` | `__init__` 内自算 `self._content_items = build_content_items(self._tool_result)`；`get_content()` 返回 `"\n".join(render_line(item) for item in self._content_items)`（一个工具一句话）；新增 `content_items` 只读属性；`_extra_fields()` 在原 tool_result 之外多返回一个 `content_items` 键（tool_result 为空时也须返回 content_items，值为 []）。`base.py` 无需改动（其 `to_dict():85` 已输出 `content: get_content()`） |
| B3 | `backend/FUNCTIONS.md` | 登记新建的 `build_content_items`（所属层、参数、返回值），AGENTS.md 1.3 要求新建公用函数必须入库 |

已作废的原方案（不实施）：

| 原编号 | 原计划 | 作废原因 |
|---|---|---|
| B3 | `observation_builder.py:153` 传 content | 调用方自算违背 DRY，且两条 emit 路径易漏 |
| B4 | `react_step.py:572` 传 content | 同上；且该处 `truncated_output` 是手写元素、非注册工具，由 B1 的未知工具兜底处理（不打 debug 日志） |

#### 3.7.3 实施代码与 diff

##### 3.7.3.1 新增 `backend/app/services/agent/steps/observation_content.py`

```python
# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-10-12 小欧 - 新建（observation.content 启用方案 B1）。由 tool_result[] 投影出
#   content_items 对象数组; content 字符串由 ObservationStep 对该数组 dumps 生成, 本文件不产字符串 — 小欧 2026-10-12
import json
from typing import Any, Dict, List

from app.logger import logger

# 参数丢弃名单: 与本文 3.5.6 表的丢列逐键一致, 改表即改本常量 — 小欧 2026-10-12
DROP_KEYS = frozenset({
    # 框架默认开关与基础设施
    "shell_type", "success_codes", "ignore_case", "overwrite",
    "preserve_metadata", "extract_format", "js_render", "append_mode",
    "proxy", "headers", "conditions",
    # 长内容载荷（含 edit 的 old/new，转 lines 前先丢原文）
    "content", "data", "slides", "table_data", "body", "old_string", "new_string",
    # 结果呈现开关
    "context", "display", "include_minimized", "all_paths", "source",
    # 平台细节 / 时间范围 / 排除规则
    "hive", "output_format", "value_type", "value", "time_range", "exclude_patterns",
})

# 命令正文类: 取首行（3.5.4 长度分级）— 小欧 2026-10-12
BODY_KEYS = frozenset({"command", "sql", "query", "prompt"})

PARAM_VALUE_MAX_CHARS = 50   # 单个参数值的字符数上限, 超限整项丢弃, 不截断（D7）
CONTENT_MAX_CHARS = 2048   # content 序列化后的字符数上限（D5）


def _first_line(value: Any) -> str:
    """取字符串首行 — 小欧 2026-10-12"""
    lines = str(value).splitlines()
    return lines[0] if lines else ""


def _diff_line_counts(diff_text: str) -> Dict[str, int]:
    """从 unified_diff 文本统计新增/删除行数 — 小欧 2026-10-12

    算法与 edit_text_file.py:320-321 完全一致(`+` 去 `+++` 头 / `-` 去 `---` 头, 零新依赖),
    不另起 difflib 实现, 避免同一口径两处计算; 返回两个计数故用复数 counts — 小欧 2026-10-12
    """
    lines = (diff_text or "").splitlines()
    added = sum(1 for ln in lines if ln.startswith("+") and not ln.startswith("+++"))
    removed = sum(1 for ln in lines if ln.startswith("-") and not ln.startswith("---"))
    return {"lines_added": added, "lines_removed": removed}


# 参数主次排序: 主体 > 路径 > 其余字母序（3.4.1）— 小欧 2026-10-12
PARAM_ORDER = ["command", "sql", "query", "prompt", "pattern", "operations",
               "method", "path", "dest"]


def _order_params(out: Dict[str, Any]) -> Dict[str, Any]:
    """按主次排序 params: P0 主体 > P1 路径 > P2 其余字母序 — 小欧 2026-10-12"""
    first = [k for k in PARAM_ORDER if k in out]
    rest = sorted(k for k in out if k not in PARAM_ORDER)
    return {k: out[k] for k in first + rest}


def _pick_params(action: Dict[str, Any]) -> Dict[str, Any]:
    """按 3.5.6 表逐键取 params: 丢列跳过 / 正文类取首行 / 其余按长度判定 — 小欧 2026-10-12"""
    params = action.get("params")
    if not isinstance(params, dict):
        return {}
    out: Dict[str, Any] = {}
    for key, val in params.items():
        if key in DROP_KEYS:
            continue
        if isinstance(val, (list, dict)):
            continue
        if key in BODY_KEYS:
            text = _first_line(val)
            if len(text) > PARAM_VALUE_MAX_CHARS:
                continue
            out[key] = text
            continue
        if len(str(val)) > PARAM_VALUE_MAX_CHARS:
            continue
        out[key] = val
    return _order_params(out)


def _build_item(element: Dict[str, Any]) -> Dict[str, Any]:
    """单个 tool_result 元素 → 一条 content 记录（7 字段；全 .get 兜底, 绝不抛异常）— 小欧 2026-10-12"""
    llm = element.get("llm_data")
    llm = llm if isinstance(llm, dict) else {}
    action = llm.get("action")
    action = action if isinstance(action, dict) else {}
    status = llm.get("status")
    status = status if isinstance(status, dict) else {}

    tool = action.get("tool") or element.get("tool_name") or ""
    duration = llm.get("duration_ms")
    duration = duration if isinstance(duration, (int, float)) else 0

    item: Dict[str, Any] = {
        "tool": str(tool),
        "tool_zh": str(action.get("tool_zh") or tool),
        "exec_code": str(status.get("exec_code") or "unknown"),
        "message": str(status.get("message") or ""),
        "params": _pick_params(action),
        "duration_ms": duration,
        "detail": str(status.get("detail") or ""),
    }

    if tool == "edit":  # edit 特例: 原文不进 content, 改出行数增减（3.5.3）
        metrics = llm.get("metrics")
        metrics = metrics if isinstance(metrics, dict) else {}
        added = metrics.get("added")
        removed = metrics.get("removed")
        if isinstance(added, dict) and isinstance(removed, dict):
            item["params"].update({
                "lines_added": added.get("value"),
                "lines_removed": removed.get("value"),
            })
        elif metrics.get("diff"):
            item["params"].update(_diff_line_counts(metrics.get("diff")))
        else:
            logger.debug("[observation_content] edit 无 added/removed/diff, 无法统计行数: tool=%r", tool)
    return item


PATH_LIKE = frozenset({"path", "dest"})  # 句子内 path 类参数（D9: 只取第一个）
COMMAND_MAX_CHARS = 35   # 句子内 command 超长截断并加 …（D9）


def _basename(value: Any) -> str:
    """路径含分隔符时只取文件名（Windows/Unix 均处理）— 小欧 2026-10-12"""
    import ntpath
    import posixpath
    text = str(value)
    return ntpath.basename(text) or posixpath.basename(text) or text


# 参数中文显示映射: 只作用于 content 句子渲染（3.4.2）, content_items 存原始键值 — 小欧 2026-10-12
# 共 84 条 = 保留列 82 键 + edit 派生 2 键, 与 3.4.2 表逐条对应, 句子里不出现任何英文键名
PARAM_ZH = {
    # 路径裸值（3.4.2.1, PATH_LIKE 分支先取文件名再套用本模板）
    "path": "{v}",
    "dest": "{v}",
    # 中文模板（3.4.2.2）
    "timeout": "超时{v}秒",
    "limit": "前{v}条",
    "offset": "从第{v}条起",
    "tail": "末{v}行",
    "sort_by": "按{v}排序",
    "top_n": "前{v}条",
    "num_results": "取{v}条",
    "max_depth": "最深{v}层",
    "page": "第{v}页",
    "slide": "第{v}页",
    # edit 派生量（3.4.2.4，与文档用字一致：新增/删除）
    "lines_added": "新增{v}行",
    "lines_removed": "删除{v}行",
    # 自由文本裸值（3.4.2.3, 值自解释，不加标签；command 仍受 35 截断约束）
    "command": "{v}",
    "sql": "{v}",
    "prompt": "{v}",
    "query": "{v}",
    "pattern": "{v}",
    "message": "{v}",
    "title": "{v}",
    "url": "{v}",
    "text_or_keys": "{v}",
    "callback": "{v}",
    # 中文显示（3.4.2.5）
    "action": "操作{v}",
    "allowed_domains": "允许域名{v}",
    "amount": "数量{v}",
    "append": "追加{v}",
    "blocked_domains": "屏蔽域名{v}",
    "button": "按键{v}",
    "chart_type": "图表{v}",
    "clicks": "点击{v}次",
    "confirm_ddl": "确认{v}",
    "connection_string": "连接串{v}",
    "connection_type": "连接类型{v}",
    "count": "次数{v}",
    "cwd": "目录{v}",
    "delay": "延迟{v}秒",
    "delta": "增量{v}",
    "direction": "方向{v}",
    "dry_run": "试运行{v}",
    "duration": "持续{v}秒",
    "encoding": "编码{v}",
    "end": "结束{v}",
    "filter_title": "过滤标题{v}",
    "force": "强制{v}",
    "format": "格式{v}",
    "glob": "通配{v}",
    "group_by": "按{v}分组",
    "height": "高度{v}",
    "host": "主机{v}",
    "include_hidden": "含隐藏{v}",
    "info_type": "信息{v}",
    "interval": "间隔{v}秒",
    "level": "级别{v}",
    "log_name": "日志{v}",
    "max_events": "最多{v}条",
    "method": "方法{v}",
    "mode": "模式{v}",
    "name": "名称{v}",
    "operations": "操作{v}",
    "pages": "页数{v}",
    "password": "密码{v}",
    "port": "端口{v}",
    "recursive": "递归{v}",
    "region": "区域{v}",
    "schedule": "计划{v}",
    "select_columns": "取列{v}",
    "sheet_name": "表{v}",
    "start": "开始{v}",
    "state": "状态{v}",
    "table_name": "表名{v}",
    "task_name": "任务{v}",
    "timer_id": "定时器{v}",
    "type": "类型{v}",
    "unit": "单位{v}",
    "value_name": "值名{v}",
    "width": "宽度{v}",
    "window_title": "窗口{v}",
    "x": "横坐标{v}",
    "x_label": "横轴{v}",
    "y": "纵坐标{v}",
    "y_label": "纵轴{v}",
    "year": "年份{v}",
}


def _zh_param(key: str, text: str) -> str:
    """单个参数 → 句子片段: 中文模板优先, 不在表内走 键=值 兜底 — 小欧 2026-10-12"""
    template = PARAM_ZH.get(key)
    if template:
        return template.format(v=text)
    return f"{key}={text}"


# 布尔参数肯定/否定词（3.4.2.6, 句子里不出现 True/False）— 小欧 2026-10-12
BOOL_ZH = {
    "append": ("追加", "覆盖"),
    "confirm_ddl": ("已确认", "未确认"),
    "dry_run": ("试运行", "正式执行"),
    "force": ("强制", "不强制"),
    "include_hidden": ("含隐藏", "不含隐藏"),
    "recursive": ("递归", "不递归"),
}


def _zh_value(key: str, val: Any) -> str:
    """单个参数值 → 句子片段: 布尔查 BOOL_ZH, 其余走 _zh_param — 小欧 2026-10-12"""
    if isinstance(val, bool) and key in BOOL_ZH:
        pos, neg = BOOL_ZH[key]
        return pos if val else neg
    text = "" if val is None else str(val)
    if key == "command" and len(text) > COMMAND_MAX_CHARS:
        text = text[:COMMAND_MAX_CHARS] + "…"
    if not text:
        return ""
    return _zh_param(key, text)


def render_line(item: Dict[str, Any]) -> str:
    """单个 item → 一句人话（顺序固定：工具名 中文名 参数 结果短句 耗时；参数遵 D9）— 小欧 2026-10-12"""
    tool = str(item.get("tool") or "")
    tool_zh = str(item.get("tool_zh") or "")
    parts = [tool]
    if tool_zh and tool_zh != tool:
        parts.append(tool_zh)
    params = item.get("params") or {}
    shown = []
    seen_path = False
    for key, val in params.items():
        text = "" if val is None else str(val)
        if key in PATH_LIKE:
            if seen_path:
                continue
            seen_path = True
            if "/" in text or "\\" in text:
                text = _basename(text)
            if not text:
                continue
            shown.append(text)  # path 类只显示值, 不加键名前缀（D9⑦）
            continue
        frag = _zh_value(key, val)
        if frag:
            shown.append(frag)
    if shown:
        parts.append(" | ".join(shown))
    message = str(item.get("message") or "")
    if message:
        parts.append(message)
    duration = item.get("duration_ms")
    if isinstance(duration, (int, float)) and duration > 0:
        parts.append(f"({duration / 1000:.1f}s)")
    return " ".join(p for p in parts if p)


def build_content_items(tool_result: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """tool_result[] → content_items 对象数组（唯一真身）。纯函数, 不抛异常 — 小欧 2026-10-12"""
    items: List[Dict[str, Any]] = []
    for element in tool_result or []:
        if not isinstance(element, dict):
            continue
        try:
            items.append(_build_item(element))
        except Exception as exc:
            logger.warning("[observation_content] 单元素投影失败已降级: %s: %r",
                           type(exc).__name__, exc)
            items.append({"tool": str(element.get("tool_name") or ""), "tool_zh": "",
                          "exec_code": "unknown", "message": "", "params": {},
                          "duration_ms": 0, "detail": ""})

    for idx in range(len(items) - 1, -1, -1):  # 体积兜底: 只置空 params, 绝不删行（D5）
        if len(json.dumps(items, ensure_ascii=False)) <= CONTENT_MAX_CHARS:
            break
        if items[idx].get("params"):
            items[idx]["params"] = {}
    if len(json.dumps(items, ensure_ascii=False)) > CONTENT_MAX_CHARS:
        logger.warning("[observation_content] content 超 %d 字符且 params 已全部置空: tool_count=%d",
                       CONTENT_MAX_CHARS, len(items))
    return items
```

##### 3.7.3.2 修改 `backend/app/services/agent/steps/observation_step.py`

```diff
--- a/backend/app/services/agent/steps/observation_step.py
+++ b/backend/app/services/agent/steps/observation_step.py
@@ -4,9 +4,15 @@
 # 编辑历史:
 # 2026-07-18 小欧 - timestamp 注解 Optional[int]→Optional[str] 与运行时 UTC Z 字符串值对齐, 消除时间归一化不一致
 # 2026-08-18 小欧 - 落码: ObservationStep 仅携带 tool_result 数组(每元素自包含);
 #   删 llm_data/other_data/parallel_results 顶层字段; get_content 返回 ""(数据在 tool_result, 不重复发 content)
+# 2026-10-12 小欧 - 启用 content（北京老陈令）: __init__ 内自算 content_items 对象数组,
+#   get_content 返回其 JSON 字符串, _extra_fields 增返回 content_items;
+#   调用方(observation_builder / react_step)零改动, 两条 emit 路径天然一致 — 小欧 2026-10-12
 
+import json
 from typing import Any, Dict, List, Optional
 
 from .base import ReasoningStep
+from .observation_content import build_content_items, render_line
@@ -23,13 +29,20 @@
     ):
         ReasoningStep.__init__(self, step, timestamp)
         self._tool_result = tool_result or []
+        self._content_items = build_content_items(self._tool_result)
 
     def get_content(self) -> str:
-        return ""
+        """一个工具一句话, 行数 == content_items 元素数 — 小欧 2026-10-12"""
+        return "\n".join(render_line(item) for item in self._content_items)
 
+    @property
+    def content_items(self) -> List[Dict[str, Any]]:
+        return self._content_items
+
     @property
     def tool_result(self) -> List[Dict[str, Any]]:
         return self._tool_result
 
     def _extra_fields(self) -> Dict[str, Any]:
+        result: Dict[str, Any] = {"content_items": self._content_items}
         if self._tool_result:
-            return {"tool_result": self._tool_result}
-        return {}
+            result["tool_result"] = self._tool_result
+        return result
```

##### 3.7.3.3 修改 `backend/FUNCTIONS.md`

```diff
+| 函数名 | 说明 | 参数 | 返回值 |
+| build_content_items | observation.content 启用: tool_result[] 投影为 content_items 对象数组（唯一真身）；按 DROP_KEYS/BODY_KEYS 规整 params；edit 特例输出 lines_added/lines_removed | tool_result: List[Dict] | List[Dict]（7 字段对象数组） |
```

##### 3.7.3.4 单测项（AGENTS.md 要求，本地验证，不提交）

| # | 用例 | 断言 |
|---|---|---|
| T1 | tool_result 为空 | 返回 []，get_content() 为空串 "" |
| T2 | 元素缺 llm_data / action / status | 不抛异常，各字段取默认值 |
| T3 | edit 元素带 metrics.added/removed | params 输出 lines_added / lines_removed，且不含 old_string / new_string；数值与工具 summary 口径一致 |
| T4 | 含丢列参数（如 shell_type） | 不出现在 params |
| T5 | 值超 50 的非正文参数 | 该键消失，不截断、不带省略号 |
| T6 | command 含多行 | 只保留首行 |
| T7 | 构造超大 items | 循环后 dumps 长度 <= CONTENT_MAX_CHARS，行数不变 |
| T8 | splitlines(content) | 行数 == len(content_items)，且每行以该 item 的 tool 开头（防两处漂移） |
| T9 | 元素为非 dict | 跳过且不抛异常 |
| T10 | 单 item 含 params、message 且 duration>0 | content 行为 `tool tool_zh k=v message (2.8s)`，顺序固定，空段省略；path 类参数显示裸值（`test_report.pdf` 而非 `path=test_report.pdf`） |
| T11 | 单 item duration_ms=0 或 message 为空 | 对应段省略，不出现空括号或多余空格 |
| T12 | 单 item 同时含 `path` + `dest` | 句子只出现第一个 path 类参数的值，不出现第二个 |
| T13 | path 值为 `F:\dir\test_report.pdf` | 句子只出现 `test_report.pdf`，不出现完整路径 |


### 3.8 前端改动（2 处）

| # | 文件 | 改动 |
|---|---|---|
| F1 | `frontend/src/features/chat/services/sseParser.ts:901-912` | observation 分支取出 `rawData.content`（字符串）与 `rawData.content_items`（数组）存入 step；取不到则给空值，不抛错；类型 `ExecutionStep` 增 `contentItems?: ObservationContentItem[]` |
| F2 | 待前端渲染讨论时定 | 是否新增渲染块、如何渲染、什么顺序、用什么样式，全部在专门讨论前端时由北京老陈定，本方案不预设 |

F2 边界（只划边界，不定实现）：

| 项 | 规则 |
|---|---|
| 数据 | 后端保证 `content` 与 `contentItems` 同源一致、一起落库、一起下发，前端可直接取用 |
| 前端职责 | 一切渲染规则在专门讨论前端时定 |
| 唯一约束 | 数据天然一行一工具（`content` 一句一行，`contentItems` 一元素一工具），供前端取用时参考 |

### 3.9 风险与防御

| # | 风险 | 防御 |
|---|---|---|
| 1 | 通用 content 渲染器把 JSON 原文显示出来 | 核查 `kind:'obs'` 分支是否经通用正文渲染器；若有则 contentItems 只存不渲染，由 F2 独占消费 |
| 2 | content / content_items 两处数据漂移 🔴 | 两者同源，content 必须由 content_items 逐条 render_line 生成，禁止分别构造；单测 T8 断言行数与 tool_zh 一致 |
| 3 | 统一阈值导致 90% bash 参数全空 🔴 | 已用长度分级（D7 / 3.5.4）取代：命令正文取首行 |
| 4 | 漏登记的工具参数静默消失 | 保留列为空属正常（3.5.5），前端无块可渲即正确行为 |
| 5 | `llm_data` 结构不完整导致投影抛异常 🔴 | 全 `.get()` 逐级兜底 + 单元素 try/except 降级（3.6 末） |
| 6 | content / content_items 误入 LLM 上下文 🔴 | 真源约定 + 单测锁死两个载体均不进上下文 |
| 7 | 新增渲染块与现有子行信息重复，观感冗余 | 两者职责不同（动作结果 vs 逐工具执行概况）；落地后由北京老陈实看观感再定去留（3.13 L4） |
| 8 | content 体积膨胀 | 2KB 上限（D5），超限置空 params |

### 3.10 验收标准

| # | 验收项 | 判定 |
|---|---|---|
| A1 | 新跑一轮对话后，查库 observation 的 `content` 非空 | ✅ |
| A2 | `content` 行数 == `content_items` 元素数 == `tool_result` 元素数，每行对应且仅对应一个工具 | ✅ |
| A3 | 数组长度 == `tool_result` 长度（单工具=1，多工具=N） | ✅ |
| A4 | 每个元素含 tool / exec_code / params / message 四要素 | ✅ |
| A5 | 失败工具的 `detail` 正确带出 | ✅ |
| A6 | `content` 为空串且 `contentItems` 为空数组时，后端不报错，落库正常 | ✅ |
| A7 | LLM 回复质量无变化（content 不进上下文） | ✅ |
| A8 | 前端 `npm run check:full` 通过 | ✅ |
| A9 | 构造 `llm_data` 缺 `status`/`action` 的假工具 → content 仍产出且不抛异常 | ✅ |
| A10 | 保留列为空的工具（params={}） | 前端不渲染其参数段，不报错不打日志 | ✅ |
| A11 | bash 行能显示首行命令（验证长度分级生效，非空 params） | ✅ |
| A12 | edit 行输出 lines_added / lines_removed，且不含 old_string / new_string 原文 | ✅ |
| A13 | 超大 content（并行多工具）被 2KB 兜底削到限内 | ✅ |
| A14 | `copy` 的 `dest` 与 `path` 均以真实键名出现在 content 中，未被改名或合并 | ✅ |

### 3.11 改动文件清单

| 文件 | 类型 | 预估 |
|---|---|---|
| `backend/app/services/agent/steps/observation_content.py` | 新增 | ~130 |
| `backend/app/services/agent/steps/observation_step.py` | 改 | ~6 |
| `backend/FUNCTIONS.md` | 改（登记新函数） | ~1 |
| `frontend/src/features/chat/services/sseParser.ts` | 改 | ~6（含类型加 `contentItems`） |
| `frontend/src/features/chat/components/pipeline/ToolCallLine.tsx` | 改 | ~40 |

### 3.12 实施顺序

```
1. B1（纯函数投影，可单测，不动线上）
2. B2 让 ObservationStep 自算content → 后端查库验收 A1~A5、A9~A14
3. B3 登记 FUNCTIONS.md
4. F1（只存不渲染）→ 确认 JSON 完整到达前端
5. 核查 3.9 风险 1
6. F2（渲染块）      → A6 / A8
7. 真实对话全链路验收 + A7
```

### 3.13 待定项与遗留（落地时须先结清）

| # | 事项 | 说明 |
|---|---|---|
| L1 | 参数归一口径复核 | B1 落地时核对 DROP_KEYS 与 3.5.6 表丢列一一对应，改表即改常量 |
| L2 | 长度阈值最终值 | 正文类首行阈值与标识类阈值（现取 50）落地时按真实观感微调 |
| L3 | 通用 content 渲染器核查 | 确认 `kind:'obs'` 分支是否会把 JSON 原文显示出来（3.9 风险 1） |
| L4 | 新增渲染块与现有子行的观感取舍 | 落地后由北京老陈实看界面，再定是否保留/精简现有子行 |

---

## 四、tool_zh 中文名准确性核查记录

### 4.1 核查结论（63 个工具逐个对照功能定义）

核查时间：2026-10-12 17:35:29，核查人：小欧。
方法：逐个读取各工具 `llm_data.action.tool_zh` 现值，对照注册表功能定义判定是否准确、名副其实。

#### 4.1.1 A类：错误（5 个，必须改）

| 工具 | 现值 | 问题 | 建议值 |
|---|---|---|---|
| `event_log` | 获取 | 二字"获取"无信息量 | 读取事件日志 |
| `window_info` | 获取 | 同上，且与 event_log 撞名 | 获取窗口信息 |
| `set_window_state` | 窗口状态 | 名词残缺（最大化/最小化/置顶是动作） | 设置窗口状态 |
| `bash` | 执行 | 笼统且与 execute_sql 撞名 | 执行命令 |
| `execute_sql` | 执行 | 同上 | 执行SQL |

#### 4.1.2 B类：笼统或不统一（12 个，建议改）

| 工具 | 现值 | 问题 | 建议值 |
|---|---|---|---|
| `query_sql` | 查询 | 笼统 | 查询SQL |
| `read` | 读取 | 读什么没说 | 读取文件 |
| `write` | 写入 | 写什么没说 | 写入文件 |
| `delete` | 删除 | 与删除注册表不对齐 | 删除文件 |
| `get_db_schema` | 获取结构 | 实为表/字段/约束/索引 | 获取表结构 |
| `rename` | 重命名 | 与复制文件/移动文件不对齐 | 重命名文件 |
| `compress` | 压缩 | 与解压文件不对齐 | 压缩文件 |
| `download` | 文件下载 | 名词，其他均为动词开头 | 下载文件 |
| `searchweb` | 搜索 | 与搜索工具/搜索文件撞车（实为搜索引擎查实时信息） | 联网搜索 |
| `sysinfo` | 系统信息 | 名词 | 获取系统信息 |
| `notify` | 系统通知 | 名词（实为发送通知） | 发送通知 |
| `clipboard_control` | 剪贴板 | 纯名词（待定） | 读写剪贴板 |

#### 4.1.3 C类：准确（46 个，不动）

`tree` 列出目录树（与 listdir 区分）、`find`/`grep`/`searchtool` 一组、`read_docx` 系列、`write_*` 系列、`timer_*` 系列、`registry_*` 系列、`keyboard_control`、`mouse_move`、`timenow` 等全部名副其实。

#### 4.1.4 落地说明

改动位置为各工具文件 `llm_data.action.tool_zh` 的值，只改中文名、不改工具名；
`tool_zh` 仅做显示（content 句子中文名与前端展示），LLM 与执行链路无影响。

### 4.2 63 个工具中文名全表（按注册表 9 分类，判定见 4.1）

#### 4.2.1 FILE（11 个）

| # | 工具 | 中文名 | 判定 | 新名词（北京老陈 2026-10-12 定） |
|---|---|---|---|---|
| 1 | copy | 复制文件 | 不动 | 复制 |
| 2 | delete | 删除 | B类：改删除文件 | 删除 |
| 3 | edit | 编辑文件 | 不动 | 编辑 |
| 4 | find | 搜索文件 | 不动 | 搜文件 |
| 5 | grep | 内容搜索 | 不动 | 搜内容 |
| 6 | listdir | 列出目录 | 不动 | 列文件 |
| 7 | move | 移动文件 | 不动 | 移文件 |
| 8 | read | 读取 | B类：改读取文件 | 读文件 |
| 9 | rename | 重命名 | B类：改重命名文件 | 重命名 |
| 10 | tree | 列出目录树 | 不动 | 列目录 |
| 11 | write | 写入 | B类：改写入文件 | 写文件 |

#### 4.2.2 DOCUMENT（11 个）

| # | 工具 | 中文名 | 判定 | 新名词（北京老陈 2026-10-12 定） |
|---|---|---|---|---|
| 12 | compress | 压缩 | B类：改压缩文件 | 压缩 |
| 13 | extract | 解压文件 | 不动 | 解压 |
| 14 | read_docx | 读取Word | 不动 | 读WORD |
| 15 | read_pdf | 读取PDF | 不动 | 读PDF |
| 16 | read_pptx | 读取PPT | 不动 | 读PPT |
| 17 | read_xlsx | 读取Excel | 不动 | 读EXCEL |
| 18 | readmedia | 读取媒体 | 不动 | 读媒体 |
| 19 | write_docx | 写入Word | 不动 | 写WORD |
| 20 | write_pdf | 写入PDF | 不动 | 写PDF |
| 21 | write_pptx | 写入PPT | 不动 | 写PPT |
| 22 | write_xlsx | 写入Excel | 不动 | 写EXCEL |

#### 4.2.3 FUNDAMENTAL（6 个）

| # | 工具 | 中文名 | 判定 | 新名词（北京老陈 2026-10-12 定） |
|---|---|---|---|---|
| 23 | bash | 执行 | A类：改执行命令 | |
| 24 | fetchpage | 获取网页 | 不动 | 读网页 |
| 25 | notify | 系统通知 | B类：改发送通知 | 发通知 |
| 26 | searchtool | 搜索工具 | 不动 | 搜TOOL |
| 27 | searchweb | 搜索 | B类：改联网搜索 | 搜网络 |
| 28 | timenow | 获取时间 | 不动 | 取时间 |

#### 4.2.4 NETWORK（3 个）

| # | 工具 | 中文名 | 判定 | 新名词（北京老陈 2026-10-12 定） |
|---|---|---|---|---|
| 29 | download | 文件下载 | B类：改下载文件 | 下载 |
| 30 | httpget | HTTP请求 | 不动 | |
| 31 | ping_port | 网络诊断 | 不动 | |

#### 4.2.5 DATAANALYSIS（6 个）

| # | 工具 | 中文名 | 判定 | 新名词（北京老陈 2026-10-12 定） |
|---|---|---|---|---|
| 32 | analyze_data | 分析数据 | 不动 | |
| 33 | execute_sql | 执行 | A类：改执行SQL | 执行SQL |
| 34 | filter_data | 筛选数据 | 不动 | |
| 35 | generate_chart | 生成图表 | 不动 | |
| 36 | get_db_schema | 获取结构 | B类：改获取表结构 | 取表结构 |
| 37 | query_sql | 查询 | B类：改查询SQL | 查询SQL |

#### 4.2.6 DESKTOP（11 个）

| # | 工具 | 中文名 | 判定 | 新名词（北京老陈 2026-10-12 定） |
|---|---|---|---|---|
| 38 | clipboard_control | 剪贴板 | B类：改读写剪贴板（待定） | 剪贴读写 |
| 39 | keyboard_control | 键盘控制 | 不动 | |
| 40 | mouse_click | 点击 | 不动 | 点击鼠标 |
| 41 | mouse_move | 鼠标移动 | 不动 | 移动鼠标 |
| 42 | mouse_position | 获取鼠标位置 | 不动 | 鼠标位置 |
| 43 | mouse_scroll | 鼠标滚动 | 不动 | |
| 44 | screen_capture | 屏幕截图 | 不动 | |
| 45 | set_window_state | 窗口状态 | A类：改设置窗口状态 | 设窗口状态 |
| 46 | window_focus | 窗口聚焦 | 不动 | |
| 47 | window_info | 获取 | A类：改获取窗口信息 | 取窗口信息 |
| 48 | window_resize | 窗口调整 | 不动 | 窗口缩放 |

#### 4.2.7 SYSTEM（6 个）

| # | 工具 | 中文名 | 判定 | 新名词（北京老陈 2026-10-12 定） |
|---|---|---|---|---|
| 49 | create_task | 创建任务 | 不动 | 建任务 |
| 50 | delete_task | 删除任务 | 不动 | 删任务 |
| 51 | event_log | 获取 | A类：改读取事件日志 | 读日志 |
| 52 | list_tasks | 列出任务 | 不动 | 列任务 |
| 53 | sysinfo | 系统信息 | B类：改获取系统信息 | 查系统 |
| 54 | which | 查找命令 | 不动 | 找命令 |

#### 4.2.8 TIMER（6 个）

| # | 工具 | 中文名 | 判定 | 新名词（北京老陈 2026-10-12 定） |
|---|---|---|---|---|
| 55 | calendar | 日历查询 | 不动 | 查日历 |
| 56 | timeadd | 时间加减 | 不动 | 加减时间 |
| 57 | timediff | 时间差值 | 不动 | 算时间差 |
| 58 | timer_clear | 清除定时器 | 不动 | 清定时器 |
| 59 | timer_list | 列出定时器 | 不动 | 列定时器 |
| 60 | timer_set | 设置定时器 | 不动 | 设定时器 |

#### 4.2.9 WIN_REGISTRY（3 个）

| # | 工具 | 中文名 | 判定 | 新名词（北京老陈 2026-10-12 定） |
|---|---|---|---|---|
| 61 | registry_delete | 删除注册表 | 不动 | 删注册表 |
| 62 | registry_read | 读取注册表 | 不动 | 读注册表 |
| 63 | registry_write | 写入注册表 | 不动 | 写注册表 |

---

## 五、message 内容优化（tool_zh + message 合读通顺）

### 5.1 问题与改法

现状：message 几乎都在重复 tool_zh（`复制文件 复制成功`、`读取PDF 读取PDF成功`、`窗口聚焦 窗口聚焦完成`），tool_zh + message 连读别扭。

改法：message 删掉 tool_zh 前缀，只留`成功/失败/完成/警告 + 具体信息`。tool_zh 用新短名词。

### 5.2 63 工具 message 现状与改后对照

#### 5.2.1 FILE（11 个）

| 工具 | tool_zh新 | message现状 | 改后message | 组合效果 |
|---|---|---|---|---|
| copy | 复制 | 复制成功/复制失败 | 成功/失败+原因 | 复制 成功 |
| delete | 删除 | 删除成功/删除失败 | 成功/失败+原因 | 删除 成功 |
| edit | 编辑 | 编辑完成/编辑失败 | 完成/失败+原因 | 编辑 完成 |
| find | 搜文件 | 搜索完成 | 完成+N个结果 | 搜文件 完成 |
| grep | 搜内容 | 搜索完成/搜索失败 | 完成/失败+原因 | 搜内容 完成 |
| listdir | 列文件 | 列出目录成功/失败 | 成功/失败 | 列文件 成功 |
| move | 移文件 | 移动成功/移动失败 | 成功/失败 | 移文件 成功 |
| read | 读文件 | 读取成功:从85行起，取130行 | 成功:+详情 | 读文件 成功:从85行起，取130行 |
| rename | 重命名 | 重命名成功 | 成功 | 重命名 成功 |
| tree | 列目录 | 列出目录树成功/失败 | 成功/失败 | 列目录 成功 |
| write | 写文件 | 写入成功/失败/成功但有警告 | 成功/失败/成功但有警告 | 写文件 成功 |

#### 5.2.2 DOCUMENT（11 个）

| 工具 | tool_zh新 | message现状 | 改后message | 组合效果 |
|---|---|---|---|---|
| compress | 压缩 | 压缩成功 | 成功 | 压缩 成功 |
| extract | 解压 | 解压成功 | 成功 | 解压 成功 |
| read_docx/pdf/pptx/xlsx | 读WORD/PDF/PPT/EXCEL | 读取X成功 | 成功 | 读PDF 成功 |
| readmedia | 读媒体 | 读取媒体文件成功 | 成功 | 读媒体 成功 |
| write_docx/pdf/pptx/xlsx | 写WORD/PDF/PPT/EXCEL | 写入X成功/失败 | 成功/失败 | 写PDF 成功 |

#### 5.2.3 FUNDAMENTAL（6 个）

| 工具 | tool_zh新 | message现状 | 改后message | 组合效果 |
|---|---|---|---|---|
| bash | （空，仍用执行） | 执行成功/失败/成功有警告 | 成功/失败/成功有警告 | 执行 成功 |
| fetchpage | 读网页 | 获取网页内容成功/失败/完成但有警告 | 成功/失败/完成但有警告 | 读网页 成功 |
| notify | 发通知 | 通知发送成功 | 成功 | 发通知 成功 |
| searchtool | 搜TOOL | 搜索完成/完成-未找到匹配 | 完成/完成-未找到匹配 | 搜TOOL 完成 |
| searchweb | 搜网络 | 搜索完成 | 完成 | 搜网络 完成 |
| timenow | 取时间 | 获取当前时间成功 | 成功 | 取时间 成功 |

#### 5.2.4 NETWORK（3 个）

| 工具 | tool_zh新 | message现状 | 改后message | 组合效果 |
|---|---|---|---|---|
| download | 下载 | 文件下载成功/失败 | 成功/失败 | 下载 成功 |
| httpget | （空，仍用HTTP请求） | HTTP请求成功/失败 | 成功/失败 | HTTP请求 成功 |
| ping_port | （空，仍用网络诊断） | Ping可达/端口开放 | 可达/开放 | 网络诊断 可达 |

#### 5.2.5 DATAANALYSIS（6 个）

| 工具 | tool_zh新 | message现状 | 改后message | 组合效果 |
|---|---|---|---|---|
| analyze_data | （空，仍用分析数据） | 分析成功/失败 | 成功/失败 | 分析数据 成功 |
| execute_sql | 执行SQL | 执行成功 | 成功 | 执行SQL 成功 |
| filter_data | （空，仍用筛选数据） | 筛选成功 | 成功 | 筛选数据 成功 |
| generate_chart | （空，仍用生成图表） | 图表生成成功 | 成功 | 生成图表 成功 |
| get_db_schema | 取表结构 | 获取成功/失败 | 成功/失败 | 取表结构 成功 |
| query_sql | 查询SQL | 查询成功/DB原生错误 | 成功/原生错误直出 | 查询SQL 成功 |

#### 5.2.6 DESKTOP（11 个）

| 工具 | tool_zh新 | message现状 | 改后message | 组合效果 |
|---|---|---|---|---|
| clipboard_control | 剪贴读写 | 剪贴板read/write成功 | 读成功/写成功 | 剪贴读写 读成功 |
| keyboard_control | （空，仍用键盘控制） | 键盘操作完成 | 完成 | 键盘控制 完成 |
| mouse_click | 点击鼠标 | 单击成功 | 成功 | 点击鼠标 成功 |
| mouse_move | 移动鼠标 | 鼠标移动完成 | 完成 | 移动鼠标 完成 |
| mouse_position | 鼠标位置 | 获取鼠标位置成功 | 成功 | 鼠标位置 成功 |
| mouse_scroll | （空，仍用鼠标滚动） | 滚动完成 | 完成 | 鼠标滚动 完成 |
| screen_capture | （空，仍用屏幕截图） | 截图完成 | 完成 | 屏幕截图 完成 |
| set_window_state | 设窗口状态 | 窗口操作restore成功 | restore成功 | 设窗口状态 restore成功 |
| window_focus | （空，仍用窗口聚焦） | 窗口聚焦完成/聚焦窗口失败 | 完成/失败 | 窗口聚焦 完成 |
| window_info | 取窗口信息 | 获取成功 | 成功 | 取窗口信息 成功 |
| window_resize | 窗口缩放 | 调整窗口大小失败 | 失败+原因 | 窗口缩放 失败 |

#### 5.2.7 SYSTEM（6 个）

| 工具 | tool_zh新 | message现状 | 改后message | 组合效果 |
|---|---|---|---|---|
| create_task | 建任务 | 创建计划任务成功 | 成功 | 建任务 成功 |
| delete_task | 删任务 | 删除计划任务成功 | 成功 | 删任务 成功 |
| event_log | 读日志 | 获取成功 | 成功 | 读日志 成功 |
| list_tasks | 列任务 | 获取计划任务列表成功 | 成功 | 列任务 成功 |
| sysinfo | 查系统 | 获取系统信息成功 | 成功 | 查系统 成功 |
| which | 找命令 | 命令可用 | 可用 | 找命令 可用 |

#### 5.2.8 TIMER（6 个）

| 工具 | tool_zh新 | message现状 | 改后message | 组合效果 |
|---|---|---|---|---|
| calendar | 查日历 | 日期检查完成 | 完成 | 查日历 完成 |
| timeadd | 加减时间 | 时间加减成功 | 成功 | 加减时间 成功 |
| timediff | 算时间差 | 计算时间差成功 | 成功 | 算时间差 成功 |
| timer_clear | 清定时器 | 定时器已取消 | 已取消 | 清定时器 已取消 |
| timer_list | 列定时器 | 获取定时器列表成功 | 成功 | 列定时器 成功 |
| timer_set | 设定时器 | 定时器设置成功 | 成功 | 设定时器 成功 |

#### 5.2.9 WIN_REGISTRY（3 个）

| 工具 | tool_zh新 | message现状 | 改后message | 组合效果 |
|---|---|---|---|---|
| registry_delete | 删注册表 | 删除注册表成功/失败 | 成功/失败 | 删注册表 成功 |
| registry_read | 读注册表 | 读取注册表成功/失败 | 成功/失败 | 读注册表 成功 |
| registry_write | 写注册表 | 写入注册表成功 | 成功 | 写注册表 成功 |

### 5.3 落地方式（待定）

| 方式 | 做法 | 代价 |
|---|---|---|
| A：改 63 个工具源码 | 每个 message 删前缀 | 63 文件，一劳永逸，LLM/前端同步受益 |
| B：只在 render_line 里去重 | 句子渲染时剥掉 tool_zh 前缀 | 0 文件改动，但 LLM 上下文不变 |

---

编写人：小欧
编写时间：2026-10-12 14:32:10