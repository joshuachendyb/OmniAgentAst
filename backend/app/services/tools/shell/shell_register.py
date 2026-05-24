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

# Shell操作工具（共4个LLM工具 — 2026-05-22 小沈 5→4）
"""

from app.services.tools.registry import register_tool, ToolCategory, tool_registry
from app.utils.logger import logger

from app.services.tools.shell.shell_schema import (
    ExecuteShellCommandInput,
    FindCommandInput,
    ShellSessionInput,
)

from app.services.tools.shell.code_execution_schema import (
    ExecuteCodeInput,
)

from app.services.tools.shell.shell_tools import (
    execute_shell_command,
    find_command,
    shell_session,
)

from app.services.tools.shell.code_execution_tools import (
    execute_code,
)

SHELL_TOOL_DESCRIPTIONS = {
    "execute_shell_command": """在指定 shell 环境中执行命令。Windows默认PowerShell，可选CMD。

【使用场景】
- 执行系统命令、脚本、程序
- 后台运行服务(npm run dev等)

【使用示例】
- 执行dir命令：execute_shell_command(command="dir")
- 后台运行：execute_shell_command(command="npm run dev", run_in_background=true)
- 指定工作目录：execute_shell_command(command="pytest", cwd="D:/project/tests")

【返回数据说明】
- 前台模式：data含stdout/stderr/returncode
- 后台模式：data含shell_id/is_running/started_at""",
    "find_command": """查找系统命令路径 - 合并check_command_available + locate_command功能。类似于 which/where 命令。

【使用场景】
- 当用户需要确认某个命令（如 python、git、npm）是否已安装时使用
- 当用户需要查找命令的安装路径时使用
- 当用户需要查看命令的所有安装位置时使用
- 当用户需要验证工具链是否正确配置时使用

【重要】all_paths=False返回第一个匹配路径（快速），all_paths=True返回全部匹配路径（完整列表）

【使用示例】【常用名转换说明】
- 检查可用/check_command_available → find_command(command="python")
- 查找所有路径/locate_command → find_command(command="python", all_paths=true)
- 检查Git → find_command(command="git")

【返回数据说明】
- all_paths=False时：data含available(命令是否可用，bool)、command(命令名称)、path(命令完整路径，不可用时为null)
- all_paths=True时：data含command(命令名称)、paths(所有匹配路径列表)、count(路径数量)
- 失败时code=ERR_SHELL_FIND_COMMAND，data=null""",
    "execute_code": """执行代码（Python或JavaScript）并返回结果 - 合并execute_python + execute_javascript功能。

【使用场景】
- 运行代码片段、快速验证逻辑、数据处理计算
- 支持python和javascript两种语言
- ⚠️ 比 shell命令直接执行更安全：内置安全检查拦截危险操作

【使用示例】【常用名转换说明】
- Python/execute_python → execute_code(code="print('Hello, World!')")
- JavaScript/execute_javascript → execute_code(code="console.log('Hello');", language="javascript")
- 多行代码 → execute_code(code="import math\\nprint(math.sqrt(16))")

【返回数据说明】
- data含stdout(标准输出)、stderr(标准错误)、returncode(返回码)""",
    "shell_session": """管理后台Shell会话 - 合并get_shell_output + terminate_shell功能。读取输出或终止会话。

【使用场景】
- action="output"：读取后台命令输出（默认），返回尾部最新输出
- action="terminate"：终止后台会话

【使用示例】【常用名转换说明】
- 读取输出/get_shell_output → shell_session(shell_id="shell_abc123")
- 过滤输出 → shell_session(shell_id="shell_abc123", filter="ERROR|FAIL")
- 终止会话/terminate_shell → shell_session(shell_id="shell_abc123", action="terminate")
- 强制终止 → shell_session(shell_id="shell_abc123", action="terminate", force=true)

【返回数据说明】
- action=output时：data含shell_id/stdout/stderr/is_running
- action=terminate时：data含shell_id/terminated/force/returncode""",
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
    "execute_code": [
        {"code": "print('Hello, World!')"},
        {"code": "console.log('Hello');", "language": "javascript"},
        {"code": "import math\nprint(math.sqrt(16))"},
    ],
}


TOOL_INPUT_MODELS = {
    "execute_shell_command": ExecuteShellCommandInput,
    "find_command": FindCommandInput,
    "shell_session": ShellSessionInput,
    "execute_code": ExecuteCodeInput,
}

def _register_shell_tools():
    """
    【2026-05-02 小沈】显式注册所有Shell工具
    【2026-05-17 小沈】8→5，find_command替代check_command_available+locate_command(-1)，
                        shell_session替代get_shell_output+terminate_shell(-1)
    【2026-05-22 小沈】5→4，合并execute_python+execute_javascript→execute_code
    使用 Pydantic 模型自动生成 OpenAI Schema
    """
    tool_methods = {
        "execute_shell_command": execute_shell_command,
        "find_command": find_command,
        "shell_session": shell_session,
        "execute_code": execute_code,
    }

    for name, method in tool_methods.items():
        desc = SHELL_TOOL_DESCRIPTIONS.get(name, "")
        input_model = TOOL_INPUT_MODELS.get(name)
        examples = SHELL_TOOL_EXAMPLES.get(name, [])

        tool_registry.register(
            name=name,
            description=desc,
            category=ToolCategory.SYSTEM,
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
    "execute_code",
]
