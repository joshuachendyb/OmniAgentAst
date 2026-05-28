# -*- coding: utf-8 -*-
"""
共享工具函数模块（第1层 - 零依赖本包其他模块）
"""

import re
import json
from typing import Dict, Any, Optional, Tuple, List

from app.utils.logger import logger


# 【改进7 2026-05-01 小沈 小健】reasoning验证辅助函数
_REASONING_MIN_LENGTH = 10


def _add_reasoning_warning(result: Dict[str, Any]) -> Dict[str, Any]:
    if result.get("tool_name") and not result.get("parse_warning"):
        reasoning = result.get("reasoning", "")
        if not reasoning or len(reasoning.strip()) < _REASONING_MIN_LENGTH:
            result["parse_warning"] = (
                "⚠️ reasoning字段为空或过短(<10字符)。"
                "有效的reasoning应包含：为什么选择这个工具、参数如何确定。"
            )
    return result


def _normalize_result_to_str(raw_result) -> str:
    if isinstance(raw_result, bool):
        return str(raw_result)
    elif isinstance(raw_result, (int, float)):
        return str(raw_result)
    elif isinstance(raw_result, (list, dict)):
        return json.dumps(raw_result, ensure_ascii=False)
    elif isinstance(raw_result, str):
        return raw_result
    else:
        return ""


# 【基于14.0分析增强】中文关键词模式
REACT_KEYWORDS = {
    "thought": r"(?:Thought|思考|推理):\s*",
    "action": r"(?:Action|行动|工具调用|(?:调用|使用|执行)\s+|(?:工具|函数)\s*为):\s*",
    "action_input": r"(?:Action Input|工具参数|输入|参数):\s*",
    "answer": r"(?:Answer|回答|最终答案|结论):\s*",
}


def _get_all_tool_names():
    try:
        from app.services.tools.registry import tool_registry
        tools = tool_registry.list_tools(include_metadata=False)
        return [t["name"] if isinstance(t, dict) else t for t in tools]
    except Exception:
        return ["list_directory", "read_file", "write_file", "delete_file",
                "move_file", "search_files", "grep_file_content", "generate_report",
                "execute_command", "run_command", "get_current_time", "get_system_info",
                "finish", "finish_with_error"]


# 【24.4.4 组件1】统一 handler 结果构建(消除 4 个 8 字段 dict 重复)
def _build_handler_result(type_: str, thought: str = "", content: str = "",
                           reasoning: str = "", tool_name: Optional[str] = None,
                           tool_params: Optional[Dict] = None,
                           response: Any = None, error: Optional[str] = None) -> Dict[str, Any]:
    return {
        "type": type_, "thought": thought, "content": content or thought,
        "reasoning": reasoning, "tool_name": tool_name, "tool_params": tool_params or {},
        "response": response or thought, "error": error,
    }


# 【小沈重构 2026-05-25】25.3节：统一构造action结果dict，消除3处字段名重复
def _make_action_result_dict(
    result_type: str, thought: str, content: str, reasoning: str,
    tool_name: Optional[str], tool_params: Optional[Dict],
    response: Optional[str], error: Optional[str] = None,
    pending_calls: Optional[List] = None,
) -> Dict[str, Any]:
    result = {
        "type": result_type, "thought": thought,
        "content": content, "reasoning": reasoning,
        "tool_name": tool_name, "tool_params": tool_params,
        "response": response, "error": error,
    }
    if pending_calls:
        result["_pending_calls"] = pending_calls
    return _add_reasoning_warning(result)


def _extract_json_with_balanced_braces(text: str) -> Tuple[Optional[str], str]:
    start_idx = None
    for i, char in enumerate(text):
        if char in '{[':
            start_idx = i
            break

    if start_idx is None:
        return None, text.strip()

    content_before = text[:start_idx].strip()

    stack = []
    end_idx = None
    in_string = False
    escape_next = False

    for i in range(start_idx, len(text)):
        char = text[i]
        if escape_next:
            escape_next = False
            continue
        if char == '\\' and in_string:
            escape_next = True
            continue
        if char == '"' and not escape_next:
            in_string = not in_string
            continue
        if in_string:
            continue
        if char in '{[':
            stack.append(char)
        elif char == '}' and stack and stack[-1] == '{':
            stack.pop()
            if not stack:
                end_idx = i + 1
                break
        elif char == ']' and stack and stack[-1] == '[':
            stack.pop()
            if not stack:
                end_idx = i + 1
                break

    if end_idx:
        return text[start_idx:end_idx], content_before

    if stack:
        truncated = text[start_idx:]
        for _ in range(len(stack)):
            opener = stack.pop()
            closer = '}' if opener == '{' else ']'
            truncated += closer
        return truncated, content_before

    return None, content_before


def _extract_key_value_pairs(text: str) -> Dict[str, Any]:
    result = {}

    pattern = r'["\']?(\w+)["\']?\s*:\s*["\']?([^,\}\]\n]+)["\']?'
    matches = re.findall(pattern, text)

    for key, value in matches:
        value = value.strip()
        if value.lower() == 'true':
            result[key] = True
        elif value.lower() == 'false':
            result[key] = False
        elif value.isdigit():
            result[key] = int(value)
        elif re.match(r'^\d+\.\d+$', value):
            result[key] = float(value)
        else:
            result[key] = value

    return result
