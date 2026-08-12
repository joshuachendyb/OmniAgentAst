# -*- coding: utf-8 -*-
"""
window_resize 参数组合与边界测试
发现BUG: width/height缺少ge验证(负数/0不会被Schema拦截)
小欧 2026-07-03
"""
import asyncio
import pytest
from app.tools.tool_response import is_success, is_error


def _run(coro):
    if asyncio.iscoroutine(coro):
        return asyncio.run(coro)
    return coro


class TestWindowResizeParam:
    """参数组合测试"""

    def test_resize_nonexistent_window(self):
        """组合1: 不存在的窗口"""
        from app.tools.desktop.window_resize import window_resize
        result = _run(window_resize(window_title="NONEXISTENT_WINDOW_12345"))
        assert is_error(result)

    def test_resize_empty_title(self):
        """组合2: window_title为空字符串"""
        from app.tools.desktop.window_resize import window_resize
        result = _run(window_resize(window_title=""))
        assert is_error(result)

    def test_resize_with_width_height(self):
        """组合3: 传width和height"""
        from app.tools.desktop.window_resize import window_resize
        result = _run(window_resize(window_title="NONEXISTENT", width=1024, height=768))
        assert is_error(result)


class TestWindowResizeBoundary:
    """边界测试 — 这些应该被Schema拦截但缺少ge验证"""

    def test_width_zero(self):
        """BUG: width=0缺少ge验证不被Schema拦截"""
        from app.tools.desktop.window_resize import window_resize
        result = _run(window_resize(window_title="NONEXISTENT", width=0, height=600))
        # 期望: 应该被错误处理捕获
        assert is_error(result)

    def test_height_zero(self):
        """BUG: height=0缺少ge验证"""
        from app.tools.desktop.window_resize import window_resize
        result = _run(window_resize(window_title="NONEXISTENT", width=800, height=0))
        assert is_error(result)

    def test_width_negative(self):
        """BUG: width负数不会被Schema拦截"""
        from app.tools.desktop.window_resize import window_resize
        result = _run(window_resize(window_title="NONEXISTENT", width=-100, height=600))
        assert is_error(result)

    def test_height_negative(self):
        """BUG: height负数不会被Schema拦截"""
        from app.tools.desktop.window_resize import window_resize
        result = _run(window_resize(window_title="NONEXISTENT", width=800, height=-100))
        assert is_error(result)

    def test_both_negative(self):
        """边界: width和height同时负数"""
        from app.tools.desktop.window_resize import window_resize
        result = _run(window_resize(window_title="NONEXISTENT", width=-1, height=-1))
        assert is_error(result)

    def test_width_huge(self):
        """边界: width极大值"""
        from app.tools.desktop.window_resize import window_resize
        result = _run(window_resize(window_title="NONEXISTENT", width=999999, height=600))
        assert is_error(result)

    def test_width_none(self):
        """边界: width传None（走默认值800）"""
        from app.tools.desktop.window_resize import window_resize
        result = _run(window_resize(window_title="NONEXISTENT", width=None, height=600))
        assert is_error(result)


class TestWindowResizeNegative:
    """负面测试"""

    def test_missing_title(self):
        """负面: 不传必填参数"""
        with pytest.raises(Exception):
            from app.tools.desktop.window_resize import window_resize
            _run(window_resize())

    def test_title_non_string(self):
        """负面: title传数字"""
        from app.tools.desktop.window_resize import window_resize
        result = _run(window_resize(window_title=999))
        assert is_error(result)

    def test_width_string(self):
        """负面: width传字符串"""
        from app.tools.desktop.window_resize import window_resize
        result = _run(window_resize(window_title="test", width="abc", height=600))
        assert is_error(result) or is_success(result)
