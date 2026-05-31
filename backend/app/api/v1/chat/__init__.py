# -*- coding: utf-8 -*-
"""
chat_router — 从 chat_router.py 拆出的职责

task操作统一在 services/task/ 层

Author: 小沈 - 2026-03-26
统一: 小健 - 2026-05-31 — 删除task wrapper导入
"""

from app.api.v1.chat.models import ChatMessage, ChatRequest
from app.api.v1.chat.route_with_fallback import route_with_fallback
from app.api.v1.chat.detect_intent import detect_intent
from app.api.v1.chat.init_route_context import init_route_context
from app.api.v1.chat.step_start import step_start
from app.api.v1.chat.step_react_loop import step_react_loop
from app.api.v1.chat.route import route
from app.api.v1.chat.chat_stream_v2 import chat_stream_v2
from app.api.v1.chat.confirm_operation import confirm_operation
from app.api.v1.chat.validate_chat_config import validate_chat_config
from app.api.v1.chat.chat_router import router, task_router
from app.services.intents.crss_scorer import detect_intent_v2

__all__ = [
    "ChatMessage", "ChatRequest",
    "route_with_fallback", "detect_intent", "init_route_context",
    "step_start", "step_react_loop", "route",
    "chat_stream_v2",
    "confirm_operation", "validate_chat_config",
    "router", "task_router",
    "detect_intent_v2",
]
