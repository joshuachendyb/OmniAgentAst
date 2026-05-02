# -*- coding: utf-8 -*-
"""
Tools/File 模块 - 文件操作工具集

【重构说明】2026-04-26 小健
- file_tools.py: FileTools 类 + 实用函数
- file_register.py: 到 tool_registry 的注册
- tool_registry: 唯一注册中心

Author: 小沈 - 2026-03-21
更新时间: 2026-04-26
"""

from app.services.tools.file.file_schema import (
    ReadFileInput,
    WriteTextFileInput,
    WriteFileInput,
    ListDirectoryInput,
    DeleteFileInput,
    MoveFileInput,
    SearchFilesInput,
    GenerateReportInput,
    CopyFileInput,
    CreateDirectoryInput,
    GetFileInfoInput,
    CompareFilesInput,
    BatchRenameInput,
    CompressFilesInput,
    FileMonitorInput,
    FileStatisticsInput,
    FileChecksumInput,
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
    # 工具函数
    encode_page_token,
    decode_page_token,
    _to_unified_format,
    _generate_summary,
    get_file_tools,
)
# 触发工具注册
from app.services.tools.file.file_register import FileTools, get_file_tools

__all__ = [
    # Schema模型
    "ReadFileInput",
    "WriteTextFileInput",
    "WriteFileInput",
    "ListDirectoryInput",
    "DeleteFileInput",
    "MoveFileInput",
    "SearchFilesInput",
    "GenerateReportInput",
    "CopyFileInput",
    "CreateDirectoryInput",
    "GetFileInfoInput",
    "CompareFilesInput",
    "BatchRenameInput",
    "CompressFilesInput",
    "FileMonitorInput",
    "FileStatisticsInput",
    "FileChecksumInput",
    # 常量
    "PAGE_SIZE",
    "MAX_PAGE_SIZE",
    "ALLOWED_PATHS",
    "_get_default_allowed_paths",
    # 类
    "FileTools",
    "ToolDefinition",
    # 工具函数
    "encode_page_token",
    "decode_page_token",
    "_to_unified_format",
    "_generate_summary",
    "get_file_tools",
]
