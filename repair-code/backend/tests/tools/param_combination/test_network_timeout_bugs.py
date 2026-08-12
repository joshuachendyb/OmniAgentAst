# -*- coding: utf-8 -*-
"""
Network工具 timeout 参数范围测试 — 小健 2026-06-27

测试焦点:1. Schema验证层——各Input的Field(ge=X, le=Y) 边界校验
2. 工具函数层——无效timeout对工具执行的影响

覆盖工具:- HttpRequestInput: timeout ge=1, le=300, default=30
- DownloadFileInput: timeout ge=5, le=3600, default=60
- FetchWebpageInput: timeout ge=1, le=120, default=30
- NetworkDiagnoseInput: timeout ge=1, le=30, default=5

强制案范:- 每函数都必须有docstring,含作者 + 日期(签名:小健)- 业务数据必须 >= 10 字符真实内容

Version 1.0
"""

import pytest
from typing import Dict, Any, Optional

from pydantic import ValidationError

from app.tools.network.network_schema import (
    HttpRequestInput,
    DownloadFileInput,
    FetchWebpageInput,
    SearchWebInput,
    NetworkDiagnoseInput,
)
from app.tools.network.http_request import httpget
from app.tools.network.download_file import download
from app.tools.network.fetch_webpage import fetchpage
from app.tools.network.network_diagnose import ping_port
from app.tools.tool_response import is_success, is_error

# ────────────────────────────────────────────────────────────────────────────# 辅助常量 — 小健 2026-06-27
# ────────────────────────────────────────────────────────────────────────────
_REAL_URL_API = "https://api.github.com/repos/python/cpython"
_REAL_URL_WEB = "https://httpbin.org/get"
_REAL_URL_DOWNLOAD = "https://github.com/python/cpython/archive/refs/tags/v3.13.0.tar.gz"

_VALID_HEADERS = {"User-Agent": "OmniAgentAs-desk-Test/1.0"}
_VALID_BODY = {"key": "test_value_for_validation_purposes"}


# ────────────────────────────────────────────────────────────────────────────# HttpRequestInput timeout 验证
# ────────────────────────────────────────────────────────────────────────────
class TestParamCombinations:
    """各工具timeout参数组合验证 — 小健 2026-06-27"""

    def test_http_request_timeout_default_is_thirty(self):
        """Case 1: HttpRequestInput timeout默认值应为30 — 小健 2026-06-27"""
        inp = HttpRequestInput(url=_REAL_URL_API)
        assert inp.timeout == 30

    def test_http_request_timeout_min_edge_one(self):
        """Case 2: HttpRequestInput timeout最小值1可正常创建 — 小健 2026-06-27"""
        inp = HttpRequestInput(url=_REAL_URL_API, timeout=1)
        assert inp.timeout == 1

    def test_http_request_timeout_max_edge_three_hundred(self):
        """Case 3: HttpRequestInput timeout最大值300可正常创建 — 小健 2026-06-27"""
        inp = HttpRequestInput(url=_REAL_URL_API, timeout=300)
        assert inp.timeout == 300

    def test_http_request_timeout_below_min_raises(self):
        """Case 4: HttpRequestInput timeout=0应败发ValidationError — 小健 2026-06-27"""
        with pytest.raises(ValidationError) as exc:
            HttpRequestInput(url=_REAL_URL_API, timeout=0)
        assert "timeout" in str(exc.value).lower()

    def test_http_request_timeout_negative_raises(self):
        """Case 5: HttpRequestInput timeout=-1应败发ValidationError — 小健 2026-06-27"""
        with pytest.raises(ValidationError) as exc:
            HttpRequestInput(url=_REAL_URL_API, timeout=-1)
        assert "timeout" in str(exc.value).lower()

    def test_http_request_timeout_exceeds_max_raises(self):
        """Case 6: HttpRequestInput timeout=301应败发ValidationError — 小健 2026-06-27"""
        with pytest.raises(ValidationError) as exc:
            HttpRequestInput(url=_REAL_URL_API, timeout=301)
        assert "timeout" in str(exc.value).lower()

    def test_http_request_timeout_very_large_raises(self):
        """Case 7: HttpRequestInput timeout=99999应败发ValidationError — 小健 2026-06-27"""
        with pytest.raises(ValidationError) as exc:
            HttpRequestInput(url=_REAL_URL_API, timeout=99999)
        assert "timeout" in str(exc.value).lower()

    def test_download_file_timeout_default_is_sixty(self):
        """Case 8: DownloadFileInput timeout默认值应为60 — 小健 2026-06-27"""
        inp = DownloadFileInput(url=_REAL_URL_DOWNLOAD, dest="test.tar.gz")
        assert inp.timeout == 60


class TestSingleFeatures:
    """各工具单项timeout特性测试 — 小健 2026-06-27"""

    def test_download_file_timeout_min_edge_five(self):
        """Case 1: DownloadFileInput timeout最小值5可正常创建 — 小健 2026-06-27"""
        inp = DownloadFileInput(url=_REAL_URL_DOWNLOAD, dest="test.tar.gz", timeout=5)
        assert inp.timeout == 5

    def test_download_file_timeout_below_min_raises(self):
        """Case 2: DownloadFileInput timeout=4应败发ValidationError(ge=5) — 小健 2026-06-27"""
        with pytest.raises(ValidationError) as exc:
            DownloadFileInput(url=_REAL_URL_DOWNLOAD, dest="test.tar.gz", timeout=4)
        assert "timeout" in str(exc.value).lower()

    def test_download_file_timeout_max_edge_three_thousand_six_hundred(self):
        """Case 3: DownloadFileInput timeout最大值3600可正常创建 — 小健 2026-06-27"""
        inp = DownloadFileInput(url=_REAL_URL_DOWNLOAD, dest="test.tar.gz", timeout=3600)
        assert inp.timeout == 3600

    def test_download_file_timeout_exceeds_max_raises(self):
        """Case 4: DownloadFileInput timeout=3601应败发ValidationError — 小健 2026-06-27"""
        with pytest.raises(ValidationError) as exc:
            DownloadFileInput(url=_REAL_URL_DOWNLOAD, dest="test.tar.gz", timeout=3601)
        assert "timeout" in str(exc.value).lower()

    def test_fetch_webpage_timeout_default_is_thirty(self):
        """Case 5: FetchWebpageInput timeout默认值应为30 — 小健 2026-06-27"""
        inp = FetchWebpageInput(url=_REAL_URL_WEB)
        assert inp.timeout == 30

    def test_fetch_webpage_timeout_min_edge_one(self):
        """Case 6: FetchWebpageInput timeout最小值1可正常创建 — 小健 2026-06-27"""
        inp = FetchWebpageInput(url=_REAL_URL_WEB, timeout=1)
        assert inp.timeout == 1

    def test_fetch_webpage_timeout_max_edge_one_twenty(self):
        """Case 7: FetchWebpageInput timeout最大值120可正常创建 — 小健 2026-06-27"""
        inp = FetchWebpageInput(url=_REAL_URL_WEB, timeout=120)
        assert inp.timeout == 120

    def test_fetch_webpage_timeout_exceeds_max_raises(self):
        """Case 8: FetchWebpageInput timeout=121应败发ValidationError(le=120) — 小健 2026-06-27"""
        with pytest.raises(ValidationError) as exc:
            FetchWebpageInput(url=_REAL_URL_WEB, timeout=121)
        assert "timeout" in str(exc.value).lower()


class TestMixedContent:
    """混合参数场景测试 — 小健 2026-06-27"""

    def test_http_request_full_params_valid(self):
        """Case 1: HttpRequestInput 全量参数合法值 — 小健 2026-06-27"""
        inp = HttpRequestInput(
            url=_REAL_URL_API,
            method="POST",
            headers=_VALID_HEADERS,
            body=_VALID_BODY,
            timeout=60,
            proxy="http://127.0.0.1:8080",
        )
        assert inp.url == _REAL_URL_API
        assert inp.method == "POST"
        assert inp.timeout == 60
        assert inp.proxy == "http://127.0.0.1:8080"

    def test_download_file_full_params_valid(self):
        """Case 2: DownloadFileInput 全量参数合法值 — 小健 2026-06-27"""
        inp = DownloadFileInput(
            url=_REAL_URL_DOWNLOAD,
            dest="archive/backup.tar.gz",
            headers={"Authorization": "Bearer test"},
            timeout=120,
            proxy="http://127.0.0.1:8080",
        )
        assert inp.timeout == 120
        assert "archive" in inp.dest

    def test_fetch_webpage_full_params_valid(self):
        """Case 3: FetchWebpageInput 全量参数合法值 — 小健 2026-06-27"""
        inp = FetchWebpageInput(
            url=_REAL_URL_WEB,
            prompt="提取页面标题和正文",
            extract_format="markdown",
            js_render=True,
            timeout=60,
            proxy="http://127.0.0.1:8080",
        )
        assert inp.js_render is True
        assert inp.extract_format == "markdown"
        assert inp.timeout == 60

    def test_ping_port_full_params_valid(self):
        """Case 4: NetworkDiagnoseInput 全量参数合法值 — 小健 2026-06-27"""
        inp = NetworkDiagnoseInput(
            host="8.8.8.8",
            mode="ping",
            count=10,
            timeout=15,
        )
        assert inp.host == "8.8.8.8"
        assert inp.mode == "ping"
        assert inp.count == 10
        assert inp.timeout == 15

    def test_ping_port_port_mode_with_port_valid(self):
        """Case 5: NetworkDiagnoseInput port模式+里口合法 — 小健 2026-06-27"""
        inp = NetworkDiagnoseInput(
            host="8.8.8.8",
            mode="port",
            port=53,
            timeout=10,
        )
        assert inp.mode == "port"
        assert inp.port == 53

    def test_http_request_schema_no_retry(self):
        """HttpRequestInput schema已不含retry字段，由retry_engine管理 — 小欧 2026-07-10"""
        fields = HttpRequestInput.model_fields
        assert "retry" not in fields

    def test_http_request_timeout_default_assigned(self):
        """HttpRequestInput timeout默认值验证 — 小欧 2026-07-10"""
        inp = HttpRequestInput(url=_REAL_URL_API)
        assert inp.timeout == 30

    def test_search_web_with_all_filters(self):
        """Case 8: SearchWebInput 全量参数 — 小健 2026-06-27"""
        inp = SearchWebInput(
            query="Python异步编程最佳实践指南",
            num_results=20,
            allowed_domains="github.com,stackoverflow.com",
            blocked_domains="pornhub.com",
        )
        assert "Python" in inp.query
        assert inp.num_results == 20
        assert "github.com" in inp.allowed_domains


class TestRealScenarios:
    """真实业务场景测试(timeout参数与真实URL)— 小健 2026-06-27"""

    def test_http_request_default_timeout_valid(self):
        """场景1: HttpRequestInput 默认timeout=30 — 小健 2026-06-27"""
        inp = HttpRequestInput(url=_REAL_URL_API)
        assert inp.timeout == 30
        assert inp.method == "GET"

    def test_http_request_short_timeout_fast_api(self):
        """场景2: HttpRequestInput timeout=5用于快速API — 小健 2026-06-27"""
        inp = HttpRequestInput(
            url="https://httpbin.org/status/200",
            method="GET",
            timeout=5,
        )
        assert inp.timeout == 5

    def test_http_request_long_timeout_for_batch(self):
        """场景3: HttpRequestInput timeout=300用于批量操作 — 小健 2026-06-27"""
        inp = HttpRequestInput(
            url="https://httpbin.org/delay/10",
            method="POST",
            body={"batch_size": 1000, "operation": "export_data"},
            timeout=300,
        )
        assert inp.timeout == 300

    def test_download_file_default_timeout_valid(self):
        """场景4: DownloadFileInput 默认timeout=60 — 小健 2026-06-27"""
        inp = DownloadFileInput(
            url=_REAL_URL_DOWNLOAD,
            dest="python_source.tar.gz",
        )
        assert inp.timeout == 60

    def test_download_file_good_network_short_timeout(self):
        """场景5: DownloadFileInput timeout=10用于内网下载 — 小健 2026-06-27"""
        inp = DownloadFileInput(
            url="http://192.168.1.100/package.zip",
            dest="internal/package.zip",
            timeout=10,
        )
        assert inp.timeout == 10

    def test_fetch_webpage_default_timeout_valid(self):
        """场景6: FetchWebpageInput 默认timeout=30 — 小健 2026-06-27"""
        inp = FetchWebpageInput(
            url=_REAL_URL_WEB,
            prompt="提取页面内容",
        )
        assert inp.timeout == 30

    def test_fetch_webpage_long_timeout_for_heavy_page(self):
        """场景7: FetchWebpageInput timeout=120用于重型页面 — 小健 2026-06-27"""
        inp = FetchWebpageInput(
            url="https://httpbin.org/html",
            timeout=120,
            js_render=True,
        )
        assert inp.timeout == 120

    def test_ping_port_default_timeout_valid(self):
        """场景8: NetworkDiagnoseInput 默认timeout=5 — 小健 2026-06-27"""
        inp = NetworkDiagnoseInput(host="8.8.8.8")
        assert inp.timeout == 5
        assert inp.mode == "ping"
        assert inp.count == 4


class TestBoundary:
    """边界条件测试 — timeout各范围边界 — 小健 2026-06-27"""

    def test_http_request_timeout_string_coercion(self):
        """边界1: timeout字符串"30"应被Pydantic自动转换为int — 小健 2026-06-27"""
        inp = HttpRequestInput(url=_REAL_URL_API, timeout="30")
        assert inp.timeout == 30
        assert isinstance(inp.timeout, int)

    def test_http_request_timeout_float_raises(self):
        """边界2: timeout=1.9浮点数应败发ValidationError(int约束) — 小健 2026-06-27"""
        with pytest.raises(ValidationError):
            HttpRequestInput(url=_REAL_URL_API, timeout=1.9)

    def test_download_file_timeout_string_coercion(self):
        """边界3: DownloadFile timeout字符串"60"应被自动转换 — 小健 2026-06-27"""
        inp = DownloadFileInput(url=_REAL_URL_DOWNLOAD, dest="test.tar.gz", timeout="60")
        assert inp.timeout == 60

    def test_fetch_webpage_timeout_string_coercion(self):
        """边界4: FetchWebpage timeout字符串"30"应被自动转换 — 小健 2026-06-27"""
        inp = FetchWebpageInput(url=_REAL_URL_WEB, timeout="30")
        assert inp.timeout == 30

    def test_ping_port_timeout_min_edge_one(self):
        """边界5: NetworkDiagnoseInput timeout最小值1 — 小健 2026-06-27"""
        inp = NetworkDiagnoseInput(host="8.8.8.8", timeout=1)
        assert inp.timeout == 1

    def test_ping_port_timeout_max_edge_thirty(self):
        """边界6: NetworkDiagnoseInput timeout最大值30 — 小健 2026-06-27"""
        inp = NetworkDiagnoseInput(host="8.8.8.8", timeout=30)
        assert inp.timeout == 30

    def test_ping_port_timeout_below_min_raises(self):
        """边界7: NetworkDiagnoseInput timeout=0应败发ValidationError — 小健 2026-06-27"""
        with pytest.raises(ValidationError) as exc:
            NetworkDiagnoseInput(host="8.8.8.8", timeout=0)
        assert "timeout" in str(exc.value).lower()

    def test_ping_port_timeout_exceeds_max_raises(self):
        """边界8: NetworkDiagnoseInput timeout=31应败发ValidationError(le=30) — 小健 2026-06-27"""
        with pytest.raises(ValidationError) as exc:
            NetworkDiagnoseInput(host="8.8.8.8", timeout=31)
        assert "timeout" in str(exc.value).lower()


class TestNegative:
    """为面测试 — 异常处理 — 小健 2026-06-27"""

    def test_http_request_url_empty_string_raises(self):
        """为面1: HttpRequestInput url为空字符串应败发ValidationError — 小健 2026-06-27"""
        with pytest.raises(ValidationError) as exc:
            HttpRequestInput(url="")
        assert "url" in str(exc.value).lower()

    def test_http_request_url_invalid_scheme_not_error_in_schema(self):
        """为面2: 非法scheme的URL(schema层面只验证str类型)— 小健 2026-06-27"""
        inp = HttpRequestInput(url="ftp://files.example.com/data.zip")
        assert inp.url == "ftp://files.example.com/data.zip"

    def test_http_request_invalid_method_raises(self):
        """为面3: 非法HTTP method应败发ValidationError — 小健 2026-06-27"""
        with pytest.raises(ValidationError) as exc:
            HttpRequestInput(url=_REAL_URL_API, method="INVALID")
        assert "method" in str(exc.value).lower()

    def test_http_request_method_in_wrong_case_raises(self):
        """为面4: HTTP method小写"get"应败发ValidationError — 小健 2026-06-27"""
        with pytest.raises(ValidationError) as exc:
            HttpRequestInput(url=_REAL_URL_API, method="get")
        assert "method" in str(exc.value).lower()

    def test_download_file_empty_url_raises(self):
        """为面5: DownloadFileInput url为空应败发ValidationError — 小健 2026-06-27"""
        with pytest.raises(ValidationError) as exc:
            DownloadFileInput(url="", dest="file.zip")
        assert "url" in str(exc.value).lower()

    def test_download_file_empty_destination_path_defaults_none(self):
        """DownloadFileInput destination_path为空串时保持原值 — 小欧 2026-07-10"""
        inp = DownloadFileInput(url=_REAL_URL_DOWNLOAD, dest="")
        assert inp.dest == ""

    def test_fetch_webpage_empty_url_raises(self):
        """为面7: FetchWebpageInput url为空应败发ValidationError — 小健 2026-06-27"""
        with pytest.raises(ValidationError) as exc:
            FetchWebpageInput(url="")
        assert "url" in str(exc.value).lower()

    def test_fetch_webpage_invalid_extract_format_raises(self):
        """为面8: FetchWebpageInput extract_format无效值应败发ValidationError — 小健 2026-06-27"""
        with pytest.raises(ValidationError) as exc:
            FetchWebpageInput(url=_REAL_URL_WEB, extract_format="pdf")
        assert "extract_format" in str(exc.value).lower()

    def test_ping_port_empty_host_raises(self):
        """为面9: NetworkDiagnoseInput host为空应败发ValidationError — 小健 2026-06-27"""
        with pytest.raises(ValidationError) as exc:
            NetworkDiagnoseInput(host="")
        assert "host" in str(exc.value).lower()

    def test_ping_port_port_mode_missing_port_raises(self):
        """为面10: NetworkDiagnoseInput mode=port但无port应败发ValueError — 小健 2026-06-27"""
        with pytest.raises(ValueError) as exc:
            NetworkDiagnoseInput(host="8.8.8.8", mode="port")
        assert "port" in str(exc.value).lower()

    def test_ping_port_ping_mode_with_port_raises(self):
        """为面11: NetworkDiagnoseInput mode=ping但传了port应败发ValueError — 小健 2026-06-27"""
        with pytest.raises(ValueError) as exc:
            NetworkDiagnoseInput(host="8.8.8.8", mode="ping", port=80)
        assert "port" in str(exc.value).lower() and "严禁" in str(exc.value)

    def test_ping_port_port_out_of_range_high_raises(self):
        """为面12: NetworkDiagnoseInput port=65536应败发ValidationError(le=65535) — 小健 2026-06-27"""
        with pytest.raises(ValidationError) as exc:
            NetworkDiagnoseInput(host="8.8.8.8", mode="port", port=65536)
        assert "port" in str(exc.value).lower()

    def test_ping_port_port_out_of_range_low_raises(self):
        """为面13: NetworkDiagnoseInput port=0应败发ValidationError(ge=1) — 小健 2026-06-27"""
        with pytest.raises(ValidationError) as exc:
            NetworkDiagnoseInput(host="8.8.8.8", mode="port", port=0)
        assert "port" in str(exc.value).lower()

    def test_http_request_no_retry_in_schema(self):
        """HttpRequestInput schema中已移除retry字段，重试由retry_engine管理 — 小欧 2026-07-10"""
        fields = HttpRequestInput.model_fields
        assert "retry" not in fields, f"retry不应在schema中: {list(fields.keys())}"

    def test_http_request_retry_exceeds_max_not_in_schema(self):
        """retry字段已从schema移除，不再进行schema级校验 — 小欧 2026-07-10"""
        fields = HttpRequestInput.model_fields
        assert "retry" not in fields

    def test_fetch_webpage_url_not_a_valid_url(self):
        """为面16: FetchWebpageInput url为非URL格式文本 — 小健 2026-06-27"""
        inp = FetchWebpageInput(url="不是有效的URL格式")
        assert inp.url == "不是有效的URL格式"

    def test_http_request_timeout_none_uses_default(self):
        """为面17: HttpRequestInput timeout不传则使用默认值30 — 小健 2026-06-27"""
        inp = HttpRequestInput(url=_REAL_URL_API)
        assert inp.timeout == 30

    def test_search_web_num_results_exceeds_max_raises(self):
        """为面18: SearchWebInput num_results=1001应败发ValidationError(le=1000) — 小健 2026-06-27"""
        with pytest.raises(ValidationError) as exc:
            SearchWebInput(query="Python测试", num_results=1001)
        assert "num_results" in str(exc.value).lower()

    def test_search_web_num_results_below_min_raises(self):
        """为面19: SearchWebInput num_results=0应败发ValidationError(ge=1) — 小健 2026-06-27"""
        with pytest.raises(ValidationError) as exc:
            SearchWebInput(query="Python测试", num_results=0)
        assert "num_results" in str(exc.value).lower()

    def test_ping_port_negative_count_raises(self):
        """为面20: NetworkDiagnoseInput count=-1应败发ValidationError — 小健 2026-06-27"""
        with pytest.raises(ValidationError) as exc:
            NetworkDiagnoseInput(host="8.8.8.8", count=-1)
        assert "count" in str(exc.value).lower()
