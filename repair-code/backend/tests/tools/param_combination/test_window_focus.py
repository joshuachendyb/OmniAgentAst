# -*- coding: utf-8 -*-
"""
window_focus 参数测试
发现BUG: 空标题处理缺陷、特殊字符边界
小欧 2026-07-03
"""
import asyncio
import pytest
from app.tools.tool_response import is_success, is_error


def _run(coro):
    if asyncio.iscoroutine(coro):
        return asyncio.run(coro)
    return coro


class TestWindowFocusParam:
    """参数组合测试"""

    def test_focus_nonexistent_title(self):
        """组合1: 聚焦不存在的窗口"""
        from app.tools.desktop.window_focus import window_focus
        result = _run(window_focus(window_title="NONEXISTENT_WINDOW_12345"))
        assert is_error(result)

    def test_focus_empty_string_title(self):
        """组合2: window_title为空字符串"""
        from app.tools.desktop.window_focus import window_focus
        result = _run(window_focus(window_title=""))
        assert is_error(result)


class TestWindowFocusBoundary:
    """边界测试"""

    def test_title_very_long(self):
        """边界: window_title超长"""
        from app.tools.desktop.window_focus import window_focus
        result = _run(window_focus(window_title="A" * 10000))
        assert is_error(result)

    def test_title_unicode_special(self):
        """边界: window_title含控制字符"""
        from app.tools.desktop.window_focus import window_focus
        result = _run(window_focus(window_title="test\u0000window"))
        assert is_error(result)

    def test_title_only_whitespace(self):
        """边界: window_title只含空白"""
        from app.tools.desktop.window_focus import window_focus
        result = _run(window_focus(window_title="   "))
        assert is_error(result)

    def test_title_newlines(self):
        """边界: window_title含换行符"""
        from app.tools.desktop.window_focus import window_focus
        result = _run(window_focus(window_title="title\nnext"))
        assert is_error(result)


class TestWindowFocusNegative:
    """负面测试"""

    def test_missing_title(self):
        """负面: 不传必填参数"""
        with pytest.raises(Exception):
            from app.tools.desktop.window_focus import window_focus
            _run(window_focus())

    def test_title_none(self):
        """负面: title传None"""
        from app.tools.desktop.window_focus import window_focus
        result = _run(window_focus(window_title=None))
        assert is_error(result)

    def test_title_non_string(self):
        """负面: title传非字符串"""
        from app.tools.desktop.window_focus import window_focus
        result = _run(window_focus(window_title=123))
        assert is_error(result)
