# -*- coding: utf-8 -*-
"""
rollback_session — 从 file_safety.py 拷出

拷贝来源: file_safety.py 第399-457行
"""

from typing import Dict, Any

from app.db import db
from app.db.models.operation_enums import OperationStatus
from app.utils.logger import logger
from app.services.safety.file.file_safety.rollback_operation import rollback_operation


def rollback_session(task_id: str) -> Dict[str, Any]:
    """拷贝自 file_safety.py 第399-457行"""
    result = {"task_id": task_id, "total": 0, "success": 0, "failed": 0, "operations": []}
    try:
        with db.get_conn("operations") as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT operation_id, operation_type, source_path, destination_path
                FROM file_operations 
                WHERE task_id = ? AND status = ?
                ORDER BY sequence_number DESC
            ''', (task_id, OperationStatus.SUCCESS.value))
            operations = cursor.fetchall()
            result["total"] = len(operations)

            for op_id, op_type, src, dst in operations:
                success = rollback_operation(op_id)
                result["operations"].append({"operation_id": op_id, "type": op_type, "success": success})
                if success:
                    result["success"] += 1
                else:
                    result["failed"] += 1

            cursor.execute('''
                UPDATE task_operations 
                SET rolled_back_count = ?, status = ?
                WHERE task_id = ?
            ''', (result["success"], OperationStatus.ROLLBACK.value, task_id))

        logger.info(f"Task rollback completed: {task_id} - {result['success']}/{result['total']} succeeded")
        return result
    except Exception as e:
        logger.error(f"Failed to rollback session {task_id}: {e}")
        return result
