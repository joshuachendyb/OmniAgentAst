# -*- coding: utf-8 -*-
"""
task_cleanup — 任务完成后清理

统一: 小健 - 2026-05-31
F4修复: 删除agent_llm_holder -> 小欧 2026-06-08
"""

from app.utils.logger import logger
from app.services.task.task_registry import cleanup_task as registry_cleanup


async def task_cleanup(
    task_id: str,
    llm_call_count: int = 0,
) -> None:
    """任务完成后清理"""
    logger.info(
        f"[LLM Total Counter] ====== Conversation finished, total LLM calls: {llm_call_count} ======"
    )
    cleaned = await registry_cleanup(task_id)
    if cleaned:
        logger.info(f"[Cleanup] 任务 {task_id} 正常完成,已清理")
    else:
        logger.info(f"[Cleanup] 任务 {task_id} 已被中断,保留记录")
