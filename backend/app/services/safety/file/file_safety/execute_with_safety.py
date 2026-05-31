# -*- coding: utf-8 -*-
"""
execute_with_safety — 从 file_safety.py 拷出

拷贝来源: file_safety.py 第229-294行
"""

from datetime import datetime, timedelta
from pathlib import Path

from app.db import db
from app.db.models.operation_enums import OperationType, OperationStatus
from app.utils.logger import logger
from app.services.safety.file.file_safety.config import FileSafetyConfig
from app.services.safety.file.file_safety.backup_to_recycle_bin import backup_to_recycle_bin
from app.services.safety.file.file_safety.collect_file_info import collect_file_info
from app.services.safety.file.file_safety.update_op_failed import update_op_failed


def execute_with_safety(operation_id: str, operation_func, *args, **kwargs) -> bool:
    """拷贝自 file_safety.py 第229-294行"""
    config = FileSafetyConfig()
    try:
        with db.get_conn("operations") as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT operation_type, source_path, destination_path, created_at
                FROM file_operations WHERE operation_id = ?
            ''', (operation_id,))
            row = cursor.fetchone()
            if not row:
                logger.error(f"Operation not found: {operation_id}")
                return False

            op_type, src_str, dst_str, created_at_str = row
            source_path = Path(src_str) if src_str else None
            dest_path = Path(dst_str) if dst_str else None
            created_at = datetime.fromisoformat(created_at_str) if isinstance(created_at_str, str) else created_at_str

            cursor.execute(
                'UPDATE file_operations SET status = ?, executed_at = ? WHERE operation_id = ?',
                (OperationStatus.EXECUTING.value, datetime.now(), operation_id),
            )

            backup_path = None
            if op_type == OperationType.DELETE.value and source_path and source_path.exists():
                backup_path = backup_to_recycle_bin(source_path)

            success = operation_func(*args, **kwargs)

            if success:
                target = dest_path if dest_path and dest_path.exists() else source_path if source_path and source_path.exists() else None
                info = collect_file_info(target) if target else {}
                executed_at = datetime.now()
                duration_ms = int((executed_at - created_at).total_seconds() * 1000) if created_at else None
                space_impact = 0
                if op_type == OperationType.DELETE.value and info.get("size"):
                    space_impact = info["size"]
                elif op_type == OperationType.CREATE.value and info.get("size"):
                    space_impact = -info["size"]

                cursor.execute('''
                    UPDATE file_operations SET status = ?, backup_path = ?, backup_expires_at = ?,
                        file_size = ?, file_hash = ?, is_directory = ?,
                        file_extension = ?, duration_ms = ?, space_impact_bytes = ?, executed_at = ?
                    WHERE operation_id = ?
                ''', (
                    OperationStatus.SUCCESS.value,
                    str(backup_path) if backup_path else None,
                    datetime.now() + timedelta(days=config.BACKUP_RETENTION_DAYS) if backup_path else None,
                    info.get("size"), info.get("hash"), info.get("is_directory", False),
                    info.get("extension"), duration_ms, space_impact, executed_at, operation_id,
                ))
                logger.info(f"Operation executed successfully: {operation_id}")
            else:
                update_op_failed(cursor, operation_id, "Operation failed")
        return success
    except Exception as e:
        logger.error(f"Error executing operation {operation_id}: {e}")
        return False
