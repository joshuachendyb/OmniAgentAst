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
    """execute_shell_command安全检查和翻译机制 - 小欧-2026-06-27
    
    【PowerShell翻译】&&和||自动翻译（兼容PS 5.1）：
    - cmd1 && cmd2 → cmd1; if ($?) { cmd2 }
    - cmd1 || cmd2 → cmd1; if (-not $?) { cmd2 }
    - PS 7+原生支持，PS 5.1需要翻译
    
    【安全检查】分级安全检查：
    - HIGH风险（拒绝）: Remove-Item递归删除、format格式化、del /s递归删除
    - MEDIUM风险（警告）: 其他危险命令
    
    【返回值结构】
    - stdout: 标准输出内容
    - stderr: 标准错误内容
    - returncode: 退出码（0=成功）
    - shell_type: 实际使用的shell类型
    """
    command: str = Field(
        ..., description="PowerShell命令字符串。多个命令用;分隔。注意：PS 5.1中&&和||会自动翻译。示例: Get-ChildItem"
    )
    shell_type: Optional[Literal["powershell", "cmd"]] = Field(
        default="powershell",
        description="powershell(默认)或cmd"
    )
    timeout: int = Field(
        default=60, ge=1, le=600, description="超时时间(秒),默认60(60秒)。最小1秒,最大600(10分钟)"
    )
    run_in_background: bool = Field(
        default=False,
        description="是否在后台运行命令"
    )
    cwd: Optional[str] = Field(
        default=None, description="命令执行的工作目录(绝对路径)。需要在特定目录下执行命令时设置,如 D:/project。不设置则使用当前目录"
    )


class FindCommandInput(BaseModel):
    command: str = Field(
        ..., description="要查找的命令名称。示例: python"
    )
    all_paths: bool = Field(
        default=False,
        description="查找模式。False=返回第一个匹配路径(快速,shutil.which), True=返回全部匹配路径(完整列表,where/which -a)"
    )


class ShellSessionInput(BaseModel):
    """后台Shell会话管理工具
    
    【action参数】决定操作类型：
    - output: 读取后台命令输出
    - terminate: 终止后台会话（强制终止）
    
    【使用示例】
    - 读取输出 → shell_session(shell_id="shell_abc123")
    - 终止会话 → shell_session(shell_id="shell_abc123", action="terminate")
    """
    shell_id: str = Field(
        ..., description="后台Shell会话ID,由 execute_shell_command(run_in_background=True) 返回"
    )
    action: Literal["output", "terminate"] = Field(
        default="output",
        description="操作类型:output=读取输出(默认),terminate=强制终止会话"
    )



class ExecuteCodeInput(BaseModel):
    """execute_code安全检查机制说明 - 小欧-2026-06-27
    
    【安全检查】分级安全检查（三层防御）：
    - HIGH风险（拒绝执行）: eval/exec/compile/pickle/ctypes/getattr绕过
    - MEDIUM风险（警告）: os.system/subprocess/open写入/importlib
    - LOW风险（允许）: 基本计算、打印等安全操作
    
    【strict_mode】配置项：
    - strict_mode=False（默认）: MEDIUM风险允许执行，仅警告
    - strict_mode=True: MEDIUM风险也拒绝执行
    
    【返回值结构】
    - stdout: 标准输出内容
    - stderr: 标准错误内容
    - returncode: 退出码（0=成功）
    - working_dir: 实际工作目录
    """
    code: str = Field(
        ..., description="要执行的代码(字符串),必填参数。注意：eval/exec/compile等高风险函数会被安全检查拦截"
    )
    language: Literal["python", "javascript"] = Field(
        default="python", description="语言类型: python 或 javascript,默认python"
    )
    timeout: int = Field(
        default=30, ge=1, le=300, description="超时时间(秒),默认30(30秒),最大300(5分钟)"
    )
    working_dir: Optional[str] = Field(
        default=None, description="工作目录(绝对路径,可选)。默认为当前工作目录。目录不存在时自动创建"
    )




__all__ = [
    "ExecuteShellCommandInput",

    "FindCommandInput",
    "ShellSessionInput",
    "ExecuteCodeInput",
]
