# -*- coding: utf-8 -*-
"""
save_execution_steps — 从 conversation.py 拷出

拷贝来源: conversation.py 第198-221行
"""

from fastapi import APIRouter, HTTPException

from app.utils.logger import logger
from app.db import db
from app.api.v1.messages import _user_message_ids, _message_ids_lock
from app.api.v1.conversation.assistant_message_id_allocator import AssistantMessageIdAllocator
from app.api.v1.conversation.ensure_session_exists import ensure_session_exists
from app.utils.common import extract_metadata_from_steps
from app.api.v1.conversation.insert_assistant_message import insert_assistant_message
from app.api.v1.conversation.update_message_fields import update_message_fields
from app.api.v1.conversation.update_session_message_count import update_session_message_count
from app.api.v1.conversation.models import ExecutionStepsUpdate


async def save_execution_steps(session_id: str, update_data: ExecutionStepsUpdate):
    """拷贝自 conversation.py 第198-221行"""
    allocator = AssistantMessageIdAllocator(_user_message_ids, _message_ids_lock)
    try:
        with db.get_conn("chat") as conn:
            ensure_session_exists(session_id, conn)
            message_id, is_new = allocator.allocate(session_id, conn)
            metadata = extract_metadata_from_steps(update_data.execution_steps)
            display_name = metadata.get("display_name")
            if is_new:
                insert_assistant_message(conn, message_id, session_id, display_name, update_data)
            update_message_fields(conn, message_id, update_data, display_name)
            update_session_message_count(conn, session_id, is_new)
        logger.info(f"保存执行步骤成功: session_id={session_id}, message_id={message_id}, is_new={is_new}")
        return {"success": True, "message_id": message_id, "is_new_message": is_new}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"保存执行步骤失败: {e}")
        raise HTTPException(status_code=500, detail=f"保存执行步骤失败: {str(e)}")
