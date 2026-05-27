# -*- coding: utf-8 -*-
"""
LLM服务包

提供LLM调用的核心能力和模型适配器。
从 llm_core.py 拆分出来，遵循SRP原则。

包结构：
- model_adapters/: 模型特定兼容
  - xml_adapter: XML工具调用转JSON
  - reasoning: reasoning_content处理

注意：BaseAIService/ChatResponse/StreamChunk仍在llm_core.py中，
通过 app.services.llm_core 或 app.services 导入。
"""

from app.services.llm.model_adapters import (
    convert_xml_tool_call_to_json,
    is_xml_tool_call,
    fix_thinking_messages,
    extract_reasoning_from_chunk,
    extract_reasoning_from_message,
)

__all__ = [
    "convert_xml_tool_call_to_json",
    "is_xml_tool_call",
    "fix_thinking_messages",
    "extract_reasoning_from_chunk",
    "extract_reasoning_from_message",
]
