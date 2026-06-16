# -*- coding: utf-8 -*-
"""
task_incident_check — 中断/暂停检查并生成SSE事件

从 chat_stream/incident_handler.py 移入
统一: 小健 - 2026-05-31
"""

import asyncio
from typing import Optional, Callable, AsyncGenerator

from app.utils.logger import logger
from app.services.agent.steps import MetaStep
from app.services.task.task_registry import check_cancelled, check_paused, check_was_paused, set_was_paused, get_pause_event



async def task_interrupt_check(
    task_id: str,
    next_step: Optional[Callable[[], int]] = None
) -> tuple:
    """检查任务是否被中断,如果是则返回中断消息"""
    if await check_cancelled(task_id):
        step_value = next_step() if next_step else None
        meta_step = MetaStep(step=step_value, type="interrupted", message='任务已被中断')
        from app.utils.sse_formatter import format_agent_sse
        return True, format_agent_sse(meta_step.to_dict())
    return False, ""


async def task_pause_check(
    task_id: str,
    next_step: Optional[Callable[[], int]] = None
) -> AsyncGenerator[str, None]:
    """检查任务是否被暂停,如果是则发送paused事件并等待恢复 — 流式开始前调用"""
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
            meta_step = MetaStep(step=step_value, type="paused", message='任务已暂停')
            from app.utils.sse_formatter import format_agent_sse
            yield format_agent_sse(meta_step.to_dict())

        await pause_event.wait()

        if await check_cancelled(task_id):
            return

        await set_was_paused(task_id, False)
        step_value = next_step() if next_step else None
        meta_step = MetaStep(step=step_value, type="resumed", message='任务已恢复')
        from app.utils.sse_formatter import format_agent_sse
        yield format_agent_sse(meta_step.to_dict())


async def task_pause_check_and_yield(
    task_id: str,
    next_step: Optional[Callable[[], int]] = None
) -> AsyncGenerator[str, None]:
    """流式循环内暂停检查 — 每次迭代调用,非阻塞检查暂停状态"""
    if await check_cancelled(task_id):
        return

    pause_event = await get_pause_event(task_id)
    if pause_event is None:
        return

    is_paused = await check_paused(task_id)
    if not is_paused:
        return

    if not await check_was_paused(task_id):
        await set_was_paused(task_id, True)
        step_value = next_step() if next_step else None
        meta_step = MetaStep(step=step_value, type="paused", message='任务已暂停')
        from app.utils.sse_formatter import format_agent_sse
        yield format_agent_sse(meta_step.to_dict())

    try:
        await asyncio.wait_for(pause_event.wait(), timeout=300)
    except asyncio.TimeoutError:
        logger.warning(f"[task_pause_check_and_yield] 任务{task_id}暂停超时(300s),自动恢复")
        await set_was_paused(task_id, False)
        return

    if await check_cancelled(task_id):
        return

    await set_was_paused(task_id, False)
    step_value = next_step() if next_step else None
    meta_step = MetaStep(step=step_value, type="resumed", message='任务已恢复')
    from app.utils.sse_formatter import format_agent_sse
    yield format_agent_sse(meta_step.to_dict())
