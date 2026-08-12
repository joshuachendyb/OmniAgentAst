
# 消息管理API路由(单条消息 CRUD)
# 编程人:小沈
# 创建时间:2026-05-28
# 编辑历史:
# 2026-07-14 - 小欧 - GET消息历史改为从chat_message_steps读取步骤列表, SELECT去除execution_steps列,无数据时从chat_messages.execution_steps列读取
# 2026-07-16 - 小欧 - SELECT 加 thought 列; MessageResponse 传 thought
# 2026-07-18 - 小欧 - timestamp 改 format_timestamp 对外统一 UTC Z; save_message 传 get_utc_timestamp; created_at 补 format_timestamp 兜底
# 2026-07-18 - 小欧 - timestamp配合MessageResponse.timestamp改为str, format_timestamp格式字符串正常传递
# 2026-08-08 - 小欧 - 全程统一本地时区: save_message 传 get_local_iso_timestamp; title_updated_at 输出改 to_local_iso(不再转UTC)
 
"""
消息管理API路由

管理会话内单条消息(一问一答):
1. 获取会话消息历史 - GET /sessions/{session_id}/messages
2. 保存消息 - POST /sessions/{session_id}/messages

对话/任务回合管理(含 execution_steps)已迁移至 conversation.py
"""

import json
from app.utils.json_utils import safe_json_dumps
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.logger import logger
from app.utils.response_utils import handle_api_errors
from app.utils.cache import LRUCache
from app.constants import MAX_CACHE_SIZE
from app.utils.display_utils import extract_display_name_from_steps
from app.utils.time_utils import ensure_timestamp_milliseconds, get_local_iso_timestamp, to_local_iso  # 小欧 2026-08-08 全程统一本地时区
from app.utils.time_utils import format_timestamp
from app.utils.json_utils import parse_json
from app.db import db
from app.db.models.chat_models import MessageResponse
from app.services.chat.storage import track_user_message, get_user_message_id, load_execution_steps

router = APIRouter()

# 消息模块共享的 display_name 缓存
display_name_cache = LRUCache(max_size=MAX_CACHE_SIZE)


@router.get("/sessions/{session_id}/messages")
@handle_api_errors("获取会话消息")
async def get_session_messages(session_id: str):
    """获取会话消息历史(21.3 重构,小沈 2026-05-25 实施)"""
    with db.get_conn("chat") as conn:
        cursor = conn.cursor()

        cursor.execute('''SELECT id, title, created_at, updated_at,
                          COALESCE(title_locked, 0) as title_locked,
                          COALESCE(title_updated_at, created_at) as title_updated_at,
                          COALESCE(version, 1) as version, COALESCE(is_valid, 1) as is_valid
                       FROM chat_sessions WHERE id = ? AND is_deleted = FALSE''', (session_id,))

        session = cursor.fetchone()
        if not session:
            raise HTTPException(status_code=404, detail=f"会话不存在: {session_id}")

        cursor.execute('''SELECT id, session_id, role, content, timestamp, display_name, thought  -- 小欧 2026-07-16 增 thought
                       FROM chat_messages WHERE session_id = ? ORDER BY timestamp ASC''', (session_id,))

        messages = []
        for row in cursor.fetchall():
            msg_id = row['id']
            # 从 chat_message_steps 表读取步骤列表 — 小欧 2026-07-14
            steps = load_execution_steps(conn, msg_id)
            display_name = row['display_name']
            if not display_name and steps:
                display_name = extract_display_name_from_steps(steps)

            messages.append(MessageResponse(
                id=row['id'], session_id=row['session_id'],
                role=row['role'], content=row['content'],
                timestamp=format_timestamp(row['timestamp']),
                execution_steps=steps, display_name=display_name,
                thought=row['thought'],  # 小欧 2026-07-16
            ))

        title_locked = bool(session['title_locked'])
        return {
            "session_id": session_id, "title": session['title'],
            "created_at": format_timestamp(session['created_at']),
            "updated_at": format_timestamp(session['updated_at']),
            "title_locked": title_locked,
            "title_source": "user" if title_locked else "auto",
            "title_updated_at": to_local_iso(session['title_updated_at']),
            "version": session['version'], "is_valid": session['is_valid'],
            "messages": messages,
        }


class MessageCreate(BaseModel):
    """创建消息请求"""
    role: str = Field(..., description="角色:user/assistant/system")
    content: str = Field(..., description="消息内容")
    display_name: Optional[str] = Field(None, description="模型显示名称(可选,记录消息收发时使用的模型)")
    execution_steps: Optional[list] = Field(None, description="执行步骤详情列表")
    client_os: Optional[str] = Field(None, description="客户端操作系统")
    browser: Optional[str] = Field(None, description="浏览器类型")
    device: Optional[str] = Field(None, description="设备类型")
    network: Optional[str] = Field(None, description="网络类型")


def _try_mark_valid(cursor, session_id: str) -> None:
    """如果会话之前is_valid=False,尝试自愈标记为True — 小健 2026-05-25"""
    cursor.execute("SELECT is_valid FROM chat_sessions WHERE id = ?", (session_id,))
    row = cursor.fetchone()
    if row and not row[0]:
        cursor.execute("UPDATE chat_sessions SET is_valid = 1 WHERE id = ?", (session_id,))
        logger.info(f"[save_message] 会话{session_id}已自愈标记为有效")


def _track_user_message(session_id: str, message_id: str) -> None:
    """线程安全地存储user_message_id,覆盖旧值 — 小健 2026-05-25"""
    track_user_message(session_id, message_id)
    logger.info(f"[save_message] 记录user消息ID: {message_id}, 会话: {session_id}")


@router.post("/sessions/{session_id}/messages")
@handle_api_errors("保存消息")
async def save_message(session_id: str, message: MessageCreate):
    """保存消息到会话 — 小健 2026-05-25 重构"""
    with db.get_conn("chat") as conn:
        cursor = conn.cursor()
        new_message_count = 0

        cursor.execute(
            "SELECT id, title, message_count, COALESCE(title_locked, 0) as title_locked "
            "FROM chat_sessions WHERE id = ? AND is_deleted = FALSE", (session_id,))
        session = cursor.fetchone()
        if not session:
            raise HTTPException(status_code=404, detail="会话不存在")

        local_time = get_local_iso_timestamp()
        new_message_count = session["message_count"] + 1

        display_name_to_save = message.display_name
        if message.role == "assistant" and not display_name_to_save:
            display_name_to_save = display_name_cache.get(session_id)

        execution_steps_json = safe_json_dumps(message.execution_steps) if message.execution_steps is not None else None
        cursor.execute(
            "INSERT INTO chat_messages(session_id, role, content, timestamp, display_name, execution_steps, client_os, browser, device, network) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (session_id, message.role, message.content, local_time, display_name_to_save,
             execution_steps_json, message.client_os, message.browser, message.device, message.network))
        message_id = cursor.lastrowid

        if message.role == "user":
            _track_user_message(session_id, message_id)

        cursor.execute(
            "UPDATE chat_sessions SET message_count = ?, updated_at = ? WHERE id = ?",
            (new_message_count, local_time, session_id))

        _try_mark_valid(cursor, session_id)

    return {"success": True, "message_id": message_id, "message_count": new_message_count}

