# -*- coding: utf-8 -*-
"""TaskQueries — 查询服务

只负责查询，不修改数据。
调用方：API、前端。

Author: 小沈 - 2026-05-29
"""

from typing import Optional, Dict, Any, List

from app.db import db
from app.utils.data_utils import parse_json


class TaskQueries:
    """任务查询服务 — 只负责查询，不修改数据"""

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取单个任务"""
        with db.get_conn("task_tracker") as conn:
            row = conn.execute(
                "SELECT * FROM tasks WHERE task_id = ?", (task_id,)
            ).fetchone()
            return dict(row) if row else None

    def get_recent_tasks(
        self, limit: int = 10, intent: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """最近任务列表，可按意图过滤"""
        with db.get_conn("task_tracker") as conn:
            if intent:
                rows = conn.execute(
                    "SELECT * FROM tasks WHERE intent = ? "
                    "ORDER BY created_at DESC LIMIT ?",
                    (intent, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            return [dict(r) for r in rows]

    def get_operations(self, task_id: str) -> List[Dict[str, Any]]:
        """获取任务的所有操作（逆序）"""
        with db.get_conn("task_tracker") as conn:
            rows = conn.execute(
                "SELECT * FROM operations WHERE task_id = ? "
                "ORDER BY sequence_number DESC",
                (task_id,),
            ).fetchall()
            result = []
            for r in rows:
                d = dict(r)
                if d.get("details"):
                    d["details"] = parse_json(d["details"], label="operation_details")
                result.append(d)
            return result
