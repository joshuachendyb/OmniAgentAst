# -*- coding: utf-8 -*-
"""
task_cancel_check — 取消检查并生成SSE事件

小健 - 2026-06-08 修复import路径
从 react_sse_wrapper/is_cancelled_and_yield.py 移入
统一: 小健 - 2026-05-31
【修改 2026-06-09 小沈】删除save_execution_steps_to_db调用，统一在run_sse_stream的finally块中保存
【修改 2026-06-17 小健】用简单dict替代MetaStep，消除task→agent循环依赖
"""

from typing import Optional, Callable

from app.utils.logger import logger
from app.utils.time_utils import create_timestamp
from app.utils.sse_formatter import format_agent_sse
from app.services.task.task_state_queries import check_cancelled


def _build_step_dict(step: int, step_type: str, message: str) -> dict:
    """构建step字典 — 替代MetaStep.to_dict()，消除对agent/steps的依赖 — 小健 2026-06-17"""
    return {"type": step_type, "step": step, "timestamp": create_timestamp(), "content": message}


async def task_cancel_check_and_yield(
    task_id: str, next_step: Callable[[], int], session_id: str,
    current_execution_steps: list, current_content: str
) -> Optional[str]:
    """检查取消状态,如果是则生成interrupted SSE事件"""
    if await check_cancelled(task_id):
        has_interrupted = any(
            s.get('incident_value') == 'interrupted' for s in current_execution_steps
        )
        if has_interrupted:
            logger.info(f"[InterruptCheck] 任务 {task_id} 已有interrupted step,跳过")
            return None
        logger.info(f"[InterruptCheck] 任务 {task_id} 取消状态: True")
        step_dict = _build_step_dict(next_step(), "interrupted", '任务已被中断')
        logger.info(f"[Step incident] 发送incident步骤(interrupted)")
        current_execution_steps.append(step_dict)
        return format_agent_sse(step_dict)
    return None
