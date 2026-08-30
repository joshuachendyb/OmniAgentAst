# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-18 - 小欧 - #23 fix: 删手动BEGIN/COMMIT，归属get_conn事务管理
# 2026-08-08 - 小欧 - 全程统一本地时区: 3处写入改 get_local_iso_timestamp; title_updated_at 输出改 to_local_iso(不再转UTC)
# 2026-08-13 - 小欧 - A7(方案4.7.3步骤3): 业务逻辑(create/list/update/delete/titles_batch + 辅助函数)迁入
#   services/chat/session_service.py; 删除会话的 display_name 缓存清理改经 message_service.delete_session_display_names
#   (不再 direct import messages 缓存对象)。本文件降为路由薄壳(DTO+路由+调service)。
# 2026-08-20 - 小欧 - 10.5 问题4/6 三堂会审落地: 新增 GET /sessions/{id}/tasks(B1会话任务列表+任务数=用户消息数) +
#   GET /sessions/{id}/trust(D1信任清单) + DELETE /sessions/{id}/trust/{tool}(D3撤销信任)。
# 2026-08-26 - 小欧 - D-2(文档2 8.D): 新增 GET /sessions/{session_id} 单会话信息路由(调 session_service.get_session_info),
#   使用场景: 设置界面读取会话级信息(title/created_at/updated_at/sessionModel) + 顶栏创建/更新时间悬浮数据源。
#   路由置于文件末尾(防御性习惯; 本路由与 /titles/batch、/{id}/tasks 等子路径段数不同, 实际无遮蔽关系)。
# 2026-08-30 - 小欧 - 设计文档[2]第十二章 v1.103: B1 响应新增 latest_task_id(最新任务显式锚点, 配合 storage.list_session_tasks 三元组返回解包, 排序一义后顶栏锚点不依赖 DESC 首行)。
"""
sessions — 会话API路由薄壳 (A7 后路由+DTO 调 session_service)
"""
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.db import db
from app.db.models.chat_models import SessionCreate, SessionListResponse  # noqa: F401 DTO 透传
from app.services.chat.session_service import (
    create_session,
    list_sessions,
    update_session,
    delete_session,
    get_session_titles_batch,
    get_session_info,
    SessionUpdate,
)
from app.services.chat.storage import save_execution_steps, ExecutionStepsUpdate  # noqa: F401
from app.services.chat.storage import (
    list_session_tasks,
    list_session_trust,
    delete_session_trust,
)

router = APIRouter()


class _SessionCreate(SessionCreate):
    """会话创建 DTO(继承 models 以兼容现有响应) — 薄壳透传"""
    pass


@router.post("/sessions")
def create_session_endpoint(session_create: Optional[SessionCreate] = None):
    return create_session(session_create)


@router.get("/sessions")
def list_sessions_endpoint(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: Optional[str] = Query(None),
    is_valid: Optional[bool] = Query(None)
):
    return list_sessions(page, page_size, keyword, is_valid)


@router.put("/sessions/{session_id}")
def update_session_endpoint(session_id: str, update_data: SessionUpdate):
    return update_session(session_id, update_data)


@router.delete("/sessions/{session_id}")
def delete_session_endpoint(session_id: str):
    return delete_session(session_id)


@router.get("/sessions/titles/batch")
def get_session_titles_batch_endpoint(
    session_ids: str = Query(..., description="逗号分隔的会话ID列表")
):
    return get_session_titles_batch(session_ids)


@router.post("/sessions/{session_id}/execution_steps")
async def save_execution_steps_endpoint(session_id: str, update_data: ExecutionStepsUpdate):
    return await save_execution_steps(session_id, update_data)


@router.get("/sessions/{session_id}/tasks")
def list_session_tasks_endpoint(session_id: str):
    """B1/问题6(10.5): 会话任务列表 + 任务数 + 最新任务id（任务数=用户消息数, chat_tasks 行数新口径）— 小欧 2026-08-20
    2026-08-30 小欧 设计文档[2]12.5 v1.103: 响应新增 latest_task_id(配合 storage 三元组返回, 排序一义后锚点解耦)"""
    with db.get_conn("chat") as conn:
        tasks, total, latest_task_id = list_session_tasks(conn, session_id)
    return {"session_id": session_id, "total": total, "tasks": tasks, "latest_task_id": latest_task_id}


@router.get("/sessions/{session_id}/trust")
def list_session_trust_endpoint(session_id: str):
    """D1(10.5 问题4): 会话已信任工具清单 — 小欧 2026-08-20"""
    with db.get_conn("chat") as conn:
        rows = list_session_trust(conn, session_id)
    return {"session_id": session_id, "total": len(rows), "trusted_tools": rows}


@router.delete("/sessions/{session_id}/trust/{tool_name}")
def delete_session_trust_endpoint(session_id: str, tool_name: str):
    """D3(10.5 问题4): 撤销会话对指定工具的信任 — 小欧 2026-08-20"""
    with db.get_conn("chat") as conn:
        removed = delete_session_trust(conn, session_id, tool_name)
    if not removed:
        raise HTTPException(status_code=404, detail="Trust not found")
    return {"success": True, "session_id": session_id, "tool_name": tool_name}


@router.get("/sessions/{session_id}")
def get_session_detail_endpoint(session_id: str):
    """D-2(文档2 8.D): 单会话信息 — 设置界面读取会话级信息 + 顶栏创建/更新时间悬浮数据源, 现有端点无单会话信息 — 小欧 2026-08-26"""
    return get_session_info(session_id)