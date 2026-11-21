# [1] Omni 系统 Tool 编写规范（入口与出口）

**创建时间**: 2026-11-20
**制定人**: 小欧
**更新时间**: 2026-11-21 19:19:20
**更新人**: 小欧
**适用范围**: OmniAgentAs 后端所有 tool（`backend/app/tools/**`）
**总结来源**: `write_text_file` / `read_text_file` / `read_media_file` / `query_sql` / `search_web` / `question` / `schedule` 七个代表工具的实际代码

---

## 版本历史

| 版本 | 时间 | 签名 | 修改简介 |
|---|---|---|---|
| V1.6 | 2026-11-21 19:19:20 | 小欧 | 3.3.2 产物声明契约改写：唯一实现迁至 `app/utils/artifacts.py`，条目定五字段（`tool_name`/`name`/`path`/`form`/`type`），落点由 `llm_data.action.artifacts` 改 `other_data["artifacts"]`（职责归位），收集条件收窄为 `exec_code ∈ {success, warning}`，去重键统一（URL 去签名参数 / 本地 normcase+abspath），上限 50 保留最新；声明入口改 `declare_artifact_file`/`declare_artifacts`/`artifact_from_url`。3.4.5 同步说明迁出与四旧函数删除（不留兼容别名）；3.6 `other_data` 键表补 `artifacts`（7→8 键）；四章消费对照与五章自查清单同步新落点 |
| V1.5 | 2026-11-21 16:56:35 | 小欧 | 2.1 阻塞工具举例去掉已删除的工具名，仅留 `shell`/`query_sql`（本规范只写入口/出口通用要求，不记录具体工具的增删）；历史条目按原样保留，不删历史 |

---

## 一、为什么要有这份规范

工具是 Agent 和 LLM 之间的契约面。返回值组装若不统一，会同时破坏三件事：给 LLM 的观察文本（`observation_formatter`）、前端的工具行与浮层参数（`ToolCallLine`/`ParamsPanel`）、落库与产出物统计（`chat_tasks.artifacts`）。

本规范只讲两个重点：**入口**（工具函数的定义与 schema）和**出口**（return 的三字段构造）。中间业务逻辑不属于本规范。

---

## 二、入口规范

### 2.1 函数签名

```python
async def <tool_name>(param1: type, param2: Optional[type] = None, ...) -> Dict[str, Any]:
```

| 要求 | 说明 |
|---|---|
| `async def` 或 `def` | 执行器按 `inspect.iscoroutinefunction` 分流（协程直调 / 同步走有界线程池），**两种都支持**；有 I/O 等待优先 `async`，纯阻塞工具（如 `shell`/`query_sql`）保持 `def`，**禁止把阻塞工具硬改 `async`**（会取消线程卸载、阻塞事件循环，见 `tool_retry_engine.py:283`） |
| 类型注解 | 参数与返回值 `-> Dict[str, Any]` 必须完整 |
| 可选参数 | 用 `Optional[X] = None`；有业务默认值的用具体默认值（如 `mode: str = "t2v"`、`limit: int = 50`） |
| 返回类型 | 恒为 `Dict[str, Any]`，且必须是 `build_success/error/warning` 产出的三字段结构 |

证据：`write(path, content, encoding=None, append=False)`、`query_sql(sql, connection_type="sqlite", limit=50)`、`generate_video(prompt, mode="t2v", timeout=660)`。

### 2.2 计时起点

入口第一行取 `t0`，出口所有分支统一算 `duration_ms`：

```python
t0 = _time_mod.perf_counter()   # 或 time.monotonic()
...
duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
```

证据：`write_text_file`、`query_sql`、`search_web`、`question`、`schedule` 全部如此。

**计时是硬要求**：所有工具入口第一行取 `t0`，各出口按实际耗时算 `duration_ms`，一律不得硬编码 `0`。没有例外，不设豁免。

### 2.3 入参定位（路径类工具）

涉及文件路径的工具，入口统一走四级合法性总入口 `check_path_four_level(path, OpCategory.EXISTS/XX)`，不在工具里自己做存在性/越界判断（去检查化）。证据：`read_text_file`、`read_media_file`、`query_sql`。

### 2.4 结构化列表参数（schedule / question 类）

当入参是"对象数组"这类结构化数据（`schedule.items`、`question.questions`）时，分两层：**Schema 层前置约束**（让 LLM 从参数结构就不会填错）+ **校验层兜底归一化**（拦住 LLM 仍填错的情况）。

#### 2.4.1 Schema 定义（第一层，最关键）

**用扁平 `List[Dict[str, Any]]` + `Field(json_schema_extra=...)` 内联 item 的 JSON Schema，禁止嵌套 BaseModel** —— 嵌套会生成 `$ref`/`$defs`，被严格 provider（opencode/deepseek）拒绝，已实测：

```python
# agent_schema.py
class ScheduleInput(BaseModel):
    items: List[Dict[str, Any]] = Field(
        ...,
        description=SCHEDULE_ITEMS_PARAM_DESC,          # 参数描述文案(单一真源常量)
        json_schema_extra={
            "items": SCHEDULE_ITEM_SCHEMA,               # 内联 item 结构(enum/required/maxLength/additionalProperties)
            "maxItems": SCHEDULE_INPUT_MAX_ITEMS,        # 数组长度上限
        },
    )
    plan_stage: str = Field(
        ..., description=SCHEDULE_PLAN_STAGE_DESC,
        json_schema_extra={"enum": list(SCHEDULE_PLAN_STAGES)},  # 枚举前置
    )
```

`SCHEDULE_ITEM_SCHEMA` 本身是普通 dict，把约束全部前置到参数层：

```python
SCHEDULE_ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "content": {"type": "string", "maxLength": 100, "description": "任务简述"},
        "status":  {"type": "string", "enum": ["pending","in_progress","completed","cancelled"], "description": "四选一"},
    },
    "required": ["content", "status"],
    "additionalProperties": False,     # 拒未知字段
}
```

嵌套结构（如 `question.options`）同样内联：item schema 里嵌 `"options": {"type":"array", "minItems":1, "maxItems":5, "items": {...}}`，全程 dict、无 BaseModel 嵌套，实测不产生 `$ref`/`$defs`。

**单一真源铁律**：上限值、枚举值、参数描述文案全部定义在 `tool_constants`（`SCHEDULE_*` / `QUESTION_*`），schema、注册描述、校验层三处 import 同一常量；允许字段白名单从 schema 的 properties 派生（`SCHEDULE_ITEM_KEYS = frozenset(SCHEDULE_ITEM_SCHEMA["properties"].keys())`），不在校验层硬编码，杜绝两处口径漂移。

#### 2.4.2 校验层归一化（第二层，兜底）

Schema 约束是"让 LLM 尽量不填错"，但仍需工具入口做兜底。必须先经模块级 `_normalize_<param>(...)` 归一化函数，返回三元组：

```python
def _normalize_items(items: Any) -> Tuple[List[Dict], str, List[str]]:
    """返回 (归一化清单, 硬错误文案, 警告列表)"""
```

| 返回值 | 语义 | 出口三态映射 |
|---|---|---|
| 归一化清单 | 裁剪/补默认值/归位后的干净数据 | 成功或警告分支的 `data` 与 `action.params` 用它 |
| 硬错误文案 | 结构不符、必填缺失、类型错、未知字段、重复 label 等**不可容忍**问题 | 非空 → `build_error`，清单不落地 |
| 警告列表 | 条数超限裁剪、字段超长截断、枚举非法归位等**可容忍**问题 | 非空但无硬错误 → `build_warning`，裁剪后数据照常落地 |

**错误二分铁律**（`schedule._normalize_items` / `question._normalize_params` 同构）：

- **完全错误 → 拒绝**：参数不是数组、元素非对象、含未知字段（按 schema properties 派生白名单校验）、必填缺失、类型错、`question` 选项 label 重复。返回错误文案要用"第 N 项 + 具体原因"，可直接回填 `hint`。
- **可容忍错 → 裁剪/归位 + 警告继续**：数组长度超上限取前 N 项、字符串超长截断、枚举值非法归默认（如 `status` 非法归 `pending`）。每处裁剪都记一条中文警告，进 `llm_data.status.detail`（→ 前端「⚠警告」行）+ 出口 `build_warning`，数据照常落地，不打断 ReAct。

**其他要求**：

- 上限与参数描述文案统一放 `tool_constants`（`SCHEDULE_*` / `QUESTION_*`），工具层只 import 不重定义；schema 描述与校验同源，口径不漂移。
- 归一化函数在工具函数外（模块级纯函数），业务主函数只调用、不内联校验逻辑（SLAP）。
- 多个相关参数的语义一致性做**宽松核对**，不一致只反馈不拒绝：如 `schedule.plan_stage` 与 `items` 语义不符，`_check_plan_stage` 返回提示进 `llm_data.plan_stage_note`，LLM 下一轮可见，不硬拒。

证据：`schedule._normalize_items`/`_check_plan_stage`、`question._normalize_params` 及各自 `build_error/build_warning/build_success` 三态出口。

### 2.5 schema 与描述

工具在 `*_register.py` 里注册，提供 `description` / `input_model`（扁平） / `examples`。描述要消除含糊、明确参数语义与执行结果的输出形态；`hide_from_steps=True` 仅用于走独立通道、不进前端步骤流工具行的交互类工具。**当前实际声明者只有 `schedule` 与 `question` 两个**（`agent_register.py:74` 的 `hide_from_steps = {"schedule", "question"}`）；生成类工具已于 2026-11-20 回归通用工具行（`media_register.py:9`）。普通工具一律默认可见。

---

## 三、出口规范（核心）

**输出部分总纲 —— data vs llm_data 的本质区别：**

| | `data` | `llm_data` |
|---|---|---|
| **本质** | 工具执行的真实产出数据（payload 本身） | 给 LLM 看的结论/状态/元信息（关于这次执行的描述） |
| **例子** | 文件内容、查询 rows、生成结果的 URL/路径 | summary、status、duration、metrics |
| **消费** | 前端「结果」视图 raw_data、LLM 观察「详情」段 | LLM 观察「观察」行、前端工具行/结果区、遥测统计 |

一句话：**data = 工具执行结果的输出（payload 本身），llm_data = 关于这次执行的描述（结论/状态）**。后续所有出口规则都建立在这个区别上。

> ⚠️ 术语区分：`data` 是 **tool 执行结果的输出**，不叫"产出物"。"产出物（artifacts）"是另一个概念——任务级产物清单，由 `agent_telemetry` 生成、终态落库到 `chat_tasks.artifacts`，见 3.3。两者完全不同，严禁混用。

### 3.0 出口分流：三路（LLM / 前端 SSE / 落库 DB）

`data` 和 `llm_data` 都是 tool 出口的东西（由构建外壳与私有 builder 组装成一个 result 返回，函数族见 3.4）。出口之后**分成三路**，各自取不同的字段、走不同的函数——三路都要高准确度，不能串味：

```
tool 返回 {data, llm_data, other_data}
   │  observation_builder.build_observation 统一构建：
   │    · obs_text = build_observation_text(result) → format_llm_observation(data, llm_data)
   │    · tool_result[i] = {tool_name, llm_data, data_text=obs_text, raw_data=result["data"], other_data}
   │    · observation 帧 ed = {type:"observation", step, timestamp, content, content_items, tool_result}
   │
   ├─ 路 A：给 LLM 的 conv 信息（喂进对话历史）
   │     message_builder.add_tool_result(tc_id, obs_text, summary=_summary)
   │       · llm_data → _format_llm_data → "观察: <summary> / ✖错误 / ⚠警告 / diff"
   │       · data     → format_data_detail → "详情: <结果正文>"
   │       → LLM 的 tool 消息（data_text 是 LLM 与回放的唯一文本源）
   │
   ├─ 路 B：给前端的 SSE step 帧（工具行/结果展示）
   │     observation 帧 ed → format_agent_sse 下发 → 前端 sseParser 解析 step.tool_result
   │       · llm_data  → ToolResultRenderer 读 summary/detail/hint/duration_ms/metrics
   │       · raw_data  → = result["data"]，前端「结果」视图（ParamsPanel）
   │       · data_text → 前端折叠文本（字符串 tool_result 兜底）
   │       · other_data→ 编排层信号（attachment 生效；return_direct/warning 现状见 3.6）
   │
   └─ 路 C：落库 DB（历史回放 / 统计权威源）
         agent_runner._route_step_to_db → append_step
           → chat_task_steps.step_json 落**整个 step 帧 ed 原样**（完整不截断）
           · 包含 tool_result 数组（llm_data/data_text/raw_data/other_data 全在内）
           · 即历史回放唯一权威源；total_steps/final_stats.step_count 同源取自此处
         action 帧、observation 帧、thought/final 等所有业务步都落；_live_only 预览帧不落
```

**三路的字段对应（高准确对照）：**

| 出口字段 | 路 A（LLM conv） | 路 B（前端 step） | 路 C（落库 step_json） |
|---|---|---|---|
| `llm_data.summary` | "观察"行；另 stash 为 tool 消息 `_summary`（供 compaction） | ToolResultRenderer 结论区 | 原样存 `tool_result[i].llm_data.summary` |
| `llm_data.status.detail/hint` | "✖错误"/"⚠警告"行 | 详情/提示行 | 原样存 |
| `llm_data.duration_ms/metrics` | 进观察文本标签 | 结果区尾部小标签 | 原样存 |
| `data`（payload） | `format_data_detail(data)` → "详情"段 | `raw_data` → 前端「结果」视图（edit diff 在 `raw_data.diff`） | 原样存 `tool_result[i].raw_data` |
| `data_text`（格式化文本） | **LLM 与历史回放的唯一文本源** | 字符串 tool_result 兜底折叠显示 | 原样存 `tool_result[i].data_text` |
| `other_data` | 编排层收集 attachment（return_direct/warning 现状见 3.6） | `tool_result[i].other_data` 原样下发 | 原样存 |

**路 C 与路 B 的关系**：落库（路 C）和前端 SSE（路 B）**同源**——都是 `build_observation` 产出的同一个 step 帧 `ed`：一路经 `format_agent_sse` 转发给前端，一路经 `_route_step_to_db` 原样写进 `chat_task_steps.step_json`。所以前端此刻看到的 step 和历史回放看到的 step 是同一份（仅 SSE 转发时会按 `hide_from_steps` 摘除隐藏工具，落库不摘）。**路 C 不是路 A/路 B 的综合，而是它们的共同源头。**

**关键区分（三路别串味）**：
- `data_text` 和 `raw_data` 不是一回事——`data_text` 是格式化可读字符串（LLM 文本源 + 落库回放源），`raw_data` 是原始 dict（前端结果视图）。**前端 raw 展示用 raw_data，绝不能拿它替换 data_text 喂 LLM**（原始 dict 直接填 tool message 会触发 LLM content 类型错误）。
- `summary` 只进 llm_data，不进 data——它是结论文字，不是执行产出。
- 三路共用同一个 `build_observation` 构建点：`obs_text` 一路进 LLM tool 消息（路A）、一路作 `data_text` 进前端 tool_result（路B）、一路随 step_json 落库供回放（路C）。
- 历史回放读的是 `step_json` 里的 `data_text`，不是重新 format——所以 `data_text` 是回放唯一文本源。

**非标准出口形态（与本地代码一致，工具编写者须知）**：上面三路分流描述的是"工具返回标准三字段"的正常路径。实际 `build_observation` 还会收到三类非标准 `result`，由外围机制（安全门禁 / 重试引擎 / 有界执行器）产生，**工具自身不构造、也不能假设只会走标准路径**：

- **`result` 为 `Exception`**：工具执行抛异常，`build_observation` 走异常分支生成 `Observation: 工具X执行异常...`，不读 data/llm_data（`observation_builder.py:110-112`）；
- **`result is None`**：全工具被安全拦截、`results` 缺失该 call 的结果，`build_observation` 合成占位 `{"llm_data": {"status": {"exec_code": "error"}, "summary": "已安全拦截：X"}, "other_data": {"synthetic": True}}`（`observation_builder.py:107-109`），使 ObservationStep 必然发出；
- **`llm_data.status` 为 `str` 等畸形**：`build_observation` 用 `isinstance` 防御，避免 `.get` 抛 `AttributeError` 炸掉整轮观察（`observation_builder.py:116-119`）。

证据：`observation_builder.build_observation`（L80-194）、`observation_formatter.build_observation_text/format_llm_observation`、`agent_runner._route_step_to_db`（L552-586）、`storage.append_step`（step_json 完整落库，storage.py L58/311/358）、`sseParser.ts` observation 分支（L995-1013）、`ToolResultRenderer/index.tsx`。

### 3.1 `data` = tool 执行结果的输出（不是入参回显）

`data` 装**工具执行结果的输出数据**，供前端「浮层参数 → 结果」视图（`raw_data`）与 LLM 观察的「详情」段消费：

| 工具 | `data` 内容 |
|---|---|
| `read_text_file` | `_data`（读到的文件内容、行号、truncated 标记） |
| `read_media_file` | `{file_name, mime_type, base64_data}` |
| `query_sql` | `{rows, columns}` |
| `search_web` | `{items: results}` |
| `write_text_file` | `{content_preview}` |
| `schedule` | `{rows: [[content, status], ...]}` |
| `question` | `{answers, questions}` |

**禁止**把入参（prompt/path/sql/model 等）回显进 `data`——那是 `llm_data.action.params` 的职责。证据：`read_text_file` 的 data 是文件内容，不是 `{path, offset}`。

失败且无产出时 `data={}`（如 `query_sql` / `search_web` 的错误分支）。

### 3.2 `llm_data` = 结论 + 状态 + 元信息

**规范的是 `llm_data` 的字段结构，不是构造方式。** 所有工具的 `llm_data` 都长下面这个结构（raw dict）：

> 构造方式：**一律用模块级 `_build_<tool>_llm_data(...)` 三态复用**。三态字段大量相同，内联会重复三遍，DRY 要求抽 builder。所有工具共用的 `build_success/error/warning` 只负责包三字段外壳（data/llm_data/other_data），llm_data 的具体字段由私有 builder 统一构造——这是规范做法，照好的工具学。

```python
{
    "summary": "<tool_zh><target>，<成功/失败/警告>：<结果>",
    "action": {
        "tool": "<注册名>",
        "tool_zh": "<中文名>",
        "params": {<本次入参>},   # 可选：入参有意义的工具带（question/search/file 类带；schedule 已删）
    },
    "status": {
        "exec_code": "success|warning|error",
        "message": "成功|完成但有警告|失败",
        "code": "<错误码常量，成功为空串>",
        "detail": "<具体原因，成功为空串>",
        "hint": "<用户下一步建议，成功为空串>",
    },
    "duration_ms": <毫秒整数>,
    "metrics": {<关键计数/量，供 summary 与前端标签>},
}
```

#### 3.2.1 字段逐项要求

| 字段 | 规范 |
|---|---|
| `summary` | 动词用 `tool_zh`；统一口径 `{tool_zh}{target}，{成功/失败/警告}：{结果}`；**答案真值唯一出口**；长内容折行不截断 |
| `action.tool` | 注册的英文工具名（如 `write`/`read`/`query_sql`） |
| `action.tool_zh` | 中文名（如 `写文件`/`读文件`/`查询SQL`），前后端只展示、不参与逻辑判等 |
| `action.params` | 本次入参快照；键用原始参数名，只放非空值。入参无展示价值的工具可不放（如 `schedule`） |
| `status.exec_code` | 三态之一；驱动 `is_success/is_error` 与前端状态水滴图标 |
| `status.message` | 严格用状态词：`成功` / `完成但有警告` / `失败`；不得写长句 |
| `status.code` | 失败/警告填错误码常量，成功填空串 `""` |
| `status.detail` | 失败/警告的具体原因（写进前端「✖错误」「⚠警告」行）；成功填空串 |
| `status.hint` | 给 LLM/用户的下一步可执行建议；成功填空串 |
| `duration_ms` | 整数毫秒，三态都要 |
| `metrics` | 关键量（行数/字节数/条数/model）的 `{value, text}` 或直接数值；无量时空 `{}` |

证据：`_build_write_text_file_llm_data`/`_build_query_sql_llm_data`/`_build_search_web_llm_data`/`_build_question_llm_data`/`_build_schedule_llm_data` 都用私有 builder 三态复用，字段结构完全一致——这是要照着学的规范做法。

**错误码来源（与代码一致）**：`status.code` 统一取 `app/tools/tool_constants.py` 的 `ERR_*` 常量（按 file / shell / network / desktop / document / dataanalysis / system / win_registry 等域分组，100+ 个，如 `ERR_FILE_WRITE_FAILED`、`ERR_PARAMETER_INVALID`、`ERR_PARAMETER_EMPTY`、`ERR_MISSING_DEPENDENCY`），**禁止自造字符串错误码**。

**同名不同层陷阱（与代码一致）**：`action` 键在 `data` 与 `llm_data` 两层语义不同——`llm_data.action` 是 LLM 展示目标（tool/tool_zh/params），`data` 若也出现 `action` 则是工具自带快照；前端 raw 视图读 `data`、LLM 观察读 `llm_data.action`，取值勿混（`tool_response.py:49/66/83` 注释，2026-10-04 小欧）。

### 3.3 tool 执行结果的输出（data）与任务产出物（artifacts）是两个概念

这是最容易搞错的地方（data/llm_data 区别见本章开头总纲表）。**"tool 执行结果的输出"和"任务产出物"是完全不同的两件事，严禁混淆。**

#### 3.3.1 tool 执行结果的输出 → 放 `data`

工具这一次调用实际算出来/读出来/生成出来的东西：**文件内容、查询 rows、搜索 items、生成结果的 URL/路径**。它是 tool 执行结果的输出，属于 `data`，和文件内容、rows 同口径。生成图片/视频成功后 `data={"url": ..., "type": "image"}`、`data={"file_path": ..., "attachment_id": ...}` 就是对的——**这是 tool 执行结果的输出，不是"产出物"，放 data**。

#### 3.3.2 任务产出物（artifacts）→ 另一个模块生成，终态落库

"产出物（artifacts）"是**任务级**概念：一个任务跑完，它到底产出了哪些文件/图片/视频的清单。它**不是 tool 返回体直接给的**，而是由 `agent_telemetry` 模块在任务运行中逐步生成、终态落库的：

| 环节 | 函数/位置 | 时机 |
|---|---|---|
| tool 声明 | 产出型工具在 `other_data` 里声明：`declare_artifact_file({}, path)`（本地单个）/ `declare_artifacts(other, items)`（多条目）/ `artifact_from_url(url, kind)`（公网 URL 造条目） | 每次 tool **成功或警告**（`exec_code ∈ {success, warning}`） |
| 遥测收集 | `agent_telemetry.collect_and_report` → `read_declared_artifacts`（读 `other_data["artifacts"]`）→ 拷贝条目注入 `tool_name` → `merge_artifacts` 合入 `telemetry._artifacts` | 每批工具执行后 |
| 终态落库 | `agent_runner` 终态 `db_ops.update_task(..., artifacts=telemetry._artifacts)` → `chat_tasks.artifacts` | 任务结束时 |
| 前端呈现 | `list_session_task_artifacts` 读 `chat_tasks.artifacts` → 会话「产出物」抽屉 | 前端打开抽屉时 |

所以产出物的**真源是 `chat_tasks.artifacts`**，由 `agent_telemetry` 生成、`agent_runner` 落库——是独立于单次 tool 返回的一整条链路。`other_data["artifacts"]` 只是这条链路的**输入声明**（tool 告诉遥测"我产出了什么"），不是产出物本身。

**产物声明契约（唯一实现 `app/utils/artifacts.py`，2026-11-21 起）**：

条目固定五字段，任何模块不得自行解释或另造字段：

| 字段 | 含义 | 来源 |
|---|---|---|
| `tool_name` | 产出工具名 | **收集器注入**（拷贝条目，不改写工具返回体里的原条目） |
| `name` | 展示名 | 本地取 `basename`；目录取目录名；URL 取末段文件名（签名查询串不进名字） |
| `path` | 资源地址 | 本地绝对路径 或 `http(s)` URL，**唯一地址字段** |
| `form` | 形态 | `file` / `dir` / `url`，**唯一形态字段**；前端只按它分派，不自行猜 |
| `type` | 展示类型 | 扩展名（小写无点）/ `dir` / 媒体类别 / `file` / `url` |

**声明入口（工具侧只用这三个，不要手搓条目 dict）**：

| 函数 | 角色 | 用法 |
|---|---|---|
| `declare_artifact_file(other_data, path)` | **单文件便捷入口**，内部走 `artifact_from_file` 判形态（目录自动 `form="dir"`） | 写文件/下载/压缩/解压/截图/改文件等约 15 个工具 |
| `declare_artifacts(other_data, items)` | **基座入口**，追加语义（`merge_artifacts` 去重+上限），不改入参 | 多条目清单、或配合 `artifact_from_url` 声明公网产物 |
| `artifact_from_url(url, kind)` | **条目构造器**，只返回条目、不挂载（`form="url"`，`type` 取 URL 后缀，认不出用 `kind`） | `generate_image` / `generate_video` 的公网产物 |

调用形态（唯一写法，与 `data` 分开给）：

```python
return build_success(
    data={"file_path": str(path)},
    llm_data=llm_data,
    other_data=declare_artifact_file({}, str(path)),
)
```

**为什么挂在 `other_data` 而不是 `llm_data.action`**：`action` 是动作描述（`tool`/`tool_zh`/`params`），往里面塞清单属职责混用（SRP）。产物声明是编排层信号，与 `attachment` 同层。

**为什么必须有 `form`**：只有 `path` 时下游无法判断它是文件、目录还是远程 URL——把 URL 当本地文件 `isfile()` 判会恒"已不存在"，把解压目录当文件判同样恒失效，前端也没法决定点击该开外链、进目录树还是加入本轮。

**去重与上限**：去重键统一由 `artifact_dedup_key` 给（URL 去 query/fragment——换签名参数仍是同一资源；本地 `normcase(abspath)`——Windows 大小写不敏感、相对路径归一）。上限 50 条，超限**丢最早、保留最新**并告警（长任务末尾产出的文件才是用户最关心的）。

**收集条件**：只有 `exec_code ∈ {success, warning}` 才收集。失败态即便工具误声明了产物也不进清单——没交付就不算产出。

#### 3.3.3 两者关系

- `data` 里的 tool 执行结果输出 = 本次调用的真实 payload（前端结果视图/LLM 详情读它）
- 任务产出物 artifacts = 跨 tool、跨轮次累加的任务级清单（遥测生成、终态落库、产物抽屉读它）

不要因为 gen 工具同时填了 `data={"url":...}` 和 `other_data.artifacts=[{path:url}]` 就以为"同一个东西放两处"——前者是这次 tool 的执行结果输出给 LLM/前端看，后者是向遥测申报一个任务产出物供终态汇总，用途和生命周期都不同。

两者的一致性靠契约保证：`data` 里的结果输出是给人/LLM 看的文本与指针，`other_data.artifacts` 是给编排层的结构化清单，字段口径统一由 `app/utils/artifacts.py` 裁定。

### 3.4 出口相关函数族（tool_response.py 真实源码）

前面 3.1~3.3 讲清了 data/llm_data 字段规则和产出物概念。**注意：工具出口函数不止 3 个 `build_*`**——`tool_response.py` 实际提供按职责分组的函数族，工具编写会用到其中的构建外壳、缺库错误体、状态判定、产物声明，外加工具自己的私有 builder：

| 组 | 函数 | 职责 |
|---|---|---|
| 构建外壳 | `build_success` / `build_error` / `build_warning`（L44/61/78） | 包 `{data, llm_data, other_data}` 三字段外壳 |
| 缺库错误体 | `build_missing_dep_error`（L95） | 缺依赖统一错误体，由 `tool_executor._missing_dep_guard` 调用 |
| 状态判定 | `is_success` / `is_warning` / `is_error`（L174/179/184） | 从 `llm_data.status.exec_code` 判态，编排层消费 |
| 产物声明 | `app/utils/artifacts.py` 的 `declare_artifact_file` / `declare_artifacts` / `artifact_from_url` | 声明产出物到 `other_data["artifacts"]`（**已迁出 `tool_response.py`**），详见 3.3.2 |
| 私有 builder | `_build_<tool>_llm_data`（各工具） | 造 `llm_data` 字段，见 3.4.2 |

#### 3.4.1 三个构建函数（tool_response.py，三者同构，只有默认 exec_code 不同）

```python
_RESERVED_TOP_KEYS: set = {"data", "llm_data", "other_data"}

def build_success(data: Any = None, llm_data: Optional[Dict] = None,
                  other_data: Optional[Dict] = None, **extra) -> Dict[str, Any]:
    """构建成功响应"""
    if llm_data is None:
        llm_data = {"status": {"exec_code": "success"}}
    result: Dict[str, Any] = {
        "data": data,
        "llm_data": llm_data,
        "other_data": other_data or {},
    }
    for k, v in extra.items():
        if k not in _RESERVED_TOP_KEYS:
            result[k] = v
    return result

def build_error(data: Any = None, llm_data: Optional[Dict] = None,
                other_data: Optional[Dict] = None, **extra) -> Dict[str, Any]:
    """构建错误响应"""
    if llm_data is None:
        llm_data = {"status": {"exec_code": "error"}}
    result: Dict[str, Any] = {
        "data": data,
        "llm_data": llm_data,
        "other_data": other_data or {},
    }
    for k, v in extra.items():
        if k not in _RESERVED_TOP_KEYS:
            result[k] = v
    return result

def build_warning(data: Any = None, llm_data: Optional[Dict] = None,
                  other_data: Optional[Dict] = None, **extra) -> Dict[str, Any]:
    """构建警告响应"""
    if llm_data is None:
        llm_data = {"status": {"exec_code": "warning"}}
    result: Dict[str, Any] = {
        "data": data,
        "llm_data": llm_data,
        "other_data": other_data or {},
    }
    for k, v in extra.items():
        if k not in _RESERVED_TOP_KEYS:
            result[k] = v
    return result
```

三者都返回 `{"data", "llm_data", "other_data"}` 三字段外壳，禁止顶层塞自定义字段（`**extra` 工具层不使用）。

#### 3.4.2 私有 builder（工具自造 llm_data，范本）

真实范本 `write_text_file._build_write_text_file_llm_data`（error/warning/success 三态齐全），新工具的 `_build_<tool>_llm_data` 照此结构写：

```python
def _build_write_text_file_llm_data(
    exec_code: str, duration_ms: int,
    file_path: str = "", bytes_written: int = 0, detail: str = "",
    hint: str = "", mtime_warning: str = "",
    user_encoding: Optional[str] = None, user_append: Optional[bool] = None,
) -> Dict[str, Any]:
    """write_text_file的llm_data构建函数 — 三态复用"""
    _act_params = {"path": file_path}
    if user_encoding:
        _act_params["encoding"] = user_encoding
    if user_append is not None:
        _act_params["append"] = user_append
    if exec_code == "error":
        return {
            "summary": f"写文件{file_path}，失败",
            "action": {"tool": "write", "tool_zh": "写文件", "params": _act_params},
            "status": {"exec_code": "error", "message": "失败", "code": ERR_FILE_WRITE_FAILED,
                       "detail": detail, "hint": hint if hint else "请检查路径和写入权限"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    if exec_code == "warning" or bool(mtime_warning):
        if mtime_warning:
            hint = ("；".join([hint, mtime_warning]) if hint else mtime_warning)
        return {
            "summary": f"写文件{file_path}，成功",
            "action": {"tool": "write", "tool_zh": "写文件", "params": _act_params},
            "status": {"exec_code": "warning", "message": f"写入成功但有警告：{detail or mtime_warning}",
                       "code": "", "detail": detail or mtime_warning, "hint": hint or "请确认编码是否正确"},
            "duration_ms": duration_ms,
            "metrics": {"bytes_written": {"value": bytes_written, "text": f"{bytes_written}字节"}},
        }
    return {
        "summary": f"写文件{file_path}，成功",
        "action": {"tool": "write", "tool_zh": "写文件", "params": _act_params},
        "status": {"exec_code": "success", "message": "成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {"bytes_written": {"value": bytes_written, "text": f"{bytes_written}字节"}},
    }
```

构建外壳与私有 builder 的关系：`build_*` 包外壳（data/llm_data/other_data），`_build_<tool>_llm_data` 造 llm_data 内容（字段规则见 3.1/3.2），主函数把两者组合后返回——调用方式见 3.5。其余三组函数见 3.4.3~3.4.5。

#### 3.4.3 缺库错误体 `build_missing_dep_error`

工具缺依赖时**不要自己写"请安装 xxx"文案**，统一由 `tool_executor._missing_dep_guard`（`tool_executor.py:107/204/212/229`）在系统自动装库仍失败时调用 `build_missing_dep_error(tool_name, missing_deps)`（`tool_response.py:95`）。它按"系统装不上 → LLM 用 bash 自装 → 转管理员"三级给可执行出路，锁定依赖（httpx/httpcore 等）不给自装指示，错误码落 `ERR_MISSING_DEPENDENCY`。该函数由引擎调用，不属于工具出口的计时范围。

#### 3.4.4 状态判定 `is_success` / `is_warning` / `is_error`

编排层/工具用它们从 `llm_data.status.exec_code` 判态（`tool_response.py:174/179/184`）：`is_success` 认 `success`+`warning`；`is_warning` 仅认 `warning`；`is_error` 认 `error`，且对畸形结果（无 `llm_data`）视为错误。工具自身一般不需要调，但改写/复用工具结果时要按此口径判。

#### 3.4.5 产物声明三函数（已迁出本文件）

`declare_artifact_file` / `declare_artifacts` / `artifact_from_url` 现住在 `app/utils/artifacts.py`（2026-11-21 迁出），职责、字段契约与调用形态见 3.3.2，此处不重复。原 `tool_response.py` 的 `with_artifacts` / `with_artifact_file` / `artifact_from_url` / `extract_ext` 与 `_ARTIFACT_SUFFIXES` 已删除，**不留兼容别名**（禁 backward）。

### 3.5 主函数怎么用这些出口函数

出口函数族源码见 3.4（`build_*` 包外壳、`_build_<tool>_llm_data` 造 llm_data）。工具主函数里三态出口照这样调用它们：

```python
if <前置校验失败>:
    return build_error(data={}, llm_data=_build_<tool>_llm_data("error", duration_ms, ..., detail=..., hint=...))
try:
    result = <执行>
except <预期异常>:
    return build_error(data={}, llm_data=_build_<tool>_llm_data("error", ..., code=..., detail=..., hint=...))
if <结果需警告>:
    return build_warning(data=<部分产出>, llm_data=_build_<tool>_llm_data("warning", ..., detail=..., hint=...))
return build_success(data=<执行结果的输出>, llm_data=_build_<tool>_llm_data("success", ...))
```

要点：
- **三态都用对应的 `build_success/error/warning`**；llm_data 一律经私有 builder 三态复用（DRY），不在调用处内联重复拼；
- **失败原因只在 `status.detail` + `summary` 出现**，不在 `data` 重复；
- 异常分支要给 `hint` 可执行出路，不让 ReAct 循环停摆；
- 大 payload（如媒体 base64）放 `data`，由 `observation_formatter` 受控截断/前端隐藏键处理，不塞进 `summary`。

### 3.6 `other_data` 契约（如实记录现状，与本地代码逐项核对）

`other_data` 是第三个顶层字段。**当前实际有 8 个键，状态参差**，新工具务必只使用"有明确消费方"的键，不要凭想象往 other_data 塞编排无关内容。逐键现状（2026-11-21 核对）：

| 键 | 写入者（证据） | 消费方（证据） | 状态 |
|---|---|---|---|
| `attachment` | `fetch_webpage.py:606`（抓图片/PDF 的 base64 媒体，`_build_media_result`） | `observation_builder.py:181` → `orchestration["attachments"]` → `attachment_wire`（原生多模态投喂/降级） | ✅ 生效 |
| `usage` | `generate_image` / `generate_video`（值来自 `vendor_spec.py:136` 的 token 用量） | 落库/遥测，不进 LLM | ✅ 生效 |
| `artifacts` | 产出型工具经 `app/utils/artifacts.py` 的 `declare_artifact_file` / `declare_artifacts` 声明（五字段条目，见 3.3.2） | `agent_telemetry.collect_and_report` → `read_declared_artifacts` → `merge_artifacts` → 终态 `chat_tasks.artifacts` → 产物抽屉 | ✅ 生效 |
| `retry_count` | 重试引擎 `tool_retry_engine.py:354/464/509/770` | 前端 `sseParser.ts:606/624` 读的是 `stats`/`final_stats` 帧的 `retry_count`，**不是** `tool_result.other_data.retry_count` | ⚠️ tool_result 侧仅落库，前端另走统计帧 |
| `synthetic` | `observation_builder.py:109`（安全拦截合成占位） | **无任何消费者**（前端 `synthetic` 0 处、后端无读取） | ❌ 只写不读 |
| `return_direct` | **无工具写入**（tools 目录 grep = 0） | `observation_builder.py:176` 读 | ❌ 死读取（工具侧已无人写） |
| `warning` | **无工具写进 other_data**（`line_pager.py:109` 的 `result["warning"]` 是业务 data，不是 other_data） | `observation_builder.py:183` 读 | ❌ 死读取 |
| `category` | **无工具写**（`tool_error_classifier.py:181` 是诊断 dict，非 other_data） | `tool_retry_engine.py:705` 可选读 | ⚠️ 无人写，读取待用 |

**结论**：真正在跑的只有 `attachment`（`fetch_webpage` 抓媒体）、`usage`（生成类 token）与 `artifacts`（产出物声明，五字段契约）；`synthetic` / `return_direct` / `warning` / `category` 是机制退役后未清理的残留。新工具**只应使用 `attachment` / `usage` / `artifacts` 这类有明确消费方的键**；历史残留的清理需单独立项，不在工具编写层擅动。

---

## 四、下游消费对照（为什么必须这样）

| 下游 | 读什么 | 不这样组装的后果 |
|---|---|---|
| LLM 观察文本 `observation_formatter.format_llm_observation(data, llm_data)` | `llm_data` → 观察行；`data` → 详情行 | summary 缺答案真值 → LLM 看不到结果；data 放入参 → 详情段重复噪声 |
| 前端工具行 `ToolCallLine` | `action.tools[].tool/params`、`content`、状态水滴读 `llm_data.status.exec_code` | 状态字段缺 → 水滴不显示状态；params 缺 → 浮层参数空 |
| 前端结果区 `ToolResultRenderer` | `tool_result[i].llm_data.summary/detail/hint/duration_ms/metrics` | 字段缺 → 结果区空白 |
| 落库/历史回放 `agent_runner._route_step_to_db` → `append_step` | 整个 step 帧 `ed`（含 `tool_result[i].data_text/raw_data/llm_data`）原样写 `chat_task_steps.step_json` | step 帧字段缺 → 历史回放内容丢失；`data_text` 缺 → 回放空白 |
| 产出物链路 `agent_telemetry.collect_and_report` → `update_task` | `other_data["artifacts"]`（五字段）→ `telemetry._artifacts` → `final_stats.artifacts` → `chat_tasks.artifacts` | 声明缺 → 产出物抽屉看不到该产出物；缺 `form` → 远程产物/目录被当本地文件判失效 |

---

## 五、自查清单（写工具/改工具后逐项核对）

- [ ] `async def` 或 `def`（按工具性质选，纯阻塞工具保持 `def`，见 2.1）+ 完整类型注解 + `-> Dict[str, Any]`
- [ ] 入口第一行 `t0`，所有出口 `duration_ms` 按实际耗时计算，不得硬编码 `0`（见 2.2）
- [ ] 出口只用 `build_success/error/warning`，顶层仅三字段；缺库走 `build_missing_dep_error`，不自造"请安装 xxx"
- [ ] `data` 是 tool 执行结果的输出，**无入参回显**
- [ ] `data.action` 与 `llm_data.action` 严格区分（同名不同层，见 3.2）
- [ ] `llm_data` 字段结构齐全（summary/action/status 五字段/duration_ms/metrics）；经私有 builder 三态复用构造
- [ ] `summary` 用 `{tool_zh}，{状态}：{结果}` 口径
- [ ] `action` 有 tool/tool_zh，入参有意义时带 params
- [ ] `status` 五字段齐全（exec_code/message/code/detail/hint）；`code` 复用 `tool_constants.ERR_*` 常量，不自造字符串
- [ ] `duration_ms` 三态都有；`metrics` 无量时为 `{}`
- [ ] tool 执行结果的输出放 `data`（url/路径/字节）；产出型工具用 `declare_artifact_file` / `declare_artifacts` / `artifact_from_url` 声明到 `other_data["artifacts"]`（五字段契约，产物声明 ≠ data 结果输出，别混）
- [ ] `other_data` 只放有明确消费方的键（当前 `attachment`/`usage`），不塞编排无关内容（见 3.6）
- [ ] `hide_from_steps` 仅 `schedule`/`question` 声明；普通工具默认可见
- [ ] 失败原因只在 status.detail + summary，不在 data 重复
- [ ] 异常分支给 hint 出路

---

## 六、反面案例（本次生成工具整改实录）

生成工具曾出现三处违规，按本规范对照如下：

| 违规点 | 错误做法 | 正确做法（本规范） |
|---|---|---|
| `data` 放入参回显 | `data={prompt, model, mode}` | `data={url, type}`（执行结果的输出）；入参进 `action.params` |
| `status` 字段不全 | 只有 `{exec_code, message}` | 五字段齐全，补 `code/detail/hint` |
| 缺 `metrics` | 无 | `metrics={model: ...}` 或 `{}` |

三处均已按本规范整改（`generate_image.py` / `generate_video.py`，抽 `_build_image_llm_data` / `_build_video_llm_data` 统一构造）。

---

**（本规范总结自 write/read_text_file/read_media_file/query_sql/search_web/question/schedule 七个代表工具的实际代码，这七个都用私有 builder 三态复用——照好的学；新增工具一律按此字段结构 + builder 构造执行，与规范不符的既有工具按此收敛。）**
