# -*- coding: utf-8 -*-
"""S3 shell_session 深度测试 — 小沈 2026-05-19"""
import pytest
from app.services.tools.shell.shell_tools import shell_session, execute_shell_command


@pytest.mark.asyncio
async def test_nonexistent_session():
    """S3-001: 不存在的会话"""
    result = shell_session(shell_id="no_such_id_xyz")
    assert result["code"] == "ERR_SHELL_NOT_FOUND"


@pytest.mark.asyncio
async def test_invalid_action():
    """S3-002: 非法action"""
    result = shell_session(shell_id="test", action="invalid")
    assert result["code"] == "ERR_INVALID_ACTION"


@pytest.mark.asyncio
async def test_terminate_nonexistent():
    """S3-003: 终止不存在的会话"""
    result = shell_session(shell_id="fake_id", action="terminate")
    assert result["code"] == "ERR_SHELL_NOT_FOUND"


@pytest.mark.asyncio
async def test_output_filter():
    """S3-004: 正则过滤输出"""
    r1 = execute_shell_command(command="echo line1 && echo ERROR_line2 && echo line3", run_in_background=True, shell_type="cmd")
    assert r1["code"] == "SUCCESS"
    sid = r1["data"]["shell_id"]

    import time
    time.sleep(0.5)

    r2 = shell_session(shell_id=sid, action="output", filter="ERROR")
    assert r2["code"] == "SUCCESS"
    assert "ERROR" in r2["data"]["stdout"]

    shell_session(shell_id=sid, action="terminate", force=True)


@pytest.mark.asyncio
async def test_output_tail():
    """S3-005: tail=True取最后行"""
    r1 = execute_shell_command(
        command="python -c \"for i in range(20): print(f'line{i}')\"",
        run_in_background=True
    )
    assert r1["code"] == "SUCCESS"
    sid = r1["data"]["shell_id"]

    import time
    time.sleep(1)

    r2 = shell_session(shell_id=sid, action="output", tail=True, max_lines=5)
    assert r2["code"] == "SUCCESS"
    lines = r2["data"]["stdout"].strip().split("\n")
    assert len(lines) <= 5

    shell_session(shell_id=sid, action="terminate", force=True)


@pytest.mark.asyncio
async def test_double_terminate():
    """S3-006: 重复终止同一会话"""
    r1 = execute_shell_command(command="ping -n 3 127.0.0.1", run_in_background=True, shell_type="cmd")
    assert r1["code"] == "SUCCESS"
    sid = r1["data"]["shell_id"]

    r2 = shell_session(shell_id=sid, action="terminate", force=True)
    assert r2["code"] == "SUCCESS"

    # 第二次终止应返回会话不存在
    r3 = shell_session(shell_id=sid, action="terminate")
    assert r3["code"] == "ERR_SHELL_NOT_FOUND"


@pytest.mark.asyncio
async def test_auto_cleanup_on_exit():
    """S3-007: 进程自然退出后output自动清理_background_shells"""
    r1 = execute_shell_command(command="echo done", run_in_background=True, shell_type="cmd")
    assert r1["code"] == "SUCCESS"
    sid = r1["data"]["shell_id"]

    import time
    time.sleep(1)  # 等待进程退出

    r2 = shell_session(shell_id=sid, action="output")
    assert r2["code"] == "SUCCESS"

    # 再次读取——进程已退出且已清理，应报错
    r3 = shell_session(shell_id=sid, action="output")
    assert r3["code"] == "ERR_SHELL_NOT_FOUND"
