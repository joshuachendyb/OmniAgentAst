# -*- coding: utf-8 -*-
"""
JSON 策略解析模块（第3层 - 依赖 _utils, _tool_params）
"""

import re
import json
from typing import Dict, Any, Optional, List

from app.utils.logger import logger
from ._utils import _extract_json_with_balanced_braces
from ._tool_params import _extract_params_by_regex_from_json_str, _extract_content_value_from_json_str


def _extract_json_string(content: str) -> Optional[str]:
    if not content:
        return None
    content = content.strip()
    json_str, _ = _extract_json_with_balanced_braces(content)
    return json_str if json_str else None


def _strategy_direct_parse(json_str: str) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        return None


def _strategy_encoding_fix(json_str: str) -> Optional[Dict[str, Any]]:
    try:
        json_fixed = json_str.encode('utf-8', errors='replace').decode('utf-8')
        return json.loads(json_fixed)
    except (json.JSONDecodeError, UnicodeError):
        return None


def _strategy_chinese_quotes(json_str: str) -> Optional[Dict[str, Any]]:
    for fix_fn in [
        lambda s: s.replace('\u201c', '\u300c').replace('\u201d', '\u300d'),
        lambda s: s.replace('\u201c', '').replace('\u201d', ''),
    ]:
        try:
            return json.loads(fix_fn(json_str))
        except json.JSONDecodeError:
            pass
    return None


def _strategy_newline_fix(json_str: str) -> Optional[Dict[str, Any]]:
    try:
        escaped = json_str.replace('\r\n', ' ').replace('\n', ' ').replace('\r', ' ')
        return json.loads(escaped)
    except json.JSONDecodeError:
        return None


def _strategy_trailing_comma(json_str: str) -> Optional[Dict[str, Any]]:
    try:
        escaped = json_str.replace('\r\n', ' ').replace('\n', ' ').replace('\r', ' ')
        fixed = re.sub(r',(\s*[}\]])', r'\1', escaped)
        return json.loads(fixed)
    except json.JSONDecodeError:
        return None


ParseStrategy = Optional[Dict[str, Any]]

STRATEGIES = [
    _strategy_direct_parse,
    _strategy_encoding_fix,
    _strategy_chinese_quotes,
    _strategy_newline_fix,
    _strategy_trailing_comma,
]


def _try_parse_with_strategies(
    json_str: str, strategies: list,
) -> Optional[Dict[str, Any]]:
    for strategy in strategies:
        result = strategy(json_str)
        if result is not None:
            return result
    return None


_FIELD_ALIASES = {
    "thought": ["thought", "content"],
    "content": ["content", "thought"],
}


def _try_extract_single_field(
    json_str: str, field: str, is_nested_object: bool,
) -> Optional[Any]:
    if is_nested_object:
        start_pattern = rf'"{field}"\s*:\s*\{{'
    else:
        start_pattern = rf'"{field}"\s*:\s*"'

    start_match = re.search(start_pattern, json_str)
    if not start_match:
        return None

    json_after, _ = _extract_json_with_balanced_braces(json_str[start_match.start():])
    if not json_after:
        return None

    try:
        partial = json.loads(json_after)
        return partial.get(field)
    except (json.JSONDecodeError, ValueError):
        pass

    if is_nested_object:
        inner_start = json_after.find('{', json_after.find(field))
        if inner_start != -1:
            inner_json, _ = _extract_json_with_balanced_braces(json_after[inner_start:])
            if inner_json:
                try:
                    return json.loads(inner_json)
                except (json.JSONDecodeError, ValueError):
                    return _extract_params_by_regex_from_json_str(json_after)
        return None

    if field == "tool_name":
        m = re.search(r'"tool_name":\s*"([^"]+)"', json_str)
        return m.group(1) if m else None

    if field in ("content", "thought"):
        val = _extract_content_value_from_json_str(json_str)
        if val:
            return val
        m = re.search(rf'"{field}"\s*:\s*"(.*?)"\s*,', json_str, re.DOTALL)
        return m.group(1) if m else None

    if field == "reasoning":
        m = re.search(r'"reasoning":\s*"([^"]*)"', json_str)
        return m.group(1) if m else None

    return None


def _extract_fields_from_json_str(
    json_str: str, fields: list,
) -> Dict[str, Any]:
    result = {}
    nested_fields = {"tool_params"}

    for field in fields:
        aliases = _FIELD_ALIASES.get(field, [field])
        is_nested = field in nested_fields

        for alias in aliases:
            value = _try_extract_single_field(json_str, alias, is_nested)
            if value is not None:
                if isinstance(value, str):
                    value = value.encode('utf-8', errors='replace').decode('utf-8', errors='replace')
                result[field] = value
                if field in ("content", "thought") and alias != field:
                    cross_field = "thought" if field == "content" else "content"
                    result[cross_field] = value
                break

        if field == "tool_params" and "tool_params" not in result:
            tp = _extract_params_by_regex_from_json_str(json_str)
            if tp:
                result["tool_params"] = tp

    return result


def _try_extract_last_tool_call(content: str) -> Optional[Dict[str, Any]]:
    last_brace = content.rfind('{')
    if last_brace < 0:
        return None
    json_str, _ = _extract_json_with_balanced_braces(content[last_brace:])
    if not json_str:
        return None
    data = _try_parse_with_strategies(json_str, STRATEGIES)
    if data and data.get("tool_name"):
        logger.info(
            f"[_extract_json_block] 第一个JSON无tool_name，从末尾提取成功: "
            f"tool_name={data.get('tool_name')}"
        )
        return data
    return None


def _extract_json_block(content: str) -> Optional[Dict[str, Any]]:
    json_str = _extract_json_string(content)
    if not json_str:
        return None

    data = _try_parse_with_strategies(json_str, STRATEGIES)

    if (not data or not data.get("tool_name")) and content.count('{') > 1:
        data = _try_extract_last_tool_call(content)

    if data:
        return data

    try:
        fields = ["tool_name", "tool_params", "content", "thought", "reasoning"]
        result = _extract_fields_from_json_str(json_str, fields)
        if result.get("tool_name"):
            if "tool_params" not in result:
                result["tool_params"] = {}
            logger.info(
                f"[_extract_json_block] Fallback成功提取: tool_name={result.get('tool_name')}, "
                f"tool_params_keys={list(result.get('tool_params', {}).keys())}"
            )
            return result
    except Exception as e:
        logger.error(f"[_extract_json_block] Fallback提取失败: {e}")

    return None


def _try_parse_non_standard_json(input_str: str) -> Optional[Dict]:
    if not isinstance(input_str, str):
        return None

    try:
        return json.loads(input_str)
    except json.JSONDecodeError:
        pass

    try:
        result = re.sub(r"'([^'\\]*(\\.[^'\\]*)*)'", r'"\1"', input_str)
        return json.loads(result)
    except json.JSONDecodeError:
        pass

    try:
        result = re.sub(r',(\s*})', r'\1', input_str)
        result = re.sub(r"'([^'\\]*(\\.[^'\\]*)*)'", r'"\1"', result)
        return json.loads(result)
    except json.JSONDecodeError:
        pass

    try:
        lines = input_str.split('\n')
        cleaned_lines = []
        for line in lines:
            in_string = False
            comment_pos = -1
            for i, ch in enumerate(line):
                if ch == '"' and (i == 0 or line[i-1] != '\\'):
                    in_string = not in_string
                elif ch == '/' and i + 1 < len(line) and line[i+1] == '/' and not in_string:
                    comment_pos = i
                    break
            if comment_pos != -1:
                cleaned_lines.append(line[:comment_pos])
            else:
                cleaned_lines.append(line)
        cleaned = '\n'.join(cleaned_lines)
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    try:
        stack = []
        in_string = False
        escape = False
        for ch in input_str:
            if escape:
                escape = False
                continue
            if ch == '\\':
                escape = True
                continue
            if ch == '"' and not in_string:
                in_string = True
                continue
            if ch == '"' and in_string:
                in_string = False
                continue
            if not in_string:
                if ch in '{[(':
                    stack.append(ch)
                elif ch in '}])':
                    if not stack:
                        return None
                    opener = stack.pop()
                    if (ch == '}' and opener != '{') or \
                       (ch == ']' and opener != '[') or \
                       (ch == ')' and opener != '('):
                        return None
        if stack:
            return None
    except:
        pass

    return None
