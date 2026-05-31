# -*- coding: utf-8 -*-
"""
_is_cancelled_and_yield — 从 react_sse_wrapper.py 拆出

复制来源: react_sse_wrapper.py 第36-56行
Author: 小沈 - 2026-05-31
"""

import asyncio
from typing import Optional, Callable

from app.services.agent.steps import IncidentStep
from app.utils.logger import logger
from app.chat_stream.message_saver import save_execution_steps_to_db
from app.chat_stream.sse_formatter import format_agent_sse


async def is_cancelled_and_yield(
    task_id: str, running_tasks: dict, running_tasks_lock: asyncio.Lock,
    next_step: Callable[[], int], session_id: str,
    current_execution_steps: list, current_content: str
) -> Optional[str]:
    """复制自 react_sse_wrapper.py 第36-56行"""
    async with running_tasks_lock:
        is_cancelled = running_tasks.get(task_id, {}).get("cancelled", False)
        if is_cancelled:
            logger.info(f"[InterruptCheck] 任务 {task_id} 取消状态: {is_cancelled}")
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
