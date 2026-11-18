# -*- coding: utf-8 -*-
# 2026-11-18 商量 - 新建 question 三原语(对称 hitl_confirmation, 无信任语义): create/wait/resolve;
#   阻塞等待经 Future 收口, 超时/取消/任务取消均以结构化结果返回, 过期清理复用 HITL 同源配置
"""
hitl_question — question 工具阻塞问询三原语(业务逻辑层)

与 hitl_confirmation 同构但无信任落库: question 只收集答案, 不写 chat_session_trust。
"""
import asyncio
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.config import get_config
from app.constants import HITL_TIMEOUT as _D_HITL_TIMEOUT
from app.constants import MAX_PENDING_CONFIRMATIONS as _D_MAX_CONFIRM
from app.logger import logger
from app.services.task.task_runtime import check_cancelled


@dataclass
class _PendingQuestion:
    """待回答问题"""
    future: asyncio.Future
    created_at: float
    questions: List[Dict[str, Any]]


_pending_questions: Dict[str, _PendingQuestion] = {}
_pending_lock = threading.Lock()
_last_cleanup_time: float = 0.0
_CLEANUP_INTERVAL = 10
_CHECK_INTERVAL = 2


def _cleanup_stale_questions():
    """清理过期/已完成的问询(防内存泄漏) — 超时判据与 HITL 同源"""
    global _last_cleanup_time
    now = time.time()
    if now - _last_cleanup_time < _CLEANUP_INTERVAL:
        return
    _last_cleanup_time = now
    try:
        timeout = int(float(get_config().get("security.hitl.timeout", _D_HITL_TIMEOUT)))
    except (TypeError, ValueError):
        timeout = _D_HITL_TIMEOUT
    with _pending_lock:
        stale = [k for k, v in _pending_questions.items()
                 if v.future.done() or now - v.created_at > timeout]
        for k in stale:
            _pending_questions.pop(k, None)
        if stale:
            logger.info(f"[question] 清理过期问询: {stale}, timeout={timeout}s")


async def create_question(task_id: str, questions: List[Dict[str, Any]]) -> str:
    """创建问询, 返回 question_id — 商量 2026-11-18"""
    _cleanup_stale_questions()
    with _pending_lock:
        max_pending = get_config().get("tuning.hitl.max_pending_confirmations", _D_MAX_CONFIRM)
        if len(_pending_questions) >= max_pending:
            raise RuntimeError(f"待回答问题数已达上限({max_pending})")
        question_id = f"{task_id}:{uuid4().hex[:8]}"
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        _pending_questions[question_id] = _PendingQuestion(
            future=future, created_at=time.time(), questions=questions,
        )
    logger.info(f"[question] 创建问询: question_id={question_id}, count={len(questions)}")
    return question_id


async def wait_for_question_result(question_id: str, timeout: int = 120) -> Dict[str, Any]:
    """阻塞等待用户答案 — 商量 2026-11-18; 返回 answers/cancelled/expired/reason"""
    with _pending_lock:
        entry = _pending_questions.get(question_id)
    if entry is None:
        logger.debug(f"[question] wait: entry=None question_id={question_id}")
        return {"answers": [], "cancelled": False, "expired": False, "reason": "stale"}

    try:
        task_id = question_id.split(":")[0] if ":" in question_id else ""
        elapsed = 0
        while elapsed < timeout:
            wait_time = min(_CHECK_INTERVAL, timeout - elapsed)
            try:
                result = await asyncio.wait_for(
                    asyncio.shield(entry.future), timeout=wait_time,
                )
                return result
            except asyncio.TimeoutError:
                elapsed += wait_time
                if task_id and await check_cancelled(task_id):
                    logger.info(f"[question] 任务已取消, 终止等待: question_id={question_id}")
                    return {"answers": [], "cancelled": True, "expired": False, "reason": "task_cancelled"}
        logger.info(f"[question] 问询窗口已关闭(未获回答): question_id={question_id}, timeout={timeout}s")
        return {"answers": [], "cancelled": False, "expired": True, "reason": "timeout"}
    finally:
        with _pending_lock:
            _pending_questions.pop(question_id, None)


async def resolve_question(
    question_id: str,
    answers: Optional[List[List[str]]] = None,
    cancelled: bool = False,
) -> bool:
    """解除问询等待(由 API 层路由调用) — 商量 2026-11-18"""
    with _pending_lock:
        entry = _pending_questions.get(question_id)
    if entry is None:
        logger.debug(f"[question] resolve: entry=None question_id={question_id}")
        return False
    if entry.future.done():
        logger.debug(f"[question] resolve: future已done question_id={question_id}")
        return False
    entry.future.set_result({
        "answers": answers or [], "cancelled": cancelled,
        "expired": False, "reason": "cancelled" if cancelled else "answered",
    })
    _cleanup_stale_questions()
    logger.info(f"[question] 用户作答: question_id={question_id}, count={len(answers or [])}, cancelled={cancelled}")
    return True


__all__ = ["create_question", "wait_for_question_result", "resolve_question"]
