# -*- coding: utf-8 -*-
"""
Time Intent 工具参数 Schema 定义

【创建时间】2026-04-29 小沈
【最后更新】2026-05-18 小沈 — 16→7精简：新增7个统一入口Schema，旧Schema标注弃用

职责：
定义 time 意图的工具参数 Pydantic 模型，作为独立的 Schema 定义文件。
其他模块（如 time_tools.py、react_schema.py）从这里导入模型使用。

Author: 小沈 - 2026-04-29
Updated: 小沈 - 2026-05-18
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, Union


# ===========================================================
# 新Schema（7个精简工具）— 小沈 2026-05-18
# ===========================================================

class GetTimeInput(BaseModel):
    """get_time统一入口Schema — 小沈 2026-05-18"""
    action: str = Field(
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
    locale: Optional[str] = Field(
        default=None,
        description="本地化语言（action=now时有效），如 zh_CN、en_US。默认为当前会话语言"
    )
    unit: Optional[str] = Field(
        default=None,
        description="时间戳单位（action=to_timestamp时有效）：seconds/milliseconds/microseconds。默认为seconds"
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
    unit: str = Field(
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
    check_type: str = Field(
        default="workday",
        description="检查类型：weekend=周末判断，holiday=节假日判断，workday=工作日判断，next_workday=下N个工作日。默认为workday"
    )
    n: int = Field(
        default=1,
        description="第N个工作日（check_type=next_workday时有效）。默认为1"
    )


class TimezoneConvertInput(BaseModel):
    """timezone_convert时区转换Schema — 小沈 2026-05-18"""
    time_value: Union[int, float, str] = Field(
        ...,
        description="时间值。支持：int/float=Unix时间戳(秒)，str=日期字符串。必填参数"
    )
    direction: str = Field(
        default="utc_to_local",
        description="转换方向：utc_to_local=UTC转本地，local_to_utc=本地转UTC，any=任意源→目标。默认为utc_to_local"
    )
    tz: Optional[str] = Field(
        default=None,
        description="时区（direction=utc_to_local时为目标时区，local_to_utc时为源时区）。默认为本地时区"
    )
    source_tz: Optional[str] = Field(
        default=None,
        description="源时区（direction=any时必填）"
    )
    target_tz: Optional[str] = Field(
        default=None,
        description="目标时区（direction=any时必填）"
    )


class TimerInput(BaseModel):
    """timer定时器管理Schema — 小沈 2026-05-18"""
    action: str = Field(
        ...,
        description="操作类型：set=设置定时器，clear=清除定时器，list=列出定时器。必填参数"
    )
    delay: Optional[float] = Field(
        default=None,
        description="延迟秒数（action=set时必填，1~86400即最长24小时）"
    )
    callback: Optional[str] = Field(
        default=None,
        description="定时器触发时的提醒内容（action=set时必填）"
    )
    callback_data: Optional[Dict[str, Any]] = Field(
        default=None,
        description="回调附加数据（action=set时可选）"
    )
    timer_id: Optional[str] = Field(
        default=None,
        description="定时器ID（action=clear时必填）"
    )
    limit: int = Field(
        default=10,
        description="返回数量限制（action=list时有效）。默认为10"
    )


# ===========================================================
# 旧Schema（标注弃用，P9向下兼容）— 小沈 2026-05-18
# ===========================================================

class TimeNowInput(BaseModel):
    """【已弃用 v2.0】请使用 GetTimeInput(action='now') — 小沈 2026-05-18"""
    timezone: Optional[str] = Field(
        default=None,
        description="时区（IANA标准），如 Asia/Shanghai、America/New_York。Agent 可从 query 中的地名自动映射。默认为系统时区"
    )
    format: Optional[str] = Field(
        default=None,
        description="输出格式字符串，如 %Y-%m-%d %H:%M:%S。Agent 语义解析：查询'几号'→%Y-%m-%d，'星期几'→%A。默认为 %Y-%m-%d %H:%M:%S"
    )
    locale: Optional[str] = Field(
        default=None,
        description="本地化语言，如 zh_CN、en_US。自动处理星期、月份、AM/PM 的本地化输出。默认为当前会话语言"
    )

    class Config:
        deprecated = True


class TimeFormatInput(BaseModel):
    """【已弃用 v2.0】请使用 GetTimeInput(action='format') — 小沈 2026-05-18"""
    timestamp: Optional[Union[int, float, str]] = Field(
        default=None,
        description="待格式化的时间值。支持：int/float=Unix时间戳(秒)，str=日期字符串如'2026-04-25'，datetime=直接使用。默认为当前时间"
    )
    pattern: Optional[str] = Field(
        default=None,
        description="输出格式字符串，如 %Y-%m-%d %H:%M:%S、%Y年%m月%d日、%A。Agent 语义解析：查询'星期几'→%A。默认为 %Y-%m-%d %H:%M:%S"
    )

    class Config:
        deprecated = True


class TimerSetInput(BaseModel):
    """【已弃用 v2.0】请使用 TimerInput(action='set') — 小沈 2026-05-18"""
    delay: float = Field(
        ...,
        gt=0,
        le=86400,
        description="延迟秒数（1~86400，即最长24小时）。必填参数"
    )
    callback: str = Field(
        ...,
        description="回调描述。描述定时器触发时要执行的操作。必填参数"
    )
    callback_data: Optional[Dict[str, Any]] = Field(
        default=None,
        description="传递给回调的附加数据（JSON对象）。可选参数"
    )

    class Config:
        deprecated = True


class TimerClearInput(BaseModel):
    """【已弃用 v2.0】请使用 TimerInput(action='clear') — 小沈 2026-05-18"""
    timer_id: str = Field(
        ...,
        description="要取消的定时器ID（由timer_set返回）。必填参数"
    )

    class Config:
        deprecated = True


class TimeUtcToLocalInput(BaseModel):
    """【已弃用 v2.0】请使用 TimezoneConvertInput(direction='utc_to_local') — 小沈 2026-05-18"""
    utc_time: Union[int, float, str] = Field(
        ...,
        description="UTC时间。支持：int/float=Unix时间戳(秒)，str=日期字符串如'2026-04-25T12:00:00Z'。必填参数"
    )
    target_tz: Optional[str] = Field(
        default=None,
        description="目标时区，如 +08:00 或 Asia/Shanghai。默认为本地时区"
    )

    class Config:
        deprecated = True


class TimeLocalToUtcInput(BaseModel):
    """【已弃用 v2.0】请使用 TimezoneConvertInput(direction='local_to_utc') — 小沈 2026-05-18"""
    local_time: Union[int, float, str] = Field(
        ...,
        description="本地时间。支持：int/float=Unix时间戳(秒)，str=日期字符串。必填参数"
    )
    source_tz: Optional[str] = Field(
        default=None,
        description="源时区，如 +08:00 或 Asia/Shanghai。默认为本地时区"
    )

    class Config:
        deprecated = True


class TimeIsWeekendInput(BaseModel):
    """【已弃用 v2.0】请使用 CheckDateInput(check_type='weekend') — 小沈 2026-05-18"""
    date: Optional[Union[int, float, str]] = Field(
        default=None,
        description="要检查的日期。支持：int/float=Unix时间戳(秒)，str=日期字符串如'2026-04-26'。默认为当前日期"
    )

    class Config:
        deprecated = True


class TimeIsHolidayInput(BaseModel):
    """【已弃用 v2.0】请使用 CheckDateInput(check_type='holiday') — 小沈 2026-05-18"""
    date: Optional[Union[int, float, str]] = Field(
        default=None,
        description="要检查的日期（支持公历+农历节日）。支持：int/float=Unix时间戳(秒)，str=日期字符串。默认为当前日期"
    )

    class Config:
        deprecated = True


class TimeCompareInput(BaseModel):
    """【已弃用 v2.0】请使用 TimeDiffInput — 小沈 2026-05-18"""
    time1: Union[int, float, str] = Field(
        ...,
        description="第一个时间。支持：int/float=Unix时间戳(秒)，str=日期字符串。必填参数"
    )
    time2: Union[int, float, str] = Field(
        ...,
        description="第二个时间。支持格式同time1。必填参数"
    )
    unit: str = Field(
        default="days",
        description="比较精度单位：days(天)、hours(小时)、minutes(分钟)、seconds(秒)。默认为days"
    )

    class Config:
        deprecated = True


class TimeToTimestampInput(BaseModel):
    """【已弃用 v2.0】请使用 GetTimeInput(action='to_timestamp') — 小沈 2026-05-18"""
    time: Union[int, float, str] = Field(
        ...,
        description="要转换的日期时间字符串，如 '2026-05-05 14:30:00'。必填参数"
    )
    unit: str = Field(
        default="seconds",
        description="时间戳单位：seconds(秒)、milliseconds(毫秒)、microseconds(微秒)。默认为seconds"
    )

    class Config:
        deprecated = True


class TimestampToTimeInput(BaseModel):
    """【已弃用 v2.0】请使用 GetTimeInput(action='from_timestamp') — 小沈 2026-05-18"""
    timestamp: Union[int, float] = Field(
        ...,
        description="Unix时间戳（秒）。必填参数"
    )
    target_tz: str = Field(
        default="+08:00",
        description="目标时区（IANA时区名称如 Asia/Shanghai，或±HH:MM格式如 +08:00）。默认为 +08:00"
    )

    class Config:
        deprecated = True


class TimeIsWorkdayInput(BaseModel):
    """【已弃用 v2.0】请使用 CheckDateInput(check_type='workday') — 小沈 2026-05-18"""
    date: Optional[Union[int, float, str]] = Field(
        default=None,
        description="要检查的日期（周一至周五为工作日）。支持：int/float=Unix时间戳(秒)，str=日期字符串。默认为当前日期"
    )

    class Config:
        deprecated = True


class TimeNextNWorkdayInput(BaseModel):
    """【已弃用 v2.0】请使用 CheckDateInput(check_type='next_workday') — 小沈 2026-05-18"""
    start: Optional[Union[int, float, str]] = Field(
        default=None,
        description="起始日期。支持：int/float=Unix时间戳(秒)，str=日期字符串。默认为当前日期"
    )
    n: int = Field(
        default=1,
        description="从起始日期开始的第N个工作日（正整数）。默认为1"
    )

    class Config:
        deprecated = True


class TimerListInput(BaseModel):
    """【已弃用 v2.0】请使用 TimerInput(action='list') — 小沈 2026-05-18"""
    limit: int = Field(
        default=10,
        description="返回的定时器数量上限。默认为10"
    )

    class Config:
        deprecated = True
