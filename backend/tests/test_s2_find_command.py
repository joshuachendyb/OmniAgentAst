# -*- coding: utf-8 -*-
"""S2 find_command 深度测试 — 小沈 2026-05-19"""
import pytest
from app.services.tools.shell.shell_tools import find_command


@pytest.mark.asyncio
async def test_find_python():
    """S2-001: 查找python命令"""
    result = find_command(command="python")
    assert result["code"] == "SUCCESS"
    assert result["data"]["available"] is True


@pytest.mark.asyncio
async def test_find_all_paths():
    """S2-002: 查找全部路径"""
    result = find_command(command="python", all_paths=True)
    assert result["code"] == "SUCCESS"
    assert result["data"]["count"] >= 1


@pytest.mark.asyncio
async def test_find_not_exist():
    """S2-003: 查找不存在的命令"""
    result = find_command(command="nonexistent_cmd_xyz")
    assert result["code"] == "SUCCESS"
    assert result["data"]["available"] is False
