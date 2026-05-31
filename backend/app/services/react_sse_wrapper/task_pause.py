# -*- coding: utf-8 -*-
"""
暂停任务 — 从 react_sse_wrapper.py 拆出

复制来源: react_sse_wrapper.py 第580-603行 (pause_task)
Author: 小沈 - 2026-05-31
"""

from app.services.react_sse_wrapper.task_registry import running_tasks_lock, running_tasks
from app.utils.logger import logger


# ============================================================
# 从 react_sse_wrapper.py 第580-603行复制（原封不动）
# ============================================================

async def pause_task(task_id: str, session_id = None) -> dict:
    """
    暂停指定的流式任务
    
    Args:
        task_id: 任务ID
        session_id: 会话ID（可选）
    
    Returns:
        {"success": bool, "message": str}
    """
    if session_id:
        logger.info(f"[Pause] 会话 {session_id} 暂停任务 {task_id}")
    
    async with running_tasks_lock:
        if task_id in running_tasks:
            # 如果任务已被中断，不能暂停
            if running_tasks[task_id].get("cancelled", False):
                return {"success": False, "message": f"任务 {task_id} 已被中断，无法暂停"}
            running_tasks[task_id]["paused"] = True
            running_tasks[task_id]["status"] = "paused"
            logger.info(f"[Pause] 任务 {task_id} 已暂停")
            return {"success": True, "message": f"任务 {task_id} 已暂停"}
        return {"success": False, "message": f"任务 {task_id} 不存在"}
