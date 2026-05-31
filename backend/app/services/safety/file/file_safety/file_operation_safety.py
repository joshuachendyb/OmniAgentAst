# -*- coding: utf-8 -*-
"""
FileOperationSafety — 从 file_safety.py 拷出

拷贝来源: file_safety.py 第42-554行（类骨架）
"""

from app.services.safety.manager import SafetyHook
from app.services.safety.file.file_safety.config import FileSafetyConfig
from app.utils.logger import logger


class FileOperationSafety(SafetyHook):
    """拷贝自 file_safety.py 第42-554行 — 类骨架"""

    def __init__(self):
        self.config = FileSafetyConfig()
        self.config.ensure_directories()

    def close(self):
        logger.info("FileOperationSafety resources cleaned up")
