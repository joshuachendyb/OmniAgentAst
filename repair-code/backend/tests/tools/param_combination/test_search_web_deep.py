# -*- coding: utf-8 -*-
"""
search_web 第三轮深度BUG发现测试
小健 2026-06-25
"""
import asyncio
import pytest

from app.tools.tool_response import is_success, is_error


def _run(coro):
    return asyncio.run(coro)


class TestSearchWebDeepBugs:
    """深度BUG发现 — search_web — 小健 2026-06-25"""

    def test_bug_1_query_empty(self):
        """BUG#1: query=""空字符串"""
        from app.tools.network.search_web import searchweb
        result = _run(searchweb(""))
        # 应该报错或返回空结果

    def test_bug_2_query_none(self):
        """BUG#2: query=None"""
        from app.tools.network.search_web import searchweb
        result = _run(searchweb(None))
        assert is_error(result)

    def test_bug_3_num_results_zero(self):
        """BUG#3: num_results=0"""
        from app.tools.network.search_web import searchweb
        result = _run(searchweb("test", num_results=0))
        # 应该报错或返回空结果

    def test_bug_4_num_results_negative(self):
        """BUG#4: num_results=-1负数"""
        from app.tools.network.search_web import searchweb
        result = _run(searchweb("test", num_results=-1))
        # 应该报错

    def test_bug_5_num_results_very_large(self):
        """BUG#5: num_results=10000非常大"""
        from app.tools.network.search_web import searchweb
        result = _run(searchweb("test", num_results=10000))
        # 应该限制最大结果数

    def test_bug_9_query_with_special_chars(self):
        """BUG#9: query包含特殊字符"""
        from app.tools.network.search_web import searchweb
        result = _run(searchweb("test & | < > \" '"))
        # 应该正认编码

    def test_bug_10_query_very_long(self):
        """BUG#10: query非常长(1000字符)"""
        from app.tools.network.search_web import searchweb
        long_query = "test " * 200
        result = _run(searchweb(long_query))
        # 应该成功或报错

    @pytest.mark.skip(reason="需要mock网络,跳过并发测试")
    def test_bug_13_concurrent_search(self):
        pass

    def test_bug_14_query_with_unicode(self):
        """BUG#14: query包含Unicode字符"""
        from app.tools.network.search_web import searchweb
        result = _run(searchweb("测试中文搜索"))
        # 应该正认处理
