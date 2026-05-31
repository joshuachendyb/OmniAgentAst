# -*- coding: utf-8 -*-
"""
消息ID追踪 — 从messages.py拆出（SRP）

存储每个session的消息ID，提供线程安全的追踪功能
重构: 2026-05-31 小健 - 从messages.py提取（问题21修复）
"""

import threading
from typing import Dict, Optional

# 存储每个session的消息ID
# key: session_id, value: user_message_id 或 assistant_message_id
_user_message_ids: Dict[str, int] = {}
_assistant_message_ids: Dict[str, int] = {}
_message_ids_lock = threading.Lock()


def track_user_message(session_id: str, message_id: int):
    """记录用户消息ID"""
    with _message_ids_lock:
        _user_message_ids[session_id] = message_id


def get_user_message_id(session_id: str) -> Optional[int]:
    """获取用户消息ID"""
    return _user_message_ids.get(session_id)
