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
        default="process", description="作用域。可选值：process（仅当前进程）、user（当前用户持久化）、system（全局持久化，需管理员权限）。Agent根据query语义自动映射。默认为process"
    )
    expand_vars: bool = Field(
        default=True, description="是否展开值中的嵌套变量（如 %JAVA_HOME%\\bin 或 $HOME/.local）。默认 true（返回绝对路径）。展开失败时保留原始字符串"
    )


class SetEnvInput(BaseModel):
    """set_env 工具的输入参数 - 小沈 2026-05-03 增加append_mode参数
    【2026-05-17 小沈】P1-5: 增加action参数合并delete_env，增加exist_ok幂等参数
    """
    name: str = Field(
        ..., description="环境变量名称。如 \"MY_VARIABLE\"、\"CONFIG_PATH\"、\"PATH\" 等"
    )
    value: Optional[str] = Field(
        default=None, description="环境变量值。action=\"set\"时必填，action=\"delete\"时忽略。任意字符串值"
    )
    scope: Literal["user", "system", "process"] = Field(
        default="process", description="作用域。可选值：process（仅当前进程）、user（持久化到当前用户）、system（持久化到全局，需管理员权限）。Agent根据语义自动映射。默认为process"
    )
    append_mode: bool = Field(
        default=False, description="追加模式。若 name 为 PATH 或 CLASSPATH，Agent 自动设true。根据OS自动选择分隔符。默认为False"
    )
    action: Literal["set", "delete"] = Field(
        default="set", description="操作类型。\"set\"=设置变量（默认），\"delete\"=删除变量（原delete_env）。Agent根据语义自动映射"
    )
    exist_ok: bool = Field(
        default=True, description="幂等模式。True时若变量已存在且值相同则直接返回成功，False时始终覆盖。默认True"
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