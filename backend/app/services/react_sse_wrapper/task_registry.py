# -*- coding: utf-8 -*-
"""
任务注册和管理（核心） — 从 react_sse_wrapper.py 拆出

复制来源: react_sse_wrapper.py 第144-146行 (running_tasks_lock, running_tasks)
Author: 小沈 - 2026-05-31
"""

import asyncio
from datetime import datetime
from app.utils.logger import logger
from app.constants import TASK_TIMEOUT


# ============================================================
# 从 react_sse_wrapper.py 第144-146行复制
# ============================================================

# 任务管理字典（存储运行中的任务，用于中断）
running_tasks_lock = asyncio.Lock()
running_tasks: dict[str, dict] = {}


class TaskRegistry:
    """任务注册表 — 封装 running_tasks 的操作"""

    def __init__(self):
        self.lock = running_tasks_lock
        self.tasks = running_tasks

    async def register(self, task_id: str, ai_service) -> None:
        """注册任务到 running_tasks"""
        async with self.lock:
            self.tasks[task_id] = {
                "status": "running",
                "cancelled": False,
                "paused": False,
                "created_at": datetime.now(),
                "ai_service": ai_service,
            }

    def get_task(self, task_id: str) -> dict | None:
        """获取任务信息"""
        return self.tasks.get(task_id)

    def is_cancelled(self, task_id: str) -> bool:
        """检查任务是否已取消"""
        task = self.tasks.get(task_id)
        return task.get("cancelled", False) if task else False

    def is_paused(self, task_id: str) -> bool:
        """检查任务是否已暂停"""
        task = self.tasks.get(task_id)
        return task.get("paused", False) if task else False


task_registry = TaskRegistry()
