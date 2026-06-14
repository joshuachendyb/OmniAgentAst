# -*- coding: utf-8 -*-
"""
Time 工具参数 Schema 定义

职责:
定义 time 意图的工具参数 Pydantic 模型,作为独立的 Schema 定义文件。

Author: 小沈 - 2026-04-29
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, Union, Literal


class TimeNowInput(BaseModel):
    action: Literal["now", "format", "to_timestamp", "from_timestamp"] = Field(
        default="now",
        description="操作类型:now=获取当前时间,format=格式化时间,to_timestamp=转时间戳,from_timestamp=时间戳转时间。默认为now"
    )
    time_value: Optional[Union[int, float, str]] = Field(
        default=None,
        description="时间值。支持:int/float=Unix时间戳(秒),str=日期字符串。action=to_timestamp/from_timestamp时必填,action=format时不传则使用当前时间,action=now时忽略"
    )
    format: Optional[str] = Field(
        default=None,
        description="Python strftime格式字符串,如 %Y-%m-%d %H:%M:%S。默认为 %Y-%m-%d %H:%M:%S。action=now/format时生效"
    )
    timezone: Optional[str] = Field(
        default=None,
        description="时区(action=now时有效),如 Asia/Shanghai、America/New_York。默认为系统时区"
    )
    target_tz: Optional[str] = Field(
        default=None,
        description="目标时区(action=from_timestamp时有效),如 Asia/Shanghai 或 +08:00。默认为 +08:00"
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


class TimerInput(BaseModel):
    action: Literal["set", "clear", "list"] = Field(
        ...,
        description="操作类型:set=设置定时器,clear=清除定时器,list=列出定时器。必填参数"
    )
    delay: Optional[float] = Field(
        default=None,
        ge=1,
        le=86400,
        description="延迟秒数(action=set时必填,1~86400即最长24小时)"
    )
    callback: Optional[str] = Field(
        default=None,
        description="定时器触发内容(action=set时必填)。支持三种模式:文本消息(记录日志)、URL(httpx回调)、其他内容"
    )
    timer_id: Optional[str] = Field(
        default=None,
        description="定时器ID(action=clear时必填)"
    )


__all__ = [
    "TimeNowInput",
    "TimeAddInput",
    "TimeDiffInput",
    "QueryCalendarInput",
    "TimerInput",
]
