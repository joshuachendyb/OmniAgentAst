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

# Shell操作工具（共8个） 小沈-2026-05-05

创建时间: 2026-04-29
更新时间: 2026-05-02
"""

from app.services.tools.registry import register_tool, ToolCategory, tool_registry
from app.utils.logger import logger

from app.services.tools.shell.shell_schema import (
    ExecuteShellCommandInput,
    GetWorkingDirectoryInput,
    ChangeDirectoryInput,
    CheckPathExistsInput,
    CheckCommandAvailableInput,
    LocateCommandInput,
    GetShellOutputInput,
    TerminateShellInput,
)

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

SHELL_TOOL_DESCRIPTIONS = {
    "execute_shell_command": """在指定 shell 环境中执行命令。Windows 原生默认 PowerShell，可选 CMD；bash 需额外安装（未来扩展）。

使用场景：
- 当用户需要执行系统命令时使用
- 当用户想要运行命令行工具时使用
- 当用户需要执行脚本或程序时使用

参数说明：
- command：要执行的命令
- shell_type：执行环境。powershell（默认）-Windows PowerShell；cmd-Windows 命令提示符
- timeout：超时毫秒数，默认120000（2分钟），最大600000（10分钟）
- run_in_background：是否在后台运行命令
- cwd：工作目录
- encoding：命令输出编码，默认null自动检测
- env_vars：环境变量对象
- run_as_admin：是否以管理员权限运行

【重要】返回命令的 stdout、stderr 和退出码

使用示例：
- 执行dir命令：{"command": "dir"}
- 执行Python脚本：{"command": "python script.py", "shell_type": "powershell"}
- 后台运行：{"command": "npm run dev", "run_in_background": true}""",
    "get_working_directory": "获取当前工作目录的完整路径。\n\n使用场景：\n- 当用户需要确认当前工作目录时使用\n- 当用户需要获取当前所在路径时使用\n- 当用户需要获取绝对路径时使用\n\n参数说明：\n- 无参数\n\n【重要】返回当前shell会话的工作目录绝对路径\n\n使用示例：\n- 获取当前目录：{}",
    "change_directory": "切换当前工作目录到指定路径。\n\n使用场景：\n- 当用户需要切换工作目录时使用\n- 当用户需要在特定目录下执行命令时使用\n- 当用户需要改变当前路径时使用\n\n参数说明：\n- path：要切换到的目录路径（必须是绝对路径）\n\n【重要】切换shell会话的工作目录，后续命令在此目录下执行\n\n使用示例：\n- 切换到D盘：{\"path\": \"D:/\"}\n- 切换到项目目录：{\"path\": \"D:/OmniAgentAs-desk\"}",
    "check_path_exists": "检查指定的文件或目录是否存在，并返回类型信息。\n\n使用场景：\n- 当用户需要检查文件是否存在时使用\n- 当用户需要确认路径是文件还是目录时使用\n- 当用户需要验证路径有效性时使用\n\n参数说明：\n- path：要检查的文件或目录路径\n\n【重要】返回路径是否存在以及类型（file/directory/nonexistent）\n\n使用示例：\n- 检查文件：{\"path\": \"D:/OmniAgentAs-desk/main.py\"}\n- 检查目录：{\"path\": \"D:/OmniAgentAs-desk/src\"}",
    "check_command_available": "检查系统命令是否可用，类似于 Linux 的 which 命令。\n\n使用场景：\n- 当用户需要确认某个命令（如 python、git、npm）是否已安装时使用\n- 当用户需要查找命令的安装路径时使用\n- 当用户需要验证工具链是否正确配置时使用\n\n参数说明：\n- command：要检查的命令名称（不含路径）\n\n【重要】返回命令是否存在以及完整路径\n\n使用示例：\n- 检查Python：{\"command\": \"python\"}\n- 检查Git：{\"command\": \"git\"}\n- 检查npm：{\"command\": \"npm\"}",
    "locate_command": "查找命令的所有可能路径，类似于 Windows 的 where 命令或 Linux 的 which -a。\n\n使用场景：\n- 当用户需要查看某个命令的所有安装位置时使用\n- 当用户想要确认使用的是哪个版本的命令时使用\n- 当用户需要选择特定版本的命令时使用\n\n参数说明：\n- command：要查找的命令名称\n\n【重要】返回命令的所有可能路径（可能多个）\n\n使用示例：\n- 查找Python：{\"command\": \"python\"}\n- 查找node：{\"command\": \"node\"}",
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
    "execute_shell_command": [
        {"command": "dir", "timeout": 10000},
        {"command": "python --version", "shell_type": "powershell", "timeout": 10000},
        {"command": "npm run dev", "run_in_background": True}
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
    "check_command_available": [
        {"command": "python"},
        {"command": "git"},
        {"command": "npm"}
    ],
    "locate_command": [
        {"command": "python"},
        {"command": "node"}
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
        "execute_shell_command": execute_shell_command,
        "get_working_directory": get_working_directory,
        "change_directory": change_directory,
        "check_path_exists": check_path_exists,
        "check_command_available": check_command_available,
        "locate_command": locate_command,
        "get_shell_output": get_shell_output,
        "terminate_shell": terminate_shell,
    }

    TOOL_INPUT_MODELS = {
        "execute_shell_command": ExecuteShellCommandInput,
        "get_working_directory": GetWorkingDirectoryInput,
        "change_directory": ChangeDirectoryInput,
        "check_path_exists": CheckPathExistsInput,
        "check_command_available": CheckCommandAvailableInput,
        "locate_command": LocateCommandInput,
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
    "execute_shell_command",
    "get_working_directory",
    "change_directory",
    "check_path_exists",
    "check_command_available",
    "locate_command",
    "get_shell_output",
    "terminate_shell",
]
