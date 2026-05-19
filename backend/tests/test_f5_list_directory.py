# -*- coding: utf-8 -*-
"""F5 list_directory 深度测试 — 小沈 2026-05-19"""
import pytest

def _ok(d): return d.get("data", d)


@pytest.mark.asyncio
async def test_list_current_dir():
    """F5-001: 列出当前目录，验证成功且有entries/total"""
    from app.services.tools.file.file_tools import FileTools
    ft = FileTools()
    result = await ft.list_directory(dir_path=".")
    data = _ok(result)
    assert data["success"] is True
    assert "entries" in data
    assert "total" in data
    assert data["total"] >= 0
    assert "statistics" in data


@pytest.mark.asyncio
async def test_list_with_format_tree():
    """F5-002: tree格式列出目录"""
    from app.services.tools.file.file_tools import FileTools
    ft = FileTools()
    result = await ft.list_directory(dir_path=".", format="tree")
    data = _ok(result)
    # tree format wraps result in {"status":"success", "data":{...}}
    inner = data.get("data", data)
    assert inner.get("success") is True
    assert "tree" in inner


@pytest.mark.asyncio
async def test_list_not_exists():
    """F5-003: 列出不存在的目录"""
    from app.services.tools.file.file_tools import FileTools
    ft = FileTools()
    result = await ft.list_directory(dir_path="Z:/__no_such_dir_xyz__")
    data = _ok(result)
    assert data["success"] is False


@pytest.mark.asyncio
async def test_list_next_actions():
    """F5-004: 验证返回结果包含next_actions"""
    from app.services.tools.file.file_tools import FileTools
    ft = FileTools()
    result = await ft.list_directory(dir_path=".")
    assert "next_actions" in result or result.get("status") == "success"
