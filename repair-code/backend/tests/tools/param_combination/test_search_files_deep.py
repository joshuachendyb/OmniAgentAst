# -*- coding: utf-8 -*-
"""
search_files 第三轮深度BUG发现测试
小健 2026-06-25
"""
import asyncio
import pytest
import tempfile
from pathlib import Path

from app.tools.tool_response import is_success, is_error


def _run(coro):
    return asyncio.run(coro)


class TestSearchFilesDeepBugs:
    """深度BUG发现 — search_files — 小健 2026-06-25"""

    def test_bug_1_pattern_empty(self, tmp_path):
        """BUG#1: pattern=""空字符串"""
        from app.tools.file.search_files import find
        result = _run(find("", str(tmp_path)))
        # 应该报错或匹配所有文件

    def test_bug_2_pattern_none(self, tmp_path):
        """BUG#2: pattern=None"""
        from app.tools.file.search_files import find
        result = _run(find(None, str(tmp_path)))
        assert is_error(result)

    def test_bug_3_search_dir_empty(self, tmp_path):
        """BUG#3: search_dir=""空字符串"""
        from app.tools.file.search_files import find
        result = _run(find("*.txt", ""))
        assert is_error(result)

    def test_bug_4_search_dir_not_exist(self, tmp_path):
        """BUG#4: search_dir不存在"""
        from app.tools.file.search_files import find
        result = _run(find("*.txt", str(tmp_path / "not_exist")))
        assert is_error(result)

    def test_bug_5_pattern_with_regex_chars(self, tmp_path):
        """BUG#5: pattern包含正则特殊字符"""
        from app.tools.file.search_files import find
        (tmp_path / "test[1].txt").write_text("test", encoding="utf-8")
        result = _run(find("test[1].txt", str(tmp_path)))
        # fnmatch应该正认处理

    def test_bug_6_ignore_case_true(self, tmp_path):
        """BUG#6: ignore_case=True大小写不敏感"""
        from app.tools.file.search_files import find
        (tmp_path / "TEST.TXT").write_text("test", encoding="utf-8")
        result = _run(find("*.txt", str(tmp_path), ignore_case=True))
        assert is_success(result)

    def test_bug_7_pattern_star_only(self, tmp_path):
        """BUG#7: pattern="*"匹配所有"""
        from app.tools.file.search_files import find
        (tmp_path / "file.txt").write_text("test", encoding="utf-8")
        (tmp_path / "data.csv").write_text("test", encoding="utf-8")
        result = _run(find("*", str(tmp_path)))
        assert is_success(result)

    def test_bug_8_very_large_directory(self, tmp_path):
        """BUG#8: 非常大的目录(1000个文件)"""
        from app.tools.file.search_files import find
        for i in range(1000):
            (tmp_path / f"file{i}.txt").write_text("test", encoding="utf-8")
        result = _run(find("*.txt", str(tmp_path)))
        assert is_success(result)

    def test_bug_9_search_dir_is_file(self, tmp_path):
        """BUG#9: search_dir指向文件"""
        from app.tools.file.search_files import find
        fp = tmp_path / "test.txt"
        fp.write_text("test", encoding="utf-8")
        result = _run(find("*.txt", str(fp)))
        assert is_error(result)

    def test_bug_10_pattern_with_path_separator(self, tmp_path):
        """BUG#10: pattern包含路径分隔符"""
        from app.tools.file.search_files import find
        result = _run(find("sub/*.txt", str(tmp_path)))
        # 应该报错或特殊处理

    def test_bug_11_concurrent_search(self, tmp_path):
        """BUG#11: 并发搜索"""
        from app.tools.file.search_files import find
        async def search_task():
            return await find("*.txt", str(tmp_path))
        async def _gather_all():
            return await asyncio.gather(*[search_task() for _ in range(10)])
        results = _run(_gather_all())
        assert all(is_success(r) for r in results)

    def test_bug_12_pattern_question_mark(self, tmp_path):
        """BUG#12: pattern="file?.txt"问号通配"""
        from app.tools.file.search_files import find
        (tmp_path / "file1.txt").write_text("test", encoding="utf-8")
        (tmp_path / "file12.txt").write_text("test", encoding="utf-8")
        result = _run(find("file?.txt", str(tmp_path)))
        assert is_success(result)
        # 应该只匹配file1.txt
