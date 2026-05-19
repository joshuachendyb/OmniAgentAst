# -*- coding: utf-8 -*-
"""F11 data_file_format 测试 — 小沈 2026-05-19"""
import pytest
import tempfile
from pathlib import Path


def _ok(d):
    return d.get("data", d)


@pytest.mark.asyncio
async def test_read_json():
    """F11-001: 读取JSON文件，验证内容"""
    from app.services.tools.file.file_tools import FileTools
    ft = FileTools()

    jpath = Path(tempfile.mktemp(suffix=".json"))
    jpath.write_text('{"key": "value", "num": 42}', encoding="utf-8")

    result = await ft.data_file_format(file_path=str(jpath), action="read")
    data = _ok(result)
    assert data["success"] is True, f"读取失败: {data.get('error')}"
    assert data.get("data", {}).get("key") == "value"
    assert data.get("data", {}).get("num") == 42


@pytest.mark.asyncio
async def test_write_json():
    """F11-002: 写入JSON文件，验证文件存在且内容正确"""
    from app.services.tools.file.file_tools import FileTools
    ft = FileTools()

    jpath = Path(tempfile.mktemp(suffix=".json"))
    if jpath.exists():
        jpath.unlink()

    payload = {"name": "test", "items": [1, 2, 3]}
    result = await ft.data_file_format(file_path=str(jpath), action="write", data=payload)
    data = _ok(result)
    assert data["success"] is True, f"写入失败: {data.get('error')}"
    assert jpath.exists(), "JSON文件未创建"

    import json
    content = json.loads(jpath.read_text(encoding="utf-8"))
    assert content == payload


@pytest.mark.asyncio
async def test_read_yaml():
    """F11-003: 读取YAML文件，验证内容"""
    from app.services.tools.file.file_tools import FileTools
    ft = FileTools()

    ypath = Path(tempfile.mktemp(suffix=".yaml"))
    ypath.write_text("key: hello\nnum: 99\n", encoding="utf-8")

    result = await ft.data_file_format(file_path=str(ypath), action="read")
    data = _ok(result)
    assert data["success"] is True, f"读取失败: {data.get('error')}"
    assert data.get("data", {}).get("key") == "hello"
    assert data.get("data", {}).get("num") == 99


@pytest.mark.asyncio
async def test_invalid_format():
    """F11-004: 不存在的文件，验证失败"""
    from app.services.tools.file.file_tools import FileTools
    ft = FileTools()
    result = await ft.data_file_format(file_path="Z:/no_such_file.json", action="read")
    data = _ok(result)
    assert data["success"] is False
