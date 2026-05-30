# -*- coding: utf-8 -*-
"""TaskTracker — 任务生命周期 + 操作管理 + 回滚标记 + 报告

调用方：Agent、回滚模块、报告模块。
所有意图共用同一个持久化 Tracker。

Author: 小沈 - 2026-05-29
"""

import json
from uuid import uuid4
from datetime import datetime
from typing import Optional, Dict, Any, List

from app.db import db
from app.utils.logger import logger
from app.db.models.operation_enums import OperationStatus
from .models import TaskStatus

# 常量已迁移到 constants.py — 北京老陈 2026-05-30
from app.constants import VALID_INTENTS


class TaskTracker:
    """任务追踪器 — 双表操作：tasks（task 级）+ operations（operation 级）"""

    # ===== 任务生命周期 =====

    def create_task(self, intent: str, agent_id: str, description: str) -> str:
        """创建任务 → 返回 task_id"""
        if intent not in VALID_INTENTS:
            raise ValueError(
                f"Invalid intent: {intent}. Must be one of: {VALID_INTENTS}"
            )
        task_id = f"task-{uuid4().hex}"
        with db.get_conn("task_tracker") as conn:
            conn.execute(
                """INSERT INTO tasks
                   (task_id, intent, agent_id, task_description, status)
                   VALUES (?, ?, ?, ?, ?)""",
                (task_id, intent, agent_id, description, TaskStatus.EXECUTING.value),
            )
        return task_id

    def complete_task(self, task_id: str, success: bool = True) -> None:
        """完成任务 — 更新 tasks 表"""
        status = TaskStatus.SUCCESS.value if success else TaskStatus.FAILED.value
        with db.get_conn("task_tracker") as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM operations WHERE task_id = ? AND status = ?",
                (task_id, OperationStatus.SUCCESS.value),
            ).fetchone()
            success_count = row[0] if row else 0
            conn.execute(
                """UPDATE tasks SET status = ?, completed_at = ?,
                   success_count = ? WHERE task_id = ?""",
                (status, datetime.now(), success_count, task_id),
            )

    # ===== 操作管理 =====

    def add_operation(
        self,
        task_id: str,
        operation_type: str,
        *,
        source_path: Optional[str] = None,
        destination_path: Optional[str] = None,
        backup_path: Optional[str] = None,
        file_size: int = 0,
        file_hash: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> str:
        """记录一次操作 → 插入 operations 表"""
        with db.get_conn("task_tracker") as conn:
            task_row = conn.execute(
                "SELECT task_id FROM tasks WHERE task_id = ?", (task_id,)
            ).fetchone()
            if not task_row:
                raise ValueError(f"Task {task_id} not found")

            seq_row = conn.execute(
                "SELECT COALESCE(MAX(sequence_number), 0) + 1 "
                "FROM operations WHERE task_id = ?",
                (task_id,),
            ).fetchone()
            seq_num = seq_row[0]

            operation_id = f"op-{uuid4().hex}"
            conn.execute(
                """INSERT INTO operations
                   (operation_id, task_id, operation_type, status,
                    source_path, destination_path, backup_path,
                    file_size, file_hash, sequence_number, details)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    operation_id,
                    task_id,
                    operation_type,
                    OperationStatus.SUCCESS.value,
                    source_path,
                    destination_path,
                    backup_path,
                    file_size,
                    file_hash,
                    seq_num,
                    json.dumps(details) if details else None,
                ),
            )
            conn.execute(
                "UPDATE tasks SET total_operations = total_operations + 1 WHERE task_id = ?",
                (task_id,),
            )
        return operation_id

    # ===== 状态管理 =====

    def mark_failed(self, task_id: str, operation_id: str, error: str) -> None:
        """标记某个操作为失败"""
        with db.get_conn("task_tracker") as conn:
            conn.execute(
                "UPDATE operations SET status = ?, error = ? WHERE operation_id = ?",
                (OperationStatus.FAILED.value, error, operation_id),
            )
            conn.execute(
                "UPDATE tasks SET failed_count = failed_count + 1 WHERE task_id = ?",
                (task_id,),
            )

    def mark_rolled_back(
        self, task_id: str, op_ids: Optional[List[str]] = None
    ) -> None:
        """标记操作为已回滚，检查是否全量回滚"""
        with db.get_conn("task_tracker") as conn:
            if op_ids:
                placeholders = ",".join("?" for _ in op_ids)
                conn.execute(
                    f"UPDATE operations SET status = ? "
                    f"WHERE operation_id IN ({placeholders})",
                    [OperationStatus.ROLLBACK.value] + op_ids,
                )
                row = conn.execute(
                    "SELECT COUNT(*) FROM operations WHERE task_id = ? AND status != ?",
                    (task_id, OperationStatus.ROLLBACK.value),
                ).fetchone()
                all_rolled_back = (row[0] == 0) if row else False
                task_status = (
                    TaskStatus.ROLLED_BACK.value
                    if all_rolled_back
                    else TaskStatus.PARTIALLY_ROLLED_BACK.value
                )
            else:
                conn.execute(
                    "UPDATE operations SET status = ? WHERE task_id = ?",
                    (OperationStatus.ROLLBACK.value, task_id),
                )
                task_status = TaskStatus.ROLLED_BACK.value

            conn.execute(
                """UPDATE tasks SET status = ?,
                   rolled_back_count = (
                       SELECT COUNT(*) FROM operations WHERE task_id = ? AND status = ?
                   ) WHERE task_id = ?""",
                (task_status, task_id, OperationStatus.ROLLBACK.value, task_id),
            )

    # ===== 报告管理 =====

    def mark_report_generated(self, task_id: str, report_path: str) -> None:
        """标记任务报告已生成"""
        with db.get_conn("task_tracker") as conn:
            conn.execute(
                "UPDATE tasks SET report_generated = 1, report_path = ? WHERE task_id = ?",
                (report_path, task_id),
            )


# ===== 单例工厂（线程安全） =====

import threading
from typing import Optional as _Optional

_tracker: _Optional[TaskTracker] = None
_lock = threading.Lock()


def get_tracker() -> TaskTracker:
    """获取追踪器单例 — 线程安全，所有意图共用"""
    global _tracker
    if _tracker is None:
        with _lock:
            if _tracker is None:
                _tracker = TaskTracker()
    return _tracker
