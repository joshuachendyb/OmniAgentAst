# -*- coding: utf-8 -*-
"""
模型适配器包

提供XML兼容和reasoning处理等模型特定适配能力。
"""

from app.services.llm.model_adapters.xml_adapter import convert_xml_tool_call_to_json, is_xml_tool_call
from app.services.llm.model_adapters.reasoning import (
    detect_reasoning_support,
    fix_thinking_messages,
    extract_reasoning_from_chunk,
    extract_reasoning_from_message,
)

__all__ = [
    "convert_xml_tool_call_to_json",
    "is_xml_tool_call",
    "detect_reasoning_support",
    "fix_thinking_messages",
    "extract_reasoning_from_chunk",
    "extract_reasoning_from_message",
]
