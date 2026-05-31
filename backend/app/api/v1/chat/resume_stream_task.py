# -*- coding: utf-8 -*-
"""
resume_stream_task — 从 chat_router.py 拷出

拷贝来源: chat_router.py 第350-356行
"""

from typing import Optional

from app.utils.logger import logger
from app.services.react_sse_wrapper import resume_task as wrapper_resume_task


async def resume_stream_task(task_id: str, session_id: Optional[str] = None):
    """拷贝自 chat_router.py 第350-356行"""
    logger.info(f"[TaskControl] 恢复任务: task_id={task_id}")
    result = await wrapper_resume_task(task_id, session_id)
    return result
