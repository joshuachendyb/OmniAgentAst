# -*- coding: utf-8 -*-
"""
REGISTRY Register - 注册表工具注册点

【2026-06-16 小沈】拆分registry_control为registry_read/registry_write/registry_delete

创建时间: 2026-05-02
更新时间: 2026-06-16 小沈 - 1→3拆分
"""

from app.tools.registry import tool_registry
from app.tools.tool_types import ToolCategory
from app.utils.logger import logger

# 注册表工具依赖配置 — 小健 2026-06-18
# 注册表工具使用内置库，无第三方依赖
REGISTRY_TOOL_DEPENDENCIES = {
    tool_name: [] for tool_name in [
        "registry_read", "registry_write", "registry_delete"
    ]
}

from app.tools.win_registry.win_registry_schema import (
    RegistryReadInput,
    RegistryWriteInput,
    RegistryDeleteInput,
)

from app.tools.win_registry.registry_read import registry_read
from app.tools.win_registry.registry_write import registry_write
from app.tools.win_registry.registry_delete import registry_delete

REGISTRY_TOOL_DESCRIPTIONS = {
    "registry_read": """读取Windows注册表键值。适用场景:需要查看注册表配置、获取系统设置时使用。""",
    "registry_write": """写入Windows注册表键值,写入前自动备份。适用场景:需要修改注册表配置、设置程序路径时使用。需谨慎操作。""",
    "registry_delete": """删除Windows注册表键值或子键,删除前自动备份。适用场景:需要移除注册表项、清理无效配置时使用。需谨慎操作。""",
}

REGISTRY_TOOL_INPUT_MODELS = {
    "registry_read": RegistryReadInput,
    "registry_write": RegistryWriteInput,
    "registry_delete": RegistryDeleteInput,
}

REGISTRY_TOOL_EXAMPLES = {
    "registry_read": [
        {"key_path": "Software\\Microsoft\\Windows\\CurrentVersion", "value_name": "ProductName"},
        {"key_path": "Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\Shell Folders", "value_name": "Desktop", "hive": "HKCU"},
        {"key_path": "Software\\MyApp"},
    ],
    "registry_write": [
        {"key_path": "Software\\MyTestApp", "value_name": "TestValue", "value": "Hello World", "value_type": "REG_SZ"},
        {"key_path": "Software\\MyTestApp", "value_name": "TestNumber", "value": "12345", "value_type": "REG_DWORD"},
        {"key_path": "Software\\MyApp", "value_name": "InstallPath", "value": "C:\\Program Files\\MyApp"},
    ],
    "registry_delete": [
        {"key_path": "Software\\MyTestApp", "value_name": "TestValue"},
        {"key_path": "Software\\TempTest", "recursive": True},
        {"key_path": "Software\\MyApp", "value_name": "OldSetting", "hive": "HKLM"},
    ],
}


def _register_registry_tools():
    """注册注册表工具 - 【2026-06-16 小沈】1→3拆分为registry_read/registry_write/registry_delete"""
    CONFIRM_TOOLS = {"registry_write", "registry_delete"}

    tool_methods = {
        "registry_read": registry_read,
        "registry_write": registry_write,
        "registry_delete": registry_delete,
    }

    for name, method in tool_methods.items():
        desc = REGISTRY_TOOL_DESCRIPTIONS.get(name, "")
        input_model = REGISTRY_TOOL_INPUT_MODELS.get(name)
        examples = REGISTRY_TOOL_EXAMPLES.get(name, [])

        tool_registry.register(
            name=name,
            description=desc,
            category=ToolCategory.WIN_REGISTRY,
            implementation=method,
            version="1.0.0",
            input_model=input_model,
            examples=examples,
            needs_confirmation=(name in CONFIRM_TOOLS),
            dependencies=REGISTRY_TOOL_DEPENDENCIES.get(name, []),
        )
        logger.debug(
            f"[registry_register] 已注册工具: {name}, "
            f"使用 Pydantic 模型: {input_model.__name__ if input_model else 'None'}, "
            f"examples: {len(examples)}个"
        )

__all__ = ["_register_registry_tools"]
