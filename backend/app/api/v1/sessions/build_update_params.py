# -*- coding: utf-8 -*-
"""
build_update_params — 从 sessions.py 拷出

拷贝来源: sessions.py 第203-210行
"""

from app.api.v1.sessions.session_update import SessionUpdate


def build_update_params(
    mode: str, update_data: SessionUpdate,
    utc_time: str, session_id: str,
) -> tuple:
    """拷贝自 sessions.py 第203-210行"""
    if mode == "optimistic":
        return (update_data.title, utc_time, 1, utc_time, session_id, update_data.version)
    return (update_data.title, utc_time, 1, utc_time, session_id)
