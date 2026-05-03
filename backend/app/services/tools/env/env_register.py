# -*- coding: utf-8 -*-
"""
ENV Register - 环境变量工具注册点

【架构规范】2026-04-29 小沈
- env_register.py 作为环境变量工具的注册点
- 使用 Pydantic 模型注册

【工具列表】（共3个）
1. get_env - 获取环境变量
2. set_env - 设置环境变量
3. list_env - 列出环境变量

创建时间: 2026-04-29
"""

# ============================================================
# 环境变量工具注册 - 使用 Pydantic 模型
# ============================================================
import logging
from app.services.tools.registry import ToolCategory, tool_registry
from app.utils.logger import logger

from app.services.tools.env.env_schema import (
    GetEnvInput,
    SetEnvInput,
    ListEnvInput,
)

from app.services.tools.env.env_tools import (
    get_env,
    set_env,
    list_env,
)

# 工具描述
ENV_TOOL_DESCRIPTIONS = {
    "get_env": """获取指定的环境变量值。

使用场景：
- 当用户需要获取环境变量时使用
- 当用户想要读取系统配置时使用
- 当用户需要获取 PATH 等系统环境变量时使用

参数说明：
- name：环境变量名称
- default：默认值（可选）
- scope：作用域（可选），默认 process
- expand_vars：是否展开嵌套变量（可选），默认 true

【重要】返回环境变量的值，自动展开嵌套变量

使用示例：
- 获取PATH：{"name": "PATH"}
- 获取带默认值：{"name": "MY_API_KEY", "default": "unknown"}""",
    "set_env": """设置指定的环境变量值。

使用场景：
- 当用户需要设置环境变量时使用
- 当用户想要配置系统环境时使用
- 当用户需要临时设置运行参数时使用

参数说明：
- name：环境变量名称
- value：环境变量值
- scope：作用域（可选），默认 process
- append_mode：追加模式（可选），默认 false

【重要】设置环境变量。默认仅对当前进程有效。若 scope 为 user/system，Agent 尝试持久化，遇权限不足自动降级为 process 并提示用户

使用示例：
- 设置变量：{"name": "MY_API_KEY", "value": "sk-abc123"}
- 追加PATH：{"name": "PATH", "value": "C:\\Python39", "append_mode": true}""",
    "list_env": """列出所有环境变量或指定前缀的环境变量。

使用场景：
- 当用户需要查看所有环境变量时使用
- 当用户想要查找特定前缀变量时使用
- 当用户问"有哪些JAVA相关变量"时使用

参数说明：
- prefix：环境变量名前缀过滤（可选），例如 PY、JAVA
- include_system：是否包含系统级环境变量（可选），默认 false

【重要】返回环境变量列表，支持前缀过滤""",
}

# 模型映射
ENV_TOOL_INPUT_MODELS = {
    "get_env": GetEnvInput,
    "set_env": SetEnvInput,
    "list_env": ListEnvInput,
}

# 使用示例
ENV_TOOL_EXAMPLES = {
    "get_env": [
        {"name": "PATH"},
        {"name": "JAVA_HOME", "default": "C:/Java"},
        {"name": "HOME", "default": "C:/Users"},
        {"name": "PATH", "scope": "user", "expand_vars": True},
    ],
    "set_env": [
        {"name": "MY_VAR", "value": "test_value", "scope": "process"},
        {"name": "APP_PATH", "value": "D:/myapp", "scope": "user"},
        {"name": "PATH", "value": "C:/Python39", "append_mode": True},
    ],
    "list_env": [
        {"prefix": "PY"},
        {"prefix": "JAVA", "include_system": True},
        {},
    ],
}


def _register_env_tools():
    """注册所有环境变量工具"""
    tool_methods = {
        "get_env": get_env,
        "set_env": set_env,
        "list_env": list_env,
    }

    for name, method in tool_methods.items():
        desc = ENV_TOOL_DESCRIPTIONS.get(name, "")
        input_model = ENV_TOOL_INPUT_MODELS.get(name)
        examples = ENV_TOOL_EXAMPLES.get(name, [])

        tool_registry.register(
            name=name,
            description=desc,
            category=ToolCategory.ENV,
            implementation=method,
            version="1.0.0",
            input_model=input_model,
            examples=examples,
        )
        logger.info(
            f"[env_register] 已注册工具: {name}, "
            f"使用 Pydantic 模型: {input_model.__name__ if input_model else 'None'}, "
            f"examples: {len(examples)}个"
        )


# 触发注册
_register_env_tools()