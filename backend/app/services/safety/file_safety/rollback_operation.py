# -*- coding: utf-8 -*-
"""
rollback_operation — 从 file_safety.py 拷出

拷贝来源: file_safety.py 第296-374行
"""

import shutil
from datetime import datetime
from pathlib import Path

from app.db import db
from app.db.models.operation_enums import OperationType, OperationStatus
from app.utils.logger import logger


def rollback_operation(operation_id: str) -> bool:
    """拷贝自 file_safety.py 第296-374行"""
    try:
        with db.get_conn("operations") as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT operation_type, source_path, destination_path, backup_path, status
                FROM file_operations WHERE operation_id = ?
            ''', (operation_id,))
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
                cursor.execute('''
                    UPDATE file_operations 
                    SET status = ?, rolled_back_at = ?
                    WHERE operation_id = ?
                ''', (OperationStatus.ROLLBACK.value, datetime.now(), operation_id))
                logger.info(f"Operation rolled back: {operation_id}")
            return success
    except Exception as e:
        logger.error(f"Failed to rollback operation {operation_id}: {e}")
        return False
