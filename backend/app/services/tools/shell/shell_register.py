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

# Shell操作工具(共4个LLM工具 — 2026-05-22 小沈 5→4)
"""

from app.services.tools.registry import register_tool, tool_registry
from app.services.tools.tool_types import ToolCategory, ToolSafetyLevel
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
    "execute_shell_command": """在指定Shell环境中执行命令。默认使用Windows PowerShell,可选CMD。支持前台模式(实时等待返回结果)和后台模式(run_in_background=True,返回会话ID供shell_session工具后续读取输出)。前台模式返回stdout/stderr/returncode。适用场景:需要执行系统命令、运行脚本、启动程序、后台启动服务(如npm run dev)时使用。""",
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
    【2026-05-17 小沈】8→5,find_command替代check_command_available+locate_command(-1),
                        shell_session替代get_shell_output+terminate_shell(-1)
    【2026-05-22 小沈】5→4,合并execute_python+execute_javascript→execute_code
    【v3.4新增 2026-06-09 小沈】添加安全级别标注
    使用 Pydantic 模型自动生成 OpenAI Schema
    """
    # 【v3.4新增】安全级别配置
    safety_levels = {
        "execute_shell_command": ToolSafetyLevel.DANGEROUS,
        "find_command": ToolSafetyLevel.READ_ONLY,
        "shell_session": ToolSafetyLevel.SAFE,
        "execute_code": ToolSafetyLevel.DANGEROUS_SANDBOX,
    }
    
    # 【v3.4新增】action级安全覆盖（execute_shell_command的read/write分级）
    action_safety_maps = {
        "execute_shell_command": {
            "read": ToolSafetyLevel.READ_ONLY,
            "write": ToolSafetyLevel.DESTRUCTIVE,
        },
    }
    
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
            category=ToolCategory.FUND_RUNTIME,
            implementation=method,
            version="1.0.0",
            input_model=input_model,
            examples=examples,
            safety_level=safety_levels.get(name, ToolSafetyLevel.SAFE),  # 【v3.4新增】
            action_safety_map=action_safety_maps.get(name),  # 【v3.4新增】
        )
        logger.debug(f"[shell_register] 已注册工具: {name}, 使用 Pydantic 模型: {input_model.__name__ if input_model else 'None'}, examples: {len(examples)}个, safety: {safety_levels.get(name, ToolSafetyLevel.SAFE).value}")



__all__ = [
    "_register_shell_tools",
    "execute_shell_command",
    "find_command",
    "shell_session",
    "execute_code",
]
