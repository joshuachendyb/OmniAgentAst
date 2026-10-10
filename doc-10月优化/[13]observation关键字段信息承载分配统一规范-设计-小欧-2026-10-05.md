# observation 关键字段信息承载分配统一规范与实施方案

**文档编号**：`doc-10月优化/[10]`
**创建时间**：2026-10-05 22:03:53
**更新时间**：2026-10-05 22:03:53

## 版本历史

| 版本 | 更新时间 | 更新人 | 修改简介 |
|------|----------|--------|----------|
| v1.0 | 2026-10-05 22:03:53 | 小欧 | 首版。先设计后实施：统一 llm_data 各字段信息承载分配规范，附 shell/move/rename/time_now 四条实施方案与三堂会审 |
| v1.1 | 2026-10-05 22:10:00 | 小欧 | 北京老陈指令修订：①删除 3.2「双通道」冗余原则，改为单通道分配；②3.1 补充 3.1.1 组装关系全表；③P4 移除；④metrics 命名与 move/rename 口径改为已定；⑤4.1/4.2/4.3 方案去数字化 |
| v1.2 | 2026-10-05 22:25:00 | 小欧 | 核实补记 P5：read_text_file 的 `total_lines` 因 `_METRICS_RENDERED_BY_HANDLER` 跳过且 handler 未呈现而在 LLM text 中彻底丢失；新增 4.5 两方案（收窄跳集合[推荐] / handler 自呈现），要求先 grep 全部 total_lines 呈现点再定方案 |
| v1.3 | 2026-10-05 22:30:00 | 小欧 | 按 4.5 执行 grep 核实后修订：原判 P5 撤销——`total_lines` 实际由各 handler 各自呈现（read_text_file 走 summary `N/M行`、read_pdf/read_docx 走 `_format_text_content` hint、read_docx 走 summary+metrics），`_METRICS_RENDERED_BY_HANDLER` 跳过它是防重复的正确设计。4.5 改写为核实结论表 + 落地风险警告；新增 4.6 read_text_file summary 去数字化方案（配套 total_lines 呈现归属二选一迁移，否则新 P5 成立）。问题表标题改「5 处问题（P1/P2/P3/P5 实施→现 P1/P2/P3 实施、P4/P5 不动）」 |
| v1.4 | 2026-10-05 22:40:00 | 小欧 | 北京老陈指令：①新增 **4.7 全量逐 tool 改法清单**（10 类 · 79 处 summary 拼接点全覆盖，每 tool 一行给现状/类型/改法，汇总需落码 51 个、不动 15 个）；②**第五章删除三堂会审内容，改为「公共函数改动」章**（5.1 observation_formatter 跳集合必改 + 通用渲染/去叠字/_tool_target/format_data_detail 不动、5.2 tool_response 不动、5.3 tool_retry_engine 需改、5.4 改动清单、5.5 三堂会审要点压缩保留）；③第二章改为「三类系统性问题」分类 + 明确不动项清单 |
| v1.5 | 2026-10-05 22:55:00 | 小欧 | 北京老陈指令「熟读全文查一致性」+「以真实 metrics 现状为据」：核对全量 metrics 现状后修正 8 处错误——①create_task/delete_task/get_system_info 的 error detail **已填**，由「需改（B）」改为合规不动；②timer_set success 原文是 `{_delay_sec//60}` 分钟，纠正笔误；③mouse_scroll 实有独立 error 分支（`鼠标滚动失败`，detail 已有），纠正「无 success/error 区分」；④download_file 的 success 有完整 summary 且 metrics 已含 `file_size`/`content_type`（此前漏登记）；⑤search_web error 的 **message 嵌了 detail**（非 summary，但同属冗余，需改 message）；⑥fetch_webpage error detail 已填合规不动 + 其 warning 含数字需去；⑦write_docx metrics 有三项非两项（补 `table_count`）；⑧window_info 的 `window_count` 确认 metrics 构造缺该键（需新增）。结论：metrics 全量经 AST+真实运行核查——除 move/rename/clipboard/window_info/notify/mouse_scroll 六处确缺外，其余 metrics 均已承载数字，**落地改法以「去 summary 数字为主、新增 metrics 为辅」为准** |
| v1.6 | 2026-10-05 23:05:00 | 小欧 | 北京老陈裁定方案 A：§3.2 补「结论性数字进 summary」豁免（`新增N行，删除M行` 属结论核心而非统计冗余，summary 与 metrics 同值）；4.4.1 edit 行改为方案 A（summary 带增减行数，`applied`/`total_matches` 仍归 metrics） |
| v1.7 | 2026-10-05 23:10:00 | 小欧 | 北京老陈裁定：move_file / rename_file / delete_file / compress_files 的 summary **不动**（路径对结论清晰；delete/compress 的数字列为结论性数字豁免）；4.4.1 四行改为「summary 不动」，4.4.11 汇总表 move/rename 仍落码（仅补 metrics）、delete/compress 移入不动列 |

---

## 一、背景与问题缘起

### 1.1 触发事件

2026-10-05，`read_text_file` 的 summary 信息顺序整改后，用户要求普查 `write/edit` 等同属 file 类与 fundamental 类工具是否存在同类问题。经两轮只读审查 + 真实 `format_llm_observation` 输出核验，发现：

1. **summary 不是孤岛**：LLM 看到的观察文本 = `工具执行行 + 观察(message - summary) + 错误/警告(detail) + 建议(hint) + 统计(metrics) + 差异(diff) + data详情`。脱离完整上下文只看 summary 模板会产生大量误报（如把已在 `处理对象`/`导致`/detail 中呈现的字段误判为缺失）。
2. **跨文件无统一承载约定**：同类信息在不同工具散落于 summary / message / detail / metrics 四处，LLM 与前端无法建立稳定预期。
3. **现有 4 处问题**（见第二章）：P1 shell metrics 不齐、P2 move 无结果量、P3 rename 无结果量可实施（P4/P5 经裁定/核实分别不动、撤销）。

### 1.2 第一轮误报教训（务必避免）

仅凭 summary 模板下"信息缺失"结论是错的。必须先用 `format_llm_observation` 真实产出核对再下定论（本报告后续核实均以真实输出为据）。已撤销的误报：grep_file_content 缺 path（实际 target 已呈现）、error 分支缺真因（实际 detail 已渲染）、list_directory 缺 total_size（实际 metrics 通用渲染已覆盖）、read_text_file 参数藏尾（已修复属例外）。

---

## 二、问题分类（三类系统性问题，79 处普查）

### 2.1 问题类型总览

| 类型 | 判据 | 影响 |
|------|------|------|
| **A 类：summary 冗余量化数字** | success/warning summary 直接写行数/字节/字符数/个数/压缩率等量化数字，而同一数字已在 `metrics` 中 | 同一数字在 LLM text 出现两次，token 浪费 |
| **B 类：summary/error 冗余嵌 detail** | summary 或 error 分支嵌 `detail` 正文（`失败: {detail}`），而 detail 已在 `status.detail` 并经 `✖ 错误:`/`⚠ 警告:` 行渲染 | 同一信息两遍 |
| **C 类：metrics 缺项 / 无结果量** | summary 写了数字但 metrics 无对应项（结构化缺失），或 success 无结果量且 metrics 恒 `{}` | 前端/telemetry 无处结构化读取；LLM 看不到规模 |

> 重点问题（v1.0~v1.3 跟踪）：**P1** shell metrics 不齐（C）、**P2** move 无结果量（C）、**P3** rename 无结果量（C）、**P4** time_now error summary（北京老陈裁定不改）、**P5** total_lines 呈现归属（核实后撤销，风险转入 4.6/5.1.1）。

### 2.2 明确不动的项（核实后判定合规）

| 项 | 判定理由 |
|----|----------|
| `time_now.py` error summary | 北京老陈裁定：detail 已渲染真因，summary 留泛词即可 |
| `total_lines/page_count` 被 `_METRICS_RENDERED_BY_HANDLER` 跳过 | 防重复渲染的正确设计（详见 4.5 核实结论表） |
| `registry_read/write`、`registry_delete`、`time_add`、`query_calendar`、`timer_clear`、`mouse_click/mouse_move`、`generate_chart`、`copy_file` 的 summary 内数值/目标对 | 属**目标标识或结果本体**（注册表值、时间结果、坐标、图表输出路径、删除动作、源→目标路径对），非统计数字，**其 success summary 不动**。注：其中 mouse_click/mouse_move/generate_chart 等的 **error 分支仍需按 B 类去 detail**（见 4.4 对应行），「不动」仅指 success 分支的数字部分 |

---

## 三、信息承载分配统一规范（核心定案）

### 3.1 各字段职责（铁律）

| 字段 | 职责 | 写什么 | 不写什么 |
|------|------|--------|----------|
| `status.exec_code` | 成败三态 | success/error/warning | — |
| `status.message` | **状态短句**（泛词） | `复制成功`/`搜索完成`/`通知发送成功` | 参数、结果量、真因 |
| `summary` | **摘要核心** | 操作 + 目标参数 + 成败结论 | 量化数字（归 metrics）、失败真因（归 detail） |
| `status.detail` | **失败/警告真因** | 具体错误信息 | 参数、结果量 |
| `status.hint` | 可执行建议 | `请检查源文件路径是否正确` | 参数重复 |
| `metrics` | **结构化数字（唯一机读源）** | 全部量化数字（结果量）；文案取 `{value, text}` 形 | 路径/文本内容 |
| `action.params` | 入参 | path/dest/encoding 等 | — |
| `data` | 内容本体 | content/stdout/文件体 | 摘要 |

### 3.1.1 llm_data → LLM text 组装关系（format_llm_observation，源自源码核实）

LLM 最终收到的 observation text = `format_llm_observation(data, llm_data)` 产出（observation_formatter.py:759）。组装方 `_format_llm_data`（L663）实际用到的 llm_data 子字段如下：

| 用到的子字段 | 拼接位置 | 形态 |
|--------------|----------|------|
| `action.tool_zh` / `action.tool` | 第1行 `工具执行:` | `{tool_zh} 调用工具-{tool},处理对象-{target}` |
| `action.params`（派生 target） | 第1行 | `_tool_target()` 取 path/source/url 族，200 截断 |
| `status.exec_code` | 第1行尾 | 成功/失败/完成-[有警告]/未知 |
| `status.message` | 第2行 `观察:` | 与 summary 去叠字后 ` - ` 拼接（summary 以 message 开头则取一） |
| `summary` | 第2行 `观察:` | 与 message 同行，L698-702 |
| `status.detail` | 第3段 | 仅 error/warning 时 `✖ 错误:`/`⚠ 警告:` |
| `status.hint` | 第4段 | 仅 error/warning 时 `建议:` |
| `metrics`（各项 `{value,text}`） | 统计段 `统计:` | L717-738 通用渲染，取 text（空取 value），跳过 total_lines/page_count |
| `diff` | 差异段 `差异:` | L740-754，行×列收口 |
| `data`（经 `format_data_detail`） | 详情段 `详情:` | success/warning 时；error 时补 `诊断补充`/`错误详情`（防遮蔽 deleted_files 等） |

**关键事实**：summary 文本里出现的数字会让 LLM 看得见，但 `metrics` 才是数字的唯一机读源；data 详情只在有值时追加。因此「summary 不再收数字」并不让 LLM 丢数字——数字由 metrics 统计段同源呈现。

### 3.2 单通道职责分配原则（不冗余、省 token）

- **每个信息只挂一次**，落点按职责归位：**summary 只写核心关系信息（操作+目标+结论），量化数字一律进 metrics；失败真因进 detail；状态词进 message**。
- **禁止关键数字在 summary 与 metrics 同时出现**（token 浪费）；summary 需要提及规模时用概括词（如 `大量`/`多个`），具体字节/行数交 metrics。
- **例外（北京老陈裁定，结论性数字进 summary）**：描述"改了什么"本身的数字（如 edit 的 `新增N行，删除M行`）属**结论核心**而非统计冗余，允许进 summary，同时 metrics 保留同值（LLM 第一眼见结论、结构化从 metrics 取）。本例外仅限"结论本身即数字"的场景（如增删行数），字节/耗时等规模量仍按单通道归 metrics。
- **禁止只写 metrics 不写 summary**：summary 是 LLM 第一眼定位成功与否的关键行，必须有操作+目标+结论。
- `metrics` 每项取 `{value, text}`（文档[8]P1 通用渲染取 text，为空取 value）；summary 不重写该数字。

### 3.3 summary 信息顺序（与 read_text_file 整改同源）

`操作 → 目标参数 → 结论`（成功）；`操作 → 目标 → 失败`（error：真因归 detail，summary 仅保留操作与目标）。

> 注：read_text_file 已落地的 summary 内嵌 `100/1167行，70544字节` 属「双通道」风格；新规范落地后其 summary 应改为 `读取文件{path}，成功`，行数/字节由 metrics 统计段呈现。方案见 4.6，`total_lines` 呈现归属配套见 5.1.1（硬要求）。

### 3.4 detail 与 summary 去冗余

`detail`（`❌ 错误`行）已承载真因，**summary 不再嵌 detail 正文**（execute_shell_command warning 的 `_warn_msg` 即违例）。

---

## 四、代码实施方案（重点项详解 + 全量逐 tool 清单）

### 4.1 P1 execute_shell_command —— metrics 补齐 + warning 去冗余

**改法**（文件 `app/tools/fundamental/execute_shell_command.py`）：

- success 分支（L589 邻域）：summary 去数字改为 `执行Shell命令{cmd_short}，成功`，原 `退出码{returncode}，输出{output_len}字符` 量化数字整段迁入 metrics：
  ```python
  "metrics": {
      "exit_code": {"value": returncode, "text": f"退出码{returncode}"},
      "output_len": {"value": output_len, "text": f"输出{output_len}字符"},
  }
  ```
- warning 分支（L582 邻域）：summary 改为 `执行Shell命令{cmd_short}，成功`（warning 态由 formatter 的 `工具执行:` 行呈现「完成-[有警告]」，summary 不重复该措辞；`_warn_msg` 归 detail，stderr 长度量迁入 metrics）：
  ```python
  "metrics": {
      "exit_code": {"value": returncode, "text": f"退出码{returncode}"},
      "stderr_len": {"value": stderr_len, "text": f"stderr {stderr_len}字符"},
  }
  ```
  detail 保留 `_warn_msg`（`⚠ 警告`行渲染），不再冗余进 summary。

### 4.2 P2 move_file ——补结果量+metrics

**改法**（`app/tools/file/move_file.py` L72 邻域）：

```python
# success
"summary": f"移动成功: {source} -> {dest}",
"metrics": {
    "moved_bytes": {"value": moved_bytes, "text": f"{moved_bytes}字节"},
    "moved_count": {"value": moved_count, "text": f"{moved_count}项"},
}
```
`moved_bytes`/`moved_count` 由实际移动结果取；字节量由 metrics 统计段呈现，不再写进 summary。

### 4.3 P3 rename_file ——补结果量+metrics

**改法**（`app/tools/file/rename_file.py` L50/L101 邻域）：

```python
"summary": f"重命名 {source} → {new_name} 成功",
"metrics": { "size": {"value": size, "text": f"{size}字节"} }
```
「名称相同，无操作」分支：summary 保留 `重命名{source}，成功: {new_name}（名称相同，无操作）`，metrics 记 `{"changed": {"value": 0, "text": "0项改动"}}` 与 success 分支结构统一；size 数字不写进 summary。

### 4.4 全量逐 tool 改法清单（10 类 · 79 处 summary 拼接点全覆盖）

> 4.1~4.3 为重点项详解，4.5/4.6 为两项核实结论与配套方案；本节补齐全量普查（`grep '"summary": f"'` 实测 79 处），每 tool 一行，给现状 summary、问题类型（A 冗余数字 / B 冗余嵌 detail / C metrics 缺项）、改法。
> 类型定义见 2.1。统一改法：success summary 去量化数字（A）→ 数字入 metrics；error/warning summary 去嵌 detail（B）→ 归 `status.detail`；metrics 补结构化项（C）。

#### 4.4.1 file 类（14 个）

| tool | 现状 summary（success / error） | 类型 | 改法 |
|------|------------------------------|------|------|
| read_text_file | `读取文件{path}，成功: {段} {n}/{total}行，{bytes}字节` / `读取文件{path}，失败` | A+C | 见 4.6（去数字化 + total_lines 迁移） |
| write_text_file | `写入文件 {path}，成功，共 {bytes_written} 字节` / warning 带「提示说明:{detail}」 | A+B | summary → `写入文件{file_path}，成功`；提示归 detail；`bytes_written` 已在 metrics |
| edit_text_file | `编辑文件{path}，成功: 替换 {applied}/{total_matches} 处` / warning 带 `{_warning_msg}` | A+B | summary → `编辑文件{file_path}，成功: 新增{added}行，删除{removed}行`（北京老陈裁定方案 A，结论性数字豁免；`added`/`removed` 同时入 metrics；替换处数 `applied`/`total_matches` 仍由 metrics 呈现，不进 summary）；warning 归 detail |
| copy_file | `复制成功: {source} -> {destination}` | 无 | **不动**（destination 是核心目标，非数字） |
| move_file | `移动成功: {source} -> {destination}`，metrics 恒 `{}` | C | **summary 不动**（北京老陈裁定：路径对结论清晰）；仅补 metrics（`moved_bytes`/`moved_count`） |
| rename_file | `重命名 {source} → {new_name} 成功`，metrics 恒 `{}` | C | **summary 不动**（北京老陈裁定：路径对结论清晰）；仅补 metrics（`size`/`changed`） |
| delete_file | `删除{source}，成功: {_suffix}`（`_suffix` 含「删除N项/跳过M项」） | 无 | **不动**（北京老陈裁定：`_suffix` 的 N 项/跳过数是结论性数字，类比 edit 豁免）；数字已在 metrics |
| compress_files | `压缩{source}，成功: {file_count}个文件，{orig}→{comp}字节，压缩率{ratio:.1%}` | 无 | **不动**（北京老陈裁定：文件数/字节/压缩率是结论性数字，类比 edit 豁免）；四数已在 metrics |
| extract_archive | `解压文件{source}，成功: 解压N个,跳过M个` | A | summary → `解压文件{source}，成功`；`extracted_files`/`skipped_files` **已在 metrics**，仅去 summary 数字 |
| grep_file_content | `搜索内容'{pattern}'，成功: {total_files}个文件{total_matches}行匹配` / warning 带「提示说明」 | A+B | summary → `搜索内容'{pattern}'，成功`（pattern 保留）；warning 归 detail；两数**已在 metrics**（实测） |
| list_directory | `列出目录{path}，成功: {total}项，{file_count}文件，{dir_count}目录，第{a}-{b}项` / warning 带提示 | A+B | summary → `列出目录{dir_path}，成功`；四项（total/dir_count/file_count/total_size）**已在 metrics**（实测）；offset 区间归 detail（hint 已提示翻页） |
| search_files | `在 {dir} 中搜索 '{pattern}' 完成，共 {total} 个匹配项` | A | summary → `在 {search_dir} 中搜索 '{pattern}'，成功`；`total` **已在 metrics**，仅去 summary 数字；截断说明归 detail |
| tree | `列出目录树{path}，成功: {file_count}个文件，{dir_count}个目录` | A | summary → `列出目录树{dir_path}，成功`；四项（file_count/dir_count/total/total_size）**已在 metrics**，仅去 summary 数字 |
| read_media_file | `读取媒体文件{path}，成功:媒体类型: {mime_type}，内容大小:{file_size}字节` | A+C | summary → `读取媒体文件{file_path}，成功`；**`mime_type` 补进 metrics**（现仅在 summary） |

#### 4.4.2 fundamental 类（4 个）

| tool | 现状 summary | 类型 | 改法 |
|------|-------------|------|------|
| execute_shell_command | 见 4.1 | A+B+C | 见 4.1（summary 去数字 + `_warn_msg` 归 detail + 补 `output_len`/`stderr_len`） |
| send_notification | `发送系统通知，"{title}"，{notif_duration}秒，成功` | A | summary → `发送系统通知，"{title}"，成功`；`duration_sec` 入 metrics |
| tool_search | `搜索 '{query}'成功:匹配 {n} 个（共 {m} 个工具）` / error `搜索工具失败:关键词为空` | A+B | summary → `搜索 '{query}'，成功`；数字已在 metrics；error 原因归 detail；**顺带修 L160 注释示例漂移** |
| time_now | `获取当前时间失败` / `获取当前时间成功:{formatted}，{weekday}` | 无 | **不动**（裁定项；`formatted` 是结果本体） |

#### 4.4.3 dataanalysis 类（6 个）

| tool | 现状 summary | 类型 | 改法 |
|------|-------------|------|------|
| analyze_data | error `分析数据{t}，失败: {detail}` / success `成功: {row_count}行, {numeric_col_count}个数值列` | A+B | error 去 detail；success summary → `分析数据{t}，成功`；两数**已在 metrics**（实测构造非空），仅去 summary 数字 |
| execute_sql | error `执行{t}，失败: {detail}` / success `成功: 影响{affected_rows}行` | A+B | 同上模式（metrics 已构造非空）；success 去数字 |
| filter_data | error `筛选数据{t}，失败: {detail}` / success `成功: 从{a}行筛选出{b}行` | A+B | 同上模式（metrics 已构造非空）；success 去数字 |
| get_db_schema | error `获取数据库结构{t}，失败: {detail}` / success `成功: {total_tables}个表` | A+B | 同上模式（metrics 已构造非空）；success 去数字 |
| query_sql | error `查询{t}，失败: {detail}` / success `成功: {row_count}行, 列: {col_text}` | A+B | 同上模式（metrics 已构造非空）；success 去数字；`col_text` 属结果本体可留 |
| generate_chart | error `生成图表{t}，失败: {detail}` / success `成功: {chart_type}，已保存为{dest}` | B | error 去 detail；success 的 `chart_type`/`dest` 是结果本体与目标，**保留** |

#### 4.4.4 document 类（8 个）

| tool | 现状 summary | 类型 | 改法 |
|------|-------------|------|------|
| read_xlsx | error `读取Excel{p}，失败: {_err_summary}` / success `成功: {row_count}行，{sheet_count}个工作表` | A+B | error 去 `_err_summary`；success summary → `读取Excel{file_path}，成功`；两数**已在 metrics**（实测构造） |
| read_pdf / read_docx / read_pptx | error `读取XX{p}，失败: {_err_summary}`（success 未见 summary） | B | error 去 `_err_summary`；**success 落地前先核实数字呈现路径**（`total_lines`/`page_count` 已由 `_format_text_content` hint 呈现，不得重复） |
| write_docx | error `写入Word {p}，失败: {detail}` / success `成功: {para_count}段, {char_count}字符`（metrics 另有 `table_count` 共三项） | A+B | error 去 detail；success summary → `写入Word {file_path}，成功`；三数**已在 metrics**，仅去 summary 数字 |
| write_pdf | error `写入PDF {p}，失败: {detail}` / success `成功: {char_count}字符` | A+B | 同 write_docx 模式（metrics 已构造） |
| write_pptx | error `写入PPT{p}，失败: {detail}` / success `成功: {slide_count}页` | A+B | 同 write_docx 模式（metrics 已构造） |
| write_xlsx | error `写入Excel {p}，失败: {detail}` / warning `警告: {detail}` / success `成功: {row_count}行` | A+B | error/warning 去 detail；success summary 去数字（metrics 已构造） |

#### 4.4.5 desktop 类（10 个）

| tool | 现状 summary | 类型 | 改法 |
|------|-------------|------|------|
| clipboard_control | error `剪贴板{action}失败`（缺空格） / success `剪贴板{action}成功: {char_count}个字符` | A+B | 补空格；success summary 去数字；`char_count` 入 metrics |
| keyboard_control | error `键盘{action}，失败: {detail}` | B | error 去 detail |
| mouse_click / mouse_move | error `...(x,y)，失败: {detail}` | B | error 去 detail；**坐标属目标标识，success 保留** |
| mouse_position | error `获取鼠标位置失败: {detail}` / success `成功: 当前(x,y)` | A+B | error 去 detail；坐标属结果本体可保留（或入 metrics） |
| mouse_scroll | error `鼠标滚动失败`(detail 已有) / success `滚动完成: {direction_cn},滚动{amount}次`，metrics 恒 `{}` | A | success summary → `滚动{direction_cn}，成功`；`amount` 入 metrics |
| set_window_state / window_focus / window_resize | error `...失败:窗口标题为 {title}`——**只报标题不报原因** | B | summary 保留操作+目标；真实原因归 `status.detail` |
| window_info | error `获取窗口{t}信息失败: {detail}` / success `成功: 共{window_count}个窗口` | A+B | error 去 detail；success 去数字；`window_count` **需新增入 metrics**（实测构造缺该键） |

#### 4.4.6 network 类（5 个）

| tool | 现状 summary | 类型 | 改法 |
|------|-------------|------|------|
| download_file | error `下载文件{url}，失败`（detail 已填）/ success `下载并成功保存文件{dest_path},文件信息:大小: {size}类型:{type}`，`file_size`/`content_type` 已在 metrics | A | error **合规**（detail 已填，summary 不动）；success summary → `下载文件{url}，成功`；size/type 由 metrics 呈现 |
| fetch_webpage | error `获取{url}网页，失败`（detail 已填，合规）/ warning `获取{url}资源，成功但有警告: {mime_type}，HTTP {status_code}` | A | error **合规不动**；warning summary 去数字 → `获取{url}网页，成功`；`status_code` 入 metrics |
| http_request | error `HTTP请求:{url}，方法: {method} 失败`（detail 以此构造为准核对） / success `成功: (HTTP {status_code}) ({ctype})`，`status_code` **已在 metrics**（实测） | A | success summary → `HTTP请求:{url}，成功`；仅去 summary 数字 |
| ping_port | 4 处，含 `Ping{host}，成功: {status_text} {latency}` / `端口检查成功: {port}（{service}）{status_text}` | A+B | summary 保留操作+目标；`latency`（avg/min/max_latency **已在 metrics**）仅需去 summary 数字；`status_text` 属结论描述可留或归 detail |
| search_web | error `搜索{query}，失败`，但其 **message 嵌了 detail**（`f"搜索失败: {detail}"`，与 summary 不同但 message 与 detail 重复）/ success `成功: {result_count}条结果`，`results`/`engine` 已在 metrics | A+B | success 去数字；**error 的 message 去 detail**（message 只留状态短句 `搜索失败`，真因归 `✖ 错误` 行）；`result_count` 由 metrics 呈现 |

#### 4.4.7 system 类（6 个）

| tool | 现状 summary | 类型 | 改法 |
|------|-------------|------|------|
| create_task / delete_task | error `创建/删除计划任务{name}，失败`（detail 已填，实测构造） | 无 | **合规不动**（summary 含操作+目标，真因在 `✖ 错误` 行） |
| find_command | success `查找命令[{cmd}]成功: 找到{count}个路径` / `成功: {status}` | A | success 去数字；`count`/`paths` **已在 metrics**（实测构造）；「命令不可用」分支 status 属结论保留 |
| get_system_info | error `获取系统信息，{info_type}，失败`（detail 已填，实测构造） | 无 | **合规不动** |
| list_tasks | error `获取计划任务列表失败: {detail}` / success `成功: 共{a}个，匹配{b}个`，`total`/`matched` **已在 metrics**（实测） | A+B | error 去 detail；success 去数字 |

#### 4.4.8 timer 类（6 个）

| tool | 现状 summary | 类型 | 改法 |
|------|-------------|------|------|
| timer_list | success `获取定时器列表成功: 共{count}个` | A | summary → `获取定时器列表，成功`；`count` **已在 metrics**（实测） |
| timer_set | error `设置定时器{_delay_sec}秒，失败: {detail}` / success `成功: {timer_id}，{_delay_sec//60}分钟后触发` | A+B | error 去 detail；success summary → `设置定时器，成功`；`timer_id` 是标识可留 |
| time_diff | success `计算时间差，{humanized}（{days}天），成功` | A | `humanized` 是结果本体保留；`days` **已在 metrics**（实测构造） |
| time_add / query_calendar / timer_clear | success 含结果本体（`result_time`/`date_str`+节假日/`status_text`） | 无 | **不动**（结果本体非统计数字） |

#### 4.4.9 win_registry 类（3 个）

| tool | 现状 summary | 类型 | 改法 |
|------|-------------|------|------|
| registry_read / registry_write | success `读取/写入注册表{path}，成功: {value_name}={value}（{value_type}）` | 无 | **不动**（注册表值与类型是结果本体） |
| registry_delete | success `删除注册表{path}，成功: {action}` | 无 | **不动**（action 是结论） |

#### 4.4.10 tool_retry_engine（非工具层公共，见 5.3）

| tool | 现状 summary | 类型 | 改法 |
|------|-------------|------|------|
| tool_retry_engine | `工具 '{action}' 未找到`（error 无原因） | B | summary 合规；确认 `status.detail` 已填原因 |

#### 4.4.11 汇总（需落码 51 个 / 不动 15 个）

| 类 | 需落码 | 不动 |
|----|--------|------|
| file (14) | read_text_file、write_text_file、edit_text_file、extract_archive、grep_file_content、list_directory、search_files、tree、read_media_file、move_file、rename_file | copy_file、delete_file、compress_files |
| fundamental (4) | execute_shell_command、send_notification、tool_search | time_now |
| dataanalysis (6) | 全部 6 个 | — |
| document (8) | 全部 8 个 | — |
| desktop (10) | 全部 10 个 | — |
| network (5) | 全部 5 个 | — |
| system (6) | 全部 6 个 | — |
| timer (6) | timer_list、timer_set、time_diff | time_add、query_calendar、timer_clear |
| win_registry (3) | — | 全部 3 个 |

**合计需落码 51 个 tool，不动 15 个 tool。**

> 表注：「不动」指该 tool 的 **success 分支** summary 无需改（含结果本体/目标标识者见 2.2）。desktop/network/system 各类虽 success 数字属目标标识或结果本体，但其 **error/warning 分支普遍存在 B 类冗余嵌 detail 或无原因**，故仍需落码。

### 4.5 P5 核实结论与落地风险（2026-10-05 20:2x 小欧核实更新）

**核实方法**：`grep` 全仓 `total_lines` 出现点，逐一比对 LLM text 实际呈现路径。

**核实结论（修正初判）**：`_METRICS_RENDERED_BY_HANDLER`（observation_formatter.py:134）中列 `total_lines/page_count` **是正确的防重复设计**，并非遗漏——三处 handler 均已各自呈现：

| 工具 | total_lines 呈现路径 | 依据 |
|------|---------------------|------|
| read_text_file | summary 的 `{line_count}/{total_lines}行`（如 `2/1167行`） | L129 模板 + 实测输出 |
| read_pdf/read_docx/clipboard | `_format_text_content` 的 hint `共 {total_lines} 行，用 offset/limit 分段读取剩余` | observation_formatter.py:408-410 |
| read_docx | summary 直带 total_lines（注释「metrics+summary 传递给 LLM」） | read_docx.py:186 注释 |

故 formatter 统计段跳过 `total_lines` 可保持「LLM text 中每处数字只出现一次」的单通道原则，**现状无漏（P5 原判撤销）**。

**落地风险（关键在 3.2 单通道实施后）**：若按 §3.2 把 read_text_file 的 summary 改为去数字，则 `total_lines` 既不靠 summary 呈现，也不被 formatter 统计段渲染 → **新 P5 正式成立**。故 §4.6（read_text_file summary 去数字化）**必须配套**：在 read_text_file 的 metrics 中保留 `total_lines`，并把该键移出 `_METRICS_RENDERED_BY_HANDLER`（或在 read_text_file 的 data 详情里主动呈现 `共 N 行`），二选一，保证 `total_lines` 迁移不丢。

**实施要求**：P5 不再单列落码项；§4.6（read_text_file 去数字化）若要落地，必须把 `total_lines` 的呈现归属一并迁移（metrics 渲染或 handler 自呈现），缺一不可。

---

（2026-10-05 22:1x 小欧 裁定：P4 time_now error summary 不动——北京老陈明确现状已够用，detail 已渲染真因，summary 留泛词即可，避免过度设计。第六章第 3 条待裁定随之取消。）

### 4.6 read_text_file summary 去 `/{total_lines}`（已实施，2026-10-05）

按 §3.2 单通道原则，read_text_file 的两分支 summary 已从 `{n}/{total}行` 改为 `{n}行`；message 同步去掉 `,共{total_lines}行`（保留 `{_ps}第{start}-{end}行` 区间供 LLM 定位，不与 metrics 冲突）。`total_lines` 已迁入 metrics 统计段通用渲染（`total_lines: 1167行`，实测在 LLM text 中恰一次）。
`offset/limit/encoding` 入参段（`{_ps}`）保留在 summary/message（行区间供 LLM 翻页定位用；`_ps` 由 `action.params` 同源，target 派生另有 path）。

---

## 五、公共函数改动（按裁定：本章替换原三堂会审内容）

> 本章登记**不属于单个 tool、需集中处理的公共函数**改动，避免在 4.4 的 51 个 tool 小节里重复。
> 回答"共有函数要处理的在哪"：就在本章。

### 5.1 observation_formatter.py（核心公共渲染层）

#### 5.1.1 `_METRICS_RENDERED_BY_HANDLER`（L134）—— 本轮唯一必改公共函数
- **现状**：`frozenset({"total_lines", "page_count"})`，统计段通用渲染时跳过这两键，防与 handler 自呈现重复。
- **核实结论**（4.5 已详述）：这是**正确的防重复设计**，三处 handler 均已各自呈现 `total_lines`。
- **本轮改动（硬要求）**：4.6/4.4.1 的 read_text_file summary 去数字化后，`total_lines` 既不靠 summary 呈现，又被本跳集合跳过 → **会从 LLM text 中消失**。必须二选一迁移：
  - **方案 A（推荐，单一呈现源最省 token）**：从本集合移除 `total_lines`，靠统计段渲染。前置条件：①同步移除 read_text_file/read_docx summary 的 `N/M行`（4.4.1 已含）；②确认 `_format_text_content` 的 hint「共 N 行」是否会与统计段双出（若会，须一并从 hint 移除）。
  - **方案 B**：保留跳集合，在 read_text_file 的 data 详情段主动呈现 `共 N 行`。
- **`page_count` 保持不动**（read_pdf/read_docx 自呈现，无同类风险）。

#### 5.1.2 metrics 通用渲染（L717-738）—— 不动
新增 metrics 键（`output_len`/`stderr_len`/`moved_bytes`/`moved_count`/`size`/`mime_type` 等）**零改动即生效**。仅需注意 `OBS_METRICS_MAX_ITEMS` 上限：本轮各 tool 的 metrics 项数均 ≤6，不会触顶。

#### 5.1.3 `_format_llm_data` 观察行去叠字（L696-702）—— 不动
message 与 summary 以 ` - ` 拼接、summary 以 message 开头时取一。本轮各 tool 的 summary 与 message 不同源（message 为泛词），不触发去叠字。

#### 5.1.4 `_tool_target`（L161-180）—— 不动
target 从 `action.params` 按 6 规范名派生（path/source/url/sql/query/command）。本轮 51 个 tool 的目标参数均在此列，无新增键需求。

#### 5.1.5 `format_data_detail` / `format_data_detail` 错误诊断补充（L784-802）—— 不动
error 时按 detail 覆盖情况补 `诊断补充`。本轮只改 summary，不影响该链路。

### 5.2 tool_response.py —— 不动
`build_success/build_error/build_warning` 统一返回 `{data, llm_data, other_data}`。本轮只改各 tool 内部 `llm_data` 内容，不改响应骨架。

### 5.3 tool_retry_engine.py（L306）—— 需改（B 类）
- **现状**：`"summary": f"工具 '{action}' 未找到"`——error summary 无原因。
- **改法**：summary 保持（操作+目标已合规），确认该分支 `status.detail` 已填原因；若未填则补。

### 5.4 公共函数改动清单（实施时按此核对）

| 公共函数 | 是否改动 | 关联 tool 小节 |
|---------|----------|--------------|
| `observation_formatter._METRICS_RENDERED_BY_HANDLER` | **必改**（total_lines 呈现迁移） | 4.6 / 4.4.1 read_text_file |
| `observation_formatter` metrics 通用渲染（L717-738） | 不改 | 全部 |
| `observation_formatter._format_llm_data` 观察行 | 不改 | 全部 |
| `observation_formatter._tool_target` | 不改 | 全部 |
| `observation_formatter.format_data_detail` | 不改 | 全部 |
| `tool_response` 响应骨架 | 不改 | 全部 |
| `tool_retry_engine` error summary | 改（确认 detail 已填） | 4.4.10 |

### 5.5 三堂会审要点（保留结论，详见 AGENTS 编码铁规 §1.2）

- **合规**：summary/message/detail/metrics 各司其职（SRP）；metrics 渲染复用既有通用函数不重写（DRY/复用优先）；仅扩 metrics 字典与 summary f-string，无新抽象（KISS-DIRECT/YAGNI）；无 backward 兼容残留（禁 backward）。
- **合理**：warning 去冗余后 `_warn_msg` 收口到 detail，summary 只留操作+目标+状态，无中间透传。
- **关联**：新增 metrics 键零改动 formatter 即生效；`page_count` 不动无重复风险；move/rename 的统计量需在实现处顺手取（不引入新依赖）。

---

## 六、已定决策（2026-10-05 小欧复核定稿，非待裁定）

1. **metrics 键命名定为**：`output_len` / `stderr_len`（shell）；`moved_bytes` / `moved_count`（move）；`size`（rename）；`duration_sec`（send_notification）；`mime_type`（read_media_file）；`changed`（rename 同名分支）；`deleted_count`/`skipped_count`（delete_file）。风格与仓库既有 `bytes`(read_media_file)、`total_lines`、`page_count`、`exit_code`、`lines` 一致：小写下划线 + 语义明确。
2. **move/rename 取值口径定为**：source 为**单文件** → 目标侧 `os.path.getsize` 字节数；source 为**目录** → `moved_count=1`（不递归累计字节，避免大目录统计拖慢）；rename 的 `size` = 重命名后目标文件 `os.path.getsize`；同名无操作分支 `size` 取原文件且 `changed=0`（表示未改动）。
3. ~~time_now~~ —— 不改（北京老陈裁定，见 2.2 与 4.4.2）。
4. **落地顺序铁律**：§5.1.1 的 `_METRICS_RENDERED_BY_HANDLER`（`total_lines` 迁移）**必须与 4.4.1 read_text_file 去数字化同批落码**，否则 `total_lines` 从 LLM text 消失；不可分两批。

---

## 七、实施后验证（待实施时执行）

1. `execute_shell_command` success/warning/error 三分支各跑一次，断言 `metrics` 含 `exit_code`+`output_len`（success）/`stderr_len`（warning），且 summary 不含任何数字、不嵌 `_warn_msg`。
2. `move_file`/`rename_file` success 跑一次，断言 `metrics` 非空（`moved_bytes`/`moved_count`、`size`），且 **summary 不含字节/数量数字**（单通道）。
3. `read_text_file` offset/limit 跑一次，断言 summary == `读取文件{path}，成功`（无数字），且 `format_llm_observation` 产出中 **`total_lines` 恰好出现一次**（统计段或 hint，不得双出、不得消失）。
4. 抽 5 个 A 类 tool（compress_files/delete_file/timer_list/search_web/list_directory）各跑一次，断言：summary 无量化数字、对应数字在 `统计:` 段可见。
5. 抽 5 个 B 类 tool（analyze_data/write_docx/write_xlsx/window_info/tool_search）各跑一次 error/warning，断言 summary 不含 detail 正文、`✖ 错误:`/`⚠ 警告:` 行承载真因。
6. 全量回归：`pytest tests/tools/param_combination -q` 全绿（断言 summary 文案的 case 需同步更新）。
