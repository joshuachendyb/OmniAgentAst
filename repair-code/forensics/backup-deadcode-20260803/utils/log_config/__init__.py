"""
日志工具模块
用于记录API请求和响应日志
支持debug模式和生产模式
"""

from .handler import SafeRotatingFileHandler, LOG_DIR
from .handler import LogConfig
from .setup_logger_func import setup_logger, setup_file_handler
from .api_logger import APILogger

api_logger = APILogger()
logger = setup_logger(__name__)

__all__ = [
    "SafeRotatingFileHandler",
    "LogConfig",
    "LOG_DIR",
    "setup_logger",
    "APILogger",
    "logger",
    "api_logger",
]
