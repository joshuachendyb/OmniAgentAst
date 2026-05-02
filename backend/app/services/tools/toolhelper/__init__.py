# -*- coding: utf-8 -*-
"""
ToolHelper 模块 - 内部辅助函数集合（不暴露给LLM）

【架构规范】2026-05-02 小沈
- 本目录包含各Tool分类共用的内部辅助函数
- 这些函数不注册到tool_registry，仅供Agent内部代码调用

目录结构：
    toolhelper/
    ├── __init__.py           # 本文件
    └── file_helpers.py       # 文件操作辅助函数（10个）

Author: 小沈 - 2026-05-02
"""

from app.services.tools.toolhelper.file_helpers import (
    extract_archive,
    get_file_hash,
    ensure_directory_exists,
    check_write_permission,
    check_read_permission,
    get_file_encoding,
    get_mime_type,
    backup_file,
    move_to_trash,
    validate_command,
    check_shell_running,
)

__all__ = [
    "extract_archive",
    "get_file_hash",
    "ensure_directory_exists",
    "check_write_permission",
    "check_read_permission",
    "get_file_encoding",
    "get_mime_type",
    "backup_file",
    "move_to_trash",
    "validate_command",
    "check_shell_running",
]
