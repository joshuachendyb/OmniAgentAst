# -*- coding: utf-8 -*-
"""
REGISTRY 工具参数 Schema 定义

【创建时间】2026-05-02 小沈
【设计依据】按2026-04-29新增工具规范流程

职责：
定义 registry 工具的 Pydantic 模型。

工具列表（3个）：
1. reg_read - 读取注册表键值
2. reg_write - 写入注册表键值
3. reg_delete - 删除注册表键值

Author: 小沈 - 2026-05-02
"""

from pydantic import BaseModel, Field
from typing import Optional, Literal


class RegReadInput(BaseModel):
    """reg_read 工具的输入参数"""
    root_key: Literal["HKEY_CLASSES_ROOT", "HKEY_CURRENT_USER", "HKEY_LOCAL_MACHINE", "HKEY_USERS", "HKEY_CURRENT_CONFIG"] = Field(
        description="注册表根键。可选值：HKEY_CLASSES_ROOT、HKEY_CURRENT_USER、HKEY_LOCAL_MACHINE、HKEY_USERS、HKEY_CURRENT_CONFIG"
    )
    sub_key: str = Field(
        description="子键路径。例如：Software\\Microsoft\\Windows\\CurrentVersion"
    )
    value_name: Optional[str] = Field(
        default=None, description="要读取的值名称。如果为None，则读取默认值"
    )


class RegWriteInput(BaseModel):
    """reg_write 工具的输入参数"""
    root_key: Literal["HKEY_CLASSES_ROOT", "HKEY_CURRENT_USER", "HKEY_LOCAL_MACHINE", "HKEY_USERS", "HKEY_CURRENT_CONFIG"] = Field(
        description="注册表根键。可选值：HKEY_CLASSES_ROOT、HKEY_CURRENT_USER、HKEY_LOCAL_MACHINE、HKEY_USERS、HKEY_CURRENT_CONFIG"
    )
    sub_key: str = Field(
        description="子键路径。例如：Software\\MyApp"
    )
    value_name: Optional[str] = Field(
        default=None, description="要写入的值名称。如果为None，则写入默认值"
    )
    value_data: str = Field(
        description="要写入的数据值"
    )
    value_type: Literal["REG_SZ", "REG_DWORD", "REG_QWORD", "REG_EXPAND_SZ", "REG_MULTI_SZ", "REG_BINARY"] = Field(
        default="REG_SZ", description="值类型。可选值：REG_SZ（字符串，默认）、REG_DWORD（32位整数）、REG_QWORD（64位整数）、REG_EXPAND_SZ（可扩展字符串）、REG_MULTI_SZ（多字符串）、REG_BINARY（二进制）"
    )


class RegDeleteInput(BaseModel):
    """reg_delete 工具的输入参数"""
    root_key: Literal["HKEY_CLASSES_ROOT", "HKEY_CURRENT_USER", "HKEY_LOCAL_MACHINE", "HKEY_USERS", "HKEY_CURRENT_CONFIG"] = Field(
        description="注册表根键。可选值：HKEY_CLASSES_ROOT、HKEY_CURRENT_USER、HKEY_LOCAL_MACHINE、HKEY_USERS、HKEY_CURRENT_CONFIG"
    )
    sub_key: str = Field(
        description="子键路径。例如：Software\\MyApp"
    )
    value_name: Optional[str] = Field(
        default=None, description="要删除的值名称。如果为None，则删除整个子键（需谨慎）"
    )


__all__ = [
    "RegReadInput",
    "RegWriteInput",
    "RegDeleteInput",
]
