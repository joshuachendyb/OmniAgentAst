# -*- coding: utf-8 -*-
"""F10 file_operation 测试 — 小沈 2026-05-19"""
import pytest
import tempfile
from pathlib import Path
from app.services.tools.file.file_tools import _current_task_id


@pytest.fixture(autouse=True)
def _set_task():
    t = _current_task_id.set("test-f10")
    yield
    _current_task_id.reset(t)


def _ok(d):
    return d.get("data", d)


@pytest.mark.asyncio
async def test_copy():
    """F10-001: 复制文件，验证目标存在"""
    from app.services.tools.file.file_tools import FileTools
    ft = FileTools()

    src = Path(tempfile.mktemp(suffix=".txt"))
    src.write_text("copy content")
    dst = Path(tempfile.mktemp(suffix=".txt"))
    if dst.exists():
        dst.unlink()

    result = await ft.file_operation(action="copy", source=str(src), destination=str(dst))
    data = _ok(result)
    assert data["success"] is True, f"复制失败: {data.get('error')}"
    assert dst.exists(), "目标文件不存在"


@pytest.mark.asyncio
async def test_move():
    """F10-002: 移动文件，验证源消失目标存在"""
    from app.services.tools.file.file_tools import FileTools
    ft = FileTools()

    src = Path(tempfile.mktemp(suffix=".txt"))
    src.write_text("move content")
    dst = Path(tempfile.mktemp(suffix=".txt"))
    if dst.exists():
        dst.unlink()

    result = await ft.file_operation(action="move", source=str(src), destination=str(dst))
    data = _ok(result)
    assert data["success"] is True, f"移动失败: {data.get('error')}"
    assert not src.exists(), "源文件应已消失"
    assert dst.exists(), "目标文件不存在"


@pytest.mark.asyncio
async def test_delete():
    """F10-003: 删除文件，验证文件消失"""
    from app.services.tools.file.file_tools import FileTools
    ft = FileTools()

    src = Path(tempfile.mktemp(suffix=".txt"))
    src.write_text("delete me")

    result = await ft.file_operation(action="delete", source=str(src), force=True)
    data = _ok(result)
    assert data["success"] is True, f"删除失败: {data.get('error')}"
    assert not src.exists(), "文件应已被删除"


@pytest.mark.asyncio
async def test_invalid_action():
    """F10-004: action="invalid" 返回失败"""
    from app.services.tools.file.file_tools import FileTools
    ft = FileTools()
    result = await ft.file_operation(action="invalid", source="test.txt")
    data = _ok(result)
    assert data["success"] is False
    assert "不支持的action" in data.get("error", "")
