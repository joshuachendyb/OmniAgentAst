# -*- coding: utf-8 -*-
"""
chat_router — API层入口

小健 - 2026-06-07 清理:删除step_react_loop和route(死代码)

Author: 小沈 - 2026-03-26
"""

from app.api.v1.chat.models import ChatMessage, ChatRequest
from app.api.v1.chat.detect_intent import detect_intent
from app.api.v1.chat.init_route_context import init_route_context
from app.api.v1.chat.step_start import step_start
from app.api.v1.chat.chat_stream_v2 import chat_stream_v2
from app.api.v1.chat.confirm_operation import confirm_operation
from app.api.v1.chat.validate_chat_config import validate_chat_config
from app.api.v1.chat.chat_router import router, task_router

__all__ = [
    "ChatMessage", "ChatRequest",
    "detect_intent", "init_route_context",
    "step_start",
    "chat_stream_v2",
    "confirm_operation", "validate_chat_config",
    "router", "task_router",
]
