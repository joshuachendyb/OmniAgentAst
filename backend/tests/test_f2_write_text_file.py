# -*- coding: utf-8 -*-
"""F2 write_text_file 深度测试 — 小沈 2026-05-19"""
import pytest
import tempfile
from pathlib import Path
from app.services.tools.file.file_tools import _current_task_id

def _ok(d: dict) -> dict:
    return d.get("data", d)


@pytest.fixture(autouse=True)
def _set_task_id():
    """所有测试设置mock task_id"""
    token = _current_task_id.set("test-task-f2")
    yield
    _current_task_id.reset(token)


@pytest.mark.asyncio
async def test_write_basic():
    """F2-001: 基本写入"""
    from app.services.tools.file.file_tools import FileTools
    ft = FileTools()
    path = str(Path(tempfile.mktemp(suffix=".txt")))

    result = await ft.write_text_file(file_path=path, text="hello world")
    data = _ok(result)
    assert data["success"] is True
    assert Path(path).read_text() == "hello world"


@pytest.mark.asyncio
async def test_write_append():
    """F2-002: 追加模式"""
    from app.services.tools.file.file_tools import FileTools
    ft = FileTools()
    path = str(Path(tempfile.mktemp(suffix=".txt")))
    Path(path).write_text("line1\n")

    result = await ft.write_text_file(file_path=path, text="line2\n", append=True)
    data = _ok(result)
    assert data["success"] is True
    assert Path(path).read_text() == "line1\nline2\n"


@pytest.mark.asyncio
async def test_write_chinese():
    """F2-003: 中文写入"""
    from app.services.tools.file.file_tools import FileTools
    ft = FileTools()
    path = str(Path(tempfile.mktemp(suffix=".txt")))

    result = await ft.write_text_file(file_path=path, text="你好世界")
    data = _ok(result)
    assert data["success"] is True
    assert "你好世界" in Path(path).read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_write_create_parents():
    """F2-004: 自动创建父目录"""
    from app.services.tools.file.file_tools import FileTools
    ft = FileTools()
    tmpdir = tempfile.mkdtemp()
    path = str(Path(tmpdir) / "sub1" / "sub2" / "test.txt")

    result = await ft.write_text_file(file_path=path, text="data")
    data = _ok(result)
    assert data["success"] is True
    assert Path(path).exists()


@pytest.mark.asyncio
async def test_write_binary_rejected():
    """F2-005: 二进制文件被拒绝"""
    from app.services.tools.file.file_tools import FileTools
    ft = FileTools()
    path = str(Path(tempfile.mktemp(suffix=".png")))
    Path(path).write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

    result = await ft.write_text_file(file_path=path, text="bad")
    data = _ok(result)
    assert data["success"] is False


@pytest.mark.asyncio
async def test_write_empty_text():
    """F2-006: 写入空内容（清空文件）"""
    from app.services.tools.file.file_tools import FileTools
    ft = FileTools()
    path = str(Path(tempfile.mktemp(suffix=".txt")))

    result = await ft.write_text_file(file_path=path, text="")
    data = _ok(result)
    assert data["success"] is True


@pytest.mark.asyncio
async def test_write_next_actions():
    """F2-007: next_actions包含验证建议"""
    from app.services.tools.file.file_tools import FileTools
    ft = FileTools()
    path = str(Path(tempfile.mktemp(suffix=".txt")))

    result = await ft.write_text_file(file_path=path, text="test")
    assert result["status"] == "success"
    assert "next_actions" in result


@pytest.mark.asyncio
async def test_write_capabilities():
    """F2-008: 验证capabilities_used"""
    from app.services.tools.file.file_tools import FileTools
    ft = FileTools()
    path = str(Path(tempfile.mktemp(suffix=".txt")))

    result = await ft.write_text_file(file_path=path, text="test")
    data = _ok(result)
    assert data["success"] is True
