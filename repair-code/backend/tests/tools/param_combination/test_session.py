# -*- coding: utf-8 -*-
"""
shell 命令工具 参数组合与边界测试
(原 session 持久会话工具已在重构中删除, 改为测试当前 shell() 命令工具的参数健壮性)
小欧 2026-07-03 / 2026-07-12 适配当前 shell() 行为 - 小欧
"""
import asyncio
import pytest
from app.tools.tool_response import is_success, is_error


def _run(coro):
    if asyncio.iscoroutine(coro):
        return asyncio.run(coro)
    return coro


class TestShellParam:
    """参数组合测试"""

    def test_shell_empty_command(self):
        """组合1: 空命令"""
        from app.tools.fundamental.execute_shell_command import shell
        result = _run(shell(""))
        assert is_error(result)

    def test_shell_invalid_shell_type(self):
        """组合2: 非法shell_type"""
        from app.tools.fundamental.execute_shell_command import shell
        result = _run(shell("echo hi", shell_type="invalid_type"))
        assert is_error(result)

    def test_shell_invalid_timeout(self):
        """组合3: 非法timeout"""
        from app.tools.fundamental.execute_shell_command import shell
        result = _run(shell("echo hi", timeout=0))
        assert is_error(result)

    def test_shell_unicode_command(self):
        """组合4: unicode命令不崩溃"""
        from app.tools.fundamental.execute_shell_command import shell
        result = _run(shell("echo 中文测试"))
        assert is_success(result) or is_error(result)


class TestShellBoundary:
    """边界测试"""

    def test_shell_very_long_command(self):
        """边界: 超长命令"""
        from app.tools.fundamental.execute_shell_command import shell
        result = _run(shell("echo " + "A" * 10000))
        assert is_success(result) or is_error(result)

    def test_shell_unicode_id(self):
        """边界: 命令含Unicode"""
        from app.tools.fundamental.execute_shell_command import shell
        result = _run(shell("echo \u4e2d\u6587"))
        assert is_success(result) or is_error(result)

    def test_shell_special_chars(self):
        """边界: 命令含特殊字符"""
        from app.tools.fundamental.execute_shell_command import shell
        result = _run(shell("echo test!@#$%^&*()"))
        assert is_success(result) or is_error(result)


class TestShellNegative:
    """负面测试"""

    def test_shell_missing_command(self):
        """负面: 不传command"""
        from app.tools.fundamental.execute_shell_command import shell
        with pytest.raises(TypeError):
            _run(shell())

    def test_shell_invalid_shell_type_negative(self):
        """负面: 非法shell_type"""
        from app.tools.fundamental.execute_shell_command import shell
        result = _run(shell("test", shell_type="invalid"))
        assert is_error(result)

    def test_shell_timeout_out_of_range(self):
        """负面: timeout超范围"""
        from app.tools.fundamental.execute_shell_command import shell
        result = _run(shell("test", timeout=99999))
        assert is_error(result)
