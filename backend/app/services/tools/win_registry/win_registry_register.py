# -*- coding: utf-8 -*-
"""
REGISTRY Register - 注册表工具注册点

【2026-06-16 小沈】拆分registry_control为registry_read/registry_write/registry_delete

创建时间: 2026-05-02
更新时间: 2026-06-16 小沈 - 1→3拆分
"""

from app.services.tools.registry import tool_registry
from app.services.tools.tool_types import ToolCategory
from app.utils.logger import logger

from app.services.tools.win_registry.win_registry_schema import (
    RegistryReadInput,
    RegistryWriteInput,
    RegistryDeleteInput,
)

from app.services.tools.win_registry.win_registry_tools import (
    registry_read,
    registry_write,
    registry_delete,
)

REGISTRY_TOOL_DESCRIPTIONS = {
    "registry_read": """读取Windows注册表键值。必填参数:key_path(注册表键路径,如Software\\Microsoft\\Windows\\CurrentVersion)。可选参数:value_name(值名称,不填读取默认值)、hive(根键HKCU/HKLM/HKCR/HKU/HKCC,默认HKCU)。适用场景:需要查看注册表配置、读取安装路径、获取系统设置时使用。""",
    "registry_write": """写入Windows注册表键值。必填参数:key_path(键路径)、value_name(值名称)、value(值数据)。可选参数:value_type(值类型,auto_detect/REG_SZ/REG_EXPAND_SZ/REG_DWORD/REG_QWORD/REG_BINARY/REG_MULTI_SZ,默认auto_detect)、hive(根键,默认HKCU)。写入前自动备份。适用场景:需要修改注册表配置、设置程序路径、配置系统参数时使用。需谨慎操作。""",
    "registry_delete": """删除Windows注册表键值或子键。必填参数:key_path(键路径)。可选参数:value_name(值名称,不填则删除整个键)、hive(根键,默认HKCU)、recursive(递归删除子键,键不为空时需设为True)。删除前自动备份。适用场景:需要移除注册表项、清理无效配置时使用。需谨慎操作。""",
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
            category=ToolCategory.SYSTEM,
            implementation=method,
            version="1.0.0",
            input_model=input_model,
            examples=examples,
            needs_confirmation=(name in CONFIRM_TOOLS),
        )
        logger.debug(
            f"[registry_register] 已注册工具: {name}, "
            f"使用 Pydantic 模型: {input_model.__name__ if input_model else 'None'}, "
            f"examples: {len(examples)}个"
        )

__all__ = ["_register_registry_tools"]
