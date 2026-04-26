# -*- coding: utf-8 -*-
"""
Time Register - 时间工具注册点

【架构规范】2026-04-26 小沈
- 使用 @register_tool 装饰器注册所有时间工具
- 工具函数从 time_tools.py 导入

注册的工具：
1. time_now - 获取当前系统时间
2. time_format - 格式化时间戳
3. time_diff - 计算时间差
4. timer_set - 设置定时器
5. timer_clear - 清除定时器
6. time_utc_to_local - UTC转本地时间
7. time_local_to_utc - 本地时间转UTC
8. time_is_weekend - 判断是否周末
9. time_is_holiday - 判断是否假日
"""

from app.services.tools.registry import register_tool, ToolCategory

# 导入工具函数
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
)

# ============================================================
# 注册时间工具
# ============================================================

@register_tool(
    name="time_now",
    description="""获取当前系统时间。

使用场景：
- 当用户问"现在几点了"时使用此工具
- 当用户问"今天星期几"时使用此工具
- 当用户问"当前时间戳是多少"时使用此工具

返回数据说明：
- iso: ISO格式时间（如2026-04-26T10:30:00+08:00）
- timestamp: Unix时间戳（秒）
- format: 默认格式时间（如2026-04-26 10:30:00）
- timezone: 时区（如+0800）
- weekday: 英文星期几（如Saturday）
- isoweekday: ISO星期几（1=Monday, 7=Sunday）""",
    category=ToolCategory.TIME,
    examples=[{}]
)
def register_time_now(): pass  # 占位，函数体在 time_tools.py


@register_tool(
    name="time_format",
    description="""格式化时间戳或日期字符串为指定格式。

使用场景：
- 当用户问"这个文件什么时候改的？用中文显示"时使用此工具
- 当用户问"把当前时间格式化成YYYY年MM月DD日"时使用此工具
- 当用户需要将时间戳转换为可读格式时使用

参数说明：
- timestamp: 时间戳（Unix秒）或日期字符串。默认为None（当前时间）
- pattern: 格式字符串，默认为"%Y-%m-%d %H:%M:%S" """,
    category=ToolCategory.TIME,
    examples=[
        {},
        {"timestamp": 1777103094},
        {"timestamp": None, "pattern": "%Y年%m月%d日"}
    ]
)
def register_time_format(): pass


@register_tool(
    name="time_diff",
    description="""计算两个时间之间的差值，返回人性化描述。

使用场景：
- 当用户问"我上次问这个是什么时候？"时使用此工具
- 当用户问"这个文件多久前修改的？"时使用此工具
- 当用户问"距离 deadline 还有多长时间？"时使用此工具

参数说明：
- start: 开始时间（时间戳、字符串、datetime）
- end: 结束时间（时间戳、字符串、datetime），默认为None（当前时间）""",
    category=ToolCategory.TIME,
    examples=[
        {"start": 1777103094},
        {"start": "2026-04-25", "end": None}
    ]
)
def register_time_diff(): pass


@register_tool(
    name="timer_set",
    description="""设置定时器，在指定延迟后执行回调。

使用场景：
- 当用户说"3分钟后提醒我"时使用此工具
- 当用户说"10分钟后执行这个任务"时使用此工具

参数说明：
- delay: 延迟时间（秒），必须大于0，不超过86400秒（24小时）
- callback: 回调函数描述
- callback_data: 传递给回调的数据（可选）""",
    category=ToolCategory.TIME,
    examples=[
        {"delay": 180, "callback": "提醒用户喝水"},
        {"delay": 600, "callback": "执行备份"}
    ]
)
def register_timer_set(): pass


@register_tool(
    name="timer_clear",
    description="""清除（取消）已设置的定时器。

使用场景：
- 当用户说"取消那个定时器"时使用此工具

参数说明：
- timer_id: 定时器ID（由timer_set返回）""",
    category=ToolCategory.TIME,
    examples=[
        {"timer_id": "timer_1_1234567890"}
    ]
)
def register_timer_clear(): pass


@register_tool(
    name="time_utc_to_local",
    description="""将UTC时间转换为本地时间或指定时区时间。

使用场景：
- 当用户需要将UTC时间转换为本地时间时使用此工具
- 当用户在跨国协作中需要转换时间时使用

参数说明：
- utc_time: UTC时间（时间戳、字符串、datetime）
- target_tz: 目标时区（如"+08:00"、"Asia/Shanghai"），默认为None（本地时区）""",
    category=ToolCategory.TIME,
    examples=[
        {"utc_time": "2026-04-25T12:00:00Z"},
        {"utc_time": 1777103094, "target_tz": "+08:00"}
    ]
)
def register_time_utc_to_local(): pass


@register_tool(
    name="time_local_to_utc",
    description="""将本地时间或指定时区时间转换为UTC时间。

使用场景：
- 当用户需要将本地时间转换为UTC时间时使用此工具
- 当用户需要提交UTC时间给系统时使用

参数说明：
- local_time: 本地时间（时间戳、字符串、datetime）
- source_tz: 源时区（如"+08:00"），默认为None（本地时区）""",
    category=ToolCategory.TIME,
    examples=[
        {"local_time": "2026-04-25 20:00:00"},
        {"local_time": "2026-04-25T20:00:00", "source_tz": "+08:00"}
    ]
)
def register_time_local_to_utc(): pass


@register_tool(
    name="time_is_weekend",
    description="""检查给定日期是否为周末（周六或周日）。

使用场景：
- 当用户问"明天是周末吗？"时使用此工具
- 当用户问"这个日期是周末吗？"时使用此工具

参数说明：
- date: 日期（时间戳、字符串、datetime），默认为None（当前日期）""",
    category=ToolCategory.TIME,
    examples=[
        {},
        {"date": "2026-04-25"},
        {"date": "2026-04-26"}
    ]
)
def register_time_is_weekend(): pass


@register_tool(
    name="time_is_holiday",
    description="""检查给定日期是否为假日（法定节假日）。

使用场景：
- 当用户问"明天是假期吗？"时使用此工具
- 当用户问"这个日期是法定节假日吗？"时使用此工具

参数说明：
- date: 日期（时间戳、字符串、datetime），默认为None（当前日期）

注意：当前为简单实现，使用内置假日列表""",
    category=ToolCategory.TIME,
    examples=[
        {},
        {"date": "2026-01-01"},
        {"date": "2026-10-01"}
    ]
)
def register_time_is_holiday(): pass


# ============================================================
# 实际注册函数（使用实际的工具函数）
# ============================================================
# 由于装饰器需要的是函数引用，我们需要重新应用装饰器
# 但实际上 time_tools.py 中的函数已经通过 registry.py 的 register_tool 注册了
# 这里只是为了保持架构一致性，实际的工具注册在导入时自动完成

# 如果需要重新注册，可以执行以下代码：
# from app.services.tools.registry import tool_registry
# tool_registry.register(name="time_now", description=..., category=ToolCategory.TIME, implementation=time_now)