# -*- coding: utf-8 -*-
"""
REGISTRY 工具参数 Schema 定义

【创建时间】2026-05-02 小沈
【更新时间】2026-05-03 小沈
【设计依据】按2026-04-29新增工具规范流程，按文档7.2节参数定义

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
    """reg_read 工具的输入参数
    
    按文档7.2节参数定义：
    - key_path: 注册表键路径
    - value_name: 值名称（可选）
    - hive: 根键（可选），默认HKCU
    - output_format: 输出格式（可选），默认auto
    """
    key_path: str = Field(
        description="注册表键路径。如 Software\\Microsoft\\Windows\\CurrentVersion。若含根键前缀则自动忽略 hive 参数"
    )
    value_name: Optional[str] = Field(
        default=None, description="值名称（可选）。不填则返回键的默认值。Agent 可自动列出该键下所有值"
    )
    hive: Literal["HKCU", "HKLM", "HKCR", "HKU", "HKCC"] = Field(
        default="HKCU", description="注册表根键。可选值：HKCU、HKLM、HKCR、HKU、HKCC。若 key_path 已含前缀则忽略此参数。默认为HKCU"
    )
    output_format: Literal["auto", "raw", "hex"] = Field(
        default="auto", description="输出格式。可选值：auto（按类型自动格式化）、raw（原始类型标识）、hex（强制 Hex 字符串）。默认为auto"
    )


class RegWriteInput(BaseModel):
    """reg_write 工具的输入参数
    
    按文档7.2节参数定义：
    - key_path: 注册表键路径
    - value_name: 值名称
    - value: 值数据
    - value_type: 值类型（可选），默认auto_detect
    - backup_before_write: 写入前备份（可选），默认true
    - dry_run: 预演模式（可选），默认false
    """
    key_path: str = Field(
        description="注册表键路径。Agent 自动标准化路径格式，消除前缀冲突"
    )
    value_name: str = Field(
        description="值名称。如 InstallPath"
    )
    value: str = Field(
        description="值数据。要写入的注册表值"
    )
    value_type: Literal["auto_detect", "REG_SZ", "REG_DWORD", "REG_BINARY", "REG_MULTI_SZ"] = Field(
        default="auto_detect", description="值类型。可选值：auto_detect（默认，保守推断）、REG_SZ、REG_DWORD、REG_BINARY、REG_MULTI_SZ。优先匹配已存在类型，新键默认 REG_SZ"
    )
    backup_before_write: bool = Field(
        default=True, description="写入前是否备份。默认 true。同一 Key 会话首次修改前备份至临时目录，后续复用快照"
    )
    dry_run: bool = Field(
        default=False, description="预演模式。默认 false。若涉及系统关键路径，Agent 强制开启仅校验，阻断实际写入"
    )
    hive: Literal["HKCU", "HKLM", "HKCR", "HKU", "HKCC"] = Field(
        default="HKCU", description="注册表根键。可选值：HKCU（默认）、HKLM、HKCR、HKU、HKCC。若 key_path 已含前缀则忽略此参数 - 小健 2026-05-06"
    )


class RegDeleteInput(BaseModel):
    """reg_delete 工具的输入参数
    
    按文档7.2节参数定义：
    - key_path: 注册表键路径
    - value_name: 值名称（可选）
    - backup_before_delete: 删除前备份（可选），默认true
    - recursive: 递归删除（可选），默认false
    - hive: 根键（可选），默认HKCU - 小健 2026-05-06
    """
    key_path: str = Field(
        description="注册表键路径。Agent 自动标准化路径"
    )
    value_name: Optional[str] = Field(
        default=None, description="值名称（可选）。不填则删除整个键。Agent 根据意图判断仅删 Value 或整个 Key"
    )
    backup_before_delete: bool = Field(
        default=True, description="删除前是否备份。默认 true。删除前自动备份，会话级复用"
    )
    recursive: bool = Field(
        default=False, description="是否递归删除子键。默认 false。仅允许删 Value 或空 Key。递归删 Key 需双重校验（白名单 + 数量确认）"
    )
    hive: Literal["HKCU", "HKLM", "HKCR", "HKU", "HKCC"] = Field(
        default="HKCU", description="注册表根键。可选值：HKCU（默认）、HKLM、HKCR、HKU、HKCC。若 key_path 已含前缀则忽略此参数 - 小健 2026-05-06"
    )


__all__ = [
    "RegReadInput",
    "RegWriteInput",
    "RegDeleteInput",
]
