# -*- coding: utf-8 -*-
"""
route — 从 chat_router.py 拷出

拷贝来源: chat_router.py 第279-313行
"""

from typing import Any, Dict, List, Optional, AsyncGenerator

from app.utils.logger import logger
from app.utils.time_utils import create_step_counter
from app.api.v1.chat.detect_intent import detect_intent
from app.api.v1.chat.init_route_context import init_route_context
from app.api.v1.chat.step_start import step_start
from app.api.v1.chat.step_react_loop import step_react_loop
from app.api.v1.chat.models import ChatRequest


async def route(
    self,
    user_input: str,
    provider: str,
    model: str,
    session_id: str,
    request: Optional[ChatRequest] = None,
    context: Optional[Dict[str, Any]] = None,
    system_prompt: Optional[str] = None,
    ai_service: Optional[Any] = None
) -> AsyncGenerator[str, None]:
    """拷贝自 chat_router.py 第279-313行"""
    intent_type, source, confidence, candidates = await detect_intent(user_input)
    logger.info(f"[ChatRouter] intent_type={intent_type}({source}), conf={confidence:.2f}")

    task_id, ai_service_ref, rt, rtl = init_route_context(provider, model, ai_service, session_id)
    next_step = create_step_counter()
    execution_steps: List[Dict] = []

    async for event in step_start(ai_service_ref, task_id, next_step, user_input, execution_steps, session_id):
        yield event

    async for event in step_react_loop(
        request.messages, intent_type, confidence, candidates, provider, model,
        task_id, session_id, ai_service_ref, next_step, rt, rtl, execution_steps
    ):
        yield event
