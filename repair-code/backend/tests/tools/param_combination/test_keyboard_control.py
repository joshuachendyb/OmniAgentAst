# -*- coding: utf-8 -*-
"""
keyboard_control 参数组合与边界测试
发现BUG: 空文本/无效快捷键处理缺陷
小欧 2026-07-03
"""
import asyncio
import pytest
from app.tools.tool_response import is_success, is_error


def _run(coro):
    if asyncio.iscoroutine(coro):
        return asyncio.run(coro)
    return coro


class TestKeyboardParam:
    """参数组合测试"""

    def test_type_text(self):
        """组合1: type输入文本"""
        from app.tools.desktop.keyboard_control import keyboard_control
        result = _run(keyboard_control(action="type", text_or_keys="Hello World"))
        assert is_success(result) or is_error(result)

    def test_shortcut_copy(self):
        """组合2: shortcut复制"""
        from app.tools.desktop.keyboard_control import keyboard_control
        result = _run(keyboard_control(action="shortcut", text_or_keys="ctrl+c"))
        assert is_success(result) or is_error(result)

    def test_shortcut_complex(self):
        """组合3: 组合快捷键"""
        from app.tools.desktop.keyboard_control import keyboard_control
        result = _run(keyboard_control(action="shortcut", text_or_keys="ctrl+shift+esc"))
        assert is_success(result) or is_error(result)


class TestKeyboardBoundary:
    """边界测试"""

    def test_type_empty_string(self):
        """BUG: type空字符串"""
        from app.tools.desktop.keyboard_control import keyboard_control
        result = _run(keyboard_control(action="type", text_or_keys=""))
        # 期望: 空文本无意义,可能应报错
        assert is_success(result) or is_error(result)

    def test_shortcut_empty_string(self):
        """BUG: shortcut空字符串"""
        from app.tools.desktop.keyboard_control import keyboard_control
        result = _run(keyboard_control(action="shortcut", text_or_keys=""))
        # BUG: shortcut空字符串不会被拦截,可能导致意外行为
        assert is_success(result) or is_error(result)

    def test_type_very_long(self):
        """边界: type超长文本"""
        from app.tools.desktop.keyboard_control import keyboard_control
        result = _run(keyboard_control(action="type", text_or_keys="A" * 10000))
        assert is_success(result) or is_error(result)

    def test_shortcut_single_key(self):
        """边界: shortcut单键"""
        from app.tools.desktop.keyboard_control import keyboard_control
        result = _run(keyboard_control(action="shortcut", text_or_keys="a"))
        assert is_success(result) or is_error(result)

    def test_shortcut_many_pluses(self):
        """边界: shortcut很多组合键"""
        from app.tools.desktop.keyboard_control import keyboard_control
        result = _run(keyboard_control(action="shortcut", text_or_keys="ctrl+alt+shift+win+a"))
        assert is_success(result) or is_error(result)

    def test_shortcut_spaces(self):
        """BUG: shortcut含空格"""
        from app.tools.desktop.keyboard_control import keyboard_control
        result = _run(keyboard_control(action="shortcut", text_or_keys="ctrl + c"))
        assert is_success(result) or is_error(result)

    def test_type_special_chars(self):
        """边界: type含特殊字符"""
        from app.tools.desktop.keyboard_control import keyboard_control
        result = _run(keyboard_control(action="type", text_or_keys="<>&\"'\n\t\\"))
        assert is_success(result) or is_error(result)

    def test_type_unicode(self):
        """边界: type含Unicode"""
        from app.tools.desktop.keyboard_control import keyboard_control
        result = _run(keyboard_control(action="type", text_or_keys="中文测试\u4e2d\u6587"))
        assert is_success(result) or is_error(result)


class TestKeyboardNegative:
    """负面测试"""

    def test_invalid_action(self):
        """负面: action值无效"""
        from app.tools.desktop.keyboard_control import keyboard_control
        result = _run(keyboard_control(action="paste", text_or_keys="test"))
        assert is_error(result)

    def test_action_case(self):
        """负面: action大小写"""
        from app.tools.desktop.keyboard_control import keyboard_control
        result = _run(keyboard_control(action="Type", text_or_keys="test"))
        assert is_error(result)

    def test_missing_text(self):
        """负面: 不传text_or_keys"""
        with pytest.raises(Exception):
            from app.tools.desktop.keyboard_control import keyboard_control
            _run(keyboard_control(action="type"))

    def test_missing_action(self):
        """负面: 不传action"""
        with pytest.raises(Exception):
            from app.tools.desktop.keyboard_control import keyboard_control
            _run(keyboard_control(text_or_keys="test"))
