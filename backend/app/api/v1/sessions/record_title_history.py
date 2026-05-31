# -*- coding: utf-8 -*-
"""
record_title_history — 从 sessions.py 拷出
"""

from typing import Optional

from app.utils.logger import logger


def record_title_history(
    cursor, session_id: str, old_title: Optional[str],
    utc_time: str, updated_by: str = "user",
):
    """拷贝自 sessions.py 第230-255行 — 小健2026-05-31 改用try/except消除全局状态"""
    if not old_title:
        return
    try:
        cursor.execute(
            """INSERT INTO chat_session_title_history
               (session_id, title, created_at, updated_by, change_reason)
               VALUES (?, ?, ?, ?, ?)""",
            (session_id, old_title, utc_time, updated_by, "user_edit"),
        )
        logger.info(f"记录标题历史: session_id={session_id}, old_title={old_title}")
    except Exception:
        logger.debug("chat_session_title_history表不存在，跳过标题历史记录")
