# -*- coding: utf-8 -*-
"""
get_session_operations — 从 file_safety.py 拷出

拷贝来源: file_safety.py 第459-485行
"""

from typing import List

from app.db import db
from app.db.models.operation_models import OperationRecord
from app.utils.logger import logger
from app.services.safety.file.file_safety.row_to_operation_record import row_to_operation_record


def get_session_operations(task_id: str) -> List[OperationRecord]:
    """拷贝自 file_safety.py 第459-485行"""
    try:
        with db.get_conn("operations") as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM file_operations 
                WHERE task_id = ?
                ORDER BY sequence_number ASC
            ''', (task_id,))
            rows = cursor.fetchall()
            return [row_to_operation_record(row) for row in rows]
    except Exception as e:
        logger.error(f"Failed to get session operations: {e}")
        return []
