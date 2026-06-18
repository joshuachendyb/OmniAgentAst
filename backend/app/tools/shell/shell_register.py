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

【2026-06-17 小欧】拆分:execute_shell_command→前台+后台两个工具

# Shell操作工具(共6个LLM工具)
"""

from app.tools.registry import register_tool, tool_registry
from app.tools.tool_types import ToolCategory
from app.utils.logger import logger

from app.tools.shell.shell_schema import (
    ExecuteShellCommandInput,
    ExecuteShellCommandForegroundInput,
    ExecuteShellCommandBackgroundInput,
    FindCommandInput,
    ShellSessionInput,
    ExecuteCodeInput,
)

from app.tools.shell.shell_tools import (
    execute_shell_command,
    execute_shell_command_foreground,
    execute_shell_command_background,
    find_command,
    shell_session,
)

from app.tools.shell.code_execution_tools import (
    execute_code,
)

SHELL_TOOL_DESCRIPTIONS = {
    "execute_shell_command": """在指定Shell环境中执行命令。默认使用Windows PowerShell,可选CMD。支持前台模式(实时等待返回结果)和后台模式(run_in_background=True,返回会话ID供shell_session工具后续读取输出)。前台模式返回stdout/stderr/returncode。适用场景:需要执行系统命令、运行脚本、启动程序、后台启动服务(如npm run dev)时使用。

【Windows命令参考】常用操作对应的CMD/PowerShell命令:
- 列目录: dir
- 读文件: type
- 复制: copy
- 移动: move
- 重命名: ren
- 删除文件: del
- 删除目录: rmdir /s /q
- 创建目录: mkdir
- 查找文件: dir /s /b
- 查找内容: findstr
- 查询路径: where
- 环境变量: set
- 进程列表: tasklist
- 杀进程: taskkill /F /PID
- 网络状态: netstat
- IP配置: ipconfig
- 磁盘信息: wmic logicaldisk get size,freespace,caption
- 权限修改: icacls""",
    "execute_shell_command_foreground": """在前台执行Shell命令,实时等待命令完成返回输出结果。默认使用Windows PowerShell,可选CMD。返回stdout/stderr/returncode。支持timeout超时控制。适用场景:需要执行一次性命令并立即获得执行结果时使用。""",
    "execute_shell_command_background": """在后台启动Shell命令,立即返回shell_id供shell_session工具后续读取输出。默认使用Windows PowerShell,可选CMD。适用场景:需要启动长期运行的服务(如npm run dev、python server.py)并持续监控输出时使用。""",
    "find_command": """查找系统命令的安装路径,类似于which/where命令。all_paths=False(默认)返回第一个匹配路径,all_paths=True返回全部匹配路径列表。适用场景:需要确认python/git/npm等命令是否已安装、查看命令安装路径、验证开发工具链配置是否正确时使用。""",
    "execute_code": """执行代码片段并返回结果。支持Python(默认)和JavaScript两种语言。内置安全检查拦截危险操作(如文件删除、网络请求等),比直接Shell命令更安全。返回stdout/stderr/returncode。适用场景:需要快速验证代码逻辑、进行数据处理计算、运行简单脚本片段时使用。""",
    "shell_session": """支持后台Shell会话管理功能。
action参数决定操作类型:
- output: 读取后台命令输出,shell_id(可选filter/max_lines)
- terminate: 终止后台会话,shell_id(可选force)

使用示例:
- 读取输出 → shell_session(shell_id="shell_abc123")
- 终止会话 → shell_session(shell_id="shell_abc123", action="terminate")""",
}

SHELL_TOOL_EXAMPLES = {
    "execute_shell_command": [
        {"command": "dir", "timeout": 10000},
        {"command": "python --version", "shell_type": "powershell", "timeout": 10000},
        {"command": "npm run dev", "run_in_background": True}
    ],
    "execute_shell_command_foreground": [
        {"command": "dir", "timeout": 10000},
        {"command": "python --version", "shell_type": "powershell", "timeout": 10000},
    ],
    "execute_shell_command_background": [
        {"command": "npm run dev", "cwd": "D:/project/frontend"},
        {"command": "python server.py", "cwd": "D:/project/backend"},
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
    "execute_shell_command_foreground": ExecuteShellCommandForegroundInput,
    "execute_shell_command_background": ExecuteShellCommandBackgroundInput,
    "find_command": FindCommandInput,
    "shell_session": ShellSessionInput,
    "execute_code": ExecuteCodeInput,
}

def _register_shell_tools():
    """
    【2026-05-02 小沈】显式注册所有Shell工具
    【2026-05-17 小沈】8→5,find_command替代check_command_available+locate_command(-1),
                        shell_session替代get_shell_output+terminate_shell(-1)
    【2026-05-22 小沈】5→4,合并execute_python+execute_javascript→execute_code
    【v3.4新增 2026-06-09 小沈】添加安全级别标注
    【2026-06-17 小欧】拆分execute_shell_command为前台/后台
    使用 Pydantic 模型自动生成 OpenAI Schema
    """
    # 【2026-06-16 小沈】二元安全配置（替代5级枚举）
    CONFIRMATION_MAP = {
        "execute_shell_command": {"write": True},
        "execute_shell_command_foreground": {"write": True},
        "execute_shell_command_background": {"write": True},
    }
    
    tool_methods = {
        "execute_shell_command": execute_shell_command,
        "execute_shell_command_foreground": execute_shell_command_foreground,
        "execute_shell_command_background": execute_shell_command_background,
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
            category=ToolCategory.SHELL,
            implementation=method,
            version="1.0.0",
            input_model=input_model,
            examples=examples,
            needs_confirmation=(name in ("execute_shell_command", "execute_shell_command_foreground", "execute_shell_command_background")),
            action_confirmation=CONFIRMATION_MAP.get(name),
        )
        logger.debug(f"[shell_register] 已注册工具: {name}, 使用 Pydantic 模型: {input_model.__name__ if input_model else 'None'}, examples: {len(examples)}个")



__all__ = [
    "_register_shell_tools",
    "execute_shell_command",
    "execute_shell_command_foreground",
    "execute_shell_command_background",
    "find_command",
    "shell_session",
    "execute_code",
]
