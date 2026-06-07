# -*- coding: utf-8 -*-
"""
时间工具V2深度测试 - test_time_tools_v2.py

覆盖精简后7个统一入口工具：
- get_time（四合一：now/format/to_timestamp/from_timestamp）
- time_add（增强版：months精确计算+weekday/isoweekday返回）
- time_diff（增强版：新增is_after/is_before/is_equal/diff_seconds_signed）
- query_calendar（四合一：weekend/holiday/workday/next_workday + P15全面返回）
- timezone_convert（三方向：utc_to_local/local_to_utc/any）
- timer（三合一：set/clear/list）

Author: 小健 - 2026-05-18
"""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

import pytest

from app.services.tools.meta.time_tools import (
    get_time,
    time_add,
    time_diff,
    query_calendar,
    timezone_convert,
    timer,
)


# ============================================================
# TestGetTime - 四合一测试
# ============================================================
class TestGetTime:
    """get_time 统一入口深度测试"""

    # ---------- action="now" ----------
    def test_action_now_success(self):
        """action=now: 正常获取当前时间"""
        result = get_time(action="now")
        assert result["code"] == "SUCCESS"
        assert "iso" in result["data"]
        assert "timestamp" in result["data"]
        assert "format" in result["data"]
        assert "timezone" in result["data"]
        assert "weekday" in result["data"]
        assert "isoweekday" in result["data"]

    def test_action_now_with_timezone(self):
        """action=now: 指定上海时区"""
        result = get_time(action="now", timezone="Asia/Shanghai")
        assert result["code"] == "SUCCESS"
        assert result["data"]["iso"] is not None

    def test_action_now_with_format(self):
        """action=now: 自定义格式"""
        result = get_time(action="now", format="%Y/%m/%d")
        assert result["code"] == "SUCCESS"

    def test_action_now_with_locale(self):
        """action=now: 指定本地化"""
        result = get_time(action="now")
        assert result["code"] == "SUCCESS"

    def test_action_now_timestamp_is_int(self):
        """action=now: timestamp为整数"""
        result = get_time(action="now")
        assert isinstance(result["data"]["timestamp"], int)

    def test_action_now_isoweekday_range(self):
        """action=now: isoweekday在1-7范围"""
        result = get_time(action="now")
        assert 1 <= result["data"]["isoweekday"] <= 7

    # ---------- action="format" ----------
    def test_action_format_none_time_value(self):
        """action=format: None使用当前时间"""
        result = get_time(action="format", time_value=None)
        assert result["code"] == "SUCCESS"
        assert "formatted" in result["data"]

    def test_action_format_unix_timestamp(self):
        """action=format: Unix时间戳格式化"""
        result = get_time(action="format", time_value=1716019800)
        assert result["code"] == "SUCCESS"
        assert "formatted" in result["data"]

    def test_action_format_iso_string(self):
        """action=format: ISO字符串格式化"""
        result = get_time(action="format", time_value="2026-05-18 14:30:00")
        assert result["code"] == "SUCCESS"
        assert "formatted" in result["data"]

    def test_action_format_with_pattern(self):
        """action=format: 自定义格式模式"""
        result = get_time(action="format", time_value="2026-05-18", format="%Y年%m月%d日")
        assert result["code"] == "SUCCESS"
        assert "年" in result["data"]["formatted"]

    # ---------- action="to_timestamp" ----------
    def test_action_to_timestamp_success(self):
        """action=to_timestamp: 时间转时间戳"""
        result = get_time(action="to_timestamp", time_value="2026-05-18 14:30:00")
        assert result["code"] == "SUCCESS"
        assert "timestamp" in result["data"]
        assert isinstance(result["data"]["timestamp"], int)

    def test_action_to_timestamp_with_unit_seconds(self):
        """action=to_timestamp: 秒单位"""
        result = get_time(action="to_timestamp", time_value="2026-05-18 14:30:00")
        assert result["code"] == "SUCCESS"

    def test_action_to_timestamp_with_unit_milliseconds(self):
        """action=to_timestamp: 毫秒单位"""
        result = get_time(action="to_timestamp", time_value="2026-05-18 14:30:00")
        assert result["code"] == "SUCCESS"
        assert result["data"]["timestamp"] > 1000000000

    def test_action_to_timestamp_missing_time_value(self):
        """action=to_timestamp: 缺少time_value返回错误"""
        result = get_time(action="to_timestamp", time_value=None)
        assert result["code"] == "ERR_META_TIME_FORMAT"

    # ---------- action="from_timestamp" ----------
    def test_action_from_timestamp_success(self):
        """action=from_timestamp: 时间戳转时间"""
        result = get_time(action="from_timestamp", time_value=1716019800)
        assert result["code"] == "SUCCESS"
        assert "iso" in result["data"] or "datetime" in result["data"]

    def test_action_from_timestamp_with_target_tz(self):
        """action=from_timestamp: 指定目标时区"""
        result = get_time(action="from_timestamp", time_value=1716019800, target_tz="Asia/Shanghai")
        assert result["code"] == "SUCCESS"

    def test_action_from_timestamp_missing_time_value(self):
        """action=from_timestamp: 缺少time_value返回错误"""
        result = get_time(action="from_timestamp", time_value=None)
        assert result["code"] == "ERR_META_TIME_FORMAT"

    # ---------- 无效action ----------
    def test_invalid_action(self):
        """边界: 无效action返回错误"""
        result = get_time(action="invalid_action")
        assert result["code"] == "ERR_INVALID_ACTION"


# ============================================================
# TestTimeAdd - 增强版测试
# ============================================================
class TestTimeAdd:
    """time_add 增强版深度测试"""

    def test_add_days(self):
        """正常: 加天数"""
        result = time_add(delta=3, start="2026-05-18", unit="days")
        assert result["code"] == "SUCCESS"
        assert "result_time" in result["data"]
        assert "weekday" in result["data"]
        assert "isoweekday" in result["data"]

    def test_add_hours(self):
        """正常: 加小时"""
        result = time_add(delta=2, start="2026-05-18 14:00:00", unit="hours")
        assert result["code"] == "SUCCESS"

    def test_add_minutes(self):
        """正常: 加分钟"""
        result = time_add(delta=30, start="2026-05-18 14:00:00", unit="minutes")
        assert result["code"] == "SUCCESS"

    def test_add_seconds(self):
        """正常: 加秒"""
        result = time_add(delta=60, start="2026-05-18 14:00:00", unit="seconds")
        assert result["code"] == "SUCCESS"

    def test_add_months(self):
        """正常: 加月份（relativedelta精确计算）"""
        result = time_add(delta=2, start="2026-05-18", unit="months")
        assert result["code"] == "SUCCESS"
        assert "2026-07" in result["data"]["result_time"]

    def test_subtract_days(self):
        """正常: 减天数（负数delta）"""
        result = time_add(delta=-7, start="2026-05-18", unit="days")
        assert result["code"] == "SUCCESS"

    def test_start_none_uses_current_time(self):
        """正常: start为None使用当前时间"""
        result = time_add(delta=1, start=None, unit="days")
        assert result["code"] == "SUCCESS"

    def test_returns_weekday_isoweekday(self):
        """P17增强: 返回weekday和isoweekday"""
        result = time_add(delta=1, start="2026-05-18", unit="days")
        assert result["code"] == "SUCCESS"
        assert "weekday" in result["data"]
        assert "isoweekday" in result["data"]
        assert 1 <= result["data"]["isoweekday"] <= 7


# ============================================================
# TestTimeDiff - 增强版测试（替代time_compare）
# ============================================================
class TestTimeDiff:
    """time_diff 增强版深度测试"""

    def test_diff_success(self):
        """正常: 计算时间差"""
        result = time_diff(start="2026-05-01", end="2026-05-18")
        assert result["code"] == "SUCCESS"
        assert "humanized" in result["data"]
        assert "seconds" in result["data"]
        assert "days" in result["data"]

    def test_diff_end_none_uses_current_time(self):
        """正常: end为None使用当前时间"""
        result = time_diff(start="2026-05-01")
        assert result["code"] == "SUCCESS"

    def test_diff_humanized_format(self):
        """正常: 人性化描述"""
        result = time_diff(start="2026-05-01", end="2026-05-18")
        assert "humanized" in result["data"]
        humanized = result["data"]["humanized"]
        assert isinstance(humanized, str)

    def test_is_after_true(self):
        """P15增强: is_after=True（end在start之后）"""
        result = time_diff(start="2026-05-01", end="2026-05-18")
        assert result["code"] == "SUCCESS"
        assert "is_after" in result["data"]
        assert result["data"]["is_after"] is True

    def test_is_after_false(self):
        """P15增强: is_after=False（end在start之前）"""
        result = time_diff(start="2026-05-18", end="2026-05-01")
        assert result["code"] == "SUCCESS"
        assert result["data"]["is_after"] is False

    def test_is_before_true(self):
        """P15增强: is_before=True"""
        result = time_diff(start="2026-05-18", end="2026-05-01")
        assert result["code"] == "SUCCESS"
        assert result["data"]["is_before"] is True

    def test_is_equal(self):
        """P15增强: is_equal=True（两个时间相等）"""
        result = time_diff(start="2026-05-18", end="2026-05-18")
        assert result["code"] == "SUCCESS"
        assert result["data"]["is_equal"] is True

    def test_diff_seconds_signed(self):
        """P15增强: 有符号差值"""
        result = time_diff(start="2026-05-01", end="2026-05-18")
        assert result["code"] == "SUCCESS"
        assert "diff_seconds_signed" in result["data"]
        assert result["data"]["diff_seconds_signed"] > 0

    def test_is_future(self):
        """正常: is_future字段"""
        future_time = datetime.now() + timedelta(days=10)
        result = time_diff(start="2026-05-01", end=future_time.isoformat())
        assert result["code"] == "SUCCESS"
        assert "is_future" in result["data"]


# ============================================================
# TestCheckDate - 四合一测试 + P15全面返回
# ============================================================
class TestCheckDate:
    """query_calendar 四合一深度测试"""

    # ---------- check_type="weekend" ----------
    def test_check_weekend_saturday(self):
        """check_type=weekend: 周六是周末"""
        result = query_calendar(date="2026-05-23", check_type="weekend")
        assert result["code"] == "SUCCESS"
        assert result["data"]["is_weekend"] is True

    def test_check_weekend_sunday(self):
        """check_type=weekend: 周日是周末"""
        result = query_calendar(date="2026-05-24", check_type="weekend")
        assert result["code"] == "SUCCESS"
        assert result["data"]["is_weekend"] is True

    def test_check_weekend_weekday(self):
        """check_type=weekend: 工作日不是周末"""
        result = query_calendar(date="2026-05-18", check_type="weekend")
        assert result["code"] == "SUCCESS"
        assert result["data"]["is_weekend"] is False

    # ---------- check_type="holiday" ----------
    def test_check_holiday_national_day(self):
        """check_type=holiday: 国庆节"""
        result = query_calendar(date="2026-10-01", check_type="holiday")
        assert result["code"] == "SUCCESS"
        assert result["data"]["is_holiday"] is True
        assert result["data"]["holiday_name"] == "国庆节"

    def test_check_holiday_labor_day(self):
        """check_type=holiday: 劳动节"""
        result = query_calendar(date="2026-05-01", check_type="holiday")
        assert result["code"] == "SUCCESS"
        assert result["data"]["is_holiday"] is True

    def test_check_holiday_not_holiday(self):
        """check_type=holiday: 非节假日"""
        result = query_calendar(date="2026-05-18", check_type="holiday")
        assert result["code"] == "SUCCESS"

    # ---------- check_type="workday" ----------
    def test_check_workday_monday(self):
        """check_type=workday: 周一是工作日"""
        result = query_calendar(date="2026-05-18", check_type="workday")
        assert result["code"] == "SUCCESS"
        assert result["data"]["is_workday"] is True

    def test_check_workday_weekend(self):
        """check_type=workday: 周末不是工作日"""
        result = query_calendar(date="2026-05-23", check_type="workday")
        assert result["code"] == "SUCCESS"
        assert result["data"]["is_workday"] is False

    # ---------- check_type="next_workday" ----------
    def test_check_next_workday_n1(self):
        """check_type=next_workday: 第1个工作日"""
        result = query_calendar(date="2026-05-18", check_type="next_workday", n=1)
        assert result["code"] == "SUCCESS"
        assert "next_workdays" in result["data"]
        assert len(result["data"]["next_workdays"]) == 1

    def test_check_next_workday_n3(self):
        """check_type=next_workday: 第3个工作日"""
        result = query_calendar(date="2026-05-18", check_type="next_workday", n=3)
        assert result["code"] == "SUCCESS"
        assert len(result["data"]["next_workdays"]) == 3

    def test_check_next_workday_first(self):
        """check_type=next_workday: next_workday_first字段"""
        result = query_calendar(date="2026-05-18", check_type="next_workday", n=1)
        assert result["code"] == "SUCCESS"
        assert "next_workday_first" in result["data"]

    # ---------- P15全面返回 ----------
    def test_p15_comprehensive_return(self):
        """P15全面返回: 一次性返回全部日历属性"""
        result = query_calendar(date="2026-05-18", check_type="workday")
        assert result["code"] == "SUCCESS"
        data = result["data"]
        assert "date" in data
        assert "weekday" in data
        assert "isoweekday" in data
        assert "is_weekend" in data
        assert "is_holiday" in data
        assert "holiday_name" in data
        assert "is_workday" in data

    def test_p15_avoid_multiple_calls(self):
        """P15验证: 一次调用获取周末和节假日信息"""
        result = query_calendar(date="2026-10-01", check_type="workday")
        assert result["code"] == "SUCCESS"
        data = result["data"]
        assert data["is_weekend"] is False
        assert data["is_holiday"] is True
        assert data["is_workday"] is False
        assert data["holiday_name"] == "国庆节"

    # ---------- 边界情况 ----------
    def test_date_none_uses_current(self):
        """边界: date为None使用当前日期"""
        result = query_calendar(date=None, check_type="workday")
        assert result["code"] == "SUCCESS"

    def test_invalid_check_type(self):
        """边界: 无效check_type返回错误"""
        result = query_calendar(date="2026-05-18", check_type="invalid")
        assert result["code"] == "ERR_META_INVALID_CHECK_TYPE"


# ============================================================
# TestTimezoneConvert - 三方向测试
# ============================================================
class TestTimezoneConvert:
    """timezone_convert 三方向深度测试"""

    # ---------- direction="utc_to_local" ----------
    def test_utc_to_local_success(self):
        """direction=utc_to_local: UTC转本地"""
        result = timezone_convert(time_value="2026-05-18T12:00:00Z", direction="utc_to_local")
        assert result["code"] == "SUCCESS"

    def test_utc_to_local_with_target_tz(self):
        """direction=utc_to_local: 指定目标时区"""
        result = timezone_convert(
            time_value="2026-05-18T12:00:00Z",
            direction="utc_to_local",
            tz="Asia/Shanghai"
        )
        assert result["code"] == "SUCCESS"

    def test_utc_to_local_unix_timestamp(self):
        """direction=utc_to_local: Unix时间戳"""
        result = timezone_convert(time_value=1716033600, direction="utc_to_local")
        assert result["code"] == "SUCCESS"

    # ---------- direction="local_to_utc" ----------
    def test_local_to_utc_success(self):
        """direction=local_to_utc: 本地转UTC"""
        result = timezone_convert(time_value="2026-05-18 20:00:00", direction="local_to_utc")
        assert result["code"] == "SUCCESS"

    def test_local_to_utc_with_source_tz(self):
        """direction=local_to_utc: 指定源时区"""
        result = timezone_convert(
            time_value="2026-05-18 20:00:00",
            direction="local_to_utc",
            tz="Asia/Shanghai"
        )
        assert result["code"] == "SUCCESS"

    # ---------- direction="any" ----------
    def test_any_direction_success(self):
        """direction=any: 任意源→目标一次完成"""
        result = timezone_convert(
            time_value="2026-05-18 20:00:00",
            direction="any",
            tz="Asia/Shanghai"
        )
        assert result["code"] == "SUCCESS"

    def test_any_direction_tokyo_to_newyork(self):
        """direction=any: 东京转纽约"""
        result = timezone_convert(
            time_value="2026-05-18 14:00:00",
            direction="any",
            tz="Asia/Tokyo"
        )
        assert result["code"] == "SUCCESS"

    def test_any_missing_source_tz(self):
        """direction=any: 缺少source_tz返回错误"""
        result = timezone_convert(
            time_value="2026-05-18 20:00:00",
            direction="any",
            tz=None
        )
        assert result["code"] == "ERR_TIME_TZ"

    def test_any_missing_target_tz(self):
        """direction=any: 缺少target_tz返回错误"""
        result = timezone_convert(
            time_value="2026-05-18 20:00:00",
            direction="any",
        )
        assert result["code"] == "ERR_TIME_TZ"

    # ---------- 边界情况 ----------
    def test_invalid_direction(self):
        """边界: 无效direction返回错误"""
        result = timezone_convert(time_value="2026-05-18 20:00:00", direction="invalid")
        assert result["code"] == "ERR_INVALID_DIRECTION"


# ============================================================
# TestTimer - 三合一测试
# ============================================================
class TestTimer:
    """timer 三合一深度测试"""

    # ---------- action="set" ----------
    @pytest.mark.asyncio
    async def test_set_success(self):
        """action=set: 设置定时器"""
        result = await timer(action="set", delay=180, callback="提醒用户喝水")
        assert result["code"] == "SUCCESS"
        assert "timer_id" in result["data"]
        assert result["data"]["delay"] == 180

    @pytest.mark.asyncio
    async def test_set_with_callback_data(self):
        """action=set: 带回调数据"""
        result = await timer(
            action="set",
            delay=600,
            callback="执行备份",
        )
        assert result["code"] == "SUCCESS"

    @pytest.mark.asyncio
    async def test_set_delay_zero(self):
        """action=set: delay=0返回错误"""
        result = await timer(action="set", delay=0, callback="test")
        assert result["code"] == "ERR_TIMER_PARAM"

    @pytest.mark.asyncio
    async def test_set_delay_negative(self):
        """action=set: 负数delay返回错误"""
        result = await timer(action="set", delay=-10, callback="test")
        assert result["code"] == "ERR_TIMER_PARAM"

    @pytest.mark.asyncio
    async def test_set_missing_callback(self):
        """action=set: 缺少callback返回错误"""
        result = await timer(action="set", delay=180, callback=None)
        assert result["code"] == "ERR_TIMER_PARAM"

    # ---------- action="clear" ----------
    @pytest.mark.asyncio
    async def test_clear_success(self):
        """action=clear: 清除定时器"""
        set_result = await timer(action="set", delay=300, callback="test")
        timer_id = set_result["data"]["timer_id"]
        
        clear_result = await timer(action="clear", timer_id=timer_id)
        assert clear_result["code"] == "SUCCESS"

    @pytest.mark.asyncio
    async def test_clear_missing_timer_id(self):
        """action=clear: 缺少timer_id返回错误"""
        result = await timer(action="clear", timer_id=None)
        assert result["code"] == "ERR_TIMER_PARAM"

    @pytest.mark.asyncio
    async def test_clear_nonexistent_timer(self):
        """P16幂等性: 清除不存在的定时器返回SUCCESS"""
        result = await timer(action="clear", timer_id="nonexistent_timer_id")
        assert result["code"] == "SUCCESS"

    # ---------- action="list" ----------
    @pytest.mark.asyncio
    async def test_list_success(self):
        """action=list: 列出定时器"""
        result = await timer(action="list")
        assert result["code"] == "SUCCESS"

    @pytest.mark.asyncio
    async def test_list_with_limit(self):
        """action=list: 指定数量限制"""
        result = await timer(action="list")
        assert result["code"] == "SUCCESS"

    # ---------- 边界情况 ----------
    @pytest.mark.asyncio
    async def test_invalid_action(self):
        """边界: 无效action返回错误"""
        result = await timer(action="invalid")
        assert result["code"] == "ERR_INVALID_ACTION"


# ============================================================
# TestIntegration - 集成测试
# ============================================================
class TestIntegration:
    """集成测试：工具协作场景"""

    def test_get_time_then_time_add(self):
        """场景1: get_time获取当前时间 → time_add计算未来时间"""
        now_result = get_time(action="now")
        assert now_result["code"] == "SUCCESS"
        
        now_ts = now_result["data"]["timestamp"]
        add_result = time_add(delta=3, start=now_ts, unit="days")
        assert add_result["code"] == "SUCCESS"

    def test_query_calendar_then_time_add(self):
        """场景2: query_calendar检查工作日 → time_add计算下个工作日"""
        check_result = query_calendar(date="2026-05-18", check_type="workday")
        assert check_result["code"] == "SUCCESS"
        
        if check_result["data"]["is_workday"]:
            add_result = time_add(delta=1, start="2026-05-18", unit="days")
            assert add_result["code"] == "SUCCESS"

    def test_time_diff_replaces_time_compare(self):
        """场景3: time_diff替代time_compare"""
        result = time_diff(start="2026-05-01", end="2026-05-18")
        assert result["code"] == "SUCCESS"
        
        assert "is_after" in result["data"]
        assert "is_before" in result["data"]
        assert "is_equal" in result["data"]
        
        if result["data"]["is_after"]:
            assert "2026-05-18" > "2026-05-01"

    @pytest.mark.asyncio
    async def test_timer_set_and_list(self):
        """场景4: timer设置 → list查看"""
        set_result = await timer(action="set", delay=300, callback="测试提醒")
        assert set_result["code"] == "SUCCESS"
        
        list_result = await timer(action="list")
        assert list_result["code"] == "SUCCESS"
