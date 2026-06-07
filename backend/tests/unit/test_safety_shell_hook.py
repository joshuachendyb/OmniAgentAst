# -*- coding: utf-8 -*-
"""safety/shell/command_safety_hook.py 测试 — 小健 2026-05-30"""

import pytest
from unittest.mock import MagicMock, patch
from app.services.safety.shell.command_safety_hook import CommandSafetyHook, get_shell_safety_hook


class TestCommandSafetyHook:
    """CommandSafetyHook 深度测试"""

    def test_check_safe_command(self):
        """正常：安全命令通过"""
        mock_parser = MagicMock()
        mock_parser.parse.return_value = {
            "operation": "read", "direction": "read",
            "sources": ["file.txt"], "targets": []
        }
        hook = CommandSafetyHook(parser=mock_parser)
        result = hook.check("cat", {"command": "cat file.txt"})
        assert result["is_safe"] is True
        assert result["risk_score"] == 0.3

    def test_check_dangerous_command(self):
        """正常：危险命令被拦截"""
        mock_parser = MagicMock()
        mock_parser.parse.return_value = {
            "operation": "delete", "direction": "write",
            "sources": ["/etc"], "targets": []
        }
        hook = CommandSafetyHook(parser=mock_parser)
        result = hook.check("rm", {"command": "rm -rf /"})
        assert result["is_safe"] is False
        assert result["risk_score"] == 0.8

    def test_check_dangerous_operation_safe_direction(self):
        """边界：危险操作但方向非write时通过"""
        mock_parser = MagicMock()
        mock_parser.parse.return_value = {
            "operation": "delete", "direction": "read",
            "sources": [], "targets": []
        }
        hook = CommandSafetyHook(parser=mock_parser)
        result = hook.check("test", {"command": "test"})
        assert result["is_safe"] is True

    def test_check_unknown_operation(self):
        """边界：未知操作返回低风险"""
        mock_parser = MagicMock()
        mock_parser.parse.return_value = {
            "operation": "unknown", "direction": "unknown",
            "sources": [], "targets": []
        }
        hook = CommandSafetyHook(parser=mock_parser)
        result = hook.check("weird", {"command": "weird"})
        assert result["is_safe"] is True

    def test_check_empty_command(self):
        """边界：空命令"""
        mock_parser = MagicMock()
        mock_parser.parse.return_value = {
            "operation": "unknown", "direction": "unknown"
        }
        hook = CommandSafetyHook(parser=mock_parser)
        result = hook.check("", {"command": ""})
        assert "risk_score" in result
        assert "is_safe" in result

    def test_check_missing_params(self):
        """边界：params中无command键"""
        mock_parser = MagicMock()
        mock_parser.parse.return_value = {
            "operation": "unknown", "direction": "read"
        }
        hook = CommandSafetyHook(parser=mock_parser)
        result = hook.check("echo", {})
        assert "risk_score" in result

    def test_on_before_execute_not_implemented(self):
        """界面：未实现on_before_execute返回None"""
        hook = CommandSafetyHook(parser=MagicMock())
        result = pytest.mark.asyncio(lambda: None)  # skip
        # SafetyHook基类默认返回None
        import asyncio
        loop = asyncio.new_event_loop()
        try:
            r = loop.run_until_complete(hook.on_before_execute("action", {}))
            assert r is None
        finally:
            loop.close()


class TestGetShellSafetyHook:
    """get_shell_safety_hook 单例测试"""

    def test_singleton(self):
        """正常：多次调用返回相同实例"""
        h1 = get_shell_safety_hook()
        h2 = get_shell_safety_hook()
        assert h1 is h2

    def test_has_parser(self):
        """正常：自动加载CommandParser"""
        hook = get_shell_safety_hook()
        assert hook._parser is not None
