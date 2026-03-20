# -*- coding: utf-8 -*-
"""
文件操作工具集 (File Operation Tools)

【重构说明】
本文件已迁移到 services/tools/file/file_tools.py
此处保留作为向后兼容层

Author: 小沈 - 2026-03-21
"""

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
    # FileToolsConfig (如果存在)
)

# 尝试导入 FileToolsConfig (如果存在)
try:
    from app.services.tools.file.file_tools import FileToolsConfig
except ImportError:
    FileToolsConfig = None

__all__ = [
    # 常量
    "PAGE_SIZE",
    "MAX_PAGE_SIZE",
    "ALLOWED_PATHS",
    "_get_default_allowed_paths",
    # 类
    "FileTools",
    "ToolDefinition",
    "FileToolsConfig",
    # 装饰器
    "register_tool",
    # 模型
    "ReadFileInput",
    "WriteFileInput",
    "ListDirectoryInput",
    "DeleteFileInput",
    "MoveFileInput",
    "SearchFilesInput",
    "GenerateReportInput",
    # 工具函数
    "get_registered_tools",
    "get_tool",
    "encode_page_token",
    "decode_page_token",
    "_to_unified_format",
    "_generate_summary",
    # 向后兼容的 get_file_tools
    "get_file_tools",
]

# 向后兼容的 get_file_tools
from app.services.tools.file.file_tools import get_file_tools
