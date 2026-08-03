
# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-10 - 小欧 - 从 services/service_manager/lifecycle.py 迁入，背 path 管理
# 2026-07-26 - 小沈 - 合并 backup_to_recycle_bin 自 operation_record，成为真正备份职责文件
"""
operation_backup — 文件备份到回收站 + 备份路径管理

职责: 备份文件/目录到回收站、管理备份路径和配置路径
小欧 2026-06-18
"""
import shutil
import threading
from pathlib import Path
from typing import Optional
from uuid import uuid4

from app.logger import logger
from app.utils.time_utils import timestamp_for_filename
from app.services.safety.operation_record import FileSafetyConfig
from app.services.safety.operation_cleanup import cleanup_expired_backups


_backup_path = None
_config_path = None
_backup_lock = threading.Lock()


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


def set_backup_paths(backup_path: str, config_path: str):
    """设置备份路径"""
    global _backup_path, _config_path
    with _backup_lock:
        _backup_path = backup_path
        _config_path = config_path


def get_backup_paths():
    """获取备份路径"""
    with _backup_lock:
        return _backup_path, _config_path


def clear_backup_paths():
    """清除备份路径"""
    global _backup_path, _config_path
    with _backup_lock:
        _backup_path = None
        _config_path = None

