# -*- coding: utf-8 -*-
"""
step_start — 从 chat_router.py 拷出

拷贝来源: chat_router.py 第255-265行
"""

from typing import List, Dict, Any

from app.services.react_sse_wrapper.chat_stream import send_start_step, create_error_response
from app.utils.sse_formatter import format_agent_sse


async def step_start(ai_service, task_id, next_step, user_input, execution_steps, session_id):
    """拷贝自 chat_router.py 第255-265行"""
    try:
        start_step = await send_start_step(
            ai_service=ai_service, task_id=task_id, next_step=next_step,
            user_message=user_input, security_check_result={},
        )
        # R5-1修复: start_step追加到execution_steps,确保保存到DB — 小沈 2026-06-09
        start_dict = start_step.to_dict()
        execution_steps.append(start_dict)
        yield format_agent_sse(start_dict)
    except Exception as e:
        yield create_error_response(error_type="start_failed", error_message=f"start步骤失败: {e}")
