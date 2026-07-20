# -*- coding: utf-8 -*-
# 编辑历史:
# 记录 2026-07-13 小欧 观测格式化兜底WARNING降级DEBUG并加非dict防御
# 记录 2026-07-14 小沈 grep匹配内容与上下文行截断防OOM
# 记录 2026-07-15 小欧 常量归一化治理: snippet/HTML摘要/sysinfo字段截断改引用tool_constants, 功能零退化
# 记录 2026-07-17 小欧 修复_format_items丢弃url: 原if desc/elif url二选一在有snippet时丢弃url, 致searchweb等"搜索→打开"工作流LLM拿不到URL无法fetchpage而空转(实测task-2ffbc517: 28分钟/1922s/11次LLM调用/重复63%); 改为desc与url并存输出(url为fetchpage必需入参), 功能零退化
# 2026-07-18 小欧 修正注释与fallback顺序一致
# 2026-07-20 小欧 _format_matches 改行×列(200行/150字符): 累计渲染行超出上限则截断并在末尾追加两态说明(有截断⚠已截断/无截断✓无截断-完整); 单行超宽尾部截断, 解决旧逻辑按单串10000字符截断致内容过大被整体丢弃、LLM 看不到匹配结果的问题
# 2026-07-20 小欧 _format_matches 无截断时仅输出"✓ 无截断-完整"一行, 不再附加冗余截断明细; 有截断明细行去除多余花括号与错配标点
# 2026-07-20 小欧 _format_shell_result 改行×列(200行/1000字符): 仿 _format_matches 截断收口, 末尾追加两态说明(有截断⚠已截断/无截断✓无截断-完整); 删除 OBS_MAX_STRING_LENGTH 单串截断, 解决 shell 长输出被盲截尾部问题
# 2026-07-20 小欧 _format_fetchpage_result 新增(fetchpage 专属行×列 OBS_FETCHPAGE_MAX_ROWS=200/OBS_FETCHPAGE_MAX_ROW_CHARS=500 + 两态说明); #2 raw str handler 按 action.tool=="fetchpage" 分流, readtext 维持 OBS_MAX_STRING_LENGTH 不变
# 2026-07-20 小欧 _format_readtext_result 新增(readtext 专属行×列 OBS_READTEXT_MAX_ROWS=200/OBS_READTEXT_MAX_ROW_CHARS=1000 + 两态说明); #2 raw str handler 按 action.tool=="readtext" 分流, OBS_MAX_STRING_LENGTH 退为未知 content 工具兜底
"""
observation_formatter — 工具结果格式化为LLM observation文本

【Phase 1 v6.0 重写 — 小欧 2026-06-21】
format_llm_observation 改为 (data, llm_data) 签名，三段式输出
新增 format_data_detail 按 data 类型自动渲染可读文本
删除旧函数: _extract_display_data/_append_data/_format_summary_parts/
  build_execution_result_dict/extract_status/_format_result_observation/
  _format_success_observation/_format_warning_observation/_format_error_observation/
  _build_base_text/_append_warning/_append_hint/_prevent_json_oom/_get_failure_hint

设计原则:
- 工具返回原始data，不做截断（工具层如果有 need_full_data=True，完整数据走 other_data）
- 安全兜底:format_data_detail加try-except确保不崩
- 三段式:观察行 + 结果行 + 详情行
- 【铁规 v2】observation_formatter 做安全截断（防 LLM observation 过大），
-   完整数据由前端 yield 层 + other_data 承载。截断常量见 tool_constants.py

工具 → handler 映射（全部 63 个工具）:
 工具            data 键                        命中 handler              formatter上限(机器二)                  tool上限(机器一)
  ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
  readtext        {content: str}                 #2-readtext              OBS_READTEXT_MAX_ROWS=200/OBS_READTEXT_MAX_ROW_CHARS=1000  INER_READTEXT_READ_SIZE=10MB保留为3.4硬安全网(文件过大拒绝, 不截断)
  fetchpage       {content: str}                 #2-fetchpage             OBS_FETCHPAGE_MAX_ROWS=200/OBS_FETCHPAGE_MAX_ROW_CHARS=500  WEB_FETCH_MAX_CHARS 已删除(正文零截断, 显示域行×列收口)
  edittext        {diff: str}                    #24 edittext             OBS_EDITTEXT_MAX_ROWS=200/OBS_EDITTEXT_MAX_ROW_CHARS=1000  INER_EDITTEXT_READ_SIZE=10MB保留为3.4硬安全网(文件过大拒绝, 不截断); diff 零截断, 显示域行×列收口
  writetext       {content_preview: str}          #23 writetext           Tool 层 _build_content_preview 文首50+文末50 预览(用户裁定恢复); 简单拼接 "已写入内容\n"+preview, 无 OBS_WRITETEXT_*(无截断/无死代码)
  clipboard_ctl   {text: str}                    #10 raw text             OBS_MAX_STRING_LENGTH=10000          N/A
  read_pdf        {text: str, ...}               #10 raw text             OBS_MAX_STRING_LENGTH=10000          页数不限
  read_docx       {text: str, ...}               #10 raw text             OBS_MAX_STRING_LENGTH=10000          字符数不限
  read_xlsx       {{headers, rows}}              #2b flat _format_table   行: OBS_MAX_DISPLAY_ITEMS=500         max_rows=10000
  query_sql       {columns, rows}                #5 _format_rows          行: OBS_MAX_DISPLAY_ITEMS=500         limit=50
  filter_data     {columns, rows}                #5 _format_rows+columns  行: OBS_MAX_DISPLAY_ITEMS=500         top_n(用户指定,无默认)
  listdir         {entries}                      #3 _format_entries       项: OBS_MAX_DISPLAY_ITEMS=500         LISTDIR_PAGE_SIZE=500
  find            {matches}                      #9b _format_find_results 项: OBS_FIND_MAX_ROWS=200        返回全部匹配(deadline超时保护), 显示域行×列收口
  grep            {matches}                      #9 _format_matches       项: OBS_MAX_DISPLAY_ITEMS=500         上限500(=OBS_MAX_DISPLAY_ITEMS,条目数)
  searchweb       {items}                        #4 _format_items         项: OBS_SEARCHWEB_MAX_ROWS=200     返回全部(num_results≤50); 显示域行×列(snippet 500字符)
  event_log       {events}                       #8 _format_events        条: OBS_MAX_DISPLAY_ITEMS=500         max_events=50
  searchtool      {matches}                      #9c _format_searchtool   项: OBS_MAX_DISPLAY_ITEMS=500         small(内置)
  get_db_schema   {tables}                       #6 _format_schema        张表: OBS_MAX_DISPLAY_ITEMS=500       不限
  shell           {stdout, stderr, ...}          #11 shell stdout         OBS_MAX_STRING_LENGTH=10000          不限
  timer_list      bare list                      non-dict str()           N/A                                  N/A
  list_tasks      {tasks, ...}                   #14 tasks table          行: OBS_MAX_DISPLAY_ITEMS=500         max_results=100
  window_info     {windows}                      #15 windows table        行: OBS_MAX_DISPLAY_ITEMS=500         不限
  read_pptx       {slide_count, slides}           #16 slides items        页: OBS_MAX_DISPLAY_ITEMS=500         页数不限
  sysinfo         {basic, cpu, ...}               #17 sysinfo sections     每段10项                             不限
  compress        {compression_ratio, ...}        _format_compress_result  OBS_MAX_STRING_LENGTH=10000          N/A
  httpget         {status_code, ...}              _format_httpget_result   OBS_HTTPGET_MAX_ROWS=200/OBS_HTTPGET_MAX_ROW_CHARS=2000  N/A
  analyze_data    {statistics, ...}               _format_analyze_data     转置表格(无行数限制)                    top_n(用户指定,默认None)
   ── _format_scalar_data ──
   36 tools        {key: scalar, ...}              _format_scalar_data     OBS_MAX_STRING_LENGTH=10000(值)       N/A
                                                                           OBS_DICT_MAX_KEYS=100(键)

【注意】listdir 的 offset 分页由工具层自行处理（tools/file/）, formatter 仅展示当前 page;
  find 自 2026-07-20 起返回全部匹配(offset 仅作跳过, 无条数上限), formatter 按 OBS_FIND_MAX_ROWS 行×列收口。

Author: 小欧 2026-06-21; 小欧 2026-07-04 更新映射表; 小欧 2026-07-05 修复4个Bug, 新增专用handler分组; 小欧 2026-07-05 拆分compress/httpget/analyze_data专用handler
  小欧 2026-07-20 章12 edittext 专属handler(#24 _format_edittext_result + OBS_EDITTEXT_MAX_ROWS/CHARS + 两态说明); edittext 由#21 fallback移出为专属handler; 映射表/截断对照表同步
  小欧 2026-07-20 章13 readmedia 专属handler(#13 _format_readmedia_result); base64 为二进制编码非可读文本, 用户裁定不按文本行×列处理, 回退为仅元数据+base64字符数摘要(原行为), 不新增 OBS_READMEDIA_*(避免死代码); INER_READMEDIA_READ_SIZE 保留3.4硬安全网
   小欧 2026-07-20 章14 用户裁定回退: writetext 恢复 Tool 层 content_preview 预览(文首50+文末50, _build_content_preview), #23 专属简单拼接 "已写入内容\n"+preview(无 OBS_WRITETEXT_* 截断/无死代码); OBS_WRITETEXT_* 删除; WRITE_TEXT_MAX_CHARS 仍依3.6删除(入参长度限制)
"""

import json
import re
from typing import Any, Dict, Optional

from app.logger import logger
from app.tools.tool_constants import (
    OBS_MAX_DISPLAY_ITEMS,
    OBS_MAX_STRING_LENGTH,
    OBS_DICT_MAX_KEYS,
    OBS_HTML_SUMMARY_MAX_CHARS,
    OBS_SYSINFO_FIELD_MAX_CHARS,
    OBS_GREP_MAX_ROWS,
    OBS_GREP_MAX_ROW_CHARS,
    OBS_SHELL_MAX_ROWS,
    OBS_SHELL_MAX_ROW_CHARS,
    OBS_FIND_MAX_ROWS,
    OBS_FIND_MAX_ROW_CHARS,
    OBS_SEARCHWEB_MAX_ROWS,
    OBS_SEARCHWEB_MAX_ROW_CHARS,
    OBS_HTTPGET_MAX_ROWS,
    OBS_HTTPGET_MAX_ROW_CHARS,
    OBS_FETCHPAGE_MAX_ROWS,
    OBS_FETCHPAGE_MAX_ROW_CHARS,
    OBS_READTEXT_MAX_ROWS,
    OBS_READTEXT_MAX_ROW_CHARS,
    OBS_EDITTEXT_MAX_ROWS,
    OBS_EDITTEXT_MAX_ROW_CHARS,
)


def _truncation_msg(llm_data: dict = None) -> str:
    """工具类型感知的截断消息 — 小沈 2026-07-08"""
    if llm_data:
        tool = llm_data.get("action", {}).get("tool", "")
        if tool in ("readtext", "edittext"):
            return "\n... (截断，完整内容见文件)"
    return "\n... (截断)"



def format_data_detail(data: Any, llm_data: dict = None) -> str:
    """按data结构类型自动格式化为可读文本 — 小欧 2026-06-21 — 小欧 2026-07-06 加llm_data参数供部分handler使用

    内部可能抛异常，兜底 JSON dump 或 str() 确保不崩。
    """
    if not data:
        return ""

    # =========================================================================
    # 截断对照表：工具层截断(机器一) vs formatter层截断(机器二)
    # 更新日期: 2026-07-06 小欧 (验证确认)
    # =========================================================================
    #
    # handler          工具                              工具上限(机器一)                      formatter上限(机器二)
    # ────────────────  ───────────────────────────────  ──────────────────────────────────  ──────────────────────────────────────
    # non-dict          timer_list                       无限制                             直接 str()，无截断
    # #2 raw str        readtext                         无行数限制(仅INER_READTEXT_READ_SIZE=10MB)  OBS_MAX_STRING_LENGTH=10000
    # #2-readtext      readtext                         无行数限制(仅INER_READTEXT_READ_SIZE=10MB, 3.4拒绝)  OBS_READTEXT_MAX_ROWS=200/OBS_READTEXT_MAX_ROW_CHARS=1000
    # #2-fetchpage     fetchpage                        正文零截断(无 Tool 层上限)            OBS_FETCHPAGE_MAX_ROWS=200/OBS_FETCHPAGE_MAX_ROW_CHARS=500
    # #24 edittext     edittext                         diff 零截断(仅INER_EDITTEXT_READ_SIZE=10MB, 3.4拒绝)  OBS_EDITTEXT_MAX_ROWS=200/OBS_EDITTEXT_MAX_ROW_CHARS=1000
    # #23 writetext    writetext                       content_preview 为 Tool 层预览(文首50+文末50), 简单拼接 "已写入内容\n"+preview; 无 formatter 截断(无 OBS_WRITETEXT_*)
    # #10 raw text      read_pdf, read_docx, clipboard_ctl 页数/字符数不限                    OBS_MAX_STRING_LENGTH=10000
    # #3 entries        listdir                          LISTDIR_PAGE_SIZE=500                OBS_MAX_DISPLAY_ITEMS=500
    # #4 items          searchweb                         返回全部(num_results≤50); 显示域行×列   OBS_SEARCHWEB_MAX_ROWS=200/CHARS=500
    # #2b flat table    read_xlsx                         max_rows=10000                      OBS_MAX_DISPLAY_ITEMS=500
    # #5 rows           query_sql                         limit=50                            OBS_MAX_DISPLAY_ITEMS=500
    #                   filter_data                       top_n(用户指定,无默认值)              OBS_MAX_DISPLAY_ITEMS=500
    # #6 schema         get_db_schema                     不限                                OBS_MAX_DISPLAY_ITEMS=500
    # #8 events         event_log                         max_events=50                       OBS_MAX_DISPLAY_ITEMS=500
    # #9 matches        grep                              上限500(=OBS_MAX_DISPLAY_ITEMS,条目数)   OBS_MAX_DISPLAY_ITEMS=500
    #                   find                              返回全部匹配(deadline超时)        OBS_FIND_MAX_ROWS=200/CHARS=300
    #                   searchtool                        小(内置)                            OBS_MAX_DISPLAY_ITEMS=500
    # #11 shell stdout  shell                             不限                                OBS_MAX_STRING_LENGTH=10000
    # #12 tree          tree                              不限                                无特定截断(嵌套渲染)
    # #13 readmedia     readmedia                         INER_READMEDIA_READ_SIZE=50MB         仅元数据+base64字符数摘要(不按文本行×列, base64非可读文本)
    # #14 tasks table   list_tasks                        max_results=100                     OBS_MAX_DISPLAY_ITEMS=500
    # #15 windows table window_info                       不限                                OBS_MAX_DISPLAY_ITEMS=500
    # #16 slides items  read_pptx                         页数不限                            OBS_MAX_DISPLAY_ITEMS=500
    # #17 sysinfo       sysinfo                           不限                                每段10项
    # #0 空data         mouse_click                       N/A                                直接返回""
    # #18 compress      compress                          N/A                                OBS_MAX_STRING_LENGTH=10000
    # #19 httpget       httpget                           N/A                                OBS_HTTPGET_MAX_ROWS=200/OBS_HTTPGET_MAX_ROW_CHARS=2000
    # #2-fetchpage     fetchpage                        正文零截断(无 Tool 层上限)            OBS_FETCHPAGE_MAX_ROWS=200/OBS_FETCHPAGE_MAX_ROW_CHARS=500
    # #20 analyze_data  analyze_data                      top_n(用户指定,默认None)             转置表格(无行数限制)
    # #21 fallback      33个scalar工具(见下方清单)          N/A                                OBS_MAX_STRING_LENGTH=10000(值)
    #                                                                                        OBS_DICT_MAX_KEYS=100(键)
    #
    # 说明:
    #   工具上限(机器一) = tool函数内部主动截断后返回data。
    #   formatter上限(机器二) = observation_formatter对data二次截断后再格式化。
    #   两者取"都截断则先到先得"：工具先截→formatter再截→最终observation文本。
    #   若工具上限 < formatter上限，最终长度由工具决定(如searchweb 50项 vs formatter 500)。
    # =========================================================================
    # 与下方 fallback 实际分发顺序一致 — 小欧 2026-07-18
    # _format_scalar_data 覆盖全部 scalar 工具（与下方 fallback 实际分发顺序一致）
    #   which, download, ping_port, write_docx, write_xlsx, write_pdf, write_pptx,
    #   timenow, timeadd, timediff, calendar, notify, execute_sql, generate_chart,
    #   create_task, delete_task, timer_set, timer_clear,
    #   registry_read, registry_write, registry_delete,
    #   window_focus, window_resize, set_window_state,
    #   mouse_move, mouse_scroll, mouse_position,
    #   keyboard_control, screen_capture
    try:
        # ── non-dict — 1 tool: timer_list (bare list) ──
        if not isinstance(data, dict):
            return str(data)

        # ── #2 raw str — readtext / #2-fetchpage — fetchpage ──
        if "content" in data and isinstance(data["content"], str):
            _tool = (llm_data or {}).get("action", {}).get("tool", "")
            if _tool == "fetchpage":
                return _format_fetchpage_result(data["content"], llm_data)
            if _tool == "readtext":
                return _format_readtext_result(data["content"], llm_data)
            content = data["content"]
            if len(content) > OBS_MAX_STRING_LENGTH:
                content = content[:OBS_MAX_STRING_LENGTH] + _truncation_msg(llm_data)
            return content

        # ── #10 raw text — 3 tools: read_pdf, read_docx, clipboard_ctl ──
        if "text" in data and isinstance(data["text"], str):
            return _format_text_content(data, llm_data)

        # ── #3 entries — 1 tool: listdir ──
        if "entries" in data:
            return _format_entries(data["entries"])

        # ── #4 items — 1 tool: searchweb ──
        if "items" in data:
            return _format_items(data["items"])

        # ── #2b flat table — 1 tool: read_xlsx (含CSV) ──
        if "headers" in data and "rows" in data:
            return _format_table(data["headers"], data["rows"])

        # ── #5 rows — 2 tools: query_sql, filter_data ──
        if "rows" in data:
            return _format_rows(data["rows"], data.get("columns"))

        # ── #6 schema — 1 tool: get_db_schema ──
        if "tables" in data:
            return _format_schema(data["tables"])

        # ── #8 events — 1 tool: event_log ──
        if "events" in data:
            return _format_events(data["events"])

        # ── #9 matches — 3 tools: grep(file+line), find(path), searchtool(category) ──
        if "matches" in data:
            ms = data["matches"]
            if ms and isinstance(ms[0], dict):
                if "file" in ms[0]:
                    return _format_matches(ms)
                elif "category" in ms[0]:
                    return _format_searchtool_results(ms)
                elif "path" in ms[0]:
                    return _format_find_results(ms)
            return _format_matches(ms)

        # ── #11 shell stdout — 1 tool: shell ──
        if "stdout" in data:
            return _format_shell_result(data, llm_data)

        # ── #12 tree — 1 tool: tree ──
        if "tree" in data and isinstance(data.get("tree"), dict):
            return _format_tree(data)

        # ── #13 readmedia — 1 tool: readmedia ──
        if "base64_data" in data:
            return _format_readmedia_result(data, llm_data)

        # ── #14 tasks — 1 tool: list_tasks ──
        if "tasks" in data:
            return _format_tasks(data)

        # ── #15 windows — 1 tool: window_info ──
        if "windows" in data:
            return _format_windows(data)

        # ── #16 slides — 1 tool: read_pptx ──
        if "slides" in data:
            return _format_slides(data, llm_data)

        # ── #17 sysinfo — 1 tool: sysinfo ──
        if "basic" in data and isinstance(data["basic"], dict):
            return _format_sysinfo(data)

        # ── #18 compress — 1 tool: compress ──
        if "compression_ratio" in data:
            return _format_compress_result(data)

        # ── #19 httpget — 1 tool: httpget ──
        if "status_code" in data:
            return _format_httpget_result(data)

        # ── #20 analyze_data — 1 tool: analyze_data ──
        if "statistics" in data or "grouped_statistics" in data:
            return _format_analyze_data(data)

        # ── #24 edittext — 1 tool: edittext（diff 专属行×列 + 两态） ──
        if "diff" in data:
            return _format_edittext_result(data["diff"], llm_data)

        # ── #23 writetext — 1 tool: writetext（content_preview 简单拼接; Tool 层已生成预览, 不截断/无 OBS_WRITETEXT_*） ──
        if "content_preview" in data:
            return "已写入内容\n" + data["content_preview"]

        # ── #22 which result — 1 tool: which ──
        if "paths" in data:
            return _format_which_result(data)

        # ── #0 空data — 1 tool: mouse_click（走第 72 行 if not data: return ""）────
        # ── #21 fallback — 33 tools（排除which/edittext/writetext） ──
        #   move, copy, delete, rename, extract,
        #   download, ping_port, write_docx, write_xlsx, write_pdf, write_pptx,
        #   timenow, timeadd, timediff, calendar, notify, execute_sql, generate_chart,
        #   create_task, delete_task, timer_set, timer_clear,
        #   registry_read, registry_write, registry_delete,
        #   window_focus, window_resize, set_window_state,
        #   mouse_move, mouse_scroll, mouse_position,
        #   keyboard_control, screen_capture
        return _format_scalar_data(data)
    except Exception as e:
        # 已兜底恢复, 非致命: 降级为DEBUG避免噪声(原WARNING) — 小欧 2026-07-13
        logger.debug(f"[observation_formatter] format_data_detail handler failed({type(e).__name__}): {e}")
        try:
            return json.dumps(data, ensure_ascii=False, indent=2)
        except Exception:
            return str(data)


# #10 raw text 样式:
#   输入: {"text": "这是文档正文...", "page_count": 5, "metadata": {...}}
#   输出: 这是文档正文...\npage_count=5, metadata={'author': '...'}
def _format_text_content(data: dict, llm_data: dict = None) -> str:
    """#10 text handler — read_pdf/read_docx 正文直接展示 — 小欧 2026-07-05 — 小沈 2026-07-08 工具感知截断消息 — 小欧 2026-07-10 fix: extra字段长度截断"""
    content = data["text"]
    if len(content) > OBS_MAX_STRING_LENGTH:
        content = content[:OBS_MAX_STRING_LENGTH] + _truncation_msg(llm_data)
    extra = {k: v for k, v in data.items() if k != "text"}
    if extra:
        parts = []
        for k, v in extra.items():
            if isinstance(v, list):
                if len(v) > 5:
                    parts.append(f"{k}: {len(v)}项")
                else:
                    parts.append(f"{k}={v}")
            else:
                v_str = str(v)
                if len(v_str) > OBS_MAX_STRING_LENGTH:
                    v_str = v_str[:OBS_MAX_STRING_LENGTH] + "..."
                parts.append(f"{k}={v_str}")
        content += "\n" + ", ".join(parts)
    return content


# #11 shell stdout 样式:
#   输入: {"stdout": "total 42\n-rw-r--r-- 1 root root 1024 ...", "stderr": "", "returncode": 0, "shell_type": "powershell", "duration_ms": 150}
#   输出: total 42\n-rw-r--r-- 1 root root 1024 ...\n---\n[rc=0, powershell, 150ms]
def _format_shell_result(data: dict, llm_data: dict = None) -> str:
    """#11 shell handler — 行×列(200×1000): 自由文本档, 长日志/JSON 原样保头部, 不盲截尾部
    小欧 2026-07-05 初版; 小欧 2026-07-06 returncode从llm_data.metrics取;
    小欧 2026-07-20 改行×列(200×1000)+截断说明行两态(Tool 输出不截断, 仅显示域按行×列收口, 见 6.4)"""
    stdout = data.get("stdout", "") or ""
    stderr = data.get("stderr", "") or ""
    if not stdout and not stderr:
        return ""
    max_rows = OBS_SHELL_MAX_ROWS
    max_chars = OBS_SHELL_MAX_ROW_CHARS
    # 第一遍：按行构建全部渲染行，并统计超宽行数（用于截断说明行）
    all_rows = []
    overwide = 0

    def _clip(text: str) -> str:
        nonlocal overwide
        if len(text) > max_chars:
            overwide += 1
        return text[:max_chars]

    if stdout:
        for line in stdout.split("\n"):
            all_rows.append(_clip(line))
    if stderr:
        for line in stderr.split("\n"):
            all_rows.append(_clip(f"⚠ {line}"))
    total = len(all_rows)
    truncated = total > max_rows
    shown = all_rows[:max_rows]
    # metadata 一行（始终保留, 不参与行数截断）
    rc_info = (llm_data or {}).get("metrics", {}).get("exit_code", {})
    returncode = rc_info.get("value", "?")
    shell_type = data.get("shell_type", "") or "powershell"
    duration_ms = data.get("duration_ms", 0)
    meta = f"[rc={returncode}, {shell_type}, {duration_ms}ms]"
    shown.append(f"---\n{meta}")
    if truncated:
        shown.append("⚠ 已截断")
        shown.append("截断情况：保留%d行,实际 %d 行，截断 %d 行；单行上限 %d 字符（超宽 %d 行尾部截断）" % (max_rows, total, total - max_rows, max_chars, overwide))
    else:
        shown.append("✓ 无截断-完整")
    return "\n".join(shown)


def _format_which_result(data: dict) -> str:
    """#22 which handler — 路径逐行展示 — 小欧 2026-07-06"""
    paths = data.get("paths", [])
    lines = [f"  路径[{i+1}]: {p}" for i, p in enumerate(paths) if p]
    return "\n".join(lines)


# #12 tree 样式:
#   输入: {"tree": {"name": "project", "children": [{"name": "src", "children": [{"name": "main.py", "size": 1024}]}]}, ...}
#   输出: project\n  └── src\n      └── main.py  (1024 bytes)\n---\n[1 files, 1 dirs, 1024 bytes total]
def _format_tree(data: dict) -> str:
    """#12 tree handler — 嵌套dict → 可视化树形字符串 — 小欧 2026-07-05"""
    tree = data.get("tree", {})
    stats = data.get("statistics", {})
    if not tree or not isinstance(tree, dict):
        return ""
    lines = []

    def _render(node: dict, prefix: str = "", is_last: bool = True) -> list:
        if not node or not isinstance(node, dict):
            return []
        result = []
        name = node.get("name", "?")
        size = node.get("size")
        label = "/" if size is None else f"  ({size} bytes)"
        children = node.get("children", [])
        result.append(f"{prefix}{'└── ' if is_last else '├── '}{name}{label}")
        if children:
            child_prefix = prefix + ("    " if is_last else "│   ")
            for i, child in enumerate(children):
                result.extend(_render(child, child_prefix, i == len(children) - 1))
        return result

    root_name = tree.get("name", "root") if isinstance(tree, dict) else str(tree)
    lines.append(f"{root_name}")
    children = tree.get("children", []) if isinstance(tree, dict) else []
    for i, child in enumerate(children):
        lines.extend(_render(child, "", i == len(children) - 1))

    if stats:
        fc = stats.get("file_count", 0)
        dc = stats.get("dir_count", 0)
        ts = stats.get("total_size", 0)
        lines.append(f"---\n[{fc} files, {dc} dirs, {ts} bytes total]")
    if len(lines) == 1 and not children and not stats:
        return ""
    return "\n".join(lines)


# #13 readmedia 样式:
#   输入: {"file_name": "photo.jpg", "mime_type": "image/jpeg", "file_size": 204800, "base64_data": "/9j/4AAQ..."}
#   输出: photo.jpg [image/jpeg, 204800 bytes] [base64: 273104 chars]
def _format_readmedia_result(data: dict, llm_data: dict = None) -> str:
    """readmedia 媒体文件 — 2026-07-20 门限治理(章13.4): 仅元数据 + base64 字符数摘要
    base64 为二进制编码, 非可读文本, 不可按文本行×列处理(LLM 无法消费截断 base64, 且体积大浪费 token);
    Tool 输出零截断(3.7); observation 仅渲染元数据摘要, 不展开 base64(6.4)。"""
    name = data.get("file_name", "?")
    mime = data.get("mime_type", "?")
    size = data.get("file_size", 0)
    b64 = data.get("base64_data", "")
    if name == "?" and mime == "?" and size == 0 and not b64:
        return ""
    b64_summary = f" [base64: {len(b64)} chars]" if b64 else ""
    return f"{name} [{mime}, {size} bytes]{b64_summary}"


# format_llm_observation 精简输出样式 — 小沈 2026-07-06
#   输入: data={...工具返回data...}, llm_data={"status":{"exec_code":"success","message":"文件已保存"},"action":{"tool_zh":"写文本文件"},"summary":"已写入 test.txt"}
#   输出: 观察: 写文本文件 - 文件已保存 - 已写入 test.txt\n  详情: \n  path: /tmp/test.txt\n  size: 1024
# 【旧版 v1 — 观察+结果+统计+建议 — 小欧 2026-07-06 → 2026-07-06 注释保留】
# def _format_llm_data(llm_data: Dict) -> str:
#     status = llm_data.get("status", {})
#     action = llm_data.get("action", {})
#     summary = llm_data.get("summary", "")
#     exec_code = status.get("exec_code", "success")
#     message = status.get("message", "")
#     tool_zh = action.get("tool_zh", "")
#     err_code = status.get("code", "")
#     metrics = llm_data.get("metrics", {}) if isinstance(llm_data.get("metrics"), dict) else {}
#     duration_ms = llm_data.get("duration_ms", 0)
# 
#     if exec_code == "success":
#         text = f"观察: {message} - {tool_zh}"
#     elif exec_code == "warning":
#         code_suffix = f" [{err_code}]" if err_code else ""
#         text = f"观察: {message} - {tool_zh}{code_suffix}\n⚠ 警告: {status.get('detail', '')}"
#     else:
#         code_suffix = f" [{err_code}]" if err_code else ""
#         text = f"观察: {message} - {tool_zh}{code_suffix}\n✖ 错误: {status.get('detail', '')}"
# 
#     if summary:
#         action_info = " ".join(
#             f"{k}={json.dumps(v, ensure_ascii=False) if isinstance(v, dict) else v}"
#             for k, v in action.items()
#         )
#         text += f"\n结果: {summary} | {action_info}"
# 
#     metric_lines = []
#     for k, v in metrics.items():
#         metric_lines.append(f"  {k}: {v}")
#     if duration_ms:
#         metric_lines.append(f"  耗时: {duration_ms}ms")
#     if metric_lines:
#         text += "\n统计:\n" + "\n".join(metric_lines)
# 
#     diff = llm_data.get("diff", "")
#     if diff:
#         text += f"\n差异:\n{diff}"
# 
#     if exec_code in ("error", "warning"):
#         hint = status.get("hint", "")
#         if hint:
#             text += f"\n建议: {hint}"
# 
#     return text

def _format_llm_data(llm_data: Dict) -> str:
    """格式化llm_data为observation文本（精简版: 合并观察+结果为一行,去掉统计,保留建议）— 小沈 2026-07-06 — 小沈 2026-07-08 修复空target/前置空格/缺空格/空parts"""
    status = llm_data.get("status", {})
    action = llm_data.get("action", {})
    summary = llm_data.get("summary", "")
    exec_code = status.get("exec_code", "success")
    message = status.get("message", "")
    tool = action.get("tool", "")
    tool_zh = action.get("tool_zh", "")
    # 小欧 2026-07-12: 防御性转换 — action.target可能为非str类型(如文档工具泄漏的WindowsPath),
    # 直接len()会触发TypeError,统一str()化兜底
    target = str(action.get("target", ""))
    if len(target) > 200:
        target = target[:200] + "..."

    # 第1行: 工具执行结果 — 小欧 2026-07-07 — 北京老陈 2026-07-07
    _target_part = f",处理对象-{target}" if target else ""
    _st = f"{tool_zh} 调用工具-{tool}{_target_part}"
    status_line = {
        "success": f"工具执行: {_st} - 执行结果: 成功",
        "error": f"工具执行: {_st} - 执行结果: 失败",
        "warning": f"工具执行: {_st} - 执行结果: 完成-[有警告]",
    }.get(exec_code)
    if status_line is None:
        logger.warning(f"[observation_formatter] unknown exec_code={exec_code!r} in _format_llm_data")
        status_line = f"工具执行: {_st} - 执行结果: 未知({exec_code})"

    # 第2行: 观察: {message} - {summary} — 小沈 2026-07-06
    parts = [p for p in [message, summary] if p]
    obs_text = ' - '.join(parts) if parts else '(无额外信息)'
    text = f"{status_line}\n观察: {obs_text}"

    # 失败/警告: 附加详情（不重复message）
    detail = status.get("detail", "")
    if exec_code == "error" and detail:
        text += f"\n✖ 错误: {detail}"
    elif exec_code == "warning" and detail:
        text += f"\n⚠ 警告: {detail}"

    # 建议（error/warning时保留）
    if exec_code in ("error", "warning"):
        hint = status.get("hint", "")
        if hint:
            text += f"\n建议: {hint}"

    diff = llm_data.get("diff", "")
    if diff:
        text += f"\n差异:\n{diff}"

    return text


def format_llm_observation(data: Any, llm_data: Dict) -> str:
    """格式化工具结果为LLM observation文本 — 小欧 2026-06-21 — 小欧 2026-07-06 拆分_format_llm_data
    【精简改版】合并观察+结果行,去掉统计+建议 — 小沈 2026-07-06
    【去详情】error时不追加详情段(原始dict混淆LLM),详情已含在✖错误/建议中 — 小欧 2026-07-07

    llm_data → _format_llm_data（观察行+error/warning详情+diff）
    data     → 详情行（通过 format_data_detail）——仅success/warning

    设计原则：工具的统计数据（total_matches/total_files等）已通过
    llm_data.metrics → summary → _format_llm_data 嵌入"观察:"行，
    最终给LLM的文本中必然包含。data中不再重复存放这些字段。
    — 小欧 2026-07-06 18:39:02
    """
    text = _format_llm_data(llm_data)

    # error 统一兜底: 主通道是 llm_data.status.detail(各工具已构造);
    # 仅当 detail 为空且 data 含诊断信息时,受控渲染 data(复用既有 format_data_detail),
    # 收敛 build_error(data={}) 不一致且不退化已有 detail 的工具 — 小欧 2026-07-13
    if llm_data.get("status", {}).get("exec_code") == "error":
        _detail = llm_data.get("status", {}).get("detail", "")
        if (not _detail or not str(_detail).strip()) and data:
            _extra = format_data_detail(data, llm_data)
            if _extra:
                text += f"\n错误详情:\n{_extra}"
        return text

    if data:
        detail = format_data_detail(data, llm_data)
        if detail:
            text += f"\n详情:\n{detail}"
        else:
            text += "\n详情: 结果已在观察中完整说明"

    return text


# #2b flat table 样式:
#   输入: headers=["name", "age", "city"], rows=[["Alice", 30, "NY"], ["Bob", 25, "LA"]]
#   输出: name=Alice | age=30 | city=NY\nname=Bob | age=25 | city=LA
def _format_table(headers: list, rows: list) -> str:
    """格式化表格数据 — 小欧 2026-06-21"""
    if not headers or not rows:
        return ""
    lines = []
    for row in rows[:OBS_MAX_DISPLAY_ITEMS]:
        if isinstance(row, (list, tuple)):
            parts = [f"{h}={v}" if v is not None else f"{h}=" for h, v in zip(headers, row)]
            lines.append(" | ".join(parts))
        elif isinstance(row, dict):
            parts = [f"{h}={row.get(h, '')}" if row.get(h) is not None else f"{h}=" for h in headers]
            lines.append(" | ".join(parts))
    if len(rows) > OBS_MAX_DISPLAY_ITEMS:
        lines.append(f"  ... 还有 {len(rows) - OBS_MAX_DISPLAY_ITEMS} 行")
    return "\n".join(lines)


# #3 entries 样式:
#   输入: [{"name": "src", "type": "dir", "size": null}, {"name": "readme.md", "type": "file", "size": 2048}]
#   输出:   src [目录]\n  readme.md [文件, 2048字节]
def _format_entries(entries: list) -> str:
    """格式化目录列表 — 小欧 2026-06-21 — 小沈 2026-07-08 加列表已展示提示（避免LLM重复请求）"""
    if not entries:
        return ""
    total = len(entries)
    lines = []
    for entry in entries[:OBS_MAX_DISPLAY_ITEMS]:
        if isinstance(entry, str):
            suffix = " [目录]" if entry.endswith("/") or entry.endswith("\\") else " [文件]"
            lines.append(f"  {entry}{suffix}")
        elif isinstance(entry, dict):
            name = entry.get("name", "")
            etype_lower = (entry.get("type") or "").lower()
            size = entry.get("size")
            label = "目录" if etype_lower in ("dir", "directory") else "文件"
            size_str = f", {size}字节" if size not in (None, "") else ""
            lines.append(f"  {name} [{label}{size_str}]")
    if total > OBS_MAX_DISPLAY_ITEMS:
        remaining = total - OBS_MAX_DISPLAY_ITEMS
        lines.append(f"  ... 还有 {remaining} 项（使用 offset={OBS_MAX_DISPLAY_ITEMS} 查看下一页）")
        lines.append(f"[已含目录结构: {total}项;列表已截断]")
    else:
        lines.append(f"[已含目录结构: {total}项;列表已完整展示]")
    return "\n".join(lines)


# #4 items 样式:
#   输入: [{"title": "Python教程", "snippet": "学习Python编程...", "url": "https://...", "source": "web"}]
#   输出:   Python教程: 学习Python编程... [web]
def _format_items(items: list) -> str:
    """格式化搜索结果/列表项(行×列: OBS_SEARCHWEB_MAX_ROWS/CHARS) — 小欧 2026-07-20"""
    if not items:
        return ""
    lines = []
    truncated = False
    for i, item in enumerate(items):
        if i >= OBS_SEARCHWEB_MAX_ROWS:
            truncated = True
            break
        if isinstance(item, str):
            s = item
            if len(s) > OBS_SEARCHWEB_MAX_ROW_CHARS:
                s = s[:OBS_SEARCHWEB_MAX_ROW_CHARS] + "...(截断)"
            lines.append(f"  {s}")
        elif isinstance(item, dict):
            name = item.get("name", item.get("title", item.get("path", "")))
            desc = item.get("snippet", item.get("description", item.get("desc", "")))
            if desc and len(desc) > OBS_SEARCHWEB_MAX_ROW_CHARS:
                desc = desc[:OBS_SEARCHWEB_MAX_ROW_CHARS] + "...(截断)"
            url = item.get("url", "")
            source = item.get("source", "")
            tag = f" [{source}]" if source else ""
            # 2026-07-17 - 小欧 - 修复url丢弃: desc与url并存输出(url非空时附在desc下方一行), url为fetchpage必需入参, 保留
            if desc:
                line = f"  {name}: {desc}{tag}"
                if url:
                    line += f"\n    URL: {url}"
                lines.append(line)
            elif url:
                lines.append(f"  {name}: {url}{tag}")
            else:
                lines.append(f"  {name}{tag}")
    total = len(items)
    if truncated:
        lines.append(f"  ... 还有 {total - OBS_SEARCHWEB_MAX_ROWS} 项（输入已全部返回, 仅展示前 {OBS_SEARCHWEB_MAX_ROWS} 项）")
        lines.append("⚠ 已截断")
    else:
        lines.append("✓ 无截断-完整")
    return "\n".join(lines)


# #5 rows 样式:
#   输入: columns=["name","age"], rows=[["Alice",30],["Bob",25]]
#   输出: name=Alice | age=30\nname=Bob | age=25
def _format_rows(rows: list, columns: list = None) -> str:
    """格式化数据库行 — 小欧 2026-06-21"""
    if not rows:
        return ""
    lines = []
    for row in rows[:OBS_MAX_DISPLAY_ITEMS]:
        if isinstance(row, (list, tuple)):
            if columns:
                parts = [f"{columns[i]}={v}" if v is not None else f"{columns[i]}=" for i, v in enumerate(row)]
            else:
                parts = [str(v) for v in row]
            lines.append(" | ".join(parts))
        elif isinstance(row, dict):
            parts = [f"{k}={v}" if v is not None else f"{k}=" for k, v in row.items()]
            lines.append(" | ".join(parts))
    if len(rows) > OBS_MAX_DISPLAY_ITEMS:
        lines.append(f"  ... 还有 {len(rows) - OBS_MAX_DISPLAY_ITEMS} 行")
    return "\n".join(lines)


# #6 schema 样式:
#   输入: [{"table":"users","columns":["id","name","email"]}, {"table":"orders","columns":["id","user_id","total"]}]
#   输出:   users: id, name, email\n  orders: id, user_id, total
def _col_display(c) -> str:
    """列显示统一处理 — 小沈 2026-07-08"""
    if isinstance(c, str):
        return c
    if isinstance(c, dict):
        return c.get('name', c.get('field', str(c)))
    return str(c)


def _format_schema(tables: list) -> str:
    """格式化Schema信息 — 小欧 2026-06-21"""
    if not tables:
        return ""
    lines = []
    for table in tables[:OBS_MAX_DISPLAY_ITEMS]:
        if isinstance(table, str):
            lines.append(f"  {table}")
        elif isinstance(table, dict):
            name = table.get("name", table.get("table", ""))
            cols = table.get("columns", [])
            if cols:
                col_str = ", ".join(_col_display(c) for c in cols)
                lines.append(f"  {name}: {col_str}")
            else:
                lines.append(f"  {name}")
    if len(tables) > OBS_MAX_DISPLAY_ITEMS:
        lines.append(f"  ... 还有 {len(tables) - OBS_MAX_DISPLAY_ITEMS} 张表")
    return "\n".join(lines)


# #8 events 样式:
#   输入: [{"time":"2026-07-05 10:00:00","message":"用户登录成功"}, {"message":"文件已保存"}]
#   输出:   [2026-07-05 10:00:00] 用户登录成功\n  文件已保存
def _format_events(events: list) -> str:
    """格式化事件日志 — 小欧 2026-06-21"""
    if not events:
        return ""
    lines = []
    for event in events[:OBS_MAX_DISPLAY_ITEMS]:
        if isinstance(event, str):
            lines.append(f"  {event}")
        elif isinstance(event, dict):
            ts = event.get("timestamp", event.get("time", ""))
            msg = event.get("message", event.get("event", str(event)))
            if ts:
                lines.append(f"  [{ts}] {msg}")
            else:
                lines.append(f"  {msg}")
    if len(events) > OBS_MAX_DISPLAY_ITEMS:
        lines.append(f"  ... 还有 {len(events) - OBS_MAX_DISPLAY_ITEMS} 条事件")
    return "\n".join(lines)


# 列宽计算样式: items=[{"name":"backup","status":"ready"},...], columns=[("name","名称"),("status","状态")]
#   输出: [10, 8]  # 每列最大宽度(上限40)
def _calc_col_widths(items: list, columns: list) -> list:
    """计算列宽度（取字段最长值, 上限40）— 小欧 2026-07-05"""
    widths = []
    for key, header in columns:
        max_w = len(header)
        for item in items:
            v = item.get(key, "")
            if isinstance(v, str) and len(v) > max_w:
                max_w = min(len(v), 40)
        widths.append(max_w)
    return widths


# 表格块样式: items=[{name:"backup",status:"ready"}], columns=[("name","名称"),("status","状态")], widths=[10,8]
#   输出: ["   名称      状态 ", "  ────────────────", "   backup    ready"]
def _format_table_block(items: list, columns: list, widths: list, indent: str = "") -> list:
    """格式化表格块：表头 + 分隔线 + 数据行 — 小欧 2026-07-05"""
    lines = []
    hdr = indent + "  ".join(f"{hdr:<{w}}" for (_, hdr), w in zip(columns, widths))
    sep = indent + "  ".join("─" * w for w in widths)
    lines.append(hdr)
    lines.append(sep)
    for i, item in enumerate(items):
        if i >= OBS_MAX_DISPLAY_ITEMS:
            lines.append(indent + f"... 还有 {len(items) - OBS_MAX_DISPLAY_ITEMS} 个")
            break
        row = indent + "  ".join(
            _fmt_cell(item.get(key, ""), w) for (key, _), w in zip(columns, widths)
        )
        lines.append(row)
    return lines


# 单元格格式化样式: val="backup", width=10
#   输出: "    backup"
def _fmt_cell(val: Any, width: int) -> str:
    """截断并右对齐单元格值 — 小欧 2026-07-05"""
    s = str(val) if val is not None else ""
    if len(s) > width:
        s = s[:width - 3] + "..."
    return f"{s:<{width}}"


# #14 tasks 样式:
#   输入: {"tasks": [{"name":"backup","next_run":"2026-07-06 03:00","status":"ready","command":"backup.bat"}], ...}
#   输出:   名称     下次运行          状态   命令\n  ──────────────────────────\n     backup  2026-07-06 03:00  ready  backup.bat\n  ---\ntasks: 1, platform: windows
def _format_tasks(data: dict) -> str:
    """#14 tasks handler — list_tasks 表格 — 小欧 2026-07-05"""
    items = data.get("tasks", [])
    if not items:
        return ""
    cols = [("name", "名称")]
    if any(t.get("next_run") for t in items):
        cols.append(("next_run", "下次运行"))
    if any(t.get("status") for t in items):
        cols.append(("status", "状态"))
    if any(t.get("command") for t in items):
        cols.append(("command", "命令"))
    widths = _calc_col_widths(items, cols)
    lines = _format_table_block(items, cols, widths)
    meta = f"tasks: {len(items)}"
    if data.get("total", 0) > len(items):
        meta += f", total: {data['total']}"
    meta += f", platform: {data.get('platform', '?')}"
    lines.append(f"---\n{meta}")
    return "\n".join(lines)


# #15 windows 样式:
#   输入: {"windows": [{"hwnd":123456,"title":"记事本","state":"visible","position":{"left":0,"top":0,"width":800,"height":600}}]}
#   输出:     HWND    标题    状态    位置\n  ────────────────────────────────\n   123456  记事本  visible  x=0,y=0 800x600\n---\nwindows: 1
def _format_windows(data: dict) -> str:
    """#15 windows handler — window_info 表格 — 小欧 2026-07-05 — 小欧 2026-07-10 fix: 不修改原始数据"""
    items = data.get("windows", [])
    if not items:
        return ""
    augmented = []
    for w in items:
        pos = w.get("position")
        if pos and isinstance(pos, dict):
            _pos_val = f"x={pos.get('left','?')},y={pos.get('top','?')} {pos.get('width','?')}x{pos.get('height','?')}"
        elif pos is None:
            _pos_val = "[hidden]"
        else:
            _pos_val = "?"
        augmented.append({**w, "_pos": _pos_val})
    cols = [("hwnd", "HWND"), ("title", "标题"), ("state", "状态"), ("_pos", "位置")]
    widths = _calc_col_widths(augmented, cols)
    lines = _format_table_block(augmented, cols, widths)
    meta = f"windows: {len(items)}"
    if data.get("total", 0) > len(items):
        meta += f", total: {data['total']}"
    lines.append(f"---\n{meta}")
    return "\n".join(lines)


# #16 slides 样式:
#   输入: {"slide_count":3,"slides":[{"slide_num":1,"text":"封面\n副标题","tables_count":0},{"slide_num":2,"text":"内容页","tables_count":1}]}
#   输出:   幻灯片 1/3\n    封面\n    副标题\n   幻灯片 2/3\n    内容页  [1个表格]\n---\n[slide_count: 3]
def _format_slides(data: dict, llm_data: dict = None) -> str:
    """#16 slides handler — read_pptx items 块 — 小欧 2026-07-05 — 小欧 2026-07-10 fix: 加llm_data参数统一截断消息"""
    items = data.get("slides", [])
    if not items:
        return ""
    lines = []
    total = data.get("slide_count", len(items))
    for i, slide in enumerate(items):
        if i >= OBS_MAX_DISPLAY_ITEMS:
            lines.append(f"  ... 还有 {len(items) - OBS_MAX_DISPLAY_ITEMS} 页")
            break
        num = slide.get("slide_num", i + 1)
        lines.append(f"  幻灯片 {num}/{total}")
        text = slide.get("text", "")
        if text:
            if len(text) > OBS_MAX_STRING_LENGTH:
                text = text[:OBS_MAX_STRING_LENGTH] + _truncation_msg(llm_data)
            for line in text.split("\n"):
                lines.append(f"    {line}")
        tables = slide.get("tables")
        if tables:
            lines.append(f"    表格: {len(tables)}个")
    notes = data.get("notes")
    if notes:
        lines.append(f"  ---\n  备注: {len(notes)}条")
    lines.append(f"---\n[slide_count: {total}]")
    return "\n".join(lines)


# #17 sysinfo 样式:
#   输入: {"basic":{"hostname":"PC","os":"Windows 11","uptime":"2h"},"cpu":{"cores":8,"usage":35.5}}
#   输出:   [基本]\n    hostname: PC\n    os: Windows 11\n    uptime: 2h\n  [CPU]\n    cores: 8\n    usage: 35.5
def _format_sysinfo(data: dict) -> str:
    """#17 sysinfo handler — 分节展示 — 小欧 2026-07-05"""
    sections = {
        "basic": "基本",
        "cpu": "CPU",
        "memory": "内存",
        "disk": "磁盘",
        "network": "网络",
    }
    lines = []
    for sec_key, sec_label in sections.items():
        sec_data = data.get(sec_key)
        if sec_data is None:
            continue
        if isinstance(sec_data, list):
            for i, entry in enumerate(sec_data):
                if i >= OBS_MAX_DISPLAY_ITEMS:
                    lines.append(f"  [{sec_label} ... 还有 {len(sec_data) - OBS_MAX_DISPLAY_ITEMS} 个]")
                    break
                lines.append(f"[{sec_label} #{i + 1}]")
                for k, v in entry.items():
                    v_str = str(v)
                    if len(v_str) > OBS_SYSINFO_FIELD_MAX_CHARS:
                        v_str = v_str[:OBS_SYSINFO_FIELD_MAX_CHARS] + "..."
                    lines.append(f"  {k}: {v_str}")
        elif isinstance(sec_data, dict):
            lines.append(f"[{sec_label}]")
            for k, v in sec_data.items():
                v_str = str(v)
                if len(v_str) > OBS_SYSINFO_FIELD_MAX_CHARS:
                    v_str = v_str[:OBS_SYSINFO_FIELD_MAX_CHARS] + "..."
                lines.append(f"  {k}: {v_str}")
    return "\n".join(lines) if lines else ""


# fallback(key:val) 实际输出样式:
#   输入: {"name": "test.txt", "size": 1024, "path": "/tmp/test.txt"}
#   输出:
#     name: test.txt
#     size: 1024
#     path: /tmp/test.txt
def _format_scalar_data(data: dict) -> str:
    """键值对展示，每行一个 key: value — 小欧 2026-07-05 — 小沈 2026-07-08 _note 特殊处理 — 小欧 2026-07-10 fix: pop→get 防副作用 + OBS_DICT_MAX_KEYS — 小欧 2026-07-13 防御: 非dict直接序列化"""
    if not isinstance(data, dict):
        try:
            return json.dumps(data, ensure_ascii=False, indent=2)
        except Exception:
            return str(data)
    _note = data.get("_note", "")
    keys = [k for k in data if k != "_note"]
    lines = []
    for i, k in enumerate(keys):
        if i >= OBS_DICT_MAX_KEYS:
            remaining = len(keys) - OBS_DICT_MAX_KEYS
            if remaining > 0:
                lines.append(f"  ... 还有 {remaining} 个键未显示")
            break
        v = data[k]
        v_str = str(v)
        if len(v_str) > OBS_MAX_STRING_LENGTH:
            v_str = v_str[:OBS_MAX_STRING_LENGTH] + "... (截断)"
        lines.append(f"  {k}: {v_str}")
    if _note:
        lines.append(f"  {_note}")
    return "\n".join(lines)


# #9b find 样式:
#   输入: [{"name":"main.py","type":"file","size":2048,"path":"/project/src/main.py"}, {"name":"test","type":"dir","path":"/project/test"}]
#   输出:   main.py [文件, 2048字节]\n    /project/src/main.py\n  test [目录]\n    /project/test
def _format_find_results(matches: list) -> str:
    """格式化 find 文件搜索结果(行×列: OBS_FIND_MAX_ROWS/CHARS) — 小欧 2026-07-20"""
    if not matches:
        return ""
    lines = []
    truncated = False
    for i, m in enumerate(matches):
        if i >= OBS_FIND_MAX_ROWS:
            truncated = True
            break
        name = str(m.get("name", ""))
        if len(name) > OBS_FIND_MAX_ROW_CHARS:
            name = name[:OBS_FIND_MAX_ROW_CHARS] + "...(截断)"
        etype = m.get("type", "")
        size = m.get("size")
        size_str = f", {size}字节" if size is not None else ""
        lines.append(f"  {name} [{etype}{size_str}]")
        p = str(m.get("path", ""))
        if len(p) > OBS_FIND_MAX_ROW_CHARS:
            p = p[:OBS_FIND_MAX_ROW_CHARS] + "...(截断)"
        if p:
            lines.append(f"    {p}")
    total = len(matches)
    if truncated:
        lines.append(f"  ... 还有 {total - OBS_FIND_MAX_ROWS} 个匹配项（输入已全部返回, 仅展示前 {OBS_FIND_MAX_ROWS} 项）")
        lines.append("⚠ 已截断")
    else:
        lines.append("✓ 无截断-完整")
    return "\n".join(lines)


# #9c searchtool 样式:
#   输入: [{"name":"http_request","category":"network"}, {"name":"read_file","category":"file"}]
#   输出:   http_request [network]\n  read_file [file]
def _format_searchtool_results(matches: list) -> str:
    """格式化 searchtool 工具搜索结果 — 小欧 2026-07-05"""
    if not matches:
        return ""
    lines = []
    for i, m in enumerate(matches):
        if i >= OBS_MAX_DISPLAY_ITEMS:
            lines.append(f"  ... 还有 {len(matches) - OBS_MAX_DISPLAY_ITEMS} 个匹配项")
            break
        name = m.get("name", "")
        cat = m.get("category", "")
        lines.append(f"  {name} [{cat}]")
    return "\n".join(lines)


# #9 matches 样式:
#   输入: [{"file":"src/main.py","line":42,"matched":["import"],"content":"import os"}, {"file":"src/utils.py","line":10,"matched":["import"],"content":"import sys"}]
#   输出:   src/main.py:42: [import] import os\n  src/utils.py:10: [import] import sys
def _is_files_mode(m: dict) -> bool:
    """判断是否为 files_with_matches 模式 — 小沈 2026-07-08"""
    return "lines" in m and "line" not in m


def _format_matches(matches: list) -> str:
    """格式化 grep 内容匹配结果 — 行×列: OBS_GREP_MAX_ROWS 行 / OBS_GREP_MAX_ROW_CHARS 列
    小欧 2026-07-04 初版; 小欧 2026-07-20 改行×列(200×150)+截断说明行两态(Tool 输出不截断, 仅显示域按行×列收口)"""
    if not matches:
        return ""
    if isinstance(matches[0], str):
        return "\n".join(f"  {m}" for m in matches)
    max_rows = OBS_GREP_MAX_ROWS
    max_chars = OBS_GREP_MAX_ROW_CHARS
    is_files_mode = _is_files_mode(matches[0]) if matches else False
    # 第一遍：构建全部渲染行，并统计超宽行数（用于截断说明行）
    all_rows = []
    overwide = 0

    def _clip(text: str) -> str:
        nonlocal overwide
        if len(text) > max_chars:
            overwide += 1
        return text[:max_chars]

    if is_files_mode:
        all_rows.append("文件 : 行号")
    for m in matches:
        file_path = m.get("file", "")
        file_lines = m.get("lines")
        if file_lines:
            all_rows.append(_clip(f"  {file_path}: 行号{file_lines}"))
            continue
        matched = m.get("matched", [])
        matched_str = ", ".join(matched) if isinstance(matched, list) else str(matched)
        content = m.get("content", "")
        line_no = m.get("line", "")
        if line_no:
            # context上下文:before在命中行之前,after在之后,命中行加>标记 — 小欧 2026-07-11
            before = m.get("before")
            after = m.get("after")
            if before or after:
                for ctx in (before or []):
                    all_rows.append(_clip(f"       {ctx.get('line')}| {(ctx.get('text', '') or '')}"))
                all_rows.append(_clip(f"  >  {file_path}:{line_no}: [{matched_str}] {content}"))
                for ctx in (after or []):
                    all_rows.append(_clip(f"       {ctx.get('line')}| {(ctx.get('text', '') or '')}"))
            else:
                all_rows.append(_clip(f"  {file_path}:{line_no}: [{matched_str}] {content}"))
        else:
            all_rows.append(_clip(f"  {file_path}"))
    total = len(all_rows)
    truncated = total > max_rows
    shown = all_rows[:max_rows]
    if truncated:
        shown.append("⚠ 已截断")
        shown.append("截断情况：保留%d行,实际 %d 行，截断 %d 行；单行上限 %d 字符（超宽 %d 行尾部截断）" % (max_rows, total, total - max_rows, max_chars, overwide))
    else:
        shown.append("✓ 无截断-完整")
    return "\n".join(shown)


# #18 compress(JSON) 样式:
#   输入: {"compression_ratio":0.45,"original_size":1024000,"compression_level":6,"encrypted":true,"compressed_files":["doc1.txt","doc2.txt"]}
#   输出: ── 压缩完成 ── | 压缩比: 45.00% 原始: 1024000 bytes 级别: 6 已加密\n压缩文件: ["doc1.txt", "doc2.txt"]
def _format_compress_result(data: dict) -> str:
    """compress 压缩结果 — 小欧 2026-07-05"""
    ratio = data.get("compression_ratio", 0)
    original = data.get("original_size", 0)
    level = data.get("compression_level", "")
    encrypted = " 已加密" if data.get("encrypted") else ""
    if ratio < 0:
        desc = f"文件膨胀 {abs(ratio):.2%}"
    else:
        desc = f"压缩率 {ratio:.2%}"
    header = f"{desc} 原始: {original} bytes 级别: {level}{encrypted}"

    lines = [f"── 压缩完成 ── | {header}"]

    files = data.get("compressed_files", [])
    if files:
        lines.append(f"压缩文件: {json.dumps(files, ensure_ascii=False)}")

    return "\n".join(lines)


def _extract_html_summary(html: str, max_len: int = OBS_HTML_SUMMARY_MAX_CHARS) -> str:
    """从 HTML 中提取纯文本摘要 — 小沈 2026-07-08"""
    text = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL)
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:max_len]


# #19 httpget(body+headers) 样式:
#   输入: {"status_code":200,"body":{"userId":1,"title":"hello"},"headers":{"content-type":"application/json","date":"2026-07-05"}}
#   输出: ── HTTP GET ── 200\n── Body ──\n{\n  "userId": 1,\n  "title": "hello"\n}\n── Headers ──\n  content-type: application/json\n  date: 2026-07-05
def _format_httpget_result(data: dict) -> str:
    """httpget HTTP 响应 — 小欧 2026-07-05; 2026-07-20 门限治理(章9.4): 专属行×列 OBS_HTTPGET_MAX_ROWS/CHARS + 两态说明"""
    lines = [f"── HTTP GET ── {data.get('status_code', '?' )}"]
    truncated = False

    body = data.get("body")
    if body is not None:
        lines.append("── Body ──")
        if isinstance(body, (dict, list)):
            body_str = json.dumps(body, ensure_ascii=False, indent=2)
        elif isinstance(body, str):
            body_str = _extract_html_summary(body)
        else:
            body_str = str(body)
        # 行×列截断收口(章9.4): OBS_HTTPGET_MAX_ROWS 行 / OBS_HTTPGET_MAX_ROW_CHARS 字符
        body_lines = body_str.split("\n")
        total_lines = len(body_lines)
        if total_lines > OBS_HTTPGET_MAX_ROWS:
            truncated = True
            body_lines = body_lines[:OBS_HTTPGET_MAX_ROWS]
        for ln in body_lines:
            if len(ln) > OBS_HTTPGET_MAX_ROW_CHARS:
                truncated = True
                lines.append(ln[:OBS_HTTPGET_MAX_ROW_CHARS] + "...(截断)")
            else:
                lines.append(ln)
        if total_lines > OBS_HTTPGET_MAX_ROWS:
            lines.append(f"  ... 还有 {total_lines - OBS_HTTPGET_MAX_ROWS} 行（仅展示前 {OBS_HTTPGET_MAX_ROWS} 行）")

    headers = data.get("headers")
    if headers:
        lines.append("── Headers ──")
        for k, v in sorted(headers.items()):
            lines.append(f"  {k}: {v}")

    lines.append("⚠ 已截断" if truncated else "✓ 无截断-完整")
    return "\n".join(lines)


def _format_fetchpage_result(content: str, llm_data: dict = None) -> str:
    """fetchpage 网页正文 — 2026-07-20 门限治理(章10.4): 专属行×列 OBS_FETCHPAGE_MAX_ROWS/CHARS + 两态说明"""
    _act = (llm_data or {}).get("action", {}) if llm_data else {}
    _url = _act.get("target", "")
    _fmt = _act.get("params", {}).get("extract_format", "")
    lines = [f"── 网页正文 ── {_url}"]
    if _fmt:
        lines[-1] += f" ({_fmt})"
    truncated = False
    content_lines = content.split("\n")
    total_lines = len(content_lines)
    if total_lines > OBS_FETCHPAGE_MAX_ROWS:
        truncated = True
        content_lines = content_lines[:OBS_FETCHPAGE_MAX_ROWS]
    for ln in content_lines:
        if len(ln) > OBS_FETCHPAGE_MAX_ROW_CHARS:
            truncated = True
            lines.append(ln[:OBS_FETCHPAGE_MAX_ROW_CHARS] + "...(截断)")
        else:
            lines.append(ln)
    if total_lines > OBS_FETCHPAGE_MAX_ROWS:
        lines.append(f"  ... 还有 {total_lines - OBS_FETCHPAGE_MAX_ROWS} 行（仅展示前 {OBS_FETCHPAGE_MAX_ROWS} 行）")
    lines.append("⚠ 已截断" if truncated else "✓ 无截断-完整")
    return "\n".join(lines)


def _format_readtext_result(content: str, llm_data: dict = None) -> str:
    """readtext 文件内容 — 2026-07-20 门限治理(章11.4): 专属行×列 OBS_READTEXT_MAX_ROWS/CHARS + 两态说明"""
    _act = (llm_data or {}).get("action", {}) if llm_data else {}
    _path = _act.get("target", "")
    lines = [f"── 文件内容 ── {_path}"]
    truncated = False
    content_lines = content.split("\n")
    total_lines = len(content_lines)
    if total_lines > OBS_READTEXT_MAX_ROWS:
        truncated = True
        content_lines = content_lines[:OBS_READTEXT_MAX_ROWS]
    for ln in content_lines:
        if len(ln) > OBS_READTEXT_MAX_ROW_CHARS:
            truncated = True
            lines.append(ln[:OBS_READTEXT_MAX_ROW_CHARS] + "...(截断)")
        else:
            lines.append(ln)
    if total_lines > OBS_READTEXT_MAX_ROWS:
        lines.append(f"  ... 还有 {total_lines - OBS_READTEXT_MAX_ROWS} 行（仅展示前 {OBS_READTEXT_MAX_ROWS} 行）")
    lines.append("⚠ 已截断" if truncated else "✓ 无截断-完整")
    return "\n".join(lines)


def _format_edittext_result(diff: str, llm_data: dict = None) -> str:
    """edittext 编辑差异 — 2026-07-20 门限治理(章12.4): 专属行×列 OBS_EDITTEXT_MAX_ROWS/CHARS + 两态说明
    Tool 输出 diff 不截断(3.7); 仅显示域按行×列收口(6.4)。无 diff 时回退标量摘要。"""
    _act = (llm_data or {}).get("action", {}) if llm_data else {}
    _path = _act.get("target", "")
    lines = [f"── 编辑差异 ── {_path}"]
    if not diff:
        lines.append("(无差异)")
        lines.append("✓ 无截断-完整")
        return "\n".join(lines)
    truncated = False
    diff_lines = diff.split("\n")
    total_lines = len(diff_lines)
    if total_lines > OBS_EDITTEXT_MAX_ROWS:
        truncated = True
        diff_lines = diff_lines[:OBS_EDITTEXT_MAX_ROWS]
    for ln in diff_lines:
        if len(ln) > OBS_EDITTEXT_MAX_ROW_CHARS:
            truncated = True
            lines.append(ln[:OBS_EDITTEXT_MAX_ROW_CHARS] + "...(截断)")
        else:
            lines.append(ln)
    if total_lines > OBS_EDITTEXT_MAX_ROWS:
        lines.append(f"  ... 还有 {total_lines - OBS_EDITTEXT_MAX_ROWS} 行（仅展示前 {OBS_EDITTEXT_MAX_ROWS} 行）")
    lines.append("⚠ 已截断" if truncated else "✓ 无截断-完整")
    return "\n".join(lines)





# #20 analyze_data(转置表) 样式:
#   输入: {"row_count":100,"columns":["price","quantity"],"statistics":{"mean":{"price":29.99,"quantity":150.25},"sum":{"price":2999.0,"quantity":15025.0},"min":{"price":5.99,"quantity":1},"max":{"price":99.99,"quantity":500}}}
#   输出: ── 数据分析 ── 100行, 2列\n         price       quantity\n  ────────────────────────\n        mean    29.9900    150.2500\n         sum  2999.0000  15025.0000\n         min     5.9900      1.0000\n         max    99.9900    500.0000
def _format_analyze_data(data: dict) -> str:
    """analyze_data 描述统计，转置表格 — 小欧 2026-07-05"""
    lines = [f"── 数据分析 ── {data.get('row_count', '?')}行"]
    cols = data.get("columns", [])
    if cols:
        lines[-1] += f", {len(cols)}列"
    if "top_n" in data:
        lines[-1] += f" (top {data['top_n']})"

    stats = data.get("statistics")
    grouped = data.get("grouped_statistics")

    if grouped:
        for gk, gs in grouped.items():
            lines.append(f"\n── 分组: {gk} ──")
            lines.extend(_build_transposed_table(gs, cols))
    elif stats:
        lines.extend(_build_transposed_table(stats, cols))
    else:
        lines.append("(无统计结果)")

    return "\n".join(lines)


# 转置表样式: stats={"mean":{"price":29.99,"qty":150.25},"sum":{"price":2999,"qty":15025}}, columns=["price","qty"]
#   输出: ["         price         qty ", " ────────────────────────", "   mean   29.9900   150.2500", "    sum 2999.0000 15025.0000"]
def _build_transposed_table(stats: dict, columns: list) -> list:
    """转置统计量字典为文本表格 — 小欧 2026-07-05"""
    if not columns:
        for op in ("mean", "sum", "min", "max", "count", "std"):
            v = stats.get(op)
            if isinstance(v, dict):
                columns = list(v.keys())
                break
    if not columns:
        return ["(无数据列)"]

    ops = [op for op in ("mean", "sum", "min", "max", "count", "std")
           if op in stats and isinstance(stats[op], dict)]
    if not ops:
        return ["(无可用统计)"]

    col_w = max(12, *(len(str(c)) for c in columns))
    op_w = max(6, *(len(op) for op in ops))

    lines = []
    h = " " * op_w
    for c in columns:
        h += f"  {str(c):>{col_w}}"
    lines.append(h)
    lines.append("─" * len(h))

    for op in ops:
        row = f"{op:>{op_w}}"
        for c in columns:
            v = stats[op].get(c)
            if v is None:
                s = "-"
            elif isinstance(v, float):
                s = f"{v:.4f}"
            else:
                s = str(v)
            row += f"  {s:>{col_w}}"
        lines.append(row)

    return lines


def build_observation_text(execution_result, tool_name: str = "", tool_params: Optional[dict] = None) -> str:
    """根据工具执行结果构建observation文本 — 小欧 2026-06-21

    从result中拆包data/llm_data，直接调format_llm_observation(data, llm_data)

    Args:
        execution_result: 工具执行结果（新格式dict或Exception）
        tool_name: 工具名称（仅异常时用）
        tool_params: 工具参数（仅异常时用）

    Returns:
        observation文本
    """
    if isinstance(execution_result, dict):
        data = execution_result.get("data")
        llm_data = execution_result.get("llm_data")
        if llm_data is not None:
            return format_llm_observation(data, llm_data)
        if data is not None:
            detail = format_data_detail(data)
            return f"Observation: {detail[:500]}" if len(detail) > 500 else f"Observation: {detail}"
        try:
            result_str = json.dumps(execution_result, ensure_ascii=False, separators=(',', ':'))
        except (TypeError, ValueError):
            result_str = str(execution_result)
        return f"Observation: {result_str[:500]}" if len(result_str) > 500 else f"Observation: {result_str}"
    result_str = str(execution_result)
    return f"Observation: {result_str[:500]}" if len(result_str) > 500 else f"Observation: {result_str}"
