# -*- coding: utf-8 -*-
"""
Time Intent 工具参数 Schema 定义

【创建时间】2026-04-29 小沈
【最后更新】2026-05-18 小沈 — 16→7精简：新增7个统一入口Schema，旧Schema标注弃用
【2026-05-19 小沈】参数精简：
- GetTimeInput: 7→5(砍locale+unit)
- TimezoneConvertInput: 5→3(砍source_tz+target_tz)
- TimerInput: 6→4(砍callback_data+limit)

职责：
定义 time 意图的工具参数 Pydantic 模型，作为独立的 Schema 定义文件。

Author: 小沈 - 2026-04-29
Updated: 小沈 2026-05-19
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, Union, Literal


# ===========================================================
# 新Schema（7个精简工具）— 小沈 2026-05-18
# ===========================================================

class GetTimeInput(BaseModel):
    """get_time统一入口Schema — 小沈 2026-05-19 参数精简7→5(砍locale+unit)"""
    action: Literal["now", "format", "to_timestamp", "from_timestamp"] = Field(
        default="now",
        description="操作类型：now=获取当前时间，format=格式化时间，to_timestamp=转时间戳，from_timestamp=时间戳转时间。默认为now"
    )
    time_value: Optional[Union[int, float, str]] = Field(
        default=None,
        description="时间值（action=format/to_timestamp/from_timestamp时必填）。支持：int/float=Unix时间戳(秒)，str=日期字符串"
    )
    format: Optional[str] = Field(
        default=None,
        description="输出格式字符串，如 %Y-%m-%d %H:%M:%S。默认为 %Y-%m-%d %H:%M:%S"
    )
    timezone: Optional[str] = Field(
        default=None,
        description="时区（action=now时有效），如 Asia/Shanghai、America/New_York。默认为系统时区"
    )
    target_tz: Optional[str] = Field(
        default=None,
        description="目标时区（action=from_timestamp时有效），如 Asia/Shanghai 或 +08:00。默认为 +08:00"
    )


class TimeAddInput(BaseModel):
    """time_add 时间加减Schema — 小沈 2026-05-18"""
    delta: float = Field(
        ...,
        description="偏移量。正数=增加，负数=减少。例如 delta=3 表示加3，delta=-2 表示减2。必填参数"
    )
    start: Optional[Union[int, float, str]] = Field(
        default=None,
        description="基准时间。支持：int/float=Unix时间戳(秒)，str=日期字符串。默认为当前时间"
    )
    unit: Literal["days", "hours", "minutes", "seconds", "months"] = Field(
        default="days",
        description="偏移单位：days(天)、hours(小时)、minutes(分钟)、seconds(秒)、months(月)。默认为days"
    )


class TimeDiffInput(BaseModel):
    """time_diff 时间差值Schema — 小沈 2026-05-18"""
    start: Union[int, float, str] = Field(
        ...,
        description="开始时间。支持：int/float=Unix时间戳(秒)，str=日期字符串。必填参数"
    )
    end: Optional[Union[int, float, str]] = Field(
        default=None,
        description="结束时间。支持格式同start。默认为当前时间"
    )


class CheckDateInput(BaseModel):
    """check_date日期综合检查Schema — 小沈 2026-05-18"""
    date: Optional[Union[int, float, str]] = Field(
        default=None,
        description="日期值，支持：int/float=Unix时间戳(秒)，str=日期字符串。默认为当前日期"
    )
    check_type: Literal["weekend", "holiday", "workday", "next_workday"] = Field(
        default="workday",
        description="检查类型：weekend=周末判断，holiday=节假日判断，workday=工作日判断，next_workday=下N个工作日。默认为workday"
    )
    n: int = Field(
        default=1,
        description="第N个工作日（check_type=next_workday时有效）。默认为1"
    )


class TimezoneConvertInput(BaseModel):
    """timezone_convert时区转换Schema — 小沈 2026-05-19 参数精简5→3(砍source_tz+target_tz)"""
    time_value: Union[int, float, str] = Field(
        ...,
        description="时间值。支持：int/float=Unix时间戳(秒)，str=日期字符串。必填参数"
    )
    direction: Literal["utc_to_local", "local_to_utc", "any"] = Field(
        default="utc_to_local",
        description="转换方向：utc_to_local=UTC转本地，local_to_utc=本地转UTC，any=任意源→目标。默认为utc_to_local"
    )
    tz: Optional[str] = Field(
        default=None,
        description="时区。direction=utc_to_local时为目标时区，local_to_utc时为源时区，any时为源时区。默认为本地时区"
    )


class TimerInput(BaseModel):
    """timer定时器管理Schema — 小沈 2026-05-19 参数精简6→4(砍callback_data+limit)"""
    action: Literal["set", "clear", "list"] = Field(
        ...,
        description="操作类型：set=设置定时器，clear=清除定时器，list=列出定时器。必填参数"
    )
    delay: Optional[float] = Field(
        default=None,
        ge=1,
        le=86400,
        description="延迟秒数（action=set时必填，1~86400即最长24小时）"
    )
    callback: Optional[str] = Field(
        default=None,
        description="定时器触发时的提醒内容（action=set时必填）"
    )
    timer_id: Optional[str] = Field(
        default=None,
        description="定时器ID（action=clear时必填）"
    )

