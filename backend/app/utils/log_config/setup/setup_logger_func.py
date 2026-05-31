# -*- coding: utf-8 -*-
"""
setup_logger — 从 setup.py 拷出

拷贝来源: setup.py 第39-100行
"""

import logging
import warnings
from typing import Optional

from app.utils.log_config.handler import (
    SafeRotatingFileHandler,
    _get_log_file_path,
    _create_handler_for_logger,
)
from app.utils.log_config.config import LogConfig
from app.utils.log_config.setup.setup_file_handler import setup_file_handler

_logging_configured = False
_file_handler: Optional[logging.handlers.RotatingFileHandler] = None
_console_handler: Optional[logging.StreamHandler] = None


def setup_logger(name: str) -> logging.Logger:
    """拷贝自 setup.py 第39-100行"""
    global _logging_configured, _file_handler, _console_handler

    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    log_level = getattr(logging, LogConfig.get_log_level().upper())
    is_debug = LogConfig.is_debug_mode()

    if is_debug:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(filename)s - [%(lineno)d] - %(message)s'
        )
    else:
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(filename)s - %(message)s'
        )

    if not _logging_configured:
        _file_handler = setup_file_handler()
        _file_handler.setFormatter(formatter)
        _file_handler.setLevel(log_level)

        _console_handler = logging.StreamHandler()
        _console_handler.setFormatter(formatter)
        _console_handler.setLevel(logging.DEBUG if is_debug else logging.WARNING)

        _logging_configured = True

    if _file_handler and _console_handler:
        file_handler = _create_handler_for_logger(name, log_level, formatter)

        if not file_handler:
            log_file = _get_log_file_path()
            warnings.warn(f"创建SafeRotatingFileHandler失败，使用普通FileHandler")
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setFormatter(formatter)
            file_handler.setLevel(log_level)

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.setLevel(logging.DEBUG if is_debug else logging.WARNING)

        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    logger.setLevel(log_level)
    logger.propagate = False

    return logger
