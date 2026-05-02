# -*- coding: utf-8 -*-
"""
REGISTRY Register - 注册表工具注册点

【架构规范】2026-05-02 小沈

【工具列表】（共3个）
1. reg_read - 读取注册表键值
2. reg_write - 写入注册表键值
3. reg_delete - 删除注册表键值

创建时间: 2026-05-02
更新时间: 2026-05-02
"""

import logging
from app.services.tools.registry import ToolCategory, tool_registry
from app.utils.logger import logger

from app.services.tools.registry_tools.registry_schema import (
    RegReadInput,
    RegWriteInput,
    RegDeleteInput,
)

from app.services.tools.registry_tools.registry_tools import (
    reg_read,
    reg_write,
    reg_delete,
)

REGISTRY_TOOL_DESCRIPTIONS = {
    "reg_read": "读取Windows注册表键值，支持所有根键（HKEY_LOCAL_MACHINE、HKEY_CURRENT_USER等）",
    "reg_write": "写入Windows注册表键值，支持多种数据类型（REG_SZ、REG_DWORD、REG_BINARY等）",
    "reg_delete": "删除Windows注册表键值或子键，需谨慎操作",
}

REGISTRY_TOOL_INPUT_MODELS = {
    "reg_read": RegReadInput,
    "reg_write": RegWriteInput,
    "reg_delete": RegDeleteInput,
}

REGISTRY_TOOL_EXAMPLES = {
    "reg_read": [
        {"root_key": "HKEY_LOCAL_MACHINE", "sub_key": "SOFTWARE\\Microsoft\\Windows\\CurrentVersion", "value_name": "ProductName"},
        {"root_key": "HKEY_CURRENT_USER", "sub_key": "Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\Shell Folders", "value_name": "Desktop"},
        {"root_key": "HKEY_LOCAL_MACHINE", "sub_key": "SYSTEM\\CurrentControlSet\\Control\\ComputerName\\ComputerName", "value_name": "ComputerName"},
    ],
    "reg_write": [
        {"root_key": "HKEY_CURRENT_USER", "sub_key": "Software\\MyTestApp", "value_name": "TestValue", "value_data": "Hello World", "value_type": "REG_SZ"},
        {"root_key": "HKEY_CURRENT_USER", "sub_key": "Software\\MyTestApp", "value_name": "TestNumber", "value_data": "12345", "value_type": "REG_DWORD"},
    ],
    "reg_delete": [
        {"root_key": "HKEY_CURRENT_USER", "sub_key": "Software\\MyTestApp", "value_name": "TestValue"},
        {"root_key": "HKEY_CURRENT_USER", "sub_key": "Software\\MyTestApp"},
    ],
}


def _register_registry_tools():
    """注册所有注册表工具"""
    tool_methods = {
        "reg_read": reg_read,
        "reg_write": reg_write,
        "reg_delete": reg_delete,
    }

    for name, method in tool_methods.items():
        desc = REGISTRY_TOOL_DESCRIPTIONS.get(name, "")
        input_model = REGISTRY_TOOL_INPUT_MODELS.get(name)
        examples = REGISTRY_TOOL_EXAMPLES.get(name, [])

        tool_registry.register(
            name=name,
            description=desc,
            category=ToolCategory.REGISTRY_TOOLS,
            implementation=method,
            version="1.0.0",
            input_model=input_model,
            examples=examples,
        )
        logger.info(
            f"[registry_register] 已注册工具: {name}, "
            f"使用 Pydantic 模型: {input_model.__name__ if input_model else 'None'}, "
            f"examples: {len(examples)}个"
        )


_register_registry_tools()
