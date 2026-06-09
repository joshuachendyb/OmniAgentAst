# -*- coding: utf-8 -*-
"""
pause_task — 暂停任务

统一: 小健 - 2026-05-31
"""

from app.services.task.task_registry import set_paused
from app.utils.logger import logger


async def pause_task(task_id: str, session_id=None) -> dict:
    """
    暂停指定的流式任务
    """
    if session_id:
        logger.info(f"[Pause] 会话 {session_id} 暂停任务 {task_id}")

    result = await set_paused(task_id)
    if result["success"]:
        logger.info(f"[Pause] 任务 {task_id} 已暂停")
    return result
