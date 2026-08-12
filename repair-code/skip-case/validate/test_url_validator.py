# ================================================================
# 【skip case 归档副本】 - 小欧 2026-08-12 10:43:59
# 原路径: backend/tests/validate/test_url_validator.py
# 归档原因: 包含 DNS 不可用类 skip case(test_https_subdomain),
#           已从 backend/tests 原文件删除对应 skip case, 此处保留完整代码,
#           便于在 DNS 可用环境恢复运行。
# ================================================================
# validate/url_validator.py 鍗曞厓测试 鈥?小欧矆 2026-06-27
import pytest
from app.tools.validate.url_validator import (
    validate_url,
    validate_proxy,
    _is_private_or_loopback_ip,
)


class TestValidateUrl:
    """validate_url() 鍗曞厓测试"""

    def test_empty_url(self):
        assert validate_url("") == (False, "URL不能为空", None)

    def test_none_url(self):
        assert validate_url(None) == (False, "URL不能为空", None)

    def test_url_without_scheme(self):
        """urlparse survives most inputs, so empty-scheme URLs hit protocol check"""
        result = validate_url("not-a-url")
        assert result[0] is False
        assert "不允许的协议" in result[1]

    def test_http_protocol_allowed(self):
        result = validate_url("http://www.example.com")
        assert result[0] is True
        assert result[1] is None

    def test_https_valid_url(self):
        assert validate_url("https://www.example.com") == (True, None, None)

    def test_localhost_ipv4(self):
        result = validate_url("https://127.0.0.1/path")
        assert result[0] is False
        assert "不允许访问回环地址" in result[1]

    def test_localhost_name(self):
        result = validate_url("https://localhost")
        assert result[0] is False
        assert "不允许访问回环地址" in result[1]

    def test_loopback_zero(self):
        result = validate_url("https://0.0.0.0")
        assert result[0] is False
        assert "不允许访问回环地址" in result[1]

    def test_private_ip_192_168(self):
        result = validate_url("https://192.168.1.100")
        assert result[0] is False
        assert "不允许访问内网地址" in result[1]

    def test_private_ip_10_0(self):
        result = validate_url("https://10.0.0.1")
        assert result[0] is False
        assert "不允许访问内网地址" in result[1]

    def test_private_ip_172_16(self):
        result = validate_url("https://172.16.0.1")
        assert result[0] is False
        assert "不允许访问内网地址" in result[1]

    def test_private_ip_172_31(self):
        result = validate_url("https://172.31.0.1")
        assert result[0] is False
        assert "不允许访问内网地址" in result[1]

    def test_literal_ip_warning(self):
        result = validate_url("https://8.8.8.8/path")
        assert result[0] is True
        assert result[1] is None
        assert "目标为IP地址而非域名，请确认" in result[2]

    def test_normal_domain(self):
        assert validate_url("https://www.example.com") == (True, None, None)

    def test_url_with_port(self):
        result = validate_url("https://example.com:443/v1/data")
        if result[0] is False and "DNS" in (result[1] or ""):
            pytest.skip("DNS不可用,跳过")
        assert result[0] is True

    def test_url_with_query_string(self):
        assert validate_url("https://example.com/search?q=test&page=1") == (True, None, None)

    def test_url_with_fragment(self):
        assert validate_url("https://example.com/page#section") == (True, None, None)

    def test_https_subdomain(self):
        result = validate_url("https://sub.domain.example.com")
        if result[0] is False and "DNS" in (result[1] or ""):
            pytest.skip("DNS不可用,跳过")
        assert result[0] is True


class TestValidateProxy:
    """validate_proxy() 鍗曞厓测试"""

    def test_empty_proxy(self):
        assert validate_proxy("") == (True, None, None)

    def test_none_proxy(self):
        assert validate_proxy(None) == (True, None, None)

    def test_invalid_proxy_url(self):
        """urlparse is very permissive; this URL lacks hostname triggering missing-hostname path"""
        result = validate_proxy(":::invalid")
        assert result[0] is False
        assert "缺少主机名" in result[1]

    def test_proxy_localhost_rejected(self):
        result = validate_proxy("http://localhost:8080")
        assert result[0] is False
        assert "不允许使用localhost作为proxy" in result[1]

    def test_proxy_loopback_ip_rejected(self):
        result = validate_proxy("http://127.0.0.1:3128")
        assert result[0] is False
        assert "不允许使用localhost作为proxy" in result[1]

    def test_proxy_private_ip_rejected(self):
        result = validate_proxy("http://192.168.1.100:3128")
        assert result[0] is False
        assert "不允许使用内网地址作为proxy" in result[1]

    def test_proxy_10_net_rejected(self):
        result = validate_proxy("http://10.0.0.1:3128")
        assert result[0] is False
        assert "不允许使用内网地址作为proxy" in result[1]

    def test_proxy_172_16_net_rejected(self):
        result = validate_proxy("http://172.16.0.1:3128")
        assert result[0] is False
        assert "不允许使用内网地址作为proxy" in result[1]

    def test_valid_proxy(self):
        assert validate_proxy("https://proxy.example.com:8080") == (True, None, None)

    def test_valid_proxy_with_credentials(self):
        assert validate_proxy("https://user:pass@proxy.example.com:3128") == (True, None, None)


class TestIsPrivateOrLoopbackIp:
    """_is_private_or_loopback_ip() 鍗曞厓测试"""

    def test_private_10_net(self):
        assert _is_private_or_loopback_ip("10.0.0.1") is True

    def test_private_192_168(self):
        assert _is_private_or_loopback_ip("192.168.1.1") is True

    def test_private_172_16(self):
        assert _is_private_or_loopback_ip("172.16.0.1") is True

    def test_private_172_31(self):
        assert _is_private_or_loopback_ip("172.31.255.255") is True

    def test_loopback_127(self):
        assert _is_private_or_loopback_ip("127.0.0.1") is True

    def test_loopback_ipv6(self):
        assert _is_private_or_loopback_ip("::1") is True

    def test_public_ip(self):
        assert _is_private_or_loopback_ip("8.8.8.8") is False

    def test_public_ip_1_1_1_1(self):
        assert _is_private_or_loopback_ip("1.1.1.1") is False

    def test_invalid_string(self):
        assert _is_private_or_loopback_ip("not_an_ip") is False

    def test_empty_string(self):
        assert _is_private_or_loopback_ip("") is False

    def test_hex_encoding_ssrf(self):
        assert _is_private_or_loopback_ip("0x7f000001") is True

    def test_decimal_integer_ssrf(self):
        assert _is_private_or_loopback_ip("2130706433") is True

    def test_octal_ip_ssrf(self):
        assert _is_private_or_loopback_ip("0177.0.0.01") is True

    def test_link_local_not_flagged(self):
        assert _is_private_or_loopback_ip("169.254.1.1") is True
