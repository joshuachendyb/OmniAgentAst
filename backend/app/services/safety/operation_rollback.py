# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-16 - 小欧 - rollback_session 改用 get_tracker().mark_rolled_back() 贯通 task_tracker 统计(消除跨库死链), 删除直接UPDATE旧operations表逻辑
# 2026-07-18 - 小欧 - rolled_back_at 改 get_utc_timestamp() 入库 UTC Z, 消除 datetime.now() 裸传 sqlite3
# 2026-07-18 - 小欧 - #1 fix: 新增 MODIFY/COPY/COMPRESS 三条回滚分支(MODIFY用备份还原, COPY/COMPRESS删目标); #2 fix: MOVE回滚前检测source是否被新文件占用, 先备份再移回, 杜绝覆盖丢失
# 2026-07-18 - 小欧 - #16 fix: rollback_session失败时添加warning提示而非静默
# 2026-08-08 - 小欧 - 全程统一本地时区: rolled_back_at 改 get_local_iso_timestamp() 本地ISO无Z入库
# 2026-08-11 - 小欧 - 三堂会审: 备份恢复链路长路径化 + MODIFY/DELETE恢复分支合并(DRY)。
#   长路径备份(\\?\前缀写入回收站)用普通Path.exists()返回False→回滚失效, 与备份/清理长路径支持闭环;
#   原MODIFY与DELETE恢复逻辑完全相同, 违反DRY, 合并为同一分支
# 2026-08-11 - 小欧 - 三堂会审复核落地(P1-1): MOVE/CREATE/COPY/COMPRESS 回滚分支长路径化, 与MODIFY/DELETE恢复链路闭环
#   (普通Path.exists()/rename()/rmtree()/unlink()对超长路径(>260字符)静默失效→回滚跳过→数据丢失/空间泄漏);
#   补 remove_readonly 函数内延迟导入(防NameError+循环依赖, 对齐 operation_cleanup 模式)
"""
operation_rollback — 操作回滚

职责: 回滚单个操作、回滚整个会话
小欧 2026-06-18 从operation_commands.py拆分，遵守SRP
"""
import os
import shutil
from pathlib import Path
from typing import Dict, Any

from app.db import db
from app.utils.path_utils import to_win_long_path
from app.utils.time_utils import get_local_iso_timestamp  # 小欧 2026-08-08 全程统一本地时区
from app.db.models.operation_models import OperationType, OperationStatus
from app.logger import logger
from app.services.task import get_tracker


def rollback_operation(operation_id: str) -> bool:
    """回滚单个文件操作"""
    # 函数内延迟导入 remove_readonly, 避免循环依赖(delete_file→app.services.safety→operation_record→operation_backup→operation_cleanup) — 小欧 2026-08-11
    from app.tools.file.delete_file import remove_readonly
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
            if op_type in (OperationType.MODIFY.value, OperationType.DELETE.value):
                # 2026-08-11 小欧 三堂会审: 恢复链路长路径化(备份\\?\前缀写入, 普通Path.exists()对超长路径为False→回滚失效);
                #   MODIFY/DELETE恢复逻辑相同, 合并为同一分支(DRY)
                if backup and os.path.exists(to_win_long_path(Path(backup))):
                    backup_path = Path(backup)
                    source_path = Path(src)
                    os.makedirs(to_win_long_path(source_path.parent), exist_ok=True)
                    backup_long = to_win_long_path(backup_path)
                    src_long = to_win_long_path(source_path)
                    if os.path.isdir(backup_long):
                        shutil.copytree(backup_long, src_long, dirs_exist_ok=True)
                    else:
                        shutil.copy2(backup_long, src_long)
                    success = True
                    logger.info(f"Restored {op_type}: {backup} -> {source_path}")
            elif op_type == OperationType.MOVE.value:
                dest_path = Path(dst)
                source_path = Path(src)
                dest_long = to_win_long_path(dest_path)
                src_long = to_win_long_path(source_path)
                if os.path.exists(dest_long):
                    # 先保全当前 source（若被新文件占用）再移回，杜绝覆盖丢失 — 小欧 2026-07-18 #2 fix; 2026-08-11 长路径化
                    if os.path.exists(src_long):
                        _bak = source_path.with_name(source_path.name + ".rollback_bak")
                        _bak_long = to_win_long_path(_bak)
                        try:
                            os.rename(src_long, _bak_long)
                        except Exception as _e:
                            logger.error(f"MOVE rollback: backup occupied source failed: {_e}")
                            return False
                    os.rename(dest_long, src_long)
                    success = True
                    logger.info(f"Moved back: {dest_path} -> {source_path}")
            elif op_type == OperationType.CREATE.value:
                dest_path = Path(dst) if dst else Path(src)
                dest_long = to_win_long_path(dest_path)
                if os.path.exists(dest_long):
                    if os.path.isdir(dest_long):
                        shutil.rmtree(dest_long, onerror=remove_readonly)
                    else:
                        os.unlink(dest_long)
                    success = True
                    logger.info(f"Removed created file: {dest_path}")
            elif op_type in (OperationType.COPY.value, OperationType.COMPRESS.value):
                dest_path = Path(dst) if dst else Path(src)
                dest_long = to_win_long_path(dest_path)
                if os.path.exists(dest_long):
                    if os.path.isdir(dest_long):
                        shutil.rmtree(dest_long, onerror=remove_readonly)
                    else:
                        os.unlink(dest_long)
                    success = True
                    logger.info(f"Removed copied/compressed target: {dest_path}")

            if success:
                cursor.execute(
                    'UPDATE file_operations SET status = ?, rolled_back_at = ? WHERE operation_id = ?',
                    (OperationStatus.ROLLBACK.value, get_local_iso_timestamp(), operation_id),
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
        if result["failed"] > 0:
            result["warning"] = (
                f"有 {result['failed']} 个操作回滚失败，可能不可恢复，"
                f"请检查文件备份状态"
            )
        logger.info(f"Task rollback completed: {task_id} - {result['success']}/{result['total']} succeeded")
        return result
    except Exception as e:
        logger.error(f"Failed to rollback session {task_id}: {e}")
        return result
