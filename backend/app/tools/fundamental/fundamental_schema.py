# -*- coding: utf-8 -*-
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
    name: Optional[str] = Field(
        default=None,
        description="【推荐】节日名称查询,输入节日名称(如端午节/春节/中秋节/国庆节)一次性返回日期、星期、假期属性,无需逐个日期重复查询。支持端午节/春节/中秋节/元旦/劳动节/国庆节/清明节等"
    )
    year: Optional[int] = Field(
        default=None,
        description="查询年份(默认当年),仅name参数不为空时有效"
    )
    date: Optional[Union[int, float, str]] = Field(
        default=None,
        description="日期值,支持:int/float=Unix时间戳(秒),str=日期字符串。默认为当前日期。name不为空时此参数被忽略"
    )
    check_type: Literal["weekend", "holiday", "workday", "next_workday"] = Field(
        default="workday",
        description="检查类型:weekend=周末判断,holiday=节假日判断,workday=工作日判断,next_workday=下N个工作日。默认为workday。name不为空时此参数被忽略"
    )
    n: int = Field(
        default=1,
        description="第N个工作日(check_type=next_workday时有效)。默认为1"
    )



__all__ = [
    "ToolSearchInput",
    "TimeNowInput",
    "TimeAddInput",
    "TimeDiffInput",
    "QueryCalendarInput",
]
