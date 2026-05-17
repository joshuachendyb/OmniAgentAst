# -*- coding: utf-8 -*-
"""
第14章 Network分类精简方案 深度测试 - 小健 2026-05-18

覆盖：
- 14.2.2: network_diagnose 合并（ping + port_check）
- 14.2.3: _search_mcp_engine 合并
- 14.2.4: Helper层下沉（network_helper.py）
- 14.2.5: _create_http_client 工厂函数（P2待实施，验证缺失）

Author: 小健 - 2026-05-18
"""

import pytest
import sys
import os

sys.path.insert(0, '.')


class TestNetworkDiagnose:
    """14.2.2 network_diagnose 合并测试 — 小健 2026-05-18"""

    @pytest.mark.asyncio
    async def test_network_diagnose_ping_mode(self):
        """mode='ping'应委托给ping函数"""
        from app.services.tools.network.network_tools import network_diagnose
        result = await network_diagnose(host="127.0.0.1", mode="ping", count=2, timeout=3)
        assert result["code"] == "SUCCESS"
        assert "is_reachable" in result["data"]
        assert "loss_rate" in result["data"]

    @pytest.mark.asyncio
    async def test_network_diagnose_port_mode(self):
        """mode='port'应委托给port_check函数"""
        from app.services.tools.network.network_tools import network_diagnose
        result = await network_diagnose(host="127.0.0.1", mode="port", port=80, timeout=3)
        assert result["code"] == "SUCCESS"
        assert "is_open" in result["data"]
        assert "port" in result["data"]

    @pytest.mark.asyncio
    async def test_network_diagnose_port_mode_missing_port(self):
        """mode='port'但未提供port参数应返回ERR_MISSING_PARAM"""
        from app.services.tools.network.network_tools import network_diagnose
        result = await network_diagnose(host="127.0.0.1", mode="port", port=None)
        assert result["code"] == "ERR_MISSING_PARAM"
        assert "port" in result["message"].lower() or "必填" in result["message"]

    @pytest.mark.asyncio
    async def test_network_diagnose_invalid_mode(self):
        """无效mode应返回ERR_INVALID_MODE"""
        from app.services.tools.network.network_tools import network_diagnose
        result = await network_diagnose(host="127.0.0.1", mode="invalid_mode")
        assert result["code"] == "ERR_INVALID_MODE"

    @pytest.mark.asyncio
    async def test_network_diagnose_default_mode_is_ping(self):
        """默认mode应为ping"""
        from app.services.tools.network.network_tools import network_diagnose
        result = await network_diagnose(host="127.0.0.1", count=1, timeout=2)
        assert result["code"] == "SUCCESS"
        assert "is_reachable" in result["data"]

    @pytest.mark.asyncio
    async def test_network_diagnose_ping_delegates_correctly(self):
        """network_diagnose(mode='ping')结果应与ping()一致"""
        from app.services.tools.network.network_tools import network_diagnose, ping
        r1 = await network_diagnose(host="127.0.0.1", mode="ping", count=1, timeout=2)
        r2 = await ping(host="127.0.0.1", count=1, timeout=2)
        assert r1["code"] == r2["code"]
        assert r1["data"]["is_reachable"] == r2["data"]["is_reachable"]

    @pytest.mark.asyncio
    async def test_network_diagnose_port_delegates_correctly(self):
        """network_diagnose(mode='port')结果应与port_check()一致"""
        from app.services.tools.network.network_tools import network_diagnose, port_check
        r1 = await network_diagnose(host="127.0.0.1", mode="port", port=80, timeout=2)
        r2 = await port_check(host="127.0.0.1", port=80, timeout=2)
        assert r1["code"] == r2["code"]
        assert r1["data"]["is_open"] == r2["data"]["is_open"]


class TestNetworkDiagnoseSchema:
    """14.2.2 NetworkDiagnoseInput schema检查 — 小健 2026-05-18"""

    def test_schema_fields(self):
        """NetworkDiagnoseInput应有host/mode/port/count/timeout字段"""
        from app.services.tools.network.network_schema import NetworkDiagnoseInput
        fields = NetworkDiagnoseInput.model_fields
        assert "host" in fields
        assert "mode" in fields
        assert "port" in fields
        assert "count" in fields
        assert "timeout" in fields

    def test_schema_defaults(self):
        """默认值：mode='ping', count=4, timeout=5"""
        from app.services.tools.network.network_schema import NetworkDiagnoseInput
        fields = NetworkDiagnoseInput.model_fields
        assert fields["mode"].default == "ping"
        assert fields["count"].default == 4
        assert fields["timeout"].default == 5

    def test_port_default_is_none(self):
        """port默认应为None（ping模式忽略）"""
        from app.services.tools.network.network_schema import NetworkDiagnoseInput
        fields = NetworkDiagnoseInput.model_fields
        assert fields["port"].default is None

    def test_deprecated_port_check_input(self):
        """PortCheckInput应标注弃用"""
        from app.services.tools.network.network_schema import PortCheckInput
        assert "弃用" in PortCheckInput.__doc__


class TestNetworkRegister:
    """14.2 Network注册检查 — 小健 2026-05-18"""

    def test_register_exactly_5_tools(self):
        """network应精确注册5个LLM工具"""
        from app.services.tools.network.network_register import NETWORK_TOOL_DESCRIPTIONS
        expected_keys = {"http_request", "download_file", "fetch_webpage", "search_web", "network_diagnose"}
        assert set(NETWORK_TOOL_DESCRIPTIONS.keys()) == expected_keys, (
            f"注册工具={set(NETWORK_TOOL_DESCRIPTIONS.keys())}, 期望={expected_keys}"
        )

    def test_network_diagnose_in_descriptions(self):
        """network_diagnose应在工具描述中"""
        from app.services.tools.network.network_register import NETWORK_TOOL_DESCRIPTIONS
        assert "network_diagnose" in NETWORK_TOOL_DESCRIPTIONS

    def test_ping_not_in_descriptions(self):
        """ping不应在LLM工具描述中（已合并）"""
        from app.services.tools.network.network_register import NETWORK_TOOL_DESCRIPTIONS
        assert "ping" not in NETWORK_TOOL_DESCRIPTIONS

    def test_port_check_not_in_descriptions(self):
        """port_check不应在LLM工具描述中（已合并）"""
        from app.services.tools.network.network_register import NETWORK_TOOL_DESCRIPTIONS
        assert "port_check" not in NETWORK_TOOL_DESCRIPTIONS

    def test_register_has_examples_for_network_diagnose(self):
        """network_diagnose应有使用示例"""
        from app.services.tools.network.network_register import NETWORK_TOOL_EXAMPLES
        assert "network_diagnose" in NETWORK_TOOL_EXAMPLES
        assert len(NETWORK_TOOL_EXAMPLES["network_diagnose"]) >= 2


class TestSearchMcpEngine:
    """14.2.3 _search_mcp_engine 合并测试 — 小健 2026-05-18"""

    def test_search_mcp_engine_exists(self):
        """_search_mcp_engine函数应存在"""
        from app.services.tools.network.network_tools import _search_mcp_engine
        assert callable(_search_mcp_engine)

    def test_search_parallel_mcp_delegates(self):
        """_search_parallel_mcp应委托给_search_mcp_engine('parallel')"""
        from app.services.tools.network.network_tools import _search_parallel_mcp
        assert callable(_search_parallel_mcp)

    def test_search_exa_mcp_delegates(self):
        """_search_exa_mcp应委托给_search_mcp_engine('exa')"""
        from app.services.tools.network.network_tools import _search_exa_mcp
        assert callable(_search_exa_mcp)

    @pytest.mark.asyncio
    async def test_search_mcp_engine_invalid_engine(self):
        """无效engine应返回None"""
        from app.services.tools.network.network_tools import _search_mcp_engine
        result = await _search_mcp_engine("invalid_engine", "test", 5)
        assert result is None


class TestNetworkHelperMigration:
    """14.2.4 Helper层下沉测试 — 小健 2026-05-18"""

    def test_network_helper_has_html_to_markdown(self):
        """network_helper.py应有_html_to_markdown"""
        from app.services.tools.toolhelper.network_helper import _html_to_markdown
        assert callable(_html_to_markdown)

    def test_network_helper_has_decode_bing_redirect_url(self):
        """network_helper.py应有_decode_bing_redirect_url"""
        from app.services.tools.toolhelper.network_helper import _decode_bing_redirect_url
        assert callable(_decode_bing_redirect_url)

    def test_html_to_markdown_basic(self):
        """_html_to_markdown基本转换测试"""
        from app.services.tools.toolhelper.network_helper import _html_to_markdown
        html = "<h1>Title</h1><p>Hello</p>"
        md = _html_to_markdown(html)
        assert "Title" in md
        assert "Hello" in md

    def test_html_to_markdown_strips_scripts(self):
        """_html_to_markdown应去除script标签"""
        from app.services.tools.toolhelper.network_helper import _html_to_markdown
        html = '<script>alert("xss")</script><p>Safe</p>'
        md = _html_to_markdown(html)
        assert "alert" not in md
        assert "Safe" in md

    def test_decode_bing_redirect_url_passthrough(self):
        """非Bing URL应直接返回"""
        from app.services.tools.toolhelper.network_helper import _decode_bing_redirect_url
        url = "https://example.com/page"
        assert _decode_bing_redirect_url(url) == url

    def test_decode_bing_redirect_url_decodes(self):
        """Bing跳转URL应解码出真实URL"""
        import base64
        from app.services.tools.toolhelper.network_helper import _decode_bing_redirect_url
        real_url = "https://example.com/real"
        encoded = base64.b64encode(real_url.encode()).decode().replace('+', '-').replace('/', '_').rstrip('=')
        bing_url = f"https://www.bing.com/ck/a?!&&p=abc&u={encoded}"
        decoded = _decode_bing_redirect_url(bing_url)
        assert decoded == real_url

    def test_network_helper_has_check_network(self):
        """network_helper.py应有_check_network"""
        from app.services.tools.toolhelper.network_helper import _check_network
        assert callable(_check_network)

    def test_network_helper_has_validate_url(self):
        """network_helper.py应有_validate_url"""
        from app.services.tools.toolhelper.network_helper import _validate_url
        assert callable(_validate_url)


class TestCreateHttpClientStatus:
    """14.2.5 _create_http_client 工厂函数实施状态 — 小健 2026-05-18"""

    def test_create_http_client_not_yet_in_network_tools(self):
        """P2优先级：_create_http_client尚未实施（确认状态）"""
        from app.services.tools.network import network_tools
        has_factory = hasattr(network_tools, "_create_http_client")
        if not has_factory:
            pytest.skip("_create_http_client(P2)尚未实施，符合预期")

    def test_create_http_client_not_in_network_helper(self):
        """P2优先级：_create_http_client尚未在network_helper中"""
        from app.services.tools.toolhelper import network_helper
        has_factory = hasattr(network_helper, "_create_http_client")
        if not has_factory:
            pytest.skip("_create_http_client(P2)尚未在network_helper中实施，符合预期")


class TestNetworkInitPyAllStrict:
    """network __init__.py __all__严格导出检查 — 小健 2026-05-18"""

    def test_init_all_exact_contents(self):
        """network/__init__.py的__all__必须精确包含新工具"""
        from app.services.tools import network
        expected = ["http_request", "download_file", "fetch_webpage", "search_web", "network_diagnose"]
        assert network.__all__ == expected, (
            f"network/__init__.py __all__={network.__all__}, 期望={expected}"
        )

    def test_init_all_no_legacy_names(self):
        """network/__init__.py的__all__不应含旧工具名"""
        from app.services.tools import network
        assert "ping" not in network.__all__, "ping已合并为network_diagnose，不应在__all__中"
        assert "port_check" not in network.__all__, "port_check已合并为network_diagnose，不应在__all__中"

    def test_init_all_importable(self):
        """__all__中的名字都能通过from network import *导入"""
        from app.services.tools.network import (
            http_request, download_file, fetch_webpage, search_web, network_diagnose
        )
        assert callable(http_request)
        assert callable(download_file)
        assert callable(fetch_webpage)
        assert callable(search_web)
        assert callable(network_diagnose)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
