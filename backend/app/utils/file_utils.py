# -*- coding: utf-8 -*-
"""
文件操作公共辅助函数 — 纯文件系统操作，不依赖任何业务层

编辑历史:
  2026-08-13 小沈 P1: 从 tools/file/delete_file.py 复制迁入 remove_readonly,
    消除 safety→tools 实现依赖(safety/operation_maintenance.py 和 operation_rollback.py
    改从本文件导入, tools/file/delete_file.py 同步改从本文件导入)
  2026-08-13 小沈 P5b: 从 tools/tool_fc_helper.py 复制迁入 backup_file,
    消除 services/model/persistence.py→tools 实现依赖
"""

import os
import shutil
from typing import Any, Dict, Optional


def remove_readonly(func, path, excinfo):
    """解除只读属性后重试（shutil.rmtree onerror 回调）

    Windows下shutil.rmtree遇到只读文件会[WinError 5]拒绝访问。
    因为备份用的是shutil.copy2，原文件的只读属性被完整保留。
    onerror回调先chmod加写权限再重新执行删除，解决此问题。

    来源: 从 app/tools/file/delete_file.py 复制迁入 — 小沈 2026-08-13
    """
    os.chmod(path, os.stat(path).st_mode | 0o200)
    func(path)


def backup_file(file_path: str, backup_dir: Optional[str] = None, suffix: str = ".bak") -> Dict[str, Any]:
    """备份文件，返回纯dict

    来源: 从 app/tools/tool_fc_helper.py 复制迁入 — 小沈 2026-08-13
    【注意】本函数返回纯dict，不含build3结构。
    """
    from app.utils.time_utils import timestamp_for_filename
    file_path = os.path.abspath(file_path)
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"文件不存在: {file_path}")
    timestamp = timestamp_for_filename()
    file_name = os.path.basename(file_path)
    backup_name = f"{file_name}{suffix}_{timestamp}"
    if backup_dir is None:
        backup_dir = os.path.dirname(file_path)
    else:
        backup_dir = os.path.abspath(backup_dir)
        os.makedirs(backup_dir, exist_ok=True)
    backup_path = os.path.join(backup_dir, backup_name)
    shutil.copy2(file_path, backup_path)
    return {
        "original_path": file_path,
        "backup_path": backup_path,
        "backup_size": os.path.getsize(backup_path),
    }