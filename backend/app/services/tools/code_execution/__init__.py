# -*- coding: utf-8 -*-
"""
Code Execution 模块 - 代码执行工具

【架构规范】2026-05-02 小沈
- code_execution_register.py: 工具注册点（导入触发注册）
- code_execution_tools.py: 具体实现
- code_execution_schema.py: Pydantic 模型

目录结构：
    code_execution/
    ├── __init__.py                # 本文件，导入 code_execution_register 触发注册
    ├── code_execution_register.py # 工具注册点
    ├── code_execution_tools.py    # 具体实现
    └── code_execution_schema.py   # Pydantic 模型

创建时间: 2026-05-02
"""

from app.services.tools.code_execution import code_execution_register
from app.services.tools.code_execution import code_execution_tools

from app.services.tools.code_execution.code_execution_tools import (
    execute_python,
    execute_javascript,
)

__all__ = [
    "execute_python",
    "execute_javascript",
]
