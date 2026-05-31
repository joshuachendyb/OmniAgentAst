# -*- coding: utf-8 -*-
"""
delete_session — 从 sessions.py 拷出

拷贝来源: sessions.py 第300-342行
"""

from fastapi import APIRouter, HTTPException
from app.utils.logger import logger
from app.utils.display_name_cache import clear_cached_display_name
from app.utils.time_utils import get_utc_timestamp
from app.db import db


async def delete_session(session_id: str):
    """拷贝自 sessions.py 第300-342行"""
    try:
        with db.get_conn("chat") as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT id FROM chat_sessions WHERE id = ? AND is_deleted = FALSE',
                (session_id,)
            )
            session = cursor.fetchone()
            if not session:
                raise HTTPException(status_code=404, detail=f"会话不存在: {session_id}")
            utc_time = get_utc_timestamp()
            cursor.execute(
                'UPDATE chat_sessions SET is_deleted = TRUE, updated_at = ? WHERE id = ?',
                (utc_time, session_id)
            )

        clear_cached_display_name(session_id)
        logger.info(f"删除会话成功: id={session_id}")
        return {"success": True, "message": "会话删除成功"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除会话失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除会话失败: {str(e)}")
