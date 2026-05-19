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


# 【2026-05-19 小沈】ExecutePythonInput/ExecuteJavascriptInput 已迁移至
# code_execution_schema.py，此处不再重复定义，避免Schema分歧。
# shell_register.py 显式从 code_execution_schema.py import 这两个类。


class ExecuteShellCommandInput(BaseModel):
    """execute_shell_command 工具的输入参数 — 小沈 2026-05-19 精简8→6"""
    command: str = Field(
        ..., description="要执行的命令。如 \"dir\"、\"ls -la\"、\"python script.py\" 等"
    )
    shell_type: Optional[Literal["powershell", "cmd"]] = Field(
        default="powershell",
        description="执行环境：powershell(默认)或cmd。Windows系统推荐powershell"
    )
    timeout: int = Field(
        default=30000, ge=1000, le=600000, description="超时毫秒数，默认30000(30秒)，最大600000(10分钟)"
    )
    run_in_background: bool = Field(
        default=False,
        description="是否在后台运行命令。长期服务(如npm run dev)Agent自动设为true"
    )
    cwd: Optional[str] = Field(
        default=None, description="工作目录。Agent根据上下文智能设置"
    )
    env_vars: Optional[dict] = Field(
        default=None, description="额外环境变量字典，将与系统环境变量合并。如 {\"PYTHONIOENCODING\": \"utf-8\", \"NODE_ENV\": \"production\"}"
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


class ShellSessionInput(BaseModel):
    """shell_session 工具的输入参数 — 小沈 2026-05-19 精简8→5
    action="output": 读取输出(filter/max_lines生效)
    action="terminate": 终止会话(force生效)
    """
    shell_id: str = Field(
        ..., description="后台Shell会话ID，由 execute_shell_command 的 run_in_background=true 时返回"
    )
    action: Literal["output", "terminate"] = Field(
        default="output",
        description="操作类型：output=读取输出，terminate=终止会话"
    )
    filter: Optional[str] = Field(
        default=None, description="输出过滤正则表达式（action=output时生效）。如 'ERROR|FAIL'"
    )
    max_lines: int = Field(
        default=1000, ge=1, le=10000, description="最大返回行数（action=output时生效）。默认1000，返回尾部最新输出"
    )
    force: bool = Field(
        default=False, description="强制终止（action=terminate时生效）。优雅终止失败时Agent自动设true"
    )


__all__ = [
    "ExecuteShellCommandInput",
    "FindCommandInput",
    "ShellSessionInput",
]
