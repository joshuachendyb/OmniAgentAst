# -*- coding: utf-8 -*-
"""
set_backup_paths — 从 factory.py 拷出

拷贝来源: factory.py 第327-331行
"""

import threading

_backup_path = None
_config_path = None
_backup_lock = threading.Lock()


def set_backup_paths(backup_path: str, config_path: str):
    """拷贝自 factory.py 第327-331行"""
    global _backup_path, _config_path
    with _backup_lock:
        _backup_path = backup_path
        _config_path = config_path
