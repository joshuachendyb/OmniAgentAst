# -*- coding: utf-8 -*-
"""Shell 模块 - Shell命令执行 + 代码执行工具

【2026-05-22 小沈】合并execute_python+execute_javascript→execute_code
"""

from app.services.tools.shell import shell_register
from app.services.tools.shell import shell_tools

from app.services.tools.shell.shell_tools import (
    execute_shell_command,
    find_command,
    shell_session,
)
from app.services.tools.shell.code_execution_tools import (
    execute_code,
)

__all__ = [
    "execute_shell_command",
    "find_command",
    "shell_session",
    "execute_code",
]
