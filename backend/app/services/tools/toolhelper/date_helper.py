# -*- coding: utf-8 -*-
"""
日期时间通用解析与计算Helper(不暴露给LLM)
【设计说明 2026-06-17 北京老陈确认】本文件是按工具分类聚合的实现文件，文件大是正常设计。后续审查关注功能逻辑本身的代码10大规范遵守和最优美简洁性，禁止以"文件过大"作为问题提出。

【创建时间】2026-05-18 小沈
【P13提取】从 time_tools.py 提取5个内部函数

函数清单:
- parse_datetime_any: 通用时间解析(datetime/int/float/str → datetime)
- parse_datetime_string: 字符串时间解析(ISO/中文/数字提取)
- is_holiday: 日期是否为假日,返回(bool, holiday_name)
- calc_next_n_workday: 计算下N个工作日
- get_holiday_date_by_name: 按节日名称查找公历日期(新增)
- resolve_timezone: 解析时区字符串
"""

import re
from app.utils.common_patterns import UTC_OFFSET_PATTERN
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

# 常量已迁移到 tool_constants.py — 北京老陈 2026-05-30
from app.services.tools.tool_constants import QINGMING_DATES

SOLAR_HOLIDAYS = {
    (1, 1): "元旦", (2, 14): "情人节", (3, 8): "妇女节",
    (3, 12): "植树节", (4, 1): "愚人节", (5, 1): "劳动节",
    (5, 4): "青年节", (6, 1): "儿童节", (7, 1): "建党节",
    (8, 1): "建军节", (9, 10): "教师节", (10, 1): "国庆节",
    (12, 24): "平安夜", (12, 25): "圣诞节",
}

SOLAR_HOLIDAY_NAMES = {v: k for k, v in SOLAR_HOLIDAYS.items()}

LUNAR_HOLIDAYS = {
    (1, 1): "春节", (1, 15): "元宵节", (5, 5): "端午节",
    (7, 7): "七夕节", (7, 15): "中元节", (8, 15): "中秋节",
    (9, 9): "重阳节", (12, 8): "腊八节", (12, 30): "除夕",
}

LUNAR_HOLIDAY_NAMES = {v: k for k, v in LUNAR_HOLIDAYS.items()}

HOLIDAY_ALIASES = {
    "过年": "春节", "端阳": "端午节", "五月节": "端午节",
    "正月": "春节", "正月十五": "元宵节", "八月十五": "中秋节",
    "正月正": "春节", "五月初五": "端午节",
}


def parse_datetime_any(value: Any) -> Optional[datetime]:
    """通用时间解析:支持datetime/int/float/str → datetime(带时区)"""
    try:
        if isinstance(value, datetime):
            return value.astimezone()
        elif isinstance(value, (int, float)):
            return datetime.fromtimestamp(value, tz=timezone.utc).astimezone()
        elif isinstance(value, str):
            return parse_datetime_string(value)
        else:
            return None
    except Exception:
        return None


def parse_datetime_string(date_str: str) -> Optional[datetime]:
    """字符串时间解析:支持ISO/常见中文格式/数字提取"""
    try:
        date_str = date_str.strip()

        # 方法1:尝试ISO格式(带冒号时区)
        try:
            s = re.sub(r'([+-]\d{2}):(\d{2})$', r'\1\2', date_str)
            if s != date_str:
                return datetime.fromisoformat(s)
        except ValueError:
            pass

        # 方法2:尝试直接ISO格式
        try:
            return datetime.fromisoformat(date_str)
        except ValueError:
            pass

        # 方法3:尝试常见格式
        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
            "%Y/%m/%d %H:%M:%S",
            "%Y/%m/%d",
            "%Y年%m月%d日 %H:%M:%S",
            "%Y年%m月%d日",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%S.%f%z",
        ]

        for fmt in formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.astimezone()
            except ValueError:
                continue

        # 方法4:尝试提取数字
        numbers = re.findall(r'\d+', date_str)
        if len(numbers) >= 3:
            try:
                year = int(numbers[0])
                month = int(numbers[1])
                day = int(numbers[2])
                hour = int(numbers[3]) if len(numbers) > 3 else 0
                minute = int(numbers[4]) if len(numbers) > 4 else 0
                second = int(numbers[5]) if len(numbers) > 5 else 0
                dt = datetime(year, month, day, hour, minute, second)
                return dt.astimezone()
            except Exception:
                pass

        return None
    except Exception:
        return None


def is_holiday(date_obj) -> Tuple[bool, Optional[str]]:
    """判断日期是否为假日,返回(是否假日, 节日名称) — 小健 2026-05-25 重构拆分

    使用场景:
        time_tools中判断工作日/节假日

    使用示例:
        is_holiday, name = is_holiday(datetime(2024, 1, 1))

    返回数据说明:
        - 返回Tuple[bool, Optional[str]],(True, "元旦")表示是节假日
    """
    try:
        dt = date_obj if hasattr(date_obj, 'month') else None
        if dt is None:
            return (False, None)

        month_day = (dt.month, dt.day)

        holiday = _is_solar_holiday(month_day, dt.year)
        if holiday:
            return (True, holiday)

        holiday = _is_lunar_holiday(dt)
        if holiday:
            return (True, holiday)

        return (False, None)
    except Exception:
        return (False, None)


def _is_solar_holiday(month_day: Tuple[int, int], year: int) -> Optional[str]:
    """判断公历假日 — 小健 2026-05-25 重构拆分

    使用场景:
        is_holiday中判断公历节日(含清明节)

    使用示例:
        holiday = _is_solar_holiday((1, 1), 2024)

    返回数据说明:
        - 返回Optional[str],节日名称或None
    """
    if month_day in SOLAR_HOLIDAYS:
        return SOLAR_HOLIDAYS[month_day]

    qingming = QINGMING_DATES.get(year, (4, 5))
    if month_day == qingming:
        return "清明节"

    return None


def _is_lunar_holiday(date_obj) -> Optional[str]:
    """判断农历假日 — 小健 2026-05-25 重构拆分

    使用场景:
        is_holiday中判断农历节日

    使用示例:
        holiday = _is_lunar_holiday(datetime(2024, 2, 10))

    返回数据说明:
        - 返回Optional[str],节日名称或None
    """
    try:
        from lunarcalendar import Converter
        solar_date = date_obj.date() if hasattr(date_obj, 'date') else date_obj
        lunar = Converter.Solar2Lunar(solar_date)
        lunar_month_day = (lunar.month, lunar.day)
        return LUNAR_HOLIDAYS.get(lunar_month_day)
    except Exception:
        return None


def calc_next_n_workday(start_date, n: int) -> list:
    """计算从start_date往后第N个工作日的日期列表(ISO格式字符串)"""
    try:
        current_date = start_date + timedelta(days=1)
        found_count = 0
        result_dates = []

        while found_count < n:
            weekday = current_date.weekday()
            is_weekend = weekday >= 5
            hol, _ = is_holiday(current_date)
            is_workday = not is_weekend and not hol

            if is_workday:
                result_dates.append(current_date.isoformat())
                found_count += 1

            current_date += timedelta(days=1)

        return result_dates
    except Exception:
        return []


def get_holiday_date_by_name(name: str, year: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """按节日名称查找公历日期 — 小沈 2026-06-14

    支持公历节日(元旦/劳动节/国庆节等)和农历节日(春节/端午节/中秋节等)的名称查询。

    使用场景:
        query_calendar(name=...) 中按名称查找节日日期

    使用示例:
        get_holiday_date_by_name("端午节", 2026) → {"name":"端午节","date":"2026-06-19","type":"lunar"}

    返回数据说明:
        - 返回 Dict[str,Any],包含 name/date/type 三个字段
        - type 为 "solar"(公历) / "lunar"(农历) / "qingming"(清明节特殊)
    """
    if not name or not isinstance(name, str):
        return None
    if year is None:
        year = datetime.now().year

    cleaned = name.strip()
    if cleaned in HOLIDAY_ALIASES:
        cleaned = HOLIDAY_ALIASES[cleaned]

    if cleaned in SOLAR_HOLIDAY_NAMES:
        m, d = SOLAR_HOLIDAY_NAMES[cleaned]
        dt = datetime(year, m, d)
        return {"name": cleaned, "date": dt.strftime("%Y-%m-%d"), "type": "solar",
                "weekday": dt.strftime("%A"), "isoweekday": dt.isoweekday()}

    # 清明节(特殊,每年不同)
    if cleaned == "清明节":
        qingming = QINGMING_DATES.get(year, (4, 5))
        m, d = qingming
        dt = datetime(year, m, d)
        return {"name": "清明节", "date": dt.strftime("%Y-%m-%d"), "type": "qingming",
                "weekday": dt.strftime("%A"), "isoweekday": dt.isoweekday()}

    # 农历节日
    if cleaned in LUNAR_HOLIDAY_NAMES:
        try:
            from lunarcalendar import Lunar, Converter
            m, d = LUNAR_HOLIDAY_NAMES[cleaned]
            lunar = Lunar(year, m, d)
            solar = Converter.Lunar2Solar(lunar)
            solar_date = solar.to_date()
            dt = datetime(solar_date.year, solar_date.month, solar_date.day)
            return {"name": cleaned, "date": dt.strftime("%Y-%m-%d"), "type": "lunar",
                    "weekday": dt.strftime("%A"), "isoweekday": dt.isoweekday()}
        except Exception:
            return None

    # 模糊匹配: 输入包含已知名称(如"端午"→"端午节")
    all_keys = list(SOLAR_HOLIDAY_NAMES.keys()) + list(LUNAR_HOLIDAY_NAMES.keys()) + ["清明节"]
    matches = [k for k in all_keys if cleaned in k]
    if len(matches) == 1:
        return get_holiday_date_by_name(matches[0], year)

    return None


def resolve_timezone(tz_str: str):
    """解析时区字符串:IANA名称(Asia/Shanghai) 或 ±HH:MM格式(+08:00)"""
    import pytz
    try:
        return pytz.timezone(tz_str)
    except Exception:
        if UTC_OFFSET_PATTERN.match(tz_str):
            sign = -1 if tz_str[0] == '-' else 1
            hours = int(tz_str[1:3])
            minutes = int(tz_str[4:6])
            return timezone(timedelta(hours=sign * hours, minutes=sign * minutes))
        raise ValueError(f"无法解析时区: {tz_str}")
