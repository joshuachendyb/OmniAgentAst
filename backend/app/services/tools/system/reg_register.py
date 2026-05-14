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

from app.services.tools.system.reg_schema import (
    RegReadInput,
    RegWriteInput,
    RegDeleteInput,
)

from app.services.tools.system.reg_tools import (
    reg_read,
    reg_write,
    reg_delete,
)

# 按文档7.2节定义的description
REGISTRY_TOOL_DESCRIPTIONS = {
    "reg_read": "读取 Windows 注册表指定键的值。\n\n使用场景：\n- 当用户需要读取 Windows 注册表中的配置信息时使用\n- 当用户想要获取系统或应用程序的注册表设置时使用\n\n【重要】仅限 Windows 平台。Agent 自动处理路径标准化与类型格式化\n\n返回数据说明：\n统一返回 {code, data, message} 格式。\n- 成功时 code=\"SUCCESS\"，data 包含：key_path（完整键路径）、value_name（值名称，默认值显示为\"(默认)\"）、value（读取到的值，hex格式时为十六进制字符串）、value_type（注册表类型名，如 REG_SZ/REG_DWORD/REG_BINARY 等）\n- 失败时 data=null，code 为错误码：ERR_REG_INVALID_ROOT_KEY（无效根键）、ERR_REG_KEY_NOT_FOUND（键或值不存在）、ERR_REG_PERMISSION_DENIED（权限不足）、ERR_REG_READ_FAILED（读取异常）",
    "reg_write": "写入或创建 Windows 注册表键值。\n\n使用场景：\n- 当用户需要修改 Windows 注册表设置时使用\n- 当用户想要创建新的注册表项时使用\n\n【重要】仅限 Windows 平台。Agent 自动推断类型、强制备份、高危拦截\n\n返回数据说明：\n统一返回 {code, data, message} 格式。\n- 成功时 code=\"SUCCESS\"，data 包含：key_path（完整键路径）、value_name（值名称）、value（写入的值）、value_type（实际使用的类型名，如 REG_SZ/REG_DWORD 等）、backup（是否已备份，bool）；dry_run模式时 data 仅含 key_path 和 dry_run=true\n- 失败时 data=null，code 为错误码：ERR_REG_INVALID_ROOT_KEY（无效根键）、ERR_REG_KEY_NOT_FOUND（dry_run时键路径不存在）、ERR_REG_UNSUPPORTED_TYPE（不支持的值类型）、ERR_REG_VALIDATE_FAILED（dry_run校验失败）、ERR_REG_PERMISSION_DENIED（权限不足）、ERR_REG_WRITE_FAILED（写入异常）",
    "reg_delete": "删除 Windows 注册表键值或整个子键。\n\n使用场景：\n- 当用户需要删除注册表中的配置时使用\n- 当用户想要清理无用注册表项时使用\n\n【重要】仅限 Windows 平台。操作不可逆需谨慎使用，建议先备份\n\n返回数据说明：\n统一返回 {code, data, message} 格式。\n- 成功时 code=\"SUCCESS\"，data 包含：key_path（完整键路径）、action（操作类型，\"deleted_value\"表示删除值、\"deleted_key\"表示删除键）；删除键时额外含 recursive（是否递归删除，bool）；删除值时额外含 value_name（被删除的值名称）\n- 失败时 data=null，code 为错误码：ERR_REG_INVALID_ROOT_KEY（无效根键）、ERR_REG_KEY_NOT_FOUND（键或值不存在）、ERR_REG_KEY_NOT_EMPTY（非递归模式下键不为空）、ERR_REG_CANNOT_DELETE_ROOT（不能删除根键下子键）、ERR_REG_PERMISSION_DENIED（权限不足）、ERR_REG_DELETE_FAILED（删除失败）",
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
        {"key_path": "Software\\MyApp", "output_format": "hex"},
    ],
    "reg_write": [
        {"key_path": "Software\\MyTestApp", "value_name": "TestValue", "value": "Hello World", "value_type": "REG_SZ"},
        {"key_path": "Software\\MyTestApp", "value_name": "TestNumber", "value": "12345", "value_type": "REG_DWORD", "backup_before_write": True},
        {"key_path": "System\\CurrentControlSet\\Services\\TestService", "value_name": "Test", "value": "1", "dry_run": True},
    ],
    "reg_delete": [
        {"key_path": "Software\\MyTestApp", "value_name": "TestValue"},
        {"key_path": "Software\\MyTestApp", "backup_before_delete": True},
        {"key_path": "Software\\TempTest", "recursive": True, "backup_before_delete": True},
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


# 【修复 2026-05-07 小沈】守护模式：只首次import时注册，防止重复注册
_initialized = False  # 守护变量，供显式调用时使用

__all__ = ["_register_registry_tools"]
