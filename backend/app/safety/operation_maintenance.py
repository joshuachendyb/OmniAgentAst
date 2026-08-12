
# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-12 - 小欧 - 从 operation_cleanup.py 承接清理职责(A2-内部环, 方案4.2.3步骤2): cleanup_expired_backups/_get_folder_size/_cleanup_by_size 整体复制,
#   FileSafetyConfig 导入改 app.services.safety.models(原 operation_record, 已独立); 其余逻辑一字不改
"""
operation_maintenance — 备份回收站维护

职责: 清理过期备份文件 + 回收站超限清理(归口维护职责, 与备份职责 operation_backup 解耦)
小欧 2026-08-12 承接原 operation_cleanup.py
"""
import os
import shutil
from pathlib import Path

from app.db import db
from app.logger import logger
from app.utils.path_utils import to_win_long_path
from app.utils.time_utils import get_local_iso_timestamp  # 小欧 2026-08-08 全程统一本地时区


def _get_folder_size(path: Path) -> int:
    """递归计算文件夹总字节数（长路径支持: 深嵌套子项普通Path无法遍历, 需\\?\前缀）"""
    total = 0
    try:
        for entry in Path(to_win_long_path(path)).rglob("*"):
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
    from app.safety.models import FileSafetyConfig
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
            # onerror解决Windows下只读文件被copy2备份后属性锁死的问题; 长路径rmtree带\\?\前缀递归删内部超长子项
            shutil.rmtree(to_win_long_path(folder), onerror=remove_readonly)
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
                (get_local_iso_timestamp(),),
            )
            rows = cursor.fetchall()
            for (backup_path,) in rows:
                try:
                    path = Path(backup_path)
                    long_path = to_win_long_path(path)
                    if os.path.exists(long_path):
                        if os.path.isdir(long_path):
                            # onerror解决Windows下只读文件备份后无法删除的问题; 长路径rmtree递归删内部超长子项
                            shutil.rmtree(long_path, onerror=remove_readonly)
                        else:
                            # 只读文件: chmod加写权限后再删(同remove_readonly逻辑) — 小欧 2026-07-26
                            os.chmod(long_path, os.stat(long_path).st_mode | 0o200)
                            try:
                                os.unlink(long_path)
                            except PermissionError:
                                # 首次chmod可能不够(Windows只读属性), 再试一次更激进
                                os.chmod(long_path, 0o666)
                                os.unlink(long_path)
                        count += 1
                        logger.info(f"Cleaned up expired backup: {backup_path}")
                except Exception as e:
                    logger.error(f"Failed to cleanup backup {backup_path}: {e}")
        count += _cleanup_by_size()
        return count
    except Exception as e:
        logger.error(f"Failed to cleanup expired backups: {e}")
        return count
