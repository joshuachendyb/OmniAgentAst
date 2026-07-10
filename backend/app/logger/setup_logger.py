# -*- coding: utf-8 -*-
"""
setup_logger — 从 setup.py 拷出

拷贝来源: setup.py 第39-100行
"""

import logging
import warnings
from typing import Optional

from app.logger.config import (
    SafeRotatingFileHandler,
    _get_log_file_path,
    _create_handler_for_logger,
)
from app.logger.config import LogConfig


def setup_file_handler() -> SafeRotatingFileHandler:
    """拷贝自 setup_file_handler.py"""
    log_file = _get_log_file_path()
    return SafeRotatingFileHandler(
        log_file,
        maxBytes=LogConfig.get_max_bytes(),
        backupCount=LogConfig.get_backup_count(),
        encoding='utf-8'
    )


def setup_logger(name: str) -> logging.Logger:
    """拷贝自 setup.py 第39-100行"""
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    log_level = getattr(logging, LogConfig.get_log_level().upper())
    is_debug = LogConfig.is_debug_mode()

    if is_debug:
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
        )
    else:
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(filename)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
        )

    file_handler = _create_handler_for_logger(name, log_level, formatter)

    if not file_handler:
        log_file = _get_log_file_path()
        warnings.warn(f"创建SafeRotatingFileHandler失败,使用普通FileHandler")
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(formatter)
        file_handler.setLevel(log_level)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.WARNING)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    logger.setLevel(log_level)
    logger.propagate = False

    return logger
