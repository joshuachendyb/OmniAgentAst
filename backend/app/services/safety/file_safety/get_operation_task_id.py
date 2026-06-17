# -*- coding: utf-8 -*-
"""
get_operation_task_id — 从 file_safety.py 拷出

拷贝来源: file_safety.py 第376-397行
"""

from typing import Optional

from app.db import db
from app.utils.logger import logger


def get_operation_task_id(operation_id: str) -> Optional[str]:
    """拷贝自 file_safety.py 第376-397行"""
    try:
        with db.get_conn("operations") as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT task_id FROM file_operations WHERE operation_id = ?',
                (operation_id,)
            )
            row = cursor.fetchone()
            return row[0] if row else None
    except Exception as e:
        logger.error(f"Failed to get task_id for operation {operation_id}: {e}")
        return None
