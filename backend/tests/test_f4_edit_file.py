# -*- coding: utf-8 -*-
"""F4 edit_file 深度测试 — 小沈 2026-05-19"""
import pytest
import tempfile
from pathlib import Path
from app.services.tools.file.file_tools import _current_task_id

@pytest.fixture(autouse=True)
def _set_task():
    t = _current_task_id.set("test-f4")
    yield
    _current_task_id.reset(t)

def _ok(d): return d.get("data", d)


@pytest.mark.asyncio
async def test_edit_single_replace():
    """F4-001: 单处精确替换"""
    from app.services.tools.file.file_tools import FileTools
    ft = FileTools()
    path = str(Path(tempfile.mktemp(suffix=".txt")))
    Path(path).write_text("hello old world")

    result = await ft.edit_file(file_path=path, old_string="old", new_string="new")
    data = _ok(result)
    assert data["success"] is True
    assert Path(path).read_text() == "hello new world"


@pytest.mark.asyncio
async def test_edit_multi_edits():
    """F4-002: 多处结构化编辑"""
    from app.services.tools.file.file_tools import FileTools
    ft = FileTools()
    path = str(Path(tempfile.mktemp(suffix=".txt")))
    Path(path).write_text("line A\nline B\nline C\n")

    result = await ft.edit_file(file_path=path, edits=[
        {"oldText": "A", "newText": "X"},
        {"oldText": "B", "newText": "Y"},
    ])
    data = _ok(result)
    assert data["success"] is True
    assert "line X\nline Y" in Path(path).read_text()


@pytest.mark.asyncio
async def test_edit_dry_run():
    """F4-003: 预览模式不修改文件"""
    from app.services.tools.file.file_tools import FileTools
    ft = FileTools()
    path = str(Path(tempfile.mktemp(suffix=".txt")))
    Path(path).write_text("hello old world")

    result = await ft.edit_file(file_path=path, old_string="old", new_string="new", dry_run=True)
    data = _ok(result)
    assert data["success"] is True
    assert Path(path).read_text() == "hello old world"  # 未修改


@pytest.mark.asyncio
async def test_edit_mutual_exclusion():
    """F4-004: old_string和edits互斥"""
    from app.services.tools.file.file_tools import FileTools
    ft = FileTools()
    path = str(Path(tempfile.mktemp(suffix=".txt")))
    Path(path).write_text("test")

    result = await ft.edit_file(file_path=path, old_string="a", edits=[{"oldText": "b", "newText": "c"}])
    data = _ok(result)
    assert data["success"] is False


@pytest.mark.asyncio
async def test_edit_nothing_provided():
    """F4-005: 不提供任何编辑内容"""
    from app.services.tools.file.file_tools import FileTools
    ft = FileTools()
    result = await ft.edit_file(file_path="test.txt")
    data = _ok(result)
    assert data["success"] is False


@pytest.mark.asyncio
async def test_edit_file_not_found():
    """F4-006: 文件不存在"""
    from app.services.tools.file.file_tools import FileTools
    ft = FileTools()
    result = await ft.edit_file(file_path="Z:/no_file.txt", old_string="x", new_string="y")
    data = _ok(result)
    assert data["success"] is False
