# -*- coding: utf-8 -*-
"""Task 查询 API 路由

提供任务查询接口：单个任务、最近任务列表、操作明细。
Author: 小沈 - 2026-05-29
"""

from typing import Optional
from fastapi import APIRouter, Query
from app.services.task import TaskQueries

router = APIRouter()
_queries = TaskQueries()


@router.get("/tasks/{task_id}")
def get_task(task_id: str):
    """获取单个任务详情"""
    result = _queries.get_task(task_id)
    if not result:
        return {"error": "Task not found"}
    return result


@router.get("/tasks")
def get_recent_tasks(
    limit: int = Query(default=10, ge=1, le=100),
    intent: Optional[str] = Query(default=None),
):
    """最近任务列表"""
    return _queries.get_recent_tasks(limit=limit, intent=intent)


@router.get("/tasks/{task_id}/operations")
def get_operations(task_id: str):
    """获取任务的操作明细"""
    return _queries.get_operations(task_id)
