# -*- coding: utf-8 -*-
"""
SYSTEM 模块 - 系统信息工具

【架构规范】2026-04-29 小沈

目录结构：
    system/
    ├── __init__.py           # 导入触发注册
    ├── system_register.py    # 工具注册点
    ├── system_tools.py       # 具体实现
    └── system_schema.py     # Pydantic 模型

创建时间: 2026-04-29
"""

from app.services.tools.system import system_register
from app.services.tools.system import system_tools

from app.services.tools.system.system_tools import (
    get_system_info,
)

__all__ = [
    "get_system_info",
]
