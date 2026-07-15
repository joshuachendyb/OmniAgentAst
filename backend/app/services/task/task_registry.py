# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-15 - 小欧 - 注释说明 TASK_TIMEOUT 兜底清理意义(防 running_tasks 内存注册表泄漏); 老陈裁定改为按终态+超时清理: 仅清非活跃(running/paused 外)且超1h任务, 避免误伤长任务/暂停任务
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
from app.services.agent.steps import MetaStep  # 小欧 2026-07-13: build_step_dict 统一走 MetaStep

from app.logger import logger
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
    """清理过期任务(running_tasks 内存注册表兜底防泄漏) — 老陈 2026-07-15 注释说明

    设计意图:
      - running_tasks 是进程内内存字典, 正常任务跑完会由 cleanup_task/pop_task_field 自行移除;
        本函数仅作兜底, 清理遗留僵尸任务, 防内存注册表泄漏。
      - 判定依据(老陈 2026-07-15 裁定: 按终态+超时, 避免误伤长任务):
        仅清理「非活跃状态」且「创建超过 TASK_TIMEOUT(1小时)」的任务。
        活跃状态(running/paused)即使超 1 小时也保留 —— running 可能是 legit 长任务,
        paused 是用户暂停待恢复, 均不应被自动清掉; 取消(cancelled)等终态任务无恢复意义, 超时即清理。
        注: 本字典 status 实际取值仅 running/cancelled/paused(status_table 的 completed/failed 是 agent 对象枚举, 不写此字典)。
    """
    now = datetime.now()
    async with running_tasks_lock:
        expired = [
            tid for tid, t in running_tasks.items()
            if t.get("created_at") and now - t["created_at"] > TASK_TIMEOUT
            and t.get("status") not in ("running", "paused")
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


def build_step_dict(step: Optional[int], step_type: str, message: str, data=None) -> dict:
    """构建step字典 — 统一走 MetaStep，生命周期事件(type=cancelled/paused/resumed)直接产出 — 小欧 2026-07-13
    说明: 不再产出 incident 裸 dict，前端按 step.type 直接渲染（禁止 backward：代码路径单一）"""
    return MetaStep(type=step_type, step=step, content=message or "", data=data or {}).to_dict()
