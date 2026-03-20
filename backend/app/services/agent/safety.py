# -*- coding: utf-8 -*-
"""
文件操作安全服务 (File Operation Safety Service)

【重构说明】
本文件已迁移到 services/safety/file/file_safety.py
此处保留作为向后兼容层

Author: 小沈 - 2026-03-21
"""

from app.services.safety.file.file_safety import (
    FileSafetyConfig,
    FileOperationSafety,
    OperationType,
    OperationStatus,
    OperationRecord,
    get_file_safety_service,
)

__all__ = [
    "FileSafetyConfig",
    "FileOperationSafety",
    "OperationType",
    "OperationStatus",
    "OperationRecord",
    "get_file_safety_service",
]
