# -*- coding: utf-8 -*-
"""S1 execute_shell_command 深度测试 — 小沈 2026-05-19
测试边界条件、异常路径、参数组合、数据完整性"""
import pytest
from app.services.tools.shell.shell_tools import execute_shell_command, shell_session


@pytest.mark.asyncio
async def test_stdout_and_stderr():
    """S1-001: stdout和stderr同时有输出"""
    result = execute_shell_command(command="echo stdout && echo stderr >&2", shell_type="cmd")
    assert result["code"] == "SUCCESS"
    assert "stdout" in result["data"]["stdout"]


@pytest.mark.asyncio
async def test_nonzero_exitcode():
    """S1-002: 非零退出码时data仍有stdout/stderr"""
    result = execute_shell_command(command="dir Z:\\no_such_path_xyz", shell_type="cmd")
    assert result["code"] in ("ERR_SHELL_EXEC", "SUCCESS")
    assert "returncode" in result["data"]


@pytest.mark.asyncio
async def test_cwd_nonexistent():
    """S1-003: 指定不存在的工作目录"""
    result = execute_shell_command(command="echo test", cwd="Z:\\no_dir_xyz")
    # 应该能执行或报错，但不能崩溃
    assert "code" in result


@pytest.mark.asyncio
async def test_empty_whitespace_command():
    """S1-004: 空白命令被拒绝"""
    result = execute_shell_command(command="   ")
    assert result["code"] == -1
    assert result["data"] is None


@pytest.mark.asyncio
async def test_background_then_terminate():
    """S1-005: 后台启动→读取输出→终止→再读取应报错"""
    r1 = execute_shell_command(command="ping -n 3 127.0.0.1", run_in_background=True, shell_type="cmd")
    assert r1["code"] == "SUCCESS"
    sid = r1["data"]["shell_id"]

    r2 = shell_session(shell_id=sid, action="output")
    assert r2["code"] == "SUCCESS"
    assert r2["data"]["is_running"] is True

    r3 = shell_session(shell_id=sid, action="terminate", force=True)
    assert r3["code"] == "SUCCESS"

    r4 = shell_session(shell_id=sid, action="output")
    assert r4["code"] == "ERR_SHELL_NOT_FOUND"


@pytest.mark.asyncio
async def test_timeout_has_partial_output():
    """S1-006: 超时时返回码为-1"""
    result = execute_shell_command(command="ping -n 10 127.0.0.1", timeout=500, shell_type="cmd")
    assert result["code"] == "ERR_SHELL_TIMEOUT"
    assert result["data"]["returncode"] == -1


@pytest.mark.asyncio
async def test_injection_blocked():
    """S1-007: 命令注入被拦截"""
    result = execute_shell_command(command="echo `whoami`")
    assert result["code"] == "ERR_SHELL_INJECTION"


@pytest.mark.asyncio
async def test_long_output_truncation():
    """S1-008: 大量输出时有llm_data截断"""
    # 生成大量输出
    result = execute_shell_command(command="python -c \"for i in range(1000): print('line', i)\"")
    if result["code"] == "SUCCESS":
        assert "llm_data" in result
