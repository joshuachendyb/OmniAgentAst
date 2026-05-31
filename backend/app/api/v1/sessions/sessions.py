# -*- coding: utf-8 -*-
"""
sessions — 路由定义

从 sessions.py 拆出，遵循 SRP：
- 各功能函数独立文件
- 本文件只保留路由定义和装饰器

Author: 小沈 - 2026-02-17
"""

from fastapi import APIRouter, Query
from typing import Optional

from app.api.v1.sessions.session_update import SessionUpdate
from app.api.v1.sessions.create_session import create_session
from app.api.v1.sessions.list_sessions import list_sessions
from app.api.v1.sessions.update_session import update_session
from app.api.v1.sessions.delete_session import delete_session
from app.api.v1.sessions.get_session_titles_batch import get_session_titles_batch

router = APIRouter()


@router.post("/sessions")
async def create_session_endpoint(session_create=None):
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
