# -*- coding: utf-8 -*-
"""
confirm_operation — HITL人工确认机制

拷贝来源: chat_router.py 第360-374行
v3.4填充空壳 — 小沈 2026-06-09
"""

import asyncio
import time
from dataclasses import dataclass
from typing import Dict

from fastapi import Request

from app.utils.logger import logger


@dataclass
class _PendingConfirmation:
    """待确认请求"""
    future: asyncio.Future
    created_at: float


_CONFIRM_TIMEOUT = 60  # 统一超时（与wait_for_confirmation默认timeout一致）
_pending_confirmations: Dict[str, _PendingConfirmation] = {}
_last_cleanup_time: float = 0.0  # 上次清理时间戳
_CLEANUP_INTERVAL = 30.0  # 清理间隔（秒）


def _cleanup_stale_confirmations():
    """清理过期/已完成的确认请求（防止内存泄漏）"""
    global _last_cleanup_time
    now = time.time()
    
    # 频率限制：每30秒最多清理一次
    if now - _last_cleanup_time < _CLEANUP_INTERVAL:
        return
    
    _last_cleanup_time = now
    stale = [k for k, v in _pending_confirmations.items()
             if v.future.done() or now - v.created_at > _CONFIRM_TIMEOUT]
    for k in stale:
        _pending_confirmations.pop(k, None)


async def confirm_operation(request: Request):
    """
    用户确认操作
    
    前端调用此接口回传用户选择
    """
    body = await request.json()
    task_id = body.get("task_id")
    confirmed = body.get("confirmed", True)
    trust_session = body.get("trust_session", False)
    
    entry = _pending_confirmations.get(task_id)
    if entry and not entry.future.done():
        entry.future.set_result({"confirmed": confirmed, "trust_session": trust_session})
    
    _cleanup_stale_confirmations()  # 每次confirm时清理
    
    logger.info(f"[HITL] 用户确认: task_id={task_id}, confirmed={confirmed}, trust_session={trust_session}")
    
    return {"success": True}


async def wait_for_confirmation(task_id: str, timeout: int = 60) -> Dict:
    """
    等待用户确认
    
    在react_cycle中调用，等待前端弹窗的用户选择
    
    Returns:
        {"confirmed": bool, "trust_session": bool}
    """
    loop = asyncio.get_running_loop()  # Python 3.10+兼容
    future = loop.create_future()
    _pending_confirmations[task_id] = _PendingConfirmation(
        future=future, created_at=time.time()
    )
    
    try:
        return await asyncio.wait_for(future, timeout=timeout)
    except asyncio.TimeoutError:
        logger.warning(f"[HITL] 确认超时: task_id={task_id}, timeout={timeout}s")
        return {"confirmed": False, "trust_session": False}
    finally:
        _pending_confirmations.pop(task_id, None)  # 保证清理


__all__ = ["confirm_operation", "wait_for_confirmation"]
