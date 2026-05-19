# -*- coding: utf-8 -*-
"""F6 search_files 深度测试 — 小沈 2026-05-19"""
import pytest
import tempfile
from pathlib import Path

def _ok(d): return d.get("data", d)


@pytest.mark.asyncio
async def test_search_py_files():
    """F6-001: 在当前目录搜索.py文件"""
    from app.services.tools.file.file_tools import FileTools
    import os
    ft = FileTools()
    result = await ft.search_files(pattern="*.py", search_dir=os.getcwd())
    data = _ok(result)
    assert data["success"] is True
    assert data["total"] > 0


@pytest.mark.asyncio
async def test_search_with_dir():
    """F6-002: 在临时目录搜索创建的文件"""
    from app.services.tools.file.file_tools import FileTools
    import os
    ft = FileTools()
    d = Path(tempfile.mkdtemp())
    (d / "test_a.txt").write_text("")
    (d / "test_b.txt").write_text("")

    result = await ft.search_files(pattern="*.txt", search_dir=str(d))
    data = _ok(result)
    assert data["success"] is True
    assert data["total"] >= 2


@pytest.mark.asyncio
async def test_search_no_match():
    """F6-003: 搜索不存在的模式"""
    from app.services.tools.file.file_tools import FileTools
    ft = FileTools()
    result = await ft.search_files(pattern="ZZZ_NO_MATCH_XYZ")
    data = _ok(result)
    assert data["success"] is True
    assert data["total"] == 0
