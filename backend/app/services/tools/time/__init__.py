# -*- coding: utf-8 -*-
"""
Time 模块 - 时间/日期工具

【架构规范】2026-04-26 小沈
- time_register.py: 工具注册点（导入触发注册）
- time_tools.py: 具体实现

【2026-05-18 小沈重构】16→7精简
- 导出7个精简工具：get_time, time_add, time_diff, check_date, timezone_convert, timer
- 旧函数通过委托仍可导入（P9向下兼容）

目录结构：
    time/
    ├── __init__.py           # 本文件，导入 time_register 触发注册
    ├── time_register.py     # 工具注册点
    ├── time_schema.py       # Schema定义
    └── time_tools.py        # 具体实现
"""

# 【修复】必须同时导入 time_register 和 time_tools 来触发注册
from app.services.tools.time import time_register
from app.services.tools.time import time_tools  # 触发 time_tools 中的函数定义

# 导出7个精简工具函数
from app.services.tools.time.time_tools import (
    get_time,
    time_add,
    time_diff,
    check_date,
    timezone_convert,
    timer,
)

# 旧函数委托（P9向下兼容）仍可导入
from app.services.tools.time.time_tools import (
    get_current_time,
    time_format,
    timer_set,
    timer_clear,
    time_utc_to_local,
    time_local_to_utc,
    time_is_weekend,
    time_is_holiday,
    timer_list,
    time_compare,
    time_to_timestamp,
    timestamp_to_time,
    time_is_workday,
    time_next_n_workday,
)

__all__ = [
    # 7个精简工具
    "get_time",
    "time_add",
    "time_diff",
    "check_date",
    "timezone_convert",
    "timer",
    # 旧函数委托（P9向下兼容）
    "get_current_time",
    "time_format",
    "timer_set",
    "timer_clear",
    "time_utc_to_local",
    "time_local_to_utc",
    "time_is_weekend",
    "time_is_holiday",
    "timer_list",
    "time_compare",
    "time_to_timestamp",
    "timestamp_to_time",
    "time_is_workday",
    "time_next_n_workday",
]
