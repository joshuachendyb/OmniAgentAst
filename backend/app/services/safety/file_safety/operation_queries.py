# -*- coding: utf-8 -*-
"""
文件操作查询 — 所有file_operations表只读查询 — 小健 2026-06-17

合并自: row_to_operation_record, get_operation, get_session_operations,
        get_operation_task_id + 原有5个visualization query函数
"""
from typing import List, Tuple, Dict, Any, Optional

from app.db import db
from app.db.models.operation_enums import OperationType, OperationStatus
from app.db.models.operation_models import OperationRecord
from app.utils.json_utils import parse_json
from app.utils.logger import logger


def row_to_operation_record(row) -> OperationRecord:
    return OperationRecord(
        operation_id=row[1], task_id=row[2],
        operation_type=OperationType(row[3]), status=OperationStatus(row[4]),
        source_path=row[5], destination_path=row[6], backup_path=row[7],
        backup_expires_at=row[8], file_size=row[9], file_hash=row[10],
        is_directory=bool(row[11]), file_extension=row[12],
        duration_ms=row[13], space_impact_bytes=row[14],
        metadata=parse_json(row[15]) or {}, error_message=row[16],
        created_at=row[17], executed_at=row[18], rolled_back_at=row[19],
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
    with db.get_conn("operations") as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT operation_type, source_path, destination_path, status,
                   file_size, is_directory, created_at, error_message
            FROM file_operations WHERE task_id = ?
            ORDER BY sequence_number ASC
        ''', (task_id,))
        return cursor.fetchall()


def query_tree_operations(task_id: str) -> List[Tuple]:
    with db.get_conn("operations") as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT operation_id, operation_type, source_path, destination_path, status
            FROM file_operations WHERE task_id = ?
            ORDER BY sequence_number ASC
        ''', (task_id,))
        return cursor.fetchall()


def query_sankey_operations(task_id: str) -> List[Tuple]:
    with db.get_conn("operations") as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT operation_type, source_path, destination_path, status
            FROM file_operations WHERE task_id = ? AND status = 'success'
            ORDER BY sequence_number ASC
        ''', (task_id,))
        return cursor.fetchall()


def query_animation_operations(task_id: str) -> List[Dict[str, Any]]:
    with db.get_conn("operations") as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT operation_type, source_path, destination_path, status, created_at
            FROM file_operations WHERE task_id = ?
            ORDER BY sequence_number ASC
        ''', (task_id,))
        rows = cursor.fetchall()
    if not rows:
        return []
    return [
        {"type": op_type, "source": src, "destination": dst, "status": status, "timestamp": created_at}
        for op_type, src, dst, status, created_at in rows
    ]


def query_mermaid_operations(task_id: str) -> List[Tuple]:
    with db.get_conn("operations") as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT operation_type, source_path, destination_path, status, sequence_number
            FROM file_operations WHERE task_id = ?
            ORDER BY sequence_number ASC
        ''', (task_id,))
        return cursor.fetchall()