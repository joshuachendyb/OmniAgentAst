# observation 工具结果显示问题 —— 深度分析与优化方案

**文档编号**：`doc-10月优化/[8]`
**创建时间**：2026-10-04 11:53:48
**更新时间**：2026-10-04 13:06:01
**编写人**：小欧
**版本**：v1.4

## 版本历史

| 版本 | 更新时间 | 更新人 | 修改简介 |
|------|----------|--------|----------|
| v1.0 | 2026-10-04 11:53:48 | 小欧 | 首版。基于生产库 1418 帧 observation / 2306 条工具子行实测取证，输出 6 项确认缺陷、根因结论与优化方案 |
| v1.1 | 2026-10-04 11:57:17 | 小欧 | 北京老陈指令：在第四章头部补充 observation SSE 事件字段清单（字段含义 + 前端是否消费）。原 4.1~4.4 顺延为 4.2~4.5 |
| v1.2 | 2026-10-04 12:26:40 | 小欧 | 北京老陈指令：补充两节 + 更正一处失准。**新增 4.1.6**（SSE 帧 vs conversation history 字段差异对照，含"format 前/后"结论与两条注入路径）、**4.1.7**（`data_text` 两段拼接结构——llm_data 段 + data 段双向耦合，揭示 P0 类缺陷总根因）、**4.1.8**（`_summary` stash 空转：判定为非缺陷，列接线前置待办）；新增 P2-11。**失准更正**：`llm_data_text` 由"全仓零消费"改为"前端零消费 + 后端 `history_loader.py:53/139` 有兜底消费（实测不可达）"，§4.1.5 零消费计数由 8/40% 修正为 7/35% |
| v1.3 | 2026-10-04 12:39:58 | 小欧 | 北京老陈指令："分析好了，有多余的就可以去掉的，要在设计文档中设计说明好了"。**新增第九章「observation 字段精简设计」**（原九/十顺延为十/十一）：9.1 删字段三条判据、9.2 `llm_data` 整删可行性前置核实（telemetry/formatter 均读原始 `result`，与下发副本解耦）、9.3 甲乙丙丁四类逐字段裁决表、9.4 体积收益（**删 3,973,267 字符 = 25.60%**）、9.5 目标契约（~~20 字段 → 12 字段~~，见 v1.4 更正）、9.6 逐文件改动清单（后端 3 + 前端 5 + 测试 5，含铁规澄清）、9.7 附带发现 `chat.ts` 旧契约死类型（违反禁止 backward）、9.8 历史数据兼容论证（只删字段不改语义 → 回放不退化）、9.9 规范逐条判定、9.10 风险与回归防护 |
| v1.4 | 2026-10-04 13:06:01 | 小欧 | **算术更正**：9.5 字段数 "20 → 12" 更正为 **18 → 10**（按一级字段口径 4+3+3=10）。原 20 的口径把 `status` 5 个子键逐个计入却漏计 `truncated`/`truncated_reason`，两处误差方向相反。另补记 link 模式装历史的三层发现（`context_link_mode` 不被读 / independent 靠空区间巧合实现 / 实际装入仅 1~3 轮）——详见 §4.1.9 |

---

## 一、报告背景与目标

### 1.1 背景

北京老陈 2026-10-04 指令：读取前端 step 页面的 observation 工具显示，要求**深入仔细研究、深入全面分析，不能走马观花**。

### 1.2 本报告的取证原则

本报告**不采信代码注释、不采信设计文档、不采信既有测试断言**，所有结论以下列三条独立证据链交叉验证：

1. **源码通读**：前端渲染链 + 后端构造链逐文件读取；
2. **生产数据实测**：直接读取 `~/.omniagent/chat_history.db` 的 `chat_task_steps` 表，取真实 `observation` 帧统计；
3. **逻辑重放**：用 Python 1:1 复刻前端渲染管线（`sseParser` → `ToolCallLine` → `resolveResultType` → `shapeRenderers`），喂真实数据，观测实际渲染分支。

### 1.3 目标输出

- 精确定位 observation 工具结果显示的全部缺陷；
- 给出每项缺陷的**量化影响面**与**根因链**；
- 给出优化方向与待裁定事项。

---

## 二、数据链路全景（后端 → 像素）

```
observation_builder.py:128-134
    tool_result[i] = {tool_name, llm_data, llm_data_text, data_text, other_data}   ← 仅 5 键
        ↓ SSE
sseParser.ts:855-921
    只取 tr[0] → 合成 execution_result{data,llm_data,other_data} / tool_name / summary / content
        ↓
PipelineRenderer.tsx:402-443
    按 step 号相等配对 action ↔ observation
        ↓
ToolCallLine.tsx:129-135
    observations.flatMap(...) 收集全部 tool_result
ToolCallLine.tsx:154-178
    getResultForIndex(idx)：按 tool_name find() 首个命中，兜底 results[idx]
ToolCallLine.tsx:181-207
    getResultSummary / getResultStatus
ToolCallLine.tsx:296-300
    singleStep = { ...obsStep, tool_result: [r] }        ← 未覆盖 tool_name（缺陷 P0-4 根因）
        ↓
resultTypes.ts:24-27
    resolveResultType(singleStep) → tree / code / generic
        ↓
shapeRenderers.tsx:40-77 extractResult
    JSON.parse(data_text) → data.*
shapeRenderers.tsx:251/403/498
    TreeResultRenderer / CodeResultRenderer / DefaultResultRenderer
```

### 2.1 链路关键事实

**`data_text` 不是业务数据，是喂给 LLM 的格式化展示文本。**

后端 `observation_builder.py:89` → `observation_formatter.build_observation_text()`，输出形如：

```
工具执行: 读取 调用工具-read,处理对象-E:\test_dir\ai.html - 执行结果: 成功
观察: 读取成功: 第1-60行,共3081行,1348212字节 - 读取成功: 60/3081行
详情:
── 文件内容 ── E:\test_dir\ai.html
   1  <!DOCTYPE html>
   2  ...
```

而**前端全链路都假设它是 JSON**。

### 2.2 生产库实测（`chat_task_steps`，2026-10-04 11:53 取数）

| 指标 | 数值 |
|------|------|
| observation 帧总数 | 1418 |
| ├ 单工具帧 | 889 |
| └ 多工具帧 | 529 |
| 工具子行总数（Σ`tool_result` 长度） | **2306** |
| `tool_result[i]` 键集合 | **恒为 5 个**：`tool_name` / `llm_data` / `llm_data_text` / `data_text` / `other_data`（2306/2306 全部齐备，无一例外） |
| **`data_text` JSON 可解析率** | **0 / 2306（0.0%）** |

---

## 三、后端 observation 数据契约（实测确认）

### 3.1 `ObservationStep.to_dict()` 实际输出

| 键 | 类型 | 语义 |
|----|------|------|
| `type` | `str` = `"observation"` | 步骤类型 |
| `step` | `int` | LLM 调用轮次 |
| `timestamp` | `str` | 本地 ISO 8601 |
| `content` | `str` **恒为 `""`** | 已废弃，不承载观察文本 |
| `tool_result` | `List[Dict]` **条件性** | 空列表时该键整个省略 |

**顶层不存在**：`llm_data` / `other_data` / `tool_name` / `tool_params` / `observation` / `summary`。
（2026-08-18 契约调整时已从顶层删除，只保留在 `tool_result[i]` 内）

### 3.2 `tool_result[i]` 结构（`observation_builder.py:128-134`）

| 键 | 类型 | 语义 |
|----|------|------|
| `tool_name` | `str` | 工具注册名（经 `_auto_correct_file_tool` 自动纠正） |
| `llm_data` | `dict`（可能 `{}`） | 结构化 LLM 观察：`summary` / `action` / `status` / `duration_ms` / `metrics` |
| `llm_data_text` | `str` | `json.dumps(llm_data, ensure_ascii=False, indent=2)`；`llm_data` 为空时为 `""`（`display_utils.py:101-118`） |
| `data_text` | `str` | **格式化展示文本原文**（见 2.1） |
| `other_data` | `dict`（可能 `{}`） | 旁路数据：`retry_count` / `attachment` / `category` / `return_direct` / `warning` / `synthetic` |

**关键缺失**：工具的**原始业务 `data` 完全不进 `tool_result`**。`tool_response.build_success(data=...)` 的 `data` 参数只经 formatter 转成 `data_text`（可能已截断），原始结构就地丢失（`observation_builder.py:122` 注释确认删除了 `_data` 死变量）。

### 3.3 `llm_data` 结构

```python
{
  "summary":    str,        # 中文短摘要，成品句
  "action":  {"tool","tool_zh","target","params","artifacts"?},
  "status":   {"exec_code","message","code","detail","hint"},
  "duration_ms": int,
  "metrics":  {<key>: {"value": <any>, "text": str}},   # ★ 注意：值是对象，不是数字
}
```

- `status.exec_code` 枚举**只有 3 值**：`success` / `error` / `warning`（全仓正则穷举确认）。
- `metrics` 生产库实测键频：`bytes`(437) / `exit_code`(433) / `total_lines`(433) / `lines`(428) / `results`(314) / `engine`(314) / `bytes_written`(299) / `total`(283) / `status_code`(111) / `file_count`(111) / `dir_count`(107) / `total_size`(107) …

### 3.4 并行配对依据

**后端保证索引严格对齐**：`tool_runner.py:123-130` 以 `results[_i] = _res` 按下标显式回填（`asyncio.gather` 完成顺序不影响），`observation_builder.py:76` 用 `zip_longest(ctx.all_calls, ctx.results)` 位置配对。

即 `tool_result[i] ↔ action.tools[i]` 恒成立。**配对问题纯在前端**（见 P0-3）。

---

## 四、前端渲染体系现状

### 4.1 observation SSE 事件字段清单与前端消费状态

> 本节数据来自 `ObservationStep.to_dict()`（`observation_step.py` + `base.py:80-88`）与 `observation_builder.py:128-134`，
> 消费状态由前端全仓 grep 逐点核实（2026-10-04 11:57）。
> **图例**：✅ 有真实读取点 ｜ ⚠️ 有读取代码但语义失效/路径不可达 ｜ ❌ 零消费（只写不读）

#### 4.1.1 顶层字段（5 个）

| 字段 | 类型 | 简要说明 | 前端是否使用 |
|------|------|----------|--------------|
| `type` | `str` = `"observation"` | 步骤类型标识 | ✅ `sseParser.ts:855` switch 分派；`PipelineRenderer.tsx:250` 建 obs 段 |
| `step` | `int` | LLM 调用轮次，**与同轮 `action` 的 `step` 相等** | ✅ `PipelineRenderer.tsx:406` 靠它配对 action ↔ observation |
| `timestamp` | `str` | 本地 ISO 8601 时间串 | ✅ `sseParser.ts:859` 归一为 number 赋 `step.timestamp` |
| `content` | `str` **恒为 `""`** | 2026-04 前的老字段，已废弃不承载文本 | ❌ 前端 3 处兜底读（`ToolCallLine.tsx:393/398`、`shapeRenderers.tsx:503`）**恒拿到空串** |
| `tool_result` | `List[Dict]` **条件性** | 本轮全部工具结果；**空列表时该键整个不下发** | ✅ `ToolCallLine.tsx:130` flatMap；`shapeRenderers.tsx:46/503` |

#### 4.1.2 `tool_result[i]` 字段（恒 5 个，2306/2306 实测齐备）

| 字段 | 类型 | 简要说明 | 前端是否使用 |
|------|------|----------|--------------|
| `tool_name` | `str` | 工具注册名（经自动纠正） | ✅ `ToolCallLine.tsx:157` 子行配对；`sseParser.ts:889` → `resolveResultType` 选渲染器 |
| `llm_data` | `dict` | 结构化 LLM 观察（见 4.1.3） | ✅ `ToolCallLine.tsx:164/184/199` 取 `summary` / `status` |
| `llm_data_text` | `str` | `llm_data` 的完整 JSON 副本（`indent=2`） | ⚠️ **前端零消费**；后端 `history_loader.py:53/139` 作 `data_text` 空值兜底回放（实测 `data_text` 非空率 100%，故该兜底实际永不触发）。详见 P2-9 |
| `data_text` | `str` | **喂 LLM 的格式化展示文本**（非 JSON） | ✅ `shapeRenderers.tsx:49` 尝试 `JSON.parse`（必失败）→ 兜底 `content`；`ToolCallLine.tsx:189` 摘要兜底 |
| `other_data` | `dict` | 旁路数据（`retry_count`/`attachment`/`category`/`return_direct`/`warning`/`synthetic`） | ❌ `sseParser.ts:887` 写入 `execution_result.other_data` 后**无人读取**；`return_direct` 派生出的 `step.return_direct` 亦**零消费** |

#### 4.1.3 `llm_data` 子字段

| 字段 | 类型 | 简要说明 | 前端是否使用 |
|------|------|----------|--------------|
| `summary` | `str` | 中文短摘要成品句，如"列出目录成功: 922项" | ✅ `ToolCallLine.tsx:188` 子行摘要首选；`sseParser.ts:894` 合成 `step.summary` |
| `action` | `dict` | `tool` / `tool_zh` / `target` / `params` / `artifacts?` | ❌ **零消费**（`tool_zh` 在前端 0 匹配；`artifacts` 的读取点全属 `final_stats` 帧，与本字段无关） |
| `status.exec_code` | `str` | 执行码，**枚举仅 3 值**：`success` / `error` / `warning` | ✅ `ToolCallLine.tsx:203` 判水滴图标颜色；`shapeRenderers.tsx:74` 判成功与否 |
| `status.message` | `str` | 人类可读结果描述 | ⚠️ `sseParser.ts:897` 赋给 `step.error_message`，但 observation 步骤的 `error_message` **无读取点**（现有读点全属 `final` / `error` 段） |
| `status.code` | `str` | 错误码常量（`ERR_*`） | ❌ 零消费 |
| `status.detail` | `str` | 错误细节 | ❌ 零消费 |
| `status.hint` | `str` | 处理建议 | ❌ 零消费 |
| `duration_ms` | `int` | 工具执行耗时 | ❌ 零消费 |
| `metrics` | `dict` | 指标集，**值为 `{value, text}` 对象** | ⚠️ `shapeRenderers.tsx:70-72` 有读取代码，但①仅 tree/code 路径调用（该路径实测 0% 可达）②按 `number` 使用，对象触发 `NaN` 比较 / `[object Object]` → **双重失效，见 P0-2** |

#### 4.1.4 前端自行合成的派生字段（非后端下发）

| 派生字段 | 来源 | 说明 | 前端是否使用 |
|----------|------|------|--------------|
| `execution_result` | `sseParser.ts:884` | `{data: {raw: data_text}, llm_data, other_data}` | ⚠️ 仅 tree/code 死路径读取；generic 路径被 `tool_result` 绕过 |
| `execution_status` | `sseParser.ts:895` | 取 `tr[0].status.exec_code` | ❌ observation 步骤零读取 |
| `summary` / `content` | `sseParser.ts:894/898` | 均取 `tr[0].llm_data.summary` | ⚠️ `content` 恒为摘要副本；`summary` 仅孤儿 obs 段读（`PipelineRenderer.tsx:458`） |
| `tool_name` | `sseParser.ts:889` | **只取 `tr[0]`** | ⚠️ 是 P0-4 错配根因 |
| `tool_params` | `sseParser.ts:890` | 读 `el.tool_params` —— **后端不下发该键** | ❌ 恒取到 `{}`，且无人消费 |
| `parallel_results` | `sseParser.ts:899` | 读 `rawData.parallel_results` —— **后端不下发** | ❌ 恒 `undefined` |
| `observation` | `sseParser.ts:911` | else 兜底分支读 `rawData.observation` —— **后端不下发** | ❌ 恒 `''` |

#### 4.1.5 字段消费统计

| 类别 | 数量 | 占比 |
|------|------|------|
| ✅ 有真实读取点 | 7 | 35% |
| ⚠️ 有读取代码但语义失效/路径不可达 | 5 | 25% |
| ❌ 零消费（只写不读 / 读不存在的键） | 7 | 35% |

**结论**：后端下发 20 个有效字段（顶层 5 + `tool_result[i]` 5 + `llm_data` 子字段 10），
前端**真实用上的仅 7 个**（`type` / `step` / `timestamp` / `tool_result` / `tool_name` / `llm_data.summary` / `llm_data.status.exec_code`），
其中最关键的 `data_text` 处于"被读取但前提错误"状态。
**40% 的字段对前端是纯负担**——`llm_data_text` 更是每条 observation 都携带一份完整 JSON 副本，前端只写不读。

#### 4.1.6 SSE 帧字段 vs conversation history 字段差异

> 本节核实于 2026-10-04 12:23。回答一个关键问题：**后端 observation 哪些字段真正喂给了 LLM？**

**先答"format 前还是 format 后"：格式化后。** 且 SSE 的 `data_text` 与 conversation history 的 `content`
是**同一个字符串变量**（`obs_text`），逐字相同、零差异。

**两条注入路径**：

```
路径1 实时（同进程同轮）
  observation_builder.py:89   obs_text = build_observation_text(...)      ← 格式化后
  observation_builder.py:113  add_tool_result(tc_id, obs_text)
  message_builder.py:186      ToolResultMessage(content=obs_text, tool_call_id=tc_id)
                              → conversation_history

路径2 回放（DB → 下一轮 LLM）
  history_loader.py:139       content = el.get("data_text") or el.get("llm_data_text") or ""
  history_loader.py:79        arguments = json.dumps(t.get("params"))     ← action.tools[i].params，未格式化
```

**字段差异对照**：

| 字段 | SSE observation 帧 | conversation history | 说明 |
|------|--------------------|---------------------|------|
| `type="observation"` | ✅ | ➡️ 变身为 `role="tool"` | 帧类型标记，LLM 不需要 |
| `step` | ✅ | ❌ | |
| `timestamp` | ✅ | ❌ | |
| `content` | ✅ 恒 `""` | ❌ | 空串，不进 |
| `tool_result[].tool_name` | ✅ | ❌ | LLM 靠 `data_text` 文本内的"调用工具-X"字样得知 |
| `tool_result[].llm_data` | ✅ 完整结构 | ❌ | **`summary` / `status` / `action` / `metrics` 全部不进** |
| `tool_result[].llm_data_text` | ✅ | ⚠️ 仅 `data_text` 为空时兜底 | 实测非空率 100%，兜底不可达 |
| `tool_result[].data_text` | ✅ | ✅ **唯一载体** | 与 SSE 逐字相同 |
| `tool_result[].other_data` | ✅ | ❌ | `return_direct`/`warning`/`attachment` 等编排信号不进 LLM |
| （action 帧）`tools[].params` | ✅ | ✅ | `tool_calls[].function.arguments`，**未格式化** |

**净结论**：

- **SSE 帧** = 面向**前端 + 落库**的完整结构（20 字段）
- **conversation history** = 面向 **LLM** 的极简二元组（格式化文本 + 工具入参）
- **`llm_data` 这套结构化数据 LLM 一次都看不到**，其信息已被 formatter 压平进 `data_text` 文本

**由此解释一个关键现象**：`llm_data.metrics`（行数/字节数/文件数）是结构化的，但 formatter 的"去掉统计"逻辑
（`observation_formatter.py:626`）已使其不进结构段 —— 故 LLM 看到的只有 `data_text` 里
"第1-60行,共3081行"这类**自然语言统计**，而非可计算的 `metrics` 字典。

#### 4.1.7 `data_text` 的两段拼接结构（llm_data 与 data 的耦合点）

**`data_text` = llm_data 段 + data 段，两者链在一起且双向耦合。**

`format_llm_observation(data, llm_data)`（`observation_formatter.py:695-734`）：

```
text = _format_llm_data(llm_data)              ← 第1段：llm_data 渲染（:712）
        ↓
if exec_code == "error":                        ← error 路径特殊（:719-725）
    if detail 为空 and data 非空:
        text += "\n错误详情:\n" + format_data_detail(data, llm_data)
    return text                                  ← 提前返回，不再出"详情:"段
if data:                                         ← success / warning 路径（:727-732）
    text += "\n详情:\n" + format_data_detail(data, llm_data)
else:
    text += "\n详情: 结果已在观察中完整说明"
```

**两处耦合事实**：

1. `format_data_detail(data, llm_data)` 的**第二参数就是 `llm_data`** —— "data 段"的渲染过程
   **也要读 `llm_data`**（用于 dispatch 判断工具类型、取 metrics）。故不只是前后拼接，是**互相依赖**。
2. llm_data 段内部再含 `status`（`exec_code`/`message`/`detail`/`hint`）+ `action`（`tool`/`tool_zh`/`target`）
   + `summary` + `llm_data["diff"]`（`:676-690`，行×列收口）。

**这正是 P0 类缺陷的总根因**：原始业务 `data` 在 formatter 内部就被**消费成文本**，
原始结构不落任何处 —— 前端 `sseParser.ts:877` 的 `JSON.parse(dataText)` 是**双重错误**：
既误判它是 JSON，又误以为它承载了分开的 `llm_data` / `data` 结构。

#### 4.1.8 `_summary` stash 空转（compaction 未接线）

| 项 | 事实 |
|----|------|
| 现象 | `add_tool_result(tool_call_id, content, summary="")` 的 `summary` 形参，**6 处调用点全部只传 2 个参数**（`observation_builder.py:46/50/113/117`、`fc_message_types.py:64`、`message_builder.py:258`） |
| 后果 | `_summary` 永不 stash → `compaction.use_tool_summary` 按其 docstring"无 `_summary` 时函数空转安全"**永远空转** |
| 是否 bug | **否** —— 与 compaction 未接线状态自洽 |
| 证据 | `use_tool_summary` / `clear_tool_outputs` / `keep_valuable_messages` / `compress_long_tool_output` 全仓搜索，**所有匹配均在 compaction 包内**（prune.py 定义处、`__init__.py` 桶导出、trigger.py / compaction_constants.py / message_builder.py 注释），**零生产调用方** |
| 设计自述 | `message_builder.py:19` 注释："因 `_pruned`/`_summary` 现为短下划线而非 `_temp_` 前缀（**compaction 模块落地备用后**这些标记留 bool/短名前缀）" |

**现在不补的理由**：补 `summary=_llm.get("summary")` 等于**为不存在的消费方写数据，违反 YAGNI**。

**接线时必须一并处理的前置待办**（本轮不动，仅记录）：

| # | 待办项 | 说明 |
|---|--------|------|
| 1 | `summary` 实参透传 | 6 处调用点**必须同时补**，否则出现"部分工具有 `_summary`、部分没有"的不一致 |
| 2 | `data` → `summary` 取值口径 | `observation_builder.py:90` 已算出 `_llm`，可直接取 `_llm.get("summary")`，无需重算（DRY） |
| 3 | 三处空转代码归属 | `summary` 形参 + `_summary` 分支 + `prepare_messages_for_llm` 的 `_COMPACTION_TEMP_KEYS` 剥离逻辑，均属 compaction 未接线的正常伴生物，**不应单独拆改**（拆了即违反"不拆已有设计"） |

---

### 4.2 形状分派

`resultTypes.ts:18-22` 仅 3 条映射：

```ts
const TOOL_RESULT_TYPE: Record<string, ResultType> = {
  listdir: 'tree',  tree: 'tree',  read: 'code',
};   // 未列者 → generic
```

### 4.3 三类渲染器

| 渲染器 | 取数 | 触发条件 |
|--------|------|----------|
| `TreeResultRenderer` | `data.entries`（分支A）/ `data.tree`（分支B），否则"目录为空" | `listdir` / `tree` |
| `CodeResultRenderer` | `data.content` | `read` |
| `DefaultResultRenderer` | `step.tool_result ?? step.execution_result ?? step.content` | 其余全部（81.6%） |

### 4.4 generic 路径实际渲染形态

`DefaultResultRenderer`（`shapeRenderers.tsx:503-510`）：`tool_result` 是数组 → `raw.data` 为 `undefined` → `?? raw` 回落 → `data` = **整个数组** → 交给 `GenericResultRenderer`：

```
└ 1px 左侧竖线块 (#e8e8e8)
  └ 长度 1 的数组 → 嵌套块 → 元素(5 键对象) → antd Descriptions column=1
      tool_name      bash
      llm_data       {summary / action{...} / status{...} / duration_ms / metrics{...}}   ← 递归嵌套 4 层
      llm_data_text  {"summary": "...", ...}    ← llm_data 的完整 JSON 副本，纯噪音
      data_text      工具执行: 执行 调用工具-bash...   ← 唯一有用，但被折叠成 2 行
      other_data     {}
```

即：**通用 observation 展示的是内部契约字段表，而非结果本身。**

### 4.5 两套折叠实现并存

| 组件 | 阈值 | 使用场景 | 交互 |
|------|------|----------|------|
| `CollapsibleText`（项目自研） | 5 行 / 200 字 | **仅字符串 `tool_result`** | 有 `stopPropagation` + Enter/Space 键盘 |
| antd `Paragraph ellipsis` | 100 字符 / 2 行 | 数组 `tool_result` 内的长字符串 | 无 `stopPropagation` |
## 4.6 保留清单：link 装配实际依赖 6 个字段，一个不删

逐行核对 `history_loader._parse_tool_calls`（`:40-105`）与 `_parse_observations`（`:127-165`）：

| # | 字段 | 装配处行号 | 作用 | 保留 |
|---|------|-----------|------|------|
| 1 | 顶层 `type` | `:45` / `:130` | 过滤 `== "observation"` | ✅ |
| 2 | 顶层 `step` | `:47` / `:132` | 合成 `tool_call_id` 第 2 段 | ✅ |
| 3 | `tool_result` | `:48` / `:133` | 结果数组载体 | ✅ |
| 4 | `tool_result[i]` 的**数组下标** | `:50` / `:136` | 合成 `tool_call_id` 第 3 段（**配对唯一依据**） | ✅ |
| 5 | `tool_result[].data_text` | `:53` / `:139` | **唯一内容载体**；`:53` 还用它判空建 `_obs_ids` | ✅ |
| 6 | `tool_result[].tool_name` | `:142` | 判 `== "truncated_output"`，决定是否跳过孤儿 | ✅ |
| 7 | 顶层 `content` | `:57` / `:154` | 老数据格式回退分支（实测 0/1418 帧走到，但**代码路径存在** → 按判据保留） | ✅ |

---

## 五、什么问题

1. `listdir` / `tree` 展开后显示"目录为空"
2. 统计数字显示不出来（要么不显示，要么显示 `[object Object]`）
3. 并行同名工具显示别人的结果
4. 展开的工具标题显示错（展开 bash 却显示"读取文件成功"）
5. 通用工具展示 5 行内部字段，看不到结果本身
6. 摘要硬截 60 字；无摘要时变成乱码片段
7. 5 个文件是死代码
8. 测试用假数据，掩盖了上面这些问题

---

## 六、要怎么解决

| # | 问题 | 怎么办 | 状态 |
|---|---|---|---|
**第 0 步先做**：删 `llm_data_text` 字段（零行为变化  后端修改和前端修改）。
| 1 | 目录显示"目录为空" | 删掉 `TreeResultRenderer`（它要的数据永远拿不到） | 已定 |
| 2 | 统计数字显示不出 | 同第 1 条，一起删掉；要正确统计就改用 `data_text` 里的文本 | 已定 |
| 3 | 同名工具串味 | **按数组下标配对**，不用工具名找 | 已定 |
| 4 | 标题显示错 | 删掉形状分派（和第 1 条一起做） | 已定 |
| 5 | 展示内部字段 | — | 本阶段不动，下一阶段再说 |
| 6 | 摘要乱码 | 去掉 `data_text` 兜底，摘要只用 `summary` | 本阶段不动，下一阶段再说  |
| 7 | 死代码 | 删 5 个零引用文件 | 已定 |
| 8 | 假数据测试 | 重写测试，用真实 `data_text` 形态 | 已定 |





**编写人**：小欧
**编写时间**：2026-10-04 11:53:48
**版本**：v1.0