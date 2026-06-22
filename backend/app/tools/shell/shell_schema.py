# -*- coding: utf-8 -*-
"""
Shell Schema - Shell工具参数模型

【Schema Docstring 规范】小健 2026-06-18
一般情况下，严禁给Schema类加docstring。
仅在以下情况可以添加：
1. 函数使用过于复杂，需要详细说明
2. 多action的tool，需要说明不同action的用法
3. 添加的是tool描述的增强信息，不是冗余信息

禁止：
- 重复register.py中的描述
- 添加过于冗长的说明
- 添加与参数无关的内容
"""
# Merged schema - 小欧 2026-06-18
# 【2026-06-18 小健】删除两个包装器schema，违反YAGNI原则

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
        default=None, description="命令执行的工作目录(绝对路径)。需要在特定目录下执行命令时设置,如 D:/project。不设置则使用当前目录"
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
    """后台Shell会话管理工具
    
    【action参数】决定操作类型：
    - output: 读取后台命令输出
    - terminate: 终止后台会话
    
    【使用示例】
    - 读取输出 → shell_session(shell_id="shell_abc123")
    - 终止会话 → shell_session(shell_id="shell_abc123", action="terminate")
    """
    shell_id: str = Field(
        ..., description="后台Shell会话ID,由 execute_shell_command(run_in_background=True) 返回"
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



class ExecuteCodeInput(BaseModel):
    code: str = Field(
        ..., description="要执行的代码(字符串),必填参数"
    )
    language: str = Field(
        default="python", description="语言类型: python 或 javascript,默认python"
    )
    timeout: int = Field(
        default=30, ge=1, le=300, description="超时时间(秒),默认为30秒,最大300秒"
    )
    working_dir: Optional[str] = Field(
        default=None, description="工作目录(可选)。默认为当前工作目录。目录不存在时自动创建"
    )




__all__ = [
    "ExecuteShellCommandInput",

    "FindCommandInput",
    "ShellSessionInput",
    "ExecuteCodeInput",
]
