# -*- coding: utf-8 -*-
"""
task_interrupt_check — 中断/暂停检查并生成SSE事件

从 chat_stream/incident_handler.py 移入
统一: 小健 - 2026-05-31
小沈 2026-06-17 DRY: 合并task_pause_check/task_pause_check_and_yield, 提取_emit_step_sse
小健 2026-06-17 用简单dict替代MetaStep，消除task→agent循环依赖
"""

import asyncio
from typing import Optional, Callable, AsyncGenerator

from app.utils.logger import logger
from app.utils.sse_formatter import format_agent_sse
from app.services.task.task_state_queries import check_cancelled, check_paused, check_was_paused, get_pause_event
from app.services.task.task_registry import set_was_paused
from app.services.task.task_utils import build_step_dict


def _emit_step_sse(step: Optional[int], step_type: str, message: str) -> str:
    """step→SSE字符串 — 小沈 2026-06-17 DRY"""
    return format_agent_sse(build_step_dict(step, step_type, message))


async def task_interrupt_check(
    task_id: str,
    next_step: Optional[Callable[[], int]] = None
) -> tuple:
    """检查任务是否被中断,如果是则返回中断消息"""
    if await check_cancelled(task_id):
        step_value = next_step() if next_step else None
        return True, _emit_step_sse(step_value, "interrupted", '任务已被中断')
    return False, ""


async def task_pause_check(
    task_id: str,
    next_step: Optional[Callable[[], int]] = None,
    timeout: Optional[float] = None,
) -> AsyncGenerator[str, None]:
    """检查任务是否被暂停,如果是则发送paused事件并等待恢复

    timeout=None: 无限等待(流式开始前调用)
    timeout=300: 带超时等待(流式循环内调用)

    小沈 2026-06-17 合并task_pause_check/task_pause_check_and_yield
    """
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
        yield _emit_step_sse(step_value, "paused", '任务已暂停')

    try:
        if timeout:
            await asyncio.wait_for(pause_event.wait(), timeout=timeout)
        else:
            await pause_event.wait()
    except asyncio.TimeoutError:
        logger.warning(f"[task_pause_check] 任务{task_id}暂停超时({timeout}s),自动恢复")
        await set_was_paused(task_id, False)
        return

    if await check_cancelled(task_id):
        return

    await set_was_paused(task_id, False)
    step_value = next_step() if next_step else None
    yield _emit_step_sse(step_value, "resumed", '任务已恢复')


async def task_pause_check_and_yield(
    task_id: str,
    next_step: Optional[Callable[[], int]] = None
) -> AsyncGenerator[str, None]:
    """流式循环内暂停检查 — 委托给task_pause_check(timeout=300) — 小沈 2026-06-17"""
    async for event in task_pause_check(task_id, next_step, timeout=300):
        yield event
