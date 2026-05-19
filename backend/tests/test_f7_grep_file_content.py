# -*- coding: utf-8 -*-
"""F7 grep_file_content 深度测试 — 小沈 2026-05-19"""
import pytest
import tempfile
from pathlib import Path

def _ok(d): return d.get("data", d)


@pytest.mark.asyncio
async def test_grep_basic():
    """F7-001: 基本正则搜索"""
    from app.services.tools.file.file_tools import FileTools
    ft = FileTools()
    d = Path(tempfile.mkdtemp())
    (d / "search_test.py").write_text("def hello():\n    return 'world'\n")

    result = await ft.grep_file_content(pattern=r"def hello", search_dir=str(d))
    data = _ok(result)
    assert data["success"] is True
    assert data["total_matches"] >= 1


@pytest.mark.asyncio
async def test_grep_no_match():
    """F7-002: 搜索不存在的模式"""
    from app.services.tools.file.file_tools import FileTools
    ft = FileTools()
    d = Path(tempfile.mkdtemp())
    (d / "empty.txt").write_text("nothing here")

    result = await ft.grep_file_content(pattern="ZZZ_NO_MATCH_XYZ", search_dir=str(d))
    data = _ok(result)
    assert data["success"] is True
    assert data["total_matches"] == 0


@pytest.mark.asyncio
async def test_grep_ignore_case():
    """F7-003: 不区分大小写搜索"""
    from app.services.tools.file.file_tools import FileTools
    ft = FileTools()
    d = Path(tempfile.mkdtemp())
    (d / "case_test.py").write_text("HELLO World\n")

    result = await ft.grep_file_content(pattern="hello", search_dir=str(d), ignore_case=True)
    data = _ok(result)
    assert data["success"] is True
    assert data["total_matches"] >= 1
