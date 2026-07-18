# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-14 - 小欧 - 新增allocate_and_insert_message/append_execution_step/load_execution_steps/finalize_message四函数,支撑运行期逐步落库+渐进耐久
# 2026-07-14 - 小欧 - 修复load_execution_steps: 无步骤且无legacy blob时返回[]而非None,避免API返回execution_steps=None
# 2026-07-18 - 小欧 - FinalStep多态自包含终态重构: derive_status_from_steps改为读最后一条final.outcome
#   【病根】原derive_status_from_steps基于type推断终态(cancelled→cancelled, error→failed),
#          与FinalStep多态设计不一致; 且type=final始终返回completed, 无法区分failed终态。
#   【改法】改为遍历找最后一条type=final, 读其outcome字段返回; 无final时兜底返回completed。
# 2026-07-18 - 小欧 - create_timestamp→get_utc_timestamp() (3处); append_execution_step 补 created_at 入库
# 2026-07-18 - 小欧 - 修复#1空步骤谎报完成: derive_status_from_steps 空/无final步默认"failed"(fail-safe, 对齐agent_runner兜底); 修复#6拼写错 ccancelled→cancelled
"""
storage — 会话存储业务逻辑
从 conversation_storage.py 移入
小欧 2026-07-10
"""

import threading
from typing import Dict, Optional, Tuple
from sqlite3 import Connection

from fastapi import HTTPException
from pydantic import BaseModel, Field

from app.logger import logger
from app.db import db
from app.utils.json_utils import safe_json_dumps, parse_json
from app.utils.time_utils import get_utc_timestamp  # 小欧 2026-07-18 时间统一入库 UTC Z
from app.utils.display_utils import extract_metadata_from_steps

# 存储每个session的消息ID
# key: session_id, value: user_message_id 或 assistant_message_id
_user_message_ids: Dict[str, int] = {}
_message_ids_lock = threading.Lock()


def track_user_message(session_id: str, message_id: int):
    """记录用户消息ID"""
    with _message_ids_lock:
        _user_message_ids[session_id] = message_id


def get_user_message_id(session_id: str) -> Optional[int]:
    """获取用户消息ID"""
    return _user_message_ids.get(session_id)


class ExecutionStepsUpdate(BaseModel):
    """执行步骤更新请求体 — 小欧 2026-07-10"""
    execution_steps: Optional[list] = Field(None, description="执行步骤详情列表")
    content: Optional[str] = Field(None, description="AI生成的文本内容")
    reply_to_message_id: Optional[int] = Field(None, description="回复的用户消息ID")
    status: Optional[str] = Field(None, description="任务终态: completed/failed/cancelled/paused — 小欧 2026-07-13")


def derive_status_from_steps(steps: Optional[list]) -> str:
    """从 execution_steps 推导任务终态(status列兜底) — 小欧 2026-07-13 初版
    2026-07-18 小欧 重构: 读最后一条 final.outcome(显式声明终态结果),
    无向后/旧数据兼容(用户: 旧数据不合适可删除或清库)。
    失败默认"failed"(fail-safe, 与 agent_runner 终态兜底一致): 空步骤/无终态步一律判失败,
    杜绝"空步骤谎报完成"。— 北京老陈 2026-07-18"""
    if not steps:
        return "failed"
    last_final = None
    for s in steps:
        if isinstance(s, dict) and s.get("type") == "final":
            last_final = s
    return last_final.get("outcome", "failed") if last_final else "failed"


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
    utc_time = get_utc_timestamp()
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
    if getattr(update_data, "status", None) is not None:
        fields.append("status = ?")
        values.append(update_data.status)
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
    utc_time = get_utc_timestamp()
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


# ====================================================================
# 独立步骤表操作 — 小欧 2026-07-14
# ====================================================================

def allocate_and_insert_message(conn: Connection, session_id: str) -> int:
    """预分配 assistant 消息ID + 插入空白行 — 小欧 2026-07-14"""
    ai_message_id, is_new = _allocator.allocate(session_id, conn)
    if is_new:
        utc_time = get_utc_timestamp()
        conn.execute(
            "INSERT INTO chat_messages(id, session_id, role, content, timestamp) "
            "VALUES (?, ?, 'assistant', ?, ?)",
            (ai_message_id, session_id, "", utc_time),
        )
    conn.execute(
        "UPDATE chat_sessions SET message_count=message_count+1, updated_at=? WHERE id=?",
        (utc_time, session_id),
    )
    return ai_message_id


def append_execution_step(conn: Connection, message_id: int, session_id: str,
                          step_index: int, step_dict: dict) -> None:
    """运行期逐步落库 — 小欧 2026-07-14"""
    conn.execute(
        "INSERT INTO chat_message_steps(message_id, session_id, step_index, step_json, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (message_id, session_id, step_index, safe_json_dumps(step_dict), get_utc_timestamp()),
    )


def load_execution_steps(conn: Connection, message_id: int) -> Optional[list]:
    """从 chat_message_steps 表组装步骤列表,无数据时从chat_messages.execution_steps列读取 — 小欧 2026-07-14"""
    rows = conn.execute(
        "SELECT step_json FROM chat_message_steps WHERE message_id=? ORDER BY step_index ASC",
        (message_id,),
    ).fetchall()
    if rows:
        return [parse_json(r["step_json"], label="step_json") for r in rows]
    row = conn.execute(
        "SELECT execution_steps FROM chat_messages WHERE id=?", (message_id,),
    ).fetchone()
    if row and row["execution_steps"]:
        return parse_json(row["execution_steps"], label="execution_steps")
    return []


def finalize_message(conn: Connection, message_id: int, content: str, status: str, thought: str = "") -> None:
    """finally 轻量终态 — 小欧 2026-07-14; 2026-07-16 小欧 增 thought 持久化"""
    conn.execute(
        "UPDATE chat_messages SET content=?, status=?, thought=? WHERE id=?",
        (content, status, thought or None, message_id),
    )
