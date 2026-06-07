# -*- coding: utf-8 -*-
"""
测试新增的网络工具：fetch_webpage 和 search_web

Author: 小沈 - 2026-05-02
"""

import pytest
import sys
sys.path.insert(0, '.')

import asyncio
from app.services.tools.network.network_tools import fetch_webpage, search_web


class TestFetchWebpage:
    """测试 fetch_webpage 工具"""
    
    @pytest.mark.asyncio
    async def test_fetch_webpage_invalid_url(self):
        """测试无效URL"""
        result = await fetch_webpage("invalid-url")
        assert result["code"] == "ERR_INVALID_URL"
    
    @pytest.mark.asyncio
    async def test_fetch_webpage_example_com(self):
        """测试获取example.com"""
        result = await fetch_webpage("https://example.com", extract_format="text", timeout=10)
        assert result["code"] == "SUCCESS"
        assert "content" in result["data"]
        assert result["data"]["format"] == "text"
    
    @pytest.mark.asyncio
    async def test_fetch_webpage_markdown_format(self):
        """测试markdown格式提取"""
        result = await fetch_webpage("https://example.com", extract_format="markdown", timeout=10)
        assert result["code"] == "SUCCESS"
        assert result["data"]["format"] == "markdown"
    
    @pytest.mark.asyncio
    async def test_fetch_webpage_with_prompt(self):
        """测试带提取指令"""
        result = await fetch_webpage(
            "https://example.com",
            prompt="提取页面标题",
            extract_format="text",
            timeout=10
        )
        assert result["code"] == "SUCCESS"
        assert "prompt" in result["data"]


class TestSearchWeb:
    """测试 search_web 工具"""
    
    @pytest.mark.asyncio
    async def test_search_query_too_short(self):
        """测试查询过短"""
        result = await search_web("a")
        assert result["code"] == "ERR_PARAM_INVALID"
    
    @pytest.mark.asyncio
    async def test_search_web_python(self):
        """测试搜索Python"""
        result = await search_web("Python programming", num_results=5)
        assert result["code"] == "SUCCESS"
        assert "results" in result["data"]
        assert result["data"]["total"] >= 0
    
    @pytest.mark.asyncio
    async def test_search_web_with_domain_filter(self):
        """测试域名过滤"""
        result = await search_web(
            "React",
            allowed_domains=["github.com"],
            num_results=3
        )
        assert result["code"] == "SUCCESS"
        # DuckDuckGo可能返回空结果
        assert "results" in result["data"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
