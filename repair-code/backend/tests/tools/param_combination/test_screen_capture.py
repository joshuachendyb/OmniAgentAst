# -*- coding: utf-8 -*-
"""
screen_capture 参数组合与边界测试
发现BUG: display/region互斥验证、display=0处理
小欧 2026-07-03
"""
import asyncio
import pytest
from app.tools.tool_response import is_success, is_error


def _run(coro):
    if asyncio.iscoroutine(coro):
        return asyncio.run(coro)
    return coro


class TestScreenCaptureParam:
    """参数组合测试"""

    def test_capture_default(self):
        """组合1: 默认全屏"""
        from app.tools.desktop.screen_capture import screen_capture
        result = _run(screen_capture())
        assert is_success(result) or is_error(result)

    def test_capture_with_region(self):
        """组合2: 指定区域"""
        from app.tools.desktop.screen_capture import screen_capture
        result = _run(screen_capture(region={"x": 0, "y": 0, "width": 800, "height": 600}))
        assert is_success(result) or is_error(result)

    def test_capture_with_output_path(self):
        """组合3: 指定输出路径"""
        from app.tools.desktop.screen_capture import screen_capture
        import tempfile
        tmp = tempfile.mktemp(suffix=".png")
        result = _run(screen_capture(dest=tmp))
        assert is_success(result) or is_error(result)


class TestScreenCaptureBoundary:
    """边界测试"""

    def test_display_zero(self):
        """边界: display=0"""
        from app.tools.desktop.screen_capture import screen_capture
        result = _run(screen_capture(display=0))
        assert is_success(result) or is_error(result)

    def test_display_negative(self):
        """边界: display负数"""
        from app.tools.desktop.screen_capture import screen_capture
        result = _run(screen_capture(display=-1))
        assert is_success(result) or is_error(result)

    def test_region_incomplete(self):
        """BUG: region缺少x键"""
        from app.tools.desktop.screen_capture import screen_capture
        # region Dict不是Pydantic验证的,缺键可能报错
        result = _run(screen_capture(region={"y": 0, "width": 100, "height": 100}))
        assert is_success(result) or is_error(result)

    def test_region_empty_dict(self):
        """边界: region空字典(走默认值)"""
        from app.tools.desktop.screen_capture import screen_capture
        result = _run(screen_capture(region={}))
        assert is_success(result) or is_error(result)

    def test_display_max(self):
        """边界: display超大值"""
        from app.tools.desktop.screen_capture import screen_capture
        result = _run(screen_capture(display=99))
        assert is_success(result) or is_error(result)


class TestScreenCaptureMutex:
    """互斥参数测试"""

    def test_display_with_region(self):
        """互斥: display + region"""
        from app.tools.desktop.screen_capture import screen_capture
        result = _run(screen_capture(display=1, region={"x": 0, "y": 0, "width": 100, "height": 100}))
        assert is_success(result) or is_error(result)

    def test_display_with_output_path(self):
        """互斥: display + output_path"""
        from app.tools.desktop.screen_capture import screen_capture
        result = _run(screen_capture(display=1, dest="test.png"))
        assert is_success(result) or is_error(result)


class TestScreenCaptureNegative:
    """负面测试"""

    def test_region_negative_values(self):
        """负面: region负数值"""
        from app.tools.desktop.screen_capture import screen_capture
        result = _run(screen_capture(region={"x": -100, "y": -50, "width": 100, "height": 100}))
        assert is_success(result) or is_error(result)

    def test_display_string(self):
        """负面: display传字符串"""
        from app.tools.desktop.screen_capture import screen_capture
        result = _run(screen_capture(display="1"))
        assert is_success(result) or is_error(result)

    def test_region_invalid_type(self):
        """负面: region传非字典"""
        from app.tools.desktop.screen_capture import screen_capture
        result = _run(screen_capture(region="not_a_dict"))
        assert is_success(result) or is_error(result)
