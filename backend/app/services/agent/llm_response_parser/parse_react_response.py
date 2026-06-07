# -*- coding: utf-8 -*-
"""
LLM响应解析 — 简化版

只保留核心解析:dict/list/空值/标准JSON/混合文本JSON
删除:非标准JSON策略、正则兜底、关键词匹配、已知工具名匹配

Author: 小沈 - 2026-06-07
"""

import re
import json
from typing import Dict, Any, Optional

from app.utils.logger import logger
from ._utils import _add_reasoning_warning, _normalize_result_to_str, _build_handler_result, _extract_json_with_balanced_braces
from ._tool_params import _normalize_tool_params_content, _filter_tool_params, _process_tool_params
from ._result_builders import _process_json_result, _create_action_result_from_dict, _create_action_result_from_list


def _handle_dict_input(output) -> Optional[Dict[str, Any]]:
    if isinstance(output, dict):
        return _create_action_result_from_dict(output)
    return None


def _handle_list_input(output) -> Optional[Dict[str, Any]]:
    if isinstance(output, list):
        return _create_action_result_from_list(output)
    return None


def _handle_json_array_string(output) -> Optional[Dict[str, Any]]:
    if isinstance(output, str) and output.strip().startswith("["):
        try:
            parsed_list = json.loads(output)
            if isinstance(parsed_list, list):
                return _create_action_result_from_list(parsed_list)
        except (json.JSONDecodeError, TypeError):
            pass
    return None


def _handle_empty_input(output) -> Optional[Dict[str, Any]]:
    if not output or not isinstance(output, str):
        thought = "(Implicit) Empty response"
        return {
            "type": "parse_error",
            "error": "Empty or non-string response from LLM",
            "thought": thought,
            "content": thought,
            "reasoning": thought,
            "tool_name": None,
            "tool_params": None,
            "response": ""
        }
    return None


def _handle_standard_json(output) -> Optional[Dict[str, Any]]:
    if not isinstance(output, str):
        return None
    try:
        data = json.loads(output)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    result = _process_json_result(data, output)
    return result


def _handle_finish_tool(json_data: Dict, prefix_text: str) -> Optional[Dict[str, Any]]:
    tool_params = json_data.get("tool_params", {})
    if not isinstance(tool_params, dict):
        tool_params = {}
    raw_result = tool_params.get("result") if tool_params else None
    result_text = _normalize_result_to_str(raw_result) if raw_result is not None else ""
    if prefix_text and result_text:
        content = prefix_text + ("\n\n" + result_text if result_text not in prefix_text else "")
    else:
        content = prefix_text or result_text or ""
    thought = prefix_text or json_data.get("thought", "")
    return _build_handler_result("answer", thought=thought, content=content, response=content)


def _handle_implicit_content(json_data: Dict, output: str, prefix_text: str) -> Optional[Dict[str, Any]]:
    if "content" not in json_data and "reasoning" not in json_data:
        return None
    if re.search(r'\bAction\s*:', output, re.IGNORECASE) or \
       re.search(r'\bAnswer\s*:', output, re.IGNORECASE):
        return None
    content = json_data.get("content", "")
    reasoning = json_data.get("reasoning", "")
    if isinstance(content, str) and content.startswith("{"):
        try:
            parsed = json.loads(content)
            if isinstance(parsed, dict):
                content = parsed.get("content", content)
        except (json.JSONDecodeError, TypeError):
            pass
    return _build_handler_result("implicit", thought=prefix_text or content,
        content=content, reasoning=reasoning, response=content)


def _extract_json_block_simple(output: str) -> Optional[Dict]:
    """简单JSON块提取:找最后一个平衡花括号对"""
    last_brace = output.rfind("{")
    if last_brace == -1:
        return None
    substr = output[last_brace:]
    json_str, _ = _extract_json_with_balanced_braces(substr)
    if not json_str:
        return None
    try:
        data = json.loads(json_str)
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, TypeError):
        pass
    return None


def _handle_mixed_text_json(output) -> Optional[Dict[str, Any]]:
    if not isinstance(output, str):
        return None
    json_data = _extract_json_block_simple(output)
    prefix_text = ""
    if json_data:
        json_start = output.find("{")
        prefix_text = output[:json_start].strip() if json_start != -1 else ""
    if not json_data:
        return _build_handler_result("chunk", thought=output.strip())
    tool_name = json_data.get("tool_name")
    tool_params = json_data.get("tool_params", {})
    if not isinstance(tool_params, dict):
        tool_params = {}
    if tool_name == "finish":
        return _handle_finish_tool(json_data, prefix_text)
    if tool_name:
        extracted = json_data.get("content", "") or prefix_text
        params = _process_tool_params(tool_params, tool_name, output)
        return _build_handler_result("action", thought=json_data.get("thought", ""),
            content=extracted, tool_name=tool_name, tool_params=params)
    return _handle_implicit_content(json_data, output, prefix_text)


_HANDLERS = [
    _handle_dict_input,
    _handle_list_input,
    _handle_json_array_string,
    _handle_empty_input,
    _handle_standard_json,
    _handle_mixed_text_json,
]


def parse_react_response(output: str) -> Dict[str, Any]:
    """解析LLM响应 — 简化版,6个核心handler"""
    output_length = len(output) if isinstance(output, str) else 0
    logger.info(f"[parse_react_response] 解析器链开始, output长度: {output_length}")
    for handler in _HANDLERS:
        result = handler(output)
        if result is not None:
            return result
    return {
        "type": "parse_error",
        "error": "Parser chain exhausted",
        "thought": "(Implicit) Internal error",
        "content": "",
        "reasoning": "",
        "tool_name": None,
        "tool_params": None,
        "response": ""
    }
