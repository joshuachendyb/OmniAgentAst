# -*- coding: utf-8 -*-
"""
conversation — 从 conversation.py 拆出的职责

- AssistantMessageIdAllocator: ID分配器
- extract_metadata_from_steps: 从utils/common.py复用
- ensure_session_exists: DB持久化
- insert_assistant_message: DB持久化
- update_message_fields: DB持久化
- update_session_message_count: DB持久化
- save_execution_steps: API路由
"""

from fastapi import APIRouter

from app.api.v1.conversation.models import ExecutionStepsUpdate, ExecutionStep
from app.api.v1.conversation.save_execution_steps import (
    save_execution_steps, ensure_session_exists,
    insert_assistant_message, update_message_fields,
    update_session_message_count,
)
from app.api.v1.conversation.assistant_message_id_allocator import AssistantMessageIdAllocator
from app.utils.display_utils import extract_metadata_from_steps


router = APIRouter()


@router.post("/sessions/{session_id}/execution_steps")
async def save_execution_steps_endpoint(session_id: str, update_data: ExecutionStepsUpdate):
    return await save_execution_steps(session_id, update_data)


__all__ = [
    "router",
    "AssistantMessageIdAllocator", "extract_metadata_from_steps", "ensure_session_exists",
    "insert_assistant_message", "update_message_fields", "update_session_message_count",
    "ExecutionStepsUpdate", "ExecutionStep", "save_execution_steps",
]
