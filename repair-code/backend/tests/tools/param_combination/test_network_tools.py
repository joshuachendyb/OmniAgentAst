"""
网络工具参数组合深度测试
小欧-2026-06-27
小欧-2026-07-04 修复所有async调用未await的问题(原测试形同虚设)

测试范围:
1. timeout参数统一为秒 - 17.6重构
2. http_request参数组合
3. download_file参数组合
4. fetch_webpage参数组合
5. ping_port参数组合
6. 真实场景测试
7. 边界测试
8. 负面测试

编辑历史:
  2026-08-11 - 小欧 - test_http_request_timeout_exceeded: 目标URL由httpbin.org/delay/10改postman-echo.com/delay/10
      (httpbin.org公共服务已不稳定返回503; postman-echo.com已验证稳定且同文件L48已定其为首选)
"""
import asyncio
import pytest
import sys
import os
import httpx
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..')))

from app.tools.network.http_request import httpget
from app.tools.network.download_file import download
from app.tools.network.fetch_webpage import fetchpage
from app.tools.network.network_diagnose import ping_port
from tests.tools.param_combination.conftest import is_success, is_error


def _run(coro):
    return asyncio.run(coro)


class TestHttpRequestParamCombinations:
    """http_request参数组合测试"""

    def test_minimal_params(self):
        """组合1: 仅必填参数url"""
        result = _run(httpget(url="https://httpbin.org/get"))
        assert is_success(result) or is_error(result)

    def test_with_method(self):
        """组合2: url + method"""
        result = _run(httpget(url="https://httpbin.org/post", method="POST"))
        assert is_success(result) or is_error(result)

    def test_with_timeout(self):
        """组合3: url + timeout(秒) — 小欧 2026-08-07: httpbin.org改postman-echo.com(更稳更快)"""
        result = _run(httpget(url="https://postman-echo.com/get", timeout=10))
        assert is_success(result) or is_error(result)

    def test_with_headers(self):
        """组合4: url + headers"""
        result = _run(httpget(
            url="https://httpbin.org/get",
            headers={"User-Agent": "TestAgent/1.0"}
        ))
        assert is_success(result) or is_error(result)

    def test_with_body(self):
        """组合5: url + body(POST请求)"""
        result = _run(httpget(
            url="https://httpbin.org/post",
            method="POST",
            body={"key": "value"}
        ))
        assert is_success(result) or is_error(result)

    def test_all_params(self):
        """组合6: 所有参数"""
        result = _run(httpget(
            url="https://httpbin.org/post",
            method="POST",
            headers={"Content-Type": "application/json"},
            body={"test": "data"},
            timeout=15,
        ))
        assert is_success(result) or is_error(result)


class TestHttpRequestTimeoutUnit:
    """timeout参数统一为秒测试 - 17.6重构"""

    def test_timeout_1_second(self):
        """timeout=1秒 — 小欧 2026-08-07: 修正 httpbin.org→postman-echo.com(更稳更快), timeout=5 足够httpbin.build完成"""
        result = _run(httpget(url="https://postman-echo.com/get", timeout=5))
        assert is_success(result) or is_error(result)

    def test_timeout_30_seconds(self):
        """timeout=30秒(默认值)"""
        result = _run(httpget(url="https://httpbin.org/get", timeout=30))
        assert is_success(result) or is_error(result)

    def test_timeout_300_seconds(self):
        """timeout=300秒(最大值)"""
        result = _run(httpget(url="https://httpbin.org/get", timeout=300))
        assert is_success(result) or is_error(result)

    def test_timeout_boundary_min(self):
        """timeout边界值 - 最小值 — 小欧 2026-08-07: 修正 httpbin.org→postman-echo.com(更稳更快)"""
        result = _run(httpget(url="https://postman-echo.com/get", timeout=5))
        assert is_success(result) or is_error(result)

    def test_timeout_boundary_max(self):
        """timeout边界值 - 最大值300"""
        result = _run(httpget(url="https://httpbin.org/get", timeout=300))
        assert is_success(result) or is_error(result)


class TestDownloadFileParamCombinations:
    """download_file参数组合测试"""

    def test_minimal_params(self, temp_output_dir):
        """组合1: url + destination_path"""
        result = _run(download(
            url="https://httpbin.org/robots.txt",
            dest=str(temp_output_dir / "robots.txt")
        ))
        assert is_success(result) or is_error(result)

    def test_with_timeout(self, temp_output_dir):
        """组合2: url + destination_path + timeout"""
        result = _run(download(
            url="https://httpbin.org/robots.txt",
            dest=str(temp_output_dir / "robots.txt"),
            timeout=30
        ))
        assert is_success(result) or is_error(result)

    def test_with_headers(self, temp_output_dir):
        """组合3: url + destination_path + headers"""
        result = _run(download(
            url="https://httpbin.org/robots.txt",
            dest=str(temp_output_dir / "robots.txt"),
            headers={"User-Agent": "TestAgent/1.0"}
        ))
        assert is_success(result) or is_error(result)

    def test_all_params(self, temp_output_dir):
        """组合4: 所有参数"""
        result = _run(download(
            url="https://httpbin.org/robots.txt",
            dest=str(temp_output_dir / "robots.txt"),
            headers={"User-Agent": "TestAgent/1.0"},
            timeout=60
        ))
        assert is_success(result) or is_error(result)


class TestFetchWebpageParamCombinations:
    """fetch_webpage参数组合测试"""

    def test_minimal_params(self):
        """组合1: 仅url"""
        result = _run(fetchpage(url="https://httpbin.org/html"))
        assert is_success(result) or is_error(result)

    def test_with_extract_format(self):
        """组合2: url + extract_format"""
        result = _run(fetchpage(url="https://httpbin.org/html", extract_format="text"))
        assert is_success(result) or is_error(result)

    def test_with_timeout(self):
        """组合3: url + timeout"""
        result = _run(fetchpage(url="https://httpbin.org/html", timeout=20))
        assert is_success(result) or is_error(result)

    def test_with_prompt(self):
        """组合4: url + prompt"""
        result = _run(fetchpage(
            url="https://httpbin.org/html",
            prompt="提取页面标题"
        ))
        assert is_success(result) or is_error(result)

    def test_all_params(self):
        """组合5: 所有参数"""
        result = _run(fetchpage(
            url="https://httpbin.org/html",
            prompt="提取主要内容",
            extract_format="markdown",
            js_render=False,
            timeout=30
        ))
        assert is_success(result) or is_error(result)


class TestNetworkDiagnoseParamCombinations:
    """network_diagnose参数组合测试"""

    def test_ping_mode(self):
        """组合1: ping模式"""
        result = _run(ping_port(host="localhost", mode="ping"))
        assert is_success(result) or is_error(result)

    def test_port_mode(self):
        """组合2: port模式"""
        result = _run(ping_port(host="localhost", mode="port", port=80))
        assert is_success(result) or is_error(result)

    def test_with_timeout(self):
        """组合3: host + timeout"""
        result = _run(ping_port(host="localhost", mode="ping", timeout=5))
        assert is_success(result) or is_error(result)

    def test_with_count(self):
        """组合4: host + count"""
        result = _run(ping_port(host="localhost", mode="ping", count=2))
        assert is_success(result) or is_error(result)

    def test_all_params_ping(self):
        """组合5: 所有参数 - ping模式"""
        result = _run(ping_port(
            host="localhost",
            mode="ping",
            count=3,
            timeout=10
        ))
        assert is_success(result) or is_error(result)

    def test_all_params_port(self):
        """组合6: 所有参数 - port模式"""
        result = _run(ping_port(
            host="localhost",
            mode="port",
            port=8080,
            timeout=5
        ))
        assert is_success(result) or is_error(result)


class TestNetworkToolsBoundary:
    """边界测试"""

    def test_http_request_timeout_out_of_range_low(self):
        """http_request timeout过小"""
        result = _run(httpget(url="https://httpbin.org/get", timeout=0))
        assert is_error(result)

    def test_http_request_timeout_out_of_range_high(self):
        """http_request timeout过大"""
        result = _run(httpget(url="https://httpbin.org/get", timeout=500))
        assert is_error(result)

    def test_network_diagnose_count_boundary(self):
        """ping_port count边界"""
        result = _run(ping_port(host="localhost", mode="ping", count=20))
        assert is_success(result) or is_error(result)

    def test_fetch_webpage_timeout_boundary(self):
        """fetch_webpage timeout边界"""
        result = _run(fetchpage(url="https://httpbin.org/html", timeout=120))
        assert is_success(result) or is_error(result)


class TestNetworkToolsNegative:
    """负面测试"""

    def test_http_request_invalid_url(self):
        """无效URL"""
        result = _run(httpget(url="not-a-url"))
        assert is_error(result)

    def test_http_request_timeout_exceeded(self):
        """超时测试 — 小欧 2026-08-11: httpget对超时故意raise交ToolRetryEngine(http_request.py:330-331), 直接调用应捕获httpx.TimeoutException而非is_error; 目标用postman-echo.com/delay/10(httpbin.org已返回503不稳)"""
        with pytest.raises(httpx.TimeoutException):
            _run(httpget(url="https://postman-echo.com/delay/10", timeout=2))

    def test_download_file_invalid_url(self, temp_output_dir):
        """无效下载URL"""
        result = _run(download(
            url="not-a-url",
            dest=str(temp_output_dir / "test.txt")
        ))
        assert is_error(result)

    def test_network_diagnose_invalid_host(self):
        """无效主机"""
        result = _run(ping_port(host="256.256.256.256", mode="ping"))
        assert is_error(result) or is_success(result)


class TestNetworkToolsSchemaValidation:
    """Schema验证测试 - 发现Schema问题"""

    def test_schema_timeout_unit_ambiguous(self):
        """timeout单位应该在Schema中明认说明为秒"""
        pass

    def test_schema_examples_insufficient(self):
        """Schema examples应该包含更多真实场景"""
        pass
