# -*- coding: utf-8 -*-
"""
工具结果格式化模块 — 小沈 2026-05-21

提供两条输出路径：
- _format_llm_observation(): 给LLM看的observation文本
- _format_frontend_event(): 给前端SSE事件的dict

设计原则：
- 工具自控：通过llm_data字段控制给LLM的数据量，格式化层不做业务截断
- 安全兜底：仅在data极端大时防json.dumps OOM
"""

import json
from typing import Any, Dict


def _safe_truncate(data: Any, limit: int) -> Any:
    """安全截断：仅防 json.dumps OOM，非业务截断 — 小沈 2026-05-21"""
    if isinstance(data, dict):
        if len(data) > limit:
            keys = list(data.keys())[:limit]
            return {k: data[k] for k in keys}
    elif isinstance(data, list):
        if len(data) > limit:
            return data[:limit]
    return data


def _format_llm_observation(result: dict) -> str:
    """
    格式化工具结果为LLM observation文本 — 小沈 2026-05-21
    工具通过 llm_data 自行控制给LLM的数据量，格式化层不做业务截断
    """
    code = result.get("code", "SUCCESS")
    LLM_SAFE_LIMIT = 100_000  # 仅防 json.dumps OOM，非业务截断

    if code == "SUCCESS":
        display_data = result.get("llm_data") or result.get("data")
        text = f"Observation: success - {result.get('message', '')}"
        if result.get("warning"):
            text += f"\n⚠ 警告: {result['warning']}"
        if display_data:
            if isinstance(display_data, (dict, list)):
                display_data = _safe_truncate(display_data, LLM_SAFE_LIMIT)
            text += f"\n数据: {json.dumps(display_data, ensure_ascii=False)}"
        return text

    elif code.startswith("WARNING_"):
        text = f"Observation: warning - {result.get('message', '')}"
        if result.get("data"):
            data = result["data"]
            if isinstance(data, (dict, list)):
                data = _safe_truncate(data, LLM_SAFE_LIMIT)
            text += f"\n部分数据: {json.dumps(data, ensure_ascii=False)}"
        return text

    else:  # ERR_*
        text = f"Observation: error [{code}] - {result.get('message', '')}"
        return text


def _format_frontend_event(result: dict) -> dict:
    """格式化工具结果为前端SSE事件 — 小沈 2026-05-21"""
    event = {
        "code": result.get("code", "SUCCESS"),
        "message": result.get("message", ""),
        "data": result.get("data"),
        "retry_count": result.get("retry_count", 0),
        "return_direct": result.get("return_direct", False),
    }
    if result.get("warning"):
        event["warning"] = result["warning"]
    if result.get("next_actions"):
        event["next_actions"] = result["next_actions"]
    return event
