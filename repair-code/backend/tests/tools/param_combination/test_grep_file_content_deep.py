# -*- coding: utf-8 -*-
"""
grep_file_content 第三轮深度BUG发现测试
小健 2026-06-25
更新 小欧 2026-06-27: 修复参数顺序错乱 + 去除不存在的关键字参数
"""
import asyncio
import pytest
from pathlib import Path

from app.tools.tool_response import is_success, is_error


def _run(coro):
    return asyncio.run(coro)


class TestGrepFileContentDeepBugs:
    """深度BUG发现 — grep_file_content — 小健 2026-06-25"""

    def test_bug_1_pattern_empty(self, tmp_path):
        """BUG#1: pattern=""空字符串"""
        from app.tools.file.grep_file_content import grep
        (tmp_path / "test.txt").write_text("test\n", encoding="utf-8")
        result = _run(grep("", str(tmp_path)))
        assert is_error(result)

    def test_bug_2_pattern_none(self, tmp_path):
        """BUG#2: pattern=None"""
        from app.tools.file.grep_file_content import grep
        result = _run(grep(None, str(tmp_path)))
        assert is_error(result)

    def test_bug_3_search_path_empty(self, tmp_path):
        """BUG#3: search_path=""空字符串"""
        from app.tools.file.grep_file_content import grep
        result = _run(grep("test", ""))
        assert is_error(result)

    def test_bug_4_invalid_regex(self, tmp_path):
        """BUG#4: 无效正则表达式"""
        from app.tools.file.grep_file_content import grep
        (tmp_path / "test.txt").write_text("test\n", encoding="utf-8")
        result = _run(grep("[invalid", str(tmp_path)))
        assert is_error(result)

    def test_bug_5_ignore_case_true(self, tmp_path):
        """BUG#5: ignore_case=True大小写不敏感"""
        from app.tools.file.grep_file_content import grep
        (tmp_path / "test.txt").write_text("TEST\n", encoding="utf-8")
        result = _run(grep("test", str(tmp_path), ignore_case=True))
        assert is_success(result)
        assert result["llm_data"]["metrics"]["total_matches"]["value"] >= 1

    def test_bug_8_file_pattern_empty(self, tmp_path):
        """BUG#8: glob=""空字符串 → 搜索所有文件"""
        from app.tools.file.grep_file_content import grep
        (tmp_path / "test.txt").write_text("test\n", encoding="utf-8")
        result = _run(grep("test", str(tmp_path), glob=""))
        assert is_success(result)

    def test_bug_9_binary_file(self, tmp_path):
        """BUG#9: 搜索二进制文件"""
        from app.tools.file.grep_file_content import grep
        fp = tmp_path / "test.bin"
        fp.write_bytes(b"\x00\x01\x02\x03test\x00")
        (tmp_path / "ref.txt").write_text("test", encoding="utf-8")
        result = _run(grep("test", str(tmp_path), glob="*.bin"))
        assert is_success(result)

    def test_bug_11_multiline_pattern(self, tmp_path):
        """BUG#11: pattern包含换行符"""
        from app.tools.file.grep_file_content import grep
        (tmp_path / "test.txt").write_text("line1\nline2\n", encoding="utf-8")
        result = _run(grep("line1\nline2", str(tmp_path)))
        assert is_success(result)

    def test_bug_12_search_path_is_file(self, tmp_path):
        """BUG#12: search_dir指向文件"""
        from app.tools.file.grep_file_content import grep
        fp = tmp_path / "test.txt"
        fp.write_text("test\n", encoding="utf-8")
        result = _run(grep("test", str(fp)))
        assert is_success(result)
