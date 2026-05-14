# -*- coding: utf-8 -*-
"""
Code Execution Register - 代码执行工具注册点

【架构规范】2026-05-02 小沈
- code_execution_register.py: 显式注册（tool_registry.register）
- code_execution_tools.py: 工具函数实现（无装饰器）
- code_execution_schema.py: Pydantic 模型

【2026-05-02 小沈重构】
- 从 @register_tool 装饰器注册改为显式注册（tool_registry.register）
- 按 shell_register.py 模式重写

创建时间: 2026-05-02
更新时间: 2026-05-02
"""

from app.services.tools.registry import tool_registry, ToolCategory
from app.utils.logger import logger

from app.services.tools.code_execution.code_execution_schema import (
    ExecutePythonInput,
    ExecuteJavascriptInput,
)

from app.services.tools.code_execution.code_execution_tools import (
    execute_python,
    execute_javascript,
)

DESCRIPTIONS = {
    "execute_python": """执行Python代码并返回结果。

使用场景：
- 当用户需要运行Python代码片段时使用
- 当用户需要快速验证Python代码逻辑时使用
- 当用户需要执行数据处理、计算等Python脚本时使用


返回数据说明（位于返回的data字段中）：
- stdout: 标准输出内容
- stderr: 标准错误内容
- returncode: 返回码（0表示成功）""",
    "execute_javascript": """执行JavaScript代码并返回结果。

使用场景：
- 当用户需要运行JavaScript代码片段时使用
- 当用户需要快速验证JavaScript代码逻辑时使用
- 当用户需要执行Node.js脚本时使用


返回数据说明（位于返回的data字段中）：
- stdout: 标准输出内容
- stderr: 标准错误内容
- returncode: 返回码（0表示成功）

注意：需要系统已安装Node.js环境""",
}

EXAMPLES = {
    "execute_python": [
        {"code": "print('Hello, World!')"},
        {"code": "import math\nprint(math.sqrt(16))"},
        {"code": "for i in range(5):\n    print(i)", "timeout": 10},
        {"code": "import os\nprint(os.listdir('.'))", "working_dir": "D:/projects"}
    ],
    "execute_javascript": [
        {"code": "console.log('Hello, World!');"},
        {"code": "const result = Math.sqrt(16);\nconsole.log(result);"},
        {"code": "for(let i=0; i<5; i++) {\n  console.log(i);\n}", "timeout": 10},
        {"code": "console.log(process.cwd());", "working_dir": "D:/projects"}
    ],
}


def _register_code_execution_tools():
    """
    【2026-05-02 小沈】显式注册所有Code Execution工具
    使用 Pydantic 模型自动生成 OpenAI Schema
    """
    tool_methods = {
        "execute_python": execute_python,
        "execute_javascript": execute_javascript,
    }

    TOOL_INPUT_MODELS = {
        "execute_python": ExecutePythonInput,
        "execute_javascript": ExecuteJavascriptInput,
    }

    for name, method in tool_methods.items():
        desc = DESCRIPTIONS.get(name, "")
        input_model = TOOL_INPUT_MODELS.get(name)
        examples = EXAMPLES.get(name, [])

        tool_registry.register(
            name=name,
            description=desc,
            category=ToolCategory.CODE_EXECUTION,
            implementation=method,
            version="1.0.0",
            input_model=input_model,
            examples=examples,
        )
        logger.info(f"[code_execution_register] 已注册工具: {name}, 使用 Pydantic 模型: {input_model.__name__ if input_model else 'None'}, examples: {len(examples)}个")


# 【修复 2026-05-07 小沈】守护模式：只首次import时注册，防止重复注册
_initialized = False  # 守护变量，供显式调用时使用

__all__ = ["_register_code_execution_tools"]


__all__ = [
    "execute_python",
    "execute_javascript",
]
