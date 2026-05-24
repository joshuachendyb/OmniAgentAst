# -*- coding: utf-8 -*-
"""
日期时间通用解析与计算Helper（不暴露给LLM）

【创建时间】2026-05-18 小沈
【P13提取】从 time_tools.py 提取5个内部函数

函数清单：
- parse_datetime_any: 通用时间解析（datetime/int/float/str → datetime）
- parse_datetime_string: 字符串时间解析（ISO/中文/数字提取）
- is_holiday: 日期是否为假日，返回(bool, holiday_name)
- calc_next_n_workday: 计算下N个工作日
- resolve_timezone: 解析时区字符串
"""

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Tuple


def parse_datetime_any(value: Any) -> Optional[datetime]:
    """通用时间解析：支持datetime/int/float/str → datetime（带时区）"""
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
    """字符串时间解析：支持ISO/常见中文格式/数字提取"""
    try:
        date_str = date_str.strip()

        # 方法1：尝试ISO格式（带冒号时区）
        try:
            s = re.sub(r'([+-]\d{2}):(\d{2})$', r'\1\2', date_str)
            if s != date_str:
                return datetime.fromisoformat(s)
        except ValueError:
            pass

        # 方法2：尝试直接ISO格式
        try:
            return datetime.fromisoformat(date_str)
        except ValueError:
            pass

        # 方法3：尝试常见格式
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

        # 方法4：尝试提取数字
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
    """判断日期是否为假日，返回(是否假日, 节日名称)

    支持14个公历节日 + 9个农历节日 + 清明节查表（2024-2035）
    """
    try:
        dt = date_obj if hasattr(date_obj, 'month') else None
        if dt is None:
            return (False, None)

        month_day = (dt.month, dt.day)
        year = dt.year

        solar_holidays = {
            (1, 1): "元旦",
            (2, 14): "情人节",
            (3, 8): "妇女节",
            (3, 12): "植树节",
            (4, 1): "愚人节",
            (5, 1): "劳动节",
            (5, 4): "青年节",
            (6, 1): "儿童节",
            (7, 1): "建党节",
            (8, 1): "建军节",
            (9, 10): "教师节",
            (10, 1): "国庆节",
            (12, 24): "平安夜",
            (12, 25): "圣诞节",
        }

        qingming_dates = {
            2024: (4, 4), 2025: (4, 4), 2026: (4, 5),
            2027: (4, 5), 2028: (4, 4), 2029: (4, 5), 2030: (4, 5),
            2031: (4, 5), 2032: (4, 4), 2033: (4, 4), 2034: (4, 5), 2035: (4, 5),
        }
        qingming = qingming_dates.get(year, (4, 5))

        if month_day in solar_holidays:
            return (True, solar_holidays[month_day])
        if month_day == qingming:
            return (True, "清明节")

        try:
            from lunarcalendar import Converter
            solar_date = dt.date() if hasattr(dt, 'date') else dt
            lunar = Converter.Solar2Lunar(solar_date)
            lunar_month_day = (lunar.month, lunar.day)
            lunar_holidays = {
                (1, 1): "春节（农历正月初一）",
                (1, 15): "元宵节（农历正月十五）",
                (5, 5): "端午节（农历五月初五）",
                (7, 7): "七夕节（农历七月初七）",
                (7, 15): "中元节（农历七月十五）",
                (8, 15): "中秋节（农历八月十五）",
                (9, 9): "重阳节（农历九月初九）",
                (12, 8): "腊八节（农历十二月初八）",
                (12, 30): "除夕（农历十二月三十）",
            }
            if lunar_month_day in lunar_holidays:
                return (True, lunar_holidays[lunar_month_day])
        except Exception:
            pass

        return (False, None)
    except Exception:
        return (False, None)


def calc_next_n_workday(start_date, n: int) -> list:
    """计算从start_date往后第N个工作日的日期列表（ISO格式字符串）"""
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


def resolve_timezone(tz_str: str):
    """解析时区字符串：IANA名称(Asia/Shanghai) 或 ±HH:MM格式(+08:00)"""
    import pytz
    try:
        return pytz.timezone(tz_str)
    except Exception:
        if re.match(r'^[+-]\d{2}:\d{2}$', tz_str):
            sign = -1 if tz_str[0] == '-' else 1
            hours = int(tz_str[1:3])
            minutes = int(tz_str[4:6])
            return timezone(timedelta(hours=sign * hours, minutes=sign * minutes))
        raise ValueError(f"无法解析时区: {tz_str}")
