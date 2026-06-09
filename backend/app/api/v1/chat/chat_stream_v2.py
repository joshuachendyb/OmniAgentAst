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
from app.chat_stream import create_error_response
from app.api.v1.chat.models import ChatRequest
from app.api.v1.chat.detect_intent import detect_intent
from app.api.v1.chat.step_start import step_start
from app.utils.counter_utils import create_step_counter
from app.services.task.task_registry import register_task
from app.services.task.task_interrupt_check import task_interrupt_check, task_pause_check_and_yield
from app.services.task.task_cancel_check import task_cancel_check_and_yield
from app.services.task.task_cleanup import task_cleanup
from app.services.react_sse_wrapper.run_sse_stream import run_sse_stream


# 无包装函数: 直接调 task_interrupt_check / task_pause_check / step_start / run_sse_stream


async def chat_stream_v2(request: ChatRequest):
    """API层入口 — 小沈 2026-06-08 重构"""
    if not request.messages:
        return PlainTextResponse(
            content=create_error_response(error_type="invalid_request", error_message="消息列表不能为空"),
            media_type="text/event-stream"
        )

    user_input = request.messages[-1].content
    intent_type, confidence, candidates = detect_intent(user_input)
    logger.debug(f"[chat_stream_v2] 意图检测: {intent_type} (confidence={confidence})")
    ai_service = get_service()
    session_id = request.session_id or str(uuid.uuid4())

    async def generate():
        """生成器 — 小沈 2026-06-08 重构"""
        task_id = str(uuid.uuid4())
        next_step = create_step_counter()
        execution_steps = []
        llm_call_count_holder = [0]
        current_content_holder = [""]  # P1-02修复: list holder,run_sse_stream内部可修改

        try:
            await register_task(task_id, ai_service)

            is_interrupted, interrupt_msg = await task_interrupt_check(task_id)
            if is_interrupted:
                yield interrupt_msg
                await task_cleanup(task_id, 0)
                return

            async for event in step_start(ai_service, task_id, next_step, user_input, execution_steps, session_id):
                yield event

            async for sse_chunk in run_sse_stream(
                intent_type=intent_type, llm_client=ai_service, task_id=task_id,
                candidates=candidates, last_message=user_input,
                next_step=next_step,
                session_id=session_id, current_execution_steps=execution_steps,
                current_content_holder=current_content_holder, llm_call_count_holder=llm_call_count_holder,
            ):
                # R1-1修复: 每次迭代检查暂停状态 — 小沈 2026-06-09
                async for pause_event in task_pause_check_and_yield(task_id, next_step):
                    yield pause_event

                cancelled_sse = await task_cancel_check_and_yield(
                    task_id, next_step, session_id, execution_steps, current_content_holder[0]
                )
                if cancelled_sse:
                    yield cancelled_sse
                    break
                yield sse_chunk

        except Exception as e:
            logger.error(f"[chat_stream_v2] Error: {e}", exc_info=True)
            yield create_error_response(error_type="router_error", error_message=f"路由异常: {str(e)}")
        finally:
            await task_cleanup(task_id, llm_call_count_holder[0])

    return StreamingResponse(generate(), media_type="text/event-stream")
