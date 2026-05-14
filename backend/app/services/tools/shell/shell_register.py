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


【重要】返回命令的 stdout、stderr 和退出码

使用示例：
- 执行dir命令：{"command": "dir"}
- 执行Python脚本：{"command": "python script.py", "shell_type": "powershell"}
- 后台运行：{"command": "npm run dev", "run_in_background": true}

返回数据说明：
- code: 状态码，SUCCESS/ERR_SHELL_EXEC/ERR_SHELL_TIMEOUT
- data: 前台模式含stdout(标准输出)、stderr(标准错误)、returncode(退出码)；后台模式含shell_id(会话ID)、is_running(是否运行中)、started_at(启动时间)；失败或超时时data可能为null
- message: 状态描述信息""",
    "get_working_directory": """获取当前工作目录的完整路径。

【重要】此工具不需要任何参数，不要传递任何参数！直接调用即可。

使用场景：
- 当用户需要确认当前工作目录时使用
- 当用户需要获取当前所在路径时使用
- 当用户需要获取绝对路径时使用

使用示例：
- 正确：{}  # 无参数，直接调用
- 错误：{"path": "xxx"}  # 不要传path参数！

返回数据说明：
- code: 状态码，SUCCESS/ERR_SHELL_GET_CWD
- data: 成功时含path(当前工作目录绝对路径)；失败时为null
- message: 状态描述信息""",
    "change_directory": "切换当前工作目录到指定路径。\n\n使用场景：\n- 当用户需要切换工作目录时使用\n- 当用户需要在特定目录下执行命令时使用\n- 当用户需要改变当前路径时使用\n\n【重要】切换shell会话的工作目录，后续命令在此目录下执行\n\n使用示例：\n- 切换到D盘：{\"path\": \"D:/\"}\n- 切换到项目目录：{\"path\": \"D:/OmniAgentAs-desk\"}\n\n返回数据说明：\n- code: 状态码，SUCCESS/ERR_SHELL_PATH_NOT_FOUND/ERR_SHELL_PERMISSION/ERR_SHELL_CHANGE_DIR\n- data: 成功时含success(是否成功，true)、path(切换后的工作目录绝对路径)；失败时为null\n- message: 状态描述信息",
    "check_path_exists": "检查指定的文件或目录是否存在，并返回类型信息。\n\n使用场景：\n- 当用户需要检查文件是否存在时使用\n- 当用户需要确认路径是文件还是目录时使用\n- 当用户需要验证路径有效性时使用\n\n【重要】返回路径是否存在以及类型（file/directory/nonexistent）\n\n使用示例：\n- 检查文件：{\"path\": \"D:/OmniAgentAs-desk/main.py\"}\n- 检查目录：{\"path\": \"D:/OmniAgentAs-desk/src\"}\n\n返回数据说明：\n- code: 状态码，SUCCESS/ERR_SHELL_CHECK_PATH\n- data: 含exists(路径是否存在，bool)、is_file(是否为文件，bool)、is_directory(是否为目录，bool)、path(检查的原始路径)；失败时为null\n- message: 状态描述信息",
    "check_command_available": "检查系统命令是否可用，类似于 Linux 的 which 命令。\n\n使用场景：\n- 当用户需要确认某个命令（如 python、git、npm）是否已安装时使用\n- 当用户需要查找命令的安装路径时使用\n- 当用户需要验证工具链是否正确配置时使用\n\n【重要】返回命令是否存在以及完整路径\n\n使用示例：\n- 检查Python：{\"command\": \"python\"}\n- 检查Git：{\"command\": \"git\"}\n- 检查npm：{\"command\": \"npm\"}\n\n返回数据说明：\n- code: 状态码，SUCCESS/ERR_SHELL_CHECK_COMMAND\n- data: 含available(命令是否可用，bool)、command(命令名称)、path(命令完整路径，不可用时为null)；失败时为null\n- message: 状态描述信息",
    "locate_command": "查找命令的所有可能路径，类似于 Windows 的 where 命令或 Linux 的 which -a。\n\n使用场景：\n- 当用户需要查看某个命令的所有安装位置时使用\n- 当用户想要确认使用的是哪个版本的命令时使用\n- 当用户需要选择特定版本的命令时使用\n\n【重要】返回命令的所有可能路径（可能多个）\n\n使用示例：\n- 查找Python：{\"command\": \"python\"}\n- 查找node：{\"command\": \"node\"}\n\n返回数据说明：\n- code: 状态码，SUCCESS/ERR_SHELL_LOCATE_COMMAND\n- data: 含command(命令名称)、paths(所有匹配路径列表)、count(路径数量)；失败时为null\n- message: 状态描述信息",
    "get_shell_output": """获取后台运行的 shell 命令输出。

使用场景：
- 当用户需要获取后台命令的执行结果时使用
- 当用户想要检查后台命令是否完成时使用
- 当用户需要分批获取长命令输出时使用


【重要】返回 shell 命令的 stdout 和 stderr 输出

使用示例：
- 获取输出：{"shell_id": "shell_abc123"}
- 过滤输出：{"shell_id": "shell_abc123", "filter": "ERROR|FAIL"}

返回数据说明：
- code: 状态码，SUCCESS/ERR_SHELL_NOT_FOUND/ERR_SHELL_NO_PROCESS/ERR_SHELL_FILTER_INVALID/ERR_SHELL_GET_OUTPUT
- data: 含shell_id(会话ID)、stdout(标准输出文本)、stderr(标准错误文本)、stdout_lines(标准输出行数)、stderr_lines(标准错误行数)、truncated(输出是否被截断，bool)、is_running(进程是否仍在运行，bool)；失败时为null
- message: 状态描述信息""",
    "terminate_shell": """终止运行中的后台 shell 会话。

使用场景：
- 当用户需要终止正在运行的后台命令时使用
- 当用户想要停止长时间运行的命令时使用
- 当用户需要清理后台进程时使用


【重要】强制终止后台进程，会丢失未读取的输出

使用示例：
- 终止后台shell：{"shell_id": "shell_abc123"}
- 强制终止：{"shell_id": "shell_abc123", "force": true}

返回数据说明：
- code: 状态码，SUCCESS/ERR_SHELL_NOT_FOUND/ERR_SHELL_TERMINATE
- data: 含shell_id(会话ID)、terminated(是否已终止，bool)、force(是否强制终止，bool)、returncode(进程退出码)、cleanup(是否已清理，bool)、already_stopped(进程是否已自行停止，bool，仅已停止时存在)；失败时为null
- message: 状态描述信息""",
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


# 【修复 2026-05-07 小沈】守护模式：只首次import时注册，防止重复注册
_initialized = False  # 守护变量，供显式调用时使用

__all__ = ["_register_shell_tools"]


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
