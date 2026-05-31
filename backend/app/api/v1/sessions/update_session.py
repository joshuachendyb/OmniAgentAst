# -*- coding: utf-8 -*-
"""
update_session — 从 sessions.py 拷出

拷贝来源: sessions.py 第259-296行
"""

from fastapi import APIRouter, HTTPException
from app.utils.logger import logger
from app.utils.time_utils import get_utc_timestamp
from app.db import db
from app.api.v1.sessions.session_update import SessionUpdate
from app.api.v1.sessions.resolve_update_mode import resolve_update_mode
from app.api.v1.sessions.build_update_sql import build_update_sql
from app.api.v1.sessions.build_update_params import build_update_params
from app.api.v1.sessions.record_title_history import record_title_history


async def update_session(session_id: str, update_data: SessionUpdate):
    """拷贝自 sessions.py 第259-296行"""
    try:
        with db.get_conn("chat") as conn:
            cursor = conn.cursor()
            cursor.execute("BEGIN")
            logger.debug(f"开始事务: session_id={session_id}, operation=update_title")
            utc_time = get_utc_timestamp()
            mode, _, params = resolve_update_mode(update_data, cursor, session_id, utc_time)
            if mode == "not_found":
                raise HTTPException(status_code=404, detail=f"会话不存在: {session_id}")
            set_clause, where_clause = build_update_sql(mode)
            update_params = build_update_params(mode, update_data, utc_time, session_id)
            cursor.execute(f"UPDATE chat_sessions {set_clause} WHERE id = ? {where_clause}", update_params)
            if mode == "optimistic":
                if cursor.rowcount == 0:
                    logger.warning(f"版本冲突: session_id={session_id}, client_version={update_data.version}")
                    raise HTTPException(status_code=409, detail="会话已被其他用户修改，请刷新后重试")
                cursor.execute("SELECT id, title, version FROM chat_sessions WHERE id = ?", (session_id,))
                session = cursor.fetchone()
                current_version = session["version"]
            else:
                session, current_version = params
            old_title = session["title"] if session else ""
            new_version = current_version + 1
            record_title_history(cursor, session_id, old_title, utc_time, update_data.updated_by or "user")
            cursor.execute("COMMIT")
        logger.info(f"更新会话成功: id={session_id}, title={update_data.title}, version={new_version}")
        return {"success": True, "title": update_data.title, "version": new_version}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新会话失败: session_id={session_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="更新会话失败，请重试")
