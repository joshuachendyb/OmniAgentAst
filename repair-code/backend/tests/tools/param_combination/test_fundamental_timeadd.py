# -*- coding: utf-8 -*-
"""time_add参数组合测试 - 小欧 2026-07-04

测试时间加减工具的各种参数组合：delta正负、单位组合、start格式、边界值
"""

import time
import pytest
from app.tools.tool_response import is_success, is_error


class TestTimeAddNormal:
    """正常参数组合"""

    def test_delta_days(self, temp_output_dir):
        from app.tools.timer.time_add import timeadd
        result = timeadd(delta=7)
        assert is_success(result)

    def test_delta_hours(self, temp_output_dir):
        from app.tools.timer.time_add import timeadd
        result = timeadd(delta=3, unit="hours")
        assert is_success(result)

    def test_delta_minutes(self, temp_output_dir):
        from app.tools.timer.time_add import timeadd
        result = timeadd(delta=30, unit="minutes")
        assert is_success(result)

    def test_delta_seconds(self, temp_output_dir):
        from app.tools.timer.time_add import timeadd
        result = timeadd(delta=90, unit="seconds")
        assert is_success(result)

    def test_delta_months(self, temp_output_dir):
        from app.tools.timer.time_add import timeadd
        result = timeadd(delta=2, unit="months")
        assert is_success(result)

    def test_negative_delta_days(self, temp_output_dir):
        from app.tools.timer.time_add import timeadd
        result = timeadd(delta=-7, unit="days")
        assert is_success(result)

    def test_negative_delta_months(self, temp_output_dir):
        from app.tools.timer.time_add import timeadd
        result = timeadd(delta=-1, unit="months")
        assert is_success(result)

    def test_delta_zero(self, temp_output_dir):
        from app.tools.timer.time_add import timeadd
        result = timeadd(delta=0)
        assert is_success(result)

    def test_delta_float(self, temp_output_dir):
        from app.tools.timer.time_add import timeadd
        result = timeadd(delta=1.5, unit="days")
        assert is_success(result)

    def test_delta_negative_float(self, temp_output_dir):
        from app.tools.timer.time_add import timeadd
        result = timeadd(delta=-0.5, unit="hours")
        assert is_success(result)

    def test_start_string_date_only(self, temp_output_dir):
        from app.tools.timer.time_add import timeadd
        result = timeadd(start="2026-05-18", delta=7, unit="days")
        assert is_success(result)

    def test_start_string_datetime(self, temp_output_dir):
        from app.tools.timer.time_add import timeadd
        result = timeadd(start="2026-05-18 10:00:00", delta=7, unit="days")
        assert is_success(result)

    def test_all_units(self, temp_output_dir):
        from app.tools.timer.time_add import timeadd
        for unit in ["days", "hours", "minutes", "seconds", "months"]:
            result = timeadd(delta=1, unit=unit)
            assert is_success(result), f"unit={unit} failed"


class TestTimeAddReturnValue:
    """返回值内容验证 — data已清空，仅验证summary"""

    def test_result_after_now(self, temp_output_dir):
        from app.tools.timer.time_add import timeadd
        result = timeadd(delta=1, unit="hours")
        assert is_success(result)
        assert result["data"] == {}
        summary = result["llm_data"]["summary"]
        assert "后" in summary

    def test_result_before_now(self, temp_output_dir):
        from app.tools.timer.time_add import timeadd
        result = timeadd(delta=-1, unit="hours")
        assert is_success(result)
        assert result["data"] == {}

    def test_delta_float_months_bug(self, temp_output_dir):
        from app.tools.timer.time_add import timeadd
        result = timeadd(delta=1.5, unit="months")
        assert is_success(result)

    def test_return_structure(self, temp_output_dir):
        from app.tools.timer.time_add import timeadd
        result = timeadd(delta=1, unit="days")
        assert result["data"] == {}
        assert "后" in result["llm_data"]["summary"]

    def test_start_with_specific_time(self, temp_output_dir):
        from app.tools.timer.time_add import timeadd
        result = timeadd(start="2026-01-01 00:00:00", delta=1, unit="days")
        assert result["data"] == {}
        assert "2026-01-02" in result["llm_data"]["summary"]

    def test_start_with_specific_time_hours(self, temp_output_dir):
        from app.tools.timer.time_add import timeadd
        result = timeadd(start="2026-01-01 10:00:00", delta=2, unit="hours")
        assert result["data"] == {}
        assert "2026-01-01" in result["llm_data"]["summary"]


class TestTimeAddEdgeCases:
    """边界情况"""

    def test_invalid_unit(self):
        from app.tools.timer.time_add import timeadd
        result = timeadd(delta=7, unit="invalid_unit")
        assert is_error(result)

    def test_invalid_start_format(self):
        from app.tools.timer.time_add import timeadd
        result = timeadd(start="not-a-date", delta=7, unit="days")
        assert is_error(result)

    def test_very_large_delta(self, temp_output_dir):
        from app.tools.timer.time_add import timeadd
        result = timeadd(delta=99999, unit="days")
        assert is_success(result)

    def test_very_small_delta(self, temp_output_dir):
        from app.tools.timer.time_add import timeadd
        result = timeadd(delta=0.001, unit="seconds")
        assert is_success(result)


class TestTimeAddNegative:
    """负面测试"""

    def test_missing_delta(self):
        from app.tools.timer.time_add import timeadd
        with pytest.raises(TypeError):
            timeadd()

    def test_invalid_unit_literal(self):
        from app.tools.timer.time_add import timeadd
        result = timeadd(delta=7, unit="years")
        assert is_error(result)
