# -*- coding: utf-8 -*-
"""F9 archive_tool 测试 — 小沈 2026-05-19"""
import pytest
import tempfile
import os
from pathlib import Path
from app.services.tools.file.file_tools import _current_task_id


@pytest.fixture(autouse=True)
def _set_task():
    t = _current_task_id.set("test-f9")
    yield
    _current_task_id.reset(t)


def _ok(d):
    return d.get("data", d)


@pytest.mark.asyncio
async def test_archive_compress():
    """F9-001: 压缩目录为zip，验证success和输出文件存在"""
    from app.services.tools.file.file_tools import FileTools
    ft = FileTools()

    src_dir = tempfile.mkdtemp()
    (Path(src_dir) / "a.txt").write_text("hello")
    (Path(src_dir) / "b.txt").write_text("world")

    zip_path = os.path.join(tempfile.mkdtemp(), "test.zip")
    result = await ft.archive_tool(action="compress", source_path=src_dir, output_path=zip_path)
    data = _ok(result)
    assert data["success"] is True, f"压缩失败: {data.get('error')}"
    assert os.path.exists(zip_path), "zip文件未生成"


@pytest.mark.asyncio
async def test_archive_extract():
    """F9-002: 解压zip，验证success"""
    from app.services.tools.file.file_tools import FileTools
    ft = FileTools()

    src_dir = tempfile.mkdtemp()
    (Path(src_dir) / "x.txt").write_text("extract test")
    zip_path = os.path.join(tempfile.mkdtemp(), "test.zip")
    await ft.archive_tool(action="compress", source_path=src_dir, output_path=zip_path)

    out_dir = tempfile.mkdtemp()
    result = await ft.archive_tool(action="extract", archive_path=zip_path, output_dir=out_dir)
    assert result["status"] == "success", f"解压失败: {result.get('summary')}"
    data = _ok(result)
    assert data.get("success") is not False


@pytest.mark.asyncio
async def test_archive_invalid_action():
    """F9-003: action="invalid" 返回失败"""
    from app.services.tools.file.file_tools import FileTools
    ft = FileTools()
    result = await ft.archive_tool(action="invalid")
    data = _ok(result)
    assert data["success"] is False
    assert "不支持的action" in data.get("error", "")


@pytest.mark.asyncio
async def test_archive_compress_no_source_path():
    """F9-004: compress模式缺少source_path返回失败"""
    from app.services.tools.file.file_tools import FileTools
    ft = FileTools()
    result = await ft.archive_tool(action="compress")
    data = _ok(result)
    assert data["success"] is False
    assert "source_path" in data.get("error", "")


@pytest.mark.asyncio
async def test_archive_extract_no_archive_path():
    """F9-005: extract模式缺少archive_path返回失败"""
    from app.services.tools.file.file_tools import FileTools
    ft = FileTools()
    result = await ft.archive_tool(action="extract")
    data = _ok(result)
    assert data["success"] is False
    assert "archive_path" in data.get("error", "")
