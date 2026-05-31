# -*- coding: utf-8 -*-
"""
AssistantMessageIdAllocator — 从 conversation.py 拷出

拷贝来源: conversation.py 第34-79行
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
        """拷贝自 conversation.py 第48-79行"""
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
        cursor.execute("SELECT id, role FROM chat_messages WHERE id=?", (expected,))
        existing = cursor.fetchone()
        if existing and existing["role"] == "assistant":
            return expected, False
        if existing and existing["role"] != "assistant":
            cursor.execute(
                "SELECT id FROM chat_messages WHERE session_id=? ORDER BY id DESC LIMIT 1",
                (session_id,),
            )
            max_row = cursor.fetchone()
            expected = (max_row["id"] + 1) if max_row else 1

        with self._lock:
            self._assistant_ids[session_id] = expected
        return expected, True
