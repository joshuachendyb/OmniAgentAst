# -*- coding: utf-8 -*-
"""
task_cancel_check — 取消检查并生成SSE事件

小健 - 2026-06-08 修复import路径

从 react_sse_wrapper/is_cancelled_and_yield.py 移入
统一: 小健 - 2026-05-31
【修改 2026-06-09 小沈】删除save_execution_steps_to_db调用，统一在run_sse_stream的finally块中保存
"""

from typing import Optional, Callable

from app.services.agent.steps import IncidentStep
from app.utils.logger import logger
from app.services.task.task_registry import check_cancelled


async def task_cancel_check_and_yield(
    task_id: str, next_step: Callable[[], int], session_id: str,
    current_execution_steps: list, current_content: str
) -> Optional[str]:
    """检查取消状态,如果是则生成interrupted SSE事件"""
    if await check_cancelled(task_id):
        # R3-2修复: 检查是否已有interrupted step,防止CancelledError路径重复append — 小沈 2026-06-09
        has_interrupted = any(
            s.get('incident_value') == 'interrupted' for s in current_execution_steps
        )
        if has_interrupted:
            logger.info(f"[InterruptCheck] 任务 {task_id} 已有interrupted step,跳过")
            return None
        logger.info(f"[InterruptCheck] 任务 {task_id} 取消状态: True")
        incident_step = IncidentStep(
            step=next_step(),
            incident_value='interrupted',
            message='任务已被中断'
        )
        logger.info(f"[Step incident] 发送incident步骤(interrupted)")
        current_execution_steps.append(incident_step.to_dict())
        # 【删除 2026-06-09 小沈】删除save调用，统一在run_sse_stream的finally块中保存
        from app.chat_stream import format_agent_sse
        return format_agent_sse(incident_step.to_dict())
    return None
