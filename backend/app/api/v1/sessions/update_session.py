# -*- coding: utf-8 -*-
"""
update_session — 从 sessions.py 拷出

拷贝来源: sessions.py 第259-296行
"""

from typing import Tuple, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.utils.logger import logger
from app.utils.time_utils import get_utc_timestamp
from app.db import db


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
