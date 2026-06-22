# -*- coding: utf-8 -*-
"""
LLM服务包

提供LLM调用的核心能力和模型适配器。
从 llm_core.py 拆分出来,遵循SRP原则。

包结构:
- base_service.py: BaseAIService (原 llm_core/llm_core.py, 2026-06-17 合入)
- core.py: 数据类(ChatResponse、StreamChunk)+ 异常解析
- stream_parser.py: StreamChunk工厂函数
- client_sdk.py: LLM客户端SDK
- model_adapters/: 模型特定兼容
  - xml_adapter: XML工具调用转JSON
  - reasoning: reasoning_content处理

小沈 2026-06-17 llm_core目录合并入llm,消除冗余分层
"""

from app.services.llm.base_service import BaseAIService

from app.services.llm.model_adapters import (
    convert_xml_tool_call_to_json,
    is_xml_tool_call,
    fix_thinking_messages,
    extract_reasoning_from_chunk,
    extract_reasoning_from_message,
)

from app.services.llm.core import (
    ChatResponse,
    StreamChunk,
    _resolve_exception,
)

from app.services.llm.stream_parser import (
    create_cancelled_chunk,
    create_error_chunk,
)

__all__ = [
    "BaseAIService",
    "convert_xml_tool_call_to_json",
    "is_xml_tool_call",
    "fix_thinking_messages",
    "extract_reasoning_from_chunk",
    "extract_reasoning_from_message",
    "ChatResponse",
    "StreamChunk",
    "_resolve_exception",
    "create_cancelled_chunk",
    "create_error_chunk",
]
