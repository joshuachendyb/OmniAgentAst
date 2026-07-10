# -*- coding: utf-8 -*-
"""
sessions — 路由定义

从 sessions.py 拆出,遵循 SRP:
- 各功能函数独立文件
- 本文件只保留路由定义和装饰器

Author: 小沈 - 2026-02-17
"""

from typing import Optional

from fastapi import APIRouter, Query, HTTPException
from app.utils.logger import logger
from app.utils.response_utils import handle_api_errors
from app.utils.time_utils import get_utc_timestamp
from app.db import db
from app.api.v1.messages import display_name_cache
from app.api.v1.sessions.update_session import SessionUpdate
from app.db.models.chat_models import SessionCreate
from app.api.v1.sessions.create_session import create_session
from app.api.v1.sessions.list_sessions import list_sessions
from app.api.v1.sessions.update_session import update_session
from app.api.v1.sessions.get_session_titles_batch import get_session_titles_batch
from app.api.v1.sessions.models import ExecutionStepsUpdate
from app.services.conversation_storage import save_execution_steps

router = APIRouter()


@handle_api_errors("删除会话")
async def delete_session(session_id: str):
    """拷贝自 sessions.py 第300-342行"""
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

    display_name_cache.delete(session_id)
    logger.info(f"删除会话成功: id={session_id}")
    return {"success": True, "message": "会话删除成功"}


@router.post("/sessions")
async def create_session_endpoint(session_create: Optional[SessionCreate] = None):
    return await create_session(session_create)


@router.get("/sessions")
async def list_sessions_endpoint(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: Optional[str] = Query(None),
    is_valid: Optional[bool] = Query(None)
):
    return await list_sessions(page, page_size, keyword, is_valid)


@router.put("/sessions/{session_id}")
async def update_session_endpoint(session_id: str, update_data: SessionUpdate):
    return await update_session(session_id, update_data)


@router.delete("/sessions/{session_id}")
async def delete_session_endpoint(session_id: str):
    return await delete_session(session_id)


@router.get("/sessions/titles/batch")
async def get_session_titles_batch_endpoint(
    session_ids: str = Query(..., description="逗号分隔的会话ID列表")
):
    return await get_session_titles_batch(session_ids)


@router.post("/sessions/{session_id}/execution_steps")
async def save_execution_steps_endpoint(session_id: str, update_data: ExecutionStepsUpdate):
    return await save_execution_steps(session_id, update_data)
