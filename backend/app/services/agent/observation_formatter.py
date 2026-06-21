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
- 工具自控:通过llm_data字段控制给LLM的数据量,格式化层不做业务截断
- 安全兜底:format_data_detail加try-except确保不崩
- 三段式:观察行 + 结果行 + 详情行
"""

import json
from typing import Any, Dict


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
            return data["content"]

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
            return "\n".join(parts)

        if "events" in data:
            return _format_events(data["events"])

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
        text += f"\n结果: {summary}"

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
    for row in rows:
        if isinstance(row, (list, tuple)):
            parts = [f"{h}={v}" for h, v in zip(headers, row) if v is not None]
            lines.append(" | ".join(parts))
        elif isinstance(row, dict):
            parts = [f"{h}={row.get(h, '')}" for h in headers if row.get(h) is not None]
            lines.append(" | ".join(parts))
    return "\n".join(lines)


def _format_entries(entries: list) -> str:
    """格式化目录列表 — 小欧 2026-06-21"""
    if not entries:
        return ""
    lines = []
    for entry in entries:
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
    return "\n".join(lines)


def _format_items(items: list) -> str:
    """格式化搜索结果/列表项 — 小欧 2026-06-21"""
    if not items:
        return ""
    lines = []
    for item in items:
        if isinstance(item, str):
            lines.append(f"  {item}")
        elif isinstance(item, dict):
            name = item.get("name", item.get("title", item.get("path", "")))
            desc = item.get("description", item.get("desc", ""))
            if desc:
                lines.append(f"  {name}: {desc}")
            else:
                lines.append(f"  {name}")
    return "\n".join(lines)


def _format_rows(rows: list) -> str:
    """格式化数据库行 — 小欧 2026-06-21"""
    if not rows:
        return ""
    lines = []
    for row in rows:
        if isinstance(row, (list, tuple)):
            lines.append(" | ".join(str(v) for v in row))
        elif isinstance(row, dict):
            parts = [f"{k}={v}" for k, v in row.items() if v is not None]
            lines.append(" | ".join(parts))
    return "\n".join(lines)


def _format_schema(tables: list) -> str:
    """格式化Schema信息 — 小欧 2026-06-21"""
    if not tables:
        return ""
    lines = []
    for table in tables:
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
    return "\n".join(lines)


def _format_events(events: list) -> str:
    """格式化事件日志 — 小欧 2026-06-21"""
    if not events:
        return ""
    lines = []
    for event in events:
        if isinstance(event, str):
            lines.append(f"  {event}")
        elif isinstance(event, dict):
            ts = event.get("timestamp", event.get("time", ""))
            msg = event.get("message", event.get("event", str(event)))
            if ts:
                lines.append(f"  [{ts}] {msg}")
            else:
                lines.append(f"  {msg}")
    return "\n".join(lines)


def _format_key_value(data: dict) -> str:
    """格式化键值对 — 小欧 2026-06-21"""
    lines = []
    for k, v in data.items():
        if isinstance(v, dict):
            for sk, sv in v.items():
                lines.append(f"  {k}.{sk}: {sv}")
        elif isinstance(v, list):
            lines.append(f"  {k}: {json.dumps(v, ensure_ascii=False)}")
        else:
            lines.append(f"  {k}: {v}")
    return "\n".join(lines)
