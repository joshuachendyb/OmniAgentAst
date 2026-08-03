# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-15 - 小欧 - execute_with_safety返回值(bool)改(bool, Optional[str]): 原仅返bool, 操作失败吞掉真实错误(如"目标路径已存在...请设置overwrite=True"), 上层只能给LLM笼统"移动/复制/删除失败", LLM无法自我纠正。改后透传真实细节, LLM可据细节重试(如带overwrite=True)。
# 2026-07-18 - 小欧 - executed_at/backup_expires_at 改 get_utc_timestamp/convert_to_utc 入库 UTC Z; duration 计算 created_at_dt 兼容老/新数据
# 2026-07-18 - 小欧 - #1 fix: MODIFY 操作也生成备份(MODIFY回滚需原文件恢复), 用 op_type in (DELETE, MODIFY) 替代仅 DELETE, 扩展且不破原有DELETE路径
"""
operation_executor — 操作执行和备份

职责: 安全执行文件操作、备份到回收站
小欧 2026-06-18 从operation_commands.py拆分，遵守SRP
"""
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Tuple
from uuid import uuid4

from app.config import get_config
from app.db import db
from app.db.models.operation_models import OperationType, OperationStatus
from app.logger import logger
from app.utils.time_utils import timestamp_for_filename
from app.utils.time_utils import get_utc_timestamp, convert_to_utc  # 小欧 2026-07-18 时间统一入库
from app.services.safety.operation_cleanup import cleanup_expired_backups
from app.services.safety.operation_recorder import (
    collect_file_info, update_op_failed,
)


class FileSafetyConfig:
    """文件安全操作配置 — 小欧 2026-07-10 从 config.py 合并至此 C-10"""
    RECYCLE_BIN_PATH: Path = Path.home() / ".omniagent" / "recycle_bin"
    BACKUP_RETENTION_DAYS: int = 5
    RECYCLE_BIN_MAX_SIZE_GB: int = 10
    PROJECT_ROOT: Path = Path(get_config().get_project_root())
    REPORT_PATH: Path = PROJECT_ROOT / "reports"

    @classmethod
    def ensure_directories(cls):
        cls.RECYCLE_BIN_PATH.mkdir(parents=True, exist_ok=True)
        cls.REPORT_PATH.mkdir(parents=True, exist_ok=True)


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
        cleanup_expired_backups()
        return backup_path
    except Exception as e:
        logger.error(f"Failed to backup file to recycle bin: {e}")
        return None


def execute_with_safety(operation_id: str, operation_func, *args, **kwargs) -> Tuple[bool, Optional[str]]:
    """安全执行文件操作（自动备份、记录结果）

    返回 (是否成功, 错误详情)：错误详情透传给上层，避免真因在链路中被吞掉 — 小欧 2026-07-15
    """
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
                return False, None

            op_type, src_str, dst_str, created_at_str = row
            source_path = Path(src_str) if src_str else None
            dest_path = Path(dst_str) if dst_str else None
            created_at_dt = datetime.fromisoformat(created_at_str.replace('Z', '+00:00')) if isinstance(created_at_str, str) else created_at_str
            if created_at_dt.tzinfo is None:
                created_at_dt = created_at_dt.replace(tzinfo=timezone.utc)

            cursor.execute(
                'UPDATE file_operations SET status = ?, executed_at = ? WHERE operation_id = ?',
                (OperationStatus.EXECUTING.value, get_utc_timestamp(), operation_id),
            )

            backup_path = None
            if source_path and source_path.exists() and op_type in (
                OperationType.DELETE.value,
                OperationType.MODIFY.value,
            ):
                backup_path = backup_to_recycle_bin(source_path)

            success_raw = operation_func(*args, **kwargs)
            # 归一化返回值：_delete_sync返回(bool,str)，_copy_sync返回bool
            success = success_raw[0] if isinstance(success_raw, tuple) else bool(success_raw)
            error_detail = success_raw[1] if isinstance(success_raw, tuple) and len(success_raw) > 1 else None

            if success:
                if op_type == OperationType.DELETE.value and backup_path and backup_path.exists():
                    info = collect_file_info(backup_path)
                else:
                    target = dest_path if dest_path and dest_path.exists() else source_path if source_path and source_path.exists() else None
                    info = collect_file_info(target) if target else {}
                executed_at = get_utc_timestamp()
                executed_at_dt = datetime.now(timezone.utc)
                duration_ms = int((executed_at_dt - created_at_dt).total_seconds() * 1000) if created_at_dt else None
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
                     convert_to_utc(datetime.now(timezone.utc) + timedelta(days=config.BACKUP_RETENTION_DAYS)) if backup_path else None,
                     info.get("size"), info.get("hash"), info.get("is_directory", False),
                     info.get("extension"), duration_ms, space_impact, get_utc_timestamp(), operation_id),
                )
                logger.debug(f"Operation executed successfully: {operation_id}")
                return True, None
            else:
                update_op_failed(cursor, operation_id, error_detail or "Operation failed")
                return False, error_detail
    except Exception as e:
        logger.error(f"Error executing operation {operation_id}: {e}")
        return False, str(e)
