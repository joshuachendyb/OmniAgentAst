# -*- coding: utf-8 -*-
"""
operation_backup — 备份路径管理
从 services/service_manager/lifecycle.py 迁入
小欧 2026-07-10
"""

import threading

_backup_path = None
_config_path = None
_backup_lock = threading.Lock()


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
