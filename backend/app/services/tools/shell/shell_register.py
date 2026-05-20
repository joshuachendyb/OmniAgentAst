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
    "execute_shell_command": """在指定 shell 环境中执行命令。Windows默认PowerShell，可选CMD。

使用场景：
- 执行系统命令、脚本、程序
- 后台运行服务(npm run dev等)

参数说明：
- shell_type：powershell(默认)或cmd
- timeout：超时毫秒数，默认30000(30秒)，最大600000(10分钟)
- run_in_background：后台运行，长期服务设为true
- cwd：工作目录，不设则使用系统当前目录
- env_vars：额外环境变量字典，与系统环境变量合并

使用示例：
- 执行dir命令：{"command": "dir"}
- 后台运行：{"command": "npm run dev", "run_in_background": true}
- 指定工作目录：{"command": "pytest", "cwd": "D:/project/tests"}

返回数据说明：
- 前台模式：data含stdout/stderr/returncode
- 后台模式：data含shell_id/is_running/started_at""",
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
    "execute_python": """执行Python代码并返回结果。

使用场景：
- 运行Python代码片段、快速验证逻辑、数据处理计算
- ⚠️ 比 execute_shell_command python -c "..." 更安全：内置安全检查拦截危险操作

参数说明：
- code：Python代码字符串，必填，可多行
- timeout：超时秒数，默认30，最大300
- working_dir：工作目录，不设则当前目录，不存在时自动创建
- safety_check：安全检查(检测os.system/subprocess等危险模式)，默认True

返回数据说明：data含stdout(标准输出)、stderr(标准错误)、returncode(返回码)""",
    "execute_javascript": """执行JavaScript代码并返回结果。需要Node.js环境。

使用场景：
- 运行JavaScript代码片段、快速验证逻辑
- ⚠️ 比 execute_shell_command node -e "..." 更安全：内置安全检查拦截危险操作

参数说明：
- code：JavaScript代码字符串，必填，可多行
- timeout：超时秒数，默认30，最大300
- working_dir：工作目录，不设则当前目录，不存在时自动创建
- safety_check：安全检查(检测child_process/fs/eval等危险模式)，默认True

返回数据说明：data含stdout(标准输出)、stderr(标准错误)、returncode(返回码)""",
    "shell_session": """管理后台Shell会话：读取输出或终止会话。

使用场景：
- action="output"：读取后台命令输出（默认），返回尾部最新输出
- action="terminate"：终止后台会话

参数说明：
- filter：输出过滤正则（action=output时生效），如 "ERROR|FAIL"
- max_lines：最大返回行数（action=output时生效），默认1000
- force：强制终止（action=terminate时生效），优雅终止失败时设true

使用示例：
- 读取输出：{"shell_id": "shell_abc123"}
- 过滤输出：{"shell_id": "shell_abc123", "filter": "ERROR|FAIL"}
- 终止会话：{"shell_id": "shell_abc123", "action": "terminate"}
- 强制终止：{"shell_id": "shell_abc123", "action": "terminate", "force": true}

返回数据说明：
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


TOOL_INPUT_MODELS = {
    "execute_shell_command": ExecuteShellCommandInput,
    "find_command": FindCommandInput,
    "shell_session": ShellSessionInput,
    "execute_python": ExecutePythonInput,
    "execute_javascript": ExecuteJavascriptInput,
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
