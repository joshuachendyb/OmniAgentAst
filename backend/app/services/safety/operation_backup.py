
# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-10 - 小欧 - 从 services/service_manager/lifecycle.py 迁入，背 path 管理
# 2026-07-26 - 小沈 - 合并 backup_to_recycle_bin 自 operation_record，成为真正备份职责文件
# 2026-08-11 - 小欧 - 长路径支持(北京老陈驱动): 源/目标加\\?\前缀绕过MAX_PATH(260)限制,
#   解决深嵌套目录(递归自复制套娃)备份WinError 206路径超长整体失败致"无备份删除"历史事故
# 2026-08-11 - 小欧 - _win_long_path 提为全局公用 app/utils/path_utils.to_win_long_path
#   (三堂会审: 清理链路 operation_cleanup 需同用长路径, 否则超长备份永远清不掉; 提公共层避免循环依赖)
# 2026-08-12 - 小欧 - A2-内部环(方案4.2.3步骤3): FileSafetyConfig 导入改 models.py, cleanup_expired_backups 导入改 operation_maintenance.py
"""
operation_backup — 文件备份到回收站 + 备份路径管理

职责: 备份文件/目录到回收站、管理备份路径和配置路径
小欧 2026-06-18
"""
import os
import shutil
import threading
from pathlib import Path
from typing import Optional
from uuid import uuid4

from app.logger import logger
from app.utils.path_utils import to_win_long_path
from app.utils.time_utils import timestamp_for_filename
from app.services.safety.models import FileSafetyConfig
from app.services.safety.operation_maintenance import cleanup_expired_backups


_backup_path = None
_config_path = None
_backup_lock = threading.Lock()


def backup_to_recycle_bin(source_path: Path) -> Optional[Path]:
    r"""备份文件到回收站 — 小欧 2026-08-11 长路径支持: 源/目标加\\?\前缀,
    解决深嵌套目录(递归自复制套娃)备份时 WinError 206 路径超长整体失败。
    """
    config = FileSafetyConfig()
    try:
        timestamp = timestamp_for_filename()
        backup_dir = config.RECYCLE_BIN_PATH / f"{timestamp}_{uuid4().hex[:8]}"
        os.makedirs(to_win_long_path(backup_dir), exist_ok=True)
        backup_path = backup_dir / source_path.name
        src_long = to_win_long_path(source_path)
        dst_long = to_win_long_path(backup_path)
        if os.path.isdir(src_long):
            shutil.copytree(src_long, dst_long)
        else:
            shutil.copy2(src_long, dst_long)
        logger.info(f"File backed up to recycle bin: {source_path} -> {backup_path}")
        cleanup_expired_backups()
        return backup_path
    except Exception as e:
        logger.warning(f"Failed to backup file to recycle bin: {e}")  # 2026-08-11 小欧 error→warning: 备份失败不阻断操作, 仅提示(北京老陈驱动)
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

