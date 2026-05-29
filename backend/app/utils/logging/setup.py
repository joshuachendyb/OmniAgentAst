"""
日志初始化与API日志记录器
负责 setup_logger、APILogger 及全局 logger 实例
"""

import logging
import time
import uuid
import warnings
from datetime import datetime
from pathlib import Path
from typing import Optional

from .handler import (
    SafeRotatingFileHandler,
    LOG_DIR,
    _get_log_file_path,
    _create_handler_for_logger,
)
from .config import LogConfig

_logging_configured = False
_file_handler: Optional[logging.handlers.RotatingFileHandler] = None
_console_handler: Optional[logging.StreamHandler] = None


def _setup_file_handler() -> SafeRotatingFileHandler:
    """创建文件处理器"""
    log_file = _get_log_file_path()
    _file_handler = SafeRotatingFileHandler(
        log_file,
        maxBytes=LogConfig.get_max_bytes(),
        backupCount=LogConfig.get_backup_count(),
        encoding='utf-8'
    )
    return _file_handler


def setup_logger(name: str) -> logging.Logger:
    """
    设置并返回logger实例
    每个logger有自己的处理器，不依赖根logger，避免重复日志

    Args:
        name: logger名称

    Returns:
        logging.Logger: 配置好的logger
    """
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
        _file_handler = _setup_file_handler()
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


logger = setup_logger("OmniAgentAst")


class APILogger:
    """API请求日志记录器"""

    _instance: Optional['APILogger'] = None

    def __init__(self):
        """初始化logger和状态"""
        self.logger: logging.Logger = setup_logger("OmniAgentAst.API")
        self.debug_mode: bool = LogConfig.is_debug_mode()
        self._request_times: dict = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.__init__()
        return cls._instance

    def _should_log(self, level: int) -> bool:
        """检查是否应该记录该级别日志"""
        return self.logger.isEnabledFor(level)

    def log_request_start(self, provider: str, model: str, message_len: int, history_count: int = 0) -> str:
        """
        记录请求开始，返回请求ID用于后续关联

        Returns:
            str: 请求ID
        """
        request_id = str(uuid.uuid4())[:8]
        self._request_times[request_id] = {
            'start_time': time.time(),
            'provider': provider,
            'model': model
        }

        self.logger.info(
            f"[{provider}] 请求开始 | ID: {request_id} | 模型: {model} | "
            f"消息长度: {message_len} | 历史消息数: {history_count}"
        )
        if self.debug_mode:
            self.logger.debug(f"[{provider}] 调试模式: 消息内容长度={message_len}")

        return request_id

    def log_response_with_time(self, request_id: str, provider: str, status_code: int,
                               content_len: int = 0, error: Optional[str] = None):
        """记录响应并计算耗时"""

        elapsed_time = 0.0
        model_info = ""
        if request_id in self._request_times:
            request_info = self._request_times[request_id]
            elapsed_time = time.time() - request_info['start_time']
            model_info = f"模型: {request_info['model']} | "
            del self._request_times[request_id]

        if error:
            self.logger.error(
                f"[{provider}] 响应错误 | ID: {request_id} | {model_info}"
                f"状态码: {status_code} | 耗时: {elapsed_time:.2f}s | 错误: {error}"
            )
        else:
            self.logger.info(
                f"[{provider}] 响应成功 | ID: {request_id} | {model_info}"
                f"状态码: {status_code} | 内容长度: {content_len} | 耗时: {elapsed_time:.2f}s"
            )

        return elapsed_time

    def log_timeout(self, provider: str, timeout_seconds: int):
        """记录超时"""
        self.logger.warning(
            f"[{provider}] 请求超时 | 超时时间: {timeout_seconds}秒"
        )

    def log_switch(self, from_provider: str, to_provider: str, success: bool, reason: Optional[str] = None):
        """记录提供商切换"""
        if success:
            self.logger.info(f"[切换] {from_provider} -> {to_provider} | 成功")
        else:
            self.logger.error(
                f"[切换] {from_provider} -> {to_provider} | 失败 | 原因: {reason}"
            )

    def log_validation(self, provider: str, model: str, success: bool, message: str):
        """记录服务验证"""
        if success:
            self.logger.info(f"[{provider}] 验证成功 | 模型: {model}")
        else:
            self.logger.warning(
                f"[{provider}] 验证失败 | 模型: {model} | 原因: {message}"
            )

    def log_error(self, provider: str, error: str, exc_info: Optional[Exception] = None):
        """记录详细错误信息"""
        if exc_info and self.debug_mode:
            self.logger.exception(f"[{provider}] 异常: {error}")
        else:
            self.logger.error(f"[{provider}] 错误: {error}")


api_logger = APILogger()
