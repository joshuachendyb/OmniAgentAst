# -*- coding: utf-8 -*-
"""
恢复任务 — 从 react_sse_wrapper.py 拆出

复制来源: react_sse_wrapper.py 第606-632行 (resume_task)
Author: 小沈 - 2026-05-31
"""

from app.services.react_sse_wrapper.task_registry import running_tasks_lock, running_tasks
from app.utils.logger import logger


# ============================================================
# 从 react_sse_wrapper.py 第606-632行复制（原封不动）
# ============================================================

async def resume_task(task_id: str, session_id = None) -> dict:
    """
    继续指定的流式任务
    
    Args:
        task_id: 任务ID
        session_id: 会话ID（可选）
    
    Returns:
        {"success": bool, "message": str}
    """
    if session_id:
        logger.info(f"[Resume] 会话 {session_id} 恢复任务 {task_id}")
    
    async with running_tasks_lock:
        if task_id in running_tasks:
            # 如果任务已被中断，不能恢复
            if running_tasks[task_id].get("cancelled", False):
                return {"success": False, "message": f"任务 {task_id} 已被中断，无法恢复"}
            # 如果任务没有暂停，不能恢复
            if not running_tasks[task_id].get("paused", False):
                return {"success": False, "message": f"任务 {task_id} 未暂停，无法恢复"}
            running_tasks[task_id]["paused"] = False
            running_tasks[task_id]["status"] = "running"
            logger.info(f"[Resume] 任务 {task_id} 已继续")
            return {"success": True, "message": f"任务 {task_id} 已继续"}
        return {"success": False, "message": f"任务 {task_id} 不存在"}
