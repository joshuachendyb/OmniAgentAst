# -*- coding: utf-8 -*-
"""
list_directory 第三轮深度BUG发现测试
小健 2026-06-25
"""
import asyncio
import pytest
import tempfile
from pathlib import Path

from app.tools.tool_response import is_success, is_error


def _run(coro):
    return asyncio.run(coro)


class TestListDirectoryDeepBugs:
    """深度BUG发现 — list_directory — 小健 2026-06-25"""

    def test_bug_1_path_empty(self, tmp_path):
        """BUG#1: path=""空字符串"""
        from app.tools.file.list_directory import listdir
        result = _run(listdir(""))
        assert is_error(result)

    def test_bug_2_path_none(self, tmp_path):
        """BUG#2: path=None"""
        from app.tools.file.list_directory import listdir
        result = _run(listdir(None))
        assert is_error(result)

    def test_bug_3_path_is_file(self, tmp_path):
        """BUG#3: path指向文件而非目录"""
        from app.tools.file.list_directory import listdir
        fp = tmp_path / "test.txt"
        fp.write_text("test", encoding="utf-8")
        result = _run(listdir(str(fp)))
        assert is_error(result)

    def test_bug_4_tree_mode(self, tmp_path):
        """BUG#4: tree=True树形模式"""
        from app.tools.file.tree import tree
        (tmp_path / "sub").mkdir()
        (tmp_path / "file.txt").write_text("test", encoding="utf-8")
        result = _run(tree(str(tmp_path)))
        assert is_success(result)

    def test_bug_5_empty_directory(self, tmp_path):
        """BUG#5: 空目录"""
        from app.tools.file.list_directory import listdir
        result = _run(listdir(str(tmp_path)))
        assert is_success(result)

    def test_bug_6_include_hidden_true(self, tmp_path):
        """BUG#6: include_hidden=True包含隐藏文件"""
        from app.tools.file.list_directory import listdir
        (tmp_path / ".hidden").write_text("test", encoding="utf-8")
        result = _run(listdir(str(tmp_path), include_hidden=True))
        assert is_success(result)

    def test_bug_7_sort_by_invalid(self, tmp_path):
        """BUG#7: sort_by="invalid"无效值"""
        from app.tools.file.list_directory import listdir
        result = _run(listdir(str(tmp_path), sort_by="invalid"))
        # 应该报错或使用默认值

    def test_bug_8_path_with_special_chars(self, tmp_path):
        """BUG#8: 路径包含特殊字符"""
        from app.tools.file.list_directory import listdir
        sp = tmp_path / "测试 目录[1]"
        sp.mkdir()
        result = _run(listdir(str(sp)))
        assert is_success(result)

    def test_bug_9_sort_by_size(self, tmp_path):
        """BUG#9: sort_by="size"按大小排序"""
        from app.tools.file.list_directory import listdir
        (tmp_path / "a").mkdir()
        (tmp_path / "b").mkdir()
        (tmp_path / "a" / "file.txt").write_text("test", encoding="utf-8")
        result = _run(listdir(str(tmp_path), sort_by="size"))
        # 应该按大小排序

    def test_bug_10_permission_denied(self, tmp_path):
        """BUG#10: 无权限目录(Windows可能无法测试)"""
        from app.tools.file.list_directory import listdir
        # Windows权限测试较复杂,跳过
        pass

    def test_bug_11_concurrent_list_same_dir(self, tmp_path):
        """BUG#11: 并发列出同一目录"""
        from app.tools.file.list_directory import listdir
        async def list_task():
            return await listdir(str(tmp_path))
        async def _gather():
            return await asyncio.gather(*[list_task() for _ in range(10)])
        results = _run(_gather())
        assert all(is_success(r) for r in results)
