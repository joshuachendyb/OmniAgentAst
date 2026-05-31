# -*- coding: utf-8 -*-
"""
list_sessions — 从 sessions.py 拷出

拷贝来源: sessions.py 第126-171行
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from app.utils.logger import logger
from app.utils.response_utils import handle_api_errors
from app.db import db
from app.db.models.chat_models import SessionListResponse, SessionResponse
from app.api.v1.sessions.build_list_where import build_list_where
from app.api.v1.sessions.format_timestamp import format_timestamp


@handle_api_errors("获取会话列表")
async def list_sessions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: Optional[str] = Query(None),
    is_valid: Optional[bool] = Query(None)
):
    """拷贝自 sessions.py 第126-171行"""
    with db.get_conn("chat") as conn:
        cursor = conn.cursor()

        where, params = build_list_where(keyword, is_valid, for_count=True)
        cursor.execute(f"SELECT COUNT(*) FROM chat_sessions {where}", params)
        total = cursor.fetchone()[0]

        where, params = build_list_where(keyword, is_valid, for_count=False)
        offset = (page - 1) * page_size
        cursor.execute(
            f"SELECT id, title, created_at, updated_at, message_count, is_valid "
            f"FROM chat_sessions {where} ORDER BY updated_at DESC, created_at DESC "
            f"LIMIT ? OFFSET ?",
            params + [page_size, offset]
        )
        rows = cursor.fetchall()

    sessions = [
        SessionResponse(
            session_id=row['id'],
            title=row['title'],
            created_at=format_timestamp(row['created_at']),
            updated_at=format_timestamp(row['updated_at']),
            message_count=row['message_count'],
            is_valid=row['is_valid']
        )
        for row in rows
    ]

    logger.info(f"获取会话列表: page={page}, page_size={page_size}, "
                 f"keyword={keyword}, count={len(sessions)}")
    return SessionListResponse(total=total, page=page, page_size=page_size, sessions=sessions)
