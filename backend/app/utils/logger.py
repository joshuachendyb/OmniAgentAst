"""
日志工具模块 — 公开入口（实现见 app.utils.log_config 包）

【10大原则规范 2026-05-30 小健】
- SRP: 本文件仅做入口导出，实现拆分到 log_config/ 子包
- DRY: 单一入口（全项目99个文件统一从 logger.py 导入）
- KISS: 保持简单导出，不混入实现逻辑
- 禁止向后兼容: log_config 是唯一实现路径，本文件是规范公开入口
"""

from app.utils.log_config import (
    SafeRotatingFileHandler,
    LogConfig,
    LOG_DIR,
    setup_logger,
    APILogger,
    logger,
    api_logger,
)

__all__ = [
    "SafeRotatingFileHandler",
    "LogConfig",
    "LOG_DIR",
    "setup_logger",
    "APILogger",
    "logger",
    "api_logger",
]
