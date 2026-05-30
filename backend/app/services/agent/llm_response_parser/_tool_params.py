# -*- coding: utf-8 -*-
"""
工具参数处理模块（第2层 - 依赖 _utils）
"""

import re
import json
from typing import Dict, Any, Optional

from app.utils.logger import logger
from ._utils import _extract_json_with_balanced_braces, _extract_string_value


# 【24.1.4 组件2/3 常量】已迁移到 constants.py — 北京老陈 2026-05-30
from app.constants import TOOL_NAME_FALLBACK_KEYS, TOOL_PARAMS_FALLBACK_KEYS


# 【24.1.4 组件1】统一 action 结果构建(消除 2 个 return dict 的 6 字段重复)
def _build_action_result(type_: str, tool_name: str, tool_params: Dict[str, Any],
                          thought: str, error: Optional[str] = None) -> Dict[str, Any]:
    return {
        "type": type_,
        "thought": thought,
        "content": thought,
        "reasoning": thought,
        "tool_name": tool_name,
        "tool_params": tool_params,
        "response": None,
        "error": error,
    }


# 【24.1.4 组件2】从 tool_params 兜底提取工具名(消除 M1a 3 个连续 if)
def _fallback_tool_name(tool_params: Dict[str, Any], current: str) -> str:
    if current:
        return current
    for key in TOOL_NAME_FALLBACK_KEYS:
        if key in tool_params:
            return tool_params.pop(key)
    return ""


# 【24.1.4 组件3】统一参数名映射(消除 M1b 3 个连续 if)
def _normalize_tool_params(tool_params: Dict[str, Any]) -> Dict[str, Any]:
    if "tool_params" in tool_params:
        return tool_params
    for key in TOOL_PARAMS_FALLBACK_KEYS:
        if key in tool_params:
            tool_params["tool_params"] = tool_params.pop(key)
            break
    return tool_params


def _normalize_tool_params_content(tool_params: Dict) -> Dict:
    if not isinstance(tool_params, dict):
        return tool_params

    normalized = dict(tool_params)

    for field_name in ("content", "result"):
        if field_name in normalized:
            field_value = normalized[field_name]

            if isinstance(field_value, bool):
                normalized[field_name] = str(field_value)
            elif isinstance(field_value, (int, float)):
                normalized[field_name] = str(field_value)
            elif isinstance(field_value, (list, dict)):
                normalized[field_name] = json.dumps(field_value, ensure_ascii=False)

    return normalized


def _filter_tool_params(tool_params: Dict) -> Dict:
    if not tool_params or not isinstance(tool_params, dict):
        return {}

    NON_PARAM_FIELDS = {
        "reasoning", "thought", "type", "tool_name",
        "action", "action_input", "extra_field", "metadata", "context",
    }

    param_name_pattern = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')

    CAMEL_TO_SNAKE = {
        "filePath": "file_path",
        "filePath2": "file_path",
        "dirPath": "dir_path",
        "dirPath2": "dir_path",
        "sourcePath": "source_path",
        "sourcePath2": "source_path",
        "destinationPath": "destination_path",
        "destinationPath2": "destination_path",
        "filePattern": "file_pattern",
        "filePattern2": "file_pattern",
        "offset2": "offset",
        "limit2": "limit",
        "Content": "content",
        "FilePath": "file_path",
        "DirPath": "dir_path",
        "SourcePath": "source_path",
        "DestinationPath": "destination_path",
        "FilePattern": "file_pattern",
    }

    filtered = {}
    for k, v in tool_params.items():
        if k not in NON_PARAM_FIELDS:
            if param_name_pattern.match(k):
                normalized_k = CAMEL_TO_SNAKE.get(k, k)
                if normalized_k not in filtered:
                    filtered[normalized_k] = v
                else:
                    filtered[k] = v

    return filtered


def _process_tool_params(tool_params, tool_name=None, raw_output=None):
    if not isinstance(tool_params, dict):
        return tool_params

    tool_params = _normalize_tool_params_content(tool_params)
    tool_params = _filter_tool_params(tool_params)

    return tool_params


def _extract_tool_params_from_thought(thought: str, tool_name: str = None) -> Dict[str, Any]:
    if not thought:
        return {}

    json_text, _ = _extract_json_with_balanced_braces(thought)

    if json_text:
        try:
            parsed = json.loads(json_text)
            if "tool_params" in parsed:
                return parsed["tool_params"]
            if "params" in parsed:
                return parsed["params"]
            if "tool_name" not in parsed:
                return parsed
        except json.JSONDecodeError:
            try:
                json_text_escaped = json_text.replace('\r\n', ' ').replace('\n', ' ').replace('\r', ' ')
                parsed = json.loads(json_text_escaped)
                if "tool_params" in parsed:
                    return parsed["tool_params"]
                if "params" in parsed:
                    return parsed["params"]
                if "tool_name" not in parsed:
                    return parsed
            except:
                pass

    return {}


def _extract_tool_params_from_text(content: str, tool_start_pos: int) -> Optional[Dict[str, Any]]:
    search_text = content[tool_start_pos:]

    tp_pattern = r'"tool_params"\s*:\s*\{'
    tp_match = re.search(tp_pattern, search_text)

    if not tp_match:
        return None

    json_start = tp_match.start()
    json_text, _ = _extract_json_with_balanced_braces(search_text[json_start:])

    if not json_text:
        return None

    try:
        parsed = json.loads(json_text)
        if "tool_params" in parsed:
            return parsed["tool_params"]
        elif isinstance(parsed, dict):
            return {k: v for k, v in parsed.items() if k not in ["reasoning", "thought", "type", "tool_name", "action", "action_input", "extra_field", "metadata", "context"]}
    except:
        pass

    try:
        inner_start = json_text.find('{', json_text.find('tool_params'))
        if inner_start != -1:
            inner_json, _ = _extract_json_with_balanced_braces(json_text[inner_start:])
            if inner_json:
                return json.loads(inner_json)
    except:
        pass

    params = _extract_params_by_regex(search_text)
    if params:
        return params

    return None


def _extract_content_value_from_json_str(json_str: str) -> Optional[str]:
    content_start = json_str.find('"content"')
    if content_start == -1:
        return None

    tool_params_pos = json_str.find('"tool_params"')
    if tool_params_pos != -1 and content_start > tool_params_pos:
        return None

    return _extract_string_value(json_str, "content")


def _extract_params_by_regex_from_json_str(json_str: str) -> Optional[Dict[str, Any]]:
    params = {}

    tp_start = json_str.find('"tool_params"')
    if tp_start == -1:
        return None

    brace_start = json_str.find('{', tp_start)
    if brace_start == -1:
        return None

    tp_json, _ = _extract_json_with_balanced_braces(json_str[brace_start:])
    if not tp_json:
        return None

    try:
        return json.loads(tp_json)
    except:
        pass

    file_path_match = re.search(r'"file_path"\s*:\s*"([^"]+)"', tp_json)
    if file_path_match:
        params["file_path"] = file_path_match.group(1)

    content_val = _extract_string_value(tp_json, "content")
    if content_val is not None:
        params["content"] = content_val

    result_val = _extract_string_value(tp_json, "result")
    if result_val is not None:
        params["result"] = result_val

    other_params = ["dir_path", "source_path", "destination_path", "file_pattern", "pattern", "offset", "limit", "encoding"]
    for p in other_params:
        pattern = rf'"{p}"\s*:\s*"([^"]+)"'
        match = re.search(pattern, tp_json)
        if match:
            params[p] = match.group(1)

    return params if params else None


def _extract_params_by_regex(text: str) -> Optional[Dict[str, Any]]:
    params = {}

    file_path_patterns = [
        r'"file_path"\s*:\s*"([^"]+)"',
        r'"filepath"\s*:\s*"([^"]+)"',
    ]
    for pattern in file_path_patterns:
        match = re.search(pattern, text)
        if match:
            params["file_path"] = match.group(1)
            break

    if "file_path" not in params:
        path_patterns = [
            r'["\']?([A-Za-z]:\\[^"\'\s,}]+)["\']?',
            r'"path"\s*:\s*"([^"]+)"',
        ]
        for pattern in path_patterns:
            match = re.search(pattern, text)
            if match:
                params["file_path"] = match.group(1)
                break

    content_val = _extract_string_value(text, "content")
    if content_val is not None:
        params["content"] = content_val

    return params if params else None
