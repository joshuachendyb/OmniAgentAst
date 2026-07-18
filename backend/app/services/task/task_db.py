# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-16 - 小欧 - operations表重命名为task_operations(正名)+在线迁移(RENAME旧表)+操作ID统一generate_operation_id+新增mark_rolled_back方法
# 2026-07-18 - 小欧 - complete_task 的 completed_at 改用 now_str() 序列化入库, 消除对已废弃默认 datetime 适配器(Python3.12+ DeprecationWarning)的依赖, 与 created_at(CURRENT_TIMESTAMP) 空格秒格式统一
# 2026-07-18 - 小欧 - complete_task/create_task/add_operation 时间统一 get_utc_timestamp() UTC Z; TaskQueries 三返回方法 format_timestamp 对外兜底
"""
task_db — 任务DB持久化（tasks表 + operations表）

合并自: task_tracker + task_queries
小欧 2026-07-10
更新: 小欧 - 2026-07-16 统一TaskID: create_task必填task_id无兜底无返回
"""

import json
import threading
from app.utils.id_utils import generate_operation_id
from app.utils.time_utils import get_utc_timestamp  # 小欧 2026-07-18: 时间统一入库 UTC Z
from app.utils.time_utils import format_timestamp  # 小欧 2026-07-18: API 对外契约统一兜底
from typing import Optional, Dict, Any, List
from enum import Enum

from app.db import db
from app.logger import logger
from app.utils.json_utils import parse_json
from app.db.models.operation_models import OperationStatus


class TaskStatus(str, Enum):
    """任务生命周期状态 — 小沈 2026-05-29"""
    PENDING = "pending"
    EXECUTING = "executing"
    SUCCESS = "success"
    FAILED = "failed"
    PARTIALLY_ROLLED_BACK = "partially_rolled_back"
    ROLLED_BACK = "rolled_back"


class TaskTracker:
    """任务追踪器 — 双表操作:tasks(task 级)+ operations(operation 级)"""

    # ===== 任务生命周期 =====

    def create_task(self, task_id: str, agent_id: str, description: str) -> None:
        """写入任务记录 — task_id 由调用方统一提供（SSE task_id），tracker 不再自编号 — 小欧 2026-07-16"""
        with db.get_conn("task_tracker") as conn:
            conn.execute(
                """INSERT INTO tasks
                   (task_id, intent, agent_id, task_description, status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (task_id, "", agent_id, description, TaskStatus.EXECUTING.value, get_utc_timestamp()),
            )

    def complete_task(self, task_id: str, success: bool = True) -> None:
        status = TaskStatus.SUCCESS.value if success else TaskStatus.FAILED.value
        with db.get_conn("task_tracker") as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM task_operations WHERE task_id = ? AND status = ?",
                (task_id, OperationStatus.SUCCESS.value),
            ).fetchone()
            success_count = row[0] if row else 0
            conn.execute(
                """UPDATE tasks SET status = ?, completed_at = ?,
                   success_count = ? WHERE task_id = ?""",
                (status, get_utc_timestamp(), success_count, task_id),  # 小欧 2026-07-18: UTC Z 字符串入库, 边界自动归一化
            )

    # ===== 操作管理 =====

    def add_operation(
        self,
        task_id: str,
        operation_type: str,
        *,
        operation_id: Optional[str] = None,
        status: Optional[str] = None,
        source_path: Optional[str] = None,
        destination_path: Optional[str] = None,
        backup_path: Optional[str] = None,
        file_size: int = 0,
        file_hash: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> str:
        op_status = status or OperationStatus.SUCCESS.value
        with db.get_conn("task_tracker") as conn:
            task_row = conn.execute(
                "SELECT task_id FROM tasks WHERE task_id = ?", (task_id,)
            ).fetchone()
            if not task_row:
                raise ValueError(f"Task {task_id} not found")

            seq_row = conn.execute(
                "SELECT COALESCE(MAX(sequence_number), 0) + 1 "
                "FROM task_operations WHERE task_id = ?",
                (task_id,),
            ).fetchone()
            seq_num = seq_row[0]

            operation_id = operation_id or generate_operation_id()
            conn.execute(
                """INSERT INTO task_operations
                   (operation_id, task_id, operation_type, status,
                    source_path, destination_path, backup_path,
                    file_size, file_hash, sequence_number, details, error, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",  # 小欧 2026-07-18: created_at 列对齐第13值 get_utc_timestamp() UTC Z 入库
                (
                    operation_id, task_id, operation_type, op_status,
                    source_path, destination_path, backup_path,
                    file_size, file_hash, seq_num,
                     json.dumps(details) if details else None, error, get_utc_timestamp(),
                 ),
            )
            if op_status == OperationStatus.FAILED.value:
                conn.execute(
                    "UPDATE tasks SET failed_count = failed_count + 1 WHERE task_id = ?",
                    (task_id,),
                )
            conn.execute(
                "UPDATE tasks SET total_operations = total_operations + 1 WHERE task_id = ?",
                (task_id,),
            )
        return operation_id

    def mark_rolled_back(
        self, task_id: str, op_ids: Optional[List[str]] = None
    ) -> None:
        with db.get_conn("task_tracker") as conn:
            if op_ids:
                placeholders = ",".join("?" for _ in op_ids)
                conn.execute(
                    f"UPDATE task_operations SET status = ? "
                    f"WHERE operation_id IN ({placeholders})",
                    [OperationStatus.ROLLBACK.value] + op_ids,
                )
                row = conn.execute(
                    "SELECT COUNT(*) FROM task_operations WHERE task_id = ? AND status != ?",
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
                    "UPDATE task_operations SET status = ? WHERE task_id = ?",
                    (OperationStatus.ROLLBACK.value, task_id),
                )
                task_status = TaskStatus.ROLLED_BACK.value

            conn.execute(
                """UPDATE tasks SET status = ?,
                   rolled_back_count = (
                       SELECT COUNT(*) FROM task_operations WHERE task_id = ? AND status = ?
                   ) WHERE task_id = ?""",
                (task_status, task_id, OperationStatus.ROLLBACK.value, task_id),
            )

    # ===== 报告管理 =====

    def mark_report_generated(self, task_id: str, report_path: str) -> None:
        with db.get_conn("task_tracker") as conn:
            conn.execute(
                "UPDATE tasks SET report_generated = 1, report_path = ? WHERE task_id = ?",
                (report_path, task_id),
            )


# ===== 单例工厂(线程安全) =====

_tracker: Optional[TaskTracker] = None
_lock = threading.Lock()


def get_tracker() -> TaskTracker:
    global _tracker
    if _tracker is None:
        with _lock:
            if _tracker is None:
                _tracker = TaskTracker()
    return _tracker


class TaskQueries:
    """任务查询服务 — 只负责查询,不修改数据"""

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        with db.get_conn("task_tracker") as conn:
            row = conn.execute(
                "SELECT * FROM tasks WHERE task_id = ?", (task_id,)
            ).fetchone()
            if not row:
                return None
            d = dict(row)
            d["created_at"] = format_timestamp(d.get("created_at"))
            d["completed_at"] = format_timestamp(d.get("completed_at"))
            return d

    def get_recent_tasks(self, limit: int = 10) -> List[Dict[str, Any]]:
        with db.get_conn("task_tracker") as conn:
            rows = conn.execute(
                "SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [{
                **dict(r),
                "created_at": format_timestamp(r["created_at"]),
                "completed_at": format_timestamp(r.get("completed_at")),
            } for r in rows]

    def get_operations(self, task_id: str) -> List[Dict[str, Any]]:
        with db.get_conn("task_tracker") as conn:
            rows = conn.execute(
                "SELECT * FROM task_operations WHERE task_id = ? "
                "ORDER BY sequence_number DESC",
                (task_id,),
            ).fetchall()
            result = []
            for r in rows:
                d = dict(r)
                if d.get("details"):
                    d["details"] = parse_json(d["details"], label="operation_details")
                d["created_at"] = format_timestamp(d.get("created_at"))
                result.append(d)
            return result
