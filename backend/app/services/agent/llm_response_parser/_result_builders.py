# -*- coding: utf-8 -*-
"""
结果构建模块（第4层 - 依赖 _utils, _tool_params）
"""

import json as _json
import json
from typing import Dict, Any, Optional, List

from app.utils.logger import logger
from ._utils import _add_reasoning_warning, _normalize_result_to_str, _build_handler_result, _make_action_result_dict
from ._tool_params import _process_tool_params


def _process_json_result(data: Dict, output: str) -> Optional[Dict[str, Any]]:
    explicit_type = data.get("type")
    if explicit_type == "parse_error":
        return _build_parse_error_result(data)
    if explicit_type == "answer":
        return _build_answer_result(data)
    if explicit_type == "chunk":
        return _build_chunk_result(data)

    if "tool_name" in data:
        return _build_action_from_new_format(data, output)

    if "name" in data and ("arguments" in data or "args" in data):
        return _build_action_from_fc_format(data, output)

    if "action" in data:
        return _build_action_from_old_format(data, output)

    return None


def _build_parse_error_result(data: Dict) -> Dict[str, Any]:
    return _build_handler_result(
        type_="parse_error",
        thought=data.get("content", data.get("thought", "")),
        content=data.get("content", ""),
        reasoning=data.get("reasoning", ""),
        error=data.get("error", "LLM返回解析错误"),
        response=data.get("content", "")
    )


def _build_answer_result(data: Dict) -> Dict[str, Any]:
    return _build_handler_result(
        type_="answer",
        thought=data.get("thought", ""),
        content=data.get("content", ""),
        reasoning=data.get("reasoning", ""),
        response=data.get("response", data.get("content", ""))
    )


def _build_chunk_result(data: Dict) -> Dict[str, Any]:
    return _build_handler_result(
        type_="chunk",
        thought=data.get("thought", ""),
        content=data.get("content", ""),
        reasoning=data.get("reasoning", ""),
        response=data.get("response", data.get("content", ""))
    )


def _build_action_from_fc_format(data: Dict, output: str) -> Dict[str, Any]:
    tool_name = data["name"]
    is_finish = tool_name == "finish"

    raw_args = data.get("arguments", data.get("args", {}))
    if isinstance(raw_args, str):
        try:
            raw_args = json.loads(raw_args)
        except (json.JSONDecodeError, TypeError):
            raw_args = {}
    if not isinstance(raw_args, dict):
        raw_args = {}

    if is_finish and raw_args.get("result"):
        raw_result = raw_args["result"]
        response = _normalize_result_to_str(raw_result)
    else:
        response = ""

    processed_params = None if is_finish else _process_tool_params(raw_args, tool_name, output)

    result = {
        "type": "answer" if is_finish else "action",
        "thought": data.get("thought", ""),
        "content": data.get("thought", ""),
        "reasoning": data.get("reasoning", ""),
        "tool_name": None if is_finish else tool_name,
        "tool_params": processed_params,
        "response": response,
    }

    logger.info(f"[parse_react_response] FC格式转换: name={tool_name} → type={result['type']}")
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

    result = {
        "type": "answer" if is_finish else "action",
        "thought": data.get("content", data.get("thought", "")),
        "content": data.get("content", data.get("thought", "")),
        "reasoning": data.get("reasoning", ""),
        "tool_name": None if is_finish else tool_name,
        "tool_params": processed_tool_params,
        "response": response
    }
    if "_pending_calls" in data:
        result["_pending_calls"] = data["_pending_calls"]
    return result


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
    result = {
        "type": "answer" if is_finish else "action",
        "thought": data.get("thought", ""),
        "content": data.get("thought", ""),
        "reasoning": data.get("reasoning", ""),
        "tool_name": None if is_finish else action_name,
        "tool_params": processed_tool_params,
        "response": response
    }
    if "_pending_calls" in data:
        result["_pending_calls"] = data["_pending_calls"]
    return result


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
        logger.warning(f"[_create_action_result_from_dict] tool_name为空，降级为implicit")
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
    if explicit_type == "parse_error":
        return _build_parse_error_result(data)
    if explicit_type == "answer":
        return _build_answer_result(data)
    if explicit_type == "chunk":
        return _build_chunk_result(data)

    if "action" in data and "tool_name" not in data:
        output = json.dumps(data, ensure_ascii=False) if isinstance(data, dict) else str(data)
        return _build_action_from_old_format(data, output)

    return _resolve_return_type(data)


def _convert_function_calling_items(items: List[Dict]) -> List[Dict]:
    converted = []
    for item in items:
        if isinstance(item, dict) and "function" in item:
            func = item["function"]
            fname = func.get("name", "") if isinstance(func, dict) else ""
            fargs_str = func.get("arguments", "{}") if isinstance(func, dict) else "{}"
            try:
                fargs = _json.loads(fargs_str) if isinstance(fargs_str, str) else (fargs_str or {})
            except (_json.JSONDecodeError, TypeError):
                fargs = {}
            converted.append({"name": fname, "args": fargs})
        else:
            converted.append(item)
    return converted


def _create_action_result_from_list(data: List) -> Dict[str, Any]:
    if not data:
        logger.info(f"[parse_react_response] list为空，返回parse_error")
        return _make_action_result_dict(
            "parse_error", "", "", None, None, "", "Empty list input from LLM"
        )

    valid_items = [item for item in data if isinstance(item, dict)]
    if not valid_items:
        logger.info(f"[parse_react_response] list中无有效dict元素，返回parse_error")
        return _make_action_result_dict(
            "parse_error", "", "", None, None, "", "No valid dict items in list"
        )

    last_item = valid_items[-1]

    if "tool_name" not in valid_items[0] and "function" in valid_items[0]:
        converted = _convert_function_calling_items(valid_items)
        last_converted = converted[-1]
        pending_calls = converted[:-1]
        logger.info(f"[parse_react_response] list检测到Function Calling格式({len(converted)}个)")
        last_item = {
            "tool_name": last_converted["name"],
            "tool_params": last_converted["args"],
            "content": last_item.get("content", ""),
            "thought": last_item.get("thought", last_item.get("content", "")),
            "reasoning": last_item.get("reasoning", ""),
        }
        if pending_calls:
            last_item["_pending_calls"] = pending_calls

    logger.info(f"[parse_react_response] list解析成功，使用最后一个元素")
    return _create_action_result_from_dict(last_item)


def _create_action_result(parsed: Dict, original_output: str) -> Dict[str, Any]:
    if not parsed or not isinstance(parsed, dict):
        return {
            "type": "implicit",
            "thought": "",
            "content": original_output or "",
            "reasoning": "",
            "tool_name": None,
            "tool_params": None,
            "response": original_output or "",
            "error": None
        }

    tool_name = parsed.get("tool_name", parsed.get("action_tool", parsed.get("action", None)))
    tool_params = parsed.get("tool_params", parsed.get("params", parsed.get("action_input", parsed.get("args", {}))))

    if isinstance(tool_params, dict):
        tool_params = _process_tool_params(tool_params, tool_name, original_output)

    if tool_name is None:
        content_for_check = parsed.get("content", "") or parsed.get("thought", "") or ""
        finish_keywords = ["完成", "结束", "任务完成", "已经", "finished", "complete", "done"]
        if any(kw in content_for_check for kw in finish_keywords):
            result_text = parsed.get("content", "")
            return {
                "type": "answer",
                "thought": parsed.get("thought", ""),
                "content": result_text,
                "reasoning": parsed.get("reasoning", ""),
                "tool_name": None,
                "tool_params": None,
                "response": result_text,
                "error": None
            }

    if not isinstance(tool_params, dict):
        tool_params = {}

    if tool_name == "finish":
        result_text = tool_params.get("result", "") if tool_params else ""
        return {
            "type": "answer",
            "thought": parsed.get("thought", ""),
            "content": result_text or parsed.get("content", ""),
            "reasoning": parsed.get("reasoning", ""),
            "tool_name": None,
            "tool_params": None,
            "response": result_text or parsed.get("content", ""),
            "error": None
        }

    final_tool_params = tool_params
    result = {
        "type": "action",
        "thought": parsed.get("thought", ""),
        "content": parsed.get("content", parsed.get("thought", original_output.strip())),
        "reasoning": parsed.get("reasoning", ""),
        "tool_name": tool_name,
        "tool_params": final_tool_params,
        "response": None,
        "error": None
    }
    return _add_reasoning_warning(result)
