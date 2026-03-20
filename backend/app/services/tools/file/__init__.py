# -*- coding: utf-8 -*-
"""
Tools/File 模块 - 文件操作工具集

【迁移说明】
本目录是从 agent/tools.py 迁移而来
迁移时间：2026-03-21

Author: 小沈 - 2026-03-21
"""

from app.services.tools.file.file_schema import (
    ReadFileInput,
    WriteFileInput,
    ListDirectoryInput,
    DeleteFileInput,
    MoveFileInput,
    SearchFilesInput,
    GenerateReportInput,
)
from app.services.tools.file.file_tools import (
    # 常量
    PAGE_SIZE,
    MAX_PAGE_SIZE,
    ALLOWED_PATHS,
    _get_default_allowed_paths,
    # 类
    FileTools,
    ToolDefinition,
    # 装饰器
    register_tool,
    # 模型
    ReadFileInput,
    WriteFileInput,
    ListDirectoryInput,
    DeleteFileInput,
    MoveFileInput,
    SearchFilesInput,
    GenerateReportInput,
    # 工具函数
    get_registered_tools,
    get_tool,
    encode_page_token,
    decode_page_token,
    _to_unified_format,
    _generate_summary,
    get_file_tools,
)

__all__ = [
    # Schema模型
    "ReadFileInput",
    "WriteFileInput",
    "ListDirectoryInput",
    "DeleteFileInput",
    "MoveFileInput",
    "SearchFilesInput",
    "GenerateReportInput",
    # 常量
    "PAGE_SIZE",
    "MAX_PAGE_SIZE",
    "ALLOWED_PATHS",
    "_get_default_allowed_paths",
    # 类
    "FileTools",
    "ToolDefinition",
    # 装饰器
    "register_tool",
    # 工具函数
    "get_registered_tools",
    "get_tool",
    "encode_page_token",
    "decode_page_token",
    "_to_unified_format",
    "_generate_summary",
    "get_file_tools",
]
