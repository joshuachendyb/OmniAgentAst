# -*- coding: utf-8 -*-
"""
save_execution_steps — 从 conversation.py 拷出

拷贝来源: conversation.py 第198-221行
"""

from typing import Optional
from sqlite3 import Connection
from fastapi import APIRouter, HTTPException

from app.utils.logger import logger
from app.db import db
from app.utils.json_utils import safe_json_dumps
from app.utils.time_utils import get_timestamp_ms
from app.utils.message_id_tracker import _user_message_ids, _message_ids_lock
from app.api.v1.conversation.assistant_message_id_allocator import AssistantMessageIdAllocator
from app.utils.display_utils import extract_metadata_from_steps
from app.api.v1.conversation.models import ExecutionStepsUpdate

# 模块级单例:AssistantMessageIdAllocator复用实例(避免每次调用新建,缓存失效)
_allocator = AssistantMessageIdAllocator(_user_message_ids, _message_ids_lock)


def ensure_session_exists(session_id: str, conn: Connection) -> None:
    """拷贝自 conversation.py 第104-112行"""
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM chat_sessions WHERE id=? AND is_deleted=FALSE", (session_id,))
    if cursor.fetchone() is None:
        raise HTTPException(status_code=404, detail=f"会话不存在: {session_id}")


def insert_assistant_message(
    conn: Connection, ai_message_id: int, session_id: str,
    display_name: Optional[str], update_data,
) -> None:
    """拷贝自 conversation.py 第115-131行

    10规范(SRP): 只负责INSERT,内容在update_message_fields中更新
    """
    cursor = conn.cursor()
    utc_time = get_timestamp_ms()
    initial_content = update_data.content or ""
    reply_to = getattr(update_data, 'reply_to_message_id', None)
    cursor.execute(
        """INSERT INTO chat_messages
           (id, session_id, role, content, timestamp, display_name, reply_to_message_id)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (ai_message_id, session_id, "assistant", initial_content, utc_time, display_name, reply_to),
    )
    logger.info(f"新消息创建: ai_message_id={ai_message_id}, session_id={session_id}, display_name={display_name}")


def update_message_fields(
    conn: Connection, ai_message_id: int,
    update_data, display_name: str,
) -> None:
    """拷贝自 conversation.py 第134-156行"""
    cursor = conn.cursor()
    fields: list = []
    values: list = []
    if update_data.execution_steps:
        fields.append("execution_steps = ?")
        values.append(safe_json_dumps(update_data.execution_steps))
    if update_data.content is not None:
        fields.append("content = ?")
        values.append(update_data.content)
    if fields:
        values.append(ai_message_id)
        cursor.execute(
            f'UPDATE chat_messages SET {", ".join(fields)} WHERE id = ?',
            values,
        )


def update_session_message_count(
    conn: Connection, session_id: str, increment: bool,
) -> None:
    """拷贝自 conversation.py 第159-177行"""
    cursor = conn.cursor()
    utc_time = get_timestamp_ms()
    if increment:
        cursor.execute(
            "UPDATE chat_sessions SET message_count=message_count+1, updated_at=? WHERE id=?",
            (utc_time, session_id),
        )
    else:
        cursor.execute(
            "UPDATE chat_sessions SET updated_at=? WHERE id=?",
            (utc_time, session_id),
        )


async def save_execution_steps(session_id: str, update_data: ExecutionStepsUpdate):
    """拷贝自 conversation.py 第198-221行"""
    try:
        with db.get_conn("chat") as conn:
            ensure_session_exists(session_id, conn)
            ai_message_id, is_new = _allocator.allocate(session_id, conn)
            metadata = extract_metadata_from_steps(update_data.execution_steps)
            display_name = metadata.get("display_name")
            if is_new:
                insert_assistant_message(conn, ai_message_id, session_id, display_name, update_data)
            update_message_fields(conn, ai_message_id, update_data, display_name)
            update_session_message_count(conn, session_id, is_new)
        logger.info(f"保存执行步骤成功: session_id={session_id}, ai_message_id={ai_message_id}, is_new={is_new}")
        return {"success": True, "ai_message_id": ai_message_id, "is_new_message": is_new}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"保存执行步骤失败: {e}")
        raise HTTPException(status_code=500, detail=f"保存执行步骤失败: {str(e)}")
