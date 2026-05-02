# -*- coding: utf-8 -*-
"""
Shell Register - Shell工具注册点

【架构规范】2026-05-02 小沈
- shell_register.py: 显式注册（tool_registry.register）
- shell_tools.py: 工具函数实现（无装饰器）
- shell_schema.py: Pydantic 模型

【2026-05-02 小沈重构】
- 从 @register_tool 装饰器注册改为显式注册（tool_registry.register）
- 按 file_register.py 模式重写

创建时间: 2026-04-29
更新时间: 2026-05-02
"""

from app.services.tools.registry import register_tool, ToolCategory, tool_registry
from app.utils.logger import logger

from app.services.tools.shell.shell_schema import (
    ExecuteCommandInput,
    GetWorkingDirectoryInput,
    ChangeDirectoryInput,
    CheckPathExistsInput,
    GetShellOutputInput,
    TerminateShellInput,
)

from app.services.tools.shell.shell_tools import (
    execute_command,
    get_working_directory,
    change_directory,
    check_path_exists,
    get_shell_output,
    terminate_shell,
)

SHELL_TOOL_DESCRIPTIONS = {
    "execute_command": """执行Shell命令并返回结果。

使用场景：
- 当用户需要执行系统命令时使用
- 当用户需要运行脚本或程序时使用
- 当用户需要获取系统信息（如ipconfig、dir等）时使用

参数说明：
- command: 要执行的Shell命令。必填参数
- cwd: 工作目录，如果为None则使用当前工作目录。可选参数
- timeout: 超时时间（秒），默认为30秒。可选参数

返回数据说明：
- stdout: 标准输出内容
- stderr: 标准错误内容
- returncode: 返回码（0表示成功）""",
    "get_working_directory": "获取当前工作目录的完整路径。",
    "change_directory": "改变当前工作目录到指定路径。",
    "check_path_exists": "检查指定的文件或目录是否存在，并返回类型信息。",
    "get_shell_output": """获取后台运行的 shell 命令输出。

使用场景：
- 当用户需要获取后台命令的执行结果时使用
- 当用户想要检查后台命令是否完成时使用
- 当用户需要分批获取长命令输出时使用

参数说明：
- shell_id：后台 shell 的 ID，由 execute_shell_command 的 run_in_background=true 时返回
- filter：过滤输出的正则表达式（可选）
- encoding：输出编码（可选），默认utf-8
- max_lines：最大返回行数（可选），默认1000
- tail：是否只返回最后N行（可选），默认false

【重要】返回 shell 命令的 stdout 和 stderr 输出

使用示例：
- 获取输出：{"shell_id": "shell_abc123"}
- 过滤输出：{"shell_id": "shell_abc123", "filter": "ERROR|FAIL"}""",
    "terminate_shell": """终止运行中的后台 shell 会话。

使用场景：
- 当用户需要终止正在运行的后台命令时使用
- 当用户想要停止长时间运行的命令时使用
- 当用户需要清理后台进程时使用

参数说明：
- shell_id：要终止的 shell ID
- force：是否强制终止（可选），默认false
- cleanup：终止后是否清理临时文件（可选），默认true

【重要】强制终止后台进程，会丢失未读取的输出

使用示例：
- 终止后台shell：{"shell_id": "shell_abc123"}
- 强制终止：{"shell_id": "shell_abc123", "force": true}""",
}

SHELL_TOOL_EXAMPLES = {
    "execute_command": [
        {"command": "dir", "timeout": 10},
        {"command": "python --version", "timeout": 10},
        {"command": "dir /b D:/项目代码", "cwd": "D:/项目代码", "timeout": 30}
    ],
    "get_working_directory": [{}],
    "change_directory": [
        {"path": "D:/项目代码"},
        {"path": "C:/Users"}
    ],
    "check_path_exists": [
        {"path": "D:/项目代码"},
        {"path": "C:/Users/用户名/Documents/config.json"}
    ],
    "get_shell_output": [
        {"shell_id": "shell_abc123"},
        {"shell_id": "shell_abc123", "filter": "ERROR|FAIL"},
        {"shell_id": "shell_abc123", "max_lines": 500, "tail": True}
    ],
    "terminate_shell": [
        {"shell_id": "shell_abc123"},
        {"shell_id": "shell_abc123", "force": True},
        {"shell_id": "shell_abc123", "force": True, "cleanup": True}
    ],
}


def _register_shell_tools():
    """
    【2026-05-02 小沈】显式注册所有Shell工具
    使用 Pydantic 模型自动生成 OpenAI Schema
    """
    tool_methods = {
        "execute_command": execute_command,
        "get_working_directory": get_working_directory,
        "change_directory": change_directory,
        "check_path_exists": check_path_exists,
        "get_shell_output": get_shell_output,
        "terminate_shell": terminate_shell,
    }

    TOOL_INPUT_MODELS = {
        "execute_command": ExecuteCommandInput,
        "get_working_directory": GetWorkingDirectoryInput,
        "change_directory": ChangeDirectoryInput,
        "check_path_exists": CheckPathExistsInput,
        "get_shell_output": GetShellOutputInput,
        "terminate_shell": TerminateShellInput,
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
        )
        logger.info(f"[shell_register] 已注册工具: {name}, 使用 Pydantic 模型: {input_model.__name__ if input_model else 'None'}, examples: {len(examples)}个")


_register_shell_tools()


__all__ = [
    "execute_command",
    "get_working_directory",
    "change_directory",
    "check_path_exists",
    "get_shell_output",
    "terminate_shell",
]
