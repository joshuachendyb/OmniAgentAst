# -*- coding: utf-8 -*-
"""
REGISTRY 工具参数 Schema 定义

【创建时间】2026-05-02 小沈
【2026-05-19 小沈】删除旧RegReadInput/RegWriteInput/RegDeleteInput(已合入RegistryControlInput)
【2026-05-19 小沈】参数精简：11→7，砍output_format/backup_before_write/backup_before_delete/dry_run

职责：
定义 registry 工具的 Pydantic 模型。

工具列表（1个LLM工具）：
1. registry_control - 注册表统一控制入口（action="read"|"write"|"delete"）

Author: 小沈 - 2026-05-02
"""

from pydantic import BaseModel, Field
from typing import Optional, Literal


class RegistryControlInput(BaseModel):
    """registry_control 工具的输入参数 - 小沈 2026-05-19 参数精简11→7
    合并 reg_read + reg_write + reg_delete，通过action路由
    【2026-05-19 小沈】砍掉4参数：output_format(默认auto够用)、backup_before_write/delete(默认True安全)、dry_run(低频)
    """
    key_path: str = Field(
        ..., description="注册表键路径。如 Software\\Microsoft\\Windows\\CurrentVersion。若含根键前缀则自动忽略 hive 参数"
    )
    action: Literal["read", "write", "delete"] = Field(
        ..., description="操作类型：read=读取，write=写入，delete=删除【FIX 2026-05-20 小健】函数签名要求必填，对齐为必填"
    )
    value_name: Optional[str] = Field(
        default=None, description="值名称。action=\"write\"时必填；action=\"read\"/\"delete\"时可选（不填则读取/删除默认值或整个键）"
    )
    value: Optional[str] = Field(
        default=None, description="值数据。仅action=\"write\"时使用"
    )
    value_type: Literal["auto_detect", "REG_SZ", "REG_EXPAND_SZ", "REG_DWORD", "REG_QWORD", "REG_BINARY", "REG_MULTI_SZ"] = Field(
        default="auto_detect", description="值类型。仅action=\"write\"时使用。默认auto_detect。REG_EXPAND_SZ=可扩展字符串(含%VAR%)，REG_QWORD=64位整数"
    )
    hive: Literal["HKCU", "HKLM", "HKCR", "HKU", "HKCC"] = Field(
        default="HKCU", description="注册表根键。默认HKCU"
    )
    recursive: bool = Field(
        default=False, description="递归删除子键。仅action=\"delete\"时使用。默认False"
    )


__all__ = [
    "RegistryControlInput",
]
