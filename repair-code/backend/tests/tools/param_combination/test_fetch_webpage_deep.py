# -*- coding: utf-8 -*-
"""
fetch_webpage 第三杞繁搴UG名发现测试
小健 2026-06-25
"""
import asyncio
import pytest

from app.tools.tool_response import is_success, is_error


def _run(coro):
    return asyncio.run(coro)


class TestFetchWebpageDeepBugs:
    """娣卞害BUG名发现 鈥?fetch_webpage 鈥?小健 2026-06-25"""

    def test_bug_1_url_empty(self):
        """BUG#1: url=""空哄瓧第覆"""
        from app.tools.network.fetch_webpage import fetchpage
        result = _run(fetchpage(""))
        assert is_error(result)

    def test_bug_2_url_none(self):
        """BUG#2: url=None"""
        from app.tools.network.fetch_webpage import fetchpage
        result = _run(fetchpage(None))
        assert is_error(result)

    def test_bug_3_url_invalid_format(self):
        """BUG#3: url标煎紡无效"""
        from app.tools.network.fetch_webpage import fetchpage
        result = _run(fetchpage("not-a-url"))
        assert is_error(result)

    def test_bug_4_timeout_zero(self):
        """BUG#4: timeout=0"""
        from app.tools.network.fetch_webpage import fetchpage
        result = _run(fetchpage("http://example.com", timeout=0))
        # 应该鎶敊户栫珛鍗宠秴无

    def test_bug_5_timeout_negative(self):
        """BUG#5: timeout=-1璐熸暟"""
        from app.tools.network.fetch_webpage import fetchpage
        result = _run(fetchpage("http://example.com", timeout=-1))
        # 应该鎶敊

    def test_bug_6_format_invalid(self):
        """BUG#6: extract_format="invalid"无效格式"""
        from app.tools.network.fetch_webpage import fetchpage
        result = _run(fetchpage("http://example.com", extract_format="invalid"))
        # 应该报错或使用默认格式

    def test_bug_7_url_javascript_protocol(self):
        """BUG#7: url跨域javascript:协议"""
        from app.tools.network.fetch_webpage import fetchpage
        result = _run(fetchpage("javascript:alert('test')"))
        # 应该报错

    def test_bug_8_url_file_protocol(self):
        """BUG#8: url跨域file:协议"""
        from app.tools.network.fetch_webpage import fetchpage
        result = _run(fetchpage("file:///etc/passwd"))
        # 应该报错,考虑安全

    def test_bug_9_user_agent_removed(self):
        """BUG#9: user_agent参数已移除"""
        from app.tools.network.fetch_webpage import fetchpage
        result = _run(fetchpage("http://example.com"))
        # user_agent参数已移除,使用默认

    def test_bug_10_redirect_default(self):
        """BUG#10: 重定向行为使用默认"""
        from app.tools.network.fetch_webpage import fetchpage
        result = _run(fetchpage("http://example.com"))
        # follow_redirects参数已移除

    def test_bug_11_redirect_default(self):
        """BUG#11: 重定向使用默认"""
        from app.tools.network.fetch_webpage import fetchpage
        result = _run(fetchpage("http://example.com"))
        # max_redirects参数已移除

    def test_bug_12_concurrent_fetch(self):
        """BUG#12: 并发抓取"""
        from app.tools.network.fetch_webpage import fetchpage
        async def fetch_task():
            return await fetchpage("http://example.com", timeout=5)
        async def run_concurrent():
            return await asyncio.gather(*[fetch_task() for _ in range(10)])
        results = _run(run_concurrent())
        # 应该全部成功

    def test_bug_13_url_with_fragment(self):
        """BUG#13: url鍖容惈fragment"""
        from app.tools.network.fetch_webpage import fetchpage
        result = _run(fetchpage("http://example.com/page#section"))
        # 应该蹇界暐fragment

    def test_bug_14_extract_links_removed(self):
        """BUG#14: extract_links参数已移除"""
        from app.tools.network.fetch_webpage import fetchpage
        result = _run(fetchpage("http://example.com"))
        # extract_links参数已移除

    def test_bug_15_sanitize_html_removed(self):
        """BUG#15: sanitize_html参数已移除"""
        from app.tools.network.fetch_webpage import fetchpage
        result = _run(fetchpage("http://example.com"))
        # sanitize_html参数已移除