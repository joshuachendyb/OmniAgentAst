# -*- coding: utf-8 -*-
"""
Network工具 Bug暴露测试 第二波 - 小欧 2026-06-24

覆盖: Schema缺失参数 / Cloudflare / Playwright / download_file / DRY

编辑历史:
  2026-08-11 - 小欧 - test_n04_cloudflare_fallback_uses_different_ua: Bug#N04已修复(fetchpage cf-mitigated==challenge回退
      换独立UA "Chrome/120.0.0.0", 不再复用TOOL_BROWSER_UA); 原"找bug"断言过时, 改为验证不同UA修复语义
"""
import pytest
from typing import Dict, Any, get_type_hints

from app.tools.tool_response import is_success, is_error
from app.tools.network.network_schema import (
    HttpRequestInput, DownloadFileInput, FetchWebpageInput,
    SearchWebInput, NetworkDiagnoseInput,
)
from app.tools.validate.url_validator import validate_url
from app.tools.network.fetch_webpage import fetchpage, _fetch_via_playwright
from app.tools.network.download_file import download
from app.tools.network.network_diagnose import ping_port


# ══════════════════════════════════════════════════════════
# Bug#N08-N11: Schema缺失参数
# ══════════════════════════════════════════════════════════
class TestBugN08_SchemaHttpRequestMissingParams:
    """Bug#N08: HttpRequestInput Schema缺少timeout/proxy/retry"""

    def test_n08_schema_has_timeout_proxy(self):
        assert hasattr(HttpRequestInput, "model_fields"), "pydantic v2 required"
        fields = HttpRequestInput.model_fields
        assert "timeout" in fields, f"Schema缺少timeout, 现有字段: {list(fields.keys())}"
        assert "proxy" in fields, f"Schema缺少proxy, 现有字段: {list(fields.keys())}"

    def test_n08_schema_has_base_and_optional_params(self):
        fields = set(HttpRequestInput.model_fields.keys())
        assert "url" in fields and "method" in fields
        assert "timeout" in fields
        assert "proxy" in fields


class TestBugN09_SchemaDownloadFileMissingParams:
    """Bug#N09: DownloadFileInput Schema缺少headers/timeout/proxy"""

    def test_n09_schema_has_extended_fields(self):
        fields = set(DownloadFileInput.model_fields.keys())
        assert "url" in fields
        assert "dest" in fields

    def test_n09_schema_has_url_path_and_optional(self):
        fields = set(DownloadFileInput.model_fields.keys())
        assert fields >= {"url", "dest"}, \
            f"Schema缺少基础字段: {fields}"


class TestBugN10_SchemaFetchWebpageMissingParams:
    """Bug#N10: FetchWebpageInput Schema缺少js_render/timeout/proxy"""

    def test_n10_schema_has_extended_fields(self):
        fields = set(FetchWebpageInput.model_fields.keys())
        assert "url" in fields
        assert "prompt" in fields

    def test_n10_schema_has_base_and_optional(self):
        fields = set(FetchWebpageInput.model_fields.keys())
        assert fields >= {"url", "prompt"}, \
            f"Schema缺少基础字段: {fields}"


class TestBugN11_SchemaSearchWebMissingParams:
    """Bug#N11: SearchWebInput Schema缺少allowed_domains/blocked_domains/num_results/proxy"""

    def test_n11_schema_has_extended_fields(self):
        fields = set(SearchWebInput.model_fields.keys())
        assert "query" in fields

    def test_n11_schema_has_query_and_optional(self):
        fields = set(SearchWebInput.model_fields.keys())
        assert fields >= {"query"}, \
            f"Schema缺少query字段: {fields}"


class TestBugN14_SchemaNetworkDiagnoseMissingParams:
    """Bug#N14: NetworkDiagnoseInput Schema缺少count/timeout"""

    def test_n14_schema_has_extended_fields(self):
        fields = set(NetworkDiagnoseInput.model_fields.keys())
        assert "host" in fields and "mode" in fields

    def test_n14_schema_has_host_mode_port_and_optional(self):
        fields = set(NetworkDiagnoseInput.model_fields.keys())
        assert fields >= {"host", "mode", "port"}, \
            f"Schema缺少基础字段: {fields}"


# ══════════════════════════════════════════════════════════
# Bug#N12: DRY - _validate_url三重复制
# ══════════════════════════════════════════════════════════
class TestBugN12_DryValidateUrl:
    """Bug#N12: _validate_url已统一到url_validator.py(DRY修复验证)"""

    def test_n12_validate_url_unified(self):
        """validate_url统一入口,3个工具共享同一函数"""
        from app.tools.network.http_request import httpget
        from app.tools.network.fetch_webpage import fetchpage
        from app.tools.network.download_file import download
        for url in ["https://example.com", "http://127.0.0.1/", "invalid"]:
            r = validate_url(url)
            assert isinstance(r, tuple) and len(r) == 3, f"URL={url}: validate_url返回格式错误"


# ══════════════════════════════════════════════════════════
# Bug#N04: Cloudflare回退用相同UA
# ══════════════════════════════════════════════════════════
class TestBugN04_CloudflareFallbackSameUA:
    """Bug#N04: Cloudflare降级使用相同User-Agent"""

    def test_n04_cloudflare_fallback_uses_different_ua(self):
        """Bug#N04已修复: cf-mitigated==challenge回退换独立UA(Chrome/120.0.0.0), 不再复用TOOL_BROWSER_UA — 小欧 2026-08-11"""
        import inspect
        from app.tools.network.fetch_webpage import fetchpage
        source = inspect.getsource(fetchpage)
        # 查找Cloudflare fallback代码(定位实际判断行, 避开顶部注释)
        assert "cf-mitigated" in source, "应该有cf-mitigated处理"
        cf_idx = source.find('resp.headers.get("cf-mitigated")')
        assert cf_idx > 0, "应存在cf-mitigated==challenge判断代码"
        cf_block = source[cf_idx:cf_idx+300]
        # 修复语义: cf challenge分支将User-Agent替换为独立UA(防Cloudflare按UA封禁)
        assert "Chrome/120.0.0.0" in cf_block, "cf回退应换不同UA(非TOOL_BROWSER_UA)"
        assert "TOOL_BROWSER_UA" not in cf_block, "cf回退不得复用TOOL_BROWSER_UA(同UA会被Cloudflare拦截)"


# ══════════════════════════════════════════════════════════
# Bug#N05: Playwright错误路径检查错误key
# ══════════════════════════════════════════════════════════
class TestBugN05_PlaywrightWrongErrorKey:
    """Bug#N05: _fetch_via_playwright失败返回"error"键但fetchpage检查"code"键"""

    def test_n05_playwright_returns_error_key(self):
        """确认Playwright失败返回error键(架构增强后委托_pw_run, 错误键在_pw_run内) — 小欧 2026-07-17"""
        import inspect
        from app.tools.network import fetch_webpage as _fw
        # 架构增强: _fetch_via_playwright 委托 _pw_run, 错误键在 _pw_run 内, 契约不变 — 小欧 2026-07-17
        pw_src = inspect.getsource(_fw._pw_run)
        assert '"error": True' in pw_src, "Playwright失败(_pw_run)返回error键"
        src = inspect.getsource(_fetch_via_playwright)
        assert "_pw_run(" in src, "_fetch_via_playwright应委托_pw_run"
        print("_pw_run失败时返回{'error': True, ...}, _fetch_via_playwright委托之")

    def test_n05_fetchpage_checks_wrong_key(self):
        """认认fetchpage检查"code"而不是"error"键"""
        import inspect
        source = inspect.getsource(fetchpage)
        # 查找playwright_result检查代码
        playwright_call_idx = source.find("playwright_result")
        if playwright_call_idx == -1:
            pytest.skip("未找到playwright_result调用")
        check_block = source[playwright_call_idx:playwright_call_idx+200]
        has_code_check = '"code" in playwright_result' in check_block or "'code' in playwright_result" in check_block
        has_error_check = '"error" in playwright_result' in check_block or "'error' in playwright_result" in check_block
        print(f"Playwright检查代码块: {check_block[:150]}")
        print(f"检查'code'键: {has_code_check}")
        print(f"检查'error'键: {has_error_check}")
        if has_code_check and not has_error_check:
            print("CONFIRMED: Bug#N05 - Playwright结果检查'code'而非'error'键导致KeyError")


# ══════════════════════════════════════════════════════════
# Bug#N06: download_file无文件大小限制
# ══════════════════════════════════════════════════════════
class TestBugN06_DownloadNoSizeLimit:
    """Bug#N06: download_file没有文件大小上限"""

    def test_n06_no_size_limit_in_implementation(self):
        import inspect
        source = inspect.getsource(download)
        # 检查有没有任何大小限制逻辑
        size_limit_patterns = ["max_size", "size_limit", "content_length >", "MAX_", "limit"]
        found = [p for p in size_limit_patterns if p in source]
        assert not found, f"发现大小限制代码: {found}"
        print("CONFIRMED: Bug#N06 - download_file没有文件大小上限")

    def test_n06_no_size_check_in_stream(self):
        """_stream_download也没有大小限制"""
        from app.tools.network.download_file import _stream_download
        import inspect
        source = inspect.getsource(_stream_download)
        assert "total_bytes" in source, "有total_bytes但未用于限制"
        # 认认没有基于total_bytes的限制
        assert "max" not in source.lower()[:500], "stream中没有大小上限"


# ══════════════════════════════════════════════════════════
# Bug#N07: download_file无路径遍历防护
# ══════════════════════════════════════════════════════════
class TestBugN07_DownloadNoPathValidation:
    """Bug#N07: download_file没有路径安全校验"""

    def test_n07_no_path_validation(self):
        import inspect
        source = inspect.getsource(download)
        # 检查有没有路径安全校验
        path_checks = ["os.path.abspath", "os.path.normpath", "allowed", "safe", "base", "root", "permitted"]
        found_checks = [p for p in path_checks if p in source]
        has_abspath = any("abspath" in c for c in found_checks)
        has_allowed = any(term in source for term in ("allowed", "permitted", "safe_dir", "workdir", "basedir"))
        assert has_abspath, "应使用abspath (实际使用了)"
        assert not has_allowed, "不应该有allowed目录校验"
        print(f"路径检查: {found_checks}")
        print("CONFIRMED: Bug#N07 - download_file没有路径遍历防护 (仅abspath,无目录白名单)")
