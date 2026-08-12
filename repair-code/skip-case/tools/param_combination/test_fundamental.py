# -*- coding: utf-8 -*-
# ================================================================
# 【skip case 归档副本】 - 小欧 2026-08-12 10:43:59
# 原路径: backend/tests/tools/param_combination/test_fundamental.py
# 归档原因: 包含 GUI 环境依赖类 skip case(TestSendNotification 类),
#           已从 backend/tests 原文件删除对应 skip case, 此处保留完整代码,
#           便于在具备 GUI 环境时恢复运行。
# ================================================================
"""
fundamental工具参数组合测试 - 小健 2026-06-24

测试工具:
1. tool_search - BM25工具搜索
2. time_now - 获取当前时间
3. time_add - 时间加减
4. time_diff - 时间差值
5. query_calendar - 节日查询
6. get_system_info - 系统信息
7. send_notification - 发送通知
"""

import pytest
from pathlib import Path
from app.tools.tool_response import is_success, is_error


class TestToolSearch:
    """tool_search参数组合测试"""
    
    def test_single_keyword(self, temp_output_dir):
        """单个关键词搜索"""
        from app.tools.fundamental.tool_search import searchtool
        
        result = searchtool(query="Word")
        assert is_success(result)
        assert "data" in result
    
    def test_multiple_keywords(self, temp_output_dir):
        """多个关键词搜索"""
        from app.tools.fundamental.tool_search import searchtool
        
        result = searchtool(query="读取 Word 文档")
        assert is_success(result)
    
    def test_chinese_keywords(self, temp_output_dir):
        """中文关键词"""
        from app.tools.fundamental.tool_search import searchtool
        
        result = searchtool(query="读取Word文档")
        assert is_success(result)
    
    def test_english_keywords(self, temp_output_dir):
        """英文关键词"""
        from app.tools.fundamental.tool_search import searchtool
        
        result = searchtool(query="read file")
        assert is_success(result)
    
    def test_mixed_keywords(self, temp_output_dir):
        """中英文混合"""
        from app.tools.fundamental.tool_search import searchtool
        
        result = searchtool(query="SQL查询 database")
        assert is_success(result)


class TestTimeNow:
    """time_now参数组合测试"""
    
    def test_no_params(self, temp_output_dir):
        """无参数(默认行为)"""
        from app.tools.fundamental.time_now import timenow
        
        result = timenow()
        assert is_success(result)
        
        llm_data = result["llm_data"]
        assert llm_data is not None
        assert llm_data["status"]["exec_code"] == "success"
    
    def test_return_structure(self, temp_output_dir):
        """验证返回结构完整性"""
        from app.tools.fundamental.time_now import timenow
        
        result = timenow()
        llm_data = result["llm_data"]
        
        assert llm_data["status"]["exec_code"] == "success"
        assert "获取当前时间成功" in llm_data["summary"]


class TestTimeAdd:
    """time_add参数组合测试"""
    
    def test_delta_only_days(self, temp_output_dir):
        """仅delta(默认days)"""
        from app.tools.timer.time_add import timeadd
        
        result = timeadd(delta=7)
        assert is_success(result)
        assert "时间加减" in result["llm_data"]["summary"]
    
    def test_delta_hours(self, temp_output_dir):
        """delta + unit=hours"""
        from app.tools.timer.time_add import timeadd
        
        result = timeadd(delta=3, unit="hours")
        assert is_success(result)
    
    def test_delta_minutes(self, temp_output_dir):
        """delta + unit=minutes"""
        from app.tools.timer.time_add import timeadd
        
        result = timeadd(delta=30, unit="minutes")
        assert is_success(result)
    
    def test_delta_seconds(self, temp_output_dir):
        """delta + unit=seconds"""
        from app.tools.timer.time_add import timeadd
        
        result = timeadd(delta=90, unit="seconds")
        assert is_success(result)
    
    def test_delta_months(self, temp_output_dir):
        """delta + unit=months"""
        from app.tools.timer.time_add import timeadd
        
        result = timeadd(delta=2, unit="months")
        assert is_success(result)
    
    def test_negative_delta(self, temp_output_dir):
        """负数delta(减少时间)"""
        from app.tools.timer.time_add import timeadd
        
        result = timeadd(delta=-7, unit="days")
        assert is_success(result)
    
    def test_with_start_string(self, temp_output_dir):
        """start为字符串"""
        from app.tools.timer.time_add import timeadd
        
        result = timeadd(start="2026-05-18 10:00:00", delta=7, unit="days")
        assert is_success(result)
    
    def test_with_start_timestamp(self, temp_output_dir):
        """start为时间戳"""
        from app.tools.timer.time_add import timeadd
        
        result = timeadd(start=1717200000, delta=1, unit="days")
        assert is_success(result)


class TestTimeDiff:
    """time_diff参数组合测试"""
    
    def test_start_only(self, temp_output_dir):
        """仅start(end默认当前)"""
        from app.tools.timer.time_diff import timediff
        
        result = timediff(start="2026-05-01")
        assert is_success(result)
        assert "计算时间差" in result["llm_data"]["summary"]
    
    def test_start_end_string(self, temp_output_dir):
        """start和end都为字符串"""
        from app.tools.timer.time_diff import timediff
        
        result = timediff(start="2026-05-01", end="2026-05-18")
        assert is_success(result)
    
    def test_start_end_timestamp(self, temp_output_dir):
        """start和end都为时间戳"""
        from app.tools.timer.time_diff import timediff
        
        result = timediff(start=1717200000, end=1717804800)
        assert is_success(result)
    
    def test_diff_result_structure(self, temp_output_dir):
        """验证返回结构"""
        from app.tools.timer.time_diff import timediff
        
        result = timediff(start="2026-05-01", end="2026-05-18")
        llm_data = result["llm_data"]
        
        assert llm_data["status"]["exec_code"] == "success"


class TestQueryCalendar:
    """query_calendar参数组合测试"""
    
    def test_festival_with_year(self, temp_output_dir):
        """节日名+年份"""
        from app.tools.timer.query_calendar import calendar
        
        result = calendar(name="端午节", year=2026)
        assert is_success(result)
        assert "日历查询" in result["llm_data"]["summary"]
    
    def test_festival_without_year(self, temp_output_dir):
        """节日名(默认当年)"""
        from app.tools.timer.query_calendar import calendar
        
        result = calendar(name="春节")
        assert is_success(result)
    
    def test_date_string(self, temp_output_dir):
        """日期字符串(判断工作日/节假日)"""
        from app.tools.timer.query_calendar import calendar
        
        result = calendar(name="2026-06-24")
        assert is_success(result)
    
    def test_multiple_festivals(self, temp_output_dir):
        """多个节日测试"""
        from app.tools.timer.query_calendar import calendar
        
        festivals = ["春节", "端午节", "中秋节", "国庆节", "元旦"]
        for festival in festivals:
            result = calendar(name=festival, year=2026)
            assert is_success(result), f"{festival}查询失败"


class TestGetSystemInfo:
    """get_system_info参数组合测试"""
    
    def test_no_params(self, temp_output_dir):
        """无参数(默认all)"""
        from app.tools.fundamental.get_system_info import sysinfo
        
        result = sysinfo()
        assert is_success(result)
    
    def test_info_type_all(self, temp_output_dir):
        """info_type=all"""
        from app.tools.fundamental.get_system_info import sysinfo
        
        result = sysinfo(info_type="all")
        assert is_success(result)
        data = result["data"]
        assert "cpu" in data or "memory" in data
    
    def test_info_type_basic(self, temp_output_dir):
        """info_type=basic"""
        from app.tools.fundamental.get_system_info import sysinfo
        
        result = sysinfo(info_type="basic")
        assert is_success(result)
    
    def test_info_type_cpu(self, temp_output_dir):
        """info_type=cpu"""
        from app.tools.fundamental.get_system_info import sysinfo
        
        result = sysinfo(info_type="cpu")
        assert is_success(result)
        assert "cpu" in result["data"]
    
    def test_info_type_memory(self, temp_output_dir):
        """info_type=memory"""
        from app.tools.fundamental.get_system_info import sysinfo
        
        result = sysinfo(info_type="memory")
        assert is_success(result)
        assert "memory" in result["data"]
    
    def test_info_type_disk(self, temp_output_dir):
        """info_type=disk"""
        from app.tools.fundamental.get_system_info import sysinfo
        
        result = sysinfo(info_type="disk")
        assert is_success(result)
    
    def test_info_type_network(self, temp_output_dir):
        """info_type=network"""
        from app.tools.fundamental.get_system_info import sysinfo
        
        result = sysinfo(info_type="network")
        assert is_success(result)


@pytest.mark.skip(reason="send_notification需要GUI环境,win10toast在无GUI环境报DISPLAY错误")
class TestSendNotification:
    """send_notification参数组合测试"""
    
    def test_title_message_only(self, temp_output_dir):
        """仅必填参数"""
        from app.tools.fundamental.send_notification import notify
        
        result = notify(title="测试通知", message="这是测试内容")
        assert is_success(result)
    
    def test_with_duration(self, temp_output_dir):
        """带duration参数"""
        from app.tools.fundamental.send_notification import notify
        
        result = notify(title="任务完成", message="全部操作已完成", duration=5)
        assert is_success(result)
    
    def test_special_chars(self, temp_output_dir):
        """特殊字符"""
        from app.tools.fundamental.send_notification import notify
        
        result = notify(
            title="特殊字符测试",
            message="包含特殊字符<>&\"'的通知",
            duration=3
        )
        assert is_success(result)
    
    def test_long_text(self, temp_output_dir):
        """长文本(超过100字符)"""
        from app.tools.fundamental.send_notification import notify
        
        long_title = "这是一个较长的通知标题用于测试系统对长文本的处理能力认保不会出现截断"
        long_message = "这是一条较长的通知内容,用于测试系统对长文本的处理能力,认保不会出现截断或显示异常.测试内容超过100字符,验证系统的稳定性." * 2
        
        result = notify(title=long_title, message=long_message, duration=8)
        assert is_success(result)


class TestNegative:
    """负面测试"""
    
    def test_time_add_invalid_unit(self):
        """time_add无效unit(应该被Schema拦截)"""
        from app.tools.timer.time_add import timeadd
        
        result = timeadd(delta=7, unit="invalid_unit")
        assert is_error(result)
    
    def test_get_system_info_invalid_type(self):
        """get_system_info无效info_type - Bug #2已修复"""
        from app.tools.fundamental.get_system_info import sysinfo
        
        result = sysinfo(info_type="invalid")
        assert is_error(result)
        assert "无效的info_type" in result["llm_data"]["status"]["detail"]
    
    def test_time_now_no_format_param(self):
        """time_now不支持format参数 - Bug #1验证"""
        from app.tools.fundamental.time_now import timenow
        
        try:
            result = timenow(format="%Y-%m-%d")
            assert False, "time_now不应该接收format参数"
        except TypeError:
            pass
    
    def test_get_system_info_valid_types(self):
        """验证get_system_info只接收有效类型"""
        from app.tools.fundamental.get_system_info import sysinfo
        
        valid_types = ["basic", "cpu", "memory", "disk", "network", "all"]
        for t in valid_types:
            result = sysinfo(info_type=t)
            assert is_success(result), f"{t}应该是有效类型"
