# -*- coding: utf-8 -*-
"""
chat_stream_v2 — API层入口

task操作只在本层处理：register → interrupt检查 → pause检查 → stream → cancel检查 → cleanup

统一: 小健 - 2026-05-31
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
from app.utils.time_utils import create_step_counter


async def chat_stream_v2(request: ChatRequest):
    """API层入口 — task操作只在本层"""
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
    intent_type, source, confidence, candidates = await detect_intent(user_input)
    logger.debug(f"[chat_stream_v2] 意图检测: {intent_type} (source={source}, confidence={confidence})")
    ai_service = AIServiceFactory.get_service()
    provider = ai_service.provider
    model = ai_service.model
    session_id = request.session_id or str(uuid.uuid4())

    async def generate():
        from app.services.task.task_registry import register_task
        from app.services.task.task_incident_check import task_interrupt_check, task_pause_check
        from app.services.task.task_cancel_check import task_cancel_check_and_yield
        from app.services.task.task_cleanup import task_cleanup
        from app.services.react_sse_wrapper.run_sse_stream import run_sse_stream
        from app.services.react_sse_wrapper.save_step_to_db import save_step_to_db

        task_id, ai_service_ref = init_route_context(provider, model, ai_service, session_id)
        next_step = create_step_counter()
        execution_steps = []
        llm_call_count = 0
        agent_llm_holder = {"n": 0}
        current_content = ""

        try:
            # register
            await register_task(task_id, ai_service_ref)

            # interrupt检查
            is_interrupted, interrupt_msg = await task_interrupt_check(task_id)
            if is_interrupted:
                yield interrupt_msg
                await save_step_to_db(interrupt_msg, session_id, execution_steps, current_content or "")
                await task_cleanup(task_id, agent_llm_holder, llm_call_count)
                return

            # pause检查
            async for pause_event in task_pause_check(task_id):
                yield pause_event
                await save_step_to_db(pause_event, session_id, execution_steps, current_content or "")

            # start步骤
            async for event in step_start(ai_service_ref, task_id, next_step, user_input, execution_steps, session_id):
                yield event

            # 运行SSE流
            last_message = request.messages[-1].content if request.messages else ""
            async for sse_chunk in run_sse_stream(
                intent_type=intent_type, llm_client=ai_service_ref, task_id=task_id,
                ai_service=ai_service_ref, candidates=candidates, last_message=last_message,
                next_step=next_step,
                session_id=session_id, current_execution_steps=execution_steps,
                current_content=current_content, agent_llm_holder=agent_llm_holder,
            ):
                # cancel检查
                cancelled_sse = await task_cancel_check_and_yield(
                    task_id, next_step, session_id, execution_steps, current_content
                )
                if cancelled_sse:
                    yield cancelled_sse
                    break
                yield sse_chunk

        except Exception as e:
            logger.error(f"[chat_stream_v2] Error: {e}", exc_info=True)
            yield create_error_response(
                error_type="router_error",
                error_message=f"路由异常: {str(e)}"
            )
        finally:
            await task_cleanup(task_id, agent_llm_holder, llm_call_count)

    return StreamingResponse(generate(), media_type="text/event-stream")
