# -*- coding: utf-8 -*-
"""
ENV 工具参数 Schema 定义

【创建时间】2026-04-29 小沈
【设计依据】按2026-04-29新增工具规范流程

职责：
定义 env 工具的 Pydantic 模型。

工具列表（3个）：
1. get_env - 获取环境变量
2. set_env - 设置环境变量
3. list_env - 列出环境变量

Author: 小沈 - 2026-04-29
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, Literal


class GetEnvInput(BaseModel):
    """get_env 工具的输入参数"""
    name: str = Field(
        ..., description="环境变量名称（必填），例如 PATH、HOME、USER"
    )
    default: Optional[str] = Field(
        default=None, description="默认值（可选）。当环境变量不存在时返回此值"
    )


class SetEnvInput(BaseModel):
    """set_env 工具的输入参数"""
    name: str = Field(
        ..., description="环境变量名称（必填），例如 MY_VAR、APP_PATH"
    )
    value: str = Field(
        ..., description="环境变量值（必填），例如 /path/to/app、true、123"
    )
    scope: Literal["user", "system", "process"] = Field(
        default="process", description="环境变量作用域：user（当前用户）、system（系统级）、process（当前进程），默认为process"
    )


class ListEnvInput(BaseModel):
    """list_env 工具的输入参数"""
    prefix: Optional[str] = Field(
        default=None, description="环境变量名前缀过滤（可选），例如 PY、JAVA"
    )
    include_system: bool = Field(
        default=False, description="是否包含系统级环境变量，默认为False（仅用户级）"
    )


__all__ = [
    "GetEnvInput",
    "SetEnvInput",
    "ListEnvInput",
]