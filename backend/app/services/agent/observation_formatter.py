# -*- coding: utf-8 -*-
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

工具 → handler 映射（全部 ~26 个工具）:
 工具            data 键                        命中 handler              formatter上限                     tool上限
 ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────
 readtext        {content: str}                 #2 raw str               OBS_MAX_STRING_LENGTH=10000      行数不限
 read_pdf        {content: str}                 #2 raw str               OBS_MAX_STRING_LENGTH=10000      页数不限
 read_docx       {content: str}                 #2 raw str               OBS_MAX_STRING_LENGTH=10000      字符数不限
 read_pptx       {content: str}                 #2 raw str               OBS_MAX_STRING_LENGTH=10000      字符数不限
 fetch_webpage   {content: str}                 #2 raw str               OBS_MAX_STRING_LENGTH=10000      5000字符
 read_xlsx       {content: {headers, rows}}     #1 _format_table         OBS_MAX_DISPLAY_ITEMS=500 行     10000行
 query_sql       {columns, rows}                #5 _format_rows          OBS_MAX_DISPLAY_ITEMS=500 行     50行
 filter_data     {columns, rows}                #5 _format_rows          OBS_MAX_DISPLAY_ITEMS=500 行     top_n
 listdir         {entries}                      #3 _format_entries       OBS_MAX_DISPLAY_ITEMS=500 项     200+offset
 find            {matches}                      #9 _format_matches       OBS_MAX_DISPLAY_ITEMS=500 项     1000+offset
 grep            {matches}                      #9 _format_matches       OBS_MAX_DISPLAY_ITEMS=500 项     1000
 searchweb       {items}                        #4 _format_items         OBS_MAX_DISPLAY_ITEMS=500 项；snippet 300字符 50项
 event_log       {events}                       #8 _format_events        OBS_MAX_DISPLAY_ITEMS=500 条     50
 searchtool      {matches}                      #9 _format_matches       OBS_MAX_DISPLAY_ITEMS=500 项     small
 get_db_schema   {tables}                       #6 _format_schema        OBS_MAX_DISPLAY_ITEMS=500 张表   不限
  shell           {output, error_output}         #7 output str            OBS_MAX_STRING_LENGTH=10000      不限
  httpget         {body, ...}                     fallback _format_kv     OBS_DICT_MAX_KEYS=100；值>10000截  400KB
 tree            {tree, statistics, ...}         fallback _format_kv     OBS_DICT_MAX_KEYS=100             depth=10
 sysinfo         {memory, cpu, ...}              fallback _format_kv     OBS_DICT_MAX_KEYS=100             不限
 readmedia       {base64_data, ...}              fallback _format_kv     OBS_DICT_MAX_KEYS=100；字符串>10000截 不限
 analyze_data    {statistics, ...}               fallback _format_kv     OBS_DICT_MAX_KEYS=100             不限
 screen_capture  {image_path}                    fallback _format_kv     OBS_DICT_MAX_KEYS=100             N/A
 generate_chart  {output_path}                   fallback _format_kv     OBS_DICT_MAX_KEYS=100             N/A
 registry_read   {value, ...}                    fallback _format_kv     OBS_DICT_MAX_KEYS=100；字符串>10000截 不限
 list_tasks      {tasks, ...}                    fallback _format_kv     OBS_DICT_MAX_KEYS=100；列表>500截  N/A
 timer_list      {ids, ...}                      fallback _format_kv     OBS_DICT_MAX_KEYS=100；列表>500截  N/A

【注意】listdir/find 的 offset 分页由工具层自行处理（tools/file/），
  formatter 仅展示当前 page（最多 OBS_MAX_DISPLAY_ITEMS 项）。

Author: 小欧 2026-06-21; 小欧 2026-07-04 更新工具→handler映射表
"""

import json
from typing import Any, Dict

from app.tools.tool_constants import (
    OBS_MAX_DISPLAY_ITEMS,
    OBS_MAX_STRING_LENGTH,
    OBS_DICT_MAX_KEYS,
)
from app.utils.json_utils import safe_json_dumps


def format_data_detail(data: Any) -> str:
    """按data结构类型自动格式化为可读文本 — 小欧 2026-06-21

    内部可能抛异常，兜底 JSON dump 或 str() 确保不崩。
    """
    if not data:
        return ""

    try:
        if not isinstance(data, dict):
            return str(data)

        if "content" in data and isinstance(data["content"], dict) and "headers" in data["content"]:
            return _format_table(data["content"]["headers"], data["content"]["rows"])

        if "content" in data and isinstance(data["content"], str):
            content = data["content"]
            if len(content) > OBS_MAX_STRING_LENGTH:
                content = content[:OBS_MAX_STRING_LENGTH] + "\n... (截断，完整内容见文件)"
            return content

        if "entries" in data:
            return _format_entries(data["entries"])

        if "items" in data:
            return _format_items(data["items"])

        if "rows" in data:
            return _format_rows(data["rows"])

        if "tables" in data:
            return _format_schema(data["tables"])

        if "output" in data:
            parts = []
            if data["output"]:
                parts.append(data["output"])
            if data.get("error_output"):
                parts.append(f"[stderr] {data['error_output']}")
            output_text = "\n".join(parts)
            if len(output_text) > OBS_MAX_STRING_LENGTH:
                output_text = output_text[:OBS_MAX_STRING_LENGTH] + "\n... (截断)"
            return output_text

        if "events" in data:
            return _format_events(data["events"])

        if "matches" in data:
            return _format_matches(data["matches"])

        return _format_key_value(data)
    except Exception:
        try:
            return json.dumps(data, ensure_ascii=False, indent=2)
        except Exception:
            return str(data)


def format_llm_observation(data: Any, llm_data: Dict) -> str:
    """格式化工具结果为LLM observation文本 — 小欧 2026-06-21

    llm_data → 观察行 + 结果行（三段式的前两段）
    data     → 详情行（通过 format_data_detail）
    """
    status = llm_data.get("status", {})
    action = llm_data.get("action", {})
    summary = llm_data.get("summary", "")
    exec_code = status.get("exec_code", "")
    message = status.get("message", "")
    tool_zh = action.get("tool_zh", "")

    if exec_code == "success":
        text = f"观察: {message} - {tool_zh}"
    elif exec_code == "warning":
        text = f"观察: {message} - {tool_zh}\n⚠ 警告: {status.get('detail', '')}"
    else:
        text = f"观察: {message} - {tool_zh}"

    if summary:
        action_info = " ".join(
            f"{k}={json.dumps(v, ensure_ascii=False) if isinstance(v, dict) else v}"
            for k, v in action.items()
        )
        text += f"\n结果: {summary} | {action_info}"

    if data is not None and data != {} and data != [] and data != "":
        detail = format_data_detail(data)
        if detail:
            text += f"\n详情:\n{detail}"

    if exec_code in ("error", "warning"):
        hint = status.get("hint", "")
        if hint:
            text += f"\n建议: {hint}"

    return text


def _format_table(headers: list, rows: list) -> str:
    """格式化表格数据 — 小欧 2026-06-21"""
    if not headers or not rows:
        return ""
    lines = []
    for row in rows[:OBS_MAX_DISPLAY_ITEMS]:
        if isinstance(row, (list, tuple)):
            parts = [f"{h}={v}" for h, v in zip(headers, row) if v is not None]
            lines.append(" | ".join(parts))
        elif isinstance(row, dict):
            parts = [f"{h}={row.get(h, '')}" for h in headers if row.get(h) is not None]
            lines.append(" | ".join(parts))
    if len(rows) > OBS_MAX_DISPLAY_ITEMS:
        lines.append(f"  ... 还有 {len(rows) - OBS_MAX_DISPLAY_ITEMS} 行")
    return "\n".join(lines)


def _format_entries(entries: list) -> str:
    """格式化目录列表 — 小欧 2026-06-21"""
    if not entries:
        return ""
    lines = []
    for entry in entries[:OBS_MAX_DISPLAY_ITEMS]:
        if isinstance(entry, str):
            suffix = " [目录]" if entry.endswith("/") or entry.endswith("\\") else " [文件]"
            lines.append(f"  {entry}{suffix}")
        elif isinstance(entry, dict):
            name = entry.get("name", "")
            etype = entry.get("type", "")
            size = entry.get("size", "")
            label = "目录" if etype in ("dir", "directory") else "文件"
            size_str = f", {size}字节" if size else ""
            lines.append(f"  {name} [{label}{size_str}]")
    if len(entries) > OBS_MAX_DISPLAY_ITEMS:
        lines.append(f"  ... 还有 {len(entries) - OBS_MAX_DISPLAY_ITEMS} 项")
    return "\n".join(lines)


def _format_items(items: list) -> str:
    """格式化搜索结果/列表项 — 小欧 2026-06-21
    更新: 2026-06-23 小欧 支持snippet/url/source字段，300字符截断"""
    if not items:
        return ""
    SNIPPET_MAX = 300
    lines = []
    for item in items[:OBS_MAX_DISPLAY_ITEMS]:
        if isinstance(item, str):
            lines.append(f"  {item}")
        elif isinstance(item, dict):
            name = item.get("name", item.get("title", item.get("path", "")))
            desc = item.get("snippet", item.get("description", item.get("desc", "")))
            if desc and len(desc) > SNIPPET_MAX:
                desc = desc[:SNIPPET_MAX] + "..."
            url = item.get("url", "")
            source = item.get("source", "")
            tag = f" [{source}]" if source else ""
            if desc:
                lines.append(f"  {name}: {desc}{tag}")
            elif url:
                lines.append(f"  {name}: {url}{tag}")
            else:
                lines.append(f"  {name}{tag}")
    if len(items) > OBS_MAX_DISPLAY_ITEMS:
        lines.append(f"  ... 还有 {len(items) - OBS_MAX_DISPLAY_ITEMS} 项")
    return "\n".join(lines)


def _format_rows(rows: list) -> str:
    """格式化数据库行 — 小欧 2026-06-21"""
    if not rows:
        return ""
    lines = []
    for row in rows[:OBS_MAX_DISPLAY_ITEMS]:
        if isinstance(row, (list, tuple)):
            lines.append(" | ".join(str(v) for v in row))
        elif isinstance(row, dict):
            parts = [f"{k}={v}" for k, v in row.items() if v is not None]
            lines.append(" | ".join(parts))
    if len(rows) > OBS_MAX_DISPLAY_ITEMS:
        lines.append(f"  ... 还有 {len(rows) - OBS_MAX_DISPLAY_ITEMS} 行")
    return "\n".join(lines)


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
                col_str = ", ".join(str(c) for c in cols)
                lines.append(f"  {name}: {col_str}")
            else:
                lines.append(f"  {name}")
    if len(tables) > OBS_MAX_DISPLAY_ITEMS:
        lines.append(f"  ... 还有 {len(tables) - OBS_MAX_DISPLAY_ITEMS} 张表")
    return "\n".join(lines)


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


def _format_key_value(data: dict) -> str:
    """格式化键值对 — 小欧 2026-06-21 — 小欧 2026-07-04 统一截断"""
    lines = []
    keys_shown = 0
    for k, v in data.items():
        if keys_shown >= OBS_DICT_MAX_KEYS:
            lines.append(f"  ... 还有 {len(data) - OBS_DICT_MAX_KEYS} 个字段")
            break
        keys_shown += 1
        if isinstance(v, dict):
            for sk, sv in v.items():
                sv_str = str(sv)
                if len(sv_str) > OBS_MAX_STRING_LENGTH:
                    sv_str = sv_str[:OBS_MAX_STRING_LENGTH] + "..."
                lines.append(f"  {k}.{sk}: {sv_str}")
        elif isinstance(v, list):
            v_list = v[:OBS_MAX_DISPLAY_ITEMS]
            v_str = safe_json_dumps(v_list, ensure_ascii=False)
            if len(v) > OBS_MAX_DISPLAY_ITEMS:
                v_str += f" ... (共{len(v)}项)"
            if len(v_str) > OBS_MAX_STRING_LENGTH:
                v_str = v_str[:OBS_MAX_STRING_LENGTH] + "..."
            lines.append(f"  {k}: {v_str}")
        else:
            v_str = str(v)
            if len(v_str) > OBS_MAX_STRING_LENGTH:
                v_str = v_str[:OBS_MAX_STRING_LENGTH] + "..."
            lines.append(f"  {k}: {v_str}")
    return "\n".join(lines)


def _format_matches(matches: list) -> str:
    """格式化 grep 匹配结果 — 小欧 2026-07-04 — 小欧 2026-07-04 使用 OBS_MAX_DISPLAY_ITEMS"""
    if not matches:
        return ""
    lines = []
    for i, m in enumerate(matches):
        if i >= OBS_MAX_DISPLAY_ITEMS:
            lines.append(f"  ... 还有 {len(matches) - OBS_MAX_DISPLAY_ITEMS} 个匹配项")
            break
        matched = m.get("matched", [])
        matched_str = ", ".join(matched) if isinstance(matched, list) else str(matched)
        content = m.get("content", "")
        lines.append(f"  {m.get('file','')}:{m.get('line','')}: [{matched_str}] {content}")
    return "\n".join(lines)
