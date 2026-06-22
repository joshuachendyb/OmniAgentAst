# -*- coding: utf-8 -*-
"""
hitl_confirmation — HITL人工确认机制(业务逻辑层)

从 app.api.v1.chat.confirm_operation 下沉而来,消除服务层→API层的反向依赖。
API层仅保留路由函数confirm_operation,业务逻辑全部在此。

小沈 2026-06-17
"""

import asyncio
import time
from dataclasses import dataclass
from typing import Dict
from uuid import uuid4

from app.utils.logger import logger


@dataclass
class _PendingConfirmation:
    """待确认请求"""
    future: asyncio.Future
    created_at: float


_CONFIRM_TIMEOUT = 120
MAX_PENDING_CONFIRMATIONS = 100
_pending_confirmations: Dict[str, _PendingConfirmation] = {}
_last_cleanup_time: float = 0.0
_CLEANUP_INTERVAL = 10


def _cleanup_stale_confirmations():
    """清理过期/已完成的确认请求（防止内存泄漏）"""
    global _last_cleanup_time
    now = time.time()

    if now - _last_cleanup_time < _CLEANUP_INTERVAL:
        return

    _last_cleanup_time = now
    stale = [k for k, v in _pending_confirmations.items()
             if v.future.done() or now - v.created_at > _CONFIRM_TIMEOUT]
    for k in stale:
        _pending_confirmations.pop(k, None)


async def create_confirmation(task_id: str) -> str:
    """
    创建确认请求，返回confirm_id

    在action_handler中调用，先创建再发射MetaStep

    小沈 2026-06-17 从confirm_operation.py下沉
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

    在action_handler中调用，等待前端弹窗的用户选择

    Returns:
        {"confirmed": bool, "trust_session": bool}

    小沈 2026-06-17 从confirm_operation.py下沉
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
        _pending_confirmations.pop(confirm_id, None)


def resolve_confirmation(confirm_id: str, confirmed: bool, trust_session: bool) -> bool:
    """
    解除确认等待(由API层路由调用)

    Returns:
        True=成功解除, False=confirm_id不存在或已处理

    小沈 2026-06-17 从confirm_operation.py下沉
    """
    entry = _pending_confirmations.get(confirm_id)
    if entry is None:
        return False

    if entry.future.done():
        return False

    entry.future.set_result({"confirmed": confirmed, "trust_session": trust_session})

    _cleanup_stale_confirmations()

    logger.info(f"[HITL] 用户确认: confirm_id={confirm_id}, confirmed={confirmed}, trust_session={trust_session}")
    return True


__all__ = ["create_confirmation", "wait_for_confirmation_result", "resolve_confirmation"]