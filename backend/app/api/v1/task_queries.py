# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-16 - 小欧 - 新增 rollback / file-operations / file-operations/report(text|html|json) 三API
# 2026-07-18 - 小欧 - file-operations API created_at 改 format_timestamp 对外兜底 UTC Z
"""Task 查询 API 路由

提供任务查询接口:单个任务、最近任务列表、操作明细。
Author: 小沈 - 2026-05-29
"""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from app.services.task import TaskQueries
from app.services.safety.operation_rollback import rollback_session
from app.db.operation_queries import query_file_operations
from app.services.visualization.text_report import generate_text_report
from app.services.visualization.html_report import generate_html_report
from app.services.visualization.json_report import generate_json_report
from app.utils.time_utils import format_timestamp  # 小欧 2026-07-18 API 对外契约统一兜底

router = APIRouter()
_queries = TaskQueries()


@router.get("/tasks/{task_id}")
def get_task(task_id: str):
    """获取单个任务详情"""
    result = _queries.get_task(task_id)
    if not result:
        raise HTTPException(status_code=404, detail="Task not found")
    return result


@router.get("/tasks")
def get_recent_tasks(
    limit: int = Query(default=10, ge=1, le=100),
):
    """最近任务列表"""
    return _queries.get_recent_tasks(limit=limit)


@router.get("/tasks/{task_id}/operations")
def get_operations(task_id: str):
    """获取任务的操作明细"""
    return _queries.get_operations(task_id)


@router.post("/tasks/{task_id}/rollback")
def rollback_task(task_id: str):
    """回滚任务的所有文件操作(激活B功能, 小欧 2026-07-16)

    说明: 回滚为显式管理动作,由调用方(前端按钮)发起即代表用户确认。
    直接同步执行 rollback_session,返回回滚统计。
    """
    if not _queries.get_task(task_id):
        raise HTTPException(status_code=404, detail="Task not found")
    result = rollback_session(task_id)
    return {"task_id": task_id, "rollback": result}


@router.get("/tasks/{task_id}/file-operations")
def get_file_operations(task_id: str):
    """查询任务的文件操作明细(file_operations表, 小欧 2026-07-16)"""
    rows = query_file_operations(task_id)
    columns = [
        "operation_type", "source_path", "destination_path", "status",
        "file_size", "is_directory", "created_at", "error_message",
    ]
    return [{
        **dict(zip(columns, row)),
        "created_at": format_timestamp(dict(zip(columns, row)).get("created_at")),
    } for row in rows]


@router.get("/tasks/{task_id}/file-operations/report")
def get_file_operations_report(
    task_id: str,
    format: str = Query(default="text", pattern="^(text|html|json)$"),
):
    """生成文件操作报告(支持text/html/json, 小欧 2026-07-16)"""
    task = _queries.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    task_desc = task.get("task_description") or ""
    if format == "html":
        content = generate_html_report(task_id, task_desc)
        return Response(content=content, media_type="text/html; charset=utf-8")
    if format == "json":
        content = generate_json_report(task_id, task_desc)
        return Response(content=content, media_type="application/json")
    content = generate_text_report(task_id, task_desc)
    return Response(content=content, media_type="text/plain; charset=utf-8")
