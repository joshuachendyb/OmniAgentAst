# -*- coding: utf-8 -*-
"""
record_title_history — 从 sessions.py 拷出

拷贝来源: sessions.py 第230-255行
"""

from typing import Optional

from app.utils.logger import logger

_TITLE_HISTORY_TABLE_EXISTS: Optional[bool] = None


def record_title_history(
    cursor, session_id: str, old_title: Optional[str],
    utc_time: str, updated_by: str = "user",
):
    """拷贝自 sessions.py 第230-255行"""
    global _TITLE_HISTORY_TABLE_EXISTS
    if _TITLE_HISTORY_TABLE_EXISTS is None:
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='chat_session_title_history'"
        )
        _TITLE_HISTORY_TABLE_EXISTS = cursor.fetchone() is not None
    if _TITLE_HISTORY_TABLE_EXISTS and old_title:
        cursor.execute(
            """INSERT INTO chat_session_title_history
               (session_id, title, created_at, updated_by, change_reason)
               VALUES (?, ?, ?, ?, ?)""",
            (session_id, old_title, utc_time, updated_by, "user_edit"),
        )
        logger.info(f"记录标题历史: session_id={session_id}, old_title={old_title}")
