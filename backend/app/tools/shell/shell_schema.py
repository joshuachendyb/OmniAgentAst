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

class ShellInput(BaseModel):
    """shell安全检查和翻译机制 - 小欧-2026-06-27
    
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
    cwd: Optional[str] = Field(
        default=None, description="命令执行的工作目录(绝对路径)。需要在特定目录下执行命令时设置,如 D:/project。不设置则使用当前目录"
    )


class WhichInput(BaseModel):
    command: str = Field(
        ..., description="要查找的命令名称。示例: python"
    )
    all_paths: bool = Field(
        default=False,
        description="查找模式。False=返回第一个匹配路径(快速,shutil.which), True=返回全部匹配路径(完整列表,where/which -a)"
    )

    


__all__ = [
    "ShellInput",
    "WhichInput",
]
