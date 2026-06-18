# -*- coding: utf-8 -*-
"""
Shell 工具参数 Schema 定义

职责:
定义 shell 工具的 Pydantic 模型。

Author: 小沈 - 2026-04-29
"""

from pydantic import BaseModel, Field
from typing import Literal, Optional


class ExecuteShellCommandInput(BaseModel):
    command: str = Field(
        ..., description="要执行的命令。如 \"dir\"、\"ls -la\"、\"python script.py\" 等"
    )
    shell_type: Optional[Literal["powershell", "cmd"]] = Field(
        default="powershell",
        description="执行环境:powershell(默认)或cmd。Windows系统推荐powershell"
    )
    timeout: int = Field(
        default=30000, ge=1, le=600000, description="超时毫秒数,默认30000(30秒)。最小1毫秒,最大600000(10分钟)"
    )
    run_in_background: bool = Field(
        default=False,
        description="是否在后台运行命令。长期服务(如npm run dev)Agent自动设为true"
    )
    cwd: Optional[str] = Field(
        default=None, description="工作目录。Agent根据上下文智能设置"
    )
    env_vars: Optional[dict] = Field(
        default=None, description="额外环境变量字典,将与系统环境变量合并。如 {\"PYTHONIOENCODING\": \"utf-8\", \"NODE_ENV\": \"production\"}"
    )


class ExecuteShellCommandForegroundInput(BaseModel):
    command: str = Field(
        ..., description="要执行的命令。如 \"dir\"、\"python script.py\" 等"
    )
    shell_type: Optional[Literal["powershell", "cmd"]] = Field(
        default="powershell",
        description="执行环境:powershell(默认)或cmd。Windows系统推荐powershell"
    )
    timeout: int = Field(
        default=30000, ge=1, le=600000, description="超时毫秒数,默认30000(30秒)。最小1毫秒,最大600000(10分钟)"
    )
    cwd: Optional[str] = Field(
        default=None, description="工作目录。Agent根据上下文智能设置"
    )
    env_vars: Optional[dict] = Field(
        default=None, description="额外环境变量字典。如 {\"PYTHONIOENCODING\": \"utf-8\"}"
    )


class ExecuteShellCommandBackgroundInput(BaseModel):
    command: str = Field(
        ..., description="要在后台运行的命令。如 \"npm run dev\"、\"python server.py\" 等长期运行命令"
    )
    shell_type: Optional[Literal["powershell", "cmd"]] = Field(
        default="powershell",
        description="执行环境:powershell(默认)或cmd。Windows系统推荐powershell"
    )
    cwd: Optional[str] = Field(
        default=None, description="工作目录。Agent根据上下文智能设置"
    )
    env_vars: Optional[dict] = Field(
        default=None, description="额外环境变量字典。如 {\"PYTHONIOENCODING\": \"utf-8\"}"
    )


class FindCommandInput(BaseModel):
    command: str = Field(
        ..., description="要查找的命令名称,如 python、git、npm、node"
    )
    all_paths: bool = Field(
        default=False,
        description="查找模式。False=返回第一个匹配路径(快速,shutil.which), True=返回全部匹配路径(完整列表,where/which -a)"
    )


class ShellSessionInput(BaseModel):
    shell_id: str = Field(
        ..., description="后台Shell会话ID,由 execute_shell_command_background 返回"
    )
    action: Literal["output", "terminate"] = Field(
        default="output",
        description="操作类型:output=读取输出(默认),terminate=终止会话"
    )
    filter: Optional[str] = Field(
        default=None, description="输出过滤正则表达式(仅action=output时使用)。如 ERROR|FAIL"
    )
    max_lines: int = Field(
        default=1000, ge=1, le=10000, description="最大返回行数(仅action=output时使用)。默认1000,返回尾部最新输出"
    )
    force: bool = Field(
        default=False, description="强制终止(仅action=terminate时使用)。优雅终止失败时Agent自动设true"
    )


__all__ = [
    "ExecuteShellCommandInput",
    "ExecuteShellCommandForegroundInput",
    "ExecuteShellCommandBackgroundInput",
    "FindCommandInput",
    "ShellSessionInput",
]
