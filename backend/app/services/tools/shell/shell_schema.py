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


class ExecuteShellCommandInput(BaseModel):
    """execute_shell_command 工具的输入参数 - 小沈 2026-05-03 补齐文档参数+timeout改毫秒"""
    command: str = Field(
        ..., description="要执行的命令。如 \"dir\"、\"ls -la\"、\"python script.py\" 等"
    )
    shell_type: Optional[str] = Field(
        default="powershell",
        description="执行环境。可选值：powershell、cmd。由 Agent 根据命令特征智能判断：默认 powershell，若执行报错且疑似语法错误（如包含 %VAR%），Agent 自动切换 cmd 重试"
    )
    timeout: int = Field(
        default=300000, ge=1000, le=600000, description="超时毫秒数，默认300000（5分钟），最大600000（10分钟）。由 Agent 根据命令类型智能调整 - 小沈 2026-05-03"
    )
    run_in_background: bool = Field(
        default=False,
        description="是否在后台运行命令。由 Agent 根据命令特征智能判断：长期运行的服务(如npm run dev)自动设true"
    )
    cwd: Optional[str] = Field(
        default=None, description="工作目录。由 Agent 根据上下文智能设置当前项目目录"
    )
    encoding: Optional[str] = Field(
        default=None, description="命令输出编码。None=自动检测(默认utf-8)，若乱码自动尝试gbk、gb2312"
    )
    env_vars: Optional[dict] = Field(
        default=None, description="环境变量对象。由 Agent 根据命令类型自动注入必要环境变量（如 PYTHONIOENCODING=utf-8）"
    )
    run_as_admin: bool = Field(
        default=False, description="是否以管理员权限运行。由 Agent 智能判断是否需要提权（如安装软件、修改注册表时设true）"
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
    "ExecuteShellCommandInput",
    "ListDirectoryInput",
    "GetWorkingDirectoryInput",
    "ChangeDirectoryInput",
    "CheckPathExistsInput",
    "GetShellOutputInput",
    "TerminateShellInput",
]
