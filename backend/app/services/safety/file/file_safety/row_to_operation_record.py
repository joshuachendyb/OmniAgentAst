# -*- coding: utf-8 -*-
"""
row_to_operation_record — 从 file_safety.py 拷出

拷贝来源: file_safety.py 第80-104行
"""

import json

from app.db.models.operation_enums import OperationType, OperationStatus
from app.db.models.operation_models import OperationRecord


def row_to_operation_record(row) -> OperationRecord:
    """拷贝自 file_safety.py 第80-104行"""
    return OperationRecord(
        operation_id=row[1],
        task_id=row[2],
        operation_type=OperationType(row[3]),
        status=OperationStatus(row[4]),
        source_path=row[5],
        destination_path=row[6],
        backup_path=row[7],
        backup_expires_at=row[8],
        file_size=row[9],
        file_hash=row[10],
        is_directory=bool(row[11]),
        file_extension=row[12],
        duration_ms=row[13],
        space_impact_bytes=row[14],
        metadata=json.loads(row[15]) if row[15] else {},
        error_message=row[16],
        created_at=row[17],
        executed_at=row[18],
        rolled_back_at=row[19],
        sequence_number=row[20]
    )
