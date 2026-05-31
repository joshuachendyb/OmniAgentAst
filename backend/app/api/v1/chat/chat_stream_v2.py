# -*- coding: utf-8 -*-
"""
chat_stream_v2 — 从 chat_router.py 拷出

拷贝来源: chat_router.py 第169-225行
"""

import uuid
from fastapi.responses import StreamingResponse, PlainTextResponse

from app.services import AIServiceFactory
from app.utils.logger import logger
from app.chat_stream.error_handler import create_error_response
from app.api.v1.chat.models import ChatRequest
from app.api.v1.chat.detect_intent import detect_intent
from app.api.v1.chat.init_route_context import init_route_context
from app.api.v1.chat.step_start import step_start
from app.api.v1.chat.step_react_loop import step_react_loop
from app.utils.time_utils import create_step_counter


async def chat_stream_v2(request: ChatRequest):
    """拷贝自 chat_router.py 第169-225行"""
    from app.services.react_sse_wrapper import running_tasks, running_tasks_lock

    if not request.messages:
        error_response = create_error_response(
            error_type="invalid_request",
            error_message="消息列表不能为空"
        )
        return PlainTextResponse(
            content=error_response,
            media_type="text/event-stream"
        )

    user_input = request.messages[-1].content
    ai_service = AIServiceFactory.get_service()
    provider = ai_service.provider
    model = ai_service.model
    session_id = request.session_id or str(uuid.uuid4())

    async def generate():
        try:
            task_id, ai_service_ref, rt, rtl = init_route_context(provider, model, ai_service, session_id)
            next_step = create_step_counter()
            execution_steps = []

            async for event in step_start(ai_service_ref, task_id, next_step, user_input, execution_steps, session_id):
                yield event

            async for event in step_react_loop(
                request.messages, "generic", 0.0, [], provider, model,
                task_id, session_id, ai_service_ref, next_step, rt, rtl, execution_steps
            ):
                yield event
        except Exception as e:
            logger.error(f"[chat_stream_v2] Error: {e}", exc_info=True)
            yield create_error_response(
                error_type="router_error",
                error_message=f"路由异常: {str(e)}"
            )

    return StreamingResponse(generate(), media_type="text/event-stream")
