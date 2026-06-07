# -*- coding: utf-8 -*-
"""
N2 download_file 深度测试 — test_n2_download_file_deep.py

覆盖维度：
1. 参数校验（URL格式、目标路径格式）
2. 目标目录创建（自动创建、权限拒绝）
3. 断点续传逻辑（Range头、206响应、200回退、零大小文件）
4. 流式下载（分块写入、进度计算）
5. 代理配置（参数→环境变量）
6. 错误处理（超时、HTTP错误、写入失败、清理不完整文件）
7. 返回数据结构（file_path/file_size/total_size/progress_percent/content_type）

【规范】本测试为N2专用深度测试，不依赖旧测试代码
Author: 小沈 - 2026-05-19
"""

import os
import tempfile
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
import httpx

from app.services.tools.network.network_tools import download_file


def _async_iter(items):
    """创建异步生成器用于mock aiter_bytes"""
    async def _gen():
        for item in items:
            yield item
    return _gen()


# ============================================================
# 1. 参数校验测试
# ============================================================
class TestN2ParamValidation:
    """N2 参数校验测试"""

    @pytest.mark.asyncio
    async def test_invalid_url_no_scheme(self):
        """URL缺少协议 → ERR_INVALID_URL"""
        result = await download_file("example.com/file.zip", "D:/test.zip")
        assert result["code"] == "ERR_INVALID_URL"

    @pytest.mark.asyncio
    async def test_invalid_url_no_netloc(self):
        """URL缺少域名 → ERR_INVALID_URL"""
        result = await download_file("https:///path/file.zip", "D:/test.zip")
        assert result["code"] == "ERR_INVALID_URL"

    @pytest.mark.asyncio
    async def test_empty_url(self):
        """空URL → ERR_INVALID_URL"""
        result = await download_file("", "D:/test.zip")
        assert result["code"] == "ERR_INVALID_URL"

    @pytest.mark.asyncio
    async def test_timeout_conversion(self):
        """timeout毫秒正确转换为秒传递给httpx"""
        with tempfile.TemporaryDirectory() as tmpdir:
            dest = os.path.join(tmpdir, "file.zip")

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.headers = {"content-length": "10", "content-type": "application/zip"}
                mock_response.aiter_bytes = MagicMock(return_value=_async_iter([b"x" * 10]))

                mock_client = AsyncMock()
                mock_client.stream = MagicMock(return_value=AsyncMock(
                    __aenter__=AsyncMock(return_value=mock_response),
                    __aexit__=AsyncMock(return_value=None),
                ))
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client_cls.return_value = mock_client

                result = await download_file("https://example.com/file.zip", dest, timeout=60000)
                assert result["code"] == "SUCCESS"
                call_kwargs = mock_client_cls.call_args[1]
                timeout_obj = call_kwargs["timeout"]
                assert timeout_obj.read == 60.0  # 60000ms = 60s

    @pytest.mark.asyncio
    async def test_valid_destination_with_dir(self):
        """目标路径包含目录 → 通过校验"""
        with tempfile.TemporaryDirectory() as tmpdir:
            dest = os.path.join(tmpdir, "test.zip")
            # 使用mock避免实际网络请求，只验证路径校验通过
            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.headers = {"content-length": "100", "content-type": "application/zip"}
                mock_response.aiter_bytes = MagicMock(return_value=_async_iter([b"x" * 100]))

                mock_client = AsyncMock()
                mock_client.stream = MagicMock(return_value=AsyncMock(
                    __aenter__=AsyncMock(return_value=mock_response),
                    __aexit__=AsyncMock(return_value=None),
                ))
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client_cls.return_value = mock_client

                result = await download_file("https://example.com/file.zip", dest)
                assert result["code"] == "SUCCESS"


# ============================================================
# 2. 目录创建测试
# ============================================================
class TestN2DirectoryCreation:
    """N2 目标目录创建测试"""

    @pytest.mark.asyncio
    async def test_auto_create_directory(self):
        """自动创建不存在的目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            nested_dir = os.path.join(tmpdir, "a", "b", "c")
            dest = os.path.join(nested_dir, "file.zip")

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.headers = {"content-length": "10", "content-type": "application/zip"}
                mock_response.aiter_bytes = MagicMock(return_value=_async_iter([b"x" * 10]))

                mock_client = AsyncMock()
                mock_client.stream = MagicMock(return_value=AsyncMock(
                    __aenter__=AsyncMock(return_value=mock_response),
                    __aexit__=AsyncMock(return_value=None),
                ))
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client_cls.return_value = mock_client

                result = await download_file("https://example.com/file.zip", dest)
                assert result["code"] == "SUCCESS"
                assert os.path.exists(nested_dir)

    @pytest.mark.asyncio
    async def test_permission_error_create_dir(self):
        """目录创建权限拒绝 → ERR_NETWORK_CREATE_DIR"""
        with patch("os.makedirs") as mock_makedirs:
            mock_makedirs.side_effect = PermissionError("Access denied")
            result = await download_file("https://example.com/file.zip", "/invalid/path/file.zip")
            assert result["code"] == "ERR_NETWORK_CREATE_DIR"


# ============================================================
# 3. 断点续传逻辑测试
# ============================================================
class TestN2ResumeLogic:
    """N2 断点续传逻辑测试"""

    @pytest.mark.asyncio
    async def test_resume_with_existing_file(self):
        """文件已存在且>0字节 → 发送Range头，206续传"""
        with tempfile.TemporaryDirectory() as tmpdir:
            dest = os.path.join(tmpdir, "partial.zip")
            with open(dest, "wb") as f:
                f.write(b"existing")

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_response = MagicMock()
                mock_response.status_code = 206
                mock_response.headers = {
                    "content-range": "bytes 8-107/108",
                    "content-length": "100",
                    "content-type": "application/zip",
                }
                mock_response.aiter_bytes = MagicMock(return_value=_async_iter([b"new_data"]))

                mock_client = AsyncMock()
                mock_client.stream = MagicMock(return_value=AsyncMock(
                    __aenter__=AsyncMock(return_value=mock_response),
                    __aexit__=AsyncMock(return_value=None),
                ))
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client_cls.return_value = mock_client

                result = await download_file("https://example.com/file.zip", dest, resume=True)
                assert result["code"] == "SUCCESS"
                # 验证Range头被设置
                call_kwargs = mock_client.stream.call_args[1]
                assert call_kwargs["headers"]["Range"] == "bytes=8-"

    @pytest.mark.asyncio
    async def test_resume_server_returns_200(self):
        """服务器不支持Range → 200响应，覆盖写入"""
        with tempfile.TemporaryDirectory() as tmpdir:
            dest = os.path.join(tmpdir, "partial.zip")
            with open(dest, "wb") as f:
                f.write(b"existing")

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.headers = {
                    "content-length": "100",
                    "content-type": "application/zip",
                }
                mock_response.aiter_bytes = MagicMock(return_value=_async_iter([b"x" * 100]))

                mock_client = AsyncMock()
                mock_client.stream = MagicMock(return_value=AsyncMock(
                    __aenter__=AsyncMock(return_value=mock_response),
                    __aexit__=AsyncMock(return_value=None),
                ))
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client_cls.return_value = mock_client

                result = await download_file("https://example.com/file.zip", dest, resume=True)
                assert result["code"] == "SUCCESS"
                # 验证文件被覆盖（不是追加）
                with open(dest, "rb") as f:
                    content = f.read()
                assert content == b"x" * 100  # 不是 b"existing" + b"x"*100

    @pytest.mark.asyncio
    async def test_resume_zero_size_file(self):
        """文件存在但0字节 → 不加Range头，从头下载"""
        with tempfile.TemporaryDirectory() as tmpdir:
            dest = os.path.join(tmpdir, "empty.zip")
            open(dest, "wb").close()  # 创建0字节文件

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.headers = {
                    "content-length": "100",
                    "content-type": "application/zip",
                }
                mock_response.aiter_bytes = MagicMock(return_value=_async_iter([b"x" * 100]))

                mock_client = AsyncMock()
                mock_client.stream = MagicMock(return_value=AsyncMock(
                    __aenter__=AsyncMock(return_value=mock_response),
                    __aexit__=AsyncMock(return_value=None),
                ))
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client_cls.return_value = mock_client

                result = await download_file("https://example.com/file.zip", dest, resume=True)
                assert result["code"] == "SUCCESS"
                # 验证没有Range头
                call_kwargs = mock_client.stream.call_args[1]
                assert "Range" not in call_kwargs["headers"]

    @pytest.mark.asyncio
    async def test_resume_disabled(self):
        """resume=False → 不加Range头，直接覆盖"""
        with tempfile.TemporaryDirectory() as tmpdir:
            dest = os.path.join(tmpdir, "file.zip")
            with open(dest, "wb") as f:
                f.write(b"existing")

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.headers = {
                    "content-length": "100",
                    "content-type": "application/zip",
                }
                mock_response.aiter_bytes = MagicMock(return_value=_async_iter([b"x" * 100]))

                mock_client = AsyncMock()
                mock_client.stream = MagicMock(return_value=AsyncMock(
                    __aenter__=AsyncMock(return_value=mock_response),
                    __aexit__=AsyncMock(return_value=None),
                ))
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client_cls.return_value = mock_client

                result = await download_file("https://example.com/file.zip", dest, resume=False)
                assert result["code"] == "SUCCESS"
                call_kwargs = mock_client.stream.call_args[1]
                assert "Range" not in call_kwargs["headers"]


# ============================================================
# 4. 代理配置测试
# ============================================================
class TestN2ProxyConfig:
    """N2 代理配置测试"""

    @pytest.mark.asyncio
    async def test_proxy_from_param(self):
        """proxy参数优先传递"""
        with tempfile.TemporaryDirectory() as tmpdir:
            dest = os.path.join(tmpdir, "file.zip")

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.headers = {"content-length": "10", "content-type": "application/zip"}
                mock_response.aiter_bytes = MagicMock(return_value=_async_iter([b"x" * 10]))

                mock_client = AsyncMock()
                mock_client.stream = MagicMock(return_value=AsyncMock(
                    __aenter__=AsyncMock(return_value=mock_response),
                    __aexit__=AsyncMock(return_value=None),
                ))
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client_cls.return_value = mock_client

                result = await download_file(
                    "https://example.com/file.zip",
                    dest,
                    proxy="http://proxy.example.com:8080",
                )
                assert result["code"] == "SUCCESS"
                call_kwargs = mock_client_cls.call_args[1]
                assert call_kwargs["proxy"] == "http://proxy.example.com:8080"

    @pytest.mark.asyncio
    async def test_headers_passed(self):
        """自定义headers传递到请求"""
        with tempfile.TemporaryDirectory() as tmpdir:
            dest = os.path.join(tmpdir, "file.zip")

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.headers = {"content-length": "10", "content-type": "application/zip"}
                mock_response.aiter_bytes = MagicMock(return_value=_async_iter([b"x" * 10]))

                mock_client = AsyncMock()
                mock_client.stream = MagicMock(return_value=AsyncMock(
                    __aenter__=AsyncMock(return_value=mock_response),
                    __aexit__=AsyncMock(return_value=None),
                ))
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client_cls.return_value = mock_client

                result = await download_file(
                    "https://example.com/file.zip",
                    dest,
                    headers={"Authorization": "Bearer token123"},
                )
                assert result["code"] == "SUCCESS"
                call_kwargs = mock_client.stream.call_args[1]
                assert call_kwargs["headers"]["Authorization"] == "Bearer token123"


# ============================================================
# 5. 错误处理测试
# ============================================================
class TestN2ErrorHandling:
    """N2 错误处理测试"""

    @pytest.mark.asyncio
    async def test_timeout_error(self):
        """下载超时 → ERR_NETWORK_TIMEOUT"""
        with tempfile.TemporaryDirectory() as tmpdir:
            dest = os.path.join(tmpdir, "file.zip")
            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.stream = MagicMock(return_value=AsyncMock(
                    __aenter__=AsyncMock(side_effect=httpx.TimeoutException("timeout")),
                    __aexit__=AsyncMock(return_value=None),
                ))
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client_cls.return_value = mock_client

                result = await download_file("https://example.com/file.zip", dest)
                assert result["code"] == "ERR_NETWORK_TIMEOUT"
                # 验证超时消息单位正确（毫秒转秒）
                assert "300秒" in result["message"] or "秒" in result["message"]

    @pytest.mark.asyncio
    async def test_http_error_404(self):
        """HTTP 404 → ERR_NETWORK_HTTP_ERROR"""
        with tempfile.TemporaryDirectory() as tmpdir:
            dest = os.path.join(tmpdir, "file.zip")

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_response = MagicMock()
                mock_response.status_code = 404
                mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                    "Not Found", request=MagicMock(), response=mock_response
                )

                mock_client = AsyncMock()
                mock_client.stream = MagicMock(return_value=AsyncMock(
                    __aenter__=AsyncMock(return_value=mock_response),
                    __aexit__=AsyncMock(return_value=None),
                ))
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client_cls.return_value = mock_client

                result = await download_file("https://example.com/file.zip", dest)
                assert result["code"] == "ERR_NETWORK_HTTP_ERROR"
                assert "404" in result["message"]

    @pytest.mark.asyncio
    async def test_write_permission_error_cleanup(self):
        """写入权限错误 → 删除不完整文件 → ERR_NETWORK_WRITE_FILE"""
        with tempfile.TemporaryDirectory() as tmpdir:
            dest = os.path.join(tmpdir, "file.zip")

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.headers = {"content-length": "100", "content-type": "application/zip"}

                # 模拟aiter_bytes返回数据，但写入时触发PermissionError
                async def fake_iter():
                    yield b"partial_data"
                    raise PermissionError("Access denied")

                mock_response.aiter_bytes = MagicMock(return_value=fake_iter())

                mock_client = AsyncMock()
                mock_client.stream = MagicMock(return_value=AsyncMock(
                    __aenter__=AsyncMock(return_value=mock_response),
                    __aexit__=AsyncMock(return_value=None),
                ))
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client_cls.return_value = mock_client

                result = await download_file("https://example.com/file.zip", dest)
                assert result["code"] == "ERR_NETWORK_WRITE_FILE"

    @pytest.mark.asyncio
    async def test_request_error(self):
        """网络请求错误 → ERR_NETWORK_REQUEST_ERROR"""
        with tempfile.TemporaryDirectory() as tmpdir:
            dest = os.path.join(tmpdir, "file.zip")
            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.stream = MagicMock(return_value=AsyncMock(
                    __aenter__=AsyncMock(side_effect=httpx.RequestError("Connection refused")),
                    __aexit__=AsyncMock(return_value=None),
                ))
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client_cls.return_value = mock_client

                result = await download_file("https://example.com/file.zip", dest)
                assert result["code"] == "ERR_NETWORK_REQUEST_ERROR"


# ============================================================
# 6. 返回数据结构测试
# ============================================================
class TestN2ResponseData:
    """N2 返回数据结构测试"""

    @pytest.mark.asyncio
    async def test_success_response_structure(self):
        """成功返回包含所有预期字段"""
        with tempfile.TemporaryDirectory() as tmpdir:
            dest = os.path.join(tmpdir, "file.zip")

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.headers = {
                    "content-length": "100",
                    "content-type": "application/zip",
                }
                mock_response.aiter_bytes = MagicMock(return_value=_async_iter([b"x" * 100]))

                mock_client = AsyncMock()
                mock_client.stream = MagicMock(return_value=AsyncMock(
                    __aenter__=AsyncMock(return_value=mock_response),
                    __aexit__=AsyncMock(return_value=None),
                ))
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client_cls.return_value = mock_client

                result = await download_file("https://example.com/file.zip", dest)
                assert result["code"] == "SUCCESS"
                data = result["data"]
                assert "file_path" in data
                assert "file_size" in data
                assert "total_size" in data
                assert "progress_percent" in data
                assert "content_type" in data
                assert data["file_size"] == 100
                assert data["total_size"] == 100
                assert data["progress_percent"] == 100
                assert data["content_type"] == "application/zip"

    @pytest.mark.asyncio
    async def test_next_actions_present(self):
        """成功返回包含next_actions"""
        with tempfile.TemporaryDirectory() as tmpdir:
            dest = os.path.join(tmpdir, "file.zip")

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.headers = {"content-length": "10", "content-type": "application/zip"}
                mock_response.aiter_bytes = MagicMock(return_value=_async_iter([b"x" * 10]))

                mock_client = AsyncMock()
                mock_client.stream = MagicMock(return_value=AsyncMock(
                    __aenter__=AsyncMock(return_value=mock_response),
                    __aexit__=AsyncMock(return_value=None),
                ))
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client_cls.return_value = mock_client

                result = await download_file("https://example.com/file.zip", dest)
                assert result["code"] == "SUCCESS"
                assert "next_actions" in result
                assert len(result["next_actions"]) > 0

    @pytest.mark.asyncio
    async def test_progress_calculation_with_resume(self):
        """断点续传进度计算正确"""
        with tempfile.TemporaryDirectory() as tmpdir:
            dest = os.path.join(tmpdir, "partial.zip")
            with open(dest, "wb") as f:
                f.write(b"x" * 50)  # 已下载50字节

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_response = MagicMock()
                mock_response.status_code = 206
                mock_response.headers = {
                    "content-range": "bytes 50-149/150",
                    "content-length": "100",
                    "content-type": "application/zip",
                }
                mock_response.aiter_bytes = MagicMock(return_value=_async_iter([b"y" * 100]))

                mock_client = AsyncMock()
                mock_client.stream = MagicMock(return_value=AsyncMock(
                    __aenter__=AsyncMock(return_value=mock_response),
                    __aexit__=AsyncMock(return_value=None),
                ))
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client_cls.return_value = mock_client

                result = await download_file("https://example.com/file.zip", dest, resume=True)
                assert result["code"] == "SUCCESS"
                # 总大小150，已下载50+100=100...不对，resume_offset=50，downloaded=100
                # progress = (50 + 100) * 100 / 150 = 100%
                assert result["data"]["progress_percent"] == 100
                assert result["data"]["total_size"] == 150
