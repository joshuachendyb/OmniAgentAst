# -*- coding: utf-8 -*-
"""
resume_task — 恢复任务

统一: 小健 - 2026-05-31
"""

from app.services.task.task_registry import set_resumed
from app.utils.logger import logger


async def resume_task(task_id: str, session_id=None) -> dict:
    """
    继续指定的流式任务
    """
    if session_id:
        logger.info(f"[Resume] 会话 {session_id} 恢复任务 {task_id}")

    result = await set_resumed(task_id)
    if result["success"]:
        logger.info(f"[Resume] 任务 {task_id} 已继续")
    return result
