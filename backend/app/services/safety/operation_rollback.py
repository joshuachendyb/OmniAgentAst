# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-16 - 小欧 - rollback_session 改用 get_tracker().mark_rolled_back() 贯通 task_tracker 统计(消除跨库死链), 删除直接UPDATE旧operations表逻辑
# 2026-07-18 - 小欧 - rolled_back_at 改 get_utc_timestamp() 入库 UTC Z, 消除 datetime.now() 裸传 sqlite3
# 2026-07-18 - 小欧 - #1 fix: 新增 MODIFY/COPY/COMPRESS 三条回滚分支(MODIFY用备份还原, COPY/COMPRESS删目标); #2 fix: MOVE回滚前检测source是否被新文件占用, 先备份再移回, 杜绝覆盖丢失
"""
operation_rollback — 操作回滚

职责: 回滚单个操作、回滚整个会话
小欧 2026-06-18 从operation_commands.py拆分，遵守SRP
"""
import shutil
from pathlib import Path
from typing import Dict, Any

from app.db import db
from app.utils.time_utils import get_utc_timestamp  # 小欧 2026-07-18 时间统一入库
from app.db.models.operation_models import OperationType, OperationStatus
from app.logger import logger
from app.services.task import get_tracker


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
            if op_type == OperationType.MODIFY.value:
                if backup and Path(backup).exists():
                    backup_path = Path(backup)
                    source_path = Path(src)
                    source_path.parent.mkdir(parents=True, exist_ok=True)
                    if backup_path.is_dir():
                        shutil.copytree(backup_path, source_path, dirs_exist_ok=True)
                    else:
                        shutil.copy2(backup_path, source_path)
                    success = True
                    logger.info(f"Restored edited file: {backup} -> {source_path}")
            elif op_type == OperationType.DELETE.value:
                if backup and Path(backup).exists():
                    backup_path = Path(backup)
                    source_path = Path(src)
                    source_path.parent.mkdir(parents=True, exist_ok=True)
                    if backup_path.is_dir():
                        shutil.copytree(backup_path, source_path, dirs_exist_ok=True)
                    else:
                        shutil.copy2(backup_path, source_path)
                    success = True
                    logger.info(f"Restored deleted file: {backup} -> {source_path}")
            elif op_type == OperationType.MOVE.value:
                dest_path = Path(dst)
                source_path = Path(src)
                if dest_path.exists():
                    # 先保全当前 source（若被新文件占用）再移回，杜绝覆盖丢失 — 小欧 2026-07-18 #2 fix
                    if source_path.exists():
                        _bak = source_path.with_name(source_path.name + ".rollback_bak")
                        try:
                            source_path.rename(_bak)
                        except Exception as _e:
                            logger.error(f"MOVE rollback: backup occupied source failed: {_e}")
                            return False
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
            elif op_type in (OperationType.COPY.value, OperationType.COMPRESS.value):
                dest_path = Path(dst) if dst else Path(src)
                if dest_path.exists():
                    if dest_path.is_dir():
                        shutil.rmtree(dest_path)
                    else:
                        dest_path.unlink()
                    success = True
                    logger.info(f"Removed copied/compressed target: {dest_path}")

            if success:
                cursor.execute(
                    'UPDATE file_operations SET status = ?, rolled_back_at = ? WHERE operation_id = ?',
                    (OperationStatus.ROLLBACK.value, get_utc_timestamp(), operation_id),
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

            success_op_ids = []
            for op_id, op_type, src, dst in operations:
                success = rollback_operation(op_id)
                result["operations"].append({"operation_id": op_id, "type": op_type, "success": success})
                if success:
                    result["success"] += 1
                    success_op_ids.append(op_id)
                else:
                    result["failed"] += 1

            # 串联 task_tracker 统计（消除死链, 小欧 2026-07-16）
            # 注: 原UPDATE task_operations已删除(该表在task_tracker.db, 此处连operations.db必报错)
            if success_op_ids:
                try:
                    get_tracker().mark_rolled_back(task_id, op_ids=success_op_ids)
                except Exception as e:
                    logger.error(f"Failed to update rollback stats for {task_id}: {e}")
        logger.info(f"Task rollback completed: {task_id} - {result['success']}/{result['total']} succeeded")
        return result
    except Exception as e:
        logger.error(f"Failed to rollback session {task_id}: {e}")
        return result
