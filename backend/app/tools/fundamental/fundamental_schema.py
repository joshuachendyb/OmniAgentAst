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
    format: Optional[str] = Field(
        default=None,
        description="Python strftime格式字符串,如 %%Y-%%m-%%d %%H:%%M:%%S。默认为 %%Y-%%m-%%d %%H:%%M:%%S"
    )
    timezone: Optional[str] = Field(
        default=None,
        description="时区,如 Asia/Shanghai、America/New_York。默认为系统时区"
    )


class TimeAddInput(BaseModel):
    delta: float = Field(
        ...,
        description="偏移量。正数=增加,负数=减少。例如 delta=3 表示加3,delta=-2 表示减2。必填参数"
    )
    start: Optional[Union[int, float, str]] = Field(
        default=None,
        description="基准时间。支持:int/float=Unix时间戳(秒),str=日期字符串。默认为当前时间"
    )
    unit: Literal["days", "hours", "minutes", "seconds", "months"] = Field(
        default="days",
        description="偏移单位:days(天)、hours(小时)、minutes(分钟)、seconds(秒)、months(月,使用dateutil.relativedelta,失败回退days*30)。默认为days"
    )


class TimeDiffInput(BaseModel):
    start: Union[int, float, str] = Field(
        ...,
        description="开始时间。支持:int/float=Unix时间戳(秒),str=日期字符串。必填参数"
    )
    end: Optional[Union[int, float, str]] = Field(
        default=None,
        description="结束时间。支持格式同start。默认为当前时间"
    )


class QueryCalendarInput(BaseModel):
    """按节日名称查询日期和假期信息
    
    【推荐】name参数查询节日：
    - query_calendar(name="端午节", year=2026)
    - query_calendar(name="春节", year=2026)
    
    【替代】check_type参数检查日期：
    - weekend: 判断周末
    - holiday: 判断节假日
    - workday: 判断工作日
    - next_workday: 计算下N个工作日
    
    【支持】端午节/春节/中秋节/元旦/国庆节/劳动节/清明节/元宵节/七夕节/重阳节/除夕
    
    【注意】设置name时，date和check_type参数被忽略
    """
    name: Optional[str] = Field(
        default=None,
        description="节日名称(推荐),如端午节/春节/中秋节/国庆节"
    )
    year: Optional[int] = Field(
        default=None,
        description="查询年份(默认当年),仅name参数有效"
    )
    date: Optional[Union[int, float, str]] = Field(
        default=None,
        description="日期值,支持时间戳或日期字符串。name不为空时被忽略"
    )
    check_type: Literal["weekend", "holiday", "workday", "next_workday"] = Field(
        default="workday",
        description="检查类型:weekend/holiday/workday/next_workday。name不为空时被忽略"
    )
    n: int = Field(
        default=1,
        description="第N个工作日(仅next_workday有效)"
    )



__all__ = [
    "ToolSearchInput",
    "TimeNowInput",
    "TimeAddInput",
    "TimeDiffInput",
    "QueryCalendarInput",
]
