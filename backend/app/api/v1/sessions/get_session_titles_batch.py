# -*- coding: utf-8 -*-
"""
get_session_titles_batch — 从 sessions.py 拷出

拷贝来源: sessions.py 第345-421行
"""

from fastapi import APIRouter, HTTPException, Query
from app.utils.logger import logger
from app.utils.time_utils import convert_to_utc
from app.db import db
from app.db.models.chat_models import BatchTitleResponse


async def get_session_titles_batch(
    session_ids: str = Query(..., description="逗号分隔的会话ID列表")
):
    """拷贝自 sessions.py 第345-421行"""
    try:
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

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"批量获取会话标题失败: {e}")
        raise HTTPException(status_code=500, detail=f"批量获取会话标题失败: {str(e)}")
