"""
meta类工具集成测试 - 基于运行中的服务
小健 2026-05-21
"""
import pytest
from tests.integration._helper import ToolClient, assert_success, assert_error, assert_data_key, assert_data_not_empty

TOOL = ToolClient()


class TestGetTime:
    """get_time 工具多场景测试"""

    def test_now(self):
        r = TOOL.call("get_time", {"action": "now"})
        assert_success(r)
        assert_data_key(r, "iso")
        assert_data_key(r, "timestamp")
        assert_data_key(r, "format")
        assert_data_key(r, "timezone")
        data = r["data"]
        assert isinstance(data["timestamp"], (int, float))
        assert "+08" in data["timezone"] or "+0800" in data["timezone"]

    def test_now_with_timezone(self):
        r = TOOL.call("get_time", {"action": "now", "timezone": "Asia/Shanghai"})
        assert_success(r)
        assert_data_key(r, "iso")

    def test_now_with_utc(self):
        r = TOOL.call("get_time", {"action": "now", "timezone": "UTC"})
        assert_success(r)
        assert_data_key(r, "iso")

    def test_format_custom(self):
        r = TOOL.call("get_time", {"action": "format", "format": "%Y-%m-%d"})
        assert_success(r)
        assert_data_key(r, "formatted")

    def test_from_timestamp(self):
        r = TOOL.call("get_time", {"action": "from_timestamp", "time_value": 1700000000})
        assert_success(r)
        assert_data_key(r, "iso")
        assert_data_key(r, "timestamp")

    def test_from_timestamp_zero(self):
        r = TOOL.call("get_time", {"action": "from_timestamp", "time_value": 0})
        assert_success(r)
        assert_data_key(r, "iso")

    def test_from_timestamp_with_timezone(self):
        r = TOOL.call("get_time", {
            "action": "from_timestamp",
            "time_value": 1700000000,
            "target_tz": "America/New_York",
        })
        assert_success(r)
        assert_data_key(r, "iso")

    def test_from_timestamp_target_tz_preserved(self):
        """验证from_timestamp不会丢失默认target_tz (Bug #5曾在此出现)"""
        r = TOOL.call("get_time", {"action": "from_timestamp", "time_value": 1700000000})
        assert_success(r)
        data = r["data"]
        assert data.get("iso") is not None, "from_timestamp不应返回空iso (Bug #5)"
        assert data.get("timezone") is not None, "from_timestamp不应返回空timezone"

    def test_from_timestamp_data_key_consistency(self):
        """验证from_timestamp与now返回的核心data key一致 (Bug #10已修复)"""
        r_now = TOOL.call("get_time", {"action": "now"})
        r_ts = TOOL.call("get_time", {"action": "from_timestamp", "time_value": 1700000000})
        now_keys = set(r_now.get("data", {}).keys())
        ts_keys = set(r_ts.get("data", {}).keys())
        # from_timestamp缺少weekday/isoweekday/locale是有意的（时间戳转换不需要）
        core_keys = {"iso", "timestamp", "timezone", "format"}
        assert core_keys.issubset(now_keys), f"now缺少核心字段: {now_keys - core_keys}"
        assert core_keys.issubset(ts_keys), f"from_timestamp缺少核心字段: {ts_keys - core_keys}"
        assert now_keys >= ts_keys, f"from_timestamp的keys是now的子集: ts={ts_keys}, now={now_keys}"

    def test_invalid_action(self):
        r = TOOL.call("get_time", {"action": "invalid_action_xyz"})
        assert_error(r)


class TestTimeAdd:
    """time_add 工具多场景测试"""

    def test_add_days(self):
        r = TOOL.call("time_add", {"delta": 1, "unit": "days"})
        assert_success(r)
        assert_data_not_empty(r)

    def test_add_hours(self):
        r = TOOL.call("time_add", {"delta": 24, "unit": "hours"})
        assert_success(r)

    def test_add_minutes(self):
        r = TOOL.call("time_add", {"delta": 60, "unit": "minutes"})
        assert_success(r)

    def test_add_seconds(self):
        r = TOOL.call("time_add", {"delta": 3600, "unit": "seconds"})
        assert_success(r)

    def test_subtract_days(self):
        r = TOOL.call("time_add", {"delta": -7, "unit": "days"})
        assert_success(r)

    def test_add_with_start(self):
        r = TOOL.call("time_add", {"delta": 1, "unit": "days", "start": "2026-01-01"})
        assert_success(r)
        data = r["data"]
        result_str = str(data)
        assert "2026-01-02" in result_str, f"2026-01-01 + 1天 应包含2026-01-02, 实际: {data}"

    def test_add_months(self):
        r = TOOL.call("time_add", {"delta": 1, "unit": "months"})
        assert_success(r)


class TestTimeDiff:
    """time_diff 工具多场景测试"""

    def test_diff_two_dates(self):
        r = TOOL.call("time_diff", {"start": "2026-01-01", "end": "2026-01-02"})
        assert_success(r)
        assert_data_not_empty(r)

    def test_diff_same_date(self):
        r = TOOL.call("time_diff", {"start": "2026-01-01", "end": "2026-01-01"})
        assert_success(r)

    def test_diff_negative(self):
        r = TOOL.call("time_diff", {"start": "2026-01-02", "end": "2026-01-01"})
        assert_success(r)

    def test_diff_timestamps(self):
        r = TOOL.call("time_diff", {"start": 1700000000, "end": 1700086400})
        assert_success(r)

    def test_diff_no_end(self):
        r = TOOL.call("time_diff", {"start": "2026-01-01"})
        assert_success(r)


class TestQueryCalendar:
    """query_calendar 工具多场景测试"""

    def test_weekend_check(self):
        r = TOOL.call("query_calendar", {"date": "2026-05-23", "check_type": "weekend"})
        assert_success(r)
        assert_data_not_empty(r)

    def test_workday_check(self):
        r = TOOL.call("query_calendar", {"date": "2026-05-21", "check_type": "workday"})
        assert_success(r)

    def test_holiday_check(self):
        r = TOOL.call("query_calendar", {"date": "2026-01-01", "check_type": "holiday"})
        assert_success(r)

    def test_next_workday(self):
        r = TOOL.call("query_calendar", {"date": "2026-05-22", "check_type": "next_workday"})
        assert_success(r)

    def test_no_date_defaults_today(self):
        r = TOOL.call("query_calendar", {"check_type": "weekend"})
        assert_success(r)


class TestTimezoneConvert:
    """timezone_convert 工具多场景测试"""

    def test_utc_to_local(self):
        r = TOOL.call("timezone_convert", {
            "time_value": "2026-01-01T00:00:00",
            "direction": "utc_to_local",
        })
        assert_success(r)

    def test_local_to_utc(self):
        r = TOOL.call("timezone_convert", {
            "time_value": "2026-01-01T08:00:00",
            "direction": "local_to_utc",
        })
        assert_success(r)

    def test_any_direction(self):
        r = TOOL.call("timezone_convert", {
            "time_value": "2026-01-01T12:00:00",
            "direction": "any",
            "tz": "America/New_York",
        })
        assert_success(r)


class TestTimer:
    """timer 工具多场景测试"""

    def test_set_timer(self):
        r = TOOL.call("timer", {"action": "set", "delay": 5, "callback": "test_timer_callback"})
        assert_success(r)

    def test_list_timers(self):
        TOOL.call("timer", {"action": "set", "delay": 10, "callback": "list_test"})
        r = TOOL.call("timer", {"action": "list"})
        assert_success(r)

    def test_clear_timer(self):
        set_r = TOOL.call("timer", {"action": "set", "delay": 10, "callback": "clear_test"})
        timer_id = None
        data = set_r.get("data", {})
        if isinstance(data, dict):
            timer_id = data.get("timer_id")
        if timer_id:
            r = TOOL.call("timer", {"action": "clear", "timer_id": timer_id})
            assert_success(r)


class TestToolHelp:
    """tool_help 工具多场景测试"""

    def test_help_for_known_tool(self):
        r = TOOL.call("tool_help", {"tool_name": "get_time"})
        assert_success(r)

    def test_help_for_unknown_tool(self):
        r = TOOL.call("tool_help", {"tool_name": "nonexistent_tool_xyz"})
        assert_error(r)


class TestToolSearch:
    """tool_search 工具多场景测试"""

    def test_search_time(self):
        r = TOOL.call("tool_search", {"query": "时间"})
        assert_success(r)

    def test_search_file(self):
        r = TOOL.call("tool_search", {"query": "文件"})
        assert_success(r)

    def test_search_no_match(self):
        r = TOOL.call("tool_search", {"query": "xyz_nonexistent_query_12345"})
        assert_success(r)
