# -*- coding: utf-8 -*-
"""
LLM服务包

提供LLM调用的核心能力和模型适配器。
从 llm_core.py 拆分出来，遵循SRP原则。

包结构：
- core.py: 数据类（ChatResponse、StreamChunk）+ 重试上下文
- stream_parser.py: SSE流解析 + HTTP错误处理
- request_builder.py: 请求体构建 + 消息构建
- model_adapters/: 模型特定兼容
  - xml_adapter: XML工具调用转JSON
  - reasoning: reasoning_content处理

注意：BaseAIService仍在llm_core.py中。
"""

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
    parse_sse_stream,
    handle_http_error_stream,
    create_cancelled_chunk,
    create_error_chunk,
)

from app.services.llm.request_builder import (
    build_request_body,
    build_messages,
)

__all__ = [
    "convert_xml_tool_call_to_json",
    "is_xml_tool_call",
    "fix_thinking_messages",
    "extract_reasoning_from_chunk",
    "extract_reasoning_from_message",
    "ChatResponse",
    "StreamChunk",
    "_resolve_exception",
    "parse_sse_stream",
    "handle_http_error_stream",
    "create_cancelled_chunk",
    "create_error_chunk",
    "build_request_body",
    "build_messages",
]
