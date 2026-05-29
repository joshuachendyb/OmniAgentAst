# 会话管理API路由（会话容器CRUD）
# 编程人：小沈
# 创建时间：2026-02-17
# 更新时间：2026-05-28 - 拆分消息管理到 messages.py

"""
会话管理API路由
提供会话容器的CRUD操作
使用SQLite数据库存储会话信息

会话（session）是聊天和消息的容器空间，
会话内有多轮对话（dialogue/conversation），
每个对话对应不同的任务（task）。

消息管理操作已迁移至 messages.py
"""

import uuid
from datetime import datetime, timezone
from typing import Any, List, Optional, Tuple
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from app.utils.logger import logger
from app.utils.display_name_cache import clear_cached_display_name
from app.utils.time_utils import get_utc_timestamp, convert_to_utc
from app.db import db
from app.db.models.chat_models import (
    Session,
    SessionCreate,
    SessionResponse,
    SessionListResponse,
    BatchTitleResponse,
)

router = APIRouter()


def _build_list_where(keyword: Optional[str], is_valid: Optional[bool],
                       for_count: bool = False) -> Tuple[str, List]:
    """构建 list_sessions 的 WHERE 子句和参数，COUNT/SELECT 两用。"""
    where = "WHERE is_deleted = FALSE"
    params: List = []
    if keyword:
        where += " AND title LIKE ?"
        params.append(f"%{keyword}%")
    if is_valid is not None:
        where += " AND is_valid = ?"
        params.append(1 if is_valid else 0)
    return where, params


def _format_timestamp(val: Any) -> str:
    """统一将时间戳转换为 ISO 格式字符串。
    
    3 种类型：
    - int/float: 毫秒 → datetime.fromtimestamp(/1000) → ISO
    - str: 替换 +00:00 为 Z，或追加 Z
    - datetime/其他: convert_to_utc 兜底
    """
    if isinstance(val, (int, float)):
        return datetime.fromtimestamp(val / 1000, timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f') + 'Z'
    if isinstance(val, str):
        return val.replace('+00:00', 'Z') if '+00:00' in val else (val + 'Z' if not val.endswith('Z') else val)
    return convert_to_utc(val)


# ============== API接口 ==============

@router.post("/sessions", response_model=SessionResponse)
async def create_session(session_create: Optional[SessionCreate] = None):
    """
    创建新会话
    
    优化内容：
    1. 初始化`title_locked = False` - 新会话标题默认未锁定，允许自动更新
    2. 设置`title_updated_at = 创建时间` - 记录标题最后更新时间
    3. 初始化`version = 1` - 用于乐观锁版本控制
    
    Args:
        session_create: 会话创建请求（可选）
        
    Returns:
        SessionResponse: 创建的会话信息
    """
    try:
        session_id = str(uuid.uuid4())
        
        # 如果没有提供标题，自动生成
        title = session_create.title if session_create and session_create.title else f"新会话 {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        
        utc_time = get_utc_timestamp()
        
        # 【小沈修改 2026-03-03】新创建的会话默认is_valid=FALSE
        # 只有在首次保存消息后，才会自动设置为TRUE
        # 【小沈修复 2026-03-04】尊重前端传入的is_valid参数
        is_valid = session_create.is_valid if session_create and session_create.is_valid is not None else False
        
        with db.get_conn("chat") as conn:
            cursor = conn.cursor()
            
            cursor.execute(
                '''INSERT INTO chat_sessions 
                   (id, title, created_at, updated_at, title_locked, title_updated_at, version, is_valid) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                (session_id, title, utc_time, utc_time, False, utc_time, 1, is_valid)
            )
            logger.info(f"创建会话（使用新字段）: id={session_id}, title={title}, is_valid={is_valid}")
        
        logger.info(f"创建会话成功: id={session_id}, title={title}")
        
        return SessionResponse(
            session_id=session_id,
            title=title,
            created_at=utc_time,
            updated_at=utc_time,
            message_count=0,
            is_valid=is_valid
        )
        
    except Exception as e:
        logger.error(f"创建会话失败: {e}")
        raise HTTPException(status_code=500, detail=f"创建会话失败: {str(e)}")


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: Optional[str] = Query(None),
    is_valid: Optional[bool] = Query(None)
):
    try:
        with db.get_conn("chat") as conn:
            cursor = conn.cursor()

            # C1: COUNT — 复用 _build_list_where
            where, params = _build_list_where(keyword, is_valid, for_count=True)
            cursor.execute(f"SELECT COUNT(*) FROM chat_sessions {where}", params)
            total = cursor.fetchone()[0]

            # S1: SELECT — 复用同一 _build_list_where
            where, params = _build_list_where(keyword, is_valid, for_count=False)
            offset = (page - 1) * page_size
            cursor.execute(
                f"SELECT id, title, created_at, updated_at, message_count, is_valid "
                f"FROM chat_sessions {where} ORDER BY updated_at DESC, created_at DESC "
                f"LIMIT ? OFFSET ?",
                params + [page_size, offset]
            )
            rows = cursor.fetchall()

        # O1: 结果映射 — 复用 _format_timestamp
        sessions = [
            SessionResponse(
                session_id=row['id'],
                title=row['title'],
                created_at=_format_timestamp(row['created_at']),
                updated_at=_format_timestamp(row['updated_at']),
                message_count=row['message_count'],
                is_valid=row['is_valid']
            )
            for row in rows
        ]

        logger.info(f"获取会话列表: page={page}, page_size={page_size}, "
                     f"keyword={keyword}, count={len(sessions)}")
        return SessionListResponse(total=total, page=page, page_size=page_size, sessions=sessions)

    except Exception as e:
        logger.error(f"获取会话列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取会话列表失败: {str(e)}")


class SessionUpdate(BaseModel):
    """会话更新请求"""
    title: Optional[str] = Field(None, description="会话标题", min_length=1, max_length=200)
    version: Optional[int] = Field(None, ge=1, description="乐观锁版本号")
    updated_by: Optional[str] = Field(None, description="修改者")





def _get_sql_mode(mode: str) -> str:
    """将外层mode映射为_build_update_sql所需的sql_mode"""
    if mode == "optimistic":
        return "optimistic"
    return "legacy"


def _resolve_update_mode(
    update_data: SessionUpdate,
    cursor, session_id: str, utc_time: str,
) -> Tuple[str, str, Tuple]:
    """判断UPDATE模式"""
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


def _build_update_params(
    mode: str, update_data: SessionUpdate,
    utc_time: str, session_id: str,
) -> tuple:
    """根据模式构建UPDATE SQL的参数元组"""
    if mode == "optimistic":
        return (update_data.title, utc_time, 1, utc_time, session_id, update_data.version)
    return (update_data.title, utc_time, 1, utc_time, session_id)


def _build_update_sql(mode: str) -> Tuple[str, str]:
    """根据模式构建SET子句和version WHERE子句"""
    base_set = "title = ?, updated_at = ?"
    if mode == "optimistic":
        return (
            f"SET {base_set}, title_locked = ?, title_updated_at = ?, version = version + 1",
            "AND is_deleted = FALSE AND version = ?",
        )
    return f"SET {base_set}, title_locked = ?, title_updated_at = ?, version = version + 1", "AND is_deleted = FALSE"





_TITLE_HISTORY_TABLE_EXISTS: Optional[bool] = None


def _record_title_history(
    cursor, session_id: str, old_title: Optional[str],
    utc_time: str, updated_by: str = "user",
):
    """记录标题变更历史，首次探测DDL后缓存结果

    使用场景: update_session中插入chat_session_title_history
    使用示例: _record_title_history(cursor, sid, "旧标题", utc_time, "user")
    返回数据说明: 无返回，直接执行INSERT

    @author 小健 2026-05-25
    """
    global _TITLE_HISTORY_TABLE_EXISTS
    if _TITLE_HISTORY_TABLE_EXISTS is None:
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='chat_session_title_history'"
        )
        _TITLE_HISTORY_TABLE_EXISTS = cursor.fetchone() is not None
    if _TITLE_HISTORY_TABLE_EXISTS and old_title:
        cursor.execute(
            """INSERT INTO chat_session_title_history
               (session_id, title, created_at, updated_by, change_reason)
               VALUES (?, ?, ?, ?, ?)""",
            (session_id, old_title, utc_time, updated_by, "user_edit"),
        )
        logger.info(f"记录标题历史: session_id={session_id}, old_title={old_title}")


@router.put("/sessions/{session_id}")
async def update_session(session_id: str, update_data: SessionUpdate):
    """更新会话标题（乐观锁+标题历史）

    重构：189行→≤60行骨架+_build_update_sql+_raise_session_error+_record_title_history
    @author 小沈, 小健 2026-05-25
    """
    try:
        with db.get_conn("chat") as conn:
            cursor = conn.cursor()
            cursor.execute("BEGIN")
            logger.debug(f"开始事务: session_id={session_id}, operation=update_title")
            utc_time = get_utc_timestamp()
            mode, _, params = _resolve_update_mode(update_data, cursor, session_id, utc_time)
            if mode == "not_found":
                raise HTTPException(status_code=404, detail=f"会话不存在: {session_id}")
            sql_mode = _get_sql_mode(mode)
            set_clause, where_clause = _build_update_sql(sql_mode)
            update_params = _build_update_params(sql_mode, update_data, utc_time, session_id)
            cursor.execute(f"UPDATE chat_sessions {set_clause} WHERE id = ? {where_clause}", update_params)
            if mode == "optimistic":
                if cursor.rowcount == 0:
                    logger.warning(f"版本冲突: session_id={session_id}, client_version={update_data.version}")
                    raise HTTPException(status_code=409, detail="会话已被其他用户修改，请刷新后重试")
                cursor.execute("SELECT id, title, version FROM chat_sessions WHERE id = ?", (session_id,))
                session = cursor.fetchone()
                current_version = session["version"]
            else:
                session, current_version = params
            old_title = session["title"] if session else ""
            new_version = current_version + 1
            _record_title_history(cursor, session_id, old_title, utc_time, update_data.updated_by or "user")
            cursor.execute("COMMIT")
        logger.info(f"更新会话成功: id={session_id}, title={update_data.title}, version={new_version}")
        return {"success": True, "title": update_data.title, "version": new_version}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新会话失败: session_id={session_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="更新会话失败，请重试")


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """
    删除会话（软删除）
    
    Args:
        session_id: 会话ID
        
    Returns:
        dict: 删除结果
    """
    try:
        with db.get_conn("chat") as conn:
            cursor = conn.cursor()
            
            # 验证会话存在
            cursor.execute(
                'SELECT id FROM chat_sessions WHERE id = ? AND is_deleted = FALSE',
                (session_id,)
            )
            session = cursor.fetchone()
            
            if not session:
                raise HTTPException(status_code=404, detail=f"会话不存在: {session_id}")
            
            # 软删除
            utc_time = get_utc_timestamp()
            cursor.execute(
                'UPDATE chat_sessions SET is_deleted = TRUE, updated_at = ? WHERE id = ?',
                (utc_time, session_id)
            )
        
        # ⭐ 【小健添加 2026-03-04】删除会话时同时清除缓存
        clear_cached_display_name(session_id)
        
        logger.info(f"删除会话成功: id={session_id}")
        
        return {"success": True, "message": "会话删除成功"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除会话失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除会话失败: {str(e)}")

@router.get("/sessions/titles/batch", response_model=BatchTitleResponse)
async def get_session_titles_batch(
    session_ids: str = Query(..., description="逗号分隔的会话ID列表")
):
    """
    批量获取会话标题状态（12.1.3节新增接口）
    
    功能：一次性获取多个会话的标题信息，包括锁定状态和更新时间
    优势：减少API调用次数，提升性能
    
    Args:
        session_ids: 逗号分隔的会话ID列表，例如：id1,id2,id3
        
    Returns:
        BatchTitleResponse: 包含所有会话标题信息的响应
        
    示例：
        GET /api/v1/sessions/titles/batch?session_ids=uuid1,uuid2,uuid3
        
        响应：
        {
            "sessions": [
                {
                    "session_id": "uuid1",
                    "title": "会话标题1",
                    "title_locked": true,
                    "title_updated_at": "2026-02-25T10:30:00Z"
                },
                ...
            ]
        }
    """
    try:
        # 解析会话ID列表
        id_list = [sid.strip() for sid in session_ids.split(',') if sid.strip()]

        if not id_list:
            raise HTTPException(status_code=400, detail="会话ID列表不能为空")

        if len(id_list) > 100:
            raise HTTPException(status_code=400, detail="最多一次查询100个会话")

        with db.get_conn("chat") as conn:
            cursor = conn.cursor()
            
            # P0风险缓解：检查数据库字段是否存在
            fields_exist = db.check_fields("chat_sessions", ["title_locked", "title_updated_at"])
            
            # 构建查询SQL
            # 使用IN子句批量查询
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
        
        # 构建响应
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
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"批量获取会话标题失败: {e}")
        raise HTTPException(status_code=500, detail=f"批量获取会话标题失败: {str(e)}")
