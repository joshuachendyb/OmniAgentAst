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

from app.api.v1.conversation.models import ExecutionStepsUpdate, ExecutionStep
from app.api.v1.conversation.routes import router

__all__ = [
    "router",
    "ExecutionStepsUpdate", "ExecutionStep",
]
