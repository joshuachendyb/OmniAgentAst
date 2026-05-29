# 消息管理API路由（单条消息 CRUD）
# 编程人：小沈
# 创建时间：2026-05-28

"""
消息管理API路由

管理会话内单条消息（一问一答）：
1. 获取会话消息历史 - GET /sessions/{session_id}/messages
2. 保存消息 - POST /sessions/{session_id}/messages

对话/任务回合管理（含 execution_steps）已迁移至 conversation.py
"""

import json
import threading
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.utils.logger import logger
from app.utils.display_name_cache import get_cached_display_name
from app.utils.time_utils import convert_to_utc, ensure_timestamp_milliseconds, get_timestamp_ms
from app.utils.data_utils import parse_json
from app.db import db
from app.db.models.chat_models import MessageResponse

# 存储每个session的消息ID
# key: session_id, value: user_message_id 或 assistant_message_id
_user_message_ids: dict = {}
_assistant_message_ids: dict = {}
_message_ids_lock = threading.Lock()

router = APIRouter()


def extract_display_name_from_steps(execution_steps_data: list) -> Optional[str]:
    """
    从 execution_steps 中提取 display_name 信息
    用于兼容早期保存的历史消息（当时没有单独存储 display_name）

    @author 小新
    @update 2026-03-07 修复历史消息 display_name 不显示的问题
    """
    if not execution_steps_data:
        return None

    for step in execution_steps_data:
        if isinstance(step, dict):
            if step.get("type") in ["start", "chunk", "final"]:
                model = step.get("model", "")
                provider = step.get("provider", "")
                if model or provider:
                    if provider and model:
                        return f"{provider} ({model})"
                    elif model:
                        return model
                    elif provider:
                        return provider
    return None


@router.get("/sessions/{session_id}/messages")
async def get_session_messages(session_id: str):
    """获取会话消息历史（21.3 重构，小沈 2026-05-25 实施）"""
    try:
        with db.get_conn("chat") as conn:
            cursor = conn.cursor()

            fields_exist = db.check_fields("chat_sessions", ["title_locked", "title_updated_at", "version", "is_valid"])

            if fields_exist['title_locked'] and fields_exist['title_updated_at'] and fields_exist['version']:
                cursor.execute('''SELECT id, title, COALESCE(title_locked, 0) as title_locked,
                                  COALESCE(title_updated_at, created_at) as title_updated_at,
                                  COALESCE(version, 1) as version, COALESCE(is_valid, 1) as is_valid
                               FROM chat_sessions WHERE id = ? AND is_deleted = FALSE''', (session_id,))
            else:
                cursor.execute('''SELECT id, title, 0 as title_locked, created_at as title_updated_at,
                                   1 as version, 1 as is_valid
                               FROM chat_sessions WHERE id = ? AND is_deleted = FALSE''', (session_id,))

            session = cursor.fetchone()
            if not session:
                raise HTTPException(status_code=404, detail=f"会话不存在: {session_id}")

            cursor.execute('''SELECT id, session_id, role, content, timestamp, execution_steps, display_name
                           FROM chat_messages WHERE session_id = ? ORDER BY timestamp ASC''', (session_id,))

            messages = []
            for row in cursor.fetchall():
                steps = parse_json(row['execution_steps'], label="execution_steps")
                display_name = row['display_name']
                if not display_name and steps:
                    display_name = extract_display_name_from_steps(steps)

                messages.append(MessageResponse(
                    id=row['id'], session_id=row['session_id'],
                    role=row['role'], content=row['content'],
                    timestamp=ensure_timestamp_milliseconds(row['timestamp']),
                    execution_steps=steps, display_name=display_name,
                ))

            title_locked = bool(session['title_locked'])
            return {
                "session_id": session_id, "title": session['title'],
                "title_locked": title_locked,
                "title_source": "user" if title_locked else "auto",
                "title_updated_at": convert_to_utc(session['title_updated_at']),
                "version": session['version'], "is_valid": session['is_valid'],
                "messages": messages,
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取会话消息失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取会话消息失败: {str(e)}")


class MessageCreate(BaseModel):
    """创建消息请求"""
    role: str = Field(..., description="角色：user/assistant/system")
    content: str = Field(..., description="消息内容")
    display_name: Optional[str] = Field(None, description="模型显示名称（可选，记录消息收发时使用的模型）")
    execution_steps: Optional[list] = Field(None, description="执行步骤详情列表")
    client_os: Optional[str] = Field(None, description="客户端操作系统")
    browser: Optional[str] = Field(None, description="浏览器类型")
    device: Optional[str] = Field(None, description="设备类型")
    network: Optional[str] = Field(None, description="网络类型")


def _try_mark_valid(cursor, session_id: str) -> None:
    """如果会话之前is_valid=False，尝试自愈标记为True — 小健 2026-05-25"""
    cursor.execute("SELECT is_valid FROM chat_sessions WHERE id = ?", (session_id,))
    row = cursor.fetchone()
    if row and not row[0]:
        cursor.execute("UPDATE chat_sessions SET is_valid = 1 WHERE id = ?", (session_id,))
        logger.info(f"[save_message] 会话{session_id}已自愈标记为有效")


def _track_user_message(session_id: str, message_id: str) -> None:
    """线程安全地存储user_message_id，覆盖旧值 — 小健 2026-05-25"""
    with _message_ids_lock:
        _user_message_ids[session_id] = message_id
        logger.info(f"[save_message] 记录user消息ID: {message_id}, 会话: {session_id}")


@router.post("/sessions/{session_id}/messages")
async def save_message(session_id: str, message: MessageCreate):
    """保存消息到会话 — 小健 2026-05-25 重构"""
    try:
        with db.get_conn("chat") as conn:
            cursor = conn.cursor()
            fields_exist = db.check_fields("chat_sessions", ["title_locked"])
            new_message_count = 0

            if fields_exist.get("title_locked"):
                cursor.execute(
                    "SELECT id, title, message_count, COALESCE(title_locked, 0) as title_locked "
                    "FROM chat_sessions WHERE id = ? AND is_deleted = FALSE", (session_id,))
            else:
                cursor.execute(
                    "SELECT id, title, message_count, 0 as title_locked "
                    "FROM chat_sessions WHERE id = ? AND is_deleted = FALSE", (session_id,))
            session = cursor.fetchone()
            if not session:
                raise HTTPException(status_code=404, detail="会话不存在")

            utc_time = get_timestamp_ms()
            new_message_count = session["message_count"] + 1

            display_name_to_save = message.display_name
            if message.role == "assistant" and not display_name_to_save:
                display_name_to_save = get_cached_display_name(session_id)

            execution_steps_json = json.dumps(message.execution_steps) if message.execution_steps else None
            cursor.execute(
                "INSERT INTO chat_messages(session_id, role, content, timestamp, display_name, execution_steps, client_os, browser, device, network) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (session_id, message.role, message.content, utc_time, display_name_to_save,
                 execution_steps_json, message.client_os, message.browser, message.device, message.network))
            message_id = cursor.lastrowid

            if message.role == "user":
                _track_user_message(session_id, message_id)

            cursor.execute(
                "UPDATE chat_sessions SET message_count = ?, updated_at = ? WHERE id = ?",
                (new_message_count, utc_time, session_id))

            _try_mark_valid(cursor, session_id)

        return {"success": True, "message_id": message_id, "message_count": new_message_count}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



