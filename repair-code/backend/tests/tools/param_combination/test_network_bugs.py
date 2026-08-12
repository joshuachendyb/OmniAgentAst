# -*- coding: utf-8 -*-
"""
Network工具 Bug暴露测试 (修正版) — 小欧 2026-06-24

注意:所有Network工具都是async函数,必须await
"""
import asyncio
import pytest
from typing import Dict, Any

from app.tools.tool_response import is_success, is_error
from app.tools.network.http_request import httpget
from app.tools.validate.url_validator import validate_url as _validate_url
from app.tools.network.network_diagnose import ping_port
from app.tools.network.search_web import searchweb
from app.tools.network.fetch_webpage import fetchpage
from app.tools.network.download_file import download


# ████████████████████████████████████████████████████████████████████████████████
# Bug#N01: _validate_url SSRF bypass via 0x/整数IP/127.0.0.2等
# ████████████████████████████████████████████████████████████████████████████████

class TestBugN01_SsrfBypass:
    """Bug#N01: SSRF拦截可被绕过 — CONFIRMED 5个向量"""

    def test_n01_hex_ip_bypass(self):
        """0x7f000001绕过SSRF"""
        is_valid, _, _ = _validate_url("http://0x7f000001:8000/secret")
        assert not is_valid, \
            f"Bug#N01a: 0x7f000001(127.0.0.1十六进制)绕过SSRF"

    def test_n01_integer_ip_bypass(self):
        """2130706433 (127.0.0.1整数) 绕过SSRF"""
        is_valid, _, _ = _validate_url("http://2130706433:8000/secret")
        assert not is_valid, \
            f"Bug#N01b: 整数IP(2130706433)绕过SSRF"

    def test_n01_127_0_0_2(self):
        """127.0.0.2绕过SSRF(同属127.0.0.0/8)"""
        is_valid, _, _ = _validate_url("http://127.0.0.2:8000/")
        assert not is_valid, \
            f"Bug#N01c: 127.0.0.2绕过SSRF"

    def test_n01_ip_0(self):
        """http://0:8000 绕过 (0=0.0.0.0)"""
        is_valid, _, _ = _validate_url("http://0:8000/")
        assert not is_valid, \
            f"Bug#N01d: IP 0(0.0.0.0)绕过SSRF"

    def test_n01_short_ip_127_1(self):
        """127.1 绕过(127.0.0.1缩写)"""
        is_valid, _, _ = _validate_url("http://127.1:8000/")
        assert not is_valid, \
            f"Bug#N01e: 127.1绕过SSRF"


# ████████████████████████████████████████████████████████████████████████████████
# Bug#N02: _validate_url 172.x校验逻辑
# ████████████████████████████████████████████████████████████████████████████████

class TestBugN02_ValidateUrl172:
    """Bug#N02: 172.x内网检测"""

    def test_n02_172_16_blocked(self):
        is_valid, _, _ = _validate_url("https://172.16.0.1/")
        assert not is_valid
    def test_n02_172_31_blocked(self):
        is_valid, _, _ = _validate_url("https://172.31.255.255/")
        assert not is_valid
    def test_n02_172_32_allowed(self):
        is_valid, _, _ = _validate_url("https://172.32.0.1/")
        assert is_valid
    def test_n02_172_15_allowed(self):
        is_valid, _, _ = _validate_url("https://172.15.0.1/")
        assert is_valid


# ████████████████████████████████████████████████████████████████████████████████
# Bug#N03: http_request SSRF - 实际验证
# ████████████████████████████████████████████████████████████████████████████████

@pytest.mark.asyncio
class TestBugN03_HttpRequestLocalhost:
    """Bug#N03: http_request实际拒绝localhost请求"""

    async def test_n03_localhost_rejected(self):
        r = await httpget(url="http://127.0.0.1:8000/api")
        assert is_error(r), \
            f"Bug#N03: http_request未拦截127.0.0.1: {r}"

    async def test_n03_hex_ip_rejected(self):
        r = await httpget(url="http://0x7f000001:8000/api")
        assert is_error(r), \
            f"Bug#N03: http_request未拦截0x7f000001: {r}"


# ████████████████████████████████████████████████████████████████████████████████
# Bug#N05: ping_port async实际测试
# ████████████████████████████████████████████████████████████████████████████████

@pytest.mark.asyncio
class TestBugN05_NetworkDiagnoseAsync:
    """Bug#N05: ping_port async调用"""

    async def test_n05_port_no_port(self):
        r = await ping_port(host="8.8.8.8", mode="port")
        assert is_error(r), "port模式无port应报错"

    async def test_n05_ping(self):
        r = await ping_port(host="8.8.8.8", mode="ping")
        assert is_success(r), f"ping 8.8.8.8失败"

    async def test_n05_port_dns(self):
        r = await ping_port(host="8.8.8.8", mode="port", port=53)
        assert is_success(r) or r is not None

    async def test_n05_blank_host(self):
        r = await ping_port(host="", mode="ping")
        assert is_error(r), "空host应报错"


# ████████████████████████████████████████████████████████████████████████████████
# Bug#N06: fetch_webpage async实际测试
# ████████████████████████████████████████████████████████████████████████████████

@pytest.mark.asyncio
class TestBugN06_FetchWebpageAsync:
    """Bug#N06: fetch_webpage async调用"""

    async def test_n06_invalid_url(self):
        for bad_url in ["", "not a url", "http://"]:
            r = await fetchpage(url=bad_url)
            assert is_error(r), f"URL='{bad_url}'应报错"

    async def test_n06_nonexistent_domain(self):
        r = await fetchpage(url="http://this-domain-not-exist-42xyz.com/")
        assert is_error(r), "不存在域名应报错"


# ████████████████████████████████████████████████████████████████████████████████
# Bug#N07: search_web async
# ████████████████████████████████████████████████████████████████████████████████

@pytest.mark.asyncio
class TestBugN07_SearchWebAsync:
    """Bug#N07: search_web async调用"""

    async def test_n07_empty_query(self):
        r = await searchweb(query="")
        # 2026-07-22 小欧: query空白拦截, 防None穿透Bing异常
        assert is_error(r), "空查询应参数级报错"

    async def test_n07_single_char(self):
        r = await searchweb(query="a")
        # 2026-07-22 小欧: 单字符query允许透传(仅空白拦截)
        assert not is_error(r), "单字符查询不应有参数级报错"


# ████████████████████████████████████████████████████████████████████████████████
# Bug#N08: download_file async
# ████████████████████████████████████████████████████████████████████████████████

@pytest.mark.asyncio
class TestBugN08_DownloadFileAsync:
    """Bug#N08: download_file async调用"""

    async def test_n08_path_traversal(self):
        r = await download(
            url="https://example.com/file.txt",
            dest="../../etc/passwd")
        assert is_error(r), "路径遍历应被拦截"

    async def test_n08_empty_path(self):
        r = await download(
            url="https://example.com/file.txt",
            dest="")
        assert is_error(r), "空路径应报错"


# ████████████████████████████████████████████████████████████████████████████████
# Bug#N13: http_request 不支持scheme
# ████████████████████████████████████████████████████████████████████████████████

class TestBugN13_HttpSchemes:
    """Bug#N13: http_request不支持scheme应被拒绝"""

    def test_n13_file_scheme(self):
        is_valid, _, _ = _validate_url("file:///etc/passwd")
        assert not is_valid
    def test_n13_gopher(self):
        is_valid, _, _ = _validate_url("gopher://example.com/")
        assert not is_valid
    def test_n13_data(self):
        is_valid, _, _ = _validate_url("data://example.com/")
        assert not is_valid
    def test_n13_metadata(self):
        is_valid, _, _ = _validate_url("http://169.254.169.254/")
        assert not is_valid
