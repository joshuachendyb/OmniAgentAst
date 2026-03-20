# -*- coding: utf-8 -*-
"""
文件操作Prompt模板 (File Operation Prompts)

【重构说明】
本文件已迁移到 services/prompts/file/file_prompts.py
此处保留作为向后兼容层

Author: 小沈 - 2026-03-21
"""

from app.services.prompts.file.file_prompts import (
    FileOperationPrompts,
    TaskTemplates,
)

__all__ = [
    "FileOperationPrompts",
    "TaskTemplates",
]
