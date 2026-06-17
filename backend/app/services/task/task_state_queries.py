# -*- coding: utf-8 -*-
"""
task_state_queries — running_tasks 只读查询

从 task_registry.py 拆出纯读查询函数，使 llm/ 等底层模块
可依赖查询层而非依赖包含写操作的 registry。

Author: 小健 - 2026-06-17
"""

import asyncio
from typing import Any, Optional

from app.services.task.task_state_store import _running_tasks_lock, _running_tasks


async def check_cancelled(task_id: str) -> bool:
    """统一取消检查"""
    async with _running_tasks_lock:
        task = _running_tasks.get(task_id)
        return bool(task and task.get("cancelled"))


async def check_paused(task_id: str) -> bool:
    """统一暂停检查"""
    async with _running_tasks_lock:
        task = _running_tasks.get(task_id)
        return bool(task and task.get("paused"))


async def check_was_paused(task_id: str) -> bool:
    """检查 _was_paused 标志"""
    async with _running_tasks_lock:
        task = _running_tasks.get(task_id)
        return bool(task and task.get("_was_paused"))


async def get_task_status(task_id: str) -> Optional[str]:
    """获取任务状态"""
    async with _running_tasks_lock:
        task = _running_tasks.get(task_id)
        return task.get("status") if task else None


async def is_task_running(task_id: str) -> bool:
    """检查任务是否存在"""
    async with _running_tasks_lock:
        return task_id in _running_tasks


async def get_cancel_request_time(task_id: str) -> Optional[float]:
    """获取取消请求时间戳"""
    async with _running_tasks_lock:
        task = _running_tasks.get(task_id)
        return task.get("cancel_request_time") if task else None


async def get_pause_event(task_id: str) -> Optional[asyncio.Event]:
    """获取任务的暂停事件 — 用于事件驱动等待"""
    async with _running_tasks_lock:
        task = _running_tasks.get(task_id)
        return task.get("_pause_event") if task else None


async def get_task_field(task_id: str, field: str) -> Any:
    """读取任务的一个字段"""
    async with _running_tasks_lock:
        task = _running_tasks.get(task_id)
        return task.get(field) if task else None