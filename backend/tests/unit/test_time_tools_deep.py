# -*- coding: utf-8 -*-
"""
时间工具深度测试 - test_time_tools_deep.py

覆盖函数：get_current_time, time_format, time_diff, time_is_weekend,
           time_is_holiday, time_compare, time_to_timestamp,
           timestamp_to_time, time_is_workday, time_add

Author: 小健 - 2026-05-06
"""

import time
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

import pytest

try:
    from app.services.tools.meta.time_tools import (
        get_current_time,
        time_format,
        time_diff,
        time_is_weekend,
        time_is_holiday,
        time_compare,
        time_to_timestamp,
        timestamp_to_time,
        time_is_workday,
        time_add,
    )
except ImportError:
    pytestmark = pytest.mark.skip("旧函数/模块已删除-2026-05-18")
    get_current_time = time_format = time_diff = time_is_weekend = None
    time_is_holiday = time_compare = time_to_timestamp = timestamp_to_time = None
    time_is_workday = time_add = None


# ============================================================
# TestGetCurrentTime
# ============================================================
class TestGetCurrentTime:
    """get_current_time 深度测试"""

    def test_returns_success_code(self):
        """正常：返回SUCCESS"""
        result = get_current_time()
        assert result["code"] == "SUCCESS"

    def test_data_has_required_fields(self):
        """正常：data包含所有必需字段"""
        result = get_current_time()
        data = result["data"]
        assert "iso" in data
        assert "timestamp" in data
        assert "format" in data
        assert "timezone" in data
        assert "weekday" in data
        assert "isoweekday" in data

    def test_timestamp_is_int(self):
        """正常：timestamp为整数"""
        result = get_current_time()
        assert isinstance(result["data"]["timestamp"], int)

    def test_isoweekday_range(self):
        """正常：isoweekday在1-7范围"""
        result = get_current_time()
        assert 1 <= result["data"]["isoweekday"] <= 7

    def test_with_timezone_shanghai(self):
        """正常：指定上海时区"""
        result = get_current_time(timezone="Asia/Shanghai")
        assert result["code"] == "SUCCESS"
        assert result["data"]["iso"] is not None

    def test_with_format_pattern(self):
        """正常：自定义格式"""
        result = get_current_time(format="%Y/%m/%d")
        assert result["code"] == "SUCCESS"
        assert "/" in result["data"]["format"]

    def test_default_format_pattern(self):
        """正常：默认格式"""
        result = get_current_time()
        formatted = result["data"]["format"]
        assert "-" in formatted and ":" in formatted

    def test_invalid_timezone_fallback(self):
        """边界：无效时区降级处理"""
        result = get_current_time(timezone="Invalid/Zone")
        assert result["code"] == "SUCCESS"


# ============================================================
# TestTimeFormat
# ============================================================
class TestTimeFormat:
    """time_format 深度测试"""

    def test_format_none_timestamp(self):
        """正常：None使用当前时间"""
        result = time_format(timestamp=None)
        assert result["code"] == "SUCCESS"
        assert "formatted" in result["data"]

    def test_format_unix_timestamp(self):
        """正常：Unix时间戳格式化"""
        ts = 1700000000
        result = time_format(timestamp=ts)
        assert result["code"] == "SUCCESS"

    def test_format_string_timestamp(self):
        """正常：字符串时间戳"""
        result = time_format(timestamp="2026-01-01 12:00:00")
        assert result["code"] == "SUCCESS"

    def test_format_with_pattern(self):
        """正常：自定义格式模式"""
        result = time_format(timestamp=1700000000, pattern="%Y年%m月%d日")
        assert result["code"] == "SUCCESS"
        assert "年" in result["data"]["formatted"]

    def test_format_default_pattern(self):
        """正常：默认格式"""
        result = time_format(timestamp=1700000000)
        assert result["data"]["pattern_used"] == "%Y-%m-%d %H:%M:%S"

    def test_format_float_timestamp(self):
        """正常：浮点时间戳"""
        result = time_format(timestamp=1700000000.5)
        assert result["code"] == "SUCCESS"

    def test_format_unsupported_type(self):
        """边界：不支持的类型"""
        result = time_format(timestamp=[1, 2, 3])
        assert result["code"] == "ERR_TIME_FORMAT"

    def test_format_negative_timestamp(self):
        """边界：负时间戳（1970年前）"""
        result = time_format(timestamp=-1000000)
        assert result["code"] in ("SUCCESS", "ERR_TIME_FORMAT")


# ============================================================
# TestTimeDiff
# ============================================================
class TestTimeDiff:
    """time_diff 深度测试"""

    def test_diff_same_time(self):
        """正常：相同时间差为0"""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        result = time_diff(start=now_str, end=now_str)
        assert result["code"] == "SUCCESS"
        assert result["data"]["seconds"] == 0

    def test_diff_one_hour(self):
        """正常：相差1小时"""
        result = time_diff(start="2026-01-01 10:00:00", end="2026-01-01 11:00:00")
        assert result["code"] == "SUCCESS"
        assert abs(result["data"]["hours"] - 1.0) < 0.01

    def test_diff_one_day(self):
        """正常：相差1天"""
        result = time_diff(start="2026-01-01", end="2026-01-02")
        assert result["code"] == "SUCCESS"
        assert abs(result["data"]["days"] - 1.0) < 0.01

    def test_diff_end_none_uses_now(self):
        """正常：end为None使用当前时间"""
        result = time_diff(start="2020-01-01")
        assert result["code"] == "SUCCESS"
        assert result["data"]["days"] > 0

    def test_diff_unix_timestamp(self):
        """正常：Unix时间戳输入"""
        result = time_diff(start=1700000000, end=1700003600)
        assert result["code"] == "SUCCESS"
        assert abs(result["data"]["hours"] - 1.0) < 0.01

    def test_diff_invalid_start(self):
        """错误：无法解析的开始时间"""
        result = time_diff(start="not_a_date")
        assert result["code"] == "ERR_TIME_DIFF"

    def test_diff_invalid_end(self):
        """错误：无法解析的结束时间"""
        result = time_diff(start="2026-01-01", end="bad_date")
        assert result["code"] == "ERR_TIME_DIFF"

    def test_diff_reversed_order(self):
        """边界：开始>结束，仍返回正值"""
        result = time_diff(start="2026-01-02", end="2026-01-01")
        assert result["code"] == "SUCCESS"
        assert result["data"]["seconds"] > 0


# ============================================================
# TestTimeIsWeekend
# ============================================================
class TestTimeIsWeekend:
    """time_is_weekend 深度测试"""

    def test_saturday_is_weekend(self):
        """正常：周六是周末（2026-05-02是周六）"""
        result = time_is_weekend(date="2026-05-02")
        assert result["code"] == "SUCCESS"
        assert result["data"]["is_weekend"] is True

    def test_sunday_is_weekend(self):
        """正常：周日是周末（2026-05-03是周日）"""
        result = time_is_weekend(date="2026-05-03")
        assert result["code"] == "SUCCESS"
        assert result["data"]["is_weekend"] is True

    def test_monday_is_not_weekend(self):
        """正常：周一不是周末（2026-05-04是周一）"""
        result = time_is_weekend(date="2026-05-04")
        assert result["code"] == "SUCCESS"
        assert result["data"]["is_weekend"] is False

    def test_friday_is_not_weekend(self):
        """正常：周五不是周末（2026-05-01是周五）"""
        result = time_is_weekend(date="2026-05-01")
        assert result["code"] == "SUCCESS"
        assert result["data"]["is_weekend"] is False

    def test_none_uses_now(self):
        """正常：None使用当前日期"""
        result = time_is_weekend(date=None)
        assert result["code"] == "SUCCESS"
        assert isinstance(result["data"]["is_weekend"], bool)

    def test_invalid_date(self):
        """错误：无效日期"""
        result = time_is_weekend(date="invalid")
        assert result["code"] in ("ERR_TIME_IS_WEEKEND", "ERR_TIME_DATE")  # 小沈 2026-05-18: 适配16→7精简委托行为


# ============================================================
# TestTimeIsHoliday
# ============================================================
class TestTimeIsHoliday:
    """time_is_holiday 深度测试"""

    def test_new_year_is_holiday(self):
        """正常：元旦是假日"""
        result = time_is_holiday(date="2026-01-01")
        assert result["code"] == "SUCCESS"
        assert result["data"]["is_holiday"] is True
        assert "元旦" in result["data"]["holiday_name"]

    def test_national_day_is_holiday(self):
        """正常：国庆节是假日"""
        result = time_is_holiday(date="2026-10-01")
        assert result["code"] == "SUCCESS"
        assert result["data"]["is_holiday"] is True

    def test_labor_day_is_holiday(self):
        """正常：劳动节是假日"""
        result = time_is_holiday(date="2026-05-01")
        assert result["code"] == "SUCCESS"
        assert result["data"]["is_holiday"] is True

    def test_normal_day_not_holiday(self):
        """正常：普通日期不是假日"""
        result = time_is_holiday(date="2026-03-15")
        assert result["code"] == "SUCCESS"
        assert result["data"]["is_holiday"] is False

    def test_none_uses_now(self):
        """正常：None使用当前日期"""
        result = time_is_holiday(date=None)
        assert result["code"] == "SUCCESS"

    def test_invalid_date(self):
        """错误：无效日期"""
        result = time_is_holiday(date="not_a_date")
        assert result["code"] in ("ERR_TIME_IS_HOLIDAY", "ERR_TIME_DATE")  # 小沈 2026-05-18: 适配16→7精简委托行为

    def test_children_day(self):
        """正常：儿童节"""
        result = time_is_holiday(date="2026-06-01")
        assert result["code"] == "SUCCESS"
        assert result["data"]["is_holiday"] is True

    def test_christmas(self):
        """正常：圣诞节"""
        result = time_is_holiday(date="2026-12-25")
        assert result["code"] == "SUCCESS"
        assert result["data"]["is_holiday"] is True


# ============================================================
# TestTimeCompare
# ============================================================
class TestTimeCompare:
    """time_compare 深度测试"""

    def test_time1_greater(self):
        """正常：time1 > time2"""
        result = time_compare("2026-01-02", "2026-01-01")
        assert result["code"] == "SUCCESS"
        assert result["data"]["result"] == "gt"

    def test_time1_less(self):
        """正常：time1 < time2"""
        result = time_compare("2026-01-01", "2026-01-02")
        assert result["code"] == "SUCCESS"
        assert result["data"]["result"] == "lt"

    def test_time_equal(self):
        """正常：时间相等"""
        result = time_compare("2026-01-01 12:00:00", "2026-01-01 12:00:00")
        assert result["code"] == "SUCCESS"
        assert result["data"]["result"] == "eq"

    def test_unit_hours(self):
        """正常：小时单位"""
        result = time_compare("2026-01-01 12:00:00", "2026-01-01 10:00:00", unit="hours")
        assert result["code"] == "SUCCESS"
        assert abs(result["data"].get("diff_seconds", result["data"].get("diff_value", 0)) / 3600.0 - 2.0) < 0.01  # 小沈 2026-05-18: 适配16→7精简委托行为

    def test_unit_minutes(self):
        """正常：分钟单位"""
        result = time_compare("2026-01-01 12:30:00", "2026-01-01 12:00:00", unit="minutes")
        assert result["code"] == "SUCCESS"
        assert abs(result["data"].get("diff_seconds", result["data"].get("diff_value", 0)) / 60.0 - 30.0) < 0.01  # 小沈 2026-05-18: 适配16→7精简委托行为

    def test_unit_seconds(self):
        """正常：秒单位"""
        result = time_compare("2026-01-01 12:00:30", "2026-01-01 12:00:00", unit="seconds")
        assert result["code"] == "SUCCESS"
        assert abs(result["data"].get("diff_seconds", result["data"].get("diff_value", 0)) - 30.0) < 0.01  # 小沈 2026-05-18: 适配16→7精简委托行为

    def test_invalid_time1(self):
        """错误：无效time1"""
        result = time_compare("bad", "2026-01-01")
        assert result["code"] in ("ERR_TIME_COMPARE", "ERR_TIME_DIFF")  # 小沈 2026-05-18: 适配16→7精简委托行为

    def test_invalid_time2(self):
        """错误：无效time2"""
        result = time_compare("2026-01-01", "bad")
        assert result["code"] in ("ERR_TIME_COMPARE", "ERR_TIME_DIFF")  # 小沈 2026-05-18: 适配16→7精简委托行为

    def test_unix_timestamps(self):
        """正常：Unix时间戳比较"""
        result = time_compare(1700003600, 1700000000)
        assert result["code"] == "SUCCESS"
        assert result["data"]["result"] == "gt"


# ============================================================
# TestTimeToTimestamp
# ============================================================
class TestTimeToTimestamp:
    """time_to_timestamp 深度测试"""

    def test_string_time(self):
        """正常：字符串时间转时间戳"""
        result = time_to_timestamp("2026-01-01 00:00:00")
        assert result["code"] == "SUCCESS"
        assert isinstance(result["data"], int)

    def test_unit_seconds(self):
        """正常：秒单位"""
        result = time_to_timestamp("2026-01-01 00:00:00", unit="seconds")
        assert result["code"] == "SUCCESS"

    def test_unit_milliseconds(self):
        """正常：毫秒单位"""
        result = time_to_timestamp("2026-01-01 00:00:00", unit="milliseconds")
        assert result["code"] == "SUCCESS"
        assert result["data"] > 1000000000000

    def test_unit_microseconds(self):
        """正常：微秒单位"""
        result = time_to_timestamp("2026-01-01 00:00:00", unit="microseconds")
        assert result["code"] == "SUCCESS"
        assert result["data"] > 1000000000000000

    def test_invalid_time(self):
        """错误：无效时间"""
        result = time_to_timestamp("not_time")
        assert result["code"] == "ERR_TIME_TO_TIMESTAMP"

    def test_unix_timestamp_input(self):
        """正常：Unix时间戳输入"""
        result = time_to_timestamp(1700000000)
        assert result["code"] == "SUCCESS"


# ============================================================
# TestTimestampToTime
# ============================================================
class TestTimestampToTime:
    """timestamp_to_time 深度测试"""

    def test_normal_conversion(self):
        """正常：正常转换"""
        result = timestamp_to_time(1700000000)
        assert result["code"] == "SUCCESS"
        assert "datetime" in result["data"]
        assert "isoformat" in result["data"]

    def test_zero_timestamp(self):
        """边界：时间戳0（Unix纪元）"""
        result = timestamp_to_time(0)
        assert result["code"] == "SUCCESS"

    def test_float_timestamp(self):
        """正常：浮点时间戳"""
        result = timestamp_to_time(1700000000.5)
        assert result["code"] == "SUCCESS"

    def test_invalid_timestamp_string(self):
        """错误：非数字字符串"""
        result = timestamp_to_time("not_a_number")
        assert result["code"] == "ERR_TIMESTAMP_TO_TIME"

    def test_negative_timestamp(self):
        """边界：负时间戳"""
        result = timestamp_to_time(-1000000)
        assert result["code"] in ("SUCCESS", "ERR_TIMESTAMP_TO_TIME")

    def test_target_tz(self):
        """正常：指定目标时区"""
        result = timestamp_to_time(1700000000, target_tz="Asia/Shanghai")
        assert result["code"] == "SUCCESS"


# ============================================================
# TestTimeIsWorkday
# ============================================================
class TestTimeIsWorkday:
    """time_is_workday 深度测试"""

    def test_monday_is_workday(self):
        """正常：周二是工作日（2026-05-05是周二，非假日）"""
        result = time_is_workday(date="2026-05-05")
        assert result["code"] == "SUCCESS"
        assert (result["data"]["is_workday"] if isinstance(result["data"], dict) else result["data"]) is True  # 小沈 2026-05-18: 适配16→7精简委托行为

    def test_saturday_is_not_workday(self):
        """正常：周六不是工作日（2026-05-02是周六）"""
        result = time_is_workday(date="2026-05-02")
        assert result["code"] == "SUCCESS"
        assert (result["data"]["is_workday"] if isinstance(result["data"], dict) else result["data"]) is False  # 小沈 2026-05-18: 适配16→7精简委托行为

    def test_sunday_is_not_workday(self):
        """正常：周日不是工作日（2026-05-03是周日）"""
        result = time_is_workday(date="2026-05-03")
        assert result["code"] == "SUCCESS"
        assert (result["data"]["is_workday"] if isinstance(result["data"], dict) else result["data"]) is False  # 小沈 2026-05-18: 适配16→7精简委托行为

    def test_holiday_not_workday(self):
        """正常：假日不是工作日（2026-01-01元旦，周四）"""
        result = time_is_workday(date="2026-01-01")
        assert result["code"] == "SUCCESS"
        assert (result["data"]["is_workday"] if isinstance(result["data"], dict) else result["data"]) is False  # 小沈 2026-05-18: 适配16→7精简委托行为

    def test_none_uses_now(self):
        """正常：None使用当前日期"""
        result = time_is_workday(date=None)
        assert result["code"] == "SUCCESS"

    def test_invalid_date(self):
        """错误：无效日期"""
        result = time_is_workday(date="bad_date")
        assert result["code"] in ("ERR_TIME_IS_WORKDAY", "ERR_TIME_DATE")  # 小沈 2026-05-18: 适配16→7精简委托行为

    def test_friday_is_workday(self):
        """正常：周五是工作日（2026-05-01是劳动节假日，选05-08周五）"""
        result = time_is_workday(date="2026-05-08")
        assert result["code"] == "SUCCESS"
        assert (result["data"]["is_workday"] if isinstance(result["data"], dict) else result["data"]) is True  # 小沈 2026-05-18: 适配16→7精简委托行为


# ============================================================
# TestTimeAdd
# ============================================================
class TestTimeAdd:
    """time_add 深度测试"""

    def test_add_one_day(self):
        """正常：加1天"""
        result = time_add(delta=1, start="2026-01-01", unit="days")
        assert result["code"] == "SUCCESS"
        assert result["data"]["result_time"].startswith("2026-01-02")

    def test_add_one_hour(self):
        """正常：加1小时"""
        result = time_add(delta=1, start="2026-01-01 10:00:00", unit="hours")
        assert result["code"] == "SUCCESS"
        assert result["data"]["unit_used"] == "hours"
        assert result["data"]["delta_used"] == 1

    def test_add_one_minute(self):
        """正常：加1分钟"""
        result = time_add(delta=1, start="2026-01-01 10:00:00", unit="minutes")
        assert result["code"] == "SUCCESS"
        assert result["data"]["unit_used"] == "minutes"

    def test_add_one_second(self):
        """正常：加1秒"""
        result = time_add(delta=1, start="2026-01-01 10:00:00", unit="seconds")
        assert result["code"] == "SUCCESS"
        assert result["data"]["unit_used"] == "seconds"

    def test_add_months(self):
        """正常：加月份（按30天）"""
        result = time_add(delta=1, start="2026-01-01", unit="months")
        assert result["code"] == "SUCCESS"

    def test_subtract_days(self):
        """正常：减天数（负delta）"""
        result = time_add(delta=-1, start="2026-01-02", unit="days")
        assert result["code"] == "SUCCESS"
        assert result["data"]["result_time"].startswith("2026-01-01")

    def test_start_none_uses_now(self):
        """正常：start为None使用当前时间"""
        result = time_add(delta=1, start=None, unit="days")
        assert result["code"] == "SUCCESS"

    def test_invalid_start(self):
        """错误：无效起始时间"""
        result = time_add(delta=1, start="bad_date", unit="days")
        assert result["code"] == "ERR_TIME_ADD"

    def test_unsupported_unit(self):
        """错误：不支持的单位"""
        result = time_add(delta=1, start="2026-01-01", unit="years")
        assert result["code"] == "ERR_TIME_ADD"

    def test_add_zero_delta(self):
        """边界：delta为0"""
        result = time_add(delta=0, start="2026-01-01 12:00:00", unit="days")
        assert result["code"] == "SUCCESS"
        assert "2026-01-01" in result["data"]["result_time"]

    def test_add_large_delta(self):
        """边界：大delta值"""
        result = time_add(delta=365, start="2026-01-01", unit="days")
        assert result["code"] == "SUCCESS"
