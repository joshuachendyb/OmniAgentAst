# observation 工具结果显示问题 —— 深度分析与优化方案

**文档编号**：`doc-10月优化/[8]`
**创建时间**：2026-10-04 11:53:48
**更新时间**：2026-10-04 18:23:29
**编写人**：小欧
**版本**：v1.6

## 版本历史

| 版本 | 更新时间 | 更新人 | 修改简介 |
|------|----------|--------|----------|
| v1.0 | 2026-10-04 11:53:48 | 小欧 | 首版。基于生产库 1418 帧 observation / 2306 条工具子行实测取证，输出 6 项确认缺陷、根因结论与优化方案 |
|
| v1.5 | 2026-10-04 17:43:47 | 小欧 | 北京老陈指令：分析文档所述与现状的差异，并在第五章提出可优化的 UI 显示方法。**重建第五章「什么问题」**（8 条清单逐条标注已修/仍在）+ **5.1 现状复核**（逐条回代码核实，附提交号与行号证据，另记 2 处原文档未记的现状 A/B）+ **5.2 UI 显示优化建议五条**（子行去硬截、摘要不兜底 data_text、展开区改"结果本体"三段式、目录按行渲染不自造树、两套折叠收敛）。**说明**：精简章节时第五章与第六章（原方案表）被一并删除，本版按裁定重建问题章并补回文末落款；第六章是否重建待裁定 |
| v1.6 | 2026-10-04 18:23:29 | 小欧 | 北京老陈指令：§4.2/4.3/4.4 三节所述代码已全部下线，按裁定**三节合并重写为新 §4.2「当前渲染实现」**（①不做形状分派：列出已删的 `resultTypes.ts`/`shapeRenderers.tsx` ②取数链三级收一级，只认 `tool_result` ③实际渲染形态：4 键对象 + `Descriptions column=1` + `data_text` 仍被折叠 2 行，含 `MAX_*` 阈值出处），§4.3/§4.4 按裁定留空并标注失效原因。同批落地的死字段清理（`execution_result`/`execution_status`/`tool_params`/`parallel_results`/`observation`/`return_direct` 及 `content`）见 §5.1 |

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
| `summary`  | `sseParser.ts:894/898` | 均取 `tr[0].llm_data.summary` | ⚠️ `content` 恒为摘要副本；`summary` 仅孤儿 obs 段读（`PipelineRenderer.tsx:458`） |

#### 4.1.5 字段消费统计

| 类别 | 数量 | 占比 |
|------|------|------|
| ✅ 有真实读取点 | 7 | 35% |
| ⚠️ 有读取代码但语义失效/路径不可达 | 5 | 25% |
| ❌ 零消费（只写不读 / 读不存在的键） | 7 | 35% |


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


**现在不补的理由**：补 `summary=_llm.get("summary")` 等于**为不存在的消费方写数据，违反 YAGNI**。

**接线时必须一并处理的前置待办**（本轮不动，仅记录）：

| # | 待办项 | 说明 |
|---|--------|------|
| 1 | `summary` 实参透传 | 6 处调用点**必须同时补**，否则出现"部分工具有 `_summary`、部分没有"的不一致 |
| 2 | `data` → `summary` 取值口径 | `observation_builder.py:90` 已算出 `_llm`，可直接取 `_llm.get("summary")`，无需重算（DRY） |
| 3 | 三处空转代码归属 | `summary` 形参 + `_summary` 分支 + `prepare_messages_for_llm` 的 `_COMPACTION_TEMP_KEYS` 剥离逻辑，均属 compaction 未接线的正常伴生物，**不应单独拆改**（拆了即违反"不拆已有设计"） |

---

### 4.2 当前渲染实现（2026-10-04 18:23:29 小欧 按清理后代码重写）

**一、不做形状分派**

**二、取数链：只认 `tool_result`**

```
ToolResultRenderer/index.tsx（当前实现全文逻辑）
  if (step.tool_result == null) return null;
  return <GenericResultRenderer data={step.tool_result} />;
```

- 原兜底 `step.tool_result ?? step.execution_result ?? step.content` 三级链已收成一级：
  `execution_result` 是前端自造派生字段（只在 `tool_result` 非空分支内赋值 → 兜底永不可达），
  `content` 恒等于 `summary` 副本（名不副实，正文真身是 `tool_result[i].data_text`），二者本轮随死字段清理删除。

**三、实际渲染形态**（`tool_result` 长度 1 时；阈值取自 `GenericResultRenderer`）

```
└ 1px 左侧竖线块 (Colors.BORDER.VERTICAL #e8e8e8)
  └ 长度 1 的数组 → 嵌套块 → 元素(4 键对象) → antd Descriptions column=1
      tool_name      bash
      llm_data       {summary / status / metrics}                  ← 递归嵌套
      data_text      观察: 执行成功: exit=0 …                      ← 唯一有用，但被折叠成 2 行
      other_data     {}
```

- 数组内联阈值 `MAX_INLINE_TAGS=5`，但元素含对象 → 不走 Tag 内联，落到嵌套块；
- 对象键值内联阈值 `MAX_INLINE_ENTRIES=3`，4 键对象 → 落 `Descriptions`（`column={1}`）；
- 字符串超 `MAX_STRING_LENGTH=100` → antd `Paragraph` `ellipsis={{ rows: 2, expandable: true }}`，即**唯一有用的 `data_text` 被折叠成 2 行**；
- `llm_data_text` 行已消失（后端第 0 步删除，commit `ad32a7777`）；`metrics` 值是 `{value,text}` 对象，故内联展开为 `value/text` 键值（不显 `[object Object]`）。

**结论（与旧 4.4 同判）**：**通用 observation 展示的是内部契约字段表，而非结果本身**——这正是第五章问题 5 的现状根因，改造方案见 §5.2 建议三。

### 4.3 两套折叠实现并存

| 组件 | 阈值 | 使用场景 | 交互 |
|------|------|----------|------|
| `CollapsibleText`（项目自研） | 5 行 / 200 字 | **仅字符串 `tool_result`** | 有 `stopPropagation` + Enter/Space 键盘 |
| antd `Paragraph ellipsis` | 100 字符 / 2 行 | 数组 `tool_result` 内的长字符串 | 无 `stopPropagation` |

---

## 五、什么问题

### 5.1  现存的情况
| 5 | ❌ 仍在 | `GenericResultRenderer` 仍按契约表渲染 `tool_name`/`llm_data`/`data_text`/`other_data`；唯一有用的 `data_text` 反被 antd `Paragraph` 折叠 2 行（§4.4 形态未变） |
| 6 | ❌ 仍在 | 硬截在 `ToolCallLine.tsx:334` `sum.slice(0, 60)`；乱码片段来自 `:169` 兜底链 `llm_data.summary → data_text → summary`，无 summary 时拿长观察文本当前 60 字 |
|
**另发现两处原文档未记的现状**（第 5/6 条的根因落点）：

| # | 现象 | 位置 | 说明 |
|---|------|------|------|
| A | 子行同时存在 CSS 省略与硬截 60 字 | `ToolCallLine.tsx:334` + 同行 `textOverflow:ellipsis` | 硬截在半句处切断并吞掉真实结尾；CSS 省略已足够，硬截纯多余 |
| B | 展开区 `singleStep` 继承 `obsStep` | `ToolCallLine.tsx` 展开区构造处 | `obsStep.tool_name` 只取 `tool_result[0]`；形状分派已删故当前无害，**一旦在展开区显示工具名即复现问题 4** |

### 5.2 UI 显示优化建议（2026-10-04 17:43:47 小欧 新发现，待北京老陈裁定）

> 均为只改前端、不改后端契约的最小改动；依据是数据契约实测形态（`metrics` 值自带面向人的 `text`），不新造结构。

**建议一：子行摘要去掉硬截（治问题 6 之一）**
- 改法：删 `slice(0, 60)`，交回同行已有的 CSS 单行省略。
- 收益：不再半句切断；纯删冗余，行为只增强。

**建议二：子行摘要不再拿 `data_text` 兜底（治问题 6 之二）**
- 改法：摘要只取 `llm_data.summary`；无 `summary` 就留空。
- 理由：`data_text` 是长观察文本，截前 60 字必然是"乱码片段"；文本展示职责归展开区即可。

**建议三：展开区改为"结果本体"三段式（治问题 5 主症）**
```
① 头：状态图标 + 工具名 + 完整 summary（一行，CSS 省略，不硬截）
② 主体：data_text 全文，等宽字体 + maxHeight 滚动，不折叠
        （用户点开就是要看结果，折叠 2 行等于不给看）
③ 尾：metrics 渲染为一排小标签，只取契约里的 text 字段
隐藏：tool_name（与子行重复）、other_data（编排信号，前端零消费）
```
- 顺带收掉问题 2 残留：`metrics` 的 `text` 本就是给人看的（§3.3），无需后端加字段即可正确显示统计。
- 依据：`GenericResultRenderer` 全仓仅 `ToolResultRenderer` 一处调用，改契约无外部牵连。
- 注意：头部工具名必须取 `tools[i].tool`，**不可取 `obsStep.tool_name`**（见 5.1 现状 B）。

**建议四：目录类结果按行渲染，不自造树**
- 改法：`data_text` 以换行拆分，每行一条、等宽字体。
- 禁止项：**不得 `JSON.parse` 造树**——实测 0/2306 条可解析（§2.2），凭空造结构即重犯问题 1/2 的根因。

**建议五：两套折叠实现收敛（对应 §4.5）**
- 现状：`CollapsibleText`（5 行/200 字）用于字符串 `tool_result`/`content` 兜底；antd `Paragraph`（2 行）用于数组内长字符串。
- 建议：按建议三，展开区 `data_text` 不折叠 → `Paragraph` 折叠路径自然消失，只剩 `CollapsibleText` 一处；随问题 5 一并在下一阶段收，本阶段仅记录不改动。

---

**编写人**：小欧
**编写时间**：2026-10-04 17:43:47
**版本**：v1.5
