# -*- coding: utf-8 -*-
"""
ENV Register - 环境变量工具注册点

【架构规范】2026-04-29 小沈
- env_register.py 作为环境变量工具的注册点
- 使用 Pydantic 模型注册

【工具列表】（共5个）
1. get_env - 获取环境变量
2. set_env - 设置环境变量
3. list_env - 列出环境变量
4. delete_env - 删除环境变量
5. exists_env - 检查环境变量是否存在

创建时间: 2026-04-29
"""

# ============================================================
# 环境变量工具注册 - 使用 Pydantic 模型
# ============================================================
from app.services.tools.registry import ToolCategory, tool_registry
from app.utils.logger import logger

from app.services.tools.environment.env_schema import (
    GetEnvInput,
    SetEnvInput,
    ListEnvInput,
    DeleteEnvInput,
    ExistsEnvInput,
)

from app.services.tools.environment.env_tools import (
    get_env,
    set_env,
    list_env,
    delete_env,
    exists_env,
)

# 工具描述
ENV_TOOL_DESCRIPTIONS = {
    "get_env": """获取指定的环境变量值。

使用场景：
- 当用户需要获取环境变量时使用
- 当用户想要读取系统配置时使用
- 当用户需要获取 PATH 等系统环境变量时使用


【重要】返回环境变量的值，自动展开嵌套变量

使用示例：
- 获取PATH：{"name": "PATH"}
- 获取带默认值：{"name": "MY_API_KEY", "default": "unknown"}""",
    "set_env": """设置指定的环境变量值。

使用场景：
- 当用户需要设置环境变量时使用
- 当用户想要配置系统环境时使用
- 当用户需要临时设置运行参数时使用


【重要】设置环境变量。默认仅对当前进程有效。若 scope 为 user/system，Agent 尝试持久化，遇权限不足自动降级为 process 并提示用户

使用示例：
- 设置变量：{"name": "MY_API_KEY", "value": "sk-abc123"}
- 追加PATH：{"name": "PATH", "value": "C:\\Python39", "append_mode": true}""",
    "list_env": """列出所有环境变量或指定前缀的环境变量。
 
使用场景：
- 当用户需要查看所有环境变量时使用
- 当用户想要查找特定前缀变量时使用
- 当用户问"有哪些JAVA相关变量"时使用
 
 
【重要】返回环境变量列表，支持前缀过滤""",
    "delete_env": """删除指定的环境变量。
 
使用场景：
- 当用户需要删除环境变量时使用
- 当用户想要清理系统配置时使用
- 当用户需要移除临时变量时使用
 
 
【重要】删除环境变量。默认仅对当前进程有效。若 scope 为 user/system，Agent 尝试持久化，遇权限不足自动降级为 process 并提示用户
 
使用示例：
- 删除变量：{"name": "MY_VAR"}
- 删除用户级：{"name": "APP_PATH", "scope": "user"}""",
    "exists_env": """检查环境变量是否存在。
 
使用场景：
- 当用户需要检查环境变量是否存在时使用
- 当用户想要验证系统配置时使用
- 当用户需要判断变量是否设置时使用
 
 
使用示例：
- 检查变量：{"name": "JAVA_HOME"}
- 检查系统级：{"name": "PATH", "scope": "system"}""",
}

# 模型映射
ENV_TOOL_INPUT_MODELS = {
    "get_env": GetEnvInput,
    "set_env": SetEnvInput,
    "list_env": ListEnvInput,
    "delete_env": DeleteEnvInput,
    "exists_env": ExistsEnvInput,
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
    "delete_env": [
        {"name": "MY_VAR"},
        {"name": "APP_PATH", "scope": "user"},
    ],
    "exists_env": [
        {"name": "JAVA_HOME"},
        {"name": "PATH", "scope": "system"},
    ],
}


def _register_env_tools():
    """注册所有环境变量工具"""
    tool_methods = {
        "get_env": get_env,
        "set_env": set_env,
        "list_env": list_env,
        "delete_env": delete_env,
        "exists_env": exists_env,
    }

    for name, method in tool_methods.items():
        desc = ENV_TOOL_DESCRIPTIONS.get(name, "")
        input_model = ENV_TOOL_INPUT_MODELS.get(name)
        examples = ENV_TOOL_EXAMPLES.get(name, [])

        tool_registry.register(
            name=name,
            description=desc,
            category=ToolCategory.ENVIRONMENT,
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


# 【修复 2026-05-07 小沈】守护模式：只首次import时注册，防止重复注册
_initialized = False
if not _initialized:
    _register_env_tools()
    _initialized = True
