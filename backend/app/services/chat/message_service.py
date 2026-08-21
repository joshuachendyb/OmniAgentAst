# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-13 - 小欧 - 新建: A7 消息业务服务(方案4.7.3步骤3)。从 api/v1/messages.py 复制 get_session_messages/save_message
#   + display_name_cache(缓存归本服务独占), 仅改导入归属, 业务逻辑一字不改; 新增 delete_session_display_names 供
#   session_service 删除会话时联动清理(经方法调用, 不直接 import 本服务缓存对象, 单向方法调用)。API 层薄壳化改调本服务。
# 2026-08-19 - 小欧 - v2.0核心数据模型重构(9.3+9.6): save_message删除execution_steps列写入;
#   user消息同步写chat_user_message(user_message_id=cursor.lastrowid一对一贯通, 根除两套自增id错位P0-2);
#   合并重复的 if role=="user" 判断块(DRY, 三堂会审Bug#9)
# 2026-08-21 - 小欧 - 12.2-Q6-D1(按文档[1]12.2 diff设计落地): chat_sessions.message_count 绝对值覆盖→SQL自增
#   (message_count + 1), 与 storage.py allocate 路径同口径, 消除并发写入丢计数; new_message_count 保留供返回值
"""
message_service — 消息业务服务(services/chat)

职责(方案4.7.3, 小欧 2026-08-13): 会话消息历史读取/保存 + display_name 缓存(独占)。
API 层仅路由薄壳 + DTO, 业务逻辑单一归属本服务(SRP)。
"""
import json
from typing import Optional

from app.logger import logger
from app.utils.json_utils import safe_json_dumps, parse_json
from app.utils.cache import LRUCache
from app.constants import MAX_CACHE_SIZE
from app.utils.display_utils import extract_display_name_from_steps
from app.utils.time_utils import ensure_timestamp_milliseconds, get_local_iso_timestamp, to_local_iso, format_timestamp  # 小欧 2026-08-08 全程统一本地时区
from app.db import db
from app.db.models.chat_models import MessageResponse
from app.services.chat.storage import track_user_message, get_user_message_id, load_execution_steps
from app.services.chat.storage import insert_user_message  # v2.0 改动2: user消息同步写chat_user_message — 小欧 2026-08-19


# 消息模块共享的 display_name 缓存(A7 迁移边界: 归 message_service 独占) — 小欧 2026-08-13
display_name_cache = LRUCache(max_size=MAX_CACHE_SIZE)


def delete_session_display_names(session_id: str) -> None:
    """联动清理: session_service 删除会话时调用, 防止 session_service 直接 import 本服务缓存对象 — 小欧 2026-08-13"""
    display_name_cache.delete(session_id)


def get_session_messages(session_id: str):
    """获取会话消息历史(21.3 重构,小沈 2026-05-25 实施) — 自 api/v1/messages.py 迁入"""
    from fastapi import HTTPException
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
            # 从 chat_task_steps 表读取步骤列表 — 小欧 2026-07-14; v2.0 表改名 chat_task_steps — 2026-08-19
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


def save_message(session_id: str, message):
    """保存消息到会话 — 小健 2026-05-25 重构 — 自 api/v1/messages.py 迁入"""
    from fastapi import HTTPException
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

        cursor.execute(
            "INSERT INTO chat_messages(session_id, role, content, timestamp, display_name, client_os, browser, device, network) VALUES(?,?,?,?,?,?,?,?,?)",
            (session_id, message.role, message.content, local_time, display_name_to_save,
             message.client_os, message.browser, message.device, message.network))
        message_id = cursor.lastrowid

        # v2.0 改动2: user消息同步写chat_user_message — 小欧 2026-08-19
        # 关键：chat_user_message.id 显式取 chat_messages.id（一对一贯通），根除两套自增id错位 — 小健 2026-08-19 三堂会审P0-2
        if message.role == "user":
            try:
                insert_user_message(
                    conn,
                    user_message_id=message_id,
                    session_id=session_id,
                    content=message.content,
                    client_os=message.client_os,
                    browser=message.browser,
                    device=message.device,
                    network=message.network,
                )
            except Exception as _um_e:
                logger.warning(f"[save_message] 写chat_user_message失败(session={session_id}): {_um_e}")
            _track_user_message(session_id, message_id)

        # 12.2-Q6附带修复: 绝对值覆盖→SQL自增(与storage.py:297 allocate路径同口径), 消除并发丢计数 — 小欧 2026-08-21
        cursor.execute(
            "UPDATE chat_sessions SET message_count = message_count + 1, updated_at = ? WHERE id = ?",
            (local_time, session_id))

        _try_mark_valid(cursor, session_id)

    return {"success": True, "message_id": message_id, "message_count": new_message_count}