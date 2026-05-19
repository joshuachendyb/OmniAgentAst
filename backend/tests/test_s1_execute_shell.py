# -*- coding: utf-8 -*-
"""S1 execute_shell_command 深度测试 — 小沈 2026-05-19"""
import pytest
from app.services.tools.shell.shell_tools import execute_shell_command

def _ok(d): return d


@pytest.mark.asyncio
async def test_shell_basic():
    """S1-001: 基本命令执行"""
    result = execute_shell_command(command="echo hello")
    assert result["code"] == "SUCCESS"
    assert "hello" in result["data"]["stdout"]


@pytest.mark.asyncio
async def test_shell_cmd():
    """S1-002: CMD环境执行"""
    result = execute_shell_command(command="echo hello", shell_type="cmd")
    assert result["code"] == "SUCCESS"


@pytest.mark.asyncio
async def test_shell_invalid_cmd():
    """S1-003: 空命令被拒绝"""
    result = execute_shell_command(command="")
    assert result["code"] != "SUCCESS"


@pytest.mark.asyncio
async def test_shell_invalid_shell_type():
    """S1-004: 非法shell_type被拒绝"""
    result = execute_shell_command(command="echo", shell_type="bash")
    assert result["code"] == -1


@pytest.mark.asyncio
async def test_shell_injection():
    """S1-005: Shell注入检测"""
    result = execute_shell_command(command="echo $(whoami)")
    assert result["code"] == "ERR_SHELL_INJECTION"


@pytest.mark.asyncio
async def test_shell_timeout():
    """S1-006: 超时处理"""
    result = execute_shell_command(command="ping -n 10 127.0.0.1", timeout=1000)
    assert result["code"] == "ERR_SHELL_TIMEOUT"


@pytest.mark.asyncio
async def test_shell_fail():
    """S1-007: 失败命令"""
    result = execute_shell_command(command="nonexistent_command_xyz")
    assert result["code"] in ("ERR_SHELL_EXEC", "ERR_SHELL_TIMEOUT")
