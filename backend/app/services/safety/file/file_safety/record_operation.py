# -*- coding: utf-8 -*-
"""
record_operation — 从 file_safety.py 拷出

拷贝来源: file_safety.py 第136-196行
"""

from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import uuid4

from app.db import db
from app.db.models.operation_enums import OperationType, OperationStatus
from app.utils.logger import logger


def record_operation(
    task_id: str,
    operation_type: Optional[str] = None,
    source_path: Optional[Path] = None,
    destination_path: Optional[Path] = None,
    sequence_number: int = 0,
    file_size: Optional[int] = None
) -> str:
    """拷贝自 file_safety.py 第136-196行"""
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
            cursor.execute('''
                INSERT INTO file_operations 
                (operation_id, task_id, operation_type, status, source_path, 
                 destination_path, sequence_number, file_size, space_impact_bytes, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                operation_id, task_id, operation_type.value,
                OperationStatus.PENDING.value,
                str(source_path) if source_path else None,
                str(destination_path) if destination_path else None,
                sequence_number, file_size, space_impact_bytes, datetime.now()
            ))
        logger.debug(f"Operation recorded: {operation_id} - {operation_type.value}")
        return operation_id
    except Exception as e:
        logger.error(f"Failed to record operation: {e}")
        raise
