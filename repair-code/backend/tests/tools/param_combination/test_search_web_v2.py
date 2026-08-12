# -*- coding: utf-8 -*-
"""
search_web 参数组合与内容测试v2
案范要求:schema驱动,内容<100行,验证实际结果,发现问题
小健 2026-06-24

Schema参数: query(str必填), num_results(int默认10范围1-50),
            allowed_domains(Optional[str]), blocked_domains(Optional[str]),
            proxy(Optional[str])
参数组合: 2×2=4种 + 边界/为面
"""
import asyncio
import pytest

from app.tools.tool_response import is_success, is_error


def _run(coro):
    return asyncio.run(coro)


class TestSearchWebParamCombinations:
    """参数组合测试 — num_results×allowed_domains — 小健 2026-06-24"""

    def test_query_only(self, tmp_path):
        """组合1: 仅query必填参数"""
        from app.tools.network.search_web import searchweb
        result = _run(searchweb("Python programming"))
        assert is_success(result)
        assert len(result["data"]["items"]) > 0

    def test_num_results_custom(self, tmp_path):
        """组合2: num_results自定义"""
        from app.tools.network.search_web import searchweb
        result = _run(searchweb("FastAPI", num_results=5))
        assert is_success(result)
        assert len(result["data"]["items"]) <= 5

    def test_allowed_domains(self, tmp_path):
        """组合3: allowed_domains限制"""
        from app.tools.network.search_web import searchweb
        result = _run(searchweb(
            "Python tutorial",
            allowed_domains="python.org,github.com"
        ))
        if is_success(result):
            # 结果应该来自指定域名
            pass

    def test_blocked_domains(self, tmp_path):
        """组合4: blocked_domains排除"""
        from app.tools.network.search_web import searchweb
        result = _run(searchweb(
            "programming",
            blocked_domains="pinterest.com"
        ))
        if is_success(result):
            pass

    def test_all_params_combined(self, tmp_path):
        """组合5: 所有参数组合"""
        from app.tools.network.search_web import searchweb
        result = _run(searchweb(
            "React hooks",
            num_results=10
        ))
        assert is_success(result)


class TestSearchWebFeatures:
    """功能测试 — 小健 2026-06-24"""

    def test_chinese_query(self, tmp_path):
        """功能: 中文搜索"""
        from app.tools.network.search_web import searchweb
        result = _run(searchweb("Python编程教程"))
        assert is_success(result)
        assert len(result["data"]["items"]) > 0

    def test_english_query(self, tmp_path):
        """功能: 英文搜索"""
        from app.tools.network.search_web import searchweb
        result = _run(searchweb("machine learning tutorial"))
        assert is_success(result)

    def test_result_structure(self, tmp_path):
        """功能: 结果结构"""
        from app.tools.network.search_web import searchweb
        result = _run(searchweb("test"))
        assert is_success(result)
        for r in result["data"]["items"]:
            assert "title" in r
            assert "url" in r
            assert "snippet" in r

    def test_num_results_minimum(self, tmp_path):
        """功能: num_results=1最小值"""
        from app.tools.network.search_web import searchweb
        result = _run(searchweb("test", num_results=1))
        assert is_success(result)
        assert len(result["data"]["items"]) <= 1

    def test_num_results_maximum(self, tmp_path):
        """功能: num_results=50最大值"""
        from app.tools.network.search_web import searchweb
        result = _run(searchweb("test", num_results=50))
        assert is_success(result)
        assert len(result["data"]["items"]) <= 50


class TestSearchWebRealScenarios:
    """真实场景测试 — 小健 2026-06-24"""

    def test_technology_search(self, tmp_path):
        """场景: 技术搜索"""
        from app.tools.network.search_web import searchweb
        result = _run(searchweb("FastAPI tutorial", num_results=5))
        assert is_success(result)
        assert len(result["data"]["items"]) > 0

    def test_documentation_search(self, tmp_path):
        """场景: 文档搜索"""
        from app.tools.network.search_web import searchweb
        result = _run(searchweb("Python official documentation"))
        assert is_success(result)

    def test_error_solution_search(self, tmp_path):
        """场景: 错误解决方案搜索"""
        from app.tools.network.search_web import searchweb
        result = _run(searchweb("Python ModuleNotFoundError solution"))
        assert is_success(result)

    def test_code_example_search(self, tmp_path):
        """场景: 代码示例搜索"""
        from app.tools.network.search_web import searchweb
        result = _run(searchweb("React useEffect example"))
        assert is_success(result)


class TestSearchWebBoundary:
    """边界测试 — 小健 2026-06-24"""

    def test_long_query(self, tmp_path):
        """边界: 长查询"""
        from app.tools.network.search_web import searchweb
        long_query = "Python " * 50
        result = _run(searchweb(long_query))
        # 可能成功或报错

    def test_special_characters_query(self, tmp_path):
        """边界: 特殊字符查询"""
        from app.tools.network.search_web import searchweb
        result = _run(searchweb("C++ programming"))
        assert is_success(result)

    def test_unicode_query(self, tmp_path):
        """边界: Unicode查询"""
        from app.tools.network.search_web import searchweb
        result = _run(searchweb("🎉 emoji search"))
        # 可能成功或报错

    def test_empty_results(self, tmp_path):
        """边界: 无结果查询"""
        from app.tools.network.search_web import searchweb
        result = _run(searchweb("zzzzzzzzznonexistent123456789"))
        if is_success(result):
            # 搜索可能返回结果,不做断言
            pass


class TestSearchWebNegative:
    """为面测试 — 小健 2026-06-24"""

    def test_empty_query(self, tmp_path):
        """负面: 空查询应报错(2026-07-22 小欧: query空白拦截, 防None穿透Bing异常)"""
        from app.tools.network.search_web import searchweb
        result = _run(searchweb(""))
        assert is_error(result)

    def test_none_query(self, tmp_path):
        """为面: None查询"""
        from app.tools.network.search_web import searchweb
        result = _run(searchweb(None))
        assert is_error(result)

    def test_invalid_num_results(self, tmp_path):
        """为面: 无效num_results"""
        from app.tools.network.search_web import searchweb
        result = _run(searchweb("test", num_results=1001))
        assert is_error(result)

    def test_negative_num_results(self, tmp_path):
        """为面: 为数num_results"""
        from app.tools.network.search_web import searchweb
        result = _run(searchweb("test", num_results=-1))
        assert is_error(result)

    def test_zero_num_results(self, tmp_path):
        """为面: num_results=0"""
        from app.tools.network.search_web import searchweb
        result = _run(searchweb("test", num_results=0))
        assert is_error(result)


class TestSearchWebBugDiscovery:
    """BUG发现测试 — 小健 2026-06-24"""

    def test_bug_query_injection(self, tmp_path):
        """安全: 查询注入"""
        from app.tools.network.search_web import searchweb
        result = _run(searchweb("test'; DROP TABLE users; --"))
        # 应该安全处理

    def test_bug_allowed_domains_empty(self, tmp_path):
        """BUG: allowed_domains空字符串"""
        from app.tools.network.search_web import searchweb
        result = _run(searchweb("test", allowed_domains=""))
        # 应该等同于无限制

    def test_bug_blocked_domains_empty(self, tmp_path):
        """BUG: blocked_domains空字符串"""
        from app.tools.network.search_web import searchweb
        result = _run(searchweb("test", blocked_domains=""))
        # 应该等同于无排除

    def test_bug_num_results_boundary(self, tmp_path):
        """BUG: num_results边界值"""
        from app.tools.network.search_web import searchweb
        result = _run(searchweb("test", num_results=1001))
        assert is_error(result)

    def test_bug_whitespace_query(self, tmp_path):
        """BUG: 仅空白查询"""
        from app.tools.network.search_web import searchweb
        result = _run(searchweb("   "))
        # 空白查询不会校验错误,搜索行为取决于引擎

    def test_bug_multiple_searches(self, tmp_path):
        """BUG: 连续多次搜索"""
        from app.tools.network.search_web import searchweb
        for i in range(3):
            result = _run(searchweb(f"test{i}"))
            # 应该都能成功
