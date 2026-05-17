# -*- coding: utf-8 -*-
"""
ENV Register - 环境变量工具注册点

【架构规范】2026-04-29 小沈
- env_register.py 作为环境变量工具的注册点
- 使用 Pydantic 模型注册

【工具列表】（共3个）— 【2026-05-17 小沈】P1-5: 5→3，delete_env合入set_env，exists_env消除
1. get_env - 获取环境变量
2. set_env - 设置或删除环境变量（action="set"|"delete"）
3. list_env - 列出环境变量

已取消注册（向下兼容，函数仍保留）：
- delete_env → 合入 set_env(action="delete")
- exists_env → get_env 已返回 data.exists

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
)

from app.services.tools.environment.env_tools import (
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


【重要】返回环境变量的值，自动展开嵌套变量

使用示例：
- 获取PATH：{"name": "PATH"}
- 获取带默认值：{"name": "MY_API_KEY", "default": "unknown"}

返回数据说明：
- 成功时 code="SUCCESS"，data 包含：name(变量名)、value(变量值或default)、exists(是否存在)、scope(作用域)、expanded(是否展开嵌套变量)
- 变量不存在时 exists=False，value 取 default 参数值
- 失败时 code="ERR_ENV_GET"，data=null，message 含错误信息""",
    "set_env": """设置或删除环境变量。

使用场景：
- 当用户需要设置环境变量时使用
- 当用户想要配置系统环境时使用
- 当用户需要临时设置运行参数时使用
- 当用户需要删除环境变量时使用（action="delete"）


【重要】设置或删除环境变量。默认action="set"设置变量，action="delete"删除变量。默认仅对当前进程有效。若 scope 为 user/system，Agent 尝试持久化，遇权限不足自动降级为 process 并提示用户

使用示例：
- 设置变量：{"name": "MY_API_KEY", "value": "sk-abc123"}
- 追加PATH：{"name": "PATH", "value": "C:\\Python39", "append_mode": true}
- 删除变量：{"name": "MY_VAR", "action": "delete"}
- 删除用户级：{"name": "APP_PATH", "action": "delete", "scope": "user"}

返回数据说明：
- action="set"成功时 code="SUCCESS"，data 包含：name(变量名)、value(实际生效值)、scope(实际作用域，可能被降级为process)、append_mode(是否追加模式)
- action="delete"成功时 code="SUCCESS"，data 包含：name(变量名)、deleted(是否实际删除)、scope(作用域)
- 权限不足时自动降级 scope 为 process，message 提示降级原因
- 名称无效时 code="ERR_ENV_INVALID_NAME"，值无效时 code="ERR_ENV_INVALID_VALUE"，作用域无效时 code="ERR_ENV_INVALID_SCOPE"，data 均为 null
- 异常时 code="ERR_ENV_SET"，data=null，message 含错误信息""",
    "list_env": """列出所有环境变量或指定前缀的环境变量。

使用场景：
- 当用户需要查看所有环境变量时使用
- 当用户想要查找特定前缀变量时使用
- 当用户问"有哪些JAVA相关变量"时使用


【重要】返回环境变量列表，支持前缀过滤

返回数据说明：
- 成功时 code="SUCCESS"，data 包含：count(变量总数)、variables(列表，每项含 name 和 value)、prefix(过滤前缀)、include_system(是否含系统级)
- variables 按 name 字母升序排列
- 异常时 code="ERR_ENV_LIST"，data=null，message 含错误信息""",
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
        {"name": "MY_VAR", "action": "delete"},
        {"name": "APP_PATH", "action": "delete", "scope": "user"},
    ],
    "list_env": [
        {"prefix": "PY"},
        {"prefix": "JAVA", "include_system": True},
        {},
    ],
}


def _register_env_tools():
    """注册所有环境变量工具 - 【2026-05-17 小沈】P1-5: 5→3"""
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
_initialized = False  # 守护变量，供显式调用时使用

__all__ = ["_register_env_tools"]
