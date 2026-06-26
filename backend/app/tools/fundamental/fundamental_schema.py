# -*- coding: utf-8 -*-
"""
FUNDAMENTAL Schema - 基础工具参数模型

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

示例：query_calendar有多个使用方式，适合添加docstring说明
"""
# Merged schema - 小欧 2026-06-18

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, Union, Literal

class ToolSearchInput(BaseModel):
    query: str = Field(..., description="先用此工具搜索未加载的工具。BM25全文检索，支持中英文混合。例如:'读取Word文档' 'SQL查询 数据库' '生成图表' '搜索文件' '压缩解压'。输入1-3个核心关键词效果最好。")



class TimeNowInput(BaseModel):
    pass


class TimeAddInput(BaseModel):
    delta: float = Field(
        ...,
        description="偏移量。正数=增加,负数=减少。例如 delta=3 表示加3,delta=-2 表示减2。必填参数"
    )
    start: Optional[Union[int, float, str]] = Field(
        default=None,
        description="""基准时间(可选)，默认当前时间。支持多种格式：

【时间戳】
- 整数: 1719360000
- 浮点数: 1719360000.123

【时间字符串】
- 日期: "2026-06-26"
- 日期时间: "2026-06-26 10:30:00"
- ISO格式: "2026-06-26T10:30:00"

【示例】
- 不传(使用当前时间): start=None
- 时间戳: start=1719360000
- 日期字符串: start="2026-06-26" """
    )
    unit: Literal["days", "hours", "minutes", "seconds", "months"] = Field(
        default="days",
        description="偏移单位:days(天)/hours(小时)/minutes(分钟)/seconds(秒)/months(月)"
    )


class TimeDiffInput(BaseModel):
    start: Union[int, float, str] = Field(
        ...,
        description="""起始时间。支持多种格式：

【时间戳】
- 整数: 1719360000
- 浮点数: 1719360000.123

【时间字符串】
- 日期: "2026-06-26"
- 日期时间: "2026-06-26 10:30:00"
- ISO格式: "2026-06-26T10:30:00"

【示例】
- 时间戳: start=1719360000
- 日期字符串: start="2026-06-26" """
    )
    end: Optional[Union[int, float, str]] = Field(
        default=None,
        description="""结束时间(可选)，默认当前时间。支持多种格式：

【时间戳】
- 整数: 1719456000
- 浮点数: 1719456000.456

【时间字符串】
- 日期: "2026-06-27"
- 日期时间: "2026-06-27 10:30:00"
- ISO格式: "2026-06-27T10:30:00"

【示例】
- 不传(使用当前时间): end=None
- 时间戳: end=1719456000
- 日期字符串: end="2026-06-27" """
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
        default=None,
        description="查询年份(默认当年),仅name为节日名时有效"
    )


class SendNotificationInput(BaseModel):
    title: str = Field(
        description="通知标题,例如:'AI热点新闻'"
    )
    message: str = Field(
        description="通知正文,例如:'已为您搜索到最新AI行业新闻'"
    )
    duration: int = Field(
        default=5,
        description="通知显示时长(秒),默认5秒"
    )


class GetSystemInfoInput(BaseModel):
    info_type: Optional[Literal["basic", "cpu", "memory", "disk", "network", "all"]] = Field(
        default="all",
        description="系统信息类型:basic(基础)/cpu/内存/磁盘/网络/all(全部,默认)"
    )



__all__ = [
    "ToolSearchInput",
    "TimeNowInput",
    "TimeAddInput",
    "TimeDiffInput",
    "QueryCalendarInput",
    "SendNotificationInput",
    "GetSystemInfoInput",
]
