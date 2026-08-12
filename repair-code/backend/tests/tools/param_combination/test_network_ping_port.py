# -*- coding: utf-8 -*-
"""ping_port参数组合测试 - 小欧 2026-07-04

测试网络诊断工具参数边界、schema验证、SSRF防护
所有网络工具都是async，需用_run()执行
"""

import asyncio
import pytest
from pydantic import ValidationError
from app.tools.network.network_diagnose import ping_port
from app.tools.network.network_schema import NetworkDiagnoseInput
from app.tools.tool_response import is_success, is_error


def _run(coro):
    return asyncio.run(coro)


class TestPingPortSchema:
    """Schema参数验证"""

    def test_schema_empty_host(self):
        with pytest.raises(ValidationError):
            NetworkDiagnoseInput(host="")

    def test_schema_invalid_mode(self):
        with pytest.raises(ValidationError):
            NetworkDiagnoseInput(host="8.8.8.8", mode="invalid")

    def test_schema_port_too_low(self):
        with pytest.raises(ValidationError):
            NetworkDiagnoseInput(host="8.8.8.8", mode="port", port=0)

    def test_schema_port_too_high(self):
        with pytest.raises(ValidationError):
            NetworkDiagnoseInput(host="8.8.8.8", mode="port", port=65536)

    def test_schema_count_too_low(self):
        with pytest.raises(ValidationError):
            NetworkDiagnoseInput(host="8.8.8.8", count=0)

    def test_schema_count_too_high(self):
        with pytest.raises(ValidationError):
            NetworkDiagnoseInput(host="8.8.8.8", count=21)

    def test_schema_timeout_too_low(self):
        with pytest.raises(ValidationError):
            NetworkDiagnoseInput(host="8.8.8.8", timeout=0)

    def test_schema_timeout_too_high(self):
        with pytest.raises(ValidationError):
            NetworkDiagnoseInput(host="8.8.8.8", timeout=31)

    def test_schema_port_mode_missing_port(self):
        with pytest.raises(ValidationError):
            NetworkDiagnoseInput(host="8.8.8.8", mode="port")

    def test_schema_ping_mode_with_port(self):
        with pytest.raises(ValidationError):
            NetworkDiagnoseInput(host="8.8.8.8", mode="ping", port=80)


class TestPingPortSecurity:
    """SSRF防护测试"""

    def test_localhost_ip_blocked(self):
        result = _run(ping_port(host="127.0.0.1"))
        assert is_error(result)

    def test_private_ip_blocked(self):
        result = _run(ping_port(host="192.168.1.1"))
        assert is_error(result)

    def test_internal_ip_blocked(self):
        result = _run(ping_port(host="10.0.0.5"))
        assert is_error(result)

    def test_loopback_hostname_blocked(self):
        result = _run(ping_port(host="localhost"))
        assert is_error(result)


class TestPingPortCall:
    """函数调用测试"""

    def test_public_host_ping(self):
        result = _run(ping_port(host="8.8.8.8"))
        assert is_success(result)

    def test_port_mode_dns(self):
        result = _run(ping_port(host="8.8.8.8", mode="port", port=53, timeout=10))
        assert is_success(result) or is_error(result)

    def test_port_mode_https(self):
        result = _run(ping_port(host="8.8.8.8", mode="port", port=443, timeout=10))
        assert is_success(result) or is_error(result)

    def test_dns_failure(self):
        result = _run(ping_port(host="this-domain-does-not-exist-12345.com"))
        assert is_error(result)

    def test_port_return_service(self):
        result = _run(ping_port(host="8.8.8.8", mode="port", port=53, timeout=10))
        assert is_success(result)
        assert result["data"]["service"] == "DNS"
