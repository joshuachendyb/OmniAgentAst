# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-20 - 小欧 - 复核schema docstring规范,ShellInput保留既有docstring,WhichInput默认行为已在Field中体现,无需新增
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
# 小欧 - 2026-07-15: 新增success_codes参数,支持追加式非零退出码视为成功,0始终成功
# 小沈 - 2026-07-18: command字段描述补本机python3不可用说明(微软商店别名未安装),引导LLM用python而非python3

from pydantic import BaseModel, Field
from typing import Literal, Optional

class ShellInput(BaseModel):
    """Shell命令执行 - 语法翻译、安全检查、编码处理

    【语法注意事项】
    - PS 7+ 语法不支持: ?. ?? ??= 三元运算符 Get-ComputerInfo Join-String
    - 管道变量用 $_.Property 形式，注意下划线不要遗漏
    - findstr 查找无匹配时 exit code=1（正常行为，非错误）

    【PowerShell翻译】&&和||自动翻译：
    - cmd1 && cmd2 → cmd1; if ($?) { cmd2 }
    - cmd1 || cmd2 → cmd1; if (-not $?) { cmd2 }

    【安全检查】分级安全检查：
    - HIGH风险（拒绝）: Remove-Item递归删除、format格式化、del /s递归删除
    - MEDIUM风险（警告）: 其他危险命令

    【编码处理】引擎自动处理编码：
    - PowerShell > 输出自动转 UTF-8
    - Python 子进程自动继承 PYTHONIOENCODING=utf-8 + PYTHONUTF8=1
    - 中文命令/路径直接使用，无需额外编码设置

    【返回值结构】
    - stdout: 标准输出内容
    - stderr: 标准错误内容
    - returncode: 退出码（0=成功）
    - shell_type: 实际使用的shell类型
    """
    # 2026-07-18 小沈: command描述补python3不可用说明,引导LLM用python而非python3(见日志fc1102db)
    # 本机python3是微软商店别名(未安装),真解释器为E:\Appsw\python31311\python.exe,命令名python
    command: str = Field(
        ..., description="PowerShell命令字符串。多个命令用;分隔。注意：PS 5.1中&&和||会自动翻译。示例: Get-ChildItem。注意:本机Python解释器命令为python(如python --version),禁止使用python3"
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
    success_codes: Optional[list[int]] = Field(
        default=None,
        description="额外视为成功的退出码(0始终算成功,无需列出)。"
               "当命令用非零退出码表达业务结果(如校验工具返回1=有问题)时,"
               "在此追加如[1,2]防止被误判为执行失败。不传则只认0。"
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
