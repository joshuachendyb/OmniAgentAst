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
    """execute_shell_command 工具的输入参数 - 小沈 2026-05-04 encoding已正确实现"""
    command: str = Field(
        ..., description="要执行的命令。如 \"dir\"、\"ls -la\"、\"python script.py\" 等"
    )
    shell_type: Optional[Literal["powershell", "cmd"]] = Field(
        default="powershell",
        description="执行环境。可选值：powershell、cmd。由 Agent 根据命令特征智能判断：默认 powershell，若执行报错且疑似语法错误（如包含 %VAR%），Agent 自动切换 cmd 重试"
    )
    timeout: int = Field(
        default=30000, ge=1000, le=600000, description="超时毫秒数，默认30000（30秒），最大600000（10分钟）。Agent 根据命令类型智能调整：简单命令 30s，编译/安装 300s - 小健 2026-05-18"
    )
    run_in_background: bool = Field(
        default=False,
        description="是否在后台运行命令。长期运行的服务(如npm run dev)Agent自动设为true。默认为False"
    )
    cwd: Optional[str] = Field(
        default=None, description="工作目录。由 Agent 根据上下文智能设置当前项目目录"
    )
    encoding: Optional[Literal["utf-8", "gbk", "gb2312", "latin-1"]] = Field(
        default=None, description="命令输出编码。可选值：utf-8、gbk、gb2312、latin-1。自动尝试回退到gbk。默认为utf-8"
    )
    env_vars: Optional[dict] = Field(
        default=None, description="环境变量对象。由 Agent 根据命令类型自动注入必要环境变量（如 PYTHONIOENCODING=utf-8）"
    )
    run_as_admin: bool = Field(
        default=False, description="是否请求管理员权限。当前版本标记意图，实际执行受限于当前进程权限。Agent对安装软件等高权限操作自动设为True。默认为False"
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
    "ShellSessionInput",
]
