# -*- coding: utf-8 -*-
"""
TaskLifecycleManager — running_tasks字典的并发安全管理 — 小沈 2026-05-25

管理任务注册、查询、清理，asyncio.Lock并发安全。
供 generate_sse_stream 和 cancel/pause/resume API端点共同使用。
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Dict, Optional


class TaskLifecycleManager:
    """管理running_tasks字典的注册、查询、清理。asyncio.Lock并发安全

    使用场景:
        - generate_sse_stream中任务的注册和清理
        - cancel/pause/resume API端点中任务状态查询
        - 所有需要操作running_tasks字典的场景

    使用示例:
        manager = TaskLifecycleManager(running_tasks, running_tasks_lock)
        await manager.register(task_id, ai_service)
        if manager.is_cancelled(task_id):
            ...
        await manager.cleanup(task_id)

    返回数据说明:
        - register: 无返回值，将任务信息写入running_tasks
        - cancel: 返回bool，True表示成功取消
        - cleanup: 返回bool，True表示已清理，False表示保留(cancelled记录)
        - is_cancelled: 返回bool，True表示任务已被取消

    Author: 小沈 2026-05-25
    """

    def __init__(self, running_tasks: Dict[str, Any], lock: asyncio.Lock):
        self._tasks = running_tasks
        self._lock = lock

    async def register(self, task_id: str, ai_service: Any) -> None:
        async with self._lock:
            self._tasks[task_id] = {
                "status": "running",
                "cancelled": False,
                "paused": False,
                "created_at": datetime.now(),
                "ai_service": ai_service,
                "_task": asyncio.current_task(),
            }

    async def cancel(self, task_id: str) -> bool:
        async with self._lock:
            if task_id in self._tasks:
                self._tasks[task_id]["cancelled"] = True
                self._tasks[task_id]["status"] = "cancelled"
                return True
            return False

    async def cleanup(self, task_id: str) -> bool:
        """返回True表示已清理，False表示保留(cancelled记录)"""
        async with self._lock:
            if task_id not in self._tasks:
                return False
            current_status = self._tasks[task_id].get("status")
            if current_status != "cancelled":
                del self._tasks[task_id]
                return True
            return False

    def is_cancelled(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        return bool(task and task.get("cancelled"))
