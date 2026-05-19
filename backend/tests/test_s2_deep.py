# -*- coding: utf-8 -*-
"""S2 find_command 深度测试 — 小沈 2026-05-19"""
import pytest
from app.services.tools.shell.shell_tools import find_command


@pytest.mark.asyncio
async def test_find_known_command():
    """S2-001: 查找python——应返回可用"""
    result = find_command(command="python")
    assert result["code"] == "SUCCESS"
    assert result["data"]["available"] is True
    assert result["data"]["path"] is not None


@pytest.mark.asyncio
async def test_find_unknown_command():
    """S2-002: 查找不存在的命令——返回不可用但不报错"""
    result = find_command(command="this_command_does_not_exist_xyz")
    assert result["code"] == "SUCCESS"
    assert result["data"]["available"] is False
    assert result["data"]["path"] is None


@pytest.mark.asyncio
async def test_find_all_paths_known():
    """S2-003: all_paths=True查python——返回列表"""
    result = find_command(command="python", all_paths=True)
    assert result["code"] == "SUCCESS"
    assert result["data"]["count"] >= 1
    assert len(result["data"]["paths"]) == result["data"]["count"]


@pytest.mark.asyncio
async def test_find_all_paths_unknown():
    """S2-004: all_paths=True查不存在命令——空列表"""
    result = find_command(command="nonexistent_xyz", all_paths=True)
    assert result["code"] == "SUCCESS"
    assert result["data"]["count"] == 0
    assert result["data"]["paths"] == []


@pytest.mark.asyncio
async def test_find_empty_command():
    """S2-005: 空命令——shutil.which返回None"""
    result = find_command(command="")
    assert result["code"] == "SUCCESS"
    assert result["data"]["available"] is False


@pytest.mark.asyncio
async def test_find_next_actions():
    """S2-006: 验证next_actions引导execute_shell_command"""
    result = find_command(command="python")
    assert "next_actions" in result
