# -*- coding: utf-8 -*-
"""
REGISTRY Register - 注册表工具注册点

【2026-05-18 小沈】3→1：reg_read/reg_write/reg_delete合并为registry_control(action路由)
原3个函数保留为内部函数，由registry_control按action分发

创建时间: 2026-05-02
更新时间: 2026-05-18 小沈 - 3→1合并
"""

import logging
from app.services.tools.registry import ToolCategory, tool_registry
from app.utils.logger import logger

from app.services.tools.system.reg_schema import (
    RegistryControlInput,
)

from app.services.tools.system.reg_tools import (
    registry_control,
)

REGISTRY_TOOL_DESCRIPTIONS = {
    "registry_control": """Windows注册表统一控制入口，通过action参数执行read/write/delete操作。

使用场景：
- 当用户需要读取、写入或删除Windows注册表时使用
- 合并原reg_read/reg_write/reg_delete三个工具

【重要】action必填；仅限Windows平台

使用示例：
- 读取注册表值：{"action": "read", "key_path": "Software\\MyApp", "value_name": "InstallPath"}
- 写入注册表值：{"action": "write", "key_path": "Software\\MyApp", "value_name": "Version", "value": "1.0"}
- 删除注册表值：{"action": "delete", "key_path": "Software\\MyApp", "value_name": "OldValue"}
- 删除整个键：{"action": "delete", "key_path": "Software\\MyApp", "recursive": true}

返回数据说明：
- read: 含key_path/value_name/value/value_type
- write: 含key_path/value_name/value/value_type/backup
- delete: 含key_path/action(deleted_value/deleted_key)""",
}

REGISTRY_TOOL_INPUT_MODELS = {
    "registry_control": RegistryControlInput,
}

REGISTRY_TOOL_EXAMPLES = {
    "registry_control": [
        {"action": "read", "key_path": "Software\\Microsoft\\Windows\\CurrentVersion", "value_name": "ProductName"},
        {"action": "read", "key_path": "Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\Shell Folders", "value_name": "Desktop", "hive": "HKCU"},
        {"action": "write", "key_path": "Software\\MyTestApp", "value_name": "TestValue", "value": "Hello World", "value_type": "REG_SZ"},
        {"action": "write", "key_path": "Software\\MyTestApp", "value_name": "TestNumber", "value": "12345", "value_type": "REG_DWORD", "backup_before_write": True},
        {"action": "delete", "key_path": "Software\\MyTestApp", "value_name": "TestValue"},
        {"action": "delete", "key_path": "Software\\TempTest", "recursive": True, "backup_before_delete": True},
    ],
}


def _register_registry_tools():
    """注册注册表工具 - 【2026-05-18 小沈】3→1合并为registry_control"""
    tool_methods = {
        "registry_control": registry_control,
    }

    for name, method in tool_methods.items():
        desc = REGISTRY_TOOL_DESCRIPTIONS.get(name, "")
        input_model = REGISTRY_TOOL_INPUT_MODELS.get(name)
        examples = REGISTRY_TOOL_EXAMPLES.get(name, [])

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
            f"[registry_register] 已注册工具: {name}, "
            f"使用 Pydantic 模型: {input_model.__name__ if input_model else 'None'}, "
            f"examples: {len(examples)}个"
        )


_initialized = False

__all__ = ["_register_registry_tools"]
