# -*- coding: utf-8 -*-
"""
Shell 工具参数 Schema 定义

【创建时间】2026-04-29 小沈
【设计依据】按2026-04-29新增工具规范流程

职责：
定义 shell 工具的 Pydantic 模型。

Author: 小沈 - 2026-04-29
"""

from pydantic import BaseModel, Field
from typing import Optional


class ExecuteCommandInput(BaseModel):
    """execute_command 工具的输入参数"""
    command: str = Field(
        ..., description="要执行的Shell命令（字符串），必填参数"
    )
    cwd: Optional[str] = Field(
        default=None, description="工作目录（可选）。如果为None则使用当前工作目录"
    )
    timeout: int = Field(
        default=60, ge=1, le=600, description="超时时间（秒），默认为60秒，最大600秒 - 小沈 2026-05-01"
    )


class ListDirectoryInput(BaseModel):
    """list_directory 工具的输入参数"""
    path: str = Field(
        default=".", description="目录路径，默认为当前目录"
    )


class GetWorkingDirectoryInput(BaseModel):
    """get_working_directory 工具的输入参数（无参数）"""
    pass


class ChangeDirectoryInput(BaseModel):
    """change_directory 工具的输入参数"""
    path: str = Field(
        ..., description="要切换到的目录路径。必填参数"
    )


class CheckPathExistsInput(BaseModel):
    """check_path_exists 工具的输入参数"""
    path: str = Field(
        ..., description="要检查的文件或目录路径。必填参数"
    )


class GetShellOutputInput(BaseModel):
    """get_shell_output 工具的输入参数"""
    shell_id: str = Field(
        ..., description="后台 shell 的 ID，由 execute_shell_command 的 run_in_background=true 时返回"
    )
    filter: Optional[str] = Field(
        default=None, description="过滤输出的正则表达式（可选）。Agent 根据用户意图智能设置，如 'ERROR|FAIL'"
    )
    encoding: Optional[str] = Field(
        default=None, description="输出编码。Agent 自动检测，默认 utf-8。若乱码自动尝试 gbk、gb2312"
    )
    max_lines: int = Field(
        default=1000, ge=1, le=10000, description="最大返回行数。默认 1000 行。若输出超长，Agent 自动截取最后 N 行并提示截断"
    )
    tail: bool = Field(
        default=False, description="是否只返回最后 N 行输出。由 Agent 根据用户意图智能判断"
    )


class TerminateShellInput(BaseModel):
    """terminate_shell 工具的输入参数"""
    shell_id: str = Field(
        ..., description="要终止的 shell ID。通过 execute_shell_command 的 run_in_background=true 执行命令后获得"
    )
    force: bool = Field(
        default=False, description="是否强制终止。Agent 智能判断：优雅终止，若进程无响应则自动重试并设 true 强制杀死"
    )
    cleanup: bool = Field(
        default=True, description="终止后是否清理临时文件和子进程。Agent 智能判断"
    )


__all__ = [
    "ExecuteCommandInput",
    "ListDirectoryInput",
    "GetWorkingDirectoryInput",
    "ChangeDirectoryInput",
    "CheckPathExistsInput",
    "GetShellOutputInput",
    "TerminateShellInput",
]
