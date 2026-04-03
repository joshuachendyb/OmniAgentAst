# -*- coding: utf-8 -*-
"""
chat_stream 模块

流式聊天相关辅助函数和处理模块
Author: 小沈 - 2026-03-22
"""

from app.chat_stream.chat_helpers import create_timestamp, get_provider_display_name, create_final_response
from app.chat_stream.error_handler import (
    create_error_response,
    get_user_friendly_error,
    ERROR_TYPE_MAP,
    classify_error,
)
from app.chat_stream.incident_handler import (
    create_incident_data,
    check_and_yield_if_interrupted,
    check_and_yield_if_paused,
)
from app.chat_stream.chat_stream_query import chat_stream_query
from app.chat_stream.sse_formatter import (
    format_sse_event,
    format_thought_sse,
    format_action_tool_sse,
    format_observation_sse,
)

__all__ = [
    # chat_helpers
    "create_timestamp",
    "get_provider_display_name",
    "create_final_response",
    # error_handler
    "create_error_response",
    "get_user_friendly_error",
    "ERROR_TYPE_MAP",
    "classify_error",
    # incident_handler
    "create_incident_data",
    "check_and_yield_if_interrupted",
    "check_and_yield_if_paused",
    # chat_stream_query
    "chat_stream_query",
    # sse_formatter
    "format_sse_event",
    "format_thought_sse",
    "format_action_tool_sse",
    "format_observation_sse",
]
