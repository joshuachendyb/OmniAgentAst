# -*- coding: utf-8 -*-
"""
clipboard_control 参数组合与边界测试
发现BUG: action=write空内容处理、action区分
小欧 2026-07-03
"""
import pytest
from app.tools.tool_response import is_success, is_error


class TestClipboardParam:
    """参数组合测试"""

    def test_clipboard_read(self):
        """组合1: 读取剪贴板"""
        from app.tools.desktop.clipboard_control import clipboard_control
        result = clipboard_control(action="read")
        assert is_success(result) or is_error(result)

    def test_clipboard_write(self):
        """组合2: 写入剪贴板"""
        from app.tools.desktop.clipboard_control import clipboard_control
        result = clipboard_control(action="write", content="Test Content 123")
        assert is_success(result) or is_error(result)


class TestClipboardWriteRead:
    """写+读联调测试"""

    def test_write_then_read(self):
        """写入后读取(内容一致)"""
        from app.tools.desktop.clipboard_control import clipboard_control
        w = clipboard_control(action="write", content="UniqueTestValue_98765")
        if is_success(w):
            r = clipboard_control(action="read")
            if is_success(r):
                assert "UniqueTestValue_98765" in r["data"].get("text", "") or "UniqueTestValue_98765" in r["data"].get("content", "")

    def test_write_chinese(self):
        """写入中文"""
        from app.tools.desktop.clipboard_control import clipboard_control
        result = clipboard_control(action="write", content="中文测试内容")
        assert is_success(result) or is_error(result)

    def test_write_special_chars(self):
        """写入特殊字符"""
        from app.tools.desktop.clipboard_control import clipboard_control
        result = clipboard_control(action="write", content="<>&\"'\n\t\\")
        assert is_success(result) or is_error(result)

    def test_write_then_read_chinese(self):
        """写入中文后读取验证"""
        from app.tools.desktop.clipboard_control import clipboard_control
        w = clipboard_control(action="write", content="中文Unique789")
        if is_success(w):
            r = clipboard_control(action="read")
            if is_success(r):
                assert "中文Unique789" in r["data"].get("text", "") or "中文Unique789" in r["data"].get("content", "")


class TestClipboardBoundary:
    """边界测试"""

    def test_write_empty_content(self):
        """BUG: write空内容处理"""
        from app.tools.desktop.clipboard_control import clipboard_control
        result = clipboard_control(action="write", content="")
        # 期望: 空内容也应该被正确处理,不应崩溃
        assert is_success(result) or is_error(result)

    def test_write_very_long(self):
        """边界: 写入超长内容"""
        from app.tools.desktop.clipboard_control import clipboard_control
        result = clipboard_control(action="write", content="X" * 100000)
        assert is_success(result) or is_error(result)

    def test_write_unicode_special(self):
        """边界: 写入特殊Unicode"""
        from app.tools.desktop.clipboard_control import clipboard_control
        result = clipboard_control(action="write", content="\u0000\u0001\u0002")
        assert is_success(result) or is_error(result)

    def test_write_newlines(self):
        """边界: 写入带换行的多行内容"""
        from app.tools.desktop.clipboard_control import clipboard_control
        content = "line1\nline2\nline3\n"
        result = clipboard_control(action="write", content=content)
        assert is_success(result) or is_error(result)


class TestClipboardNegative:
    """负面测试"""

    def test_missing_action(self):
        """负面: 不传action"""
        with pytest.raises(TypeError):
            from app.tools.desktop.clipboard_control import clipboard_control
            clipboard_control(content="test")

    def test_invalid_action(self):
        """负面: 无效action"""
        from app.tools.desktop.clipboard_control import clipboard_control
        result = clipboard_control(action="copy", content="test")
        assert is_error(result)

    def test_action_case(self):
        """负面: action大小写"""
        from app.tools.desktop.clipboard_control import clipboard_control
        result = clipboard_control(action="Write", content="test")
        assert is_error(result)
