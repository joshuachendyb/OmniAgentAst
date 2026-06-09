# -*- coding: utf-8 -*-
"""
FileOperationSafety — 文件操作安全服务

小沈 - 2026-06-09 删除SafetyHook继承(SafetyHook已删除)
"""

from app.services.safety.file.file_safety.config import FileSafetyConfig
from app.utils.logger import logger


class FileOperationSafety:

    def __init__(self):
        self.config = FileSafetyConfig()
        self.config.ensure_directories()

    def close(self):
        logger.info("FileOperationSafety resources cleaned up")
