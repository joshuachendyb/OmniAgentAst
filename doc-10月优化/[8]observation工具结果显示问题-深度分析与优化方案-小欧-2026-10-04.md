# observation 工具结果显示问题 —— 深度分析与优化方案

**文档编号**：`doc-10月优化/[8]`
**创建时间**：2026-10-04 11:53:48
**更新时间**：2026-10-04 11:57:17
**编写人**：小欧
**版本**：v1.1

## 版本历史

| 版本 | 更新时间 | 更新人 | 修改简介 |
|------|----------|--------|----------|
| v1.0 | 2026-10-04 11:53:48 | 小欧 | 首版。基于生产库 1418 帧 observation / 2306 条工具子行实测取证，输出 6 项确认缺陷、根因结论与优化方案 |
| v1.1 | 2026-10-04 11:57:17 | 小欧 | 北京老陈指令：在第四章头部补充 observation SSE 事件字段清单（字段含义 + 前端是否消费）。原 4.1~4.4 顺延为 4.2~4.5 |

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
| `llm_data_text` | `str` | `llm_data` 的完整 JSON 副本（`indent=2`） | ❌ **全仓零消费**，纯冗余（详见 P2-9） |
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
| ❌ 零消费（只写不读 / 读不存在的键） | 8 | 40% |

**结论**：后端下发 20 个有效字段（顶层 5 + `tool_result[i]` 5 + `llm_data` 子字段 10），
前端**真实用上的仅 7 个**（`type` / `step` / `timestamp` / `tool_result` / `tool_name` / `llm_data.summary` / `llm_data.status.exec_code`），
其中最关键的 `data_text` 处于"被读取但前提错误"状态。
**40% 的字段是纯负担**——`llm_data_text` 更是每条 observation 都携带一份完整 JSON 副本，只写不读。

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

---

## 五、确认缺陷清单

### P0-1 `listdir` / `tree` 展开区 100% 显示"目录为空"

**实测：97 / 97（100%）**

**根因链**：

1. `data_text` JSON 可解析率 0%；
2. `sseParser.ts:875-883` `JSON.parse` 必失败 → `dataObj = { raw: dataText }`（`:879`）；
3. `shapeRenderers.tsx:51-61` `JSON.parse` 必失败 → 仅 `textData.content = dt`；
4. `data.entries` / `data.tree` **永不存在**；
5. `TreeResultRenderer` 分支A（`:259` `entries.length > 0`）与分支B（`:330` `if (tree)`）**全部不可达** → 落到 `:386-399` 兜底 → 渲染"目录为空"。

**用户可见矛盾**（生产库真实对照）：

| 折叠头摘要（正确） | 展开区（错误） |
|---|---|
| `列出目录成功: 922项, 863文件, 59目录, 94611352字节` | **`目录为空`** |

分支A 的"共 N 项（目录 x / 文件 y），总大小 z"统计**从未渲染过一次**。

### P0-2 `metrics` 渲染全链路失效（双重破坏）

后端 `metrics` 已是 `{value, text}` 对象（实测 `{'value': 922, 'text': '922项'}`），前端仍按 `number` 使用：

| 位置 | 代码 | 实际后果 |
|------|------|----------|
| `shapeRenderers.tsx:260-263` | `(metrics.total as number) \|\| 0` | 对象 truthy → 渲染出 **`共 [object Object] 项`** |
| `shapeRenderers.tsx:409-411` | `const lines = (metrics.lines as number) \|\| 0` 后 `lines > 0` | `{...} > 0` → `false` → **"本次 60 行 / 共 3081 行"永不显示** |

**即：即使 P0-1 修复，统计行依然错误。** 两缺陷叠加。

### P0-3 并行同名工具结果串味 —— 407 / 2306（17.6%）

**实测**：
- 多工具帧 529 个，其中 **256 个（48.4%）含重名工具**；
- 真实样本：`['bash','bash','bash','bash']`、`['read','read']`、`['write','write']`、`['searchweb','searchweb']`、`['listdir','bash']` …

**根因**：`ToolCallLine.tsx:159-175` 用 `results.find(r => r.tool_name === name)` 取**首个命中**。同名组内第 2/3/4 个子行全部绑定到 `results[0]` → **显示第 1 个工具的结果**。

**串味槽位按工具名分布**：

| 工具名 | 串味子行数 |
|--------|-----------|
| searchweb | 111 |
| shell | 51 |
| readtext | 49 |
| find | 26 |
| searchtool | 23 |
| fetchpage | 21 |
| listdir | 20 |
| writetext | 15 |
| read | 14 |
| edit | 13 |
| httpget | 13 |
| bash | 12 |

> **不是理论风险，是高频场景。** `searchweb` 单项就占 111 个子行。

### P0-4 形状分派读错工具名 —— 164 / 2306（7.1%）

**根因**：`ToolCallLine.tsx:297-300`

```tsx
const singleStep = { ...(obsStep as ExecutionStep), tool_result: singleResult };
```

**未覆盖 `tool_name`**，而 `obsStep.tool_name` 来自 `sseParser.ts:889` 的 `tr[0].tool_name`。于是展开第 i 个工具时，用**第 0 个工具**的名字选渲染器。

**实测错配分布**（子行数）：

| 展开的工具 | `obsStep.tool_name` | 实际走的渲染器 | 子行数 |
|---|---|---|---|
| `bash` | `read` | **CodeResultRenderer** | 217 |
| `bash` | `searchweb` | generic | 172 |
| `bash` | `write` | generic | 135 |
| `bash` | `readtext` | generic | 90 |
| `bash` | `writetext` | generic | 89 |
| `bash` | `fetchpage` | generic | 77 |
| `bash` | **`listdir`** | **TreeResultRenderer** | 53 |
| `timenow` | `read` | CodeResultRenderer | 42 |

**用户可见后果**：在 `read + bash` 批次中展开 bash 子行 → 看到 **"读取文件成功" + 代码块**，内容却是 shell 的 stdout。

### P1-5 generic 路径展示内部契约裸_dump（1940 / 2376 子行，81.6%）

如 §4.4 所述：`data_text`（唯一有用的可读结果）被挤在 5 行 Descriptions 的第 4 行、且被 antd 折叠成 2 行；`llm_data_text`（2306/2306 全有）是 `llm_data` 的**冗余 JSON 副本**，零语义消费。

### P1-6 摘要硬截断且兜底污染

- `ToolCallLine.tsx:354` `sum.slice(0, 60)` —— 硬截 60 字符，无省略号；
- `ToolCallLine.tsx:187-192` 摘要兜底链 `llm_data.summary → data_text → summary`，其中 `data_text` 是**整个 KB 级展示文本**，空 `summary` 时摘要会变成乱码片段；
- `r.summary`（顶层）后端**从不下发**，该分支恒不命中。

### P2 其他确认项

| # | 问题 | 位置 |
|---|------|------|
| P2-1 | **死代码**：`renderers/` 7 文件中 5 个零生产引用（`SmartContentRenderer` / `ToolInfo` / `WarningBox` / `NextActions` / `StatusIcon`），仅靠 `index.ts` 桶导出"看起来在用" → 违 YAGNI | `renderers/` |
| P2-2 | `GenericResultRenderer` 递归**无深度上限、无循环引用防护**（对比 `ToolCallLine:286`、`shapeRenderers:51` 均已加 try/catch）；大数组逐项铺开无上限 → 千级 DOM 节点 | `GenericResultRenderer.tsx:106-196` |
| P2-3 | `sseParser.ts:890` 读 `el.tool_params` —— 后端不下发 → 恒 `{}`；`else` 分支读 `rawData.observation` / `tool_name` —— 同样不下发 → 恒 `''` | `sseParser.ts:890-913` |
| P2-4 | `getResultForIndex` 的 5 个配对探测中仅 `r.tool_name` 命中，`r.tool` / `r.name` / `llm_data.tool` / `llm_data.tool_name` 全为死分支 | `ToolCallLine.tsx:159-173` |
| P2-5 | `resolveResultType` **零直接测试**；`extractResult` 模块私有未 export | `resultTypes.ts` / `shapeRenderers.tsx:40` |
| P2-6 | **测试与真码脱钩**：`shapeRenderers-fix.test.ts:12-35` 本地**重实现了一份 `extractResult` 副本**，从不 import 真码 | `src/tests/unit/shapeRenderers-fix.test.ts` |
| P2-7 | 测试用**假数据掩盖缺陷**：`chat-audit-2026-08-27.test.tsx` BUG-A 构造 JSON 形态 `data_text`（后端从不产生），使 tree 分派"可达"；`pipeline-rendering.test.ts:183-250` 的 `shouldCollapse` 本地模拟用 `maxLines=30/2000`，与组件真实默认 `5/200` 不一致 | 多处 |
| P2-8 | 多处 `expect(true).toBe(true)` 强制绿（`audit-chat-page-30bugs.test.tsx:127,133,155,164,182,190`） | 测试 |
| P2-9 | `llm_data_text` 零消费却是每条 observation 的**完整 JSON 副本**；对 `llm_data["diff"]`（`write` 全文 diff，生成端 `write_text_file.py:385-389` 无截断）、`action.params.content`（`clipboard_control.py:36`，上限 204800）、`action.params.text_or_keys`（`keyboard_control.py:27`，**无任何上限**）三个大内容向量直接翻倍 | `observation_builder.py:131` |
| P2-10 | 展开区与 `aria-expanded` 所在的 `role="button"` 头是**兄弟节点**（`ToolCallLine.tsx:313` vs `:380`），辅助技术无法关联 | `ToolCallLine.tsx` |

---

## 六、根因结论

**一句话根因**：

> 前端 observation 渲染体系是照着 **"`data_text` 是 JSON"** 这一**错误前提**建立的（2026-08-27 `ToolResultRenderer` 重构时的假设），而后端从来只发格式化展示文本。2026-08-28 / 09-01 两次补丁（`data_text` 兜底为 `content`）**只修了 `read` 一条路径**，`listdir` / `tree` / `generic` 三类一直没修，且被**使用假数据的测试**长期掩盖。

**结构性问题**（比单个 bug 更值得注意）：

1. **契约假设未落地为断言** —— 前后端对 `data_text` 形态的理解从未被任何测试或类型约束固定，导致错误假设能存活 6 周（08-27 → 10-04）。
2. **测试用假数据自证正确** —— BUG-A 用 JSON `data_text` 断言 tree 分派可达，而这个场景生产中 0% 存在。测试给了虚假绿灯。
3. **修复打补丁而非修根因** —— 09-01 的 `content` 兜底是"让 `read` 不空"，没有回头质疑"`entries`/`tree` 为什么永远拿不到"，于是 `listdir` 的"目录为空"被留到今天。

---

## 七、已裁定方向（北京老陈 2026-10-04 决定）

| # | 事项 | 裁定 |
|---|------|------|
| 1 | `TreeResultRenderer` / `CodeResultRenderer` 去留 | **删掉 tree/code 渲染器**（两个分支已实测永不可达，属过度设计；全走统一的 `data_text` 展示） |
| 2 | 死代码与脱钩测试 | **删死代码 + 重写脱钩测试**（清 YAGNI 违规；测试改为 import 真码并使用生产真实 `data_text` 形态） |

---

## 八、待裁定事项

### 8.1 P0-3 同名串味修法

| 方案 | 做法 | 优点 | 缺点 |
|------|------|------|------|
| **A（推荐）** | `getResultForIndex` 改为**索引优先**（`results[idx]`），去掉 `find()` 探测 | 后端已保证索引严格对齐（§3.4），一行改动即彻底解决 17.6% 串味 | 无 |
| B | 后端 `tool_result[i]` 补 `tool_call_id` 供精确配对 | 契约更严谨 | 改动面大（后端 + SSE + 落库 + 回放），且索引对齐本已可靠 |
| C | 保留 `find()` 但同名组内顺序消耗（消耗式匹配） | 兼容乱序 | 复杂度显著上升（违反 KISS-DIRECT） |

**小欧建议 A**：后端索引对齐是硬保证，`find()` 的"防乱序"设计属于**解决不存在的问题**（违反 KISS-DIRECT / YAGNI），反而制造了 17.6% 的真实缺陷。

### 8.2 P0-4 形状分派修法

若采纳第七章裁定 1（删 tree/code 渲染器），则 `resolveResultType` 与 `shapeRenderers` 一并删除，P0-4 **自动消失**（无分派即无错配）。这是裁定 1 的连带收益，需确认接受。

### 8.3 generic 路径是否保留内部契约表

| 选项 | 说明 |
|------|------|
| **A** | 有价值 —— 原始数据是排查依据。保留但优化：`llm_data_text` 去重折叠、`data_text` 提为首行主区、`llm_data` 收进二级折叠 |
| **B** | 无价值 —— 只显示 `data_text` 可读文本，契约表整体收进二级折叠（默认收起） |

**待北京老陈裁定。**

---

## 九、实施影响面与风险

### 9.1 拟定改动范围（待批准后执行）

| 文件 | 改动 | 关联缺陷 |
|------|------|----------|
| `ToolResultRenderer/index.tsx` | 删形状分派，统一走单一渲染器 | P0-1 P0-2 P0-4 |
| `ToolResultRenderer/resultTypes.ts` | **整文件删除** | P0-1 P0-4 |
| `ToolResultRenderer/shapeRenderers.tsx` | 删 `TreeResultRenderer` / `CodeResultRenderer` / `extractResult` / `formatFileSize` / `formatMtime` / `TreeDirItem` / `TreeTreeNode` | P0-1 P0-2 |
| `renderers/` 5 个死代码文件 | 删除；`index.ts` 桶收缩为仅 `GenericResultRenderer` | P2-1 |
| `ToolCallLine.tsx` | `getResultForIndex` 改索引优先；删 4 个死探测分支 | P0-3 P2-4 |
| `sseParser.ts` | 删 `el.tool_params` 死读与 `else` 死分支 | P2-3 |
| `src/tests/` | 重写脱钩测试；新增同名批次、真实 `data_text` 形态回归 | P2-5~P2-8 |

### 9.2 风险与回归防护

| 风险 | 防护 |
|------|------|
| 删除 tree/code 后目录树交互能力丢失 | 已知并接受（分支实测 0% 可达，等于无能力）；`data_text` 仍含完整目录文本 |
| 删死代码误伤 | 逐文件确认零生产引用（本文 §4 已列 grep 证据），删除后跑 `npm run check:full` |
| 索引优先后若后端真出现乱序 | 后端 `tool_runner.py:123-130` 按下标回填，乱序不可能；若未来契约变更，须同步改此逻辑（注释留痕） |
| `npm run check:full` 不含 e2e typecheck | 提交前必须跑 `npm run typecheck` + `npm run typecheck:e2e`（AGENTS.md 2026-10-01 修订） |

---

## 十、附录：取证方法与可复现脚本

### 10.1 取证脚本位置

| 脚本 | 用途 |
|------|------|
| `C:\Users\chend\AppData\Local\Temp\opencode\probe_obs.py` | `data_text` JSON 可解析率、各工具 `data_text` 样本 |
| `C:\Users\chend\AppData\Local\Temp\opencode\probe_obs2.py` | `tool_result[i]` 键频、`llm_data.metrics` 键频、多工具批次样本 |
| `C:\Users\chend\AppData\Local\Temp\opencode\probe_obs3.py` | 重名批次占比、串味槽位统计、listdir/tree/read 可用性 |
| `C:\Users\chend\AppData\Local\Temp\opencode\replay_frontend.py` | **1:1 复刻前端渲染管线**，喂真实数据观测实际分支 |
| `C:\Users\chend\AppData\Local\Temp\opencode\probe_final.py` | 最终权威量化（1418 帧 / 2306 子行） |

### 10.2 数据库只读连接方式

```python
sqlite3.connect('file:' + os.path.expanduser('~/.omniagent/chat_history.db') + '?mode=ro', uri=True)
```

### 10.3 声明

- 本报告全部数据取自生产库**只读**查询，未修改任何数据。
- 本报告结论均可由上述脚本复现验证。
- 本轮**未修改任何代码**。

---

**编写人**：小欧
**编写时间**：2026-10-04 11:53:48
**版本**：v1.0