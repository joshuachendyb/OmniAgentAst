# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-18 - 小欧 - OperationRecord/query_animation_operations 时间字段 format_timestamp 对外兜底 UTC Z
"""
文件操作查询 — 所有file_operations表只读查询

从 app/services/safety/file_safety/operation_queries.py 迁移至 db/
原因: 纯SQL查询函数，不含安全逻辑，应属于数据访问层而非安全层

合并自: row_to_operation_record, get_operation, get_session_operations,
        get_operation_task_id + 原有5个visualization query函数

Author: 小健 - 2026-06-17
"""
from typing import List, Tuple, Dict, Any, Optional

from app.db import db
from app.db.models.operation_models import OperationType, OperationStatus
from app.db.models.operation_models import OperationRecord
from app.utils.json_utils import parse_json
from app.utils.time_utils import format_timestamp  # 小欧 2026-07-18 API 对外契约统一兜底
from app.logger import logger


def _execute_query(sql: str, params: tuple) -> list:
    """公用查询：打开 operations 连接并执行 SQL — 小欧 2026-07-10 M-18"""
    with db.get_conn("operations") as conn:
        return conn.cursor().execute(sql, params).fetchall()


def row_to_operation_record(row) -> OperationRecord:
    return OperationRecord(
        operation_id=row[1], task_id=row[2],
        operation_type=OperationType(row[3]), status=OperationStatus(row[4]),
        source_path=row[5], destination_path=row[6], backup_path=row[7],
        backup_expires_at=row[8], file_size=row[9], file_hash=row[10],
        is_directory=bool(row[11]), file_extension=row[12],
        duration_ms=row[13], space_impact_bytes=row[14],
        metadata=parse_json(row[15]) or {}, error_message=row[16],
        created_at=format_timestamp(row[17]), executed_at=format_timestamp(row[18]), rolled_back_at=format_timestamp(row[19]),
        sequence_number=row[20],
    )


def get_operation(operation_id: str) -> Optional[OperationRecord]:
    try:
        with db.get_conn("operations") as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM file_operations WHERE operation_id = ?', (operation_id,))
            row = cursor.fetchone()
            return row_to_operation_record(row) if row else None
    except Exception as e:
        logger.error(f"Failed to get operation {operation_id}: {e}")
        return None


def get_session_operations(task_id: str) -> List[OperationRecord]:
    try:
        with db.get_conn("operations") as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT * FROM file_operations WHERE task_id = ? ORDER BY sequence_number ASC',
                (task_id,),
            )
            return [row_to_operation_record(row) for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Failed to get session operations: {e}")
        return []


def get_operation_task_id(operation_id: str) -> Optional[str]:
    try:
        with db.get_conn("operations") as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT task_id FROM file_operations WHERE operation_id = ?', (operation_id,))
            row = cursor.fetchone()
            return row[0] if row else None
    except Exception as e:
        logger.error(f"Failed to get task_id for operation {operation_id}: {e}")
        return None


def query_file_operations(task_id: str) -> List[Tuple]:
    return _execute_query('''
        SELECT operation_type, source_path, destination_path, status,
               file_size, is_directory, created_at, error_message
        FROM file_operations WHERE task_id = ?
        ORDER BY sequence_number ASC
    ''', (task_id,))


def query_tree_operations(task_id: str) -> List[Tuple]:
    return _execute_query('''
        SELECT operation_id, operation_type, source_path, destination_path, status
        FROM file_operations WHERE task_id = ?
        ORDER BY sequence_number ASC
    ''', (task_id,))


def query_sankey_operations(task_id: str) -> List[Tuple]:
    return _execute_query('''
        SELECT operation_type, source_path, destination_path, status
        FROM file_operations WHERE task_id = ? AND status = 'success'
        ORDER BY sequence_number ASC
    ''', (task_id,))


def query_animation_operations(task_id: str) -> List[Dict[str, Any]]:
    rows = _execute_query('''
        SELECT operation_type, source_path, destination_path, status, created_at
        FROM file_operations WHERE task_id = ?
        ORDER BY sequence_number ASC
    ''', (task_id,))
    if not rows:
        return []
    return [
        {"type": op_type, "source": src, "destination": dst, "status": status, "timestamp": format_timestamp(created_at)}
        for op_type, src, dst, status, created_at in rows
    ]


def query_mermaid_operations(task_id: str) -> List[Tuple]:
    return _execute_query('''
        SELECT operation_type, source_path, destination_path, status, sequence_number
        FROM file_operations WHERE task_id = ?
        ORDER BY sequence_number ASC
    ''', (task_id,))