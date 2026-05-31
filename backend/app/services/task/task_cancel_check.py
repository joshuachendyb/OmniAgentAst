# -*- coding: utf-8 -*-
"""
task_cancel_check — 取消检查并生成SSE事件

从 react_sse_wrapper/is_cancelled_and_yield.py 移入
统一: 小健 - 2026-05-31
"""

from typing import Optional, Callable

from app.services.agent.steps import IncidentStep
from app.utils.logger import logger
from app.chat_stream.message_saver import save_execution_steps_to_db
from app.chat_stream.sse_formatter import format_agent_sse
from app.services.task.task_registry import check_cancelled


async def task_cancel_check_and_yield(
    task_id: str, next_step: Callable[[], int], session_id: str,
    current_execution_steps: list, current_content: str
) -> Optional[str]:
    """检查取消状态，如果是则生成interrupted SSE事件"""
    if await check_cancelled(task_id):
        logger.info(f"[InterruptCheck] 任务 {task_id} 取消状态: True")
        incident_step = IncidentStep(
            step=next_step(),
            incident_value='interrupted',
            message='任务已被中断'
        )
        logger.info(f"[Step incident] 发送incident步骤(interrupted)")
        current_execution_steps.append(incident_step.to_dict())
        await save_execution_steps_to_db(session_id, current_execution_steps, current_content or "")
        return format_agent_sse(incident_step)
    return None
