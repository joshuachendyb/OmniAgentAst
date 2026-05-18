# -*- coding: utf-8 -*-
"""
Shell 模块 - Shell命令执行工具

【架构规范】2026-04-29 小沈
- shell_register.py: 工具注册点（导入触发注册）
- shell_tools.py: 具体实现
- shell_schema.py: Pydantic 模型

【2026-05-17 小健】LLM工具 8→4，降级3个工具

目录结构：
    shell/
    ├── __init__.py           # 本文件，导入 shell_register 触发注册
    ├── shell_register.py     # 工具注册点
    ├── shell_tools.py        # 具体实现
    └── shell_schema.py       # Pydantic 模型

创建时间: 2026-04-29
更新时间: 2026-05-17 小健
"""

from app.services.tools.shell import shell_register
from app.services.tools.shell import shell_tools

from app.services.tools.shell.shell_tools import (
    execute_shell_command,
    find_command,
    shell_session,
)
from app.services.tools.code_execution.code_execution_tools import (
    execute_python,
    execute_javascript,
)

__all__ = [
    "execute_shell_command",
    "find_command",
    "shell_session",
    "execute_python",
    "execute_javascript",
]
