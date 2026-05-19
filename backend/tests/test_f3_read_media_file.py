# -*- coding: utf-8 -*-
"""F3 read_media_file 深度测试 — 小沈 2026-05-19"""
import pytest
import tempfile
from pathlib import Path

def _ok(d): return d.get("data", d)

@pytest.mark.asyncio
async def test_read_png():
    """F3-001: 读取PNG图片"""
    from app.services.tools.file.file_tools import FileTools
    ft = FileTools()
    # 创建最小有效PNG
    path = str(Path(tempfile.mktemp(suffix=".png")))
    Path(path).write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

    result = await ft.read_media_file(file_path=path)
    data = _ok(result)
    assert data["success"] is True
    assert data["mime_type"] == "image/png"
    assert len(data.get("base64_data", "")) > 0


@pytest.mark.asyncio
async def test_read_jpg():
    """F3-002: 读取JPG图片"""
    from app.services.tools.file.file_tools import FileTools
    ft = FileTools()
    path = str(Path(tempfile.mktemp(suffix=".jpg")))
    Path(path).write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)

    result = await ft.read_media_file(file_path=path)
    data = _ok(result)
    assert data["success"] is True
    assert "image/jpeg" in data["mime_type"]


@pytest.mark.asyncio
async def test_read_not_found():
    """F3-003: 文件不存在"""
    from app.services.tools.file.file_tools import FileTools
    ft = FileTools()
    result = await ft.read_media_file(file_path="Z:/no_such_file.png")
    data = _ok(result)
    assert data["success"] is False


@pytest.mark.asyncio
async def test_read_directory():
    """F3-004: 传入目录路径"""
    from app.services.tools.file.file_tools import FileTools
    ft = FileTools()
    result = await ft.read_media_file(file_path=tempfile.mkdtemp())
    data = _ok(result)
    assert data["success"] is False


@pytest.mark.asyncio
async def test_read_unknown_extension():
    """F3-005: 未知扩展名默认MIME"""
    from app.services.tools.file.file_tools import FileTools
    ft = FileTools()
    path = str(Path(tempfile.mktemp(suffix=".xyz")))
    Path(path).write_bytes(b"\x00" * 50)

    result = await ft.read_media_file(file_path=path)
    data = _ok(result)
    assert data["success"] is True
    assert data["mime_type"] == "application/octet-stream"
