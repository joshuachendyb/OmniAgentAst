# -*- coding: utf-8 -*-
"""
task_cleanup — 任务完成后清理

统一: 小健 - 2026-05-31
"""

from typing import Dict, Any
from app.utils.logger import logger
from app.services.task.task_registry import cleanup_task as registry_cleanup


async def task_cleanup(
    task_id: str,
    agent_llm_holder: Dict[str, Any],
    llm_call_count: int,
) -> None:
    """任务完成后清理"""
    reported_llm = agent_llm_holder.get("n", 0) if agent_llm_holder.get("n", 0) > 0 else llm_call_count
    logger.info(
        f"[LLM Total Counter] ====== Conversation finished, total LLM calls: {reported_llm} ======"
    )
    cleaned = await registry_cleanup(task_id)
    if cleaned:
        logger.info(f"[Cleanup] 任务 {task_id} 正常完成，已清理")
    else:
        logger.info(f"[Cleanup] 任务 {task_id} 已被中断，保留记录")
