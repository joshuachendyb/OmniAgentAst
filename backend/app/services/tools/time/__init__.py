# -*- coding: utf-8 -*-
"""
Time 模块 - 时间/日期工具

【架构规范】2026-04-26 小沈
- time_register.py: 工具注册点（导入触发注册）
- time_tools.py: 具体实现

目录结构：
    time/
    ├── __init__.py           # 本文件，导入 time_register 触发注册
    ├── time_register.py     # 工具注册点
    └── time_tools.py        # 具体实现

【修复】2026-04-26 小沈
- 必须同时导入 time_register 和 time_tools 来触发注册
"""

# 【修复】必须同时导入 time_register 和 time_tools 来触发注册
from app.services.tools.time import time_register
from app.services.tools.time import time_tools  # 触发 time_tools 中的 @register_tool 装饰器

# 导出常用工具函数（方便直接导入使用）
from app.services.tools.time.time_tools import (
    time_now,
    time_format,
    time_diff,
    timer_set,
    timer_clear,
    time_utc_to_local,
    time_local_to_utc,
    time_is_weekend,
    time_is_holiday,
    time_add,
    timer_list,
    time_compare,
    time_to_timestamp,
    timestamp_to_time,
    time_is_workday,
    time_next_n_workday,
)

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
    "time_add",
    "timer_list",
    "time_compare",
    "time_to_timestamp",
    "timestamp_to_time",
    "time_is_workday",
    "time_next_n_workday",
]