# -*- coding: utf-8 -*-
"""
task_registry — running_tasks 数据层唯一入口

所有对 running_tasks 的读写操作必须通过本文件的函数。
禁止其他文件直接 import running_tasks / running_tasks_lock 操作字典。

Author: 小健 - 2026-05-31
"""

import asyncio
from datetime import datetime
from typing import Any, Optional

from app.utils.logger import logger
from app.constants import TASK_TIMEOUT

# ============================================================
# 数据存储（本文件私有，外部禁止直接访问）
# ============================================================
_running_tasks_lock = asyncio.Lock()
_running_tasks: dict[str, dict] = {}


# ============================================================
# 注册 / 清理
# ============================================================

async def register_task(task_id: str, ai_service: Any) -> None:
    """注册任务到 running_tasks"""
    async with _running_tasks_lock:
        _running_tasks[task_id] = {
            "status": "running",
            "cancelled": False,
            "paused": False,
            "created_at": datetime.now(),
            "ai_service": ai_service,
            "_task": asyncio.current_task(),
        }


async def cleanup_task(task_id: str) -> bool:
    """清理非cancelled任务，返回True=已清理，False=保留(cancelled记录)"""
    async with _running_tasks_lock:
        if task_id not in _running_tasks:
            return False
        if _running_tasks[task_id].get("status") != "cancelled":
            del _running_tasks[task_id]
            return True
        return False


async def cleanup_expired_tasks() -> None:
    """清理过期任务"""
    now = datetime.now()
    async with _running_tasks_lock:
        expired = [
            tid for tid, t in _running_tasks.items()
            if t.get("created_at") and now - t["created_at"] > TASK_TIMEOUT
        ]
        for tid in expired:
            del _running_tasks[tid]
        if expired:
            logger.info(f"[TaskRegistry] 清理了 {len(expired)} 个过期任务")


# ============================================================
# 读操作（check / get）
# ============================================================

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


async def pop_task_field(task_id: str, field: str) -> Any:
    """从任务中弹出一个字段"""
    async with _running_tasks_lock:
        task = _running_tasks.get(task_id)
        if task:
            return task.pop(field, None)
        return None


async def get_task_field(task_id: str, field: str) -> Any:
    """读取任务的一个字段"""
    async with _running_tasks_lock:
        task = _running_tasks.get(task_id)
        return task.get(field) if task else None


# ============================================================
# 写操作（set）
# ============================================================

async def set_cancelled(task_id: str, **extra) -> bool:
    """设置任务为cancelled状态，返回是否成功"""
    async with _running_tasks_lock:
        task = _running_tasks.get(task_id)
        if not task:
            return False
        task["cancelled"] = True
        task["status"] = "cancelled"
        task.update(extra)
        return True


async def set_paused(task_id: str) -> dict:
    """设置任务暂停，返回 {"success": bool, "message": str}"""
    async with _running_tasks_lock:
        task = _running_tasks.get(task_id)
        if not task:
            return {"success": False, "message": f"任务 {task_id} 不存在"}
        if task.get("cancelled"):
            return {"success": False, "message": f"任务 {task_id} 已被中断，无法暂停"}
        task["paused"] = True
        task["status"] = "paused"
        return {"success": True, "message": f"任务 {task_id} 已暂停"}


async def set_resumed(task_id: str) -> dict:
    """设置任务恢复，返回 {"success": bool, "message": str}"""
    async with _running_tasks_lock:
        task = _running_tasks.get(task_id)
        if not task:
            return {"success": False, "message": f"任务 {task_id} 不存在"}
        if task.get("cancelled"):
            return {"success": False, "message": f"任务 {task_id} 已被中断，无法恢复"}
        if not task.get("paused"):
            return {"success": False, "message": f"任务 {task_id} 未暂停，无法恢复"}
        task["paused"] = False
        task["status"] = "running"
        return {"success": True, "message": f"任务 {task_id} 已继续"}


async def set_was_paused(task_id: str, value: bool) -> None:
    """设置 _was_paused 标志"""
    async with _running_tasks_lock:
        task = _running_tasks.get(task_id)
        if task:
            task["_was_paused"] = value
