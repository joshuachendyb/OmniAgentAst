# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-18 - 小欧 - #11 fix: wait_for_confirmation_result 超时返回加 expired=True 标记, 供 action_handler 分流超时/拒绝
# 2026-07-18 - 小欧 - #42 fix: _pending_confirmations 加 threading.Lock 防并发读写
# 2026-08-16 - 小欧 - S2(10.1.7②-5/10.1.8 S2, 北京老陈驱动): "信任本次会话"落库闭环——
#   _PendingConfirmation 加 tool_name 字段; create_confirmation 增 tool_name 透传参数;
#   resolve_confirmation confirm 成功+trust_session=True 时, 经 confirm_id 拆 task_id 反查 session_id(禁伪 agent.session_id)
#   落 insert_session_trust(chat_session_trust), 落库失败只留日志不影响确认结果
# 2026-08-17 - 小健 - 三堂会审-T1修复(北京老陈驱动): 落库用 normalize_tool_name(entry.tool_name) 规范名,
#   与豁免查询侧(action_handler 端 normalize)一致, 防止 LLM 以别名(write_text/writefile)提名时信任落库别名、
#   而查询用规范名导致漏配失效仍触发二次 HITL(与写保护 BUG-2 同模式)。
# 2026-08-24 - 小欧 - 后端卡死修复收尾(offload): resolve_confirmation 为同步函数(API层直调),
#   "信任本次会话"旁路落库块改 daemon 线程投递(本块原为 fire-and-forget: 失败只留日志不影响确认结果),
#   调用线程零 sqlite3 I/O+锁重试 sleep, 落库语义不变
# 2026-09-02 - 小欧 - 会话信任功能修复(v1.5, 北京老陈定案, 详见doc-9月优化/会话信任功能修复方案):
#   5.1: resolve_confirmation 由同步函数改 async def, 信任落库由 daemon Thread 异步投递改 await db.atxn 同步提交(删Thread, API返回前信任行已落库零竞态);
#      反查 session_id 失败由静默跳过改 raise→atxn 回滚并告警(3.2 根因修复, 杜绝"勾信任却不落库"静默丢失);
#   5.5③: _PendingConfirmation 增 path 字段; create_confirmation 增 path 透传参数(tool+path 精确信任落库, 北京老陈"只有tool+path才是准确对象"定案)
# 2026-09-03 - 小欧 - 清理过期确认超时可配置化(北京老陈驱动): _cleanup_stale_confirmations 改读
#   security.hitl_timeout(config.yaml优先, HITL_TIMEOUT 默认120兜底), 与真HITL确认超时同源。
"""
hitl_confirmation — HITL人工确认机制(业务逻辑层)

从 app.api.v1.chat.confirm_operation 下沉而来,消除服务层→API层的反向依赖。
API层仅保留路由函数confirm_operation,业务逻辑全部在此。

小沈 2026-06-17

编辑历史:
  2026-07-14 小欧 集中MAX_PENDING_CONFIRMATIONS至app.constants(代码变迁遗留,非功能退化,同步改导入)
"""

import asyncio
import threading
import time
from dataclasses import dataclass
from typing import Dict, Optional
from uuid import uuid4

from app.services.task.task_runtime import check_cancelled

from app.constants import HITL_TIMEOUT, MAX_PENDING_CONFIRMATIONS
from app.logger import logger


@dataclass
class _PendingConfirmation:
    """待确认请求"""
    future: asyncio.Future
    created_at: float
    tool_name: str = ""  # ②-5 S2(10.1.7②-5): tool_name 随 create_confirmation 透传, 供 trust 落库 — 小欧 2026-08-16
    path: Optional[str] = None  # v1.5(2026-09-02 小欧): 信任目标路径透传, tool+path 精确落库 — 小欧 2026-09-02
# 注: MAX_PENDING_CONFIRMATIONS 已集中迁移至 app.constants(2026-07-14 小欧)
# #42 fix: 加锁防并发读写_pending_confirmations — 小欧 2026-07-18
_pending_confirmations: Dict[str, _PendingConfirmation] = {}
_pending_lock = threading.Lock()
_last_cleanup_time: float = 0.0
_CLEANUP_INTERVAL = 10


def _cleanup_stale_confirmations():
    """清理过期/已完成的确认请求（防止内存泄漏）"""
    global _last_cleanup_time
    now = time.time()

    if now - _last_cleanup_time < _CLEANUP_INTERVAL:
        return

    _last_cleanup_time = now
    from app.config import get_config as _get_cfg_cln  # 对应 config.yaml security.hitl_timeout(过期清理判据与确认等待同源,默认120); 兜底常量 HITL_TIMEOUT — 小欧 2026-09-03
    _hitl_timeout = int(float(_get_cfg_cln().get("security.hitl_timeout", HITL_TIMEOUT)))
    with _pending_lock:
        stale = [k for k, v in _pending_confirmations.items()
                 if v.future.done() or now - v.created_at > _hitl_timeout]
        for k in stale:
            _pending_confirmations.pop(k, None)


async def create_confirmation(task_id: str, tool_name: str = "", path: Optional[str] = None) -> str:
    """
    创建确认请求，返回confirm_id

    在action_handler中调用，先创建再发射MetaStep

    小沈 2026-06-17 从confirm_operation.py下沉
    2026-08-16 小欧 S2(10.1.7②-5): 增 tool_name 透传参数, 存入 _PendingConfirmation
    供 trust 落库(confirm 成功回调经 task_id 反查 session_id 后写 chat_session_trust)
    2026-09-02 小欧 v1.5(北京老陈定案): 增 path 透传参数, 存入 _PendingConfirmation,
    供 tool+path 精确信任落库(check_session_trust 前缀递归匹配豁免)
    """
    _cleanup_stale_confirmations()
    with _pending_lock:
        if len(_pending_confirmations) >= MAX_PENDING_CONFIRMATIONS:
            raise RuntimeError(f"待确认操作数已达上限({MAX_PENDING_CONFIRMATIONS})")

        confirm_id = f"{task_id}:{uuid4().hex[:8]}"
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        _pending_confirmations[confirm_id] = _PendingConfirmation(
            future=future, created_at=time.time(), tool_name=tool_name, path=path
        )
    return confirm_id


async def wait_for_confirmation_result(confirm_id: str, timeout: int = 120) -> Dict:
    """
    等待用户确认结果

    在action_handler中调用，等待前端弹窗的用户选择

    Returns:
        {"confirmed": bool, "trust_session": bool}

    小沈 2026-06-17 从confirm_operation.py下沉
    chendyg 2026-06-26 P1-9修复: 等待确认时检查任务取消状态
    """
    with _pending_lock:
        entry = _pending_confirmations.get(confirm_id)
    if entry is None:
        return {"confirmed": False, "trust_session": False}

    try:
        # 【P1-9修复】等待确认期间检查任务是否已取消 — chendyg 2026-06-26
        task_id = confirm_id.split(":")[0] if ":" in confirm_id else ""
        check_interval = 2
        elapsed = 0
        while elapsed < timeout:
            wait_time = min(check_interval, timeout - elapsed)
            try:
                result = await asyncio.wait_for(
                    asyncio.shield(entry.future), timeout=wait_time,
                )
                return result
            except asyncio.TimeoutError:
                elapsed += wait_time
                if task_id and await check_cancelled(task_id):
                    logger.info(f"[HITL] 任务已取消,终止确认等待: confirm_id={confirm_id}")
                    return {"confirmed": False, "trust_session": False}
        logger.warning(f"[HITL] 确认超时: confirm_id={confirm_id}, timeout={timeout}s")
        return {"confirmed": False, "trust_session": False, "expired": True}
    finally:
        with _pending_lock:
            _pending_confirmations.pop(confirm_id, None)


async def resolve_confirmation(confirm_id: str, confirmed: bool, trust_session: bool) -> bool:
    """
    解除确认等待(由API层路由调用)

    Returns:
        True=成功解除, False=confirm_id不存在或已处理

    小沈 2026-06-17 从confirm_operation.py下沉
    2026-09-02 小欧 5.1/3.2修复(三堂会审): 同步函数改 async; 信任落库由 daemon Thread 异步投递
    改 await db.atxn 同步提交, API 返回前信任行已落库(零竞态强一致, 删 Thread);
    反查 session_id 失败由静默跳过改 raise→atxn 回滚并告警, 杜绝"勾信任却不落库"静默丢失;
    5.5(v1.5 北京老陈定案): 落库增 entry.path 透传, tool+path 精确信任
    """
    with _pending_lock:
        entry = _pending_confirmations.get(confirm_id)
    if entry is None:
        return False

    if entry.future.done():
        return False

    _task_id = confirm_id.split(":")[0] if ":" in confirm_id else ""

    entry.future.set_result({"confirmed": confirmed, "trust_session": trust_session})

    if confirmed and trust_session and entry.tool_name and _task_id:
        try:
            from app.db import db
            from app.services.chat.storage import get_session_id_by_task, insert_session_trust
            from app.tools.tools_alias_mapper import normalize_tool_name  # 落库用规范名, 与豁免查询(normalize)一致防别名漏配 — 小健 2026-08-17

            def _do(conn):
                _sid = get_session_id_by_task(conn, _task_id)
                if not _sid:
                    raise ValueError(f"[HITL] task_id={_task_id} 无 session_id 可反查,信任禁止落库")
                # 5.5(v1.5): 带 path 落库(entry.path 经 create_confirmation 透传) — 小欧 2026-09-02
                insert_session_trust(conn, _sid, normalize_tool_name(entry.tool_name), getattr(entry, "path", None))

            await db.atxn("chat", _do)
            logger.info(f"[HITL] 会话信任落库: task_id={_task_id}, tool_name={normalize_tool_name(entry.tool_name)}")
        except Exception as _te:
            logger.warning(f"[HITL] 会话信任落库失败: task_id={_task_id}, tool_name={entry.tool_name}, err={_te}")

    _cleanup_stale_confirmations()

    logger.info(f"[HITL] 用户确认: confirm_id={confirm_id}, confirmed={confirmed}, trust_session={trust_session}")
    return True


__all__ = ["create_confirmation", "wait_for_confirmation_result", "resolve_confirmation"]