# -*- coding: utf-8 -*-
"""
set_window_state 参数组合与边界测试
发现BUG: 无效action处理、不存在的窗口各状态的错误信息一致性
小欧 2026-07-03
"""
import asyncio
import pytest
from app.tools.tool_response import is_success, is_error


def _run(coro):
    if asyncio.iscoroutine(coro):
        return asyncio.run(coro)
    return coro


class TestSetWindowStateParams:
    """5种action的测试"""

    @pytest.mark.parametrize("action", ["maximize", "minimize", "restore", "topmost", "unpin"])
    def test_nonexistent_window_all_actions(self, action):
        """5种action对不存在窗口的错误处理"""
        from app.tools.desktop.set_window_state import set_window_state
        result = _run(set_window_state(window_title="NONEXISTENT_WIN_12345", action=action))
        assert is_error(result)
        assert result.get("llm_data", {}).get("status", {}).get("exec_code") == "error"

    @pytest.mark.parametrize("action", ["maximize", "minimize", "restore", "topmost", "unpin"])
    def test_empty_title_all_actions(self, action):
        """5种action对空标题的处理"""
        from app.tools.desktop.set_window_state import set_window_state
        result = _run(set_window_state(window_title="", action=action))
        assert is_error(result)


class TestSetWindowStateBoundary:
    """边界测试"""

    def test_title_very_long(self):
        """边界: window_title超长"""
        from app.tools.desktop.set_window_state import set_window_state
        result = _run(set_window_state(window_title="A" * 10000, action="maximize"))
        assert is_error(result)

    def test_title_whitespace_only(self):
        """边界: window_title只含空白"""
        from app.tools.desktop.set_window_state import set_window_state
        result = _run(set_window_state(window_title="   ", action="minimize"))
        assert is_error(result)

    def test_title_unicode(self):
        """边界: window_title含Unicode"""
        from app.tools.desktop.set_window_state import set_window_state
        result = _run(set_window_state(window_title="\u4e2d\u6587\u7a97\u53e3", action="restore"))
        assert is_error(result)

    def test_title_special_chars(self):
        """边界: window_title含特殊字符"""
        from app.tools.desktop.set_window_state import set_window_state
        result = _run(set_window_state(window_title="test<>:\"/\\|?*", action="topmost"))
        assert is_error(result)

    def test_action_case_sensitivity(self):
        """BUG: action大小写是否敏感"""
        from app.tools.desktop.set_window_state import set_window_state
        result = _run(set_window_state(window_title="test", action="MAXIMIZE"))
        assert is_error(result)

    def test_action_extra_spaces(self):
        """BUG: action含空格"""
        from app.tools.desktop.set_window_state import set_window_state
        result = _run(set_window_state(window_title="test", action=" maximize "))
        assert is_error(result)


class TestSetWindowStateNegative:
    """负面测试"""

    def test_invalid_action(self):
        """负面: 无效action值"""
        from app.tools.desktop.set_window_state import set_window_state
        result = _run(set_window_state(window_title="test", action="invalid_action"))
        assert is_error(result)

    def test_missing_title(self):
        """负面: 不传title"""
        with pytest.raises(Exception):
            from app.tools.desktop.set_window_state import set_window_state
            _run(set_window_state(action="maximize"))

    def test_missing_action(self):
        """负面: 不传action"""
        with pytest.raises(Exception):
            from app.tools.desktop.set_window_state import set_window_state
            _run(set_window_state(window_title="test"))

    def test_title_non_string(self):
        """负面: title传数字"""
        from app.tools.desktop.set_window_state import set_window_state
        result = _run(set_window_state(window_title=123, action="maximize"))
        assert is_error(result)
