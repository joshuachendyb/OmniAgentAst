# -*- coding: utf-8 -*-
"""
sessions — merged from sessions/ 7 files
COPY — 小欧 2026-07-10
"""

from typing import Optional, Any, Dict, List, Tuple
import uuid

from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Query

from app.utils.logger import logger
from app.utils.response_utils import handle_api_errors
from app.utils.time_utils import get_utc_timestamp, now_str, format_timestamp, convert_to_utc
from app.db import db
from app.db.models.chat_models import SessionCreate, SessionResponse, SessionListResponse, BatchTitleResponse
from app.api.v1.messages import display_name_cache
from app.services.conversation_storage import save_execution_steps

router = APIRouter()

# ===== models =====

class ExecutionStep:
    """执行步骤数据模型"""
    def __init__(self, step_type: str, content: str = "", tool: str = "",
                 params: Optional[Dict] = None, result: Any = None, timestamp: int = 0):
        self.type = step_type
        self.content = content
        self.tool = tool
        self.params = params or {}
        self.result = result
        self.timestamp = timestamp

    def to_dict(self):
        data = {"type": self.type, "timestamp": self.timestamp}
        if self.content:
            data["content"] = self.content
        if self.tool:
            data["tool"] = self.tool
            data["params"] = self.params
        if self.result is not None:
            data["result"] = self.result
        return data


class ExecutionStepsUpdate(BaseModel):
    """执行步骤更新请求体"""
    execution_steps: Optional[list] = Field(None, description="执行步骤详情列表")
    content: Optional[str] = Field(None, description="AI生成的文本内容")
    reply_to_message_id: Optional[int] = Field(None, description="回复的用户消息ID")

# ===== create_session =====

@handle_api_errors("创建会话")
async def create_session(session_create: Optional[SessionCreate] = None):
    """拷贝自 sessions.py 第70-122行"""
    session_id = str(uuid.uuid4())
    title = session_create.title if session_create and session_create.title else f"新会话 {now_str('%Y-%m-%d %H:%M')}"
    utc_time = get_utc_timestamp()
    is_valid = session_create.is_valid if session_create and session_create.is_valid is not None else False

    with db.get_conn("chat") as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''INSERT INTO chat_sessions
               (id, title, created_at, updated_at, title_locked, title_updated_at, version, is_valid)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            (session_id, title, utc_time, utc_time, False, utc_time, 1, is_valid)
        )

    logger.info(f"创建会话成功: id={session_id}, title={title}, is_valid={is_valid}")

    return SessionResponse(
        session_id=session_id,
        title=title,
        created_at=utc_time,
        updated_at=utc_time,
        message_count=0,
        is_valid=is_valid
    )

# ===== list_sessions =====

def build_list_where(keyword: Optional[str], is_valid: Optional[bool],
                     for_count: bool = False) -> Tuple[str, List]:
    """拷贝自 sessions.py 第38-49行"""
    where = "WHERE is_deleted = FALSE"
    params: List = []
    if keyword:
        where += " AND title LIKE ?"
        params.append(f"%{keyword}%")
    if is_valid is not None:
        where += " AND is_valid = ?"
        params.append(1 if is_valid else 0)
    return where, params


@handle_api_errors("获取会话列表")
async def list_sessions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: Optional[str] = Query(None),
    is_valid: Optional[bool] = Query(None)
):
    """拷贝自 sessions.py 第126-171行"""
    with db.get_conn("chat") as conn:
        cursor = conn.cursor()

        where, params = build_list_where(keyword, is_valid, for_count=True)
        cursor.execute(f"SELECT COUNT(*) FROM chat_sessions {where}", params)
        total = cursor.fetchone()[0]

        where, params = build_list_where(keyword, is_valid, for_count=False)
        offset = (page - 1) * page_size
        cursor.execute(
            f"SELECT id, title, created_at, updated_at, message_count, is_valid "
            f"FROM chat_sessions {where} ORDER BY updated_at DESC, created_at DESC "
            f"LIMIT ? OFFSET ?",
            params + [page_size, offset]
        )
        rows = cursor.fetchall()

    sessions = [
        SessionResponse(
            session_id=row['id'],
            title=row['title'],
            created_at=format_timestamp(row['created_at']),
            updated_at=format_timestamp(row['updated_at']),
            message_count=row['message_count'],
            is_valid=row['is_valid']
        )
        for row in rows
    ]

    logger.info(f"获取会话列表: page={page}, page_size={page_size}, "
                 f"keyword={keyword}, count={len(sessions)}")
    return SessionListResponse(total=total, page=page, page_size=page_size, sessions=sessions)

# ===== update_session =====

class SessionUpdate(BaseModel):
    """会话更新请求 — 小沈 2026-02-17"""
    title: Optional[str] = Field(None, description="会话标题", min_length=1, max_length=200)
    version: Optional[int] = Field(None, ge=1, description="乐观锁版本号")
    updated_by: Optional[str] = Field(None, description="修改者")


def resolve_update_mode(
    update_data: SessionUpdate,
    cursor, session_id: str, utc_time: str,
) -> Tuple[str, str, tuple]:
    """拷贝自 sessions.py 第184-200行"""
    if update_data.version is not None:
        return "optimistic", "", ()
    cursor.execute(
        """SELECT id, title, COALESCE(version, 1) as version,
                  COALESCE(title_locked, 0) as title_locked
           FROM chat_sessions WHERE id = ? AND is_deleted = FALSE""",
        (session_id,),
    )
    session = cursor.fetchone()
    if not session:
        return "not_found", "", (None, 0)
    return "select_then_update", "", (session, session["version"])


def build_update_sql(mode: str) -> Tuple[str, str]:
    """拷贝自 sessions.py 第213-221行 — 小健 2026-06-18 DRY提取公共SET子句"""
    base_set = "title = ?, updated_at = ?"
    extra_set = "title_locked = ?, title_updated_at = ?, version = version + 1"
    set_clause = f"SET {base_set}, {extra_set}"
    where_clause = "AND is_deleted = FALSE"

    if mode == "optimistic":
        where_clause += " AND version = ?"

    return (set_clause, where_clause)


def build_update_params(
    mode: str, update_data: SessionUpdate,
    utc_time: str, session_id: str,
) -> tuple:
    """拷贝自 sessions.py 第203-210行"""
    if mode == "optimistic":
        return (update_data.title, utc_time, 1, utc_time, session_id, update_data.version)
    return (update_data.title, utc_time, 1, utc_time, session_id)


def record_title_history(
    cursor, session_id: str, old_title: Optional[str],
    utc_time: str, updated_by: str = "user",
):
    """拷贝自 sessions.py 第230-255行 — 小健2026-05-31 改用try/except消除全局状态"""
    if not old_title:
        return
    try:
        cursor.execute(
            """INSERT INTO chat_session_title_history
               (session_id, title, created_at, updated_by, change_reason)
               VALUES (?, ?, ?, ?, ?)""",
            (session_id, old_title, utc_time, updated_by, "user_edit"),
        )
        logger.info(f"记录标题历史: session_id={session_id}, old_title={old_title}")
    except Exception:
        logger.debug("chat_session_title_history表不存在,跳过标题历史记录")


async def update_session(session_id: str, update_data: SessionUpdate):
    """拷贝自 sessions.py 第259-296行 — 小欧 2026-06-22 空body返回400"""
    if not update_data.title:
        raise HTTPException(status_code=400, detail="标题不能为空")
    try:
        with db.get_conn("chat") as conn:
            cursor = conn.cursor()
            cursor.execute("BEGIN")
            logger.debug(f"开始事务: session_id={session_id}, operation=update_title")
            utc_time = get_utc_timestamp()
            mode, _, params = resolve_update_mode(update_data, cursor, session_id, utc_time)
            if mode == "not_found":
                raise HTTPException(status_code=404, detail=f"会话不存在: {session_id}")
            set_clause, where_clause = build_update_sql(mode)
            update_params = build_update_params(mode, update_data, utc_time, session_id)
            cursor.execute(f"UPDATE chat_sessions {set_clause} WHERE id = ? {where_clause}", update_params)
            if mode == "optimistic":
                if cursor.rowcount == 0:
                    logger.warning(f"版本冲突: session_id={session_id}, client_version={update_data.version}")
                    raise HTTPException(status_code=409, detail="会话已被其他用户修改,请刷新后重试")
                cursor.execute("SELECT id, title, version FROM chat_sessions WHERE id = ?", (session_id,))
                session = cursor.fetchone()
                current_version = session["version"]
            else:
                session, current_version = params
            old_title = session["title"] if session else ""
            new_version = current_version + 1
            record_title_history(cursor, session_id, old_title, utc_time, update_data.updated_by or "user")
            cursor.execute("COMMIT")
        logger.info(f"更新会话成功: id={session_id}, title={update_data.title}, version={new_version}")
        return {"success": True, "title": update_data.title, "version": new_version}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新会话失败: session_id={session_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="更新会话失败,请重试")

# ===== get_session_titles_batch =====

@handle_api_errors("批量获取会话标题")
async def get_session_titles_batch(
    session_ids: str = Query(..., description="逗号分隔的会话ID列表")
):
    """拷贝自 sessions.py 第345-421行"""
    id_list = [sid.strip() for sid in session_ids.split(',') if sid.strip()]

    if not id_list:
        raise HTTPException(status_code=400, detail="会话ID列表不能为空")

    if len(id_list) > 100:
        raise HTTPException(status_code=400, detail="最多一次查询100个会话")

    with db.get_conn("chat") as conn:
        cursor = conn.cursor()
        placeholders = ','.join(['?' for _ in id_list])
        cursor.execute(
            f'''SELECT id, title,
                     COALESCE(title_locked, 0) as title_locked,
                     COALESCE(title_updated_at, created_at) as title_updated_at
                FROM chat_sessions
                WHERE id IN ({placeholders}) AND is_deleted = FALSE''',
            id_list
        )
        rows = cursor.fetchall()

    sessions = []
    for row in rows:
        sessions.append({
            "session_id": row['id'],
            "title": row['title'],
            "title_locked": bool(row['title_locked']),
            "title_updated_at": convert_to_utc(row['title_updated_at'])
        })

    logger.info(f"批量获取会话标题: count={len(sessions)}, session_ids={session_ids}")
    return BatchTitleResponse(sessions=sessions)

# ===== routes =====

@handle_api_errors("删除会话")
async def delete_session(session_id: str):
    """拷贝自 sessions.py 第300-342行"""
    with db.get_conn("chat") as conn:
        cursor = conn.cursor()
        cursor.execute(
            'SELECT id FROM chat_sessions WHERE id = ? AND is_deleted = FALSE',
            (session_id,)
        )
        session = cursor.fetchone()
        if not session:
            raise HTTPException(status_code=404, detail=f"会话不存在: {session_id}")
        utc_time = get_utc_timestamp()
        cursor.execute(
            'UPDATE chat_sessions SET is_deleted = TRUE, updated_at = ? WHERE id = ?',
            (utc_time, session_id)
        )

    display_name_cache.delete(session_id)
    logger.info(f"删除会话成功: id={session_id}")
    return {"success": True, "message": "会话删除成功"}


@router.post("/sessions")
async def create_session_endpoint(session_create: Optional[SessionCreate] = None):
    return await create_session(session_create)


@router.get("/sessions")
async def list_sessions_endpoint(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: Optional[str] = Query(None),
    is_valid: Optional[bool] = Query(None)
):
    return await list_sessions(page, page_size, keyword, is_valid)


@router.put("/sessions/{session_id}")
async def update_session_endpoint(session_id: str, update_data: SessionUpdate):
    return await update_session(session_id, update_data)


@router.delete("/sessions/{session_id}")
async def delete_session_endpoint(session_id: str):
    return await delete_session(session_id)


@router.get("/sessions/titles/batch")
async def get_session_titles_batch_endpoint(
    session_ids: str = Query(..., description="逗号分隔的会话ID列表")
):
    return await get_session_titles_batch(session_ids)


@router.post("/sessions/{session_id}/execution_steps")
async def save_execution_steps_endpoint(session_id: str, update_data: ExecutionStepsUpdate):
    return await save_execution_steps(session_id, update_data)