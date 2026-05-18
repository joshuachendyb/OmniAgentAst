# -*- coding: utf-8 -*-
"""
Time 模块 - 时间/日期工具（已迁入Meta分类）

【2026-05-18 小沈】Time→Meta：注册改由time_register.py完成（ToolCategory.META）
"""

# 【修复】必须同时导入 time_register 和 time_tools 来触发注册
from app.services.tools.time import time_register
from app.services.tools.time import time_tools  # 触发 time_tools 中的函数定义

# 导出6个精简工具函数
from app.services.tools.time.time_tools import (
    get_time,
    time_add,
    time_diff,
    check_date,
    timezone_convert,
    timer,
)

__all__ = [
    "get_time",
    "time_add",
    "time_diff",
    "check_date",
    "timezone_convert",
    "timer",
]
