# -*- coding: utf-8 -*-
"""
消息ID追踪 — 从messages.py拆出(SRP)

存储每个session的消息ID,提供线程安全的追踪功能
重构: 2026-05-31 小健 - 从messages.py提取(问题21修复)
移动: 2026-06-13 小欧 - 从services/移到utils/层(消除跨层依赖)
"""

import threading
from contextvars import ContextVar
from typing import Dict, Optional

# 存储每个session的消息ID
# key: session_id, value: user_message_id 或 assistant_message_id
_user_message_ids: Dict[str, int] = {}
_message_ids_lock = threading.Lock()


def track_user_message(session_id: str, message_id: int):
    """记录用户消息ID"""
    with _message_ids_lock:
        _user_message_ids[session_id] = message_id


def get_user_message_id(session_id: str) -> Optional[int]:
    """获取用户消息ID"""
    return _user_message_ids.get(session_id)


# ============================================================
# 跨模块 task_id 追踪(原 app.utils.context_vars) — 小欧 2026-07-10
# 合并原因：都是 ID 追踪职责，减少文件数量
# ============================================================

_current_task_id: ContextVar[Optional[str]] = ContextVar("tool_task_id", default=None)
