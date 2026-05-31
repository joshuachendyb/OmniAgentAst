# -*- coding: utf-8 -*-
"""
update_session_message_count — 从 conversation.py 拷出

拷贝来源: conversation.py 第159-177行
"""

from sqlite3 import Connection

from app.utils.time_utils import get_timestamp_ms


def update_session_message_count(
    conn: Connection, session_id: str, increment: bool,
) -> None:
    """拷贝自 conversation.py 第159-177行"""
    cursor = conn.cursor()
    utc_time = get_timestamp_ms()
    if increment:
        cursor.execute(
            "UPDATE chat_sessions SET message_count=message_count+1, updated_at=? WHERE id=?",
            (utc_time, session_id),
        )
    else:
        cursor.execute(
            "UPDATE chat_sessions SET updated_at=? WHERE id=?",
            (utc_time, session_id),
        )
