# -*- coding: utf-8 -*-
"""
conversation — 从 conversation.py 拆出的职责

- AssistantMessageIdAllocator: ID分配器
- extract_metadata: DB持久化
- ensure_session_exists: DB持久化
- insert_assistant_message: DB持久化
- update_message_fields: DB持久化
- update_session_message_count: DB持久化
- save_execution_steps: API路由
"""

from app.api.v1.conversation.assistant_message_id_allocator import AssistantMessageIdAllocator
from app.api.v1.conversation.extract_metadata import extract_metadata
from app.api.v1.conversation.ensure_session_exists import ensure_session_exists
from app.api.v1.conversation.insert_assistant_message import insert_assistant_message
from app.api.v1.conversation.update_message_fields import update_message_fields
from app.api.v1.conversation.update_session_message_count import update_session_message_count
from app.api.v1.conversation.models import ExecutionStepsUpdate
from app.api.v1.conversation.save_execution_steps import save_execution_steps
from app.api.v1.conversation.conversation import router

__all__ = [
    "router",
    "AssistantMessageIdAllocator", "extract_metadata", "ensure_session_exists",
    "insert_assistant_message", "update_message_fields", "update_session_message_count",
    "ExecutionStepsUpdate", "save_execution_steps",
]
