# -*- coding: utf-8 -*-
"""
setup_logger — 全局共享一个 SafeRotatingFileHandler 实例
- 修改人 小欧 2026-07-11
- 所有 logger 共用一个文件 handler，消灭多 handler 写同一文件的 Windows rename 锁竞争
"""

import logging
from typing import Optional

from app.logger.config import SafeRotatingFileHandler, LogConfig


# ---- 全局共享文件 handler ------------------------------------------------
# 关键：整个进程只创建一个 SafeRotatingFileHandler，所有 logger 共用
# 根因：7个 handler 分别写同一文件 → Windows rename 被其他句柄锁住
# 修复：1 handler → 1 文件描述符 → 0 竞争
# — 小欧 2026-07-11

_FILE_HANDLER: Optional[SafeRotatingFileHandler] = None


def _get_shared_handler() -> SafeRotatingFileHandler:
    """获取全局唯一的文件 handler — 小欧 2026-07-11"""
    global _FILE_HANDLER
    if _FILE_HANDLER is None:
        from app.logger.config import _get_log_file_path
        log_file = _get_log_file_path()
        _FILE_HANDLER = SafeRotatingFileHandler(
            log_file,
            maxBytes=LogConfig.get_max_bytes(),
            backupCount=LogConfig.get_backup_count(),
            encoding='utf-8',
        )
    return _FILE_HANDLER


# ---- Console 截断 Formatter --------------------------------------------

class _TruncateConsoleFormatter(logging.Formatter):
    """console 日志截断 Formatter — 写文件完整，console 只显示前 100 字符 — 小欧 2026-07-11"""
    def format(self, record):
        msg = super().format(record)
        if len(msg) > 100:
            msg = msg[:100] + f"...(截断{len(msg)-100}字符)"
        return msg


# ---- setup_logger -----------------------------------------------------

def setup_logger(name: str) -> logging.Logger:
    """
    创建或获取指定名称的 logger
    - 所有 logger 共享同一个文件 handler（全局单例）
    - 每个 logger 独立拥有一个 console handler
    — 小欧 2026-07-11
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    log_level = getattr(logging, LogConfig.get_log_level().upper())
    is_debug = LogConfig.is_debug_mode()

    # formatter — 文件 handler 和 console handler 共用
    if is_debug:
        _fmt = '%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
    else:
        _fmt = '%(asctime)s - %(levelname)s - %(filename)s - %(message)s'
    formatter = logging.Formatter(_fmt, datefmt='%Y-%m-%d %H:%M:%S')

    # 文件 handler — 全局共享
    file_handler = _get_shared_handler()
    file_handler.setFormatter(formatter)
    file_handler.setLevel(log_level)

    # console handler — 每 logger 独立
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(
        _TruncateConsoleFormatter(fmt=_fmt, datefmt='%Y-%m-%d %H:%M:%S')
    )
    console_handler.setLevel(logging.WARNING)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    logger.setLevel(log_level)
    logger.propagate = False

    return logger
