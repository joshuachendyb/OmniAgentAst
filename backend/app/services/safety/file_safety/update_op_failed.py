# -*- coding: utf-8 -*-
"""
update_op_failed — 从 file_safety.py 拷出

拷贝来源: file_safety.py 第218-227行
"""

from app.db.models.operation_enums import OperationStatus


def update_op_failed(cursor, operation_id: str, error_message: str):
    """拷贝自 file_safety.py 第218-227行"""
    cursor.execute('''
        UPDATE file_operations 
        SET status = ?, error_message = ?
        WHERE operation_id = ?
    ''', (OperationStatus.FAILED.value, error_message, operation_id))
