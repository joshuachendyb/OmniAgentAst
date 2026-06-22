# -*- coding: utf-8 -*-
"""
operation_recorder — 操作记录和文件信息收集

职责: 记录操作、更新操作状态、收集文件信息
小欧 2026-06-18 从operation_commands.py拆分，遵守SRP
"""
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
from uuid import uuid4

from app.db import db
from app.db.models.operation_enums import OperationType, OperationStatus
from app.utils.logger import logger
from app.services.safety.hash_helper import compute_file_hash


def collect_file_info(path: Path) -> Dict[str, Any]:
    """收集文件信息"""
    if not path or not path.exists():
        return {"size": None, "hash": None, "extension": None, "is_directory": False}
    info = {"size": path.stat().st_size, "is_directory": path.is_dir()}
    if path.is_file():
        info["hash"] = compute_file_hash(path)
        info["extension"] = path.suffix.lower() if path.suffix else None
    else:
        info["hash"] = None
        info["extension"] = None
    return info


def update_op_failed(cursor: sqlite3.Cursor, operation_id: str, error_message: str):
    """更新操作为失败状态"""
    cursor.execute(
        'UPDATE file_operations SET status = ?, error_message = ? WHERE operation_id = ?',
        (OperationStatus.FAILED.value, error_message, operation_id),
    )


def record_operation(
    task_id: str,
    operation_type: Optional[str] = None,
    source_path: Optional[Path] = None,
    destination_path: Optional[Path] = None,
    sequence_number: int = 0,
    file_size: Optional[int] = None,
) -> str:
    """记录文件操作到数据库"""
    operation_id = f"op-{uuid4().hex}"
    space_impact_bytes = None
    if file_size is not None:
        if operation_type == OperationType.CREATE:
            space_impact_bytes = -file_size
        elif operation_type == OperationType.DELETE:
            space_impact_bytes = file_size
    try:
        with db.get_conn("operations") as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''INSERT INTO file_operations
                (operation_id, task_id, operation_type, status, source_path,
                 destination_path, sequence_number, file_size, space_impact_bytes, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (operation_id, task_id, operation_type.value,
                 OperationStatus.PENDING.value,
                 str(source_path) if source_path else None,
                 str(destination_path) if destination_path else None,
                 sequence_number, file_size, space_impact_bytes, datetime.now()),
            )
        logger.debug(f"Operation recorded: {operation_id} - {operation_type.value}")
        return operation_id
    except Exception as e:
        logger.error(f"Failed to record operation: {e}")
        raise
