# -*- coding: utf-8 -*-
"""N1 http_request 深度测试 — 小沈 2026-05-19"""
import pytest
from app.services.tools.network.network_tools import http_request


@pytest.mark.asyncio
async def test_get_json():
    """N1-001: GET请求JSON API"""
    result = await http_request(url="https://httpbin.org/get", timeout=15000)
    assert result["code"] == "SUCCESS"
    assert result["data"]["status_code"] == 200


@pytest.mark.asyncio
async def test_post_json():
    """N1-002: POST请求带json_body"""
    result = await http_request(
        url="https://httpbin.org/post",
        method="POST",
        json_body={"test": "value"},
        timeout=15000
    )
    assert result["code"] == "SUCCESS"


@pytest.mark.asyncio
async def test_invalid_url():
    """N1-003: 无效URL被拒绝"""
    result = await http_request(url="not-a-valid-url")
    assert result["code"] == "ERR_INVALID_URL"


@pytest.mark.asyncio
async def test_timeout():
    """N1-004: 超时处理"""
    result = await http_request(url="https://httpbin.org/delay/10", timeout=1000, retry=0)
    assert result["code"] in ("ERR_NETWORK_TIMEOUT", "ERR_NETWORK_REQUEST_ERROR")


@pytest.mark.asyncio
async def test_404_error():
    """N1-005: HTTP 404错误"""
    result = await http_request(url="https://httpbin.org/status/404", timeout=10000, retry=0)
    assert result["code"] == "ERR_NETWORK_HTTP_ERROR"
    assert result["data"]["status_code"] == 404


@pytest.mark.asyncio
async def test_invalid_retry():
    """N1-006: 无效重试次数被拒绝"""
    result = await http_request(url="https://example.com", retry=999)
    assert result["code"] == "ERR_NETWORK_INVALID_PARAM"


@pytest.mark.asyncio
async def test_next_actions():
    """N1-007: 成功时注入next_actions"""
    result = await http_request(url="https://httpbin.org/get", timeout=10000)
    if result["code"] == "SUCCESS":
        assert "next_actions" in result
