# -*- coding: utf-8 -*-
"""
conversation 路由定义 — 小沈 2026-05-28
"""

from fastapi import APIRouter

from app.api.v1.conversation.models import ExecutionStepsUpdate
from app.services.conversation_storage import save_execution_steps

router = APIRouter()


@router.post("/sessions/{session_id}/execution_steps")
async def save_execution_steps_endpoint(session_id: str, update_data: ExecutionStepsUpdate):
    return await save_execution_steps(session_id, update_data)
