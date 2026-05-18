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

【2026-05-17 小健 降级】LLM工具 8→4
- 降级3个：get_working_directory/change_directory/check_path_exists → 内部函数
- 合并2个：check_command_available+locate_command → find_command

# Shell操作工具（共4个LLM工具）

创建时间: 2026-04-29
更新时间: 2026-05-17 小健
"""

from app.services.tools.registry import register_tool, ToolCategory, tool_registry
from app.utils.logger import logger

from app.services.tools.shell.shell_schema import (
    ExecuteShellCommandInput,
    FindCommandInput,
    ShellSessionInput,
)

from app.services.tools.shell.code_execution_schema import (
    ExecutePythonInput,
    ExecuteJavascriptInput,
)

from app.services.tools.shell.shell_tools import (
    execute_shell_command,
    find_command,
    shell_session,
)

from app.services.tools.shell.code_execution_tools import (
    execute_python,
    execute_javascript,
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
    "find_command": """查找系统命令路径。类似于 which/where 命令。

使用场景：
- 当用户需要确认某个命令（如 python、git、npm）是否已安装时使用
- 当用户需要查找命令的安装路径时使用
- 当用户需要查看命令的所有安装位置时使用
- 当用户需要验证工具链是否正确配置时使用


【重要】all_paths=False返回第一个匹配路径（快速），all_paths=True返回全部匹配路径（完整列表）

使用示例：
- 检查Python是否可用：{"command": "python"}
- 查找Python所有路径：{"command": "python", "all_paths": true}
- 检查Git：{"command": "git"}

返回数据说明：
- all_paths=False时：data含available(命令是否可用，bool)、command(命令名称)、path(命令完整路径，不可用时为null)
- all_paths=True时：data含command(命令名称)、paths(所有匹配路径列表)、count(路径数量)
- 失败时code=ERR_SHELL_FIND_COMMAND，data=null""",
    "execute_python": """执行Python代码并返回结果。支持安全检查。
使用场景：
- 当用户需要运行Python代码片段时使用
- 当用户需要快速验证Python代码逻辑时使用
- 当用户需要执行数据处理、计算等Python脚本时使用

返回数据说明：data含stdout(标准输出)、stderr(标准错误)、returncode(返回码)""",
    "execute_javascript": """执行JavaScript代码并返回结果。
使用场景：
- 当用户需要运行JavaScript代码片段时使用
- 当用户需要快速验证JavaScript代码逻辑时使用

返回数据说明：data含stdout(标准输出)、stderr(标准错误)、returncode(返回码)""",
    "shell_session": """管理后台Shell会话，读取输出或终止会话。

使用场景：
- 当用户需要获取后台命令的执行结果时使用（action="output"）
- 当用户需要终止正在运行的后台命令时使用（action="terminate"）
- 当用户需要检查后台命令是否完成时使用


【重要】action="output"读取输出（默认），action="terminate"终止会话。后台Shell会话由execute_shell_command(run_in_background=true)创建。

使用示例：
- 读取输出：{"shell_id": "shell_abc123"}
- 过滤输出：{"shell_id": "shell_abc123", "filter": "ERROR|FAIL"}
- 终止会话：{"shell_id": "shell_abc123", "action": "terminate"}
- 强制终止：{"shell_id": "shell_abc123", "action": "terminate", "force": true}

返回数据说明：
- action="output"时：data含shell_id(会话ID)、stdout(标准输出)、stderr(标准错误)、is_running(进程是否仍在运行)等
- action="terminate"时：data含shell_id(会话ID)、terminated(是否已终止)、force(是否强制)、returncode(退出码)等
- 失败时data为null""",
}

SHELL_TOOL_EXAMPLES = {
    "execute_shell_command": [
        {"command": "dir", "timeout": 10000},
        {"command": "python --version", "shell_type": "powershell", "timeout": 10000},
        {"command": "npm run dev", "run_in_background": True}
    ],
    "find_command": [
        {"command": "python"},
        {"command": "python", "all_paths": True},
        {"command": "git"},
        {"command": "npm"}
    ],
    "shell_session": [
        {"shell_id": "shell_abc123"},
        {"shell_id": "shell_abc123", "filter": "ERROR|FAIL"},
        {"shell_id": "shell_abc123", "action": "terminate"},
        {"shell_id": "shell_abc123", "action": "terminate", "force": True}
    ],
    "execute_python": [
        {"code": "print('Hello, World!')"},
        {"code": "import math\nprint(math.sqrt(16))"},
        {"code": "for i in range(5):\n    print(i)", "timeout": 10},
    ],
    "execute_javascript": [
        {"code": "console.log('Hello, World!');"},
        {"code": "const result = Math.sqrt(16);\nconsole.log(result);"},
        {"code": "for(let i=0; i<5; i++) {\n  console.log(i);\n}", "timeout": 10},
    ],
}


def _register_shell_tools():
    """
    【2026-05-02 小沈】显式注册所有Shell工具
    【2026-05-17 小沈】8→5，find_command替代check_command_available+locate_command(-1)，
                        shell_session替代get_shell_output+terminate_shell(-1)
    【2026-05-18 小健】5→5，降级3个工具(get_working_directory/change_directory/check_path_exists)不再注册LLM
    使用 Pydantic 模型自动生成 OpenAI Schema
    """
    tool_methods = {
        "execute_shell_command": execute_shell_command,
        "find_command": find_command,
        "shell_session": shell_session,
        "execute_python": execute_python,
        "execute_javascript": execute_javascript,
    }

    TOOL_INPUT_MODELS = {
        "execute_shell_command": ExecuteShellCommandInput,
        "find_command": FindCommandInput,
        "shell_session": ShellSessionInput,
        "execute_python": ExecutePythonInput,
        "execute_javascript": ExecuteJavascriptInput,
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

__all__ = [
    "_register_shell_tools",
    "execute_shell_command",
    "find_command",
    "shell_session",
    "execute_python",
    "execute_javascript",
]
