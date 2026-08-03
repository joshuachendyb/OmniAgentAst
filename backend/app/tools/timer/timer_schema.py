# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-20 - 小欧 - 复核schema docstring规范,3个工具默认行为均已在Field描述中体现，无需新增docstring
# 2026-07-25 - 小欧 - description去冗?3处必填参数重复移除
# 2026-07-25 - 小欧 - Field格式统一: callback/timer_id多余空格清理
# 2026-07-31 - 小欧 - timer_set.callback加min_length=1防空字符串; time_add.delta加范围指引; query_calendar.year加ge/le约束
"""
Timer Schema - 定时器工具参数模型

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
from typing import Optional, Literal


class TimerSetInput(BaseModel):
    delay: float = Field(
        ..., ge=1, le=86400,
        description="延迟秒数(1~86400即最24小时)"
    )
    callback: str = Field(
        ..., min_length=1, description="定时器触发内容(文本消息)，不可为空"
    )


class TimerClearInput(BaseModel):
    timer_id: str = Field(
        ..., description="定时器ID,由 timer_set 返回"
    )


class TimerListInput(BaseModel):
    pass


class TimeAddInput(BaseModel):
    delta: float = Field(
        ...,
        description="偏移量(秒)。正数增加,负数=减少"
    )
    start: Optional[str] = Field(
        default=None,
        description="""基准时间，默认当前时间。

【格式要求】ISO格式字符串: "YYYY-MM-DD HH:MM:SS"

【示例】
- 不传(使用当前时间): start=None
- 日期: start="2026-06-26"
- 日期时间: start="2026-06-26 10:30:00"

【注意】只支持字符串格式，不支持时间戳"""
    )
    unit: Literal["days", "hours", "minutes", "seconds", "months"] = Field(
        default="days",
        description="偏移单位:days(天)/hours(小时)/minutes(分钟)/seconds(秒)/months(月)"
    )


class TimeDiffInput(BaseModel):
    start: str = Field(
        ...,
        description="""起始时间。

【格式要求】ISO格式字符串: "YYYY-MM-DD HH:MM:SS"

【示例】
- 日期: start="2026-06-26"
- 日期时间: start="2026-06-26 10:30:00"

【注意】只支持字符串格式，不支持时间戳"""
    )
    end: Optional[str] = Field(
        default=None,
        description="""结束时间，默认当前时间。

【格式要求】ISO格式字符串: "YYYY-MM-DD HH:MM:SS"

【示例】
- 不传(使用当前时间): end=None
- 日期: end="2026-06-27"
- 日期时间: end="2026-06-27 10:30:00"

【注意】只支持字符串格式，不支持时间戳"""
    )


class QueryCalendarInput(BaseModel):
    """节日/日期查询工具
    
    【name参数】支持两种用法：
    - 传节日名 → 返回节日日期和信息（如"端午节"、"春节"）
    - 传日期字符串 → 返回工作日/节假日判断（如"2026-06-23"）
    
    【支持的节日】端午节/春节/中秋节/元旦/国庆节/劳动节/清明节/元宵节/七夕节/重阳节/除夕
    
    【使用示例】
    - query_calendar(name="端午节", year=2026)
    - query_calendar(name="2026-06-23")
    """
    name: str = Field(
        ..., description="节日名称或日期字符串。节日名如'端午节'、'春节'；日期如'2026-06-23'自动判断工作日/节假日"
    )
    year: Optional[int] = Field(
        default=None, ge=1900, le=2100,
        description="查询年份(默认当年),仅name为节日名时有效"
    )


__all__ = [
    "TimerSetInput",
    "TimerClearInput",
    "TimerListInput",
    "TimeAddInput",
    "TimeDiffInput",
    "QueryCalendarInput",
]
