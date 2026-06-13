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
from uuid import uuid4

from fastapi import Request

from app.utils.logger import logger


@dataclass
class _PendingConfirmation:
    """待确认请求"""
    future: asyncio.Future
    created_at: float


_CONFIRM_TIMEOUT = 120  # 增加到120s — 修复SSE延迟导致的超时（auth事件yield到客户端需60s）— 小沈 2026-06-10
MAX_PENDING_CONFIRMATIONS = 100  # 【修复P2-4】最大待确认操作数 — 北京老陈 2026-06-13
_pending_confirmations: Dict[str, _PendingConfirmation] = {}
_last_cleanup_time: float = 0.0  # 上次清理时间戳
_CLEANUP_INTERVAL = 10  # 【修复P1-3 2026-06-09 小沈】30秒→10秒，更频繁清理


def _cleanup_stale_confirmations():
    """清理过期/已完成的确认请求（防止内存泄漏）"""
    global _last_cleanup_time
    now = time.time()
    
    # 频率限制：每_CLEANUP_INTERVAL秒最多清理一次
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
    confirm_id = body.get("confirm_id")
    confirmed = body.get("confirmed", True)
    trust_session = body.get("trust_session", False)
    
    if not confirm_id:
        return {"success": False, "error": "missing confirm_id"}
    
    entry = _pending_confirmations.get(confirm_id)
    if entry is None:
        return {"success": False, "error": "confirm_id not found or already processed"}
    
    if entry.future.done():
        return {"success": False, "error": "confirmation already resolved"}
    
    entry.future.set_result({"confirmed": confirmed, "trust_session": trust_session})
    
    _cleanup_stale_confirmations()  # 每次confirm时清理
    
    logger.info(f"[HITL] 用户确认: confirm_id={confirm_id}, confirmed={confirmed}, trust_session={trust_session}")
    
    return {"success": True}


async def create_confirmation(task_id: str) -> str:
    """
    创建确认请求，返回confirm_id
    
    在react_cycle中调用，先创建再发射IncidentStep
    
    【修复 2026-06-09 小沈】使用get_running_loop替代get_event_loop
    【修复P2-4】添加大小限制 — 北京老陈 2026-06-13
    """
    _cleanup_stale_confirmations()
    if len(_pending_confirmations) >= MAX_PENDING_CONFIRMATIONS:
        raise RuntimeError(f"待确认操作数已达上限({MAX_PENDING_CONFIRMATIONS})")

    confirm_id = f"{task_id}:{uuid4().hex[:8]}"
    loop = asyncio.get_running_loop()
    future = loop.create_future()
    _pending_confirmations[confirm_id] = _PendingConfirmation(
        future=future, created_at=time.time()
    )
    return confirm_id


async def wait_for_confirmation_result(confirm_id: str, timeout: int = 120) -> Dict:
    """
    等待用户确认结果
    
    在react_cycle中调用，等待前端弹窗的用户选择
    
    Returns:
        {"confirmed": bool, "trust_session": bool}
    """
    entry = _pending_confirmations.get(confirm_id)
    if entry is None:
        return {"confirmed": False, "trust_session": False}
    
    try:
        return await asyncio.wait_for(entry.future, timeout=timeout)
    except asyncio.TimeoutError:
        logger.warning(f"[HITL] 确认超时: confirm_id={confirm_id}, timeout={timeout}s")
        return {"confirmed": False, "trust_session": False}
    finally:
        _pending_confirmations.pop(confirm_id, None)  # 保证清理


__all__ = ["confirm_operation", "create_confirmation", "wait_for_confirmation_result"]
