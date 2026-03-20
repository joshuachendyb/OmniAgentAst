# -*- coding: utf-8 -*-
"""
ReAct Agent Structured Outputs 实现 (Function Calling Schema Generator)

【重构说明】
本文件已迁移到 services/agent/types/react_schema.py
此处保留作为向后兼容层

Author: 小沈 - 2026-03-21
"""

from app.services.agent.types.react_schema import (
    get_tools_schema_for_function_calling,
    get_tool_schema,
    validate_tool_call,
    get_available_tools,
    get_finish_tool_schema,
    _process_description,
    _clean_properties,
    _extract_type,
    _generate_example_hints,
)

__all__ = [
    "get_tools_schema_for_function_calling",
    "get_tool_schema",
    "validate_tool_call",
    "get_available_tools",
    "get_finish_tool_schema",
    "_process_description",
    "_clean_properties",
    "_extract_type",
    "_generate_example_hints",
]
