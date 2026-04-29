# -*- coding: utf-8 -*-
"""
SYSTEM Register - 系统信息工具注册点

【架构规范】2026-04-29 小沈

【工具列表】（共1个）
1. get_system_info - 获取系统信息

创建时间: 2026-04-29
"""

import logging
from app.services.tools.registry import ToolCategory, tool_registry
from app.utils.logger import logger

from app.services.tools.system.system_schema import (
    GetSystemInfoInput,
)

from app.services.tools.system.system_tools import (
    get_system_info,
)

# 工具描述
SYSTEM_TOOL_DESCRIPTIONS = {
    "get_system_info": "获取系统信息，包括平台、CPU、内存、磁盘、网络等详细信息",
}

# 模型映射
SYSTEM_TOOL_INPUT_MODELS = {
    "get_system_info": GetSystemInfoInput,
}

# 使用示例
SYSTEM_TOOL_EXAMPLES = {
    "get_system_info": [
        {"info_type": "all"},
        {"info_type": "cpu"},
        {"info_type": "memory"},
        {"info_type": "disk"},
        {"info_type": "basic"},
    ],
}


def _register_system_tools():
    """注册所有系统信息工具"""
    tool_methods = {
        "get_system_info": get_system_info,
    }

    for name, method in tool_methods.items():
        desc = SYSTEM_TOOL_DESCRIPTIONS.get(name, "")
        input_model = SYSTEM_TOOL_INPUT_MODELS.get(name)
        examples = SYSTEM_TOOL_EXAMPLES.get(name, [])

        tool_registry.register(
            name=name,
            description=desc,
            category=ToolCategory.SYSTEM,
            implementation=method,
            version="1.0.0",
            input_model=input_model,
            examples=examples,
        )
        logger.info(
            f"[system_register] 已注册工具: {name}, "
            f"使用 Pydantic 模型: {input_model.__name__ if input_model else 'None'}, "
            f"examples: {len(examples)}个"
        )


# 触发注册
_register_system_tools()
