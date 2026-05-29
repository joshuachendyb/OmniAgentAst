"""
安全轮转文件处理器
负责日志文件的轮转与错误保护
"""

import logging
import logging.handlers
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

logging.raiseExceptions = False

# 延迟导入，避免循环依赖（_create_handler_for_logger 内部使用）
from .config import LogConfig

LOG_DIR = Path(__file__).parent.parent.parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)


class SafeRotatingFileHandler(logging.handlers.RotatingFileHandler):
    """安全的轮转文件处理器，捕获轮转错误避免程序崩溃"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._current_date = datetime.now().strftime('%Y-%m-%d')
        self._logger_name = None

    def set_logger_name(self, name: str):
        """设置logger名称，用于获取对应的logger进行Handler替换"""
        self._logger_name = name

    def _check_and_rotate_by_date(self):
        """检查日期变化，必要时轮转日志文件"""

        today = datetime.now().strftime('%Y-%m-%d')

        if self._current_date != today:
            old_date = self._current_date
            self._current_date = today

            print(f"[Logger] 日志文件轮转: {old_date} -> {today}")

            if self._logger_name:
                try:
                    logger = logging.getLogger(self._logger_name)

                    self.close()
                    if self in logger.handlers:
                        logger.removeHandler(self)

                    new_handler = _create_handler_for_logger(
                        self._logger_name,
                        logger.level,
                        logger.handlers[0].formatter if logger.handlers else None
                    )

                    if new_handler:
                        logger.addHandler(new_handler)

                except Exception as e:
                    print(f"[Logger] 日志文件切换失败: {e}")

    def emit(self, record):
        self._check_and_rotate_by_date()

        try:
            super().emit(record)
        except PermissionError:
            sys.stderr.write(f"[Logger] 日志写入权限不足: {record.getMessage()}\n")
        except Exception as e:
            sys.stderr.write(f"[Logger] 日志写入失败: {e}\n")


def _get_log_file_path() -> Path:
    """获取当日日志文件路径"""
    return LOG_DIR / f"app_{datetime.now().strftime('%Y-%m-%d')}.log"


def _create_handler_for_logger(logger_name: str, level: int = None, formatter: logging.Formatter = None) -> Optional[SafeRotatingFileHandler]:
    """
    为指定logger创建新的文件处理器（使用当前日期的文件名）

    Args:
        logger_name: logger名称
        level: 日志级别（可选）
        formatter: 日志格式（可选）

    Returns:
        SafeRotatingFileHandler: 新的文件处理器，失败返回None
    """
    try:
        log_file = _get_log_file_path()
        handler = SafeRotatingFileHandler(
            log_file,
            maxBytes=LogConfig.get_max_bytes(),
            backupCount=LogConfig.get_backup_count(),
            encoding='utf-8'
        )
        handler.set_logger_name(logger_name)

        if formatter:
            handler.setFormatter(formatter)

        if level:
            handler.setLevel(level)

        return handler
    except Exception as e:
        print(f"[Logger] 创建文件处理器失败: {e}")
        return None
