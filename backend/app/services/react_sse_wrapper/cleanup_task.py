# -*- coding: utf-8 -*-
"""
_cleanup_task — 从 react_sse_wrapper.py 拆出

复制来源: react_sse_wrapper.py 第246-262行
Author: 小沈 - 2026-05-31
"""

from typing import Dict, Any

from app.utils.logger import logger
from app.services.task_lifecycle import TaskLifecycleManager


async def cleanup_task(
    task_id: str,
    manager: TaskLifecycleManager,
    agent_llm_holder: Dict[str, Any],
    llm_call_count: int,
) -> None:
    """复制自 react_sse_wrapper.py 第246-262行"""
    reported_llm = agent_llm_holder.get("n", 0) if agent_llm_holder.get("n", 0) > 0 else llm_call_count
    logger.info(
        f"[LLM Total Counter] ====== Conversation finished, total LLM calls: {reported_llm} ======"
    )
    cleaned = await manager.cleanup(task_id)
    if cleaned:
        logger.info(f"[Cleanup] 任务 {task_id} 正常完成，已清理")
    else:
        logger.info(f"[Cleanup] 任务 {task_id} 已被中断，保留记录")
