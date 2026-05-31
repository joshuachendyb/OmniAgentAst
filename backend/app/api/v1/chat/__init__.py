# -*- coding: utf-8 -*-
"""
chat_router — 从 chat_router.py 拆出的职责

- models: Pydantic模型
- route_with_fallback: 意图路由
- detect_intent: 意图检测
- init_route_context: 初始化上下文
- step_start: start步骤
- step_react_loop: ReAct循环
- route: 主路由
- chat_stream_v2: FastAPI路由
- cancel/pause/resume_stream_task: 任务控制
- confirm_operation: 用户确认
- validate_chat_config: 配置验证
"""

from app.api.v1.chat.models import ChatMessage, ChatRequest
from app.api.v1.chat.route_with_fallback import route_with_fallback
from app.api.v1.chat.detect_intent import detect_intent
from app.api.v1.chat.init_route_context import init_route_context
from app.api.v1.chat.step_start import step_start
from app.api.v1.chat.step_react_loop import step_react_loop
from app.api.v1.chat.route import route
from app.api.v1.chat.chat_stream_v2 import chat_stream_v2
from app.api.v1.chat.cancel_stream_task import cancel_stream_task
from app.api.v1.chat.pause_stream_task import pause_stream_task
from app.api.v1.chat.resume_stream_task import resume_stream_task
from app.api.v1.chat.confirm_operation import confirm_operation
from app.api.v1.chat.validate_chat_config import validate_chat_config
from app.api.v1.chat.chat_router import router, task_router
from app.services.intents.crss_scorer import detect_intent_v2

__all__ = [
    "ChatMessage", "ChatRequest",
    "route_with_fallback", "detect_intent", "init_route_context",
    "step_start", "step_react_loop", "route",
    "chat_stream_v2",
    "cancel_stream_task", "pause_stream_task", "resume_stream_task",
    "confirm_operation", "validate_chat_config",
    "router", "task_router",
    "detect_intent_v2",
]
