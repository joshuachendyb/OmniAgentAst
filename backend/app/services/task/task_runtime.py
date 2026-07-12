# -*- coding: utf-8 -*-
"""
task_runtime — 运行态任务管理（内存）

合并自: task_state_queries + task_cancel + task_cancel_check + task_interrupt_check
小欧 2026-07-10
"""

from datetime import datetime
from typing import Optional, Callable, AsyncGenerator

from app.logger import logger
from app.utils.sse_formatter import format_agent_sse
from app.utils.response_utils import api_success, api_failure
from app.services.task.task_state import (
    check_cancelled, check_paused, check_was_paused,
    get_task_field, get_pause_event, running_tasks_lock, running_tasks,
)
from app.services.task.task_registry import (
    set_cancelled, pop_task_field,
    set_was_paused, build_step_dict,
)

from app.services.agent.status_table import set_status, AgentStatus

# ============================================================
# 取消/暂停操作（从 task_cancel 迁入）
# ============================================================

async def cancel_task(task_id: str, session_id=None) -> dict:
    interrupt_time = datetime.now()
    logger.info(f"[TaskControl] 取消任务 {task_id}")
    success = await set_cancelled(
        task_id,
        interrupt_time=interrupt_time.isoformat(),
        cancel_request_time=interrupt_time.timestamp(),
    )
    ai_service = await get_task_field(task_id, "ai_service")
    if ai_service:
        try:
            await ai_service.cancel()
            logger.info(f"[Task Cancelled] 任务 {task_id} HTTP连接已强制关闭")
        except Exception as e:
            logger.error(f"[Task Cancelled] 关闭HTTP连接失败: {e}")
    if success:
        logger.info(f"[Task Cancelled] 任务 {task_id} 已标记为cancelled,保留记录")
        return api_success(message=f"任务 {task_id} 已中断", task_status="cancelled", interrupt_time=interrupt_time.isoformat())
    else:
        logger.warning(f"[TaskControl] 任务 {task_id} 不存在,可能已结束")
        return api_failure(message=f"任务 {task_id} 不存在", task_status="not_found")

# ============================================================
# 取消/暂停检查 + SSE（从 task_cancel_check + task_interrupt_check 迁入）
# ============================================================

async def task_cancel_check_and_yield(
    task_id: str, next_step: Callable[[], int], session_id: str,
    current_execution_steps: list, current_content: str
) -> Optional[str]:
    if await check_cancelled(task_id):
        has_interrupted = any(
            s.get('incident_value') == 'interrupted' for s in current_execution_steps
        )
        if has_interrupted:
            logger.info(f"[InterruptCheck] 任务 {task_id} 已有interrupted step,跳过")
            return None
        logger.info(f"[InterruptCheck] 任务 {task_id} 取消状态: True")
        step_dict = build_step_dict(next_step(), "interrupted", '任务已被中断')
        logger.info(f"[Step incident] 发送incident步骤(interrupted)")
        current_execution_steps.append(step_dict)
        return format_agent_sse(step_dict)
    return None


def _emit_step_sse(step: Optional[int], step_type: str, message: str) -> str:
    return format_agent_sse(build_step_dict(step, step_type, message))


async def task_interrupt_check(
    task_id: str,
    next_step: Optional[Callable[[], int]] = None
) -> tuple:
    if await check_cancelled(task_id):
        step_value = next_step() if next_step else None
        return True, _emit_step_sse(step_value, "interrupted", '任务已被中断')
    return False, ""


async def task_pause_check(
    task_id: str,
    next_step: Optional[Callable[[], int]] = None,
    timeout: Optional[float] = None,
) -> AsyncGenerator[str, None]:
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
        _agent = running_tasks.get(task_id, {}).get("agent")
        if _agent is not None and _agent.status in (AgentStatus.THINKING, AgentStatus.EXECUTING):
            set_status(_agent, AgentStatus.SUSPENDED, "用户暂停任务")
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
    _agent = running_tasks.get(task_id, {}).get("agent")
    if _agent is not None and _agent.status == AgentStatus.SUSPENDED:
        set_status(_agent, AgentStatus.THINKING, "任务已恢复")
    step_value = next_step() if next_step else None
    yield _emit_step_sse(step_value, "resumed", '任务已恢复')


async def task_pause_check_and_yield(
    task_id: str,
    next_step: Optional[Callable[[], int]] = None
) -> AsyncGenerator[str, None]:
    async for event in task_pause_check(task_id, next_step, timeout=300):
        yield event
