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
    """get_env 工具的输入参数 - 小沈 2026-05-03 增加scope+expand_vars参数"""
    name: str = Field(
        ..., description="环境变量名称。如 \"PATH\"、\"HOME\"、\"USER\"、\"JAVA_HOME\" 等"
    )
    default: Optional[str] = Field(
        default=None, description="默认值（可选）。如果指定的环境变量不存在，则返回此默认值"
    )
    scope: Literal["process", "user", "system"] = Field(
        default="process", description="作用域。process（仅当前进程，默认）、user（当前用户持久化）、system（全局持久化，需管理员权限）。由 Agent 根据 query 语义自动映射"
    )
    expand_vars: bool = Field(
        default=True, description="是否展开值中的嵌套变量（如 %JAVA_HOME%\\bin 或 $HOME/.local）。默认 true（返回绝对路径）。展开失败时保留原始字符串"
    )


class SetEnvInput(BaseModel):
    """set_env 工具的输入参数 - 小沈 2026-05-03 增加append_mode参数"""
    name: str = Field(
        ..., description="环境变量名称。如 \"MY_VARIABLE\"、\"CONFIG_PATH\"、\"PATH\" 等"
    )
    value: str = Field(
        ..., description="环境变量值。任意字符串值"
    )
    scope: Literal["user", "system", "process"] = Field(
        default="process", description="作用域。可选值：process（仅当前进程，默认）、user（持久化到当前用户）、system（持久化到全局，需管理员权限）。Agent 根据语义自动映射，遇权限不足自动降级为 process 并提示用户"
    )
    append_mode: bool = Field(
        default=False, description="追加模式。默认 false（覆盖）。若 name 为 PATH 或 CLASSPATH，Agent 自动设 true，安全追加新路径且自动去除重复路径。根据 OS 自动选择分隔符（Win ; / Linux :）"
    )


class ListEnvInput(BaseModel):
    """list_env 工具的输入参数"""
    prefix: Optional[str] = Field(
        default=None, description="环境变量名前缀过滤（可选），例如 PY、JAVA"
    )
    include_system: bool = Field(
        default=False, description="是否包含系统级环境变量，默认为False（仅用户级）"
    )


class DeleteEnvInput(BaseModel):
    """delete_env 工具的输入参数"""
    name: str = Field(..., description="要删除的环境变量名称")
    scope: Literal["process", "user", "system"] = Field(default="process", description="作用域")


class ExistsEnvInput(BaseModel):
    """exists_env 工具的输入参数"""
    name: str = Field(..., description="要检查的环境变量名称")
    scope: Literal["process", "user", "system"] = Field(default="process", description="作用域")


__all__ = [
    "GetEnvInput",
    "SetEnvInput",
    "ListEnvInput",
    "DeleteEnvInput",
    "ExistsEnvInput",
]