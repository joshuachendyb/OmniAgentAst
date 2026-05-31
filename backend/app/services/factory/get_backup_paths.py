# -*- coding: utf-8 -*-
"""
get_backup_paths — 从 factory.py 拷出

拷贝来源: factory.py 第334-337行
"""

from app.services.factory.set_backup_paths import _backup_path, _config_path, _backup_lock


def get_backup_paths():
    """拷贝自 factory.py 第334-337行"""
    import app.services.factory.set_backup_paths as bp
    with bp._backup_lock:
        return bp._backup_path, bp._config_path
