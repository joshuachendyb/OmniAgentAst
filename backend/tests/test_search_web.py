"""
search_web 双引擎fallback测试 - 验证2026-05-07修复
Author: 小沈 - 2026-05-09
"""
import pytest
from unittest.mock import patch, AsyncMock


class TestSearchWebFallback:
    @pytest.mark.asyncio
    async def test_duckduckgo_success_returns_ddg(self):
        from app.services.tools.network import network_tools
        mock_results = [{"title": "Test Result", "url": "http://example.com", "snippet": "Test"}]
        with patch("app.services.tools.network.network_tools._search_duckduckgo", new_callable=AsyncMock, return_value=mock_results):
            result = await network_tools.search_web(query="test query")
        assert result["code"] == "SUCCESS"
        assert result["data"]["engine"] == "DuckDuckGo"

    @pytest.mark.asyncio
    async def test_duckduckgo_fails_falls_back_to_bing(self):
        from app.services.tools.network import network_tools
        mock_bing_results = [{"title": "Bing Result", "url": "http://bing.com", "snippet": "Bing Test"}]
        with patch("app.services.tools.network.network_tools._search_duckduckgo", new_callable=AsyncMock, return_value=None):
            with patch("app.services.tools.network.network_tools._search_bing", new_callable=AsyncMock, return_value=mock_bing_results):
                result = await network_tools.search_web(query="test query")
        assert result["code"] == "SUCCESS"
        assert result["data"]["engine"] == "Bing"

    @pytest.mark.asyncio
    async def test_both_engines_empty(self):
        from app.services.tools.network import network_tools
        with patch("app.services.tools.network.network_tools._search_duckduckgo", new_callable=AsyncMock, return_value=[]):
            with patch("app.services.tools.network.network_tools._search_bing", new_callable=AsyncMock, return_value=[]):
                result = await network_tools.search_web(query="test query")
        assert result["code"] == "SUCCESS"
        assert result["data"]["total"] == 0

    @pytest.mark.asyncio
    async def test_short_query(self):
        from app.services.tools.network import network_tools
        result = await network_tools.search_web(query="a")
        assert result["code"] == "ERR_SEARCH_QUERY_TOO_SHORT"


class TestSearchWebParameters:
    @pytest.mark.asyncio
    async def test_default_num_results(self):
        from app.services.tools.network import network_tools
        mock_results = [{"title": f"Result {i}", "url": f"http://example{i}.com", "snippet": f"Test {i}"} for i in range(15)]
        with patch("app.services.tools.network.network_tools._search_duckduckgo", new_callable=AsyncMock, return_value=mock_results):
            result = await network_tools.search_web(query="test query")
        assert result["data"]["total"] == 10

    @pytest.mark.asyncio
    async def test_custom_num_results(self):
        from app.services.tools.network import network_tools
        mock_results = [{"title": f"Result {i}", "url": f"http://example{i}.com", "snippet": f"Test {i}"} for i in range(20)]
        with patch("app.services.tools.network.network_tools._search_duckduckgo", new_callable=AsyncMock, return_value=mock_results):
            result = await network_tools.search_web(query="test query", num_results=5)
        assert result["data"]["total"] == 5

    @pytest.mark.asyncio
    async def test_domain_filter(self):
        from app.services.tools.network import network_tools
        mock_results = [
            {"title": "Example", "url": "http://example.com", "snippet": "Test"},
            {"title": "Other", "url": "http://other.com", "snippet": "Test"},
        ]
        with patch("app.services.tools.network.network_tools._search_duckduckgo", new_callable=AsyncMock, return_value=mock_results):
            result = await network_tools.search_web(query="test", allowed_domains=["example.com"])
        assert len(result["data"]["results"]) == 1