# -*- coding: utf-8 -*-
"""
chat_stream_v2 — API层入口

小健 - 2026-06-07 清理:删除save_step_to_db调用,改用统一save_execution_steps_to_db
task操作只在本层处理:register → interrupt检查 → pause检查 → stream → cancel检查 → cleanup

统一: 小健 - 2026-05-31
"""

import uuid
from fastapi.responses import StreamingResponse, PlainTextResponse

from app.services import get_service
from app.utils.logger import logger
from app.chat_stream import create_error_response, save_execution_steps_to_db
from app.api.v1.chat.models import ChatRequest
from app.api.v1.chat.detect_intent import detect_intent
from app.api.v1.chat.step_start import step_start
from app.utils.time_utils import create_step_counter
from app.services.task.task_registry import register_task
from app.services.task.task_incident_check import task_interrupt_check, task_pause_check
from app.services.task.task_cancel_check import task_cancel_check_and_yield
from app.services.task.task_cleanup import task_cleanup
from app.services.react_sse_wrapper.run_sse_stream import run_sse_stream


async def chat_stream_v2(request: ChatRequest):
    if not request.messages:
        return PlainTextResponse(
            content=create_error_response(error_type="invalid_request", error_message="消息列表不能为空"),
            media_type="text/event-stream"
        )

    user_input = request.messages[-1].content
    intent_type, source, confidence, candidates = await detect_intent(user_input)
    logger.debug(f"[chat_stream_v2] 意图检测: {intent_type} (source={source}, confidence={confidence})")
    ai_service = get_service()
    session_id = request.session_id or str(uuid.uuid4())

    async def generate():
        task_id = str(uuid.uuid4())
        next_step = create_step_counter()
        execution_steps = []
        agent_llm_holder = {"n": 0}
        current_content = ""

        try:
            await register_task(task_id, ai_service)

            is_interrupted, interrupt_msg = await task_interrupt_check(task_id)
            if is_interrupted:
                yield interrupt_msg
                await save_execution_steps_to_db(session_id, execution_steps, current_content or "")
                await task_cleanup(task_id, agent_llm_holder, 0)
                return

            async for pause_event in task_pause_check(task_id):
                yield pause_event
                await save_execution_steps_to_db(session_id, execution_steps, current_content or "")

            async for event in step_start(ai_service, task_id, next_step, user_input, execution_steps, session_id):
                yield event

            async for sse_chunk in run_sse_stream(
                intent_type=intent_type, llm_client=ai_service, task_id=task_id,
                ai_service=ai_service, candidates=candidates, last_message=user_input,
                next_step=next_step,
                session_id=session_id, current_execution_steps=execution_steps,
                current_content=current_content, agent_llm_holder=agent_llm_holder,
            ):
                cancelled_sse = await task_cancel_check_and_yield(
                    task_id, next_step, session_id, execution_steps, current_content
                )
                if cancelled_sse:
                    yield cancelled_sse
                    break
                yield sse_chunk

        except Exception as e:
            logger.error(f"[chat_stream_v2] Error: {e}", exc_info=True)
            yield create_error_response(error_type="router_error", error_message=f"路由异常: {str(e)}")
        finally:
            await task_cleanup(task_id, agent_llm_holder, 0)

    return StreamingResponse(generate(), media_type="text/event-stream")
