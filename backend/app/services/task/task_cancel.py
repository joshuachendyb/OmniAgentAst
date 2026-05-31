# -*- coding: utf-8 -*-
"""
cancel_task — 取消任务

统一: 小健 - 2026-05-31
"""

from datetime import datetime
from app.services.task.task_registry import set_cancelled, pop_task_field, get_task_field
from app.utils.logger import logger


async def cancel_task(task_id: str, session_id=None) -> dict:
    """
    中断指定的流式任务

    1. 立即设置cancelled状态
    2. 强制关闭LLM HTTP连接
    3. 返回详细的状态信息
    """
    interrupt_time = datetime.now()
    logger.info(f"[TaskControl] 取消任务 {task_id}")

    # 弹出 asyncio.Task 对象并真正取消
    running_task = await pop_task_field(task_id, "_task")
    if running_task is not None and not running_task.done():
        running_task.cancel()
        logger.info(f"[Task Cancelled] 任务 {task_id} asyncio.Task.cancel() 已调用")

    # 强制关闭HTTP连接（兜底）
    ai_service = await get_task_field(task_id, "ai_service")
    if ai_service:
        try:
            ai_service.cancel()
            logger.info(f"[Task Cancelled] 任务 {task_id} HTTP连接已强制关闭")
        except Exception as e:
            logger.error(f"[Task Cancelled] 关闭HTTP连接失败: {e}")

    # 设置cancelled状态（含时间戳）
    success = await set_cancelled(
        task_id,
        interrupt_time=interrupt_time.isoformat(),
        cancel_request_time=interrupt_time.timestamp(),
    )

    if success:
        logger.info(f"[Task Cancelled] 任务 {task_id} 已标记为cancelled，保留记录")
        return {
            "success": True,
            "message": f"任务 {task_id} 已中断",
            "task_status": "cancelled",
            "interrupt_time": interrupt_time.isoformat()
        }
    else:
        logger.warning(f"[TaskControl] 任务 {task_id} 不存在，可能已结束")
        return {"success": False, "message": f"任务 {task_id} 不存在", "task_status": "not_found"}
