# -*- coding: utf-8 -*-
"""download_file参数组合测试 - 小欧 2026-07-04

测试文件下载工具参数边界、schema验证、错误路径
所有网络工具都是async，需用_run()执行
"""

import asyncio
import pytest
from pydantic import ValidationError
from app.tools.network.download_file import download
from app.tools.network.network_schema import DownloadFileInput
from app.tools.tool_response import is_success, is_error


def _run(coro):
    return asyncio.run(coro)


class TestDownloadSchema:
    """Schema参数验证"""

    def test_schema_empty_url(self):
        with pytest.raises(ValidationError):
            DownloadFileInput(url="", dest="test.zip")

    def test_schema_empty_dest_is_optional(self):
        result = DownloadFileInput(url="https://example.com/f.zip", dest="")
        assert result.dest == ""

    def test_schema_timeout_too_low(self):
        with pytest.raises(ValidationError):
            DownloadFileInput(url="https://example.com/f.zip", dest="test.zip", timeout=1)

    def test_schema_timeout_too_high(self):
        with pytest.raises(ValidationError):
            DownloadFileInput(url="https://example.com/f.zip", dest="test.zip", timeout=3601)


class TestDownloadCall:
    """函数调用测试"""

    def test_minimal_url_fails(self):
        result = _run(download(url="https://example.com/file.zip", dest="test.zip"))
        assert is_error(result)

    def test_localhost_blocked(self):
        result = _run(download(url="http://127.0.0.1:80/file.zip", dest="test.zip"))
        assert is_error(result)

    def test_private_ip_blocked(self):
        result = _run(download(url="http://10.0.0.1/file.zip", dest="test.zip"))
        assert is_error(result)

    def test_invalid_url(self):
        result = _run(download(url="not-a-valid-url", dest="test.zip"))
        assert is_error(result)

    def test_path_traversal(self):
        result = _run(download(url="https://example.com/f.zip", dest="../f.zip"))
        assert is_error(result)

    def test_path_traversal_backslash(self):
        result = _run(download(url="https://example.com/f.zip", dest="..\\f.zip"))
        assert is_error(result)

    def test_invalid_proxy(self):
        result = _run(download(url="https://example.com/f.zip", dest="test.zip", proxy="not-a-url"))
        assert is_error(result)
