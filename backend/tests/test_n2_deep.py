# -*- coding: utf-8 -*-
"""N2 download_file 深度测试 — 小沈 2026-05-19"""
import pytest, tempfile, os
from pathlib import Path
from app.services.tools.network.network_tools import download_file


@pytest.mark.asyncio
async def test_download_small_file():
    """N2-001: 下载小文件"""
    dest = str(Path(tempfile.mktemp(suffix=".json")))
    result = await download_file(
        url="https://httpbin.org/bytes/100",
        destination_path=dest,
        timeout=15000
    )
    assert result["code"] == "SUCCESS"
    assert os.path.exists(dest)
    assert os.path.getsize(dest) == 100


@pytest.mark.asyncio
async def test_invalid_url():
    """N2-002: 无效URL"""
    result = await download_file(url="not-a-url", destination_path="/tmp/test")
    assert result["code"] == "ERR_INVALID_URL"


@pytest.mark.asyncio
async def test_invalid_path():
    """N2-003: 无效目标路径"""
    result = await download_file(url="https://example.com", destination_path="")
    assert result["code"] == "ERR_NETWORK_INVALID_PATH"


@pytest.mark.asyncio
async def test_create_parent_dir():
    """N2-004: 自动创建父目录"""
    tmp = tempfile.mkdtemp()
    dest = str(Path(tmp) / "sub" / "file.json")
    result = await download_file(
        url="https://httpbin.org/bytes/50",
        destination_path=dest,
        timeout=15000
    )
    assert result["code"] == "SUCCESS"
    assert os.path.exists(dest)
