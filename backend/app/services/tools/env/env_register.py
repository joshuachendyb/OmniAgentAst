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
    "get_env": "获取指定环境变量的值，支持设置默认值（变量不存在时返回默认值）。适合读取PATH、HOME、JAVA_HOME等系统环境变量",
    "set_env": "设置环境变量，支持进程级（仅当前进程有效）和用户级（持久化到系统）作用域。适合临时修改变量、配置环境",
    "list_env": "列出所有环境变量或指定前缀的环境变量（如列出所有JAVA_开头的变量）。适合查看所有环境变量、查找特定前缀变量",
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
    ],
    "set_env": [
        {"name": "MY_VAR", "value": "test_value", "scope": "process"},
        {"name": "APP_PATH", "value": "D:/myapp", "scope": "user"},
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