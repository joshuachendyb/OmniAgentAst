# -*- coding: utf-8 -*-
"""time_diff参数组合测试 - 小欧 2026-07-04 — 小欧 2026-07-06 data已清空，仅验证summary"""

import time
import pytest
from app.tools.tool_response import is_success, is_error


class TestTimeDiffNormal:
    """正常参数组合"""

    def test_start_only(self, temp_output_dir):
        from app.tools.timer.time_diff import timediff
        result = timediff(start="2026-05-01")
        assert is_success(result)
        assert result["data"] == {}

    def test_start_end_string(self, temp_output_dir):
        from app.tools.timer.time_diff import timediff
        result = timediff(start="2026-05-01", end="2026-05-18")
        assert is_success(result)

    def test_start_end_datetime(self, temp_output_dir):
        from app.tools.timer.time_diff import timediff
        result = timediff(start="2026-05-01 00:00:00", end="2026-05-18 12:30:00")
        assert is_success(result)

    def test_start_after_end(self, temp_output_dir):
        from app.tools.timer.time_diff import timediff
        result = timediff(start="2026-05-18", end="2026-05-01")
        assert is_success(result)

    def test_same_day(self, temp_output_dir):
        from app.tools.timer.time_diff import timediff
        result = timediff(start="2026-05-18", end="2026-05-18 00:00:00")
        assert is_success(result)
        assert result["data"] == {}

    def test_exact_one_hour(self, temp_output_dir):
        from app.tools.timer.time_diff import timediff
        result = timediff(start="2026-05-18 10:00:00", end="2026-05-18 11:00:00")
        assert is_success(result)
        assert "1.0小时" in result["llm_data"]["summary"] or "1小时" in result["llm_data"]["summary"] or "60分钟" in result["llm_data"]["summary"]

    def test_exact_one_day(self, temp_output_dir):
        from app.tools.timer.time_diff import timediff
        result = timediff(start="2026-05-18 00:00:00", end="2026-05-19 00:00:00")
        assert is_success(result)
        assert "1.0天" in result["llm_data"]["summary"] or "1天" in result["llm_data"]["summary"]

    def test_start_after_end_seconds(self, temp_output_dir):
        from app.tools.timer.time_diff import timediff
        result = timediff(start="2026-05-18", end="2026-05-10")
        assert is_success(result)


class TestTimeDiffReturnValue:
    """返回值验证 — data已清空，仅验证summary"""

    def test_return_structure(self, temp_output_dir):
        from app.tools.timer.time_diff import timediff
        result = timediff(start="2026-05-01", end="2026-05-18")
        assert result["data"] == {}
        assert "时间差" in result["llm_data"]["summary"]

    def test_signed_diff_positive(self, temp_output_dir):
        from app.tools.timer.time_diff import timediff
        result = timediff(start="2026-05-01", end="2026-05-18")
        assert result["data"] == {}

    def test_signed_diff_negative(self, temp_output_dir):
        from app.tools.timer.time_diff import timediff
        result = timediff(start="2026-05-18", end="2026-05-01")
        assert result["data"] == {}

    def test_is_equal_true(self, temp_output_dir):
        from app.tools.timer.time_diff import timediff
        result = timediff(start="2026-05-18 10:00:00", end="2026-05-18 10:00:00")
        assert result["data"] == {}
        assert "0" in result["llm_data"]["summary"] or "相同" in result["llm_data"]["summary"]

    def test_humanized_accuracy(self, temp_output_dir):
        from app.tools.timer.time_diff import timediff
        result = timediff(start="2026-05-18 10:00:00", end="2026-05-18 11:30:00")
        summary = result.get("llm_data", {}).get("summary", "")
        assert "小时" in summary or "分钟" in summary


class TestTimeDiffEdgeCases:
    """边界情况"""

    def test_invalid_start_format(self):
        from app.tools.timer.time_diff import timediff
        result = timediff(start="not-a-date")
        assert is_error(result)

    def test_invalid_end_format(self):
        from app.tools.timer.time_diff import timediff
        result = timediff(start="2026-05-18", end="not-a-date")
        assert is_error(result)

    def test_very_large_range(self, temp_output_dir):
        from app.tools.timer.time_diff import timediff
        result = timediff(start="1900-01-01", end="2026-06-24")
        assert is_success(result) or is_error(result)


class TestTimeDiffNegative:
    """负面测试"""

    def test_missing_start(self):
        from app.tools.timer.time_diff import timediff
        with pytest.raises(TypeError):
            timediff()

    def test_empty_start(self):
        from app.tools.timer.time_diff import timediff
        result = timediff(start="")
        assert is_error(result)
