# -*- coding: utf-8 -*-
"""
取消任务 — 从 react_sse_wrapper.py 拆出

复制来源: react_sse_wrapper.py 第509-577行 (cancel_task)
Author: 小沈 - 2026-05-31
"""

from datetime import datetime
from app.services.react_sse_wrapper.task_registry import running_tasks_lock, running_tasks
from app.utils.logger import logger


# ============================================================
# 从 react_sse_wrapper.py 第509-577行复制（原封不动）
# ============================================================

async def cancel_task(task_id: str, session_id = None) -> dict:
    """
    中断指定的流式任务
    
    【方案4改进】增强中断响应机制：
    1. 立即设置cancelled状态
    2. 强制关闭LLM HTTP连接
    3. 返回详细的状态信息
    
    Args:
        task_id: 任务ID
        session_id: 会话ID（可选，用于阻止重连）
    
    Returns:
        {"success": bool, "message": str, "task_status": str}
    """
    # 记录中断时间戳
    interrupt_time = datetime.now()
    
    async with running_tasks_lock:
        logger.info(f"[TaskControl] 当前running_tasks数量: {len(running_tasks)}, keys: {list(running_tasks.keys())}")
        
        if task_id in running_tasks:
            task_info = running_tasks[task_id]
            task_info["cancelled"] = True
            task_info["status"] = "cancelled"
            task_info["interrupt_time"] = interrupt_time.isoformat()  # 【方案4】记录中断时间
            task_info["cancel_request_time"] = interrupt_time.timestamp()  # 【时间测量】记录取消请求时间
            
            # 【日志增强】记录任务详细信息和时间差
            now_ts = interrupt_time.timestamp()
            logger.info(f"[TaskControl] 中断任务 {task_id}，时间戳: {now_ts}")
            logger.info(f"[TaskControl] ai_service存在: {'ai_service' in task_info}")
            logger.info(f"[TaskControl] 任务步骤: {task_info.get('current_step', 'unknown')}")
            
            # 【2026-05-13 小沈】优先用asyncio.Task.cancel()真正中断运行中的生成器
            running_task = task_info.pop("_task", None)
            if running_task is not None and not running_task.done():
                running_task.cancel()
                logger.info(f"[Task Cancelled] 任务 {task_id} asyncio.Task.cancel() 已调用")
            
            # 【方案4】强制关闭HTTP连接（兜底）
            if "ai_service" in task_info and task_info["ai_service"]:
                ai_service = task_info["ai_service"]
                try:
                    ai_service.cancel()
                    logger.info(f"[Task Cancelled] 任务 {task_id} HTTP连接已强制关闭")
                except Exception as e:
                    logger.error(f"[Task Cancelled] 关闭HTTP连接失败: {e}")
            
            # 从 running_tasks 中移除任务（避免内存泄漏）
            # 修改：不立即删除，设置为cancelled状态保留记录
            # del running_tasks[task_id]  # 不要立即删除
            # 改为设置状态为已取消，但保留记录
            logger.info(f"[Task Cancelled] 任务 {task_id} 已标记为cancelled，保留记录")
            
            # 返回更详细的状态信息
            return {
                "success": True, 
                "message": f"任务 {task_id} 已中断",
                "task_status": "cancelled",
                "interrupt_time": interrupt_time.isoformat()
            }
        else:
            logger.warning(f"[TaskControl] 任务 {task_id} 不在running_tasks中，可能已结束")
            return {"success": False, "message": f"任务 {task_id} 不存在", "task_status": "not_found"}
