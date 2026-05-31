# -*- coding: utf-8 -*-
"""
create_session — 从 sessions.py 拷出

拷贝来源: sessions.py 第70-122行
"""

import uuid
from typing import Optional

from fastapi import HTTPException
from app.utils.logger import logger
from app.utils.response_utils import handle_api_errors
from app.utils.time_utils import get_utc_timestamp, now_str
from app.db import db
from app.db.models.chat_models import SessionCreate, SessionResponse


@handle_api_errors("创建会话")
async def create_session(session_create: Optional[SessionCreate] = None):
    """拷贝自 sessions.py 第70-122行"""
    session_id = str(uuid.uuid4())
    title = session_create.title if session_create and session_create.title else f"新会话 {now_str('%Y-%m-%d %H:%M')}"
    utc_time = get_utc_timestamp()
    is_valid = session_create.is_valid if session_create and session_create.is_valid is not None else False

    with db.get_conn("chat") as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''INSERT INTO chat_sessions 
               (id, title, created_at, updated_at, title_locked, title_updated_at, version, is_valid) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            (session_id, title, utc_time, utc_time, False, utc_time, 1, is_valid)
        )
        logger.info(f"创建会话（使用新字段）: id={session_id}, title={title}, is_valid={is_valid}")

    logger.info(f"创建会话成功: id={session_id}, title={title}")

    return SessionResponse(
        session_id=session_id,
        title=title,
        created_at=utc_time,
        updated_at=utc_time,
        message_count=0,
        is_valid=is_valid
    )
