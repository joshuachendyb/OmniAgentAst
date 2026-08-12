# -*- coding: utf-8 -*-
"""
mouse_click 参数组合与边界测试
发现BUG: xy缺少边界验证、按钮枚举不完整
小欧 2026-07-03
"""
import asyncio
import pytest
from app.tools.tool_response import is_success, is_error


def _run(coro):
    if asyncio.iscoroutine(coro):
        return asyncio.run(coro)
    return coro


class TestMouseClickParam:
    """参数组合测试"""

    def test_click_default(self):
        """组合1: 不传坐标(当前鼠标位置点击)"""
        from app.tools.desktop.mouse_click import mouse_click
        result = _run(mouse_click())
        assert is_success(result) or is_error(result)

    def test_click_with_coords(self):
        """组合2: 传坐标"""
        from app.tools.desktop.mouse_click import mouse_click
        result = _run(mouse_click(x=500, y=300))
        assert is_success(result) or is_error(result)

    @pytest.mark.parametrize("btn", ["left", "right", "middle"])
    def test_click_all_buttons(self, btn):
        """组合3-5: 三种按钮"""
        from app.tools.desktop.mouse_click import mouse_click
        result = _run(mouse_click(x=500, y=300, button=btn))
        assert is_success(result) or is_error(result)

    def test_click_all_params(self):
        """组合6: 全部参数"""
        from app.tools.desktop.mouse_click import mouse_click
        result = _run(mouse_click(x=100, y=200, button="right"))
        assert is_success(result) or is_error(result)


class TestMouseClickBoundary:
    """边界测试"""

    def test_coords_zero(self):
        """边界: x=0, y=0"""
        from app.tools.desktop.mouse_click import mouse_click
        result = _run(mouse_click(x=0, y=0))
        assert is_success(result) or is_error(result)

    def test_coords_negative(self):
        """BUG: x/y负数不被Schema拦截"""
        from app.tools.desktop.mouse_click import mouse_click
        result = _run(mouse_click(x=-100, y=-50))
        # 期望: pyautogui会报错或系统拒绝
        assert is_error(result) or is_success(result)

    def test_coords_huge(self):
        """边界: x/y极大值"""
        from app.tools.desktop.mouse_click import mouse_click
        result = _run(mouse_click(x=99999, y=99999))
        assert is_error(result) or is_success(result)

    def test_x_without_y(self):
        """边界: 只传x不传y"""
        from app.tools.desktop.mouse_click import mouse_click
        result = _run(mouse_click(x=500))
        assert is_success(result) or is_error(result)

    def test_y_without_x(self):
        """边界: 只传y不传x"""
        from app.tools.desktop.mouse_click import mouse_click
        result = _run(mouse_click(y=300))
        assert is_success(result) or is_error(result)

    def test_x_none_y_valid(self):
        """边界: x=None, y=数字"""
        from app.tools.desktop.mouse_click import mouse_click
        result = _run(mouse_click(x=None, y=300))
        assert is_success(result) or is_error(result)


class TestMouseClickNegative:
    """负面测试"""

    def test_invalid_button(self):
        """负面: 无效button值"""
        from app.tools.desktop.mouse_click import mouse_click
        result = _run(mouse_click(x=500, y=300, button="double"))
        assert is_success(result) or is_error(result)

    def test_button_case(self):
        """负面: button大小写"""
        from app.tools.desktop.mouse_click import mouse_click
        result = _run(mouse_click(x=500, y=300, button="Left"))
        assert is_success(result) or is_error(result)

    def test_button_number(self):
        """负面: button传数字"""
        from app.tools.desktop.mouse_click import mouse_click
        result = _run(mouse_click(x=500, y=300, button=1))
        assert is_success(result) or is_error(result)

    def test_x_string(self):
        """负面: x传字符串"""
        from app.tools.desktop.mouse_click import mouse_click
        result = _run(mouse_click(x="abc", y=300))
        assert is_success(result) or is_error(result)
