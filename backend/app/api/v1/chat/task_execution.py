# -*- coding: utf-8 -*-
# v2.0 C1/C2 任务级回放与统计接口 — 小欧 2026-08-19
# 2026-08-29 - 小沈 - 修复#17: 两端点读库由同步 db.get_conn 改为 db.atxn 离载子线程, 不阻塞事件循环
"""
task_execution — C1 任务详情统计 + C2 按 task_id 步骤回放
落在 chat 域（与 execution_stream C3 同域）
"""
from fastapi import APIRouter, HTTPException
from app.db import db
from app.services.chat.storage import (
    get_task_detail, get_task_tool_stats, load_steps_by_task, load_user_message_by_task,
)

router = APIRouter()


@router.get("/chat/execution/task/{task_id}")
async def get_task_detail_endpoint(task_id: str):
    """C1: 任务详情 + 工具统计"""
    def _read(conn):
        task = get_task_detail(conn, task_id)
        if not task:
            raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")
        tool_stats = get_task_tool_stats(conn, task_id)
        user_msg = load_user_message_by_task(conn, task_id)
        return {
            "task": task,
            "tool_stats": tool_stats,
            "user_message": user_msg,
        }
    return await db.atxn("chat", _read)


@router.get("/chat/execution/task/{task_id}/steps")
async def get_task_steps_endpoint(task_id: str):
    """C2: 按 task_id 步骤回放"""
    def _read(conn):
        steps = load_steps_by_task(conn, task_id)
        return {"task_id": task_id, "steps": steps, "count": len(steps)}
    return await db.atxn("chat", _read)
