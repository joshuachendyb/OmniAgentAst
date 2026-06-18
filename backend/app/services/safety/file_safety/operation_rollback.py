# -*- coding: utf-8 -*-
"""
operation_rollback — 操作回滚

职责: 回滚单个操作、回滚整个会话
小欧 2026-06-18 从operation_commands.py拆分，遵守SRP
"""
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

from app.db import db
from app.db.models.operation_enums import OperationType, OperationStatus
from app.utils.logger import logger


def rollback_operation(operation_id: str) -> bool:
    """回滚单个文件操作"""
    try:
        with db.get_conn("operations") as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT operation_type, source_path, destination_path, backup_path, status FROM file_operations WHERE operation_id = ?',
                (operation_id,),
            )
            row = cursor.fetchone()
            if not row:
                logger.error(f"Operation not found for rollback: {operation_id}")
                return False

            op_type, src, dst, backup, status = row
            if status == OperationStatus.ROLLBACK.value:
                logger.info(f"Operation already rolled back: {operation_id}")
                return True

            success = False
            if op_type == OperationType.DELETE.value:
                if backup and Path(backup).exists():
                    backup_path = Path(backup)
                    source_path = Path(src)
                    source_path.parent.mkdir(parents=True, exist_ok=True)
                    if backup_path.is_dir():
                        shutil.copytree(backup_path, source_path)
                    else:
                        shutil.copy2(backup_path, source_path)
                    success = True
                    logger.info(f"Restored deleted file: {backup} -> {source_path}")
            elif op_type == OperationType.MOVE.value:
                dest_path = Path(dst)
                source_path = Path(src)
                if dest_path.exists():
                    dest_path.rename(source_path)
                    success = True
                    logger.info(f"Moved back: {dest_path} -> {source_path}")
            elif op_type == OperationType.CREATE.value:
                dest_path = Path(dst) if dst else Path(src)
                if dest_path.exists():
                    if dest_path.is_dir():
                        shutil.rmtree(dest_path)
                    else:
                        dest_path.unlink()
                    success = True
                    logger.info(f"Removed created file: {dest_path}")

            if success:
                cursor.execute(
                    'UPDATE file_operations SET status = ?, rolled_back_at = ? WHERE operation_id = ?',
                    (OperationStatus.ROLLBACK.value, datetime.now(), operation_id),
                )
                logger.info(f"Operation rolled back: {operation_id}")
            return success
    except Exception as e:
        logger.error(f"Failed to rollback operation {operation_id}: {e}")
        return False


def rollback_session(task_id: str) -> Dict[str, Any]:
    """回滚整个任务会话的所有操作"""
    result = {"task_id": task_id, "total": 0, "success": 0, "failed": 0, "operations": []}
    try:
        with db.get_conn("operations") as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''SELECT operation_id, operation_type, source_path, destination_path
                FROM file_operations WHERE task_id = ? AND status = ?
                ORDER BY sequence_number DESC''',
                (task_id, OperationStatus.SUCCESS.value),
            )
            operations = cursor.fetchall()
            result["total"] = len(operations)

            for op_id, op_type, src, dst in operations:
                success = rollback_operation(op_id)
                result["operations"].append({"operation_id": op_id, "type": op_type, "success": success})
                if success:
                    result["success"] += 1
                else:
                    result["failed"] += 1

            cursor.execute(
                'UPDATE task_operations SET rolled_back_count = ?, status = ? WHERE task_id = ?',
                (result["success"], OperationStatus.ROLLBACK.value, task_id),
            )
        logger.info(f"Task rollback completed: {task_id} - {result['success']}/{result['total']} succeeded")
        return result
    except Exception as e:
        logger.error(f"Failed to rollback session {task_id}: {e}")
        return result
