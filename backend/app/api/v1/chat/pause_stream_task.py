# -*- coding: utf-8 -*-
"""
pause_stream_task — 从 chat_router.py 拷出

拷贝来源: chat_router.py 第340-346行
"""

from typing import Optional

from app.utils.logger import logger
from app.services.react_sse_wrapper import pause_task as wrapper_pause_task


async def pause_stream_task(task_id: str, session_id: Optional[str] = None):
    """拷贝自 chat_router.py 第340-346行"""
    logger.info(f"[TaskControl] 暂停任务: task_id={task_id}")
    result = await wrapper_pause_task(task_id, session_id)
    return result
