# -*- coding: utf-8 -*-
"""F8 rename_file 深度测试 — 小沈 2026-05-19"""
import pytest
import tempfile
from pathlib import Path
from app.services.tools.file.file_tools import _current_task_id

def _ok(d): return d.get("data", d)


@pytest.fixture(autouse=True)
def _set_task():
    t = _current_task_id.set("test-f8")
    yield
    _current_task_id.reset(t)


@pytest.mark.asyncio
async def test_rename_single():
    """F8-001: 单文件重命名"""
    from app.services.tools.file.file_tools import FileTools
    ft = FileTools()
    import uuid
    path = str(Path(tempfile.mktemp(suffix=".txt")))
    Path(path).write_text("rename me")
    new_name = f"renamed_{uuid.uuid4().hex[:8]}.txt"

    result = await ft.rename_file(path=path, new_name=new_name)
    data = _ok(result)
    assert data["success"] is True
    assert not Path(path).exists()
    assert Path(Path(path).parent / new_name).exists()


@pytest.mark.asyncio
async def test_rename_mutual():
    """F8-002: path和directory同时提供应失败"""
    from app.services.tools.file.file_tools import FileTools
    ft = FileTools()
    result = await ft.rename_file(path="test.txt", directory=".")
    data = _ok(result)
    assert data["success"] is False


@pytest.mark.asyncio
async def test_rename_not_exists():
    """F8-003: 重命名不存在的文件"""
    from app.services.tools.file.file_tools import FileTools
    ft = FileTools()
    result = await ft.rename_file(path="Z:/__no_such_rename__.txt", new_name="x.txt")
    data = _ok(result)
    assert data["success"] is False
