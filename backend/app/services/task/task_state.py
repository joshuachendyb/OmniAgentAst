"""
task_state — 运行态任务数据存储 + 只读查询

合并自: task_state_queries
无外部依赖(不导入 task_registry)，专为消除循环导入设计。
小欧 2026-07-10
"""

import asyncio
from typing import Any, Optional

running_tasks_lock = asyncio.Lock()
running_tasks: dict[str, dict] = {}


async def check_cancelled(task_id: str) -> bool:
    async with running_tasks_lock:
        task = running_tasks.get(task_id)
        return bool(task and task.get("cancelled"))


async def check_paused(task_id: str) -> bool:
    async with running_tasks_lock:
        task = running_tasks.get(task_id)
        return bool(task and task.get("paused"))


async def check_was_paused(task_id: str) -> bool:
    async with running_tasks_lock:
        task = running_tasks.get(task_id)
        return bool(task and task.get("_was_paused"))


async def get_task_status(task_id: str) -> Optional[str]:
    async with running_tasks_lock:
        task = running_tasks.get(task_id)
        return task.get("status") if task else None


async def is_task_running(task_id: str) -> bool:
    async with running_tasks_lock:
        return task_id in running_tasks


async def get_cancel_request_time(task_id: str) -> Optional[float]:
    async with running_tasks_lock:
        task = running_tasks.get(task_id)
        return task.get("cancel_request_time") if task else None


async def get_pause_event(task_id: str) -> Optional[asyncio.Event]:
    async with running_tasks_lock:
        task = running_tasks.get(task_id)
        return task.get("_pause_event") if task else None


async def get_task_field(task_id: str, field: str) -> Any:
    async with running_tasks_lock:
        task = running_tasks.get(task_id)
        return task.get(field) if task else None


__all__ = [
    "running_tasks_lock", "running_tasks",
    "check_cancelled", "check_paused", "check_was_paused",
    "get_task_status", "is_task_running",
    "get_cancel_request_time", "get_pause_event", "get_task_field",
]
