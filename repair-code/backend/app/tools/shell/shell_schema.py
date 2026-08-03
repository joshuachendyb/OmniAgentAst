# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-06-18 - 小欧 - Merged schema
# 2026-06-18 - 小健 - 删除两个包装器schema，违反YAGNI原则
# 2026-07-15 - 小欧 - 新增success_codes参数,支持追加式非零退出码视为成功,0始终成功
# 2026-07-18 - 小沈 - command字段描述补本机python3不可用说明(微软商店别名未安装),引导LLM用python而非python3(见日志fc1102db)
# 2026-07-20 - 小欧 - 复核schema docstring规范,ShellInput保留既有docstring,WhichInput默认行为已在Field中体现,无需新增
# 2026-07-25 - 小欧 - description去冗余: shell_type/timeout移除默认/范围重复(2处)
# 2026-07-25 - 小欧 - description去冗余: command/cwd/WhichInput.command移除冗余示例(3处)
# 2026-07-27 - 小欧 - 去PS提醒: command描述去"PowerShell"前缀, shell_type description中性化"命令解释器类型", docstring拆PS/CMD语法注意事项+PS翻译→命令链支持
# 2026-07-28 - 小欧 - shell_type名称改为ps7/ps5/cmd/bash, 默认ps7; docstring补充bash语法注意事项, Field description更新
"""
Shell Schema - Shell工具参数模型(ps7/ps5/cmd/bash)

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

from pydantic import BaseModel, Field
from typing import Literal, Optional


class WhichInput(BaseModel):
    command: str = Field(
        ..., description="要查找的命令名称"
    )
    all_paths: bool = Field(
        default=False,
        description="查找模式。False=返回第一个匹配路径(快速,shutil.which), True=返回全部匹配路径(完整列表,where/which -a)"
    )


__all__ = [
    "WhichInput",
]
