# -*- coding: utf-8 -*-
"""
结果构建模块(第4层 - 依赖 _utils, _tool_params)

重写记录 — 小欧 2026-06-07:
- TYPE-3: 4次 isinstance(data, dict) 用 type_guards.validate_data_dict 统一

Author: 小欧 - 2026-06-07
"""
from typing import Dict, Any, Optional, List

from app.utils.logger import logger
from app.utils.json_utils import parse_json
from ._utils import _add_reasoning_warning, _normalize_result_to_str, _build_handler_result, _make_action_result_dict
from ._tool_params import _process_tool_params


def _process_json_result(data: Dict, output: str) -> Optional[Dict[str, Any]]:
    explicit_type = data.get("type")
    if explicit_type in ("parse_error", "answer", "chunk"):
        return _build_type_result(data, explicit_type)

    if "tool_name" in data:
        return _build_action_from_new_format(data, output)

    if "name" in data and ("arguments" in data or "args" in data):
        return _build_action_from_fc_format(data, output)

    if "action" in data:
        return _build_action_from_old_format(data, output)

    return None


def _build_type_result(data: Dict, type_: str) -> Dict[str, Any]:
    """通用type结果构建 — P3-3 合并 _build_parse_error_result/_build_answer_result/_build_chunk_result"""
    return _build_handler_result(
        type_=type_,
        thought=data.get("thought", data.get("content", "")),
        content=data.get("content", ""),
        reasoning=data.get("reasoning", ""),
        error=data.get("error", ""),
        response=data.get("response", data.get("content", ""))
    )


def _build_action_result(type_: str, thought: str, content: str, reasoning: str,
                         tool_name: Optional[str], tool_params: Optional[Dict],
                         response: Any, pending_calls: Optional[List] = None) -> Dict[str, Any]:
    """统一构建action结果字典 - 小欧 2026-06-09"""
    result = {
        "type": type_, "thought": thought, "content": content,
        "reasoning": reasoning, "tool_name": tool_name,
        "tool_params": tool_params, "response": response,
    }
    if pending_calls:
        result["_pending_calls"] = pending_calls
    return result


def _build_action_from_fc_format(data: Dict, output: str) -> Dict[str, Any]:
    tool_name = data["name"]
    is_finish = tool_name == "finish"

    raw_args = data.get("arguments", data.get("args", {}))
    if isinstance(raw_args, str):
        raw_args = parse_json(raw_args) or {}
    if not isinstance(raw_args, dict):
        raw_args = {}

    if is_finish and raw_args.get("result"):
        raw_result = raw_args["result"]
        response = _normalize_result_to_str(raw_result)
    else:
        response = ""

    processed_params = None if is_finish else _process_tool_params(raw_args, tool_name, output)

    result = _build_action_result(
        "answer" if is_finish else "action",
        data.get("thought", ""), data.get("thought", ""),
        data.get("reasoning", ""),
        None if is_finish else tool_name, processed_params, response
    )

    logger.info(f"[parse_llm_response] FC格式转换: name={tool_name} → type={result['type']}")
    return _add_reasoning_warning(result)


def _build_action_from_new_format(data: Dict, output: str) -> Dict[str, Any]:
    tool_name = data["tool_name"]
    is_finish = tool_name == "finish"

    if is_finish and data.get("tool_params", {}).get("result"):
        raw_result = data["tool_params"]["result"]
        response = _normalize_result_to_str(raw_result)
    else:
        response = data.get("response", "")

    raw_params = data.get("tool_params", data.get("args", {}))
    processed_tool_params = None if is_finish else _process_tool_params(
        raw_params, tool_name, output
    )

    return _build_action_result(
        "answer" if is_finish else "action",
        data.get("content", data.get("thought", "")),
        data.get("content", data.get("thought", "")),
        data.get("reasoning", ""),
        None if is_finish else tool_name, processed_tool_params, response,
        data.get("_pending_calls")
    )


def _build_action_from_old_format(data: Dict, output: str = "") -> Dict[str, Any]:
    action_name = data["action"]
    is_finish = action_name == "finish"

    if is_finish and data.get("action_input", {}).get("result"):
        raw_result = data["action_input"]["result"]
        response = _normalize_result_to_str(raw_result)
    else:
        response = ""

    raw_params = data.get("action_input", data.get("args", {}))
    processed_tool_params = None if is_finish else _process_tool_params(
        raw_params, action_name, output
    )
    return _build_action_result(
        "answer" if is_finish else "action",
        data.get("thought", ""), data.get("thought", ""),
        data.get("reasoning", ""),
        None if is_finish else action_name, processed_tool_params, response,
        data.get("_pending_calls")
    )


def _resolve_return_type(data: Dict) -> Dict[str, Any]:
    thought, content = data.get("thought", ""), data.get("content", data.get("thought", ""))
    reasoning = data.get("reasoning", "")
    raw_params = data.get("tool_params", data.get("args", {}))
    tool_params = _process_tool_params(raw_params, data.get("tool_name"), None)
    pending = data.get("_pending_calls")
    tool_name = data.get("tool_name")

    if tool_name == "finish":
        raw_result = tool_params.get("result") if isinstance(tool_params, dict) else None
        result_text = _normalize_result_to_str(raw_result) if raw_result is not None else ""
        return _make_action_result_dict(
            "answer", content, result_text or content, reasoning,
            None, None, result_text or content, None, pending)

    if not tool_name:
        logger.warning(f"[_create_action_result_from_dict] tool_name为空,降级为implicit")
        return _make_action_result_dict(
            "implicit", thought, content, reasoning,
            None, None, content or thought, None, pending)

    return _make_action_result_dict(
        "action", thought, content, reasoning,
        tool_name, tool_params, None, None, pending)


def _create_action_result_from_dict(data: Dict) -> Dict[str, Any]:
    if not data or not isinstance(data, dict):
        return _make_action_result_dict("parse_error", "", "", "", None, None, "", "Empty or invalid dict input")

    explicit_type = data.get("type")
    if explicit_type in ("parse_error", "answer", "chunk"):
        return _build_type_result(data, explicit_type)

    if "action" in data and "tool_name" not in data:
        output = json.dumps(data, ensure_ascii=False) if isinstance(data, dict) else str(data)
        return _build_action_from_old_format(data, output)

    return _resolve_return_type(data)


def _create_action_result_from_list(data: List) -> Dict[str, Any]:
    if not data:
        logger.info(f"[parse_llm_response] list为空,返回parse_error")
        return _make_action_result_dict(
            "parse_error", "", "", None, None, "", "Empty list input from LLM"
        )

    valid_items = [item for item in data if isinstance(item, dict)]
    if not valid_items:
        logger.info(f"[parse_llm_response] list中无有效dict元素,返回parse_error")
        return _make_action_result_dict(
            "parse_error", "", "", None, None, "", "No valid dict items in list"
        )

    last_item = valid_items[-1]

    if "tool_name" not in valid_items[0] and "function" in valid_items[0]:
        func = valid_items[0].get("function", {})
        fname = func.get("name", "") if isinstance(func, dict) else ""
        fargs_str = func.get("arguments", "{}") if isinstance(func, dict) else "{}"
        fargs = parse_json(fargs_str) if isinstance(fargs_str, str) else (fargs_str or {})
        if fargs is None:
            fargs = {}
        pending_calls = [{"name": fname, "args": fargs}] if len(valid_items) > 1 else []
        logger.info(f"[parse_llm_response] list检测到Function Calling格式")
        last_item = {
            "tool_name": fname,
            "tool_params": fargs,
            "content": last_item.get("content", ""),
            "thought": last_item.get("thought", last_item.get("content", "")),
            "reasoning": last_item.get("reasoning", ""),
        }
        if pending_calls:
            last_item["_pending_calls"] = pending_calls

    logger.info(f"[parse_llm_response] list解析成功,使用最后一个元素")
    return _create_action_result_from_dict(last_item)



