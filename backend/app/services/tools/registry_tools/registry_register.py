# -*- coding: utf-8 -*-
"""
REGISTRY Register - 注册表工具注册点

【架构规范】2026-05-02 小沈
【更新时间】2026-05-03 小沈
【设计依据】按文档7.2节参数定义

【工具列表】（共3个）
1. reg_read - 读取注册表键值
2. reg_write - 写入注册表键值
3. reg_delete - 删除注册表键值

创建时间: 2026-05-02
更新时间: 2026-05-03
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

# 按文档7.2节定义的description
REGISTRY_TOOL_DESCRIPTIONS = {
    "reg_read": "读取 Windows 注册表指定键的值。\n\n使用场景：\n- 当用户需要读取 Windows 注册表中的配置信息时使用\n- 当用户想要获取系统或应用程序的注册表设置时使用\n\n参数说明：\n- key_path：注册表键路径\n- value_name：值名称（可选）\n- hive：根键（可选），默认 HKCU\n- output_format：输出格式（可选），默认 auto\n\n【重要】仅限 Windows 平台。Agent 自动处理路径标准化与类型格式化",
    "reg_write": "写入或创建 Windows 注册表键值。\n\n使用场景：\n- 当用户需要修改 Windows 注册表设置时使用\n- 当用户想要创建新的注册表项时使用\n\n参数说明：\n- key_path：注册表键路径\n- value_name：值名称\n- value：值数据\n- value_type：值类型（可选），默认 auto_detect\n- backup_before_write：写入前备份（可选），默认 true\n- dry_run：预演模式（可选），默认 false\n\n【重要】仅限 Windows 平台。Agent 自动推断类型、强制备份、高危拦截",
    "reg_delete": "删除 Windows 注册表键值或整个子键。\n\n使用场景：\n- 当用户需要删除注册表中的配置时使用\n- 当用户想要清理无用注册表项时使用\n\n参数说明：\n- key_path：注册表键路径\n- value_name：值名称（可选）\n- backup_before_delete：删除前备份（可选），默认 true\n- recursive：递归删除（可选），默认 false\n\n【重要】仅限 Windows 平台。操作不可逆需谨慎使用，建议先备份",
}

REGISTRY_TOOL_INPUT_MODELS = {
    "reg_read": RegReadInput,
    "reg_write": RegWriteInput,
    "reg_delete": RegDeleteInput,
}

# 按文档7.2节定义的examples（使用key_path参数格式）
REGISTRY_TOOL_EXAMPLES = {
    "reg_read": [
        {"key_path": "Software\\Microsoft\\Windows\\CurrentVersion", "value_name": "ProductName"},
        {"key_path": "Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\Shell Folders", "value_name": "Desktop", "hive": "HKCU"},
        {"key_path": "SYSTEM\\CurrentControlSet\\Control\\ComputerName\\ComputerName", "value_name": "ComputerName", "hive": "HKLM"},
    ],
    "reg_write": [
        {"key_path": "Software\\MyTestApp", "value_name": "TestValue", "value": "Hello World", "value_type": "REG_SZ"},
        {"key_path": "Software\\MyTestApp", "value_name": "TestNumber", "value": "12345", "value_type": "REG_DWORD", "backup_before_write": True},
    ],
    "reg_delete": [
        {"key_path": "Software\\MyTestApp", "value_name": "TestValue"},
        {"key_path": "Software\\MyTestApp"},
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
