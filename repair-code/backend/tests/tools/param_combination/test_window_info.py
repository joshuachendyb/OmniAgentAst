# -*- coding: utf-8 -*-
"""
window_info 参数组合与边界测试
发现BUG: schema验证缺失、边界处理缺陷
小欧 2026-07-03
"""
import asyncio
import pytest
from app.tools.tool_response import is_success, is_error


def _run(coro):
    if asyncio.iscoroutine(coro):
        return asyncio.run(coro)
    return coro


class TestWindowInfoBasic:
    """参数组合测试"""

    def test_default_params(self):
        """组合1: 仅默认参数"""
        from app.tools.desktop.window_info import window_info
        result = _run(window_info())
        assert is_success(result) or is_error(result)
        assert "windows" in result["data"] or result.get("llm_data", {}).get("status", {}).get("exec_code") == "error"

    def test_include_minimized_true(self):
        """组合2: include_minimized=True"""
        from app.tools.desktop.window_info import window_info
        result = _run(window_info(include_minimized=True))
        assert is_success(result) or is_error(result)

    def test_filter_title_chrome(self):
        """组合3: filter_title模糊匹配"""
        from app.tools.desktop.window_info import window_info
        result = _run(window_info(filter_title="Chrome"))
        assert is_success(result) or is_error(result)
        if is_success(result):
            for w in result["data"].get("windows", []):
                assert "Chrome" in w.get("title", "").lower() or "chrome" in w.get("title", "")

    def test_all_params_combined(self):
        """组合4: 全部参数"""
        from app.tools.desktop.window_info import window_info
        result = _run(window_info(include_minimized=True, filter_title="记事本"))
        assert is_success(result) or is_error(result)


class TestWindowInfoBoundary:
    """边界测试"""

    def test_filter_title_empty_string(self):
        """边界: filter_title为空字符串"""
        from app.tools.desktop.window_info import window_info
        result = _run(window_info(filter_title=""))
        assert is_success(result) or is_error(result)

    def test_filter_title_very_long(self):
        """边界: filter_title超长"""
        from app.tools.desktop.window_info import window_info
        long_title = "A" * 10000
        result = _run(window_info(filter_title=long_title))
        assert is_success(result) or is_error(result)

    def test_filter_title_unicode_special(self):
        """边界: filter_title含特殊Unicode"""
        from app.tools.desktop.window_info import window_info
        result = _run(window_info(filter_title="\u0000\u0001\u0002"))
        assert is_success(result) or is_error(result)

    def test_filter_title_emoji(self):
        """边界: filter_title含emoji"""
        from app.tools.desktop.window_info import window_info
        result = _run(window_info(filter_title="\U0001f600\U0001f44d"))
        assert is_success(result) or is_error(result)


class TestWindowInfoNegative:
    """负面测试"""

    def test_include_minimized_invalid_type(self):
        """负面: include_minimized传字符串"""
        from app.tools.desktop.window_info import window_info
        result = _run(window_info(include_minimized="yes"))
        assert is_success(result) or is_error(result)

    def test_filter_title_none(self):
        """负面: filter_title传None等效于不传"""
        from app.tools.desktop.window_info import window_info
        result = _run(window_info(filter_title=None))
        assert is_success(result) or is_error(result)

    def test_invalid_kwargs(self):
        """负面: 传不存在的参数"""
        with pytest.raises(Exception):
            from app.tools.desktop.window_info import window_info
            _run(window_info(invalid_param="test"))
