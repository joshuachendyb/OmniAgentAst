# -*- coding: utf-8 -*-
"""tool_search参数组合测试 - 小欧 2026-07-04

测试BM25搜索工具的各种参数组合、边界条件和异常场景
"""

import pytest
from app.tools.tool_response import is_success, is_error


class TestSearchtoolNormal:
    """正常参数组合"""

    def test_single_keyword(self, temp_output_dir):
        from app.tools.fundamental.tool_search import searchtool
        result = searchtool(query="Word")
        assert is_success(result)
        data = result["data"]
        assert "matches" in data
        assert "total" in result["llm_data"]["metrics"]
        assert "matched" in result["llm_data"]["metrics"]

    def test_chinese_keyword(self, temp_output_dir):
        from app.tools.fundamental.tool_search import searchtool
        result = searchtool(query="读取")
        assert is_success(result)

    def test_english_keyword(self, temp_output_dir):
        from app.tools.fundamental.tool_search import searchtool
        result = searchtool(query="read")
        assert is_success(result)

    def test_mixed_chinese_english(self, temp_output_dir):
        from app.tools.fundamental.tool_search import searchtool
        result = searchtool(query="读取 Word")
        assert is_success(result)

    def test_single_char_chinese(self, temp_output_dir):
        from app.tools.fundamental.tool_search import searchtool
        result = searchtool(query="读")
        assert is_success(result)

    def test_single_char_english(self, temp_output_dir):
        from app.tools.fundamental.tool_search import searchtool
        result = searchtool(query="a")
        assert is_success(result)

    def test_multiple_keywords(self, temp_output_dir):
        from app.tools.fundamental.tool_search import searchtool
        result = searchtool(query="Word Excel PDF")
        assert is_success(result)

    def test_purely_numeric_query(self, temp_output_dir):
        from app.tools.fundamental.tool_search import searchtool
        result = searchtool(query="12345")
        assert is_success(result)

    def test_unicode_non_cjk(self, temp_output_dir):
        from app.tools.fundamental.tool_search import searchtool
        result = searchtool(query="日本語")
        assert is_success(result)

    def test_very_long_query(self, temp_output_dir):
        from app.tools.fundamental.tool_search import searchtool
        long_query = "read " * 200
        result = searchtool(query=long_query)
        assert is_success(result)

    def test_return_structure(self, temp_output_dir):
        from app.tools.fundamental.tool_search import searchtool
        result = searchtool(query="file")
        assert is_success(result)
        data = result["data"]
        llm = result["llm_data"]["metrics"]
        assert isinstance(data["matches"], list)
        assert isinstance(llm["matched"]["value"], int)
        assert isinstance(llm["total"]["value"], int)
        if data["matches"]:
            assert "name" in data["matches"][0]
            assert "category" in data["matches"][0]


class TestSearchtoolEdgeCases:
    """边界条件和异常场景"""

    def test_empty_query(self):
        from app.tools.fundamental.tool_search import searchtool
        result = searchtool(query="")
        assert is_error(result)
        assert "不能为空" in result["llm_data"]["status"]["detail"]

    def test_whitespace_only(self):
        from app.tools.fundamental.tool_search import searchtool
        result = searchtool(query="   ")
        assert is_error(result)
        assert "不能为空" in result["llm_data"]["status"]["detail"]

    def test_tab_and_newline(self):
        from app.tools.fundamental.tool_search import searchtool
        result = searchtool(query="file\tread\nwrite")
        assert is_success(result)

    def test_special_chars_only(self, temp_output_dir):
        from app.tools.fundamental.tool_search import searchtool
        result = searchtool(query="@#$%^&*()")
        assert is_success(result)

    def test_emoji_in_query(self, temp_output_dir):
        from app.tools.fundamental.tool_search import searchtool
        result = searchtool(query="📁 file")
        assert is_success(result)

    def test_underline_in_query(self, temp_output_dir):
        from app.tools.fundamental.tool_search import searchtool
        result = searchtool(query="read_text_file")
        assert is_success(result)


class TestSearchtoolContent:
    """内容验证"""

    def test_matches_consistency(self, temp_output_dir):
        from app.tools.fundamental.tool_search import searchtool
        result1 = searchtool(query="file")
        result2 = searchtool(query="file")
        assert result1["llm_data"]["metrics"]["total"]["value"] == result2["llm_data"]["metrics"]["total"]["value"]
        assert result1["llm_data"]["metrics"]["matched"]["value"] == result2["llm_data"]["metrics"]["matched"]["value"]

    def test_total_tools_positive(self, temp_output_dir):
        from app.tools.fundamental.tool_search import searchtool
        result = searchtool(query="file")
        assert result["llm_data"]["metrics"]["total"]["value"] >= 0
