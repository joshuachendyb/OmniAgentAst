# -*- coding: utf-8 -*-
"""
清理过期任务 — 从 react_sse_wrapper.py 拆出

复制来源: react_sse_wrapper.py 第151-162行 (cleanup_expired_tasks)
Author: 小沈 - 2026-05-31
"""

from datetime import datetime
from app.services.react_sse_wrapper.task_registry import running_tasks_lock, running_tasks
from app.constants import TASK_TIMEOUT
from app.utils.logger import logger


# ============================================================
# 从 react_sse_wrapper.py 第151-162行复制（原封不动）
# ============================================================

async def cleanup_expired_tasks():
    """清理过期任务"""
    now = datetime.now()
    async with running_tasks_lock:
        expired_tasks = [
            task_id for task_id, task in running_tasks.items()
            if task.get("created_at") and now - task["created_at"] > TASK_TIMEOUT
        ]
        for task_id in expired_tasks:
            del running_tasks[task_id]
        if expired_tasks:
            logger.info(f"清理了 {len(expired_tasks)} 个过期任务")
