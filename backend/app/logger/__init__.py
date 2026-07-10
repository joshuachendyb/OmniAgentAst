"""
日志工具模块 — 统一入口
整合 log_config(通用日志)

创建时间: 2026-07-10
迁移更新: 2026-07-10 小欧 — 从 utils/log_config/ 迁入合并
"""

from app.logger.config import SafeRotatingFileHandler, LogConfig, LOG_DIR
from app.logger.setup_logger import setup_logger
from app.logger.api_logger import APILogger

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
