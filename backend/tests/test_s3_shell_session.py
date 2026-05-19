# -*- coding: utf-8 -*-
"""S3 shell_session 深度测试 — 小沈 2026-05-19"""
import pytest
from app.services.tools.shell.shell_tools import shell_session, execute_shell_command


@pytest.mark.asyncio
async def test_session_not_found():
    """S3-001: 不存在的会话报错"""
    result = shell_session(shell_id="nonexistent_id")
    assert result["code"] == "ERR_SHELL_NOT_FOUND"


@pytest.mark.asyncio
async def test_session_invalid_action():
    """S3-002: 非法action被拒绝"""
    result = shell_session(shell_id="test", action="invalid")
    assert result["code"] == "ERR_INVALID_ACTION"


@pytest.mark.asyncio
async def test_session_background_lifecycle():
    """S3-003: 后台命令完整生命週期"""
    # 启动后台命令
    r1 = execute_shell_command(command="ping -n 3 127.0.0.1", run_in_background=True, shell_type="cmd")
    assert r1["code"] == "SUCCESS"
    sid = r1["data"]["shell_id"]

    # 读取输出
    r2 = shell_session(shell_id=sid, action="output")
    assert r2["code"] == "SUCCESS"
    assert r2["data"]["is_running"] is True

    # 终止会话
    r3 = shell_session(shell_id=sid, action="terminate", force=True)
    assert r3["code"] == "SUCCESS"
