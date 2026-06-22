# -*- coding: utf-8 -*-
"""
operation_executor — 操作执行和备份

职责: 安全执行文件操作、备份到回收站
小欧 2026-06-18 从operation_commands.py拆分，遵守SRP
"""
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from uuid import uuid4

from app.db import db
from app.db.models.operation_enums import OperationType, OperationStatus
from app.utils.logger import logger
from app.utils.time_utils import timestamp_for_filename
from app.services.safety.file_safety.config import FileSafetyConfig
from app.services.safety.file_safety.operation_recorder import (
    collect_file_info, update_op_failed,
)


def backup_to_recycle_bin(source_path: Path) -> Optional[Path]:
    """备份文件到回收站"""
    config = FileSafetyConfig()
    try:
        timestamp = timestamp_for_filename()
        backup_dir = config.RECYCLE_BIN_PATH / f"{timestamp}_{uuid4().hex[:8]}"
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_path = backup_dir / source_path.name
        if source_path.is_dir():
            shutil.copytree(source_path, backup_path)
        else:
            shutil.copy2(source_path, backup_path)
        logger.info(f"File backed up to recycle bin: {source_path} -> {backup_path}")
        return backup_path
    except Exception as e:
        logger.error(f"Failed to backup file to recycle bin: {e}")
        return None


def execute_with_safety(operation_id: str, operation_func, *args, **kwargs) -> bool:
    """安全执行文件操作（自动备份、记录结果）"""
    config = FileSafetyConfig()
    try:
        with db.get_conn("operations") as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT operation_type, source_path, destination_path, created_at FROM file_operations WHERE operation_id = ?',
                (operation_id,),
            )
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
                cursor.execute(
                    '''UPDATE file_operations SET status = ?, backup_path = ?, backup_expires_at = ?,
                        file_size = ?, file_hash = ?, is_directory = ?,
                        file_extension = ?, duration_ms = ?, space_impact_bytes = ?, executed_at = ?
                    WHERE operation_id = ?''',
                    (OperationStatus.SUCCESS.value,
                     str(backup_path) if backup_path else None,
                     datetime.now() + timedelta(days=config.BACKUP_RETENTION_DAYS) if backup_path else None,
                     info.get("size"), info.get("hash"), info.get("is_directory", False),
                     info.get("extension"), duration_ms, space_impact, executed_at, operation_id),
                )
                logger.info(f"Operation executed successfully: {operation_id}")
            else:
                update_op_failed(cursor, operation_id, "Operation failed")
        return success
    except Exception as e:
        logger.error(f"Error executing operation {operation_id}: {e}")
        return False
