# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-13 - 小欧 - 新建: A7 会话业务服务(方案4.7.3步骤3)。从 api/v1/sessions.py 复制 create_session/list_sessions/
#   update_session/get_session_titles_batch/delete_session + 辅助函数(build_list_where/resolve_update_mode/build_update_sql/
#   build_update_params/record_title_history), 仅改导入归属, 业务逻辑一字不改。删除会话的 display_name 清理改为调
#   message_service.delete_session_display_names(经方法调用, 不 direct import 缓存对象, 单向方法调用)。API 层薄壳化改调本服务。
"""
session_service — 会话业务服务(services/chat)

职责(方案4.7.3, 小欧 2026-08-13): 会话 CRUD(创建/列表/更新/删除/批量标题) + 乐观锁 + 标题历史。
API 层仅路由薄壳 + DTO, 业务逻辑单一归属本服务(SRP)。
"""
from typing import Optional, List, Tuple
import uuid

from pydantic import BaseModel, Field
from fastapi import HTTPException

from app.logger import logger
from app.utils.time_utils import get_local_iso_timestamp, now_str, format_timestamp, to_local_iso  # 小欧 2026-08-08 全程统一本地时区
from app.db import db
from app.db.models.chat_models import SessionCreate, SessionResponse, SessionListResponse, BatchTitleResponse
from app.services.chat.message_service import delete_session_display_names
from app.services.chat.storage import save_execution_steps, ExecutionStepsUpdate


class SessionUpdate(BaseModel):
    """会话更新请求 — 小沈 2026-02-17"""
    title: Optional[str] = Field(None, description="会话标题", min_length=1, max_length=200)
    version: Optional[int] = Field(None, ge=1, description="乐观锁版本号")
    updated_by: Optional[str] = Field(None, description="修改者")


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


def resolve_update_mode(
    update_data: SessionUpdate,
    cursor, session_id: str, local_time: str,
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
    local_time: str, session_id: str,
) -> tuple:
    """拷贝自 sessions.py 第203-210行"""
    if mode == "optimistic":
        return (update_data.title, local_time, 1, local_time, session_id, update_data.version)
    return (update_data.title, local_time, 1, local_time, session_id)


# ===== CRUD 业务函数 =====

def create_session(session_create):
    """创建会话 — 自 api/v1/sessions.py 迁入"""
    session_id = str(uuid.uuid4())
    title = session_create.title if session_create and session_create.title else f"新会话 {now_str('%Y-%m-%d %H:%M')}"
    is_valid = session_create.is_valid if session_create and session_create.is_valid is not None else False
    local_time = get_local_iso_timestamp()

    with db.get_conn("chat") as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''INSERT INTO chat_sessions
               (id, title, created_at, updated_at, title_locked, title_updated_at, version, is_valid)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            (session_id, title, local_time, local_time, False, local_time, 1, is_valid)
        )

    logger.info(f"创建会话成功: id={session_id}, title={title}, is_valid={is_valid}")

    return SessionResponse(
        session_id=session_id,
        title=title,
        created_at=local_time,
        updated_at=local_time,
        message_count=0,
        is_valid=is_valid
    )


def list_sessions(
    page: int = 1,
    page_size: int = 20,
    keyword: Optional[str] = None,
    is_valid: Optional[bool] = None,
):
    """获取会话列表 — 自 api/v1/sessions.py 迁入"""
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


def update_session(session_id: str, update_data: SessionUpdate):
    """更新会话 — 自 api/v1/sessions.py 迁入 — 小欧 2026-06-22 空body返回400"""
    if not update_data.title:
        raise HTTPException(status_code=400, detail="标题不能为空")
    try:
        with db.get_conn("chat") as conn:
            cursor = conn.cursor()
            local_time = get_local_iso_timestamp()
            mode, _, params = resolve_update_mode(update_data, cursor, session_id, local_time)
            if mode == "not_found":
                raise HTTPException(status_code=404, detail=f"会话不存在: {session_id}")
            set_clause, where_clause = build_update_sql(mode)
            update_params = build_update_params(mode, update_data, local_time, session_id)
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
        logger.info(f"更新会话成功: id={session_id}, title={update_data.title}, version={new_version}")
        return {"success": True, "title": update_data.title, "version": new_version}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新会话失败: session_id={session_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="更新会话失败,请重试")


def delete_session(session_id: str):
    """删除会话(软删) + 清理 display_name 缓存 — 自 api/v1/sessions.py 迁入, 缓存清理改经 message_service 方法"""
    with db.get_conn("chat") as conn:
        cursor = conn.cursor()
        cursor.execute(
            'SELECT id FROM chat_sessions WHERE id = ? AND is_deleted = FALSE',
            (session_id,)
        )
        session = cursor.fetchone()
        if not session:
            raise HTTPException(status_code=404, detail=f"会话不存在: {session_id}")
        local_time = get_local_iso_timestamp()
        cursor.execute(
            'UPDATE chat_sessions SET is_deleted = TRUE, updated_at = ? WHERE id = ?',
            (local_time, session_id)
        )

    delete_session_display_names(session_id)
    logger.info(f"删除会话成功: id={session_id}")
    return {"success": True, "message": "会话删除成功"}


def get_session_titles_batch(session_ids: str):
    """批量获取会话标题 — 自 api/v1/sessions.py 迁入"""
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
            "title_updated_at": to_local_iso(row['title_updated_at'])
        })

    logger.info(f"批量获取会话标题: count={len(sessions)}, session_ids={session_ids}")
    return BatchTitleResponse(sessions=sessions)