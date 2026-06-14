# -*- coding: utf-8 -*-
"""
resolve_update_mode — 从 sessions.py 拷出

拷贝来源: sessions.py 第184-200行
"""

from typing import Tuple

from app.api.v1.sessions.session_update import SessionUpdate


def resolve_update_mode(
    update_data: SessionUpdate,
    cursor, session_id: str, utc_time: str,
) -> Tuple[str, str, tuple]:
    """拷贝自 sessions.py 第184-200行"""
    if update_data.version is not None:
        return "optimistic", "", ()
    cursor.execute(
        """SELECT id, title, COALESCE(version, 1) as version,
                  COALESCE(title_locked, 0) as title_locked
           FROM chat_sessions WHERE id = ? AND is_deleted = FALSE""",
        (session_id,),
    )
    session = cursor.fetchone()
    if not session:
        return "not_found", "", (None, 0)
    return "select_then_update", "", (session, session["version"])
