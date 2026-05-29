# 对话管理API路由（对话/任务回合 CRUD）
# 编程人：小沈
# 创建时间：2026-05-28

"""
对话管理API路由

对话（conversation）是一次任务处理的完整回合，
包含用户消息、助手回复和执行步骤（execution_steps）。

与 messages.py 的关系：
- messages.py 管理单条消息（一问一答）
- conversation.py 管理对话/任务回合（含 execution_steps）

从 messages.py 迁移，保留原始代码和注释。
"""

import json
import threading
from typing import Any, Dict, List, Optional, Tuple
from sqlite3 import Connection

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.utils.logger import logger
from app.utils.time_utils import get_timestamp_ms
from app.db import db
from app.api.v1.messages import _user_message_ids, _message_ids_lock

router = APIRouter()


class AssistantMessageIdAllocator:
    """为assistant消息分配唯一ID。save_execution_steps和save_message复用

    使用场景: save_execution_steps中为新的assistant消息分配ID; save_message中复用同一ID分配逻辑
    使用示例: allocator = AssistantMessageIdAllocator(_user_message_ids, _message_ids_lock); message_id, is_new = allocator.allocate(session_id, conn)
    返回数据说明: allocate返回Tuple[int, bool]，(消息ID, 是否为新消息)

    @author 小健 2026-05-25
    """
    def __init__(self, user_ids: Dict[str, int], lock: threading.Lock):
        self._user_ids = user_ids
        self._assistant_ids: Dict[str, int] = {}
        self._lock = lock

    def allocate(self, session_id: str, conn: Connection) -> Tuple[int, bool]:
        """返回 (message_id, is_new)"""
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
        cursor.execute("SELECT id, role FROM chat_messages WHERE id=?", (expected,))
        existing = cursor.fetchone()
        if existing and existing["role"] == "assistant":
            return expected, False
        if existing and existing["role"] != "assistant":
            cursor.execute(
                "SELECT id FROM chat_messages WHERE session_id=? ORDER BY id DESC LIMIT 1",
                (session_id,),
            )
            max_row = cursor.fetchone()
            expected = (max_row["id"] + 1) if max_row else 1

        with self._lock:
            self._assistant_ids[session_id] = expected
        return expected, True


def _extract_metadata(execution_steps: Optional[List[Dict[str, Any]]]) -> Dict[str, Optional[str]]:
    """从execution_steps的start步骤提取model/provider/display_name

    使用场景: save_execution_steps中提取metadata用于display_name
    使用示例: metadata = extract_metadata(update_data.execution_steps)
    返回数据说明: {"model": str|None, "provider": str|None, "display_name": str|None}

    @author 小健 2026-05-25
    """
    if not execution_steps:
        return {"model": None, "provider": None, "display_name": None}
    for step in execution_steps:
        if step.get("type") == "start":
            model = step.get("model")
            provider = step.get("provider")
            display_name = step.get("display_name")
            if not display_name and provider and model:
                display_name = f"{provider} ({model})"
            return {"model": model, "provider": provider, "display_name": display_name}
    return {"model": None, "provider": None, "display_name": None}


def _ensure_session_exists(session_id: str, conn: Connection) -> None:
    """检查会话是否存在，不存在则抛出HTTPException

    @author 小健 2026-05-25
    """
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM chat_sessions WHERE id=? AND is_deleted=FALSE", (session_id,))
    if cursor.fetchone() is None:
        raise HTTPException(status_code=404, detail=f"会话不存在: {session_id}")


def _insert_assistant_message(
    conn: Connection, message_id: int, session_id: str,
    display_name: Optional[str], update_data: "ExecutionStepsUpdate",
) -> None:
    """插入新的assistant消息

    @author 小健 2026-05-25
    """
    cursor = conn.cursor()
    utc_time = get_timestamp_ms()
    initial_content = update_data.content or ""
    cursor.execute(
        """INSERT INTO chat_messages
           (id, session_id, role, content, timestamp, display_name) VALUES (?, ?, ?, ?, ?, ?)""",
        (message_id, session_id, "assistant", initial_content, utc_time, display_name),
    )
    logger.info(f"🆕 [新消息创建] message_id={message_id}, session_id={session_id}, display_name={display_name}")


def _update_message_fields(
    conn: Connection, message_id: int,
    update_data: "ExecutionStepsUpdate", display_name: Optional[str],
) -> None:
    """动态构建并执行消息字段更新

    @author 小健 2026-05-25
    """
    cursor = conn.cursor()
    fields: list = []
    values: list = []
    if update_data.execution_steps:
        fields.append("execution_steps = ?")
        values.append(json.dumps(update_data.execution_steps))
    if update_data.content is not None:
        fields.append("content = ?")
        values.append(update_data.content)
    if fields:
        values.append(message_id)
        cursor.execute(
            f'UPDATE chat_messages SET {", ".join(fields)} WHERE id = ?',
            values,
        )


def _update_session_message_count(
    conn: Connection, session_id: str, increment: bool,
) -> None:
    """更新会话message_count（仅首次创建+1）和updated_at

    @author 小健 2026-05-25
    """
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


class ExecutionStepsUpdate(BaseModel):
    """
    更新执行步骤请求

    @author 小沈
    @update 2026-03-16 v11.0修复：增加content参数，解决前端调用时传递content参数被忽略的问题

    修复的问题：
    - 缺陷1：API参数不匹配 - 后端saveExecutionSteps只有execution_steps参数，没有content参数
    - 缺陷5：visibilitychange调用无效 - 前端传递content参数但API不支持
    - 缺陷6：无法判断新一轮对话 - 添加reply_to_message_id参数用于校验
    """
    execution_steps: Optional[list] = Field(None, description="执行步骤详情列表")
    content: Optional[str] = Field(None, description="AI生成的文本内容，用于实时保存流式输出的内容")
    reply_to_message_id: Optional[int] = Field(None, description="回复的用户消息ID，用于校验和创建正确的AI消息ID")


@router.post("/sessions/{session_id}/execution_steps")
async def save_execution_steps(session_id: str, update_data: ExecutionStepsUpdate):
    """保存/更新会话的执行步骤（智能UPSERT）

    重构：259行大函数拆分为骨架+Allocator+辅助函数
    @author 小沈, 小健 2026-05-25
    """
    allocator = AssistantMessageIdAllocator(_user_message_ids, _message_ids_lock)
    try:
        with db.get_conn("chat") as conn:
            _ensure_session_exists(session_id, conn)
            message_id, is_new = allocator.allocate(session_id, conn)
            metadata = _extract_metadata(update_data.execution_steps)
            display_name = metadata.get("display_name")
            if is_new:
                _insert_assistant_message(conn, message_id, session_id, display_name, update_data)
            _update_message_fields(conn, message_id, update_data, display_name)
            _update_session_message_count(conn, session_id, is_new)
        logger.info(f"保存执行步骤成功: session_id={session_id}, message_id={message_id}, is_new={is_new}")
        return {"success": True, "message_id": message_id, "is_new_message": is_new}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"保存执行步骤失败: {e}")
        raise HTTPException(status_code=500, detail=f"保存执行步骤失败: {str(e)}")
