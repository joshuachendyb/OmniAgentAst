# -*- coding: utf-8 -*-
"""
confirm_operation — 从 chat_router.py 拷出

拷贝来源: chat_router.py 第360-374行
"""

from fastapi import Request

from app.utils.logger import logger


async def confirm_operation(request: Request):
    """拷贝自 chat_router.py 第360-374行"""
    body = await request.json()
    task_id = body.get("task_id")
    confirmed = body.get("confirmed", True)

    logger.info(f"[TaskControl] 用户确认: task_id={task_id}, confirmed={confirmed}")

    return {
        "success": True,
        "message": "确认已收到"
    }
