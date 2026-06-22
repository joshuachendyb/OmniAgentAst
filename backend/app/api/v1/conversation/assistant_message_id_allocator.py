# -*- coding: utf-8 -*-
"""
AssistantMessageIdAllocator — 从 conversation.py 拷出

拷贝来源: conversation.py 第34-79行
修复: 并发session_id归属检查+递增寻空位 — 小健-2026-06-16
"""

import threading
from typing import Dict, Tuple
from sqlite3 import Connection


class AssistantMessageIdAllocator:
    """拷贝自 conversation.py 第34-79行"""

    def __init__(self, user_ids: Dict[str, int], lock: threading.Lock):
        self._user_ids = user_ids
        self._assistant_ids: Dict[str, int] = {}
        self._lock = lock

    def allocate(self, session_id: str, conn: Connection) -> Tuple[int, bool]:
        """拷贝自 conversation.py 第48-79行

        10规范(SRP): 只负责分配assistant消息ID
        10规范(DRY): 复用conn执行查询
        修复: 并发场景下检查session_id归属+递增寻空位
        """
        with self._lock:
            user_id = self._user_ids.get(session_id)

        if user_id is not None:
            expected = user_id + 1
        else:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM chat_messages WHERE session_id=? AND role='user' ORDER BY id DESC LIMIT 1",
                (session_id,),
            )
            row = cursor.fetchone()
            expected = (row["id"] + 1) if row else 1

        cursor = conn.cursor()
        for _ in range(10):
            cursor.execute("SELECT id, role, session_id FROM chat_messages WHERE id=?", (expected,))
            existing = cursor.fetchone()
            if existing is None:
                break
            if existing["role"] == "assistant" and existing["session_id"] == session_id:
                return expected, False
            expected += 1
        else:
            cursor.execute(
                "SELECT id FROM chat_messages ORDER BY id DESC LIMIT 1",
            )
            max_row = cursor.fetchone()
            expected = (max_row["id"] + 1) if max_row else 1

        with self._lock:
            self._assistant_ids[session_id] = expected
        return expected, True
