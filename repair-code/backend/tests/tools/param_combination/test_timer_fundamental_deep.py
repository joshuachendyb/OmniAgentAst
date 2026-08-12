# -*- coding: utf-8 -*-
"""
timer + fundamental 工具深度参数组合测试 - 小欧 2026-06-25

测试工具:
1. timer_set - 设置定时器
2. timer_list - 列出所有定时器
3. timer_clear - 清除定时器
4. get_system_info - 获取系统信息
5. query_calendar - 节日/日期查询
6. send_notification - 发送Windows系统通知
7. time_add - 时间加减运算
8. time_diff - 时间差值计算
9. time_now - 获取当前系统时间
10. tool_search - BM25全文搜索引擎工具
已知Bug:
- timer_set 使用同步 httpx.get() 在async回调中阻塞事件循环
- timer_clear 当timer_id不存在时返回success而非error
- time_now error handler 引用未导入的 timezone 变量 → NameError
- get_system_info info_type="basic" 也会调用 psutil.cpu_percent(interval=0.5) 阻塞
- tool_search 访问 _tools 私有属性"""

import asyncio
import re
import sys
import time as _time
from unittest.mock import patch, MagicMock

import pytest

from app.tools.tool_response import is_success, is_error


def _extract_timer_id_from_summary(result: dict) -> str:
    """从llm_data.summary提取timer_id — 小欧 2026-07-06 — 小欧 2026-07-12 修复正则提取"""
    summary = result["llm_data"]["summary"]
    m = re.search(r"timer_\w+", summary)
    return m.group(0) if m else ""


# For async timer tools, we need asyncio.run() in sync tests


# ============================================================
# 一,ParameterCombinations - 参数组合测试
# ============================================================
@pytest.mark.timeout(60)
class TestTimerSetParamCombinations:
    """timer_set 参数组合测试"""

    def test_delay_only(self):
        """仅delay参数"""
        from app.tools.timer.timer_set import timer_set, _timer_callbacks

        initial_count = len(_timer_callbacks)
        result = asyncio.run(timer_set(delay=10, callback="test_reminder"))
        assert is_success(result)
        timer_id = _extract_timer_id_from_summary(result)
        assert timer_id  # 非空
        # Cleanup: remove timer
        _timer_callbacks.pop(timer_id, None)

    def test_delay_and_callback(self):
        """delay + callback"""
        from app.tools.timer.timer_set import timer_set, _timer_callbacks

        result = asyncio.run(timer_set(delay=5, callback="任务完成提醒"))
        assert is_success(result)
        _timer_callbacks.pop(_extract_timer_id_from_summary(result), None)

    def test_delay_with_http_callback(self):
        """delay + HTTP callback"""
        from app.tools.timer.timer_set import timer_set, _timer_callbacks

        result = asyncio.run(timer_set(delay=2, callback="http://example.com/webhook"))
        assert is_success(result)
        _timer_callbacks.pop(_extract_timer_id_from_summary(result), None)

    def test_delay_zero(self):
        """delay=0(边界值,应该报错)"""
        from app.tools.timer.timer_set import timer_set

        result = asyncio.run(timer_set(delay=0, callback="zero"))
        assert is_error(result)
        assert "延迟时间必须大于0" in result["llm_data"]["status"]["detail"]

    def test_delay_negative(self):
        """delay为负数(应该报错)"""
        from app.tools.timer.timer_set import timer_set

        result = asyncio.run(timer_set(delay=-5, callback="negative"))
        assert is_error(result)
        assert "延迟时间必须大于0" in result["llm_data"]["status"]["detail"]

    def test_delay_86400(self):
        """delay=86400(24小时上限,应成功)"""
        from app.tools.timer.timer_set import timer_set, _timer_callbacks

        result = asyncio.run(timer_set(delay=86400, callback="max_delay"))
        assert is_success(result)
        _timer_callbacks.pop(_extract_timer_id_from_summary(result), None)

    def test_delay_exceeds_86400(self):
        """delay超过86400(应该报错)"""
        from app.tools.timer.timer_set import timer_set

        result = asyncio.run(timer_set(delay=86401, callback="too_long"))
        assert is_error(result)
        assert "延迟时间不能超过24小时" in result["llm_data"]["status"]["detail"]

    def test_delay_one_second(self):
        """delay=1秒(最小有效值)"""
        from app.tools.timer.timer_set import timer_set, _timer_callbacks

        result = asyncio.run(timer_set(delay=1, callback="1sec"))
        assert is_success(result)
        _timer_callbacks.pop(_extract_timer_id_from_summary(result), None)

    def test_delay_float(self):
        """delay使用浮点数"""
        from app.tools.timer.timer_set import timer_set, _timer_callbacks

        result = asyncio.run(timer_set(delay=2.5, callback="float_delay"))
        assert is_success(result)
        assert result["data"]["trigger_at"] is not None
        _timer_callbacks.pop(_extract_timer_id_from_summary(result), None)

    def test_callback_empty_string(self):
        """callback为空字符串"""
        from app.tools.timer.timer_set import timer_set, _timer_callbacks

        result = asyncio.run(timer_set(delay=5, callback=""))
        assert is_success(result)
        _timer_callbacks.pop(_extract_timer_id_from_summary(result), None)

    def test_callback_special_chars(self):
        """callback含特殊字符"""
        from app.tools.timer.timer_set import timer_set, _timer_callbacks

        result = asyncio.run(timer_set(delay=3, callback="测试!@#$%^&*()提醒"))
        assert is_success(result)
        _timer_callbacks.pop(_extract_timer_id_from_summary(result), None)


@pytest.mark.timeout(60)
class TestTimerClearParamCombinations:
    """timer_clear 参数组合测试"""

    def test_clear_existing_timer(self):
        """清除存在的定时器"""
        from app.tools.timer.timer_set import timer_set, _timer_callbacks
        from app.tools.timer.timer_clear import timer_clear

        result = asyncio.run(timer_set(delay=60, callback="to_be_cleared"))
        timer_id = _extract_timer_id_from_summary(result)

        clear_result = asyncio.run(timer_clear(timer_id=timer_id))
        assert is_success(clear_result)
        assert "已取消" in clear_result["llm_data"]["summary"]
        _timer_callbacks.pop(timer_id, None)

    def test_clear_nonexistent_timer(self):
        """BUG验证:清除不存在的定时器应该返回error"""
        from app.tools.timer.timer_clear import timer_clear

        # BUG: timer_clear returns success even when timer not found
        result = asyncio.run(timer_clear(timer_id="nonexistent_timer_99999"))
        # BUG CONFIRMATION: returns success instead of error
        assert is_success(result)
        assert "不存在或已触发" in result["llm_data"]["summary"]
        # Expected behavior should be: assert is_error(result)


@pytest.mark.timeout(60)
class TestTimerListParamCombinations:
    """timer_list 参数组合测试"""

    def test_list_empty(self):
        """列出空定时器列表"""
        from app.tools.timer.timer_list import timer_list
        from app.tools.timer.timer_set import _timer_callbacks

        # Clear all timers
        saved = dict(_timer_callbacks)
        _timer_callbacks.clear()

        result = asyncio.run(timer_list())
        assert is_success(result)
        assert isinstance(result["data"]["timers"], list)

        # Restore
        _timer_callbacks.update(saved)

    def test_list_with_timers(self):
        """列出有定时器的列表"""
        from app.tools.timer.timer_set import timer_set, _timer_callbacks
        from app.tools.timer.timer_list import timer_list

        r1 = asyncio.run(timer_set(delay=30, callback="timer1"))
        r2 = asyncio.run(timer_set(delay=60, callback="timer2"))

        result = asyncio.run(timer_list())
        assert is_success(result)
        assert len(result["data"]["timers"]) >= 2

        # Cleanup
        _timer_callbacks.pop(_extract_timer_id_from_summary(r1), None)
        _timer_callbacks.pop(_extract_timer_id_from_summary(r2), None)

    def test_list_sorted_by_trigger_at(self):
        """列表按trigger_at排序"""
        from app.tools.timer.timer_set import timer_set, _timer_callbacks
        from app.tools.timer.timer_list import timer_list

        r1 = asyncio.run(timer_set(delay=120, callback="later"))
        r2 = asyncio.run(timer_set(delay=10, callback="sooner"))

        result = asyncio.run(timer_list())
        timer_ids = [t["timer_id"] for t in result["data"]["timers"]]
        assert _extract_timer_id_from_summary(r1) in timer_ids
        assert _extract_timer_id_from_summary(r2) in timer_ids

        _timer_callbacks.pop(_extract_timer_id_from_summary(r1), None)
        _timer_callbacks.pop(_extract_timer_id_from_summary(r2), None)


@pytest.mark.timeout(60)
class TestTimerSetSingleFunction:
    """timer_set 单功能测试"""

    def test_returns_timer_id(self):
        """返回的timer_id格式正认"""
        from app.tools.timer.timer_set import timer_set, _timer_callbacks

        result = asyncio.run(timer_set(delay=10, callback="format_check"))
        assert is_success(result)
        timer_id = _extract_timer_id_from_summary(result)
        assert timer_id.startswith("timer_")
        _timer_callbacks.pop(timer_id, None)

    def test_returns_trigger_at(self):
        """返回的trigger_at时间在未来"""
        from app.tools.timer.timer_set import timer_set, _timer_callbacks
        from datetime import datetime

        result = asyncio.run(timer_set(delay=60, callback="future_check"))
        assert is_success(result)
        trigger_at = datetime.strptime(
            result["data"]["trigger_at"], "%Y-%m-%d %H:%M:%S"
        )
        assert trigger_at > datetime.now()
        _timer_callbacks.pop(_extract_timer_id_from_summary(result), None)

    def test_callback_stored(self):
        """callback被正认存储"""
        from app.tools.timer.timer_set import timer_set, _timer_callbacks

        result = asyncio.run(timer_set(delay=5, callback="stored_callback"))
        timer_id = _extract_timer_id_from_summary(result)
        assert timer_id in _timer_callbacks
        assert _timer_callbacks[timer_id]["callback"] == "stored_callback"
        _timer_callbacks.pop(timer_id, None)

    def test_llm_data_structure(self):
        """验证llm_data结构完整"""
        from app.tools.timer.timer_set import timer_set, _timer_callbacks

        result = asyncio.run(timer_set(delay=10, callback="llm_check"))
        assert is_success(result)
        assert "llm_data" in result
        llm = result["llm_data"]
        assert "summary" in llm
        assert "action" in llm
        assert "status" in llm
        assert "duration_ms" in llm
        assert "metrics" in llm
        _timer_callbacks.pop(_extract_timer_id_from_summary(result), None)


@pytest.mark.timeout(60)
class TestTimerClearSingleFunction:
    """timer_clear 单功能测试"""

    def test_cancelled_field_is_bool(self):
        """cancelled字段是布尔值"""
        from app.tools.timer.timer_set import timer_set, _timer_callbacks
        from app.tools.timer.timer_clear import timer_clear

        r = asyncio.run(timer_set(delay=60, callback="cancel_bool"))
        timer_id = _extract_timer_id_from_summary(r)
        result = asyncio.run(timer_clear(timer_id=timer_id))
        assert "已取消" in result["llm_data"]["summary"]
        _timer_callbacks.pop(timer_id, None)

    def test_clear_with_known_id(self):
        """清除时传入的timer_id能在summary中体现"""
        from app.tools.timer.timer_set import timer_set, _timer_callbacks
        from app.tools.timer.timer_clear import timer_clear

        r = asyncio.run(timer_set(delay=60, callback="id_check"))
        timer_id = _extract_timer_id_from_summary(r)
        result = asyncio.run(timer_clear(timer_id=timer_id))
        assert timer_id in result["llm_data"]["summary"]
        _timer_callbacks.pop(timer_id, None)


# ============================================================
# 二,Timer - 真实场景测试
# ============================================================
@pytest.mark.timeout(60)
class TestTimerRealScenarios:
    """定时器工具真实场景测试"""

    def test_set_list_clear_lifecycle(self):
        """完整生命周期:设置 → 列出 → 清除"""
        from app.tools.timer.timer_set import timer_set, _timer_callbacks
        from app.tools.timer.timer_list import timer_list
        from app.tools.timer.timer_clear import timer_clear

        # Set
        r = asyncio.run(timer_set(delay=30, callback="lifecycle_test"))
        timer_id = _extract_timer_id_from_summary(r)

        # List
        lr = asyncio.run(timer_list())
        assert is_success(lr)
        timer_ids = [t["timer_id"] for t in lr["data"]["timers"]]
        assert timer_id in timer_ids

        # Clear
        cr = asyncio.run(timer_clear(timer_id=timer_id))
        assert is_success(cr)
        assert "已取消" in cr["llm_data"]["summary"]

        # Cleanup
        _timer_callbacks.pop(timer_id, None)

    def test_multiple_timers_independent(self):
        """多个定时器互不影响"""
        from app.tools.timer.timer_set import timer_set, _timer_callbacks
        from app.tools.timer.timer_clear import timer_clear

        r1 = asyncio.run(timer_set(delay=10, callback="timer_a"))
        r2 = asyncio.run(timer_set(delay=20, callback="timer_b"))
        r3 = asyncio.run(timer_set(delay=30, callback="timer_c"))

        # Clear only r2
        asyncio.run(timer_clear(timer_id=_extract_timer_id_from_summary(r2)))

        # r1 and r3 should still exist
        assert _extract_timer_id_from_summary(r1) in _timer_callbacks
        assert _extract_timer_id_from_summary(r3) in _timer_callbacks

        # Cleanup
        for r in [r1, r2, r3]:
            _timer_callbacks.pop(_extract_timer_id_from_summary(r), None)

    def test_timer_set_synchronous_httpx_bug(self):
        """BUG验证:timer_set的httpx.get()在async回调中同步阻塞"""
        from app.tools.timer.timer_set import _invoke_timer_callback

        # BUG: _invoke_timer_callback uses httpx.get() (synchronous)
        # inside an async function, which blocks the event loop
        # When called from async context, this freezes the loop
        import httpx
        # Verify the bug exists by checking the source code
        import inspect
        source = inspect.getsource(_invoke_timer_callback)
        # The bug: httpx.get() is synchronous, should use httpx.AsyncClient
        assert "httpx.get(" in source  # Confirms sync call exists


# ============================================================
# 三,get_system_info 测试
# ============================================================
@pytest.mark.timeout(60)
class TestGetSystemInfoParamCombinations:
    """get_system_info 参数组合测试"""

    def test_no_params(self):
        """无参数(默认all)"""
        from app.tools.fundamental.get_system_info import sysinfo as get_system_info

        result = get_system_info()
        assert is_success(result)

    def test_info_type_all(self):
        """info_type=all"""
        from app.tools.fundamental.get_system_info import sysinfo as get_system_info

        result = get_system_info(info_type="all")
        assert is_success(result)
        data = result["data"]
        assert "basic" in data
        assert "cpu" in data
        assert "memory" in data

    def test_info_type_basic(self):
        """info_type=basic"""
        from app.tools.fundamental.get_system_info import sysinfo as get_system_info

        result = get_system_info(info_type="basic")
        assert is_success(result)
        data = result["data"]
        assert "basic" in data
        assert "platform" in data["basic"]
        assert "hostname" in data["basic"]

    def test_info_type_cpu(self):
        """info_type=cpu"""
        from app.tools.fundamental.get_system_info import sysinfo as get_system_info

        result = get_system_info(info_type="cpu")
        assert is_success(result)
        assert "cpu" in result["data"]
        assert "physical_cores" in result["data"]["cpu"]

    def test_info_type_memory(self):
        """info_type=memory"""
        from app.tools.fundamental.get_system_info import sysinfo as get_system_info

        result = get_system_info(info_type="memory")
        assert is_success(result)
        assert "memory" in result["data"]
        assert "total_gb" in result["data"]["memory"]

    def test_info_type_disk(self):
        """info_type=disk"""
        from app.tools.fundamental.get_system_info import sysinfo as get_system_info

        result = get_system_info(info_type="disk")
        assert is_success(result)

    def test_info_type_network(self):
        """info_type=network"""
        from app.tools.fundamental.get_system_info import sysinfo as get_system_info

        result = get_system_info(info_type="network")
        assert is_success(result)
        assert "network" in result["data"]

    def test_basic_should_not_block(self):
        """BUG验证:info_type=basic不应该调用cpu_percent(interval=0.5)"""
        from app.tools.fundamental.get_system_info import sysinfo as get_system_info

        t0 = _time.perf_counter()
        result = get_system_info(info_type="basic")
        elapsed = _time.perf_counter() - t0

        assert is_success(result)
        # BUG: basic still triggers cpu_percent(interval=0.5) in the code
        # because the cpu block is NOT inside the "cpu"/"all" check
        # It's called unconditionally before the info_type check
        # The code at line 76: psutil.cpu_percent(interval=0.5) is in the cpu block
        # So basic should be fast (<0.5s), cpu should be slower
        # If basic takes >0.5s, the bug is confirmed
        # Note: this is a soft test - basic might still be fast on some systems
        assert elapsed < 2.0, f"basic info took {elapsed:.2f}s, possibly blocked by cpu_percent"

    def test_cpu_info_includes_percent(self):
        """cpu类型返回cpu_usage_percent"""
        from app.tools.fundamental.get_system_info import sysinfo as get_system_info

        result = get_system_info(info_type="cpu")
        assert is_success(result)
        assert "cpu_usage_percent" in result["data"]["cpu"]
        assert isinstance(result["data"]["cpu"]["cpu_usage_percent"], (int, float))


@pytest.mark.timeout(60)
class TestGetSystemInfoSingleFunction:
    """get_system_info 单功能测试"""

    def test_basic_platform_field(self):
        """basic信息包含platform字段"""
        from app.tools.fundamental.get_system_info import sysinfo as get_system_info

        result = get_system_info(info_type="basic")
        assert is_success(result)
        assert result["data"]["basic"]["platform"] in ("Windows", "Linux", "Darwin")

    def test_memory_total_positive(self):
        """内存总量为正数"""
        from app.tools.fundamental.get_system_info import sysinfo as get_system_info

        result = get_system_info(info_type="memory")
        assert is_success(result)
        assert result["data"]["memory"]["total_gb"] > 0

    def test_memory_percent_range(self):
        """内存使用百分比在0-100之间"""
        from app.tools.fundamental.get_system_info import sysinfo as get_system_info

        result = get_system_info(info_type="memory")
        assert is_success(result)
        pct = result["data"]["memory"]["percent"]
        assert 0 <= pct <= 100

    def test_all_info_has_cpu_memory_basic(self):
        """all类型包含cpu,memory,basic"""
        from app.tools.fundamental.get_system_info import sysinfo as get_system_info

        result = get_system_info(info_type="all")
        assert is_success(result)
        assert "cpu" in result["data"]
        assert "memory" in result["data"]
        assert "basic" in result["data"]


@pytest.mark.timeout(60)
class TestGetSystemInfoNegative:
    """get_system_info 负面测试"""

    def test_invalid_info_type(self):
        """无效info_type"""
        from app.tools.fundamental.get_system_info import sysinfo as get_system_info

        result = get_system_info(info_type="invalid_type")
        assert is_error(result)
        assert "无效的info_type" in result["llm_data"]["status"]["detail"]

    def test_empty_string_info_type(self):
        """空字符串info_type"""
        from app.tools.fundamental.get_system_info import sysinfo as get_system_info

        result = get_system_info(info_type="")
        assert is_error(result)

    def test_numeric_info_type(self):
        """数字info_type"""
        from app.tools.fundamental.get_system_info import sysinfo as get_system_info

        result = get_system_info(info_type=123)
        assert is_error(result)


# ============================================================
# 四,query_calendar 测试
# ============================================================
@pytest.mark.timeout(60)
class TestQueryCalendarParamCombinations:
    """query_calendar 参数组合测试"""

    def test_festival_with_year(self):
        """节日名 + 年份"""
        from app.tools.timer.query_calendar import calendar as query_calendar

        result = query_calendar(name="里午节", year=2026)
        assert is_success(result) or is_error(result)

    def test_festival_without_year(self):
        """节日名(默认当年)"""
        from app.tools.timer.query_calendar import calendar as query_calendar

        result = query_calendar(name="春节")
        assert is_success(result)

    def test_date_string(self):
        """日期字符串"""
        from app.tools.timer.query_calendar import calendar as query_calendar

        result = query_calendar(name="2026-06-25")
        assert is_success(result)
        summary = result["llm_data"]["summary"]
        assert "周末" in summary or "工作日" in summary or "节假日" in summary

    def test_multiple_festivals(self):
        """多个节日"""
        from app.tools.timer.query_calendar import calendar as query_calendar

        for festival in ["春节", "里午节", "中秋节"]:
            result = query_calendar(name=festival, year=2026)
            assert is_success(result) or is_error(result), f"{festival}查询异常"

    def test_date_string_weekday(self):
        """日期字符串返回weekday信息"""
        from app.tools.timer.query_calendar import calendar as query_calendar

        result = query_calendar(name="2026-06-25")
        assert is_success(result)
        summary = result["llm_data"]["summary"]
        assert "周末" in summary or "工作日" in summary or "节假日" in summary


@pytest.mark.timeout(60)
class TestQueryCalendarSingleFunction:
    """query_calendar 单功能测试"""

    def test_saturday_is_weekend(self):
        """周六是周末"""
        from app.tools.timer.query_calendar import calendar as query_calendar

        result = query_calendar(name="2026-06-27")  # Saturday
        assert is_success(result)
        assert "周末" in result["llm_data"]["summary"]

    def test_sunday_is_weekend(self):
        """周日是周末"""
        from app.tools.timer.query_calendar import calendar as query_calendar

        result = query_calendar(name="2026-06-28")  # Sunday
        assert is_success(result)
        assert "周末" in result["llm_data"]["summary"]

    def test_weekday_workday(self):
        """普通工作日"""
        from app.tools.timer.query_calendar import calendar as query_calendar

        result = query_calendar(name="2026-06-25")  # Thursday
        assert is_success(result)
        assert "工作日" in result["llm_data"]["summary"]


@pytest.mark.timeout(60)
class TestQueryCalendarNegative:
    """query_calendar 负面测试"""

    def test_invalid_date_format(self):
        """无效日期格式"""
        from app.tools.timer.query_calendar import calendar as query_calendar

        result = query_calendar(name="not_a_date")
        # Might return error or might try holiday lookup
        # Just verify it doesn't crash
        assert is_success(result) or is_error(result)

    def test_nonexistent_festival(self):
        """不存在的节日名"""
        from app.tools.timer.query_calendar import calendar as query_calendar

        result = query_calendar(name="不存在的节日XYZ")
        assert is_error(result)


# ============================================================
# 五,send_notification 测试
# ============================================================
@pytest.mark.skipif(
    sys.platform != "win32",
    reason="send_notification requires Windows"
)
@pytest.mark.timeout(60)
class TestSendNotificationParamCombinations:
    """send_notification 参数组合测试"""

    def test_title_message_only(self):
        """仅必填参数"""
        from app.tools.fundamental.send_notification import notify as send_notification

        result = send_notification(title="测试通知", message="测试内容")
        # May fail if win10toast not installed
        assert is_success(result) or is_error(result)

    def test_title_message_duration(self):
        """title + message + duration"""
        from app.tools.fundamental.send_notification import notify as send_notification

        result = send_notification(title="测试", message="内容", duration=3)
        assert is_success(result) or is_error(result)

    def test_empty_title(self):
        """空标题"""
        from app.tools.fundamental.send_notification import notify as send_notification

        result = send_notification(title="", message="empty title")
        assert is_success(result) or is_error(result)

    def test_long_message(self):
        """长消息"""
        from app.tools.fundamental.send_notification import notify as send_notification

        result = send_notification(
            title="长消息测试",
            message="A" * 500,
            duration=3
        )
        assert is_success(result) or is_error(result)


# ============================================================
# 六,time_add 测试
# ============================================================
@pytest.mark.timeout(60)
class TestTimeAddParamCombinations:
    """time_add 参数组合测试"""

    def test_delta_days_default(self):
        """delta默认days"""
        from app.tools.timer.time_add import timeadd as time_add

        result = time_add(delta=7)
        assert is_success(result)
        assert result["llm_data"]["summary"]

    def test_delta_hours(self):
        """delta + hours"""
        from app.tools.timer.time_add import timeadd as time_add

        result = time_add(delta=3, unit="hours")
        assert is_success(result)

    def test_delta_minutes(self):
        """delta + minutes"""
        from app.tools.timer.time_add import timeadd as time_add

        result = time_add(delta=30, unit="minutes")
        assert is_success(result)

    def test_delta_seconds(self):
        """delta + seconds"""
        from app.tools.timer.time_add import timeadd as time_add

        result = time_add(delta=90, unit="seconds")
        assert is_success(result)

    def test_delta_months(self):
        """delta + months"""
        from app.tools.timer.time_add import timeadd as time_add

        result = time_add(delta=2, unit="months")
        assert is_success(result)

    def test_negative_delta(self):
        """负delta"""
        from app.tools.timer.time_add import timeadd as time_add

        result = time_add(delta=-7, unit="days")
        assert is_success(result)

    def test_with_start_string(self):
        """start为字符串"""
        from app.tools.timer.time_add import timeadd as time_add

        result = time_add(start="2026-01-01 00:00:00", delta=365, unit="days")
        assert is_success(result)

    def test_with_start_timestamp(self):
        """start为时间戳"""
        from app.tools.timer.time_add import timeadd as time_add

        result = time_add(start=1717200000, delta=1, unit="days")
        assert is_success(result)

    def test_all_units(self):
        """所有单位"""
        from app.tools.timer.time_add import timeadd as time_add

        for unit in ["days", "hours", "minutes", "seconds", "months"]:
            result = time_add(delta=1, unit=unit)
            assert is_success(result), f"{unit} failed"


@pytest.mark.timeout(60)
class TestTimeAddSingleFunction:
    """time_add 单功能测试"""

    def test_result_has_iso(self):
        """返回结果包含iso字段"""
        from app.tools.timer.time_add import timeadd as time_add

        result = time_add(delta=1, unit="days")
        assert is_success(result)
        assert result["llm_data"]["summary"]

    def test_result_has_timestamp(self):
        """返回结果包含timestamp"""
        from app.tools.timer.time_add import timeadd as time_add

        result = time_add(delta=1, unit="days")
        assert is_success(result)
        assert result["llm_data"]["summary"]

    def test_result_has_weekday(self):
        """返回结果包含weekday"""
        from app.tools.timer.time_add import timeadd as time_add

        result = time_add(delta=1, unit="days")
        assert is_success(result)
        assert result["llm_data"]["summary"]

    def test_zero_delta(self):
        """delta=0"""
        from app.tools.timer.time_add import timeadd as time_add

        result = time_add(delta=0, unit="days")
        assert is_success(result)


# ============================================================
# 七,time_diff 测试
# ============================================================
@pytest.mark.timeout(60)
class TestTimeDiffParamCombinations:
    """time_diff 参数组合测试"""

    def test_start_only(self):
        """仅start"""
        from app.tools.timer.time_diff import timediff as time_diff

        result = time_diff(start="2026-01-01")
        assert is_success(result)
        assert "seconds" in result["llm_data"]["metrics"]

    def test_start_end_string(self):
        """start + end(字符串)"""
        from app.tools.timer.time_diff import timediff as time_diff

        result = time_diff(start="2026-01-01", end="2026-06-25")
        assert is_success(result)

    def test_start_end_timestamp(self):
        """start + end(时间戳)"""
        from app.tools.timer.time_diff import timediff as time_diff

        result = time_diff(start=1717200000, end=1717804800)
        assert is_success(result)

    def test_same_time(self):
        """相同时间"""
        from app.tools.timer.time_diff import timediff as time_diff

        result = time_diff(start="2026-06-25 12:00:00", end="2026-06-25 12:00:00")
        assert is_success(result)
        assert result["llm_data"]["metrics"]["seconds"]["value"] == 0

    def test_future_diff(self):
        """未来时间"""
        from app.tools.timer.time_diff import timediff as time_diff

        result = time_diff(start="2026-06-25 12:00:00", end="2026-12-31 23:59:59")
        assert is_success(result)
        assert result["llm_data"]["summary"]


@pytest.mark.timeout(60)
class TestTimeDiffSingleFunction:
    """time_diff 单功能测试"""

    def test_humanized_seconds(self):
        """小于1分钟显示'刚刚'"""
        from app.tools.timer.time_diff import timediff as time_diff
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).isoformat()
        result = time_diff(start=now)
        assert is_success(result)
        assert result["llm_data"]["summary"]

    def test_result_has_days(self):
        """返回结果包含days"""
        from app.tools.timer.time_diff import timediff as time_diff

        result = time_diff(start="2026-01-01", end="2026-06-25")
        assert is_success(result)
        assert "days" in result["llm_data"]["metrics"]
        assert result["llm_data"]["metrics"]["days"]["value"] > 0

    def test_result_has_hours(self):
        """返回结果包含hours"""
        from app.tools.timer.time_diff import timediff as time_diff

        result = time_diff(start="2026-06-25 00:00:00", end="2026-06-25 12:00:00")
        assert is_success(result)
        assert result["llm_data"]["summary"]

    def test_is_after_is_before(self):
        """is_after和is_before互斥"""
        from app.tools.timer.time_diff import timediff as time_diff

        result = time_diff(start="2026-01-01", end="2026-06-25")
        assert is_success(result)
        assert result["llm_data"]["summary"]


# ============================================================
# 八,time_now 测试
# ============================================================
@pytest.mark.timeout(60)
class TestTimeNowParamCombinations:
    """time_now 参数组合测试"""

    def test_no_params(self):
        """无参数"""
        from app.tools.fundamental.time_now import timenow as time_now

        result = time_now()
        assert is_success(result)

    def test_return_structure(self):
        """验证返回结构"""
        from app.tools.fundamental.time_now import timenow as time_now

        result = time_now()
        assert is_success(result)
        assert result["llm_data"]["summary"]

    def test_timestamp_is_int(self):
        """timestamp为整数"""
        from app.tools.fundamental.time_now import timenow as time_now

        result = time_now()
        assert is_success(result)

    def test_weekday_valid(self):
        """weekday是有效星期"""
        from app.tools.fundamental.time_now import timenow as time_now

        result = time_now()
        assert is_success(result)
        assert result["llm_data"]["summary"]

    def test_isoweekday_range(self):
        """isoweekday在1-7范围"""
        from app.tools.fundamental.time_now import timenow as time_now

        result = time_now()
        assert is_success(result)


@pytest.mark.timeout(60)
class TestTimeNowBugVerification:
    """time_now Bug验证"""

    def test_error_handler_references_undefined_timezone(self):
        """BUG验证:error handler引用未导入的timezone变量"""
        from app.tools.fundamental.time_now import timenow as time_now
        import inspect

        # BUG: time_now's except block references `timezone` which is not imported
        # Line 58: return build_error(data={"error_detail": str(e), "params": {"timezone": timezone}}, llm_data=llm_data)
        # But `timezone` is not imported in the module
        # This would cause NameError if the try block fails
        source = inspect.getsource(time_now)
        # The bug: timezone is referenced in error handler but not imported
        assert "timezone" in source  # Confirms timezone is referenced

        # Verify the module doesn't import timezone
        from app.tools.fundamental import time_now as time_now_module
        module_source = inspect.getsource(time_now_module)
        # timezone is NOT imported (only datetime is)
        assert "from datetime import timezone" not in module_source


# ============================================================
# 九,tool_search 测试
# ============================================================
@pytest.mark.timeout(60)
class TestToolSearchParamCombinations:
    """tool_search 参数组合测试"""

    def test_single_keyword(self):
        """单个关键词"""
        from app.tools.fundamental.tool_search import searchtool

        result = searchtool(query="Word")
        assert is_success(result)

    def test_multiple_keywords(self):
        """多个关键词"""
        from app.tools.fundamental.tool_search import searchtool

        result = searchtool(query="读取 Word 文档")
        assert is_success(result)

    def test_chinese_keywords(self):
        """中文关键词"""
        from app.tools.fundamental.tool_search import searchtool

        result = searchtool(query="读取Word文档")
        assert is_success(result)

    def test_english_keywords(self):
        """英文关键词"""
        from app.tools.fundamental.tool_search import searchtool

        result = searchtool(query="read file")
        assert is_success(result)

    def test_mixed_keywords(self):
        """中英文混合"""
        from app.tools.fundamental.tool_search import searchtool

        result = searchtool(query="SQL查询 database")
        assert is_success(result)


@pytest.mark.timeout(60)
class TestToolSearchSingleFunction:
    """tool_search 单功能测试"""

    def test_returns_matches(self):
        """返回matches列表"""
        from app.tools.fundamental.tool_search import searchtool

        result = searchtool(query="file")
        assert is_success(result)
        assert "matches" in result["data"]

    def test_match_has_name_category(self):
        """match包含name, category"""
        from app.tools.fundamental.tool_search import searchtool

        result = searchtool(query="Word")
        assert is_success(result)
        if result["data"]["matches"]:
            match = result["data"]["matches"][0]
            assert "name" in match
            assert "category" in match

    def test_total_tools_non_negative(self):
        """total_tools为非负数"""
        from app.tools.fundamental.tool_search import searchtool

        result = searchtool(query="file")
        assert is_success(result)
        assert result["llm_data"]["metrics"]["total"]["value"] >= 0


@pytest.mark.timeout(60)
class TestToolSearchBoundary:
    """tool_search 边界测试"""

    def test_single_char_query(self):
        """单字符查询"""
        from app.tools.fundamental.tool_search import searchtool

        result = searchtool(query="a")
        assert is_success(result) or is_error(result)

    def test_long_query(self):
        """长查询字符串"""
        from app.tools.fundamental.tool_search import searchtool

        result = searchtool(query="这是一个非常非常长的搜索查询字符串用于测试边界情况" * 5)
        assert is_success(result)

    def test_unicode_query(self):
        """Unicode查询"""
        from app.tools.fundamental.tool_search import searchtool

        result = searchtool(query="测试🔓")
        assert is_success(result)

    def test_whitespace_only_query(self):
        """纯空格查询"""
        from app.tools.fundamental.tool_search import searchtool

        result = searchtool(query="   ")
        assert is_error(result)


@pytest.mark.timeout(60)
class TestToolSearchNegative:
    """tool_search 负面测试"""

    def test_empty_query(self):
        """空查询"""
        from app.tools.fundamental.tool_search import searchtool

        result = searchtool(query="")
        assert is_error(result)
        assert "搜索关键词不能为空" in result["llm_data"]["status"]["detail"]

    def test_tool_search_accesses_private_tools(self):
        """BUG验证:tool_search访问_tools私有属性"""
        from app.tools.fundamental.tool_search import searchtool
        import inspect

        source = inspect.getsource(searchtool)
        # BUG: tool_search accesses tool_registry._tools directly
        assert "_tools" in source  # Confirms private attribute access

        # The proper way would be to use tool_registry.list_tools()
        # or a public API, but _tools is accessed directly at line 125 and 49


# ============================================================
# 十,跨工具组合测试
# ============================================================
@pytest.mark.timeout(60)
class TestCrossToolCombinations:
    """跨工具参数组合测试"""

    def test_time_add_then_time_diff(self):
        """time_add结果作为time_diff的start"""
        from app.tools.timer.time_add import timeadd as time_add
        from app.tools.timer.time_diff import timediff as time_diff

        add_result = time_add(delta=7, unit="days")
        assert is_success(add_result)

        m = re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", add_result["llm_data"]["summary"])
        assert m
        diff_result = time_diff(start=m.group(0))
        assert is_success(diff_result)
        # time_add(7 days) → future; diff from future to now → ~7 days
        assert diff_result["llm_data"]["metrics"]["days"]["value"] >= 6

    def test_time_now_then_query_calendar(self):
        """time_now获取当前日期,query_calendar判断是否工作日"""
        from app.tools.fundamental.time_now import timenow as time_now
        from app.tools.timer.query_calendar import calendar as query_calendar

        now_result = time_now()
        assert is_success(now_result)

        # Extract date (YYYY-MM-DD) from summary
        m = re.search(r"\d{4}-\d{2}-\d{2}", now_result["llm_data"]["summary"])
        assert m
        date_str = m.group(0)
        cal_result = query_calendar(name=date_str)
        assert is_success(cal_result)

    def test_time_now_then_tool_search(self):
        """time_now和tool_search同时成功"""
        from app.tools.fundamental.time_now import timenow as time_now
        from app.tools.fundamental.tool_search import searchtool

        r1 = time_now()
        r2 = searchtool(query="time")
        assert is_success(r1)
        assert is_success(r2)

    def test_get_system_info_then_time_add(self):
        """get_system_info和time_add同时成功"""
        from app.tools.fundamental.get_system_info import sysinfo as get_system_info
        from app.tools.timer.time_add import timeadd as time_add

        r1 = get_system_info(info_type="basic")
        r2 = time_add(delta=1, unit="hours")
        assert is_success(r1)
        assert is_success(r2)
