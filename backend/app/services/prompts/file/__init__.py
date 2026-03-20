# -*- coding: utf-8 -*-
"""
Prompts/File 模块 - 文件操作Prompt模板

【迁移说明】
本目录是从 agent/prompts.py 迁移而来
迁移时间：2026-03-21

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
