# -*- coding: utf-8 -*-
"""
task_incident_check — 中断/暂停检查并生成SSE事件

从 chat_stream/incident_handler.py 移入
统一: 小健 - 2026-05-31
"""

from typing import Optional, Callable, AsyncGenerator


from app.chat_stream import format_agent_sse
from app.services.agent.steps import IncidentStep
from app.services.task.task_registry import check_cancelled, check_paused, check_was_paused, set_was_paused, get_pause_event



async def task_interrupt_check(
    task_id: str,
    next_step: Optional[Callable[[], int]] = None
) -> tuple:
    """检查任务是否被中断,如果是则返回中断消息"""
    if await check_cancelled(task_id):
        step_value = next_step() if next_step else None
        incident_step = IncidentStep(
            step=step_value,
            incident_value='interrupted',
            message='任务已被中断'
        )
        return True, format_agent_sse(incident_step.to_dict())
    return False, ""


async def task_pause_check(
    task_id: str,
    next_step: Optional[Callable[[], int]] = None
) -> AsyncGenerator[str, None]:
    """检查任务是否被暂停,如果是则发送paused事件并等待恢复"""
    if await check_cancelled(task_id):
        return

    pause_event = await get_pause_event(task_id)
    if pause_event is None:
        return

    is_paused = await check_paused(task_id)
    if is_paused:
        if not await check_was_paused(task_id):
            await set_was_paused(task_id, True)
            step_value = next_step() if next_step else None
            incident_step = IncidentStep(
                step=step_value,
                incident_value='paused',
                message='任务已暂停'
            )
            yield format_agent_sse(incident_step.to_dict())

        await pause_event.wait()

        if await check_cancelled(task_id):
            return

        await set_was_paused(task_id, False)
        step_value = next_step() if next_step else None
        incident_step = IncidentStep(
            step=step_value,
            incident_value='resumed',
            message='任务已恢复'
        )
        yield format_agent_sse(incident_step.to_dict())
