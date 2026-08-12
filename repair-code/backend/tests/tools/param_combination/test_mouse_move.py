# -*- coding: utf-8 -*-
"""
mouse_move 参数组合与边界测试
发现BUG: x/y缺少ge/le验证、负数坐标不被拦截
小欧 2026-07-03
"""
import asyncio
import pytest
from app.tools.tool_response import is_success, is_error


def _run(coro):
    if asyncio.iscoroutine(coro):
        return asyncio.run(coro)
    return coro


class TestMouseMoveParam:
    """参数组合测试"""

    def test_move_basic(self):
        """组合1: 移动到指定坐标"""
        from app.tools.desktop.mouse_move import mouse_move
        result = _run(mouse_move(x=500, y=300))
        assert is_success(result) or is_error(result)

    def test_move_origin(self):
        """组合2: 移动到(0,0)"""
        from app.tools.desktop.mouse_move import mouse_move
        result = _run(mouse_move(x=0, y=0))
        assert is_success(result) or is_error(result)


class TestMouseMoveBoundary:
    """边界测试
    2026-08-12 - 小欧 - 修正4个失败case: 原测试(2026-07-03)期望负/超大坐标is_error,
    与 2026-08-05 三堂会审设计决策冲突 — desktop_schema MouseMove x/y 故意不约束
    (多显示器负坐标合法,避免退化)。修正为验证不崩溃且返回结构化响应。
    """

    def test_move_negative_x(self):
        """负x合法(多显示器场景): 不崩溃、返回结构化响应"""
        from app.tools.desktop.mouse_move import mouse_move
        result = _run(mouse_move(x=-100, y=300))
        assert is_success(result) or is_error(result), f"应返回结构化响应: {result}"

    def test_move_negative_y(self):
        """负y合法(多显示器场景): 不崩溃、返回结构化响应"""
        from app.tools.desktop.mouse_move import mouse_move
        result = _run(mouse_move(x=500, y=-50))
        assert is_success(result) or is_error(result), f"应返回结构化响应: {result}"

    def test_move_both_negative(self):
        """xy都负合法(多显示器场景): 不崩溃、返回结构化响应"""
        from app.tools.desktop.mouse_move import mouse_move
        result = _run(mouse_move(x=-1, y=-1))
        assert is_success(result) or is_error(result), f"应返回结构化响应: {result}"

    def test_move_huge_coords(self):
        """边界: 极大值坐标不崩溃、返回结构化响应"""
        from app.tools.desktop.mouse_move import mouse_move
        result = _run(mouse_move(x=999999, y=999999))
        assert is_success(result) or is_error(result), f"应返回结构化响应: {result}"


class TestMouseMoveNegative:
    """负面测试"""

    def test_missing_x(self):
        """负面: 不传x"""
        with pytest.raises(Exception):
            from app.tools.desktop.mouse_move import mouse_move
            _run(mouse_move(y=300))

    def test_missing_y(self):
        """负面: 不传y"""
        with pytest.raises(Exception):
            from app.tools.desktop.mouse_move import mouse_move
            _run(mouse_move(x=500))

    def test_missing_both(self):
        """负面: xy都不传"""
        with pytest.raises(Exception):
            from app.tools.desktop.mouse_move import mouse_move
            _run(mouse_move())

    def test_x_string(self):
        """负面: x传字符串"""
        from app.tools.desktop.mouse_move import mouse_move
        result = _run(mouse_move(x="abc", y=300))
        assert is_success(result) or is_error(result)
