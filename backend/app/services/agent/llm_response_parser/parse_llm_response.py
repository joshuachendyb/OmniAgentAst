# -*- coding: utf-8 -*-
"""
LLM响应解析 — 简化版

只保留核心解析:dict/list/空值/标准JSON/混合文本JSON
删除:非标准JSON策略、正则兜底、关键词匹配、已知工具名匹配

【流程图 - 小沈 2026-06-09】
输入(str) → _HANDLERS链式调用
  ├─ _handle_empty_input → 空输入处理
  ├─ _handle_dict_input → dict直接返回
  ├─ _handle_list_input → list处理
  ├─ _handle_json_array_string → JSON数组字符串
  ├─ _handle_standard_json → 标准JSON提取
  └─ _handle_mixed_text_json → 混合文本JSON
       ↓
  _extract_json_with_balanced_braces → JSON提取
       ↓
  _process_json_result → 结果处理
       ├─ _build_type_result → type字段处理
       ├─ _build_action_from_new_format → 新格式action
       ├─ _build_action_from_fc_format → function calling格式
       └─ _build_action_from_old_format → 旧格式action
            ↓
  _process_tool_params → 参数处理
       ├─ _normalize_tool_params_content → 内容归一化
       └─ _filter_tool_params → 参数过滤

【分层职责】
- parse_llm_response.py: 主入口，HANDLERS分派
- _utils.py: 通用工具函数（JSON提取、字符串处理）
- _tool_params.py: 工具参数处理（归一化、过滤）
- _result_builders.py: 结果构建（type/action/answer等）

Author: 小沈 - 2026-06-07
"""

import re
from typing import Dict, Any, Optional
from app.utils.json_utils import parse_json

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
        parsed_list = parse_json(output)
        if isinstance(parsed_list, list):
            return _create_action_result_from_list(parsed_list)
    return None


def _handle_empty_input(output) -> Optional[Dict[str, Any]]:
    if not output or not isinstance(output, str):
        thought = "(Implicit) Empty response"
        return _build_handler_result(
            type_="parse_error",
            thought=thought,
            content=thought,
            reasoning=thought,
            error="Empty or non-string response from LLM",
            response=""
        )
    return None


def _handle_standard_json(output) -> Optional[Dict[str, Any]]:
    if not isinstance(output, str):
        return None
    data = parse_json(output)
    if not isinstance(data, dict):
        return None
    return _process_json_result(data, output)


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
    reasoning = json_data.get("reasoning", "")
    return _build_handler_result("answer", thought=thought, content=content, reasoning=reasoning, response=content)


def _handle_implicit_content(json_data: Dict, output: str, prefix_text: str) -> Optional[Dict[str, Any]]:
    if "content" not in json_data and "reasoning" not in json_data:
        return None
    if re.search(r'\bAction\s*:', output, re.IGNORECASE) or \
       re.search(r'\bAnswer\s*:', output, re.IGNORECASE):
        return None
    content = json_data.get("content", "")
    reasoning = json_data.get("reasoning", "")
    if isinstance(content, str) and content.startswith("{"):
        parsed = parse_json(content)
        if isinstance(parsed, dict):
            content = parsed.get("content", content)
    return _build_handler_result("implicit", thought=prefix_text or content,
        content=content, reasoning=reasoning, response=content)


def _extract_json_block_simple(output: str) -> Optional[Dict]:
    last_brace = output.rfind("{")
    if last_brace == -1:
        return None
    substr = output[last_brace:]
    json_str, _ = _extract_json_with_balanced_braces(substr)
    if not json_str:
        return None
    data = parse_json(json_str)
    if isinstance(data, dict):
        return data
    return None


def _extract_json_and_prefix(output: str) -> tuple:
    """提取JSON块和前缀文本 — 小沈 2026-06-08"""
    json_data = _extract_json_block_simple(output)
    prefix_text = ""
    if json_data:
        json_start = output.find("{")
        prefix_text = output[:json_start].strip() if json_start != -1 else ""
    return json_data, prefix_text


def _build_chunk_result(output: str) -> Dict[str, Any]:
    """构建chunk结果 — 小沈 2026-06-08"""
    return _build_handler_result("chunk", thought=output.strip())


def _build_action_result(json_data: Dict, prefix_text: str, output: str) -> Dict[str, Any]:
    """构建action结果 — 小沈 2026-06-08"""
    tool_name = json_data.get("tool_name")
    tool_params = json_data.get("tool_params", {})
    if not isinstance(tool_params, dict):
        tool_params = {}
    extracted = json_data.get("content", "") or prefix_text
    params = _process_tool_params(tool_params, tool_name, output)
    return _build_handler_result("action", thought=json_data.get("thought", ""),
        content=extracted, tool_name=tool_name, tool_params=params)


def _handle_mixed_text_json(output) -> Optional[Dict[str, Any]]:
    """处理混合文本JSON — 小沈 2026-06-08 重构"""
    if not isinstance(output, str):
        return None
    
    json_data, prefix_text = _extract_json_and_prefix(output)
    
    if not json_data:
        return _build_chunk_result(output)
    
    tool_name = json_data.get("tool_name")
    
    if tool_name == "finish":
        return _handle_finish_tool(json_data, prefix_text)
    
    if tool_name:
        return _build_action_result(json_data, prefix_text, output)
    
    return _handle_implicit_content(json_data, output, prefix_text)


_HANDLERS = [
    _handle_dict_input,
    _handle_list_input,
    _handle_json_array_string,
    _handle_empty_input,
    _handle_standard_json,
    _handle_mixed_text_json,
]


def parse_llm_response(output: str) -> Dict[str, Any]:
    """解析LLM响应 — 支持多种格式（dict/list/JSON/混合文本）"""
    output_length = len(output) if isinstance(output, str) else 0
    logger.info(f"[parse_llm_response] 解析器链开始, output长度: {output_length}")
    for handler in _HANDLERS:
        result = handler(output)
        if result is not None:
            return result
    return _build_handler_result(
        type_="parse_error",
        thought="(Implicit) Internal error",
        content="",
        reasoning="",
        error="Parser chain exhausted",
        response=""
    )
