# -*- coding: utf-8 -*-
"""
LLM服务包

提供LLM调用的核心能力和模型适配器。
从 llm_core.py 拆分出来,遵循SRP原则。

包结构:
- base_service.py: BaseAIService (原 llm_core/llm_core.py, 2026-06-17 合入)
- core.py: 数据类(ChatResponse、StreamChunk)+ 异常解析
- client_sdk.py: LLM客户端SDK
- xml_adapter.py: XML工具调用转JSON
- reasoning.py: reasoning_content处理

小沈 2026-06-17 llm_core目录合并入llm,消除冗余分层
小欧 2026-08-14 llm 独立为 app 顶层能力层目录(services/llm→app/llm), 包内 import 路径同步
"""

from app.llm.base_service import BaseAIService

from app.llm.xml_adapter import (
    convert_xml_tool_call_to_json,
    is_xml_tool_call,
)
from app.llm.reasoning import (
    fix_thinking_messages,
    extract_reasoning_from_chunk,
    extract_reasoning_from_message,
)

from app.llm.core import (
    ChatResponse,
    StreamChunk,
    _resolve_exception,
)

from app.llm.core import (
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
