# -*- coding: utf-8 -*-
"""
XML工具调用适配器

某些模型（如LongCat）返回XML格式工具调用而不是标准OpenAI tool_calls。
此模块提供XML→JSON转换能力。

从 llm_core.py 拆分出来，遵循SRP原则。
Author: 小沈 - 2026-05-27
"""

import json
import re
from typing import Optional


def convert_xml_tool_call_to_json(content: str) -> Optional[str]:
    """
    通用XML工具调用转JSON

    格式: <XXX_tool_call>TOOL_NAME\\n<XXX_arg_key>k</XXX_arg_key>\\n<XXX_arg_value>v</XXX_arg_value>\\n</XXX_tool_call>

    Returns:
        转换后的JSON字符串，如果无匹配返回None
    """
    if not content or '<' not in content or '_tool_call>' not in content:
        return None

    m = re.search(r'<(\w+)_tool_call>\s*(\w+)', content)
    if not m:
        return None

    prefix = m.group(1)
    tool_name = m.group(2)

    arg_keys = re.findall(rf'<{prefix}_arg_key>([^<]+)</{prefix}_arg_key>', content)
    arg_values = re.findall(rf'<{prefix}_arg_value>([^<]*)</{prefix}_arg_value>', content)

    if not arg_keys:
        return None

    tool_params = {}
    for i, key in enumerate(arg_keys):
        val = arg_values[i] if i < len(arg_values) else ''
        tool_params[key.strip()] = val.strip()

    result = json.dumps({
        "tool_name": tool_name,
        "tool_params": tool_params
    }, ensure_ascii=False)

    return result


def is_xml_tool_call(content: str) -> bool:
    """
    判断内容是否包含XML工具调用

    Args:
        content: 待检测内容

    Returns:
        True如果包含XML工具调用标签
    """
    return bool(content and '<' in content and '>' in content and '_tool_call>' in content)


__all__ = ["convert_xml_tool_call_to_json", "is_xml_tool_call"]
