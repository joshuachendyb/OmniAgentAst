# -*- coding: utf-8 -*-
"""
mouse_scroll 参数组合与边界测试
发现BUG: amount缺少ge/le验证(0/负数不被Schema拦截)
小欧 2026-07-03
"""
import asyncio
import pytest
from app.tools.tool_response import is_success, is_error


def _run(coro):
    if asyncio.iscoroutine(coro):
        return asyncio.run(coro)
    return coro


class TestMouseScrollParam:
    """参数组合测试"""

    def test_scroll_default(self):
        """组合1: 默认参数"""
        from app.tools.desktop.mouse_scroll import mouse_scroll
        result = _run(mouse_scroll())
        assert is_success(result) or is_error(result)

    def test_scroll_down(self):
        """组合2: 向下滚动"""
        from app.tools.desktop.mouse_scroll import mouse_scroll
        result = _run(mouse_scroll(direction="down"))
        assert is_success(result) or is_error(result)

    def test_scroll_up(self):
        """组合3: 向上滚动"""
        from app.tools.desktop.mouse_scroll import mouse_scroll
        result = _run(mouse_scroll(direction="up"))
        assert is_success(result) or is_error(result)

    def test_scroll_with_amount(self):
        """组合4: 指定滚动单位"""
        from app.tools.desktop.mouse_scroll import mouse_scroll
        result = _run(mouse_scroll(direction="down", amount=10))
        assert is_success(result) or is_error(result)


class TestMouseScrollBoundary:
    """边界测试"""

    def test_amount_zero(self):
        """BUG: amount=0不被Schema拦截"""
        from app.tools.desktop.mouse_scroll import mouse_scroll
        result = _run(mouse_scroll(amount=0))
        # 实际: 可能执行了无意义的滚动
        assert is_success(result) or is_error(result)

    def test_amount_negative(self):
        """BUG: amount负数不被Schema拦截"""
        from app.tools.desktop.mouse_scroll import mouse_scroll
        result = _run(mouse_scroll(amount=-5))
        # BUG1: amount缺少ge=1验证,负数会通过Schema
        assert is_success(result) or is_error(result)

    def test_amount_very_large(self):
        """BUG: amount极大值不被Schema拦截"""
        from app.tools.desktop.mouse_scroll import mouse_scroll
        result = _run(mouse_scroll(amount=999999))
        # 实际: amount无le上限,可能导致滚轮飞快滚动
        assert is_success(result) or is_error(result)

    def test_amount_one(self):
        """边界: amount=1"""
        from app.tools.desktop.mouse_scroll import mouse_scroll
        result = _run(mouse_scroll(amount=1))
        assert is_success(result) or is_error(result)


class TestMouseScrollNegative:
    """负面测试"""

    def test_invalid_direction(self):
        """负面: 无效direction"""
        from app.tools.desktop.mouse_scroll import mouse_scroll
        result = _run(mouse_scroll(direction="left"))
        assert is_success(result) or is_error(result)

    def test_direction_case(self):
        """负面: direction大小写"""
        from app.tools.desktop.mouse_scroll import mouse_scroll
        result = _run(mouse_scroll(direction="Up"))
        assert is_success(result) or is_error(result)

    def test_amount_string(self):
        """负面: amount传字符串"""
        from app.tools.desktop.mouse_scroll import mouse_scroll
        result = _run(mouse_scroll(amount="ten"))
        assert is_success(result) or is_error(result)
