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
from typing import Literal, Optional


class ExecuteShellCommandInput(BaseModel):
    """execute_shell_command 工具的输入参数 - 小沈 2026-05-04 encoding已正确实现"""
    command: str = Field(
        ..., description="要执行的命令。如 \"dir\"、\"ls -la\"、\"python script.py\" 等"
    )
    shell_type: Optional[str] = Field(
        default="powershell",
        description="执行环境。可选值：powershell、cmd。由 Agent 根据命令特征智能判断：默认 powershell，若执行报错且疑似语法错误（如包含 %VAR%），Agent 自动切换 cmd 重试"
    )
    timeout: int = Field(
        default=300000, ge=1000, le=600000, description="超时毫秒数，默认300000（5分钟），最大600000（10分钟）。Agent 根据命令类型智能调整：简单命令 30s，编译/安装 300s - 小沈 2026-05-03"
    )
    run_in_background: bool = Field(
        default=False,
        description="是否在后台运行命令。长期运行的服务(如npm run dev)Agent自动设为true。默认为False"
    )
    cwd: Optional[str] = Field(
        default=None, description="工作目录。由 Agent 根据上下文智能设置当前项目目录"
    )
    encoding: Optional[str] = Field(
        default=None, description="命令输出编码。可选值：utf-8、gbk、gb2312、latin-1。自动尝试回退到gbk。默认为utf-8"
    )
    env_vars: Optional[dict] = Field(
        default=None, description="环境变量对象。由 Agent 根据命令类型自动注入必要环境变量（如 PYTHONIOENCODING=utf-8）"
    )
    run_as_admin: bool = Field(
        default=False, description="是否请求管理员权限。当前版本标记意图，实际执行受限于当前进程权限。Agent对安装软件等高权限操作自动设为True。默认为False"
    )


class GetWorkingDirectoryInput(BaseModel):
    """get_working_directory 工具的输入参数（无参数）
    【2026-05-17 小健 已弃用】get_working_directory 已降级为 _get_working_directory 内部函数
    """
    pass


class ChangeDirectoryInput(BaseModel):
    """change_directory 工具的输入参数
    【2026-05-17 小健 已弃用】change_directory 已删除，请使用 execute_shell_command 的 cwd 参数替代
    """
    path: str = Field(
        ..., description="要切换到的目录路径。必填参数"
    )


class CheckPathExistsInput(BaseModel):
    """check_path_exists 工具的输入参数
    【2026-05-17 小健 已弃用】check_path_exists 已降级为 _check_path_exists 内部函数
    """
    path: str = Field(
        ..., description="要检查的文件或目录路径。必填参数"
    )


class CheckCommandAvailableInput(BaseModel):
    """check_command_available 工具的输入参数
    【2026-05-17 小沈 已弃用】请使用 FindCommandInput 代替
    """
    command: str = Field(
        ..., description="要检查的命令名称，如 python、git、npm"
    )


class LocateCommandInput(BaseModel):
    """locate_command 工具的输入参数
    【2026-05-17 小沈 已弃用】请使用 FindCommandInput 代替
    """
    command: str = Field(
        ..., description="要查找的命令名称，如 python、node"
    )


class FindCommandInput(BaseModel):
    """find_command 工具的输入参数 - 小沈 2026-05-17
    合并 check_command_available + locate_command
    """
    command: str = Field(
        ..., description="要查找的命令名称，如 python、git、npm、node"
    )
    all_paths: bool = Field(
        default=False,
        description="查找模式。False=返回第一个匹配路径(快速,shutil.which), True=返回全部匹配路径(完整列表,where/which -a)"
    )


class GetShellOutputInput(BaseModel):
    """get_shell_output 工具的输入参数
    【2026-05-17 小沈 已弃用】请使用 ShellSessionInput 代替
    """
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
        default=1000, ge=1, le=10000, description="最大返回行数。输出超长时Agent自动截取最后N行。默认为1000"
    )
    tail: bool = Field(
        default=False, description="是否只返回最后 N 行输出。由 Agent 根据用户意图智能判断"
    )


class TerminateShellInput(BaseModel):
    """terminate_shell 工具的输入参数
    【2026-05-17 小沈 已弃用】请使用 ShellSessionInput 代替
    """
    shell_id: str = Field(
        ..., description="要终止的 shell ID。通过 execute_shell_command 的 run_in_background=true 执行命令后获得"
    )
    force: bool = Field(
        default=False, description="是否强制终止。优雅终止失败时Agent自动设为true强制杀死。默认为False"
    )
    cleanup: bool = Field(
        default=True, description="终止后是否清理临时文件和子进程。默认为True"
    )


class ShellSessionInput(BaseModel):
    """shell_session 工具的输入参数 - 小沈 2026-05-17
    合并 get_shell_output + terminate_shell
    """
    shell_id: str = Field(
        ..., description="后台Shell会话ID，由 execute_shell_command 的 run_in_background=true 时返回"
    )
    action: Literal["output", "terminate"] = Field(
        default="output",
        description="操作类型。output=读取输出, terminate=终止会话"
    )
    filter: Optional[str] = Field(
        default=None, description="输出过滤正则表达式（action=output时生效）。如 'ERROR|FAIL'"
    )
    encoding: Optional[str] = Field(
        default=None, description="输出编码（action=output时生效）。默认utf-8，乱码自动尝试gbk"
    )
    max_lines: int = Field(
        default=1000, ge=1, le=10000, description="最大返回行数（action=output时生效）。默认1000"
    )
    tail: bool = Field(
        default=False, description="只返回最后N行（action=output时生效）"
    )
    force: bool = Field(
        default=False, description="强制终止（action=terminate时生效）。优雅终止失败时Agent自动设true"
    )
    cleanup: bool = Field(
        default=True, description="终止后清理资源（action=terminate时生效）。默认True"
    )


__all__ = [
    "ExecuteShellCommandInput",
    "FindCommandInput",
    "GetShellOutputInput",
    "TerminateShellInput",
    "ShellSessionInput",
]
