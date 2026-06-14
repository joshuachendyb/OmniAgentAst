# -*- coding: utf-8 -*-
"""
ensure_session_exists — 从 conversation.py 拷出

拷贝来源: conversation.py 第104-112行
"""

from sqlite3 import Connection
from fastapi import HTTPException


def ensure_session_exists(session_id: str, conn: Connection) -> None:
    """拷贝自 conversation.py 第104-112行"""
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM chat_sessions WHERE id=? AND is_deleted=FALSE", (session_id,))
    if cursor.fetchone() is None:
        raise HTTPException(status_code=404, detail=f"会话不存在: {session_id}")
