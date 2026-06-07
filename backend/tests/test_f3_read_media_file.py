# -*- coding: utf-8 -*-
"""F3 read_media_file 深度测试 — 小沈 2026-05-19"""
import pytest
import tempfile
from pathlib import Path

def _ok(d): return d.get("data") if isinstance(d.get("data"), dict) else d

@pytest.mark.asyncio
async def test_read_png():
    """F3-001: 读取PNG图片"""
    from app.services.tools.file.file_tools import FileTools
    ft = FileTools()
    # 创建最小有效PNG
    path = str(Path(tempfile.mktemp(suffix=".png")))
    Path(path).write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

    result = await ft.read_media_file(file_path=path)
    assert result["code"] == "SUCCESS"
    assert result["data"]["mime_type"] == "image/png"
    assert len(result["data"].get("base64_data", "")) > 0


@pytest.mark.asyncio
async def test_read_jpg():
    """F3-002: 读取JPG图片"""
    from app.services.tools.file.file_tools import FileTools
    ft = FileTools()
    path = str(Path(tempfile.mktemp(suffix=".jpg")))
    Path(path).write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)

    result = await ft.read_media_file(file_path=path)
    assert result["code"] == "SUCCESS"
    assert "image/jpeg" in result["data"]["mime_type"]


@pytest.mark.asyncio
async def test_read_not_found():
    """F3-003: 文件不存在"""
    from app.services.tools.file.file_tools import FileTools
    ft = FileTools()
    result = await ft.read_media_file(file_path="Z:/no_such_file.png")
    assert result["code"] != "SUCCESS"


@pytest.mark.asyncio
async def test_read_directory():
    """F3-004: 传入目录路径"""
    from app.services.tools.file.file_tools import FileTools
    ft = FileTools()
    result = await ft.read_media_file(file_path=tempfile.mkdtemp())
    assert result["code"] != "SUCCESS"


@pytest.mark.asyncio
async def test_read_unknown_extension():
    """F3-005: 未知扩展名默认MIME"""
    from app.services.tools.file.file_tools import FileTools
    ft = FileTools()
    path = str(Path(tempfile.mktemp(suffix=".xyz")))
    Path(path).write_bytes(b"\x00" * 50)

    result = await ft.read_media_file(file_path=path)
    data = result["data"]
    assert result["code"] == "SUCCESS"
    assert data["mime_type"] == "application/octet-stream"


@pytest.mark.asyncio
async def test_read_pdf_rejected():
    """F3-006: PDF文件被拒绝，引导到read_document【FIX1 2026-05-20 小健】"""
    from app.services.tools.file.file_tools import FileTools
    ft = FileTools()
    path = str(Path(tempfile.mktemp(suffix=".pdf")))
    Path(path).write_bytes(b"%PDF-1.4" + b"\x00" * 50)

    result = await ft.read_media_file(file_path=path)
    assert result["code"] != "SUCCESS"
    assert "read_document" in result.get("message", "")
