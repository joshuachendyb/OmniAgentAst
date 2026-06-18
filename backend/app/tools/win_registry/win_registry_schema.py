# -*- coding: utf-8 -*-
"""
REGISTRY Schema - 注册表工具参数模型

【Schema Docstring 规范】小健 2026-06-18
一般情况下，严禁给Schema类加docstring。
仅在以下情况可以添加：
1. 函数使用过于复杂，需要详细说明
2. 多action的tool，需要说明不同action的用法
3. 添加的是tool描述的增强信息，不是冗余信息

禁止：
- 重复register.py中的描述
- 添加过于冗长的说明
- 添加与参数无关的内容

工具列表(3个LLM工具):
1. registry_read - 读取注册表键值
2. registry_write - 写入注册表键值
3. registry_delete - 删除注册表键值或子键

Author: 小沈 - 2026-05-02
更新: 小沈 - 2026-06-16 拆分registry_control为3个独立工具
"""

from pydantic import BaseModel, Field
from typing import Optional, Literal


class RegistryReadInput(BaseModel):
    key_path: str = Field(
        ..., description="注册表键路径(必填)。如 Software\\Microsoft\\Windows\\CurrentVersion。若含根键前缀则自动忽略 hive 参数"
    )
    value_name: Optional[str] = Field(
        default=None, description="值名称(可选)。不填则读取默认值"
    )
    hive: Literal["HKCU", "HKLM", "HKCR", "HKU", "HKCC"] = Field(
        default="HKCU", description="注册表根键(可选)。默认HKCU"
    )


class RegistryWriteInput(BaseModel):
    key_path: str = Field(
        ..., description="注册表键路径(必填)。如 Software\\MyApp"
    )
    value_name: str = Field(
        ..., description="值名称(必填)。如 Version、InstallPath"
    )
    value: str = Field(
        ..., description="值数据(必填)。如 '1.0'、'C:\\Program Files\\MyApp'"
    )
    value_type: Literal["auto_detect", "REG_SZ", "REG_EXPAND_SZ", "REG_DWORD", "REG_QWORD", "REG_BINARY", "REG_MULTI_SZ"] = Field(
        default="auto_detect", description="值类型(可选)。默认auto_detect。REG_EXPAND_SZ=可扩展字符串(含%VAR%),REG_QWORD=64位整数"
    )
    hive: Literal["HKCU", "HKLM", "HKCR", "HKU", "HKCC"] = Field(
        default="HKCU", description="注册表根键(可选)。默认HKCU"
    )


class RegistryDeleteInput(BaseModel):
    key_path: str = Field(
        ..., description="注册表键路径(必填)。如 Software\\MyApp"
    )
    value_name: Optional[str] = Field(
        default=None, description="值名称(可选)。不填则删除整个键"
    )
    hive: Literal["HKCU", "HKLM", "HKCR", "HKU", "HKCC"] = Field(
        default="HKCU", description="注册表根键(可选)。默认HKCU"
    )
    recursive: bool = Field(
        default=False, description="递归删除子键(可选)。默认False。键不为空时需设为True才能删除"
    )


__all__ = [
    "RegistryReadInput",
    "RegistryWriteInput",
    "RegistryDeleteInput",
]
