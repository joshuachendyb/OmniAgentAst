# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-18 - 小欧 - #23 fix: 删手动BEGIN/COMMIT，归属get_conn事务管理
# 2026-08-08 - 小欧 - 全程统一本地时区: 3处写入改 get_local_iso_timestamp; title_updated_at 输出改 to_local_iso(不再转UTC)
# 2026-08-13 - 小欧 - A7(方案4.7.3步骤3): 业务逻辑(create/list/update/delete/titles_batch + 辅助函数)迁入
#   services/chat/session_service.py; 删除会话的 display_name 缓存清理改经 message_service.delete_session_display_names
#   (不再 direct import messages 缓存对象)。本文件降为路由薄壳(DTO+路由+调service)。
"""
sessions — 会话API路由薄壳 (A7 后路由+DTO 调 session_service)
"""
from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.db.models.chat_models import SessionCreate, SessionListResponse  # noqa: F401 DTO 透传
from app.services.chat.session_service import (
    create_session,
    list_sessions,
    update_session,
    delete_session,
    get_session_titles_batch,
    SessionUpdate,
)
from app.services.chat.storage import save_execution_steps, ExecutionStepsUpdate  # noqa: F401

router = APIRouter()


class _SessionCreate(SessionCreate):
    """会话创建 DTO(继承 models 以兼容现有响应) — 薄壳透传"""
    pass


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