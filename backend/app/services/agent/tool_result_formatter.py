# -*- coding: utf-8 -*-
"""
工具结果格式化模块 — 小沈 2026-05-21

提供两条输出路径：
- format_llm_observation(): 给LLM看的observation文本
- _format_frontend_event(): 给前端SSE事件的dict

设计原则：
- 工具自控：通过llm_data字段控制给LLM的数据量，格式化层不做业务截断
- 安全兜底：仅在data极端大时防json.dumps OOM
"""

import json
from typing import Any, Dict, List, Optional

from app.constants import SUCCESS_CODE, LLM_SAFE_LIMIT
from app.utils.data_utils import safe_truncate


def _get_failure_hint(tool_name: str, tool_params: Optional[dict] = None) -> str:
    """工具执行失败时获取替代建议 — 小健 2026-05-24

    优先从tool_registry获取工具自定义提示，
    无自定义提示时返回通用重试建议。
    """
    try:
        from app.services.tools.registry import tool_registry
        meta = tool_registry.get_tool(tool_name)
        if meta and hasattr(meta, 'get_failure_hint'):
            hint = meta.get_failure_hint(tool_params)
            if hint:
                return hint
    except Exception:
        pass
    return "请尝试其他可用工具，不要重复调用同一失败操作。"


def extract_status(result: dict) -> str:
    """从工具统一返回格式提取Agent消费的status字段 — 小健 2026-05-21

    映射规则:
      SUCCESS        → "success"
      WARNING_*      → "warning"
      ERR_* / 其他   → "error"
    """
    code = result.get("code", SUCCESS_CODE)
    if code == SUCCESS_CODE:
        return "warning" if result.get("warning") else "success"
    elif isinstance(code, str) and code.startswith("WARNING_"):
        return "warning"
    else:
        return "error"


def build_execution_result_dict(execution_result: Dict[str, Any]) -> Dict[str, Any]:
    """从工具返回结果构建统一格式dict（供StepFactory使用）— 小健 2026-05-24

    统一主工具和并行工具的execution_result_dict构建逻辑。
    """
    _status = extract_status(execution_result)
    return {
        "status": _status,
        "summary": execution_result.get("message", ""),
        "data": execution_result.get("data"),
        "retry_count": execution_result.get("retry_count", 0),
        "code": execution_result.get("code", "SUCCESS"),
        "warning": execution_result.get("warning"),
        "attachment": execution_result.get("attachment"),
        "next_actions": execution_result.get("next_actions"),
        "return_direct": execution_result.get("return_direct", False),
        "error_message": execution_result.get("error_message", ""),
    }


def _format_next_actions(result: dict, text: str) -> str:
    """将next_actions格式化为文本追加到observation — 小健 2026-05-22"""
    next_actions = result.get('next_actions')
    if not next_actions or not isinstance(next_actions, list):
        return text
    na_lines = ["\n推荐下一步操作:"]
    for i, na in enumerate(next_actions[:5], 1):
        if isinstance(na, dict):
            tool = na.get('tool', '')
            desc = na.get('description', '')
            when = na.get('when', '')
            params = na.get('params')
            line = f"  {i}. {tool}"
            if desc:
                line += f" - {desc}"
            if when:
                line += f"（{when}）"
            if params:
                line += f" 参数建议: {params}"
        elif isinstance(na, tuple) and len(na) >= 2:
            line = f"  {i}. {na[0]} - {na[1]}"
        else:
            line = f"  {i}. {na}"
        na_lines.append(line)
    return text + "\n".join(na_lines)


def format_llm_observation(result: dict, tool_name: str = "", tool_params: Optional[dict] = None) -> str:
    """
    格式化工具结果为LLM observation文本 — 小沈 2026-05-21
    更新 2026-05-22 小健：合入next_actions拼接逻辑（从base_react.py搬入）
    工具通过 llm_data 自行控制给LLM的数据量，格式化层不做业务截断
    更新 2026-05-24 小健：增加 tool_name/tool_params 参数供 failure hint 使用
    """
    code = result.get("code", "SUCCESS")
    LLM_SAFE_LIMIT_LOCAL = LLM_SAFE_LIMIT

    from app.utils.logger import logger as _logger

    if code == "SUCCESS":
        display_data = result.get("llm_data") or result.get("data")
        if display_data is None:
            _logger.warning("[OBS-001] format_llm_observation: llm_data和data均为空")
        text = f"Observation: success - {result.get('message', '')}"
        if result.get("warning"):
            text += f"\n⚠ 警告: {result['warning']}"
        if display_data:
            if isinstance(display_data, (dict, list)):
                display_data = safe_truncate(display_data, LLM_SAFE_LIMIT_LOCAL)
            text += f"\n数据: {json.dumps(display_data, ensure_ascii=False)}"
        text = _format_next_actions(result, text)
        return text

    elif code.startswith("WARNING_"):
        text = f"Observation: warning - {result.get('message', '')}"
        if result.get("data"):
            data = result["data"]
            if isinstance(data, (dict, list)):
                data = safe_truncate(data, LLM_SAFE_LIMIT_LOCAL)
            text += f"\n部分数据: {json.dumps(data, ensure_ascii=False)}"
        text = _format_next_actions(result, text)
        return text

    else:  # ERR_*
        text = f"Observation: error [{code}] - {result.get('message', '')}"
        if tool_name:
            hint = _get_failure_hint(tool_name, tool_params)
            if hint:
                text += f"\n{hint}"
        text = _format_next_actions(result, text)
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
    if result.get("attachment"):
        event["attachment"] = result["attachment"]
    return event
