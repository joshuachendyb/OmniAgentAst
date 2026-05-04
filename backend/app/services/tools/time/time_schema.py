# -*- coding: utf-8 -*-
"""
Time Intent 工具参数 Schema 定义

【创建时间】2026-04-29 小沈
【设计依据】按2026-04-29新增工具规范流程

职责：
定义 time 意图的9个工具的参数 Pydantic 模型，作为独立的 Schema 定义文件。
其他模块（如 time_tools.py、react_schema.py）从这里导入模型使用。

各工具的 Schema 文件统一放在 tools/{type}/ 目录下：
- tools/time/time_schema.py   → time 意图的工具参数 Schema
- tools/file/file_schema.py  → file 意图的工具参数 Schema
- tools/network/network_schema.py → network 意图的工具参数 Schema（待实现）

Author: 小沈 - 2026-04-29
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, Union


# ===========================================================
# P0 核心基础（5个）
# ===========================================================

class TimeNowInput(BaseModel):
    """get_current_time 工具的输入参数 - 小沈 2026-05-03 增加3参数"""
    timezone: Optional[str] = Field(
        default=None,
        description="时区（IANA标准），如'Asia/Shanghai'、'America/New_York'。None(默认)跟随系统时区。Agent可从query地名自动映射"
    )
    format: Optional[str] = Field(
        default=None,
        description="输出格式字符串（如'%Y-%m-%d %H:%M:%S'）。None(默认)使用'%Y-%m-%d %H:%M:%S'。Agent语义解析意图：'几号'→'%Y-%m-%d'，'星期几'→'%A'，'时间戳'→'X'"
    )
    locale: Optional[str] = Field(
        default=None,
        description="本地化语言（如'zh_CN'、'en_US'）。None(默认)匹配当前会话语言。自动处理星期、月份、AM/PM的本地化输出"
    )


class TimeFormatInput(BaseModel):
    """time_format 工具的输入参数"""
    timestamp: Optional[Union[int, float, str]] = Field(
        default=None,
        description="时间戳（Unix秒）、日期字符串（如'2026-04-25'）、或datetime对象。Agent 判断：如果为None（默认），则使用当前时间。支持格式：int/float=Unix时间戳，str=日期字符串自动识别，datetime=直接使用"
    )
    pattern: Optional[str] = Field(
        default=None,
        description="格式字符串（如'%Y-%m-%d %H:%M:%S'）。Agent语义解析意图：'几号'→'%Y-%m-%d'，'星期几'→'%A'，'时间戳'→'X'。如果为None（默认），则使用'%Y-%m-%d %H:%M:%S'"
    )


class TimeDiffInput(BaseModel):
    """time_diff 工具的输入参数"""
    start: Union[int, float, str] = Field(
        ...,
        description="开始时间（时间戳、字符串、datetime）。支持格式：int/float=Unix时间戳，str=日期字符串，datetime=直接使用。必填参数"
    )
    end: Optional[Union[int, float, str]] = Field(
        default=None,
        description="结束时间（时间戳、字符串、datetime）。Agent 判断：如果为None（默认），则使用当前时间。支持格式同start"
    )


class TimerSetInput(BaseModel):
    """timer_set 工具的输入参数"""
    delay: float = Field(
        ...,
        gt=0,
        le=86400,
        description="延迟时间（秒）。必须大于0，不能超过86400秒（24小时）。必填参数"
    )
    callback: str = Field(
        ...,
        description="回调函数标识或描述（字符串）。描述要执行的操作。必填参数"
    )
    callback_data: Optional[Dict[str, Any]] = Field(
        default=None,
        description="传递给回调的数据（可选）。可选参数，默认为None"
    )


class TimerClearInput(BaseModel):
    """timer_clear 工具的输入参数"""
    timer_id: str = Field(
        ...,
        description="定时器ID（由timer_set返回）。必填参数"
    )


# ===========================================================
# P1 常用辅助（4个）
# ===========================================================

class TimeUtcToLocalInput(BaseModel):
    """time_utc_to_local 工具的输入参数"""
    utc_time: Union[int, float, str] = Field(
        ...,
        description="UTC时间（时间戳、字符串、datetime）。支持格式：int/float=Unix时间戳，str=日期字符串，datetime=直接使用。必填参数"
    )
    target_tz: Optional[str] = Field(
        default=None,
        description="目标时区（如'+08:00'、'Asia/Shanghai'）。如果为None则使用本地时区。可选参数，默认为None（本地时区）"
    )


class TimeLocalToUtcInput(BaseModel):
    """time_local_to_utc 工具的输入参数"""
    local_time: Union[int, float, str] = Field(
        ...,
        description="本地时间（时间戳、字符串、datetime）。支持格式：int/float=Unix时间戳，str=日期字符串，datetime=直接使用。必填参数"
    )
    source_tz: Optional[str] = Field(
        default=None,
        description="源时区（如'+08:00'、'Asia/Shanghai'）。如果为None则使用本地时区。可选参数，默认为None（本地时区）"
    )


class TimeIsWeekendInput(BaseModel):
    """time_is_weekend 工具的输入参数"""
    date: Optional[Union[int, float, str]] = Field(
        default=None,
        description="日期（时间戳、字符串、datetime）。如果为None则使用当前日期。可选参数，默认为None（当前日期）"
    )


class TimeIsHolidayInput(BaseModel):
    """time_is_holiday 工具的输入参数"""
    date: Optional[Union[int, float, str]] = Field(
        default=None,
        description="日期（时间戳、字符串、datetime）。如果为None则使用当前日期。可选参数，默认为None（当前日期）"
    )

class TimeAddInput(BaseModel):
    """time_add 工具的输入参数"""
    start: Union[int, float, str] = Field(
        ...,
        description="基准时间（时间戳、字符串、datetime）。支持格式：int/float=Unix时间戳，str=日期字符串，datetime=直接使用。必填参数"
    )
    delta: float = Field(
        ...,
        description="偏移量（数字）。正数表示增加，负数表示减少。必填参数"
    )
    unit: str = Field(
        default="days",
        description="单位（days/hours/minutes/seconds/months）。默认为days。Agent 语义解析：'3天'→unit='days', '2小时'→unit='hours'。可选参数，默认为days"
    )