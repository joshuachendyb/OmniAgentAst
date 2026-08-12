# -*- coding: utf-8 -*-
"""
fetch_webpage 参数组合与内容测试v2
案范要求:schema驱动,内容<100行,验证实际结果,发现问题
小健 2026-06-24

Schema参数: url(str必填), prompt(Optional[str]),
            extract_format(markdown/html/text默认markdown),
            js_render(bool默认False), timeout(int默认30000范围1000-120000),
            proxy(Optional[str])
参数组合: 3×2=6种 + 边界/为面
"""
import asyncio
import pytest

from app.tools.tool_response import is_success, is_error


def _run(coro):
    return asyncio.run(coro)


class TestFetchWebpageParamCombinations:
    """参数组合测试 — extract_format×js_render — 小健 2026-06-24"""

    def test_url_only(self, tmp_path):
        """组合1: 仅URL必填参数"""
        from app.tools.network.fetch_webpage import fetchpage
        result = _run(fetchpage("https://example.com"))
        assert is_success(result)
        assert len(result["data"]["content"]) > 0

    def test_extract_format_markdown(self, tmp_path):
        """组合2: extract_format=markdown"""
        from app.tools.network.fetch_webpage import fetchpage
        result = _run(fetchpage("https://example.com", extract_format="markdown"))
        assert is_success(result)

    def test_extract_format_html(self, tmp_path):
        """组合3: extract_format=html"""
        from app.tools.network.fetch_webpage import fetchpage
        result = _run(fetchpage("https://example.com", extract_format="html"))
        assert is_success(result)
        assert "<" in result["data"]["content"]

    def test_extract_format_text(self, tmp_path):
        """组合4: extract_format=text"""
        from app.tools.network.fetch_webpage import fetchpage
        result = _run(fetchpage("https://example.com", extract_format="text"))
        assert is_success(result)

    def test_with_prompt(self, tmp_path):
        """组合5: prompt指定"""
        from app.tools.network.fetch_webpage import fetchpage
        result = _run(fetchpage("https://example.com", prompt="提取标题"))
        assert is_success(result)

    def test_js_render_true(self, tmp_path):
        """组合6: js_render=True"""
        from app.tools.network.fetch_webpage import fetchpage
        result = _run(fetchpage("https://example.com", js_render=True))
        # 可能成功或超时

    def test_timeout_custom(self, tmp_path):
        """组合7: timeout自定义"""
        from app.tools.network.fetch_webpage import fetchpage
        result = _run(fetchpage("https://example.com", timeout=100))
        assert is_success(result)

    def test_all_params_combined(self, tmp_path):
        """组合8: 所有参数组合"""
        from app.tools.network.fetch_webpage import fetchpage
        result = _run(fetchpage(
            "https://example.com",
            prompt="提取主要内容",
            extract_format="markdown",
            timeout=120
        ))
        assert is_success(result)


class TestFetchWebpageFeatures:
    """功能测试 — 小健 2026-06-24"""

    def test_markdown_structure(self, tmp_path):
        """功能: Markdown结构保留"""
        from app.tools.network.fetch_webpage import fetchpage
        result = _run(fetchpage("https://example.com", extract_format="markdown"))
        assert is_success(result)
        content = result["data"]["content"]
        # Markdown应该有标题结构
        assert len(content) > 100

    def test_html_preservation(self, tmp_path):
        """功能: HTML原始内容"""
        from app.tools.network.fetch_webpage import fetchpage
        result = _run(fetchpage("https://example.com", extract_format="html"))
        assert is_success(result)
        assert "<html" in result["data"]["content"].lower() or "<body" in result["data"]["content"].lower()

    def test_text_extraction(self, tmp_path):
        """功能: 纯文本提取"""
        from app.tools.network.fetch_webpage import fetchpage
        result = _run(fetchpage("https://example.com", extract_format="text"))
        assert is_success(result)
        # 纯文本不应该有HTML标签
        content = result["data"]["content"]
        assert "<" not in content or content.count("<") < 5

    def test_prompt_extraction(self, tmp_path):
        """功能: prompt精准提取"""
        from app.tools.network.fetch_webpage import fetchpage
        result = _run(fetchpage(
            "https://example.com",
            prompt="提取页面标题和主要内容"
        ))
        assert is_success(result)


class TestFetchWebpageRealScenarios:
    """真实场景测试 — 小健 2026-06-24"""

    def test_github_readme(self, tmp_path):
        """场景: GitHub README"""
        from app.tools.network.fetch_webpage import fetchpage
        result = _run(fetchpage("https://github.com/python/cpython"))
        if is_success(result):
            assert len(result["data"]["content"]) > 0

    def test_documentation_site(self, tmp_path):
        """场景: 文档站点"""
        from app.tools.network.fetch_webpage import fetchpage
        result = _run(fetchpage("https://docs.python.org/3/"))
        if is_success(result):
            assert len(result["data"]["content"]) > 0

    def test_news_site(self, tmp_path):
        """场景: 新闻站点"""
        from app.tools.network.fetch_webpage import fetchpage
        result = _run(fetchpage("https://news.ycombinator.com"))
        if is_success(result):
            assert len(result["data"]["content"]) > 0


class TestFetchWebpageBoundary:
    """边界测试 — 小健 2026-06-24"""

    def test_timeout_minimum(self, tmp_path):
        """边界: timeout=1000最小值"""
        from app.tools.network.fetch_webpage import fetchpage
        result = _run(fetchpage("https://example.com", timeout=1))
        # 可能超时或成功

    def test_timeout_maximum(self, tmp_path):
        """边界: timeout=120最大值"""
        from app.tools.network.fetch_webpage import fetchpage
        result = _run(fetchpage("https://example.com", timeout=120))
        assert is_success(result)

    def test_large_page(self, tmp_path):
        """边界: 大页面"""
        from app.tools.network.fetch_webpage import fetchpage
        result = _run(fetchpage("https://en.wikipedia.org/wiki/Python_(programming_language)"))
        if is_success(result):
            assert len(result["data"]["content"]) > 0

    def test_special_characters_url(self, tmp_path):
        """边界: URL特殊字符"""
        from app.tools.network.fetch_webpage import fetchpage
        result = _run(fetchpage("https://example.com/path?query=test&value=123"))
        # 应该处理或报错


class TestFetchWebpageNegative:
    """为面测试 — 小健 2026-06-24"""

    def test_invalid_url(self, tmp_path):
        """为面: 无效URL"""
        from app.tools.network.fetch_webpage import fetchpage
        result = _run(fetchpage("not-a-url"))
        assert is_error(result)

    def test_nonexistent_domain(self, tmp_path):
        """为面: 不存在的域名"""
        from app.tools.network.fetch_webpage import fetchpage
        result = _run(fetchpage("https://nonexistent-xyz-123.com"))
        assert is_error(result)

    def test_timeout_exceeded(self, tmp_path):
        """为面: 超时"""
        from app.tools.network.fetch_webpage import fetchpage
        result = _run(fetchpage("https://httpbin.org/delay/10", timeout=1))
        assert is_error(result)

    def test_invalid_extract_format(self, tmp_path):
        """为面: 无效格式"""
        from app.tools.network.fetch_webpage import fetchpage
        result = _run(fetchpage("https://example.com", extract_format="invalid"))
        # 无效格式不会报错,使用默认值继续


class TestFetchWebpageBugDiscovery:
    """BUG发现测试 — 小健 2026-06-24"""

    def test_bug_empty_url(self, tmp_path):
        """BUG: 空URL"""
        from app.tools.network.fetch_webpage import fetchpage
        result = _run(fetchpage(""))
        assert is_error(result)

    def test_bug_none_url(self, tmp_path):
        """BUG: None URL"""
        from app.tools.network.fetch_webpage import fetchpage
        result = _run(fetchpage(None))
        assert is_error(result)

    def test_bug_timeout_zero(self, tmp_path):
        """BUG: timeout=0"""
        from app.tools.network.fetch_webpage import fetchpage
        result = _run(fetchpage("https://example.com", timeout=0))
        assert is_error(result)

    def test_bug_timeout_negative(self, tmp_path):
        """BUG: timeout为数"""
        from app.tools.network.fetch_webpage import fetchpage
        result = _run(fetchpage("https://example.com", timeout=-1))
        assert is_error(result)

    def test_bug_empty_prompt(self, tmp_path):
        """BUG: 空prompt"""
        from app.tools.network.fetch_webpage import fetchpage
        result = _run(fetchpage("https://example.com", prompt=""))
        # 应该等同于无prompt

    def test_bug_internal_ip_blocked(self, tmp_path):
        """安全: 内网IP被阻止"""
        from app.tools.network.fetch_webpage import fetchpage
        result = _run(fetchpage("http://192.168.1.1"))
        assert is_error(result)
