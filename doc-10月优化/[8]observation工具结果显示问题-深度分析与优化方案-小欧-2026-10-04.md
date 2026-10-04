# observation 工具结果显示问题 —— 深度分析与优化方案

**文档编号**：`doc-10月优化/[8]`
**创建时间**：2026-10-04 11:53:48
**更新时间**：2026-10-04 22:20:00

## 版本历史

| 版本 | 更新时间 | 更新人 | 修改简介 |
|------|----------|--------|----------|
| v1.0 | 2026-10-04 11:53:48 | 小欧 | 首版。基于生产库 1418 帧 observation / 2306 条工具子行实测取证，输出 6 项确认缺陷、根因结论与优化方案 |
|
| v1.5 | 2026-10-04 17:43:47 | 小欧 | 北京老陈指令：分析文档所述与现状的差异，并在第五章提出可优化的 UI 显示方法。**重建第五章「什么问题」**（8 条清单逐条标注已修/仍在）+ **5.1 现状复核**（逐条回代码核实，附提交号与行号证据，另记 2 处原文档未记的现状 A/B）+ **5.2 UI 显示优化建议五条**（子行去硬截、摘要不兜底 data_text、展开区改"结果本体"三段式、目录按行渲染不自造树、两套折叠收敛）。**说明**：精简章节时第五章与第六章（原方案表）被一并删除，本版按裁定重建问题章并补回文末落款；第六章是否重建待裁定 |
| v1.6 | 2026-10-04 18:23:29 | 小欧 | 北京老陈指令：§4.2/4.3/4.4 三节所述代码已全部下线，按裁定**三节合并重写为新 §4.2「当前渲染实现」**（①不做形状分派：列出已删的 `resultTypes.ts`/`shapeRenderers.tsx` ②取数链三级收一级，只认 `tool_result` ③实际渲染形态：4 键对象 + `Descriptions column=1` + `data_text` 仍被折叠 2 行，含 `MAX_*` 阈值出处），§4.3/§4.4 按裁定留空并标注失效原因。同批落地的死字段清理（`execution_result`/`execution_status`/`tool_params`/`parallel_results`/`observation`/`return_direct` 及 `content`）见 §5.1 |
| v1.7 | 2026-10-04 18:41:52 | 小欧 | 北京老陈指令："这个要在第 5 章的修改清单上说明这个问题，以及如何处理的策略"。**§5.2 建议五改写为完整条目**（问题/危害/现状/处理策略/风险/状态六栏）：两套折叠实现并存（自研 `CollapsibleText` 5行200字带 `stopPropagation` vs antd `Paragraph` 100字符2行无 `stopPropagation`）→ 策略定为**保留 `CollapsibleText` 作唯一折叠实现**（全仓 50 处引用不可删）、**删 `GenericResultRenderer` 的 antd 折叠分支**改长文本全量渲染 + 400px 滚动 + 等宽字体，零后端改动。**明确记载代码未动**（`GenericResultRenderer.tsx` 与 HEAD 一致），待裁定后随建议三一起实施 |
| v1.8 | 2026-10-04 18:44:44 | 小欧 | 北京老陈指令："重新梳理，这里是不是有重复的问题？"。**第五章去重梳理**：核实出 4 处交叉重复（5.1 的 A 与建议一同一件事、建议五 ⊂ 建议三、建议四 ⊂ 建议三②、B 只是实施注意），改为**问题与建议一一对应**——5.1 改列 3 条现存问题（⑤展示内部契约字段表 ⑥摘要硬截+乱码兜底 ⑦两套折叠实现并存〔新增条目，原只在 §4.5 记录〕），A 并入问题 6 的证据、B 降级为「实施注意（非独立问题）」；5.2 由五条建议收敛为两条（建议一 ↔ 问题 6；建议二 ↔ 问题 5+7），折叠收敛与目录按行渲染并入建议二子项，删独立的建议四/建议五。**代码未动。** |
| v1.9 | 2026-10-04 21:12:20 | 小欧 | 北京老陈指令：按 observation 现在的实现实际情况完全替换第五章。第五章由待优化方案改写为实施后现状：5.1 四层结构（集合行/子行/展开区/被拒工具行）5.2 逐元素字段来源+令牌规格（含乙案参数每键一行、丙案超5项折叠、亮蓝五角星）5.3 结论区不显示清单（data_text 与契约字段表等）5.4 折叠实现只剩 CollapsibleText 5.5 UI 与字段来源总览 5.6 实跑证据（截图+展开区文本）5.7 已知取舍与遗留 |
| v1.10 | 2026-10-04 21:32:48 | 小欧 | 北京老陈指令：把 action 字段的前一轮分析与全量普查一起整理成第六章（只读分析，代码未改）。6.1 三消费端各用哪些子键（formatter: tool/tool_zh/target/params.extract_format；telemetry: 只认 artifacts；前端零消费）6.2 赋值质量三类问题与甲乙丙丁四方案评估 6.3 AST 全量普查（163 处 action / 144 非空且四键 100% 齐备 / 14 处 data.action 同名脏数据 / 1 处空 action / 66 文件）6.4 target 与 params 重复铁证（tree.py:130/138，144/144 全含）6.5 五条优化方案（去重为核心）+ 建议顺序 6.6 三项待裁定 |
| v1.11 | 2026-10-04 22:03:47 | 小欧 | 北京老陈指令：参数键名统一方案写入第七章。7.1 现状诊断三套命名体系并存（LLM侧别名已归一/实现侧未统一/别名表残留）7.2 规范名清单5类（path/source/destination/output_path/url等）7.3 三步落地（实现统一79文件→注册schema与别名同步→删action.target并按6规范名派生）7.4 风险（历史回放缺target需裁定/测试断言/面广/schema与实现须同批）7.5 三项待裁定 |
| v1.12 | 2026-10-04 22:20:00 | 小欧 | 北京老陈指令：按实测收窄更新第七章范围。复核发现初稿「79 文件/8 种命名」判断有误——AST 普查 144 处 action 字面量后确认 **138 处params 键已规范**（FILE 类全部用 path/source/destination），仅 document/read_pdf、read_pptx、write_pptx **3 文件 6 处**用 file_path。7.1 改为「键名基本已统一，只剩 3 处」7.2 标注现状已基本达成 7.3 改为四步（144 处删 action.target / 3 文件改键名+3 处 schema / formatter 派生 6 规范名 / 截断帧补齐），明确不动工具函数名与内部变量名 7.4 面广风险由 79 文件降为 3 文件 7.5 待裁定减为 2 条；6.6 方案A 表述同步校正 |

---

## 一、报告背景与目标

### 1.1 背景

北京老陈 2026-10-04 指令：读取前端 step 页面的 observation 工具显示，要求**深入仔细研究、深入全面分析，不能走马观花**。

### 1.2 本报告的取证原则

本报告**不采信代码注释、不采信设计文档、不采信既有测试断言**，所有结论以下列三条独立证据链交叉验证：

1. **源码通读**：前端渲染链 + 后端构造链逐文件读取；
2. **生产数据实测**：直接读取 `~/.omniagent/chat_history.db` 的 `chat_task_steps` 表，取真实 `observation` 帧统计；
3. **逻辑重放**：用 Python 1:1 复刻前端渲染管线（`sseParser` → `ToolCallLine` → `resolveResultType` → `shapeRenderers`），喂真实数据，观测实际渲染分支。（2026-10-04 清理后管线已无 `resolveResultType` / `shapeRenderers`，现链路见 §4.2；本条记录的是**取证当时**的管线）

### 1.3 目标输出

- 精确定位 observation 工具结果显示的全部缺陷；
- 给出每项缺陷的**量化影响面**与**根因链**；
- 给出优化方向与待裁定事项。

---

## 二、数据链路全景（后端 → 像素）

```
observation_builder.py:128-134
    tool_result[i] = {tool_name, llm_data, data_text, other_data}                ← 4 键(2026-10-04 删 llm_data_text)
        ↓ SSE
sseParser.ts:855-921
    只取 tr[0] → 合成 tool_name / summary / error_message（2026-10-04 删 execution_result 等 6 处死派生字段与 content 兜底）
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
    singleStep = { ...obsStep, tool_result: [r] }        ← 未覆盖 tool_name（历史缺陷 P0-4 根因）
        ↓
ToolResultRenderer/index.tsx（2026-10-04 起不再分派）
    step.tool_result → GenericResultRenderer（按值类型递归渲染）        ← 原 resultTypes.ts/shapeRenderers.tsx 已删
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
| `tool_result[i]` 键集合 | **恒为 4 个**：`tool_name` / `llm_data` / `data_text` / `other_data`（2306/2306 全部齐备；2026-10-04 第 0 步删 `llm_data_text`，本行为删后口径） |
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
| ~~`llm_data_text`~~ | — | **2026-10-04 第 0 步已删**（前端零引用、回放兜底实测 0/2306 不可达，体积反超本体 28%；`format_llm_data_text` 随之整函数下线，提交 `ad32a7777`） |
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
| `content` | `str` **恒为 `""`** | 2026-04 前的老字段，已废弃不承载文本 | ❌ 前端 3 处兜底读已删（`ToolCallLine` 展开区两处 + `shapeRenderers`）→ **现零读取**；后端仍下发（link 回放老格式兜底用，见 §4.2） |
| `tool_result` | `List[Dict]` **条件性** | 本轮全部工具结果；**空列表时该键整个不下发** | ✅ `ToolCallLine.tsx` flatMap 收集；`ToolResultRenderer` 唯一渲染入口 |

#### 4.1.2 `tool_result[i]` 字段（恒 4 个，2306/2306 实测齐备；2026-10-04 删 `llm_data_text` 后口径）

| 字段 | 类型 | 简要说明 | 前端是否使用 |
|------|------|----------|--------------|
| `tool_name` | `str` | 工具注册名（经自动纠正） | ✅ `ToolCallLine` 子行显示；形状分派已删（原 `resolveResultType` 选渲染器那条读取点已下线） |
| `llm_data` | `dict` | 结构化 LLM 观察（见 4.1.3） | ✅ `ToolCallLine` 取 `summary` / `status.exec_code` |
| `data_text` | `str` | **喂 LLM 的格式化展示文本**（非 JSON，实测 0/2306 可解析） | ⚠️ 现仅 `GenericResultRenderer` 渲染；原 `JSON.parse` 尝试与摘要兜底均已删 |
| `other_data` | `dict` | 旁路数据（`retry_count`/`attachment`/`category`/`return_direct`/`warning`/`synthetic`） | ❌ 零消费（`step.return_direct` 派生字段 2026-10-04 已删） |

#### 4.1.3 `llm_data` 子字段

| 字段 | 类型 | 简要说明 | 前端是否使用 |
|------|------|----------|--------------|
| `summary` | `str` | 中文短摘要成品句，如"列出目录成功: 922项" | ✅ `ToolCallLine.tsx:188` 子行摘要首选；`sseParser.ts:894` 合成 `step.summary` |
| `action` | `dict` | `tool` / `tool_zh` / `target` / `params` / `artifacts?` | ❌ **零消费**（`tool_zh` 在前端 0 匹配；`artifacts` 的读取点全属 `final_stats` 帧，与本字段无关） |
| `status.exec_code` | `str` | 执行码，**枚举仅 3 值**：`success` / `error` / `warning` | ✅ `ToolCallLine` 判水滴图标颜色（原 `shapeRenderers.tsx:74` 随渲染器删除） |
| `status.message` | `str` | 人类可读结果描述 | ⚠️ `sseParser` 赋给 `step.error_message`，但 observation 步骤的 `error_message` **无读取点**（`StatusLine` 只渲染 `type==='error'`） |
| `status.code` | `str` | 错误码常量（`ERR_*`） | ❌ 零消费 |
| `status.detail` | `str` | 错误细节 | ❌ 零消费 |
| `status.hint` | `str` | 处理建议 | ❌ 零消费 |
| `duration_ms` | `int` | 工具执行耗时 | ❌ 零消费 |
| `metrics` | `dict` | 指标集，**值为 `{value, text}` 对象** | ⚠️ 现由 `GenericResultRenderer` 渲染为内联 `value/text` 键值（不再出现 `[object Object]`，原 `shapeRenderers.tsx` 按 number 使用的双重失效已随之消失）；尚未按 `text` 提取为统计标签 → 见 §5.2 问题 1 改法③ |

#### 4.1.4 前端自行合成的派生字段（非后端下发）

> 2026-10-04 清理后**仅剩 1 个**：`execution_result` / `execution_status` / `tool_params` / `parallel_results` / `observation` / `return_direct` / `content` 七项已删（提交 `3b8630519`）。

| 派生字段 | 来源 | 说明 | 前端是否使用 |
| `summary` | `sseParser.ts:894` | 取 `tr[0].llm_data.summary`（`content` 曾是它的副本，已删） | ✅ 孤儿 obs 段读（`PipelineRenderer` obs 分支）；子行摘要直接读 `tool_result[i].llm_data.summary` |

#### 4.1.5 字段消费统计

> 2026-10-04 清理后重算（后端下发 18 个一级字段 = 顶层 5 + `tool_result[i]` 4 + `llm_data` 子字段 10；原 20/12 口径含已删的 `llm_data_text`）。

| 类别 | 数量 | 占比 |
|------|------|------|
| ✅ 有真实读取点 | 8 | 44% |
| ⚠️ 有读取代码但语义不完整 | 3 | 17% |
| ❌ 零消费（只写不读 / 读不存在的键） | 7 | 39% |

明细：✅ = `type`/`step`/`timestamp`/`tool_result`/`tool_name`/`llm_data`/`llm_data.summary`/`status.exec_code`；⚠️ = `data_text`（仍渲染，但已裁定不再显示，见 §5.2 问题 1）、`status.message`（赋值无读点）、`metrics`（内联显示未成统计标签）；❌ = 顶层 `content`、`other_data`、`action`、`status.code`、`status.detail`、`status.hint`、`duration_ms`。


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
  history_loader.py:139       content = el.get("data_text") or ""      ← 2026-10-04 删 llm_data_text 兜底
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
| ~~`tool_result[].llm_data_text`~~ | ❌ 已删 | ❌ | 2026-10-04 第 0 步下线（前端零引用 + 兜底实测不可达） |
| `tool_result[].data_text` | ✅ | ✅ **唯一载体** | 与 SSE 逐字相同 |
| `tool_result[].other_data` | ✅ | ❌ | `return_direct`/`warning`/`attachment` 等编排信号不进 LLM |
| （action 帧）`tools[].params` | ✅ | ✅ | `tool_calls[].function.arguments`，**未格式化** |

**净结论**：

- **SSE 帧** = 面向**前端 + 落库**的结构（18 个一级字段，2026-10-04 删 `llm_data_text` 后口径）
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

**结论（与旧 4.4 同判）**：**通用 observation 展示的是内部契约字段表，而非结果本身**——这正是第五章**问题 1**（通用工具展示内部字段）的现状根因，改造方案见 §5.2 问题 1 与 §5.3 方法二。

### 4.3 两套折叠实现并存

| 组件 | 阈值 | 使用场景 | 交互 |
|------|------|----------|------|
| `CollapsibleText`（项目自研） | 5 行 / 200 字 | **仅字符串 `tool_result`** | 有 `stopPropagation` + Enter/Space 键盘 |
| antd `Paragraph ellipsis` | 100 字符 / 2 行 | 数组 `tool_result` 内的长字符串 | 无 `stopPropagation` |

---

## 五、observation UI 显示的实际情况（2026-10-04 实施后）

> 本章按 **实施后的代码实际状态** 描述（不再是"待优化方案"）。
> 涉及文件：`ToolCallLine.tsx`（集合行/子行/参数块）、`ToolResultRenderer/index.tsx`（展开区结论区）。
> 相关提交：`d26f2a15e`（删形状分派+下标配对）、`61ed58963`/`3b8630519`（死字段与死文件清理）、`29b0ba2c3`（结论区+子行/参数优化）、`be85d69d6`（实跑截图脚本）。

### 5.1 整体结构（四层）

```
集合行（每轮 action 一条）
  ⚙ + "并行 N 个工具" 或 "调用 1 个工具" + [工具名列表, 逗号分隔] + (重试N次)
子行（每工具一条，折叠态一直可见的那一行）
  💧水滴(按 status.exec_code 上色) + 工具名 + 结果摘要(单行 CSS 省略) + ⌄箭头
  └ 点开 → 展开区（下面两层）
展开区
  ├ 参数块  每键一行等宽字体；项数 >5 时折叠为"▸ 参数（N 项）"，点击展开
  └ 结论区  ★(亮蓝五角星) + 完整摘要(单行省略) + metrics 小标签排
被拒工具行（有被拦截/拒绝时追加在子行之后）
  [图标] [安全]/[超时]/[拒绝]/[沙箱] + 工具名 + "未执行：{原因}"
```

### 5.2 各层渲染的字段与样式（全部用现成令牌，无新增设计变量）

| 层 | 元素 | 数据来源 | 样式规格 |
|---|------|---------|---------|
| 集合行 | 齿轮图标 + 集合文案 | `action.tools[]` | `并行 ${toolCount} 个工具` / `调用 1 个工具`；`exec_type === 'multi'` 判并行 |
| | 工具名列表 | `action.tools[].tool` | 逗号分隔 |
| | 重试标记 | `action.action_retry_count` | >0 时 `(重试N次)` |
| 子行 | 水滴图标 | `tool_result[i].llm_data.status.exec_code` | `success`→`Colors.SUCCESS` / `error`→`Colors.ERROR` / `warning`→`Colors.WARNING`；`size=10` |
| | 工具名 | `action.tools[i].tool`（**不是** `step.tool_name`，后者只取 `tool_result[0]`） | `FontSize.SECONDARY(12)`，`flexShrink:0` |
| | 结果摘要 | `tool_result[i].llm_data.summary`（**唯一来源，无兜底**） | `FontSize.SECONDARY` + `Colors.TEXT.SECONDARY`；`flexGrow:1` + `overflow:hidden` + `textOverflow:ellipsis` + `whiteSpace:nowrap`；**无摘要整块不渲染** |
| | 箭头 | — | `CircleArrow size=16`，随展开态翻转 |
| 展开区·参数块 | 每键一行 | `action.tools[i].params` | 等宽 `Consolas/Monaco/Courier New`；格式 `${key}: ${value}`，字符串值直接取原值（**不二次序列化**，故路径 `\` 不双重转义）；项数 >5 才出现 `▸/▾ 参数（N 项）` 可点行（`Enter/Space` 同样切换） |
| 展开区·结论区 | 五角星 | — | `StarOutlined` + `Colors.PRIMARY(#1677ff)` 固定亮蓝，`FontSize.SECONDARY` |
| | 完整摘要 | `tool_result[i].llm_data.summary` | `FontSize.SECONDARY` + `FontWeight.MEDIUM(500)` + `Colors.TEXT.PRIMARY`；单行 CSS 省略 |
| | metrics 标签 | `tool_result[i].llm_data.metrics[k]` | 每键一枚 `${k}: ${text ?? value}`；`FontSize.SMALL(11)`、`Radius.SM(4)`、边框 `Colors.BORDER.VERTICAL`、行高 `11+Spacing.XS` |

### 5.3 结论区**不显示**的内容（2026-10-04 北京老陈裁定，已实施）

| 不显示 | 原因 |
|--------|------|
| `data_text` | 是喂 LLM 的"请求-处理对象-结果"三段拼接文本，原样铺满等于把内部话术怼给用户；且工具结果正文已由 assistant 回答承载 |
| `tool_name`（契约键） | 与子行显示的工具名重复 |
| `llm_data.action` | 前端零消费 |
| `status.code` / `status.detail` / `status.hint` | 前端零消费 |
| `duration_ms` | 前端零消费 |
| `other_data`（`retry_count` 等） | 编排信号，前端零消费 |
| 原契约字段表（antd `Descriptions` 键值表） | 已下线：结论区不再消费整份 `tool_result`，`GenericResultRenderer` 随之整体下线 |

> 代价（如实记录）：**目录/文件清单不再出现在 observation 展开区**，需看 assistant 回答正文。

### 5.4 折叠实现的现状

| 组件 | 阈值 | 使用场景 | 交互 |
|------|------|---------|------|
| `CollapsibleText`（项目自研，唯一折叠实现） | 5 行 / 200 字 | ① `tool_result` 为**字符串**时的结果块；② AI 长消息 | `stopPropagation` + `Enter/Space` |


即：折叠实现从 2 套收敛为 1 套；数组形态的 `tool_result` 不再走任何折叠分支。

### 5.5 数据来源总览

| UI 元素 | 后端字段 | 是否进 LLM |
|--------|---------|-----------|
| 集合行工具名/参数 | action 帧 `tools[].tool` / `tools[].params` | ✅（`tool_calls[].function.arguments`，未格式化） |
| 子行工具名 | action 帧 `tools[].tool` | ✅ |
| 子行摘要 / 结论区摘要 | `tool_result[i].llm_data.summary` | ❌ 不进 |
| 子行水滴状态 | `tool_result[i].llm_data.status.exec_code` | ❌ 不进 |
| 结论区 metrics 标签 | `tool_result[i].llm_data.metrics[k].text` | ❌ 不进（其信息已被 formatter 压平进 `data_text` 文本） |
| （不显示）`data_text` | `tool_result[i].data_text` | ✅ **唯一载体**（conversation history 靠它） |

### 5.6 实跑证据（2026-10-04）

- 截图：`frontend/e2e_case/output/ui-shots/observation-light.png`、`observation-dark.png`（脚本 `frontend/e2e_case/shot_observation_ui.mjs`，亮/暗两态）
- 展开区实抓文本（`listdir`）：
  ```
  listdir
  列出目录F:\OmniAgentAs-repair\backend\app\utils，成功: 18项，18个文件，0个目录
  参数：
  path: F:\OmniAgentAs-repair\backend\app\utils
  total: 18项   dir_count: 0个目录   file_count: 18个文件   total_size: 73094字节
  ```
- 自动化护栏：`npm run typecheck` 0 error；`npm run test` 134 文件 1483 用例全绿（含 4 例按新口径改写的契约测试）。

### 5.7 已知取舍与遗留

| 项 | 说明 |
|---|---|
| 目录清单不可见 | 展开区不再显示 `data_text`，目录/文件清单需看 assistant 回答 |
| 失败/警告在结论区无色 | 结论区五角星固定亮蓝（不按 `exec_code` 变色），状态语义由**子行水滴**承担 |
| 参数 >5 项需点开 | 已按阈值 5 折叠；若某工具参数长期很多，可考虑改为默认展开首屏 |
| 回归防护 | 契约测试守护"摘要可见 + metrics 标签可见 + `data_text`/契约字段不可见"；新增 UI 改动须同步这 4 例 |

---

## 六、`llm_data.action` 字段深度分析与优化方案（2026-10-04）

> **分析口径（2026-10-04 北京老陈定案）**：`llm_data.action` 的**第一目的是服务 formatter 拼 `data_text`**（喂 LLM 的观察文本），**次要目的才是给前端显示**。因此评估标准是"对 formatter 有用且赋值准确"，而不是"前端有没有读"。
> 本章为**只读分析**产出，代码未改动。

### 6.1 三个消费端各自用了哪些子键（决定字段去留的唯一依据）

| 消费端 | 实际读取的子键 | 代码位置 | 目的 |
|--------|---------------|---------|------|
| **`observation_formatter`（第一目的）** | `action.tool`、`action.tool_zh`、`action.target`（经 `_tool_target()` 取，统一 `truncate_text` 截到 200 字）、`action.params.extract_format` | `observation_formatter.py:634-652`、`:1322-1324` | 拼喂 LLM 的第 1 行：`工具执行: {tool_zh} 调用工具-{tool},处理对象-{target} - 执行结果: 成功` |
| **`agent_telemetry`（统计）** | **只认 `action.artifacts`**（注释明言"仅认写工具 with_artifacts 自声明，兜底派生已删"） | `app/monitoring/agent_telemetry.py` | 产出物清单 → `final_stats.tool_stats` |
| **前端** | **零消费**（`tool_zh` 在 `frontend/src` 0 匹配；`artifacts` 的读取点全属 `final_stats` 帧） | — | — |

**关键结论**：`action.params` **从不整体进入文本**，只在 `:1324` 被读了一个 `extract_format`（read 工具的输出格式分支）。而 `action.target` 是 formatter 第 1 行的**唯一"处理对象"来源**——它比 `params` 更重要。

### 6.2 `action` 子键被读取的全量清单（含第一目的之外的隐性依赖）

> 前一轮只统计了"拼文本用到哪些"，**遗漏了截断提示/handler 分派也在读 `action.tool`**。下表为 formatter 内全部读取点：

| 读取点 | 读的子键 | 用途 | 缺 `action.tool` 的后果 |
|---|---|---|---|
| `_format_llm_data` :632-637 | `tool` / `tool_zh` | 拼第 1 行 `工具执行: …` | 工具名退化 |
| `format_data_detail` :143-144 | `target` | per-tool 详情里的处理对象 | 处理对象缺失 |
| `_truncation_msg` | `tool` | **截断提示按工具分流**（`read`/`edit` → "完整内容见文件"，其他 → 通用截断） | **提示文案错配** |
| handler 分派 :151 / :228 / :251 / :366 | `tool` | 按工具选不同详情格式器 | 走错格式分支 |

**结论**：`action.tool` 与 `action.target` 是 formatter 的**双刚需**（文本 + 分流），`tool_zh` 次要（仅文本），`params` **只被读一个 `extract_format`**。

### 6.3 赋值质量的前一轮结论 + 本轮补充发现

| # | 问题 | 证据 | 对第一目的的影响 |
|---|------|------|----------------|
| 1 | **类型不统一** | `observation_formatter.py:23` 注释："status/action 可能为 str（工具实现不规范）"，全文件 6 处读取均用 `_safe_llm_sub()` + `isinstance` 兜底 | 工具把 `action` 填成字符串时，`tool`/`target`/`tool_zh` 全丢，第 1 行退化 |
| 2 | **`target` 曾泄漏非 str 类型** | formatter 内注释（2026-07-12）："action.target 可能为非 str 类型（如文档工具泄漏的 WindowsPath），直接 `len()` 会 TypeError，统一 str() 化兜底"；`_tool_target` 现有 `str(_t)` 兜底 | 已修，但说明"赋值规范"未被工具层遵守，只是被 formatter 吸收 |
| 3 | **空 `action`** | `react_step.py:593` 截断帧为 `"action": {}` | 第 1 行工具名为空；`_truncation_msg` 也走通用分支 |
| 4 | **与 action 帧语义重叠** | `action.params`（工具**实际生效**）vs action 帧 `tools[].params`（LLM **下发**），仅沙箱改写/默认值时不同 | 双份传输（体积） |
| 5 | **本轮补充：`data.action` 命名撞车** | 14 处 `data.action`（`rollback` / 桌面动作类 / `delete`）与 `llm_data.action` **完全同名不同层** | 现状不冲突（formatter 只取 llm_data 层），但将来 data 串层即污染 |
| 6 | **本轮补充：`action` 统一入口存在但未强制** | `app/tools/tool_response.py:117` 有 `llm_data["action"] = _act` 的统一写入点，但 144 处工具仍各填各的 dict 字面量 | 入口形同虚设，类型/字段一致性无人把关 |

（前一轮的四方向评估——甲保持现状 / 乙前端用起来 / 丙后端精简下发 / 丁删冗余子键——结论仍成立：**丁最贴近第一目的**，因为 `params` 只被读一个 `extract_format`，而 `tool/tool_zh/target` 是刚需。）

### 6.4 全量普查（AST 解析，只读）

普查口径：AST 遍历 `backend/app/**/*.py`，抓所有 `"action": {...}` 字典字面量，统计子键覆盖与异常形态。

| 指标 | 数值 |
|------|------|
| `"action"` 字面量出现总数 | **163** |
| 其中非空字典 | **144** |
| 非空字典中含 `tool` / `tool_zh` / `target` / `params` | **各 144（100% 齐备，无一例外）** |
| `"action"` 为非 dict 字面量（脏数据） | **14** |
| `"action"` 为表达式（运行时填充，未普查） | 4 |
| `"action": {}` 空字典 | **1**（`react_step.py:593` 截断帧） |
| 含 action 字面量的文件数 | **66** |

**脏数据明细（14 处，全部是 `data.action` 同名撞车，不是 `llm_data.action`）**：

| 文件 | 键值示例 |
|------|---------|
| `tools/dataanalysis/execute_sql.py:266/277` | `"action": "rollback"`（与 `llm_data.action` 同名不同层） |
| `tools/desktop/desktop_register.py:141-145/163-166/175-176` | `"action": "maximize"/"minimize"/"restore"/"topmost"/"unpin"/"type"/"shortcut"/"read"/"write"` |
| `tools/file/delete_file.py:258` | `"action": "delete"` |

**结论**：`llm_data.action` 的填充一致性其实**很好**（144/144 四键齐备）；真正的问题是 ①`data.action` 与 `llm_data.action` **命名撞车**（将来谁把 data 塞进 llm_data 即污染）②截断帧空 action。

### 6.5 用户指出的重复问题：`target` 与 `params` 高度重复（已证实）

**铁证**（`app/tools/file/tree.py:130/138`）：
```python
_act_params = {"path": dir_path}
"action": {"tool": "tree", "tool_zh": "列出目录树",
           "target": dir_path,          # ← 与 params["path"] 同值
           "params": _act_params}
```
- 普查确认：**144 处 action 全部同时含 `target` 与 `params`**；
- FILE 类工具（read/write/listdir/tree/edit…）的 `params` 主体就是路径，`target` 正是该路径（或其 basename）；
- 即：**同一个"处理对象"信息在一条 observation 里存了两份**（`target` 一份 + `params.path` 一份），每帧多传一份 params 副本。

### 6.6 优化方案（以"删除 `action.target`"为基础改动，2026-10-04 北京老陈裁定）

> **裁定（用户）**：`action.params` **不删**（以后要用）；`action.target` **删掉**（前端零消费），这是**基础改动**，其余围绕它展开。
> **关键收益**：删掉 `target` 后，运行时"处理对象"只剩 `params` 一份 → §6.5 的重复问题**真正消除**，且**工具内部变量名一个都不用改**（符合项目既定原则"对外注册名/schema 统一，内部实现不动"，见 `file_register.py` 2026-10-02 编辑历史）。

**问题 → 方案对照总表**（每行可追溯到前面小节）：

| 问题出处 | 问题 | 处理 |
|---------|------|------|
| §6.5 / §6.2 | `action.target` 与 `action.params` 重复（144/144 全含） | **基础改动：删 `action.target`**，formatter 改从 `params` 派生 |
| §6.2 | `action.tool` 被 6 处读取（文本 + 截断提示分流 + handler 分派） | **保留，不动** |
| §6.2 | `action.tool_zh` 拼文本用 | **保留**（前端将来显示也用它） |
| §6.2 | `action.params.extract_format` 被读（read 输出格式分支） | **保留 params**，该行不改 |
| §6.3-1 | `action` 类型不统一（str 脏数据） | 不单独治理（现状 144/144 全为 dict 且四键齐备）；派生时统一 `str()` 即可 |
| §6.3-3 | 空 `action`（`react_step.py:593` 截断帧） | 顺带补 `tool`/`tool_zh`（1 处零风险） |
| §6.3-5 | `data.action` 与 `llm_data.action` 同名不同层（14 处） | **不改名**，仅加注释说明"同名不同层"（现状分层取值不会冲突） |
| §6.3-6 | `tool_response` 统一入口形同虚设（144 处各填各的） | **不做**（普查证明无缺失，统一入口改造属过度设计） |
| §6.1 | 前端零消费 | **需求已确认需要**（用 `tool_zh`+处理对象），**暂不实施** |

**方案明细**：

| # | 方案 | 具体做法 | 影响面 | 风险 |
|---|------|---------|--------|------|
| **A（基础）** | **删除 `action.target`** | 144 处工具 action 字面量去掉 `target` 键；`tool`/`tool_zh`/`params`/`artifacts` 保留 | 工具实现（仅删一个键，**不改内部变量名**） | 低。派生链按 §7.2 规范名（实测 138/144 处 params 键已规范，仅 3 处待补，见第七章） |
| **B（配套）** | **`formatter._tool_target` 改为派生** | 从 `action.params` 按候选链取"处理对象"，命中即用、全空则省略该段 | `observation_formatter`（一处） | 低。派生规则集中单点 + 单测覆盖 |
| **C（配套）** | **截断帧补齐** | `react_step.py:593` 的 `"action": {}` 补 `tool="truncated_output"`、`tool_zh="输出截断"` | 1 处 | 零风险 |
| **D（配套）** | **`data.action` 加注释** | 明确"与 `llm_data.action` 同名不同层"，不改名 | 1~2 处注释 | 零风险 |
| **E（记录）** | **前端消费 `tool_zh` + 处理对象** | 需求已确认，**暂不实施**；将来实施时从 `action.params` 派生链取处理对象 | 前端 | 需与子行 `tool_name` 去重评估 |

**建议顺序**：C（零风险）→ A+B（同批，必须一起改否则 formatter 拿不到处理对象）→ D → E（待排期）。

### 6.7 待裁定事项

| # | 待裁定 |
|---|---------|
| 1 | 方案 3：`action.params` 是否从下发中删除；`extract_format` 改从何处取（`data`？工具上下文？保留 params 但不入帧？） |
| 2 | 方案 2：统一入口时 `tool` 缺失的兜底来源（调用上下文注册名？）与 66 文件改造是否安排 |
| 3 | 方案 5：`data.action` 是否改名 |
| 4 | 方案 6：前端是否消费 `tool_zh`+`target`（或继续零消费） |

---

## 七、工具参数键名统一方案（2026-10-04 北京老陈指令：在注册层统一名称）

> 起因：第六章确认 `action.target` 与 `action.params` 大量重复，且 `target` 前端零消费 → 决定删 `target`、改由 `params` 派生。
> **本章为方案设计（代码未改动）**。数据来源：AST 普查 `backend/app/tools` 的 **144 处 action 字面量**（工具实现内）+ `tools_alias_mapper.PARAM_ALIASES`（覆盖 37 工具）。
> **2026-10-04 复核修正**：初稿据"79 文件/8 种命名"判断需大规模统一，实测**138/144 处 params 键已规范**，仅 **3 文件 6 处**例外（见 §7.1），故范围大幅收窄。

### 7.1 现状诊断：键名基本已统一，只剩 3 处

| 体系 | 现状（实测） |
|------|------------|
| ① LLM 下发侧容错别名 | `PARAM_ALIASES`（2026-07-11 起）把 `file_path`/`filepath`/`file`/`filename`/`file_name`/`filePath`/`dir_path` 等降级为 `path`，覆盖 37 工具 → **属输入侧容错，必须保留** |
| ② **工具实现内 `action.params` 键名** | **138/144 处已是规范名**（`path` / `source` / `destination` / `url` / `query` / `command` / `sql` 等）；FILE 类全部工具（read/write/edit/listdir/tree/search/copy/rename/move/compress…）均已用 `path`/`source`/`destination` |
| ③ **仅剩的非规范项** | **3 文件 6 处**：<br>· `app/tools/document/read_pdf.py` → `file_path`<br>· `app/tools/document/read_pptx.py` → `file_path`<br>· `app/tools/document/write_pptx.py` → `file_path` |

**结论**：键名统一的历史工作**基本已完成**（项目 2026-07~2026-10 陆续做过），本次只需补 3 处 + 删 `action.target`。

### 7.2 规范名清单（目标口径，现状已基本达成）

| 类别 | 规范名 | 待统一的散名 |
|------|--------|------------|
| 主对象路径 | **`path`** | `file_path` / `filepath` / `filePath` / `file` / `filename` / `file_name` / `dir_path` / `dir` / `directory`（**实现侧仅剩 `file_path`×3 处**） |
| 源位置 | **`source`** | `src` / `from` / `src_path` / `source_path`（实现侧暂无） |
| 目标位置 | **`destination`** | `dst` / `to` / `dst_path` / `dest` / `destination_path`（实现侧暂无） |
| 产出物 | **`output_path`** | `output` / `output_file` / `archive_path`（实现侧暂无） |
| 网络 / 检索 / 命令 / 数据 | `url` / `query`(+`pattern`) / `command` / `sql` / `dataset` / `table` | 已一致 |

### 7.3 落地方案（按实测范围收窄；不动工具内部变量名与函数名）

**第 1 步 · 删除 `action.target`（基础改动，144 处）**
```python
# 现状（tree.py:138）
"action": {"tool": "tree", "tool_zh": "列出目录树",
           "target": dir_path,                 # ← 删这一项
           "params": _act_params},             # _act_params = {"path": dir_path} 原样保留
```
- **只删 action 里那一个键**，`_act_params` 与内部变量（`dir_path`/`file_path`）一行不动；
- 144 处机械删除，遵循 AGENTS 1.4「复制不重写」。

**第 2 步 · 补 3 处非规范键 + 对应 schema（3 文件）**
```python
# document/read_pdf.py、read_pptx.py、write_pptx.py
_act_params = {"file_path": pdf_path}   →   {"path": pdf_path}
```
- 同时同步 `document_register.py` 里这三个工具的 schema 字段名（否则 LLM 下发 `path`、实现读不到）；
- `PARAM_ALIASES` 已有 `file_path → path` 别名（`read_pdf`/`read_pptx` 在覆盖列表内），LLM 侧容错不受影响。

**第 3 步 · formatter 派生"处理对象"（一处改动）**
```python
# observation_formatter._tool_target：由读 action.target 改为从 params 派生
_p = _action.get("params", {})
_t = (_p.get("path") or _p.get("source") or _p.get("url")
       or _p.get("sql") or _p.get("query") or _p.get("command") or "")
```
- **行为等价性已验证**：FILE 类原手写 `target` 与 `params["path"]` 同值（§6.5），派生结果与现状一致，**喂 LLM 的观察文本不变**；
- 全空则省略"处理对象"段（formatter 已有 `if target:` 分支）；
- 补单测：6 个规范名各 1 例 + 全空 1 例。

**第 4 步 · 顺带（1 处）**：截断帧 `react_step.py:593` 的 `"action": {}` 补 `tool="truncated_output"`、`tool_zh="输出截断"`。

**总计改动**：144 处删键 + 3 文件改键名 + 3 处 schema + formatter 一处 + 1 处截断帧；**工具函数名与内部变量名零改动**。

### 7.4 风险与影响面

| 风险 | 说明 | 兜底 |
|------|------|------|
| **历史 observation 回放**（关键） | 旧 `execution_steps` 存的是旧结构（**带 `action.target`**）；新代码不写 target、派生靠 `params`——旧数据的 params 里键名可能是 `file_path` 等旧名，派生链可能取不到 → 回放时"处理对象"为空，**影响历史多轮会话的 LLM 注入质量** | **建议**：`history_loader` 回放时按派生链 + 旧键名兜底（一次性修历史，运行时不留兼容壳）——**需北京老陈裁定** |
| 单测 / E2E 断言 | 少量测试直接传 `file_path` 或断言 `action.target` | 别名层先归一，多不受影响；需跑全量验证 |
| schema 与实现不同步 | 第 2 步必须同批改 | 强制同提交 |
| 派生链需全覆盖 | 若将来新工具用非规范键，派生会取不到 | 单测兜底 + 新增工具时 schema 评审 |

### 7.5 待裁定事项

| # | 待裁定 |
|---|---------|
| 1 | **历史回放**：旧数据缺 `params` 规范键时如何补（建议 `history_loader` 派生时兼容旧键名，不在运行时代码留兼容壳） |
| 2 | 实施节奏：144 处删键一次性做完，还是分批（FILE 类 → document 类 → 其余）提交 |

**编写人**：小欧
**版本**：v1.12

**编写人**：小欧
**编写时间**：2026-10-04 22:20:00
**版本**：v1.12
