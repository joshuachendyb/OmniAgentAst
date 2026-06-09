# -*- coding: utf-8 -*-
"""
clear_backup_paths — 从 factory.py 拷出

拷贝来源: factory.py 第340-344行
"""

import app.services.factory.set_backup_paths as bp


def clear_backup_paths():
    """拷贝自 factory.py 第340-344行"""
    with bp._backup_lock:
        bp._backup_path = None
        bp._config_path = None
