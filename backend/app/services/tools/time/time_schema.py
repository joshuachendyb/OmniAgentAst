# -*- coding: utf-8 -*-
"""
Time Intent 工具参数 Schema 定义

【创建时间】2026-04-29 小沈
【最后更新】2026-05-08 小沈 小健 — 统一定义格式：所有Field description采用
  "默认为X" 格式（对齐 generate_param_reminder 的 _extract_semantic_default 正则提取）
【设计依据】按2026-04-29新增工具规范流程

职责：
定义 time 意图的9个工具的参数 Pydantic 模型，作为独立的 Schema 定义文件。
其他模块（如 time_tools.py、react_schema.py）从这里导入模型使用。

各工具的 Schema 文件统一放在 tools/{type}/ 目录下：
- tools/time/time_schema.py   → time 意图的工具参数 Schema
- tools/file/file_schema.py  → file 意图的工具参数 Schema

Author: 小沈 - 2026-04-29
Updated: 小沈 小健 - 2026-05-08
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


class TimeFormatInput(BaseModel):
    """time_format 工具的输入参数"""
    timestamp: Optional[Union[int, float, str]] = Field(
        default=None,
        description="待格式化的时间值。支持：int/float=Unix时间戳(秒)，str=日期字符串如'2026-04-25'，datetime=直接使用。默认为当前时间"
    )
    pattern: Optional[str] = Field(
        default=None,
        description="输出格式字符串，如 %Y-%m-%d %H:%M:%S、%Y年%m月%d日、%A。Agent 语义解析：查询'星期几'→%A。默认为 %Y-%m-%d %H:%M:%S"
    )


class TimeDiffInput(BaseModel):
    """time_diff 工具的输入参数"""
    start: Union[int, float, str] = Field(
        ...,
        description="开始时间。支持：int/float=Unix时间戳(秒)，str=日期字符串。必填参数"
    )
    end: Optional[Union[int, float, str]] = Field(
        default=None,
        description="结束时间。支持格式同start。默认为当前时间"
    )


class TimerSetInput(BaseModel):
    """timer_set 工具的输入参数"""
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


class TimerClearInput(BaseModel):
    """timer_clear 工具的输入参数"""
    timer_id: str = Field(
        ...,
        description="要取消的定时器ID（由timer_set返回）。必填参数"
    )


# ===========================================================
# P1 常用辅助（4个）
# ===========================================================

class TimeUtcToLocalInput(BaseModel):
    """time_utc_to_local 工具的输入参数"""
    utc_time: Union[int, float, str] = Field(
        ...,
        description="UTC时间。支持：int/float=Unix时间戳(秒)，str=日期字符串如'2026-04-25T12:00:00Z'。必填参数"
    )
    target_tz: Optional[str] = Field(
        default=None,
        description="目标时区，如 +08:00 或 Asia/Shanghai。默认为本地时区"
    )


class TimeLocalToUtcInput(BaseModel):
    """time_local_to_utc 工具的输入参数"""
    local_time: Union[int, float, str] = Field(
        ...,
        description="本地时间。支持：int/float=Unix时间戳(秒)，str=日期字符串。必填参数"
    )
    source_tz: Optional[str] = Field(
        default=None,
        description="源时区，如 +08:00 或 Asia/Shanghai。默认为本地时区"
    )


class TimeIsWeekendInput(BaseModel):
    """time_is_weekend 工具的输入参数"""
    date: Optional[Union[int, float, str]] = Field(
        default=None,
        description="要检查的日期。支持：int/float=Unix时间戳(秒)，str=日期字符串如'2026-04-26'。默认为当前日期"
    )


class TimeIsHolidayInput(BaseModel):
    """time_is_holiday 工具的输入参数"""
    date: Optional[Union[int, float, str]] = Field(
        default=None,
        description="要检查的日期（支持公历+农历节日）。支持：int/float=Unix时间戳(秒)，str=日期字符串。默认为当前日期"
    )

class TimeAddInput(BaseModel):
    """time_add 工具的输入参数"""
    # 【修复 2026-05-05 小沈】start改为可选，默认None=当前时间
    # 避免LLM犹豫"start是必填需要先获取时间"而不调用工具
    start: Optional[Union[int, float, str]] = Field(
        default=None,
        description="基准时间。支持：int/float=Unix时间戳(秒)，str=日期字符串。默认为当前时间"
    )
    delta: float = Field(
        ...,
        description="偏移量。正数=增加，负数=减少。例如 delta=3 表示加3，delta=-2 表示减2。必填参数"
    )
    unit: str = Field(
        default="days",
        description="偏移单位：days(天)、hours(小时)、minutes(分钟)、seconds(秒)、months(月)。Agent 语义解析：'3天'→days，'2小时'→hours。默认为 days"
    )

class TimerListInput(BaseModel):
    """timer_list 工具的输入参数"""
    limit: int = Field(
        default=10,
        description="返回的定时器数量上限。默认为10"
    )

class TimeCompareInput(BaseModel):
    """time_compare 工具的输入参数"""
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

class TimeToTimestampInput(BaseModel):
    """time_to_timestamp 工具的输入参数"""
    time: Union[int, float, str] = Field(
        ...,
        description="要转换的日期时间字符串，如 '2026-05-05 14:30:00'。必填参数"
    )
    unit: str = Field(
        default="seconds",
        description="时间戳单位：seconds(秒)、milliseconds(毫秒)、microseconds(微秒)。默认为seconds"
    )

class TimestampToTimeInput(BaseModel):
    """timestamp_to_time 工具的输入参数"""
    timestamp: Union[int, float] = Field(
        ...,
        description="Unix时间戳（秒）。必填参数"
    )
    target_tz: str = Field(
        default="+08:00",
        description="目标时区（IANA时区名称如 Asia/Shanghai，或±HH:MM格式如 +08:00）。默认为 +08:00"
    )

class TimeIsWorkdayInput(BaseModel):
    """time_is_workday 工具的输入参数"""
    date: Optional[Union[int, float, str]] = Field(
        default=None,
        description="要检查的日期（周一至周五为工作日）。支持：int/float=Unix时间戳(秒)，str=日期字符串。默认为当前日期"
    )

class TimeNextNWorkdayInput(BaseModel):
    """time_next_n_workday 工具的输入参数"""
    start: Optional[Union[int, float, str]] = Field(
        default=None,
        description="起始日期。支持：int/float=Unix时间戳(秒)，str=日期字符串。默认为当前日期"
    )
    n: int = Field(
        default=1,
        description="从起始日期开始的第N个工作日（正整数）。默认为1"
    )
