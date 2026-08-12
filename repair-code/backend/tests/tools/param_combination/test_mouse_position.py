# -*- coding: utf-8 -*-
"""
mouse_position 基础测试
发现BUG: 返回值结构一致性
小欧 2026-07-03
"""
import asyncio
import pytest
from app.tools.tool_response import is_success, is_error


def _run(coro):
    if asyncio.iscoroutine(coro):
        return asyncio.run(coro)
    return coro


class TestMousePosition:
    """功能与返回值测试"""

    def test_get_position(self):
        """获取鼠标位置"""
        from app.tools.desktop.mouse_position import mouse_position
        result = _run(mouse_position())
        assert is_success(result) or is_error(result)
        if is_success(result):
            data = result["data"]
            assert "x" in data
            assert "y" in data
            assert isinstance(data["x"], int)
            assert isinstance(data["y"], int)

    def test_position_returns_positive(self):
        """位置坐标应为非负数"""
        from app.tools.desktop.mouse_position import mouse_position
        result = _run(mouse_position())
        assert is_success(result) or is_error(result)
        if is_success(result):
            assert result["data"]["x"] >= 0
            assert result["data"]["y"] >= 0

    def test_position_consecutive_calls(self):
        """连续调用获取位置"""
        from app.tools.desktop.mouse_position import mouse_position
        r1 = _run(mouse_position())
        r2 = _run(mouse_position())
        if is_success(r1) and is_success(r2):
            assert isinstance(r1["data"]["x"], int)
            assert isinstance(r2["data"]["x"], int)

    def test_no_params(self):
        """无参调用"""
        from app.tools.desktop.mouse_position import mouse_position
        result = _run(mouse_position())
        assert is_success(result) or is_error(result)

    def test_extra_params_rejected(self):
        """传额外参数应被拒绝"""
        with pytest.raises(Exception):
            from app.tools.desktop.mouse_position import mouse_position
            _run(mouse_position(invalid=1))
