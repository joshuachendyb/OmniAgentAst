# -*- coding: utf-8 -*-
"""
task_registry — running_tasks 数据层唯一入口

写操作(register/cleanup/set)保留在本文件。
纯读查询函数已迁移至 task_state_queries.py，本文件re-export保持兼容。

Author: 小健 - 2026-05-31
更新: 小健 - 2026-06-17 读查询函数迁移至task_state_queries.py
"""

import asyncio
from datetime import datetime
from typing import Any, Optional
from app.utils.time_utils import create_timestamp

from app.utils.logger import logger
from app.constants import TASK_TIMEOUT
from app.utils.response_utils import api_success, api_failure

from app.services.task.task_state import (
    check_cancelled,
    check_paused,
    check_was_paused,
    get_task_status,
    is_task_running,
    get_cancel_request_time,
    get_pause_event,
    get_task_field,
    running_tasks_lock,
    running_tasks,
)


# ============================================================
# 注册 / 清理
# ============================================================

async def register_task(task_id: str, ai_service: Any) -> None:
    """注册任务到 running_tasks"""
    async with running_tasks_lock:
        running_tasks[task_id] = {
            "status": "running",
            "cancelled": False,
            "paused": False,
            "created_at": datetime.now(),
            "ai_service": ai_service,
            "_task": asyncio.current_task(),
            "_pause_event": asyncio.Event(),
        }
        running_tasks[task_id]["_pause_event"].set()


async def cleanup_task(task_id: str) -> bool:
    """清理非cancelled任务,返回True=已清理,False=保留(cancelled记录)"""
    async with running_tasks_lock:
        if task_id not in running_tasks:
            return False
        if running_tasks[task_id].get("status") != "cancelled":
            del running_tasks[task_id]
            return True
        return False


async def cleanup_expired_tasks() -> None:
    """清理过期任务"""
    now = datetime.now()
    async with running_tasks_lock:
        expired = [
            tid for tid, t in running_tasks.items()
            if t.get("created_at") and now - t["created_at"] > TASK_TIMEOUT
        ]
        for tid in expired:
            del running_tasks[tid]
        if expired:
            logger.info(f"[TaskRegistry] 清理了 {len(expired)} 个过期任务")


# ============================================================
# 读写操作(pop — 读取并删除)
# ============================================================

async def pop_task_field(task_id: str, field: str) -> Any:
    """从任务中弹出一个字段"""
    async with running_tasks_lock:
        task = running_tasks.get(task_id)
        if task:
            return task.pop(field, None)
        return None


# ============================================================
# 写操作(set)
# ============================================================

async def set_cancelled(task_id: str, **extra) -> bool:
    """设置任务为cancelled状态,返回是否成功"""
    async with running_tasks_lock:
        task = running_tasks.get(task_id)
        if not task:
            return False
        task["cancelled"] = True
        task["status"] = "cancelled"
        task.update(extra)
        return True


async def set_paused(task_id: str) -> dict:
    """设置任务暂停,返回 {"success": bool, "message": str}"""
    async with running_tasks_lock:
        task = running_tasks.get(task_id)
        if not task:
            return api_failure(message=f"任务 {task_id} 不存在")
        if task.get("cancelled"):
            return api_failure(message=f"任务 {task_id} 已被中断,无法暂停")
        task["paused"] = True
        task["status"] = "paused"
        pause_event = task.get("_pause_event")
        if pause_event:
            pause_event.clear()
        return api_success(message=f"任务 {task_id} 已暂停")


async def set_resumed(task_id: str) -> dict:
    """设置任务恢复,返回 {"success": bool, "message": str}"""
    async with running_tasks_lock:
        task = running_tasks.get(task_id)
        if not task:
            return api_failure(message=f"任务 {task_id} 不存在")
        if task.get("cancelled"):
            return api_failure(message=f"任务 {task_id} 已被中断,无法恢复")
        if not task.get("paused"):
            return api_failure(message=f"任务 {task_id} 未暂停,无法恢复")
        task["paused"] = False
        task["status"] = "running"
        pause_event = task.get("_pause_event")
        if pause_event:
            pause_event.set()
        return api_success(message=f"任务 {task_id} 已继续")


async def set_was_paused(task_id: str, value: bool) -> None:
    """设置 _was_paused 标志"""
    async with running_tasks_lock:
        task = running_tasks.get(task_id)
        if task:
            task["_was_paused"] = value


# ============================================================
# 薄包装: 仅供外部调用
# ============================================================

async def pause_task(task_id: str, session_id=None) -> dict:
    """暂停指定的流式任务"""
    if session_id:
        logger.info(f"[Pause] 会话 {session_id} 暂停任务 {task_id}")
    result = await set_paused(task_id)
    if result["success"]:
        logger.info(f"[Pause] 任务 {task_id} 已暂停")
    return result


async def resume_task(task_id: str, session_id=None) -> dict:
    """继续指定的流式任务"""
    if session_id:
        logger.info(f"[Resume] 会话 {session_id} 恢复任务 {task_id}")
    result = await set_resumed(task_id)
    if result["success"]:
        logger.info(f"[Resume] 任务 {task_id} 已继续")
    return result


async def task_cleanup(task_id: str, llm_call_count: int = 0) -> None:
    """任务完成后清理"""
    logger.info(
        f"[LLM Total Counter] ====== Conversation finished, total LLM calls: {llm_call_count} ======"
    )
    cleaned = await cleanup_task(task_id)
    if cleaned:
        logger.info(f"[Cleanup] 任务 {task_id} 正常完成,已清理")
    else:
        logger.info(f"[Cleanup] 任务 {task_id} 已被中断,保留记录")


def build_step_dict(step: Optional[int], step_type: str, message: str) -> dict:
    """构建step字典 — 替代MetaStep.to_dict()，消除对agent/steps的依赖 — 小健 2026-06-17"""
    return {"type": step_type, "step": step, "timestamp": create_timestamp(), "content": message}
