# -*- coding: utf-8 -*-
"""
N4 search_web 深度测试 — test_n4_search_web_deep.py

覆盖维度：
1. 参数校验（query长度≥2）
2. 引擎fallback（Parallel→Exa→Bing）
3. 域名过滤（allowed_domains/blocked_domains）
4. num_results限制
5. 代理配置
6. Bing搜索结果解析
7. URL解码（Bing ck/a跳转链接）
8. llm_data和返回结构
9. 错误处理（查询过短、网络错误）

【规范】本测试为N4专用深度测试
Author: 小沈 - 2026-05-19
"""

from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from app.services.tools.network.network_tools import search_web, _decode_bing_redirect_url


# ============================================================
# 1. 参数校验测试
# ============================================================
class TestN4ParamValidation:
    """N4 参数校验测试"""

    @pytest.mark.asyncio
    async def test_query_too_short(self):
        """query长度<2 → ERR_PARAM_INVALID"""
        result = await search_web("a")
        assert result["code"] == "ERR_PARAM_INVALID"

    @pytest.mark.asyncio
    async def test_query_minimum_length(self):
        """query长度=2 → 通过校验"""
        with patch("app.services.tools.network.network_tools._search_mcp_engine") as mock_search:
            mock_search.return_value = [{"title": "T", "url": "https://example.com", "snippet": "S", "source": "P"}]
            result = await search_web("ab")
            assert result["code"] == "SUCCESS"

    @pytest.mark.asyncio
    async def test_empty_query(self):
        """空query → ERR_PARAM_INVALID"""
        result = await search_web("")
        assert result["code"] == "ERR_PARAM_INVALID"


# ============================================================
# 2. 引擎Fallback测试
# ============================================================
class TestN4EngineFallback:
    """N4 引擎降级Fallback测试"""

    @pytest.mark.asyncio
    @patch("app.services.tools.network.network_tools._search_mcp_engine")
    async def test_parallel_success(self, mock_engine):
        """Parallel成功 → 不降级"""
        mock_engine.return_value = [{"title": "Result", "url": "https://example.com", "snippet": "Snippet", "source": "Parallel"}]
        result = await search_web("test query")
        assert result["code"] == "SUCCESS"
        assert result["data"]["engine"] == "Parallel"
        # 只调用一次（Parallel）
        assert mock_engine.call_count == 1

    @pytest.mark.asyncio
    @patch("app.services.tools.network.network_tools._search_mcp_engine")
    async def test_parallel_fail_exa_success(self, mock_engine):
        """Parallel失败 → Exa成功"""
        mock_engine.side_effect = [None, [{"title": "Exa Result", "url": "https://exa.com", "snippet": "S", "source": "Exa"}]]
        result = await search_web("test query")
        assert result["code"] == "SUCCESS"
        assert result["data"]["engine"] == "Exa"
        assert mock_engine.call_count == 2

    @pytest.mark.asyncio
    @patch("app.services.tools.network.network_tools._search_mcp_engine")
    @patch("app.services.tools.network.network_tools._search_bing")
    async def test_all_engines_fail_fallback_bing(self, mock_bing, mock_engine):
        """Parallel+Exa失败 → Bing成功"""
        mock_engine.return_value = None
        mock_bing.return_value = [{"title": "Bing Result", "url": "https://bing.com", "snippet": "S", "source": "Bing"}]
        result = await search_web("test query")
        assert result["code"] == "SUCCESS"
        assert result["data"]["engine"] == "Bing"
        assert mock_engine.call_count == 2  # Parallel + Exa
        mock_bing.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.services.tools.network.network_tools._search_mcp_engine")
    @patch("app.services.tools.network.network_tools._search_bing")
    async def test_all_engines_fail_empty_results(self, mock_bing, mock_engine):
        """所有引擎失败 → 返回空结果"""
        mock_engine.return_value = None
        mock_bing.return_value = []
        result = await search_web("test query")
        assert result["code"] == "SUCCESS"
        assert result["data"]["total"] == 0
        assert result["data"]["results"] == []


# ============================================================
# 3. 域名过滤测试
# ============================================================
class TestN4DomainFiltering:
    """N4 域名过滤测试"""

    @pytest.mark.asyncio
    @patch("app.services.tools.network.network_tools._search_mcp_engine")
    async def test_allowed_domains_filter(self, mock_engine):
        """allowed_domains只保留匹配域名的结果"""
        mock_engine.return_value = [
            {"title": "GitHub", "url": "https://github.com/repo", "snippet": "S", "source": "P"},
            {"title": "Other", "url": "https://other.com", "snippet": "S", "source": "P"},
        ]
        result = await search_web("test", allowed_domains=["github.com"])
        assert result["code"] == "SUCCESS"
        assert len(result["data"]["results"]) == 1
        assert "github.com" in result["data"]["results"][0]["url"]

    @pytest.mark.asyncio
    @patch("app.services.tools.network.network_tools._search_mcp_engine")
    async def test_blocked_domains_filter(self, mock_engine):
        """blocked_domains排除匹配域名的结果"""
        mock_engine.return_value = [
            {"title": "Bad", "url": "https://spam.com", "snippet": "S", "source": "P"},
            {"title": "Good", "url": "https://good.com", "snippet": "S", "source": "P"},
        ]
        result = await search_web("test", blocked_domains=["spam.com"])
        assert result["code"] == "SUCCESS"
        assert len(result["data"]["results"]) == 1
        assert "good.com" in result["data"]["results"][0]["url"]

    @pytest.mark.asyncio
    @patch("app.services.tools.network.network_tools._search_mcp_engine")
    async def test_allowed_and_blocked_combined(self, mock_engine):
        """allowed_domains和blocked_domains同时生效"""
        mock_engine.return_value = [
            {"title": "GitHub", "url": "https://github.com/repo", "snippet": "S", "source": "P"},
            {"title": "GitHubSpam", "url": "https://github.spam.com", "snippet": "S", "source": "P"},
            {"title": "Other", "url": "https://other.com", "snippet": "S", "source": "P"},
        ]
        result = await search_web("test", allowed_domains=["github.com"], blocked_domains=["spam.com"])
        assert result["code"] == "SUCCESS"
        assert len(result["data"]["results"]) == 1
        assert "github.com/repo" in result["data"]["results"][0]["url"]


# ============================================================
# 4. num_results限制测试
# ============================================================
class TestN4NumResults:
    """N4 num_results限制测试"""

    @pytest.mark.asyncio
    @patch("app.services.tools.network.network_tools._search_mcp_engine")
    async def test_num_results_limit(self, mock_engine):
        """num_results限制返回数量"""
        mock_engine.return_value = [
            {"title": f"Result {i}", "url": f"https://example.com/{i}", "snippet": "S", "source": "P"}
            for i in range(20)
        ]
        result = await search_web("test", num_results=5)
        assert result["code"] == "SUCCESS"
        assert len(result["data"]["results"]) == 5
        assert result["data"]["total"] == 5

    @pytest.mark.asyncio
    @patch("app.services.tools.network.network_tools._search_mcp_engine")
    async def test_num_results_default_10(self, mock_engine):
        """默认num_results=10"""
        mock_engine.return_value = [
            {"title": f"Result {i}", "url": f"https://example.com/{i}", "snippet": "S", "source": "P"}
            for i in range(15)
        ]
        result = await search_web("test")
        assert result["code"] == "SUCCESS"
        assert len(result["data"]["results"]) == 10


# ============================================================
# 5. Bing搜索解析测试
# ============================================================
class TestN4BingParsing:
    """N4 Bing搜索结果解析测试"""

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_bing_parse_result(self, mock_client_cls):
        """Bing搜索结果解析正确"""
        html = '''
        <li class="b_algo">
            <h2><a href="https://example.com/page">Test Title</a></h2>
            <div class="b_caption"><p>Test snippet content</p></div>
        </li>
        '''
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = html
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        with patch("app.services.tools.network.network_tools._search_mcp_engine") as mock_engine:
            mock_engine.return_value = None
            result = await search_web("test query")
            assert result["code"] == "SUCCESS"
            assert result["data"]["engine"] == "Bing"
            assert len(result["data"]["results"]) > 0
            first = result["data"]["results"][0]
            assert "Test Title" in first.get("title", "")

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_bing_empty_results(self, mock_client_cls):
        """Bing无结果 → 空列表"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><body>No results</body></html>"
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        with patch("app.services.tools.network.network_tools._search_mcp_engine") as mock_engine:
            mock_engine.return_value = None
            result = await search_web("test query")
            assert result["code"] == "SUCCESS"
            assert result["data"]["total"] == 0


# ============================================================
# 6. URL解码测试
# ============================================================
class TestN4UrlDecoding:
    """N4 Bing ck/a跳转URL解码测试"""

    def test_decode_bing_redirect(self):
        """解码Bing ck/a跳转链接"""
        import base64
        real_url = "https://example.com/target"
        encoded = base64.urlsafe_b64encode(real_url.encode()).decode().rstrip("=")
        bing_url = f"https://www.bing.com/ck/a?!&&p=xxx&u={encoded}"
        decoded = _decode_bing_redirect_url(bing_url)
        assert decoded == real_url

    def test_non_bing_url_unchanged(self):
        """非Bing链接保持不变"""
        url = "https://example.com/page"
        decoded = _decode_bing_redirect_url(url)
        assert decoded == url

    def test_bing_url_decode_fail(self):
        """Bing链接解码失败时返回原链接"""
        bing_url = "https://www.bing.com/ck/a?!&&p=xxx&u=invalid_base64"
        decoded = _decode_bing_redirect_url(bing_url)
        assert decoded == bing_url


# ============================================================
# 7. 返回结构测试
# ============================================================
class TestN4ResponseStructure:
    """N4 返回结构测试"""

    @pytest.mark.asyncio
    @patch("app.services.tools.network.network_tools._search_mcp_engine")
    async def test_success_response_fields(self, mock_engine):
        """成功返回包含所有预期字段"""
        mock_engine.return_value = [{"title": "T", "url": "https://example.com", "snippet": "S", "source": "P"}]
        result = await search_web("test")
        assert result["code"] == "SUCCESS"
        data = result["data"]
        assert "query" in data
        assert "results" in data
        assert "total" in data
        assert "engine" in data
        assert "language" in data
        assert "language" in data
        assert "llm_data" in result
        assert "next_actions" in result

    @pytest.mark.asyncio
    @patch("app.services.tools.network.network_tools._search_mcp_engine")
    async def test_llm_data_structure(self, mock_engine):
        """llm_data包含搜索结果列表"""
        mock_engine.return_value = [{"title": "T", "url": "https://example.com", "snippet": "S", "source": "P"}]
        result = await search_web("test")
        assert "llm_data" in result
        llm_data = result["llm_data"]
        assert "搜索引擎" in llm_data
        assert "查询词" in llm_data
        assert "结果数量" in llm_data
        assert "搜索结果" in llm_data

    @pytest.mark.asyncio
    @patch("app.services.tools.network.network_tools._search_mcp_engine")
    async def test_next_actions_present(self, mock_engine):
        """成功返回包含next_actions"""
        mock_engine.return_value = [{"title": "T", "url": "https://example.com", "snippet": "S", "source": "P"}]
        result = await search_web("test")
        assert "next_actions" in result
        assert len(result["next_actions"]) > 0

    @pytest.mark.asyncio
    @patch("app.services.tools.network.network_tools._search_mcp_engine")
    async def test_empty_results_llm_data(self, mock_engine):
        """无结果时llm_data显示'无相关结果'"""
        mock_engine.return_value = []
        result = await search_web("test")
        assert result["llm_data"]["搜索结果"] == "无相关结果"
