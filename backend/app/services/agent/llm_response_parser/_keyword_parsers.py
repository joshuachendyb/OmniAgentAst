# -*- coding: utf-8 -*-
"""
关键词/ReAct 传统解析模块（第5层 - 依赖 _utils, _tool_params, _result_builders）
"""

import re
import json
from typing import Dict, Any, Optional, Tuple

from app.utils.logger import logger
from app.utils.data_utils import parse_json
from ._utils import REACT_KEYWORDS, _extract_json_with_balanced_braces, _extract_key_value_pairs
from ._tool_params import _fallback_tool_name, _normalize_tool_params, _process_tool_params, _build_action_result
from ._result_builders import _create_action_result


def _try_codeblock_parse(output: str) -> Optional[Dict[str, Any]]:
    if '```' not in output:
        return None
    try:
        json_match = re.search(r'```(?:json)?\s*\n?([\s\S]*?)\n?```', output)
        if json_match and "tool_name" in (jd := json.loads(json_match.group(1).strip())):
            return _create_action_result(jd, output)
    except Exception:
        pass
    return None


def _parse_thought_only(output: str, thought_match: re.Match) -> Dict[str, Any]:
    thought_text = output[thought_match.end():].strip()
    return {
        "type": "thought_only",
        "thought": thought_text,
        "content": thought_text,
        "reasoning": thought_text,
        "tool_name": None,
        "tool_params": None,
        "response": None,
    }


def _try_keyword_parse(output: str) -> Optional[Dict[str, Any]]:
    try:
        thought_match = re.search(REACT_KEYWORDS["thought"], output, re.IGNORECASE)
        action_match = re.search(REACT_KEYWORDS["action"], output, re.IGNORECASE)
        answer_match = re.search(REACT_KEYWORDS["answer"], output, re.IGNORECASE)

        action_idx = action_match.start() if action_match else float('inf')
        answer_idx = answer_match.start() if answer_match else float('inf')

        if action_match and action_idx < answer_idx:
            return _parse_action(output, thought_match, action_match)
        if answer_match:
            return _parse_answer(output, thought_match, answer_match)
        if thought_match:
            return _parse_thought_only(output, thought_match)
    except Exception:
        pass
    return None


def _make_fallback_result(text: str, is_implicit: bool) -> Dict[str, Any]:
    error_msg = None if is_implicit else "无法解析LLM响应，所有解析层（JSON/关键词/工具名）都失败"
    return {
        "type": "implicit" if is_implicit else "parse_error",
        "thought": text, "content": text, "reasoning": text,
        "tool_name": None, "tool_params": None,
        "response": text, "error": error_msg,
    }


def _determine_parse_type(output: str) -> Dict[str, Any]:
    if not output or not output.strip():
        return _make_fallback_result("", is_implicit=False)

    output = output.strip()

    result = _try_codeblock_parse(output)
    if result:
        return result

    result = _try_keyword_parse(output)
    if result:
        return result

    stripped = output.strip()
    is_implicit = len(stripped) >= 5
    text = stripped if is_implicit else stripped[:200]
    return _make_fallback_result(text, is_implicit=is_implicit)


def _parse_action(
    output: str,
    thought_match: Optional[re.Match],
    action_match: re.Match
) -> Dict[str, Any]:
    thought = output[thought_match.end():action_match.start()].strip() if thought_match \
        else output[:action_match.start()].strip()

    action_input_match = re.search(REACT_KEYWORDS["action_input"], output, re.IGNORECASE)
    action_start = action_match.end()

    if action_input_match:
        action_section = output[action_start:action_input_match.start()].strip()
        input_section = output[action_input_match.end():].strip()
        tool_params = _parse_action_input(input_section) or {}
    else:
        action_section = output[action_start:].strip()
        tool_params = {}

    tool_name_match = re.match(r'^([^\n\(\) ]+)', action_section)
    tool_name = tool_name_match.group(1) if tool_name_match \
        else (action_section.split()[0] if action_section else "")

    if isinstance(tool_params, dict):
        tool_name = _fallback_tool_name(tool_params, tool_name)
        tool_params = _normalize_tool_params(tool_params)

    final_tool_params = _process_tool_params(tool_params or {}, tool_name, output)
    return _build_action_result("action", tool_name, final_tool_params, thought)


def _parse_answer(
    output: str,
    thought_match: Optional[re.Match],
    answer_match: re.Match
) -> Dict[str, Any]:
    if thought_match:
        thought_start = thought_match.end()
        thought_end = answer_match.start()
        thought = output[thought_start:thought_end].strip()
    else:
        thought = ""

    answer_start = answer_match.end()
    response = output[answer_start:].strip()

    return {
        "type": "answer",
        "thought": thought,
        "content": thought,
        "reasoning": thought,
        "tool_name": None,
        "tool_params": None,
        "response": response
    }


def _try_parse_chain(input_str: str, parsers) -> Optional[Dict]:
    for parser in parsers:
        try:
            result = parser(input_str)
            if result is not None:
                return result
        except Exception:
            continue
    return None


def _try_markdown_parse(s: str) -> Optional[Dict]:
    mc = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', s, re.DOTALL | re.IGNORECASE)
    return json.loads(mc.group(1).strip()) if mc else None


def _try_json_parse(s: str) -> Optional[Dict]:
    return parse_json(s)


def _try_balanced_braces(s: str) -> Optional[Dict]:
    js, _ = _extract_json_with_balanced_braces(s)
    return json.loads(js) if js else None


def _try_single_quotes(s: str) -> Optional[Dict]:
    return json.loads(s.replace("'", '"'))


def _try_kv_parse(s: str) -> Optional[Dict]:
    return _extract_key_value_pairs(s)


_TOOL_NAME_KEYS = [r'"tool_name"', r'"action_tool"', r'"action"']
_TOOL_PARAMS_KEYS = [r'"tool_params"', r'"params"', r'"action_input"']


def _extract_fields_partial(s: str) -> Optional[Dict]:
    result = {}
    for pat in _TOOL_NAME_KEYS:
        m = re.search(rf'{pat}\s*:\s*"([^"]*)"', s)
        if m:
            result["tool_name"] = m.group(1)
            break
    for pat in _TOOL_PARAMS_KEYS:
        m = re.search(rf'{pat}\s*:\s*(\{{[^}}]*\}})', s)
        if m:
            try:
                result["tool_params"] = json.loads(m.group(1))
            except Exception:
                result["tool_params"] = {}
            break
    return result if result else None


def _parse_action_input(input_section: str) -> Dict[str, Any]:
    if not input_section:
        return {}

    PARSERS = [
        _try_markdown_parse,
        _try_json_parse,
        _try_balanced_braces,
        _try_single_quotes,
        _extract_fields_partial,
        _try_kv_parse,
    ]

    result = _try_parse_chain(input_section, PARSERS)
    if result is not None:
        return result

    logger.error(f"[_parse_action_input] All parsers failed for: {input_section[:100]}...")
    return None
