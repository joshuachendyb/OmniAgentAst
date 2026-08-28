# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-09 - 小欧 - P4拆分(见doc-8月优化修复代码三堂会审报告v1.1): 暂停阻塞核心提取为 _pause_core,
#   react_cycle后台路径改 wait_for_resume(纯阻塞不产SSE), task_pause_check 保留产SSE供前端消费路径
#   (openai._stream_with_control 的 task_pause_check_and_yield)。职责单一, 消除后台死路SSE事件。ast语法✓
# 2026-08-17 - 小健 - 三堂会审收敛(北京老陈深挖db_ops/_stream_with_control): task_cancel_check_and_yield 删
#   死参数 session_id/current_content(函数体从未使用, 调用点 stream_orchestrator 曾白算 current_content 传入);
#   签名收窄为 (task_id, next_step, current_execution_steps), 消除 KISS-DIRECT 透传无用参数 — 小健 2026-08-17
# 2026-08-18 - 小欧 - §10.4.4 P2(弃用 next_step): 各函数删 next_step 参数, 统一经 _current_step(task_id)
#   读 running_tasks[task_id].agent.llm_call_count(or 1 兜底); 删 Callable import — 小欧 2026-08-18
# 2026-08-28 小欧 - yield日志审计: _pause_core 的 paused/resumed yield 前加 logger.info("[pause] task step"), 覆盖4个无日志yield(SRP); 三堂会审无逻辑修正
"""
task_runtime — 运行态任务管理（内存）

合并自: task_state_queries + task_cancel + task_cancel_check
小欧 2026-07-10
"""

from datetime import datetime
from typing import Optional, AsyncGenerator

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

def _current_step(task_id: str) -> int:
    """取任务的当前轮数(统一步号口径) — 小欧 2026-08-18
    §10.4.4 P2(弃用 next_step): 统一读 running_tasks[task_id].agent.llm_call_count,
    or 1 兜底(消费路径可能先于 agent 注册, 防 0 异常)。"""
    _agent = running_tasks.get(task_id, {}).get("agent")
    if _agent is not None:
        return getattr(_agent, "llm_call_count", None) or 1
    return 1

async def cancel_task(task_id: str, session_id=None) -> dict:
    cancel_time = datetime.now()
    logger.info(f"[TaskControl] 取消任务 {task_id}")
    success = await set_cancelled(
        task_id,
        cancel_time=cancel_time.isoformat(),
        cancel_request_time=cancel_time.timestamp(),
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
        return api_success(message=f"任务 {task_id} 已取消", task_status="cancelled", cancel_time=cancel_time.isoformat())
    else:
        logger.warning(f"[TaskControl] 任务 {task_id} 不存在,可能已结束")
        return api_failure(message=f"任务 {task_id} 不存在", task_status="not_found")

# ============================================================
# 取消/暂停检查 + SSE（从 task_cancel_check 迁入）
# ============================================================

async def task_cancel_check_and_yield(
    task_id: str, current_execution_steps: list
) -> Optional[str]:
    # 小健 2026-08-17 三堂会审收敛(KISS-DIRECT): 删死参数 session_id/current_content(函数体从未使用, 调用点白算)
    # 小欧 2026-08-18 P2(§10.4.4): 删 next_step, 步号统一 _current_step(task_id)
    if await check_cancelled(task_id):
        has_cancelled = any(
            s.get('incident_value') == 'cancelled' or s.get('type') == 'cancelled'
            for s in current_execution_steps
        )
        if has_cancelled:
            logger.info(f"[CancelCheck] 任务 {task_id} 已有cancelled step,跳过")
            return None
        logger.info(f"[CancelCheck] 任务 {task_id} 取消状态: True")
        step_dict = build_step_dict(_current_step(task_id), "cancelled", '任务已被取消')
        logger.info(f"[Step] 发送 cancelled 步骤")
        current_execution_steps.append(step_dict)
        return format_agent_sse(step_dict)
    return None


def _emit_step_sse(step: Optional[int], step_type: str, message: str) -> str:
    return format_agent_sse(build_step_dict(step, step_type, message))


async def task_cancel_check(
    task_id: str,
) -> tuple:
    if await check_cancelled(task_id):
        step_value = _current_step(task_id)
        return True, _emit_step_sse(step_value, "cancelled", '任务已被取消')
    return False, ""


async def _pause_core(
    task_id: str,
    timeout: Optional[float],
    emit_sse: bool,
) -> AsyncGenerator[str, None]:
    """暂停阻塞核心: 检测暂停→置SUSPENDED→阻塞等恢复→置THINKING。可选产出SSE。
    拆分依据(三审, 小欧 2026-08-09): 原 task_pause_check 在 react_cycle→agent_runner 路径产出的
    SSE 字符串被 agent_runner 以"跳过非Step事件"丢弃(死路), 但该 SSE 对前端消费路径(openai)是真实所需。
    故拆为两薄封装: wait_for_resume(纯阻塞) / task_pause_check(阻塞+SSE), 职责单一无重复。
    前端暂停提示由 openai._stream_with_control 的 task_pause_check_and_yield 统一下发。"""
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
        if emit_sse:
            step_value = _current_step(task_id)
            # 2026-08-28 小欧 yield日志审计: 暂停事件日志(SRP)
            logger.info(f"[pause] task={task_id} step={step_value} paused")
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
    if emit_sse:
        step_value = _current_step(task_id)
        # 2026-08-28 小欧 yield日志审计: 恢复事件日志(SRP)
        logger.info(f"[pause] task={task_id} step={step_value} resumed")
        yield _emit_step_sse(step_value, "resumed", '任务已恢复')


async def wait_for_resume(task_id: str, timeout: Optional[float] = None) -> None:
    """仅阻塞等待暂停恢复(不产出SSE)。react_cycle 后台编排路径用 — 小欧 2026-08-09
    SSE 上报统一由前端消费路径 task_pause_check 负责, 后台路径不再产出死路事件。"""
    async for _ in _pause_core(task_id, timeout, emit_sse=False):
        pass


async def task_pause_check(
    task_id: str,
    timeout: Optional[float] = None,
) -> AsyncGenerator[str, None]:
    """阻塞+产出暂停/恢复SSE。前端SSE消费路径(openai._stream_with_control)用 — 小欧 2026-08-09
    小欧 2026-08-18 P2(§10.4.4): 删 next_step, 步号统一 _current_step(task_id)"""
    async for sse in _pause_core(task_id, timeout, emit_sse=True):
        yield sse


async def task_pause_check_and_yield(
    task_id: str,
) -> AsyncGenerator[str, None]:
    async for event in task_pause_check(task_id, timeout=300):
        yield event
