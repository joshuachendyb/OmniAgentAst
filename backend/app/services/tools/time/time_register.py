# -*- coding: utf-8 -*-
"""
Time Register - 时间工具注册点

【架构规范】2026-04-26 小沈
- 使用 @register_tool 装饰器注册所有时间工具
- 工具函数从 time_tools.py 导入（实际注册在 time_tools.py 的导入时完成）

【注意】2026-04-26 小沈修复
- time_tools.py 中的 @register_tool 装饰器会自动注册
- 这里只需要导入以触发加载
- 不需要重复注册
"""

# 触发 time_tools 导入（@register_tool 装饰器自动完成注册）
from app.services.tools.time import time_tools

# 导出工具函数（方便直接导入）
__all__ = [
    "time_now",
    "time_format", 
    "time_diff",
    "timer_set",
    "timer_clear",
    "time_utc_to_local",
    "time_local_to_utc",
    "time_is_weekend",
    "time_is_holiday",
]