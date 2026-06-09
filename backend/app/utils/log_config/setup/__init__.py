# -*- coding: utf-8 -*-
"""
setup — 从 setup.py 拆出的职责

- setup_file_handler: Logger基础设施
- setup_logger: Logger基础设施
- APILogger: API结构化日志
"""

from app.utils.log_config.setup.setup_file_handler import setup_file_handler
from app.utils.log_config.setup.setup_logger_func import setup_logger
from app.utils.log_config.setup.api_logger import APILogger

api_logger = APILogger()
logger = setup_logger("OmniAgentAst")

__all__ = [
    "setup_file_handler",
    "setup_logger",
    "APILogger",
    "api_logger",
    "logger",
]
