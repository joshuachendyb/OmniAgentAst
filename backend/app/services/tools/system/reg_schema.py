# -*- coding: utf-8 -*-
"""
REGISTRY 工具参数 Schema 定义

【创建时间】2026-05-02 小沈
【2026-05-19 小沈】删除旧RegReadInput/RegWriteInput/RegDeleteInput(已合入RegistryControlInput)

职责：
定义 registry 工具的 Pydantic 模型。

工具列表（1个LLM工具）：
1. registry_control - 注册表统一控制入口（action="read"|"write"|"delete"）

Author: 小沈 - 2026-05-02
"""

from pydantic import BaseModel, Field
from typing import Optional, Literal


class RegistryControlInput(BaseModel):
    """registry_control 工具的输入参数 - 小沈 2026-05-18
    合并 reg_read + reg_write + reg_delete，通过action路由
    """
    action: Literal["read", "write", "delete"] = Field(
        default="read", description="操作类型。\"read\"=读取（默认），\"write\"=写入，\"delete\"=删除。Agent根据意图自动映射"
    )
    key_path: str = Field(
        description="注册表键路径。如 Software\\Microsoft\\Windows\\CurrentVersion。若含根键前缀则自动忽略 hive 参数"
    )
    value_name: Optional[str] = Field(
        default=None, description="值名称。action=\"write\"时必填；action=\"read\"/\"delete\"时可选（不填则读取/删除默认值或整个键）"
    )
    value: Optional[str] = Field(
        default=None, description="值数据。仅action=\"write\"时使用"
    )
    value_type: Literal["auto_detect", "REG_SZ", "REG_DWORD", "REG_BINARY", "REG_MULTI_SZ"] = Field(
        default="auto_detect", description="值类型。仅action=\"write\"时使用。默认auto_detect"
    )
    hive: Literal["HKCU", "HKLM", "HKCR", "HKU", "HKCC"] = Field(
        default="HKCU", description="注册表根键。默认HKCU"
    )
    output_format: Literal["auto", "raw", "hex"] = Field(
        default="auto", description="输出格式。仅action=\"read\"时使用。默认auto"
    )
    backup_before_write: bool = Field(
        default=True, description="写入前备份。仅action=\"write\"时使用。默认True"
    )
    backup_before_delete: bool = Field(
        default=True, description="删除前备份。仅action=\"delete\"时使用。默认True"
    )
    dry_run: bool = Field(
        default=False, description="预演模式。仅action=\"write\"时使用。默认False"
    )
    recursive: bool = Field(
        default=False, description="递归删除子键。仅action=\"delete\"时使用。默认False"
    )


__all__ = [
    "RegistryControlInput",
]
