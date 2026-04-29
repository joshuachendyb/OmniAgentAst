# -*- coding: utf-8 -*-
"""
Shell Register - Shell工具注册点

【架构规范】2026-04-29 小沈
- shell_tools.py: 实现工具函数
- shell_register.py: 注册点（导入触发注册）

【2026-04-29 小沈重构】
- 删除旧版不存在的 register_category API
- 改为使用 @register_tool 装饰器 + Pydantic 模型
- 按新规范（registry.py + input_model）注册

创建时间: 2026-04-29
更新时间: 2026-04-29
"""

# 触发 shell_tools 导入（@register_tool 装饰器自动完成注册）
from app.services.tools.shell import shell_tools

__all__ = [
    "execute_command",
    "get_working_directory",
    "change_directory",
    "check_path_exists",
]
