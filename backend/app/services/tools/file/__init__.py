# -*- coding: utf-8 -*-
"""
Tools/File 模块 - 文件操作工具集

【迁移说明】
本目录是从 agent/tools.py 迁移而来
迁移时间：2026-03-21

【重构说明】2026-04-26 小沈
- file_tools.py 使用独立的 @register_tool 装饰器（已废弃）
- 但保留导出以兼容现有代码
- 未来将迁移到 registry.py 的统一注册

Author: 小沈 - 2026-03-21
更新时间: 2026-04-26
"""

from app.services.tools.file.file_schema import (
    ReadFileInput,
    WriteFileInput,
    ListDirectoryInput,
    DeleteFileInput,
    MoveFileInput,
    SearchFileContentInput,
    SearchFilesByNameInput,
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
    SearchFileContentInput,
    SearchFilesByNameInput,
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
# 注册点（触发工具注册）
from app.services.tools.file import file_register

__all__ = [
    # Schema模型
    "ReadFileInput",
    "WriteFileInput",
    "ListDirectoryInput",
    "DeleteFileInput",
    "MoveFileInput",
    "SearchFileContentInput",
    "SearchFilesByNameInput",
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
