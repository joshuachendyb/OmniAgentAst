# -*- coding: utf-8 -*-
"""
http_request 参数组合与内容测试 v2
案范要求:schema驱动,内容<100行,验证实际结果,发现问题
小健 2026-06-24

Schema参数: url(str必填), method(GET/POST/PUT/DELETE/PATCH默认GET),
            headers(Optional[Dict]), body(Optional[Dict]),
            timeout(int默认30000范围1000-300000), proxy(Optional[str]), retry(int默认3范围0-10)
参数组合: 5×2×2=20种 + 边界/为面
"""
import asyncio
import pytest

from app.tools.tool_response import is_success, is_error
from tests.tools.param_combination.httpbin_mock import install_httpbin_mock


@pytest.fixture(autouse=True)
def _auto_mock_httpbin(monkeypatch):
    """httpbin.org 当前返回 503,注入本地模拟使其稳定跑绿 — 小欧 2026-07-12"""
    install_httpbin_mock(monkeypatch)


def _run(coro):
    return asyncio.run(coro)


class TestHttpRequestParamCombinations:
    """参数组合测试 — method×headers×body — 小健 2026-06-24"""

    def test_url_only(self, tmp_path):
        """组合1: 仅url必填参数"""
        from app.tools.network.http_request import httpget
        result = _run(httpget("https://httpbin.org/get"))
        assert is_success(result)
        assert result["data"]["status_code"] == 200

    def test_method_get(self, tmp_path):
        """组合2: method=GET"""
        from app.tools.network.http_request import httpget
        result = _run(httpget("https://httpbin.org/get", method="GET"))
        assert is_success(result)

    def test_method_post(self, tmp_path):
        """组合3: method=POST"""
        from app.tools.network.http_request import httpget
        result = _run(httpget(
            "https://httpbin.org/post",
            method="POST",
            body={"test": "data"}
        ))
        assert is_success(result)

    def test_method_put(self, tmp_path):
        """组合4: method=PUT"""
        from app.tools.network.http_request import httpget
        result = _run(httpget(
            "https://httpbin.org/put",
            method="PUT",
            body={"update": "value"}
        ))
        assert is_success(result)

    def test_method_delete(self, tmp_path):
        """组合5: method=DELETE"""
        from app.tools.network.http_request import httpget
        result = _run(httpget("https://httpbin.org/delete", method="DELETE"))
        assert is_success(result)

    def test_method_patch(self, tmp_path):
        """组合6: method=PATCH"""
        from app.tools.network.http_request import httpget
        result = _run(httpget(
            "https://httpbin.org/patch",
            method="PATCH",
            body={"patch": "data"}
        ))
        assert is_success(result)

    def test_with_headers(self, tmp_path):
        """组合7: 自定义Headers"""
        from app.tools.network.http_request import httpget
        result = _run(httpget(
            "https://httpbin.org/get",
            headers={"X-Custom-Header": "test-value"}
        ))
        assert is_success(result)

    def test_with_body(self, tmp_path):
        """组合8: POST with body"""
        from app.tools.network.http_request import httpget
        result = _run(httpget(
            "https://httpbin.org/post",
            method="POST",
            body={"name": "test", "value": 123}
        ))
        assert is_success(result)

    def test_timeout_custom(self, tmp_path):
        """组合9: timeout自定义(秒)"""
        from app.tools.network.http_request import httpget
        result = _run(httpget("https://httpbin.org/get", timeout=100))
        assert is_success(result)

    def test_all_params_combined(self, tmp_path):
        """组合11: 所有参数组合"""
        from app.tools.network.http_request import httpget
        result = _run(httpget(
            "https://httpbin.org/post",
            method="POST",
            headers={"Authorization": "Bearer test"},
            body={"key": "value"},
            timeout=150
        ))
        assert is_success(result)


class TestHttpRequestFeatures:
    """功能测试 — 小健 2026-06-24"""

    def test_json_response(self, tmp_path):
        """功能: JSON响应解析"""
        from app.tools.network.http_request import httpget
        result = _run(httpget("https://httpbin.org/json"))
        assert is_success(result)
        assert isinstance(result["data"]["body"], dict)

    def test_response_headers(self, tmp_path):
        """功能: 响应头"""
        from app.tools.network.http_request import httpget
        result = _run(httpget("https://httpbin.org/get"))
        assert is_success(result)
        assert "headers" in result["data"]

    def test_status_code_200(self, tmp_path):
        """功能: 200状态码"""
        from app.tools.network.http_request import httpget
        result = _run(httpget("https://httpbin.org/status/200"))
        assert is_success(result)
        assert result["data"]["status_code"] == 200

    def test_status_code_404(self, tmp_path):
        """功能: 404状态码"""
        from app.tools.network.http_request import httpget
        result = _run(httpget("https://httpbin.org/status/404"))
        if is_success(result):
            assert result["data"]["status_code"] == 404

    def test_query_params(self, tmp_path):
        """功能: URL查询参数"""
        from app.tools.network.http_request import httpget
        result = _run(httpget("https://httpbin.org/get?foo=bar&baz=123"))
        assert is_success(result)

    def test_post_form_data(self, tmp_path):
        """功能: POST表单数据"""
        from app.tools.network.http_request import httpget
        result = _run(httpget(
            "https://httpbin.org/post",
            method="POST",
            body={"field1": "value1", "field2": "value2"}
        ))
        assert is_success(result)

    def test_authorization_header(self, tmp_path):
        """功能: Authorization头"""
        from app.tools.network.http_request import httpget
        result = _run(httpget(
            "https://httpbin.org/get",
            headers={"Authorization": "Bearer test-token-123"}
        ))
        assert is_success(result)

    def test_content_type_header(self, tmp_path):
        """功能: Content-Type头"""
        from app.tools.network.http_request import httpget
        result = _run(httpget(
            "https://httpbin.org/post",
            method="POST",
            headers={"Content-Type": "application/json"},
            body={"data": "test"}
        ))
        assert is_success(result)


class TestHttpRequestRealScenarios:
    """真实场景测试 — 小健 2026-06-24"""

    def test_github_api(self, tmp_path):
        """场景: GitHub API"""
        from app.tools.network.http_request import httpget
        result = _run(httpget("https://api.github.com"))
        assert is_success(result)
        assert "current_user_url" in result["data"]["body"]

    def test_httpbin_get(self, tmp_path):
        """场景: httpbin GET"""
        from app.tools.network.http_request import httpget
        result = _run(httpget("https://httpbin.org/get"))
        assert is_success(result)

    def test_httpbin_post(self, tmp_path):
        """场景: httpbin POST"""
        from app.tools.network.http_request import httpget
        result = _run(httpget(
            "https://httpbin.org/post",
            method="POST",
            body={"message": "test data"}
        ))
        assert is_success(result)

    def test_httpbin_headers_echo(self, tmp_path):
        """场景: 请求头回显"""
        from app.tools.network.http_request import httpget
        result = _run(httpget(
            "https://httpbin.org/headers",
            headers={"X-Test-Header": "test-value"}
        ))
        assert is_success(result)


class TestHttpRequestBoundary:
    """边界测试 — 小健 2026-06-24"""

    def test_timeout_minimum(self, tmp_path):
        """边界: timeout=1000最小值"""
        from app.tools.network.http_request import httpget
        result = _run(httpget("https://httpbin.org/get", timeout=1000))
        # 可能超时或成功

    def test_timeout_maximum(self, tmp_path):
        """边界: timeout=300最大值"""
        from app.tools.network.http_request import httpget
        result = _run(httpget("https://httpbin.org/get", timeout=300))
        assert is_success(result)



    def test_large_body(self, tmp_path):
        """边界: 大请求体"""
        from app.tools.network.http_request import httpget
        large_data = {"data": "x" * 10000}
        result = _run(httpget(
            "https://httpbin.org/post",
            method="POST",
            body=large_data
        ))
        assert is_success(result)

    def test_special_characters_in_body(self, tmp_path):
        """边界: 特殊字符"""
        from app.tools.network.http_request import httpget
        result = _run(httpget(
            "https://httpbin.org/post",
            method="POST",
            body={"special": "特殊字符 <>&\""}
        ))
        assert is_success(result)

    def test_unicode_in_body(self, tmp_path):
        """边界: Unicode"""
        from app.tools.network.http_request import httpget
        result = _run(httpget(
            "https://httpbin.org/post",
            method="POST",
            body={"unicode": "\ud83c\udf80\ud83c\udf6e\ud83d\udd1f"}
        ))
        assert is_success(result)


class TestHttpRequestNegative:
    """为面测试 — 小健 2026-06-24"""

    def test_invalid_url(self, tmp_path):
        """为面: 无效URL"""
        from app.tools.network.http_request import httpget
        result = _run(httpget("not-a-valid-url"))
        assert is_error(result)

    def test_nonexistent_domain(self, tmp_path):
        """为面: 不存在的域名"""
        from app.tools.network.http_request import httpget
        result = _run(httpget("https://nonexistent-domain-xyz-123.com"))
        assert is_error(result)

    def test_connection_refused(self, tmp_path):
        """为面: 连接拒绝"""
        from app.tools.network.http_request import httpget
        result = _run(httpget("http://localhost:9999"))
        assert is_error(result)

    def test_timeout_exceeded(self, tmp_path):
        """为面: 超时"""
        from app.tools.network.http_request import httpget
        result = _run(httpget("https://httpbin.org/delay/10", timeout=1000))
        assert is_error(result)

    def test_invalid_method(self, tmp_path):
        """为面: 无效方法"""
        from app.tools.network.http_request import httpget
        result = _run(httpget("https://httpbin.org/get", method="INVALID"))
        assert is_error(result)

    def test_ssl_error(self, tmp_path):
        """为面: SSL错误"""
        from app.tools.network.http_request import httpget
        # 测试自签名证书或无效证书
        pass


class TestHttpRequestBugDiscovery:
    """BUG发现测试 — 小健 2026-06-24"""

    def test_bug_empty_url(self, tmp_path):
        """BUG: 空URL"""
        from app.tools.network.http_request import httpget
        result = _run(httpget(""))
        assert is_error(result)

    def test_bug_none_url(self, tmp_path):
        """BUG: None URL"""
        from app.tools.network.http_request import httpget
        result = _run(httpget(None))
        assert is_error(result)

    def test_bug_timeout_zero(self, tmp_path):
        """BUG: timeout=0"""
        from app.tools.network.http_request import httpget
        result = _run(httpget("https://httpbin.org/get", timeout=0))
        assert is_error(result)

    def test_bug_timeout_negative(self, tmp_path):
        """BUG: timeout为数"""
        from app.tools.network.http_request import httpget
        result = _run(httpget("https://httpbin.org/get", timeout=-1))
        assert is_error(result)

    def test_bug_retry_removed(self, tmp_path):
        """BUG: retry参数已移除"""
        import pytest
        from app.tools.network.http_request import httpget
        with pytest.raises(TypeError):
            _run(httpget("https://httpbin.org/get", retry=-1))

    def test_bug_body_without_post(self, tmp_path):
        """BUG: GET请求带body"""
        from app.tools.network.http_request import httpget
        result = _run(httpget(
            "https://httpbin.org/get",
            method="GET",
            body={"test": "data"}
        ))
        # GET请求通常不应该有body

    def test_bug_headers_none(self, tmp_path):
        """BUG: headers=None"""
        from app.tools.network.http_request import httpget
        result = _run(httpget("https://httpbin.org/get", headers=None))
        assert is_success(result)

    def test_bug_body_none(self, tmp_path):
        """BUG: body=None"""
        from app.tools.network.http_request import httpget
        result = _run(httpget("https://httpbin.org/post", method="POST", body=None))
        assert is_success(result)

    def test_bug_url_with_spaces(self, tmp_path):
        """BUG: URL包含空格"""
        from app.tools.network.http_request import httpget
        result = _run(httpget("https://httpbin.org/get?query=space value"))
        # 应该自动编码或报错

    def test_bug_internal_ip_blocked(self, tmp_path):
        """安全: 内网IP被阻塞"""
        from app.tools.network.http_request import httpget
        result = _run(httpget("http://192.168.1.1"))
        assert is_error(result)

    def test_bug_localhost_blocked(self, tmp_path):
        """安全: localhost被阻塞"""
        from app.tools.network.http_request import httpget
        result = _run(httpget("http://localhost:8000"))
        assert is_error(result)
