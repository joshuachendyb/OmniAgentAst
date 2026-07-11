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

from pydantic import BaseModel, Field, model_validator
from typing import Optional, Literal, Union


class RegistryReadInput(BaseModel):
    r"""path含根键前缀(如HKCU\...)时hive参数无效,严禁同时指定"""
    path: str = Field(
        ..., description="注册表键路径(必填)。两种写法:1.含根键前缀如HKCU\\Software\\MyApp(此时hive参数无效) 2.不含根键如Software\\MyApp(此时通过hive指定根键)。严禁path含根键前缀的同时指定非默认hive"
    )
    value_name: Optional[str] = Field(
        default=None, description="值名称(可选)。不填则读取默认值"
    )
    hive: Literal["HKCU", "HKLM", "HKCR", "HKU", "HKCC"] = Field(
        default="HKCU", description="注册表根键(仅path不含根键前缀时生效)。默认HKCU"
    )
    output_format: Literal["auto", "hex"] = Field(
        default="auto", description="输出格式。auto=自动格式(默认),hex=二进制值转换为十六进制字符串"
    )

    @model_validator(mode="after")
    def _check_path_hive(self):
        _ROOT_PREFIXES = ("HKCU\\", "HKLM\\", "HKCR\\", "HKU\\", "HKCC\\",
                          "HKEY_CURRENT_USER\\", "HKEY_LOCAL_MACHINE\\", "HKEY_CLASSES_ROOT\\", "HKEY_USERS\\", "HKEY_CURRENT_CONFIG\\")
        has_root_prefix = self.path.upper().startswith(_ROOT_PREFIXES)
        if has_root_prefix and self.hive != "HKCU":
            raise ValueError("path含根键前缀时hive参数无效,请去掉path中的根键前缀或使用默认hive")
        return self


class RegistryWriteInput(BaseModel):
    r"""path含根键前缀(如HKCU\...)时hive参数无效,严禁同时指定"""
    path: str = Field(
        ..., description="注册表键路径(必填)。两种写法:1.含根键前缀如HKCU\\Software\\MyApp(此时hive参数无效) 2.不含根键如Software\\MyApp(此时通过hive指定根键)。严禁path含根键前缀的同时指定非默认hive"
    )
    value_name: str = Field(
        ..., description="值名称(必填)。如 Version、InstallPath"
    )
    value: Union[str, int] = Field(
        ..., description="值数据(必填)。如 '1.0'、'C:\\Program Files\\MyApp'、20260711。数字会自动转为字符串后再按value_type处理"
    )
    value_type: Literal["auto_detect", "REG_SZ", "REG_EXPAND_SZ", "REG_DWORD", "REG_QWORD", "REG_BINARY", "REG_MULTI_SZ"] = Field(
        default="auto_detect", description="值类型(可选)。默认auto_detect。REG_EXPAND_SZ=可扩展字符串(含%VAR%),REG_QWORD=64位整数"
    )
    hive: Literal["HKCU", "HKLM", "HKCR", "HKU", "HKCC"] = Field(
        default="HKCU", description="注册表根键(仅path不含根键前缀时生效)。默认HKCU"
    )

    @model_validator(mode="after")
    def _check_path_hive(self):
        _ROOT_PREFIXES = ("HKCU\\", "HKLM\\", "HKCR\\", "HKU\\", "HKCC\\",
                          "HKEY_CURRENT_USER\\", "HKEY_LOCAL_MACHINE\\", "HKEY_CLASSES_ROOT\\", "HKEY_USERS\\", "HKEY_CURRENT_CONFIG\\")
        has_root_prefix = self.path.upper().startswith(_ROOT_PREFIXES)
        if has_root_prefix and self.hive != "HKCU":
            raise ValueError("path含根键前缀时hive参数无效,请去掉path中的根键前缀或使用默认hive")
        return self


class RegistryDeleteInput(BaseModel):
    r"""path含根键前缀(如HKCU\...)时hive参数无效,严禁同时指定"""
    path: str = Field(
        ..., description="注册表键路径(必填)。两种写法:1.含根键前缀如HKCU\\Software\\MyApp(此时hive参数无效) 2.不含根键如Software\\MyApp(此时通过hive指定根键)。严禁path含根键前缀的同时指定非默认hive"
    )
    value_name: Optional[str] = Field(
        default=None, description="值名称(可选)。不填则删除整个键"
    )
    hive: Literal["HKCU", "HKLM", "HKCR", "HKU", "HKCC"] = Field(
        default="HKCU", description="注册表根键(仅path不含根键前缀时生效)。默认HKCU"
    )
    recursive: bool = Field(
        default=False, description="递归删除子键(可选)。默认False。键不为空时需设为True才能删除"
    )

    @model_validator(mode="after")
    def _check_path_hive(self):
        _ROOT_PREFIXES = ("HKCU\\", "HKLM\\", "HKCR\\", "HKU\\", "HKCC\\",
                          "HKEY_CURRENT_USER\\", "HKEY_LOCAL_MACHINE\\", "HKEY_CLASSES_ROOT\\", "HKEY_USERS\\", "HKEY_CURRENT_CONFIG\\")
        has_root_prefix = self.path.upper().startswith(_ROOT_PREFIXES)
        if has_root_prefix and self.hive != "HKCU":
            raise ValueError("path含根键前缀时hive参数无效,请去掉path中的根键前缀或使用默认hive")
        return self


__all__ = [
    "RegistryReadInput",
    "RegistryWriteInput",
    "RegistryDeleteInput",
]
