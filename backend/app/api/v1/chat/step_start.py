# -*- coding: utf-8 -*-
"""
step_start — 从 chat_router.py 拷出

拷贝来源: chat_router.py 第255-265行
"""

from typing import List, Dict, Any

from app.chat_stream.start_step import send_start_step
from app.chat_stream.sse_formatter import format_agent_sse
from app.chat_stream.error_handler import create_error_response


async def step_start(ai_service, task_id, next_step, user_input, execution_steps, session_id):
    """拷贝自 chat_router.py 第255-265行"""
    try:
        start_step = await send_start_step(
            ai_service=ai_service, task_id=task_id, next_step=next_step,
            user_message=user_input, security_check_result={},
            current_execution_steps=execution_steps, session_id=session_id,
        )
        yield format_agent_sse(start_step)
    except Exception as e:
        yield create_error_response(error_type="start_failed", error_message=f"start步骤失败: {e}")
