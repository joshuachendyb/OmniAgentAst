# -*- coding: utf-8 -*-
"""
conversation_storage — 会话存储业务逻辑（从 API 层下沉）

合并来源:
- app.api.v1.conversation.save_execution_steps
- app.api.v1.conversation.assistant_message_id_allocator

小欧 2026-07-10 M-15: 从 API 层下沉到服务层，消除 chat_stream 反向依赖
"""

import threading
from typing import Dict, Optional, Tuple
from sqlite3 import Connection

from fastapi import HTTPException
from pydantic import BaseModel, Field

from app.utils.logger import logger
from app.db import db
from app.utils.json_utils import safe_json_dumps
from app.utils.time_utils import create_timestamp
from app.utils.message_id_tracker import _user_message_ids, _message_ids_lock
from app.utils.display_utils import extract_metadata_from_steps


class ExecutionStepsUpdate(BaseModel):
    """执行步骤更新请求体 — 小欧 2026-07-10"""
    execution_steps: Optional[list] = Field(None, description="执行步骤详情列表")
    content: Optional[str] = Field(None, description="AI生成的文本内容")
    reply_to_message_id: Optional[int] = Field(None, description="回复的用户消息ID")


class AssistantMessageIdAllocator:
    """拷贝自 conversation.py 第34-79行"""

    def __init__(self, user_ids: Dict[str, int], lock: threading.Lock):
        self._user_ids = user_ids
        self._assistant_ids: Dict[str, int] = {}
        self._lock = lock

    def allocate(self, session_id: str, conn: Connection) -> Tuple[int, bool]:
        """拷贝自 conversation.py 第48-79行

        10规范(SRP): 只负责分配assistant消息ID
        10规范(DRY): 复用conn执行查询
        修复: 并发场景下检查session_id归属+递增寻空位
        """
        with self._lock:
            user_id = self._user_ids.get(session_id)

        if user_id is not None:
            expected = user_id + 1
        else:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM chat_messages WHERE session_id=? AND role='user' ORDER BY id DESC LIMIT 1",
                (session_id,),
            )
            row = cursor.fetchone()
            expected = (row["id"] + 1) if row else 1

        cursor = conn.cursor()
        for _ in range(10):
            cursor.execute("SELECT id, role, session_id FROM chat_messages WHERE id=?", (expected,))
            existing = cursor.fetchone()
            if existing is None:
                break
            if existing["role"] == "assistant" and existing["session_id"] == session_id:
                return expected, False
            expected += 1
        else:
            cursor.execute(
                "SELECT id FROM chat_messages ORDER BY id DESC LIMIT 1",
            )
            max_row = cursor.fetchone()
            expected = (max_row["id"] + 1) if max_row else 1

        with self._lock:
            self._assistant_ids[session_id] = expected
        return expected, True


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
    """拷贝自 conversation.py 第115-131行"""
    cursor = conn.cursor()
    utc_time = create_timestamp()
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
    utc_time = create_timestamp()
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


async def save_execution_steps(session_id: str, update_data):
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
