# -*- coding: utf-8 -*-
"""
Shell Register - Shell工具注册点

【架构规范】2026-05-02 小沈
- shell_register.py: 显式注册(tool_registry.register)
- shell_tools.py: 工具函数实现(无装饰器)
- shell_schema.py: Pydantic 模型

【2026-05-02 小沈重构】
- 从 @register_tool 装饰器注册改为显式注册(tool_registry.register)
- 按 file_register.py 模式重写

【2026-05-17 小健 降级】LLM工具 8→4
- 降级3个:get_working_directory/change_directory/check_path_exists → 内部函数
- 合并2个:check_command_available+locate_command → find_command

【2026-06-18 小健】删除两个包装器(execute_shell_command_foreground/background)，违反YAGNI原则

# Shell操作工具(共4个LLM工具)
"""

from app.tools.registry import register_tool, tool_registry
from app.tools.tool_types import ToolCategory
from app.logger import logger

# Shell工具依赖配置 — 小健 2026-06-18
# Shell工具使用内置库，无第三方依赖
SHELL_TOOL_DEPENDENCIES = {
    tool_name: [] for tool_name in [
        "shell", "which"
    ]
}

from app.tools.shell.shell_schema import (
    ShellInput,
    WhichInput,
)

from app.tools.shell.execute_shell_command import shell
from app.tools.shell.find_command import which

SHELL_TOOL_DESCRIPTIONS = {
    "shell": """在Windows环境中执行PowerShell/CMD命令。推荐使用PowerShell语法。适用场景:需要运行系统命令、执行脚本、启动程序时使用。""",

    "which": """查找系统命令的安装路径。适用场景:需要确认命令是否已安装、查看其安装路径时使用。""",
}

SHELL_TOOL_EXAMPLES = {
    "shell": [
        {"command": "dir", "timeout": 10},
        {"command": "python --version", "shell_type": "powershell", "timeout": 10},
    ],

    "which": [
        {"command": "python"},
        {"command": "python", "all_paths": True},
        {"command": "git"},
        {"command": "npm"}
    ],
}


TOOL_INPUT_MODELS = {
    "shell": ShellInput,
    "which": WhichInput,
}

def _register_shell_tools():
    """
    【2026-05-02 小沈】显式注册所有Shell工具
    【2026-05-17 小沈】8→5,find_command替代check_command_available+locate_command(-1),
                        shell_session替代get_shell_output+terminate_shell(-1)
    【2026-05-22 小沈】5→4,合并execute_python+execute_javascript→execute_code
    【v3.4新增 2026-06-09 小沈】添加安全级别标注
    【2026-06-18 小健】删除两个包装器，违反YAGNI原则
    使用 Pydantic 模型自动生成 OpenAI Schema
    """
    CONFIRMATION_MAP = {
        "shell": {"write": True},
    }
    
    tool_methods = {
        "shell": shell,
        "which": which,
    }

    for name, method in tool_methods.items():
        desc = SHELL_TOOL_DESCRIPTIONS.get(name, "")
        input_model = TOOL_INPUT_MODELS.get(name)
        examples = SHELL_TOOL_EXAMPLES.get(name, [])

        tool_registry.register(
            name=name,
            description=desc,
            category=ToolCategory.SHELL,
            implementation=method,
            version="1.0.0",
            input_model=input_model,
            examples=examples,
            needs_confirmation=(name == "shell"),
            action_confirmation=CONFIRMATION_MAP.get(name),
            dependencies=SHELL_TOOL_DEPENDENCIES.get(name, []),
        )
        logger.debug(f"[shell_register] 已注册工具: {name}, 使用 Pydantic 模型: {input_model.__name__ if input_model else 'None'}, examples: {len(examples)}个")



__all__ = [
    "_register_shell_tools",
    "shell",
    "which",
]
