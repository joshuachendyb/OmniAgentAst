# -*- coding: utf-8 -*-
"""
Shell 模块 - Shell命令执行工具

【架构规范】2026-04-29 小沈
- shell_register.py: 工具注册点（导入触发注册）
- shell_tools.py: 具体实现
- shell_schema.py: Pydantic 模型

目录结构：
    shell/
    ├── __init__.py           # 本文件，导入 shell_register 触发注册
    ├── shell_register.py     # 工具注册点
    ├── shell_tools.py        # 具体实现
    └── shell_schema.py       # Pydantic 模型

创建时间: 2026-04-29
"""

# 导入 shell_register 触发注册
from app.services.tools.shell import shell_register
from app.services.tools.shell import shell_tools

from app.services.tools.shell.shell_tools import (
    execute_shell_command,
    get_working_directory,
    change_directory,
    check_path_exists,
    check_command_available,
    locate_command,
    get_shell_output,
    terminate_shell,
)

__all__ = [
    "execute_shell_command",
    "get_working_directory",
    "change_directory",
    "check_path_exists",
    "check_command_available",
    "locate_command",
    "get_shell_output",
    "terminate_shell",
]
