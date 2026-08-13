# -*- coding: utf-8 -*-
"""Shell Prompt Templates — 按 shell_type 输出 shell 语法指引 (不含 TOOL_CALL_RULES_BASE 工具映射, 纯语法提示)

【创建时间】2026-07-28 小欧
【迁移】2026-08-13 小沈 - 从 tools/shell/ 迁入 tools/fundamental/ (Prompt模板是基础能力, 非shell工具专属)
"""

from typing import Final

_SHELL_DISPLAY: Final[dict[str, str]] = {
    "ps7": "PowerShell 7+",
    "ps5": "Windows PowerShell 5.1",
    "cmd": "cmd.exe",
    "bash": "bash",
}

_PS7_TEXT = """- 链式命令: 原生支持 && 和 ||
- 引号: 插值用双引号, 字面用单引号
- 子表达式: $(...) 用于子表达式, @(...) 用于数组
- 路径含空格: 用 & 调用运算符: & "path/to/exe" args
- 转义: PowerShell 反引号 `"""

_PS5_TEXT = """- 链式命令: 不支持 &&, 用 cmd1; if ($?) { cmd2 } 代替
- 引号: 插值用双引号, 字面用单引号
- 子表达式: $(...) 用于子表达式, @(...) 用于数组
- 路径含空格: 用 & 调用运算符: & "path/to/exe" args
- 转义: PowerShell 反引号 `"""

_CMD_TEXT = """- 环境变量: %VAR% 语法
- 存在检查: if exist
- 链式命令: 用 &&
- 路径: 反斜杠 \\ 分隔"""

_BASH_TEXT = """- 链式命令: 用 && 和 ||
- 路径: 标准 POSIX 路径 /home/xxx/file.txt
- Windows Git Bash: /c/Users/xxx/file.txt
- 路径含空格: 用双引号 "path with spaces/file.txt"
- 转义: 单引号阻止变量展开, 双引号允许"""

_TEMPLATES = {
    "ps7": _PS7_TEXT,
    "ps5": _PS5_TEXT,
    "cmd": _CMD_TEXT,
    "bash": _BASH_TEXT,
}


def render_shell_section(shell_type: str) -> str:
    _type = shell_type or "ps7"
    display = _SHELL_DISPLAY.get(_type, _type)
    text = _TEMPLATES.get(_type, _PS7_TEXT)
    return f"【Shell】{display}\n{text}"