# -*- coding: utf-8 -*-
"""
get_operation — 从 file_safety.py 拷出

拷贝来源: file_safety.py 第487-514行
"""

from typing import Optional

from app.db import db
from app.db.models.operation_models import OperationRecord
from app.utils.logger import logger
from app.services.safety.file.file_safety.row_to_operation_record import row_to_operation_record


def get_operation(operation_id: str) -> Optional[OperationRecord]:
    """拷贝自 file_safety.py 第487-514行"""
    try:
        with db.get_conn("operations") as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM file_operations WHERE operation_id = ?', (operation_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return row_to_operation_record(row)
    except Exception as e:
        logger.error(f"Failed to get operation {operation_id}: {e}")
        return None
