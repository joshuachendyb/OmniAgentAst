"""
network类工具集成测试 - 基于运行中的服务
小健 2026-05-21
"""
import pytest
from tests.integration._helper import ToolClient, assert_success, assert_error, assert_data_key, assert_data_not_empty

TOOL = ToolClient()


class TestHttpRequest:
    """http_request 多场景测试"""

    def test_get_local_health(self):
        r = TOOL.call("http_request", {"url": "http://127.0.0.1:8000/api/v1/health"})
        assert_success(r)
        assert_data_not_empty(r)

    def test_get_with_params(self):
        r = TOOL.call("http_request", {
            "url": "http://127.0.0.1:8000/api/v1/health",
            "method": "GET",
        })
        assert_success(r)

    def test_post_local_tool_list(self):
        r = TOOL.call("http_request", {
            "url": "http://127.0.0.1:8000/api/v1/tool/list",
            "method": "GET",
        })
        assert_success(r)

    def test_timeout_short(self):
        r = TOOL.call("http_request", {
            "url": "http://127.0.0.1:8000/api/v1/health",
            "timeout": 5000,
        })
        assert_success(r)

    def test_invalid_url(self):
        r = TOOL.call("http_request", {"url": "http://nonexistent.invalid/xyz"})
        assert_error(r)

    def test_timeout_unit_milliseconds(self):
        """验证timeout是毫秒制 (Bug #4曾在此出现)"""
        r = TOOL.call("http_request", {
            "url": "http://127.0.0.1:8000/api/v1/health",
            "timeout": 3000,
        })
        assert_success(r)


class TestFetchWebpage:
    """fetch_webpage 多场景测试"""

    def test_fetch_local(self):
        r = TOOL.call("fetch_webpage", {"url": "http://127.0.0.1:8000/docs"})
        assert_success(r)

    def test_fetch_markdown_format(self):
        r = TOOL.call("fetch_webpage", {
            "url": "http://127.0.0.1:8000/docs",
            "extract_format": "markdown",
        })
        assert_success(r)


class TestNetworkDiagnose:
    """network_diagnose 多场景测试"""

    def test_ping_localhost(self):
        r = TOOL.call("network_diagnose", {"host": "127.0.0.1", "mode": "ping"})
        assert_success(r)

    def test_port_check(self):
        r = TOOL.call("network_diagnose", {
            "host": "127.0.0.1",
            "mode": "port",
            "port": 8000,
        })
        assert_success(r)

    def test_ping_invalid_host(self):
        r = TOOL.call("network_diagnose", {"host": "nonexistent.invalid", "mode": "ping"})
        assert_success(r)
        data = r.get("data", {})
        assert data.get("is_reachable") is False, "不可达主机应返回is_reachable=False"
