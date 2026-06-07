# -*- coding: utf-8 -*-
"""
Time工具V2系统测试 - test_time_system.py

系统级测试：验证7个精简工具端到端功能

Author: 小健 - 2026-05-18
"""

import asyncio
from datetime import datetime

import pytest

from app.services.tools.meta.time_tools import (
    get_time,
    time_add,
    time_diff,
    query_calendar,
    timezone_convert,
    timer,
)

# 【FIX3 2026-05-20 小健】验证旧名 check_date 已不可导入
def test_check_date_name_removed():
    """旧名 check_date 已从 time_tools 移除，必须使用 query_calendar"""
    import importlib
    import app.services.tools.meta.time_tools as tt
    assert not hasattr(tt, 'check_date'), "check_date 应已移除"
    assert hasattr(tt, 'query_calendar'), "query_calendar 应存在"


class TestTimeSystemIntegration:
    """系统级集成测试"""

    def test_full_time_workflow(self):
        """场景1: 完整时间工作流"""
        # Step 1: 获取当前时间
        now = get_time(action="now")
        assert now["code"] == "SUCCESS"
        
        # Step 2: 格式化时间
        formatted = get_time(action="format", time_value=now["data"]["timestamp"])
        assert formatted["code"] == "SUCCESS"
        
        # Step 3: 计算未来时间
        future = time_add(delta=7, start=now["data"]["timestamp"], unit="days")
        assert future["code"] == "SUCCESS"
        
        # Step 4: 计算时间差
        diff = time_diff(start=now["data"]["timestamp"], end=future["data"]["timestamp"])
        assert diff["code"] == "SUCCESS"
        assert diff["data"]["days"] >= 6

    def test_holiday_check_workflow(self):
        """场景2: 节假日检查工作流"""
        # Step 1: 检查国庆节
        result = query_calendar(date="2026-10-01", check_type="holiday")
        assert result["code"] == "SUCCESS"
        assert result["data"]["is_holiday"] is True
        assert result["data"]["holiday_name"] == "国庆节"
        
        # Step 2: P15验证 - 一次性获取全部信息
        data = result["data"]
        assert "is_weekend" in data
        assert "is_workday" in data
        assert data["is_workday"] is False

    def test_timezone_workflow(self):
        """场景3: 时区转换工作流"""
        # UTC → 本地
        utc_time = "2026-05-18T12:00:00Z"
        local = timezone_convert(time_value=utc_time, direction="utc_to_local")
        assert local["code"] == "SUCCESS"
        
        # 本地 → UTC
        back_to_utc = timezone_convert(
            time_value=local["data"]["local_time"],
            direction="local_to_utc"
        )
        assert back_to_utc["code"] == "SUCCESS"

    def test_timer_workflow(self):
        """场景4: 定时器工作流"""
        async def _test():
            # 设置定时器
            set_result = await timer(action="set", delay=300, callback="测试提醒")
            assert set_result["code"] == "SUCCESS"
            timer_id = set_result["data"]["timer_id"]
            
            # 列出定时器
            list_result = await timer(action="list")
            assert list_result["code"] == "SUCCESS"
            
            # 清除定时器
            clear_result = await timer(action="clear", timer_id=timer_id)
            assert clear_result["code"] == "SUCCESS"
        
        asyncio.run(_test())

    def test_query_calendar_comprehensive(self):
        """场景5: check_date P15全面返回测试"""
        # 查询一个工作日
        result = query_calendar(date="2026-05-18", check_type="workday")
        assert result["code"] == "SUCCESS"
        
        # 验证一次性返回全部日历属性
        data = result["data"]
        assert data["date"] == "2026-05-18"
        assert "weekday" in data
        assert 1 <= data["isoweekday"] <= 7
        assert isinstance(data["is_weekend"], bool)
        assert isinstance(data["is_holiday"], bool)
        assert data["holiday_name"] is None
        assert isinstance(data["is_workday"], bool)
        
        # 工作日场景：周一应该是工作日
        if data["isoweekday"] == 1:
            assert data["is_weekend"] is False
            assert data["is_workday"] is True

    def test_time_diff_replaces_compare(self):
        """场景6: time_diff替代time_compare"""
        # 两个时间比较
        result = time_diff(start="2026-05-01", end="2026-05-18")
        assert result["code"] == "SUCCESS"
        
        # 验证新增字段（替代time_compare）
        assert "is_after" in result["data"]
        assert "is_before" in result["data"]
        assert "is_equal" in result["data"]
        assert "diff_seconds_signed" in result["data"]
        
        # 逻辑验证
        assert result["data"]["is_after"] is True
        assert result["data"]["is_before"] is False
        assert result["data"]["is_equal"] is False
        assert result["data"]["diff_seconds_signed"] > 0

    def test_get_time_all_actions(self):
        """场景7: get_time所有action测试"""
        # action=now
        now = get_time(action="now")
        assert now["code"] == "SUCCESS"
        
        # action=format
        formatted = get_time(action="format", time_value="2026-05-18 14:30:00")
        assert formatted["code"] == "SUCCESS"
        
        # action=to_timestamp
        ts = get_time(action="to_timestamp", time_value="2026-05-18 14:30:00")
        assert ts["code"] == "SUCCESS"
        assert "timestamp" in ts["data"]
        
        # action=from_timestamp
        from_ts = get_time(action="from_timestamp", time_value=ts["data"]["timestamp"])
        assert from_ts["code"] == "SUCCESS"





class TestErrorHandling:
    """错误处理测试"""

    def test_get_time_invalid_action(self):
        """get_time无效action"""
        result = get_time(action="invalid")
        assert result["code"] == "ERR_INVALID_ACTION"

    def test_get_time_to_timestamp_missing_value(self):
        """get_time to_timestamp缺少time_value"""
        result = get_time(action="to_timestamp", time_value=None)
        assert result["code"] == "ERR_META_TIME_FORMAT"

    def test_query_calendar_invalid_type(self):
        """check_date无效check_type"""
        result = query_calendar(date="2026-05-18", check_type="invalid")
        assert result["code"] == "ERR_META_INVALID_CHECK_TYPE"

    def test_timezone_convert_invalid_direction(self):
        """timezone_convert无效direction"""
        result = timezone_convert(time_value="2026-05-18", direction="invalid")
        assert result["code"] == "ERR_INVALID_DIRECTION"

    def test_timezone_convert_any_missing_params(self):
        """timezone_convert any缺少参数【FIX 2026-05-20 小健】对齐精简后API"""
        result = timezone_convert(
            time_value="2026-05-18",
            direction="any",
        )
        assert result["code"] == "ERR_TIME_TZ"

    def test_timer_invalid_action(self):
        """timer无效action"""
        async def _test():
            result = await timer(action="invalid")
            assert result["code"] == "ERR_INVALID_ACTION"
        asyncio.run(_test())
