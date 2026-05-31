# -*- coding: utf-8 -*-
"""
cancel_stream_task — 从 chat_router.py 拷出

拷贝来源: chat_router.py 第330-336行
"""

from typing import Optional

from app.utils.logger import logger
from app.services.react_sse_wrapper import cancel_task as wrapper_cancel_task


async def cancel_stream_task(task_id: str, session_id: Optional[str] = None):
    """拷贝自 chat_router.py 第330-336行"""
    logger.info(f"[TaskControl] 取消任务: task_id={task_id}")
    result = await wrapper_cancel_task(task_id, session_id)
    return result
