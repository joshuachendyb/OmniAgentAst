# -*- coding: utf-8 -*-
"""
operation_cleanup — 操作清理

职责: 清理过期备份文件
小欧 2026-06-18 从operation_commands.py拆分，遵守SRP
"""
import shutil
from datetime import datetime
from pathlib import Path

from app.db import db
from app.utils.logger import logger
from app.services.safety.file_safety.config import FileSafetyConfig


def _get_folder_size(path: Path) -> int:
    """递归计算文件夹总字节数"""
    total = 0
    try:
        for entry in path.rglob("*"):
            if entry.is_file():
                total += entry.stat().st_size
    except Exception:
        pass
    return total


def _cleanup_by_size() -> int:
    """总大小超过上限时，从最旧的备份开始删
    
    说明：延迟导入remove_readonly是为了避免循环依赖
    (operation_cleanup→delete_file→file_safety→operation_cleanup)
    """
    from app.tools.file.delete_file import remove_readonly
    config = FileSafetyConfig()
    max_bytes = config.RECYCLE_BIN_MAX_SIZE_GB * 1024 ** 3
    recycle_path = config.RECYCLE_BIN_PATH
    if not recycle_path.exists():
        return 0

    total = _get_folder_size(recycle_path)
    if total <= max_bytes:
        return 0

    folders = sorted(
        [p for p in recycle_path.iterdir() if p.is_dir()],
        key=lambda p: p.name,
    )
    count = 0
    for folder in folders:
        if total <= max_bytes:
            break
        try:
            folder_size = _get_folder_size(folder)
            # onerror解决Windows下只读文件被copy2备份后属性锁死的问题
            shutil.rmtree(folder, onerror=remove_readonly)
            total -= folder_size
            count += 1
            logger.info(f"Size cleanup: removed {folder.name} (saved {folder_size / 1024**3:.2f}GB)")
        except Exception as e:
            logger.error(f"Failed to size-cleanup {folder}: {e}")
    return count


def cleanup_expired_backups() -> int:
    """清理过期的备份文件 + 超出大小上限时清理最旧的
    
    说明：延迟导入remove_readonly避免循环依赖；
    shutil.rmtree加onerror是因为Windows下只读文件+备份文件属性继承会导致[WinError 5]
    """
    from app.tools.file.delete_file import remove_readonly
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
                            # onerror解决Windows下只读文件备份后无法删除的问题
                            shutil.rmtree(path, onerror=remove_readonly)
                        else:
                            path.unlink()
                        count += 1
                        logger.info(f"Cleaned up expired backup: {backup_path}")
                except Exception as e:
                    logger.error(f"Failed to cleanup backup {backup_path}: {e}")
        count += _cleanup_by_size()
        return count
    except Exception as e:
        logger.error(f"Failed to cleanup expired backups: {e}")
        return count
