# -*- coding: utf-8 -*-
"""
文件操作命令 — 写入/备份/回滚/清理 — 小健 2026-06-17

合并自: record_operation, update_op_failed, backup_to_recycle_bin, collect_file_info,
        execute_with_safety, rollback_operation, rollback_session, cleanup_expired_backups
"""
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional
from uuid import uuid4

from app.db import db
from app.db.models.operation_enums import OperationType, OperationStatus
from app.utils.logger import logger
from app.utils.time_utils import timestamp_for_filename
from app.services.safety.hash_helper import compute_file_hash
from app.services.safety.file_safety.config import FileSafetyConfig


def collect_file_info(path: Path) -> Dict[str, Any]:
    if not path or not path.exists():
        return {"size": None, "hash": None, "extension": None, "is_directory": False}
    info = {"size": path.stat().st_size, "is_directory": path.is_dir()}
    if path.is_file():
        info["hash"] = compute_file_hash(path)
        info["extension"] = path.suffix.lower() if path.suffix else None
    else:
        info["hash"] = None
        info["extension"] = None
    return info


def update_op_failed(cursor, operation_id: str, error_message: str):
    cursor.execute(
        'UPDATE file_operations SET status = ?, error_message = ? WHERE operation_id = ?',
        (OperationStatus.FAILED.value, error_message, operation_id),
    )


def backup_to_recycle_bin(source_path: Path) -> Optional[Path]:
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


def record_operation(
    task_id: str,
    operation_type: Optional[str] = None,
    source_path: Optional[Path] = None,
    destination_path: Optional[Path] = None,
    sequence_number: int = 0,
    file_size: Optional[int] = None,
) -> str:
    operation_id = f"op-{uuid4().hex}"
    space_impact_bytes = None
    if file_size is not None:
        if operation_type == OperationType.CREATE:
            space_impact_bytes = -file_size
        elif operation_type == OperationType.DELETE:
            space_impact_bytes = file_size
    try:
        with db.get_conn("operations") as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''INSERT INTO file_operations
                (operation_id, task_id, operation_type, status, source_path,
                 destination_path, sequence_number, file_size, space_impact_bytes, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (operation_id, task_id, operation_type.value,
                 OperationStatus.PENDING.value,
                 str(source_path) if source_path else None,
                 str(destination_path) if destination_path else None,
                 sequence_number, file_size, space_impact_bytes, datetime.now()),
            )
        logger.debug(f"Operation recorded: {operation_id} - {operation_type.value}")
        return operation_id
    except Exception as e:
        logger.error(f"Failed to record operation: {e}")
        raise


def execute_with_safety(operation_id: str, operation_func, *args, **kwargs) -> bool:
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


def rollback_operation(operation_id: str) -> bool:
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


def cleanup_expired_backups() -> int:
    count = 0
    try:
        with db.get_conn("operations") as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT backup_path FROM file_operations WHERE backup_expires_at < ? AND backup_path IS NOT NULL',
                (datetime.now(),),
            )
            rows = cursor.fetchall()
            for (backup_path,) in rows:
                try:
                    path = Path(backup_path)
                    if path.exists():
                        if path.is_dir():
                            shutil.rmtree(path)
                        else:
                            path.unlink()
                        count += 1
                        logger.info(f"Cleaned up expired backup: {backup_path}")
                except Exception as e:
                    logger.error(f"Failed to cleanup backup {backup_path}: {e}")
        return count
    except Exception as e:
        logger.error(f"Failed to cleanup expired backups: {e}")
        return count