# -*- coding: utf-8 -*-
"""
_setup_file_handler — 从 setup.py 拷出

拷贝来源: setup.py 第27-36行
"""

import logging
from typing import Optional

from app.utils.log_config.handler import (
    SafeRotatingFileHandler,
    _get_log_file_path,
)
from app.utils.log_config.config import LogConfig


def setup_file_handler() -> SafeRotatingFileHandler:
    """拷贝自 setup.py 第27-36行"""
    log_file = _get_log_file_path()
    _file_handler = SafeRotatingFileHandler(
        log_file,
        maxBytes=LogConfig.get_max_bytes(),
        backupCount=LogConfig.get_backup_count(),
        encoding='utf-8'
    )
    return _file_handler
