# -*- coding: utf-8 -*-
"""
Code Execution Register - 代码执行工具注册点

【架构规范】2026-05-02 小沈
- code_execution_tools.py: 实现工具函数
- code_execution_register.py: 注册点（导入触发注册）

创建时间: 2026-05-02
更新时间: 2026-05-02
"""

from app.services.tools.code_execution import code_execution_tools

__all__ = [
    "execute_python",
    "execute_javascript",
]
