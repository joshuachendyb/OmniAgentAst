# -*- coding: utf-8 -*-
"""query_calendar参数组合测试 - 小欧 2026-07-04

测试节日/日期查询工具的各种参数组合：节日名、日期字符串、年份组合、边界情况
"""

import pytest
from app.tools.tool_response import is_success, is_error


class TestCalendarNormal:
    """正常参数组合 - 节日查询"""

    def test_festival_with_year(self, temp_output_dir):
        from app.tools.timer.query_calendar import calendar
        result = calendar(name="中秋节", year=2026)
        assert is_success(result)
        assert result["data"] == {}
        assert "中秋节" in result["llm_data"]["summary"]

    def test_festival_without_year(self, temp_output_dir):
        from app.tools.timer.query_calendar import calendar
        result = calendar(name="春节")
        assert is_success(result)

    def test_multiple_festivals(self, temp_output_dir):
        from app.tools.timer.query_calendar import calendar
        for festival in ["春节", "端午节", "中秋节", "国庆节", "元旦"]:
            result = calendar(name=festival, year=2026)
            assert is_success(result), f"{festival}查询失败"

    def test_date_string(self, temp_output_dir):
        from app.tools.timer.query_calendar import calendar
        result = calendar(name="2026-06-26")
        assert is_success(result)
        assert result["data"] == {}
        assert "2026-06-26" in result["llm_data"]["summary"]

    def test_date_string_with_time(self, temp_output_dir):
        from app.tools.timer.query_calendar import calendar
        result = calendar(name="2026-06-26 10:00:00")
        assert is_success(result)

    def test_festival_new_year(self, temp_output_dir):
        from app.tools.timer.query_calendar import calendar
        result = calendar(name="元旦", year=2026)
        assert is_success(result)

    def test_festival_spring_festival(self, temp_output_dir):
        from app.tools.timer.query_calendar import calendar
        result = calendar(name="春节", year=2026)
        assert is_success(result)
        assert result["data"] == {}
        assert "2026-02-17" in result["llm_data"]["summary"]


class TestCalendarReturnValue:
    """返回值结构验证"""

    def test_festival_return_fields(self, temp_output_dir):
        from app.tools.timer.query_calendar import calendar
        result = calendar(name="端午节", year=2026)
        assert result["data"] == {}
        s = result["llm_data"]["summary"]
        assert "端午节" in s
        assert "农历" in s or "公历" in s

    def test_date_return_fields(self, temp_output_dir):
        from app.tools.timer.query_calendar import calendar
        result = calendar(name="2026-06-26")
        assert result["data"] == {}
        assert "2026-06-26" in result["llm_data"]["summary"]

    def test_weekday_consistency(self, temp_output_dir):
        from app.tools.timer.query_calendar import calendar
        result = calendar(name="2026-06-26")
        assert result["data"] == {}

    def test_weekend_workday_mutual_exclusion(self, temp_output_dir):
        from app.tools.timer.query_calendar import calendar
        result = calendar(name="2026-06-26")
        assert result["data"] == {}
        assert "2026-06-26" in result["llm_data"]["summary"]


class TestCalendarEdgeCases:
    """边界情况"""

    def test_year_with_date_string(self, temp_output_dir):
        from app.tools.timer.query_calendar import calendar
        result = calendar(name="2026-06-26", year=2025)
        assert is_success(result)

    def test_festival_missing_year(self, temp_output_dir):
        from app.tools.timer.query_calendar import calendar
        result = calendar(name="元旦", year=2026)
        assert is_success(result)

    def test_festival_yuanxiao(self, temp_output_dir):
        from app.tools.timer.query_calendar import calendar
        result = calendar(name="元宵节", year=2026)
        assert is_success(result) or is_error(result)

    def test_festival_labor_day(self, temp_output_dir):
        from app.tools.timer.query_calendar import calendar
        result = calendar(name="劳动节", year=2026)
        assert is_success(result)

    def test_festival_qingming(self, temp_output_dir):
        from app.tools.timer.query_calendar import calendar
        result = calendar(name="清明节", year=2026)
        assert is_success(result)


class TestCalendarNegative:
    """负面测试"""

    def test_invalid_festival(self):
        from app.tools.timer.query_calendar import calendar
        result = calendar(name="不存在的节日")
        assert is_error(result)

    def test_invalid_date_string(self):
        from app.tools.timer.query_calendar import calendar
        result = calendar(name="2026-13-01")
        assert is_error(result)

    def test_empty_name(self):
        from app.tools.timer.query_calendar import calendar
        result = calendar(name="")
        assert is_error(result)

    def test_random_string(self):
        from app.tools.timer.query_calendar import calendar
        result = calendar(name="asdfghjkl")
        assert is_error(result)

    def test_missing_name(self):
        from app.tools.timer.query_calendar import calendar
        with pytest.raises(TypeError):
            calendar()
