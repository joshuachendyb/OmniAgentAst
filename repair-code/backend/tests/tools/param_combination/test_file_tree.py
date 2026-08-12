# -*- coding: utf-8 -*-
"""tree参数组合测试 - 小欧 2026-07-04

测试目录树工具参数组合、边界条件、异常场景
注意：tree是async函数，需用_run()执行
"""

import asyncio
import os
import pytest
from app.tools.tool_response import is_success, is_error
from app.tools.file.tree import tree


def _run(coro):
    return asyncio.run(coro)


class TestTreeNormal:
    """正常参数组合"""

    def test_default_params(self, temp_output_dir):
        result = _run(tree(path=str(temp_output_dir)))
        assert is_success(result)
        data = result["data"]
        assert "tree" in data
        assert isinstance(data["tree"], dict)

    def test_include_hidden_false(self, temp_output_dir):
        result = _run(tree(path=str(temp_output_dir), include_hidden=False))
        assert is_success(result)

    def test_include_hidden_true(self, temp_output_dir):
        hidden_dir = temp_output_dir / ".hidden"
        hidden_dir.mkdir()
        result = _run(tree(path=str(temp_output_dir), include_hidden=True))
        assert is_success(result)

    def test_sort_by_name(self, temp_output_dir):
        for i in range(3):
            (temp_output_dir / f"dir_{i}").mkdir()
        result = _run(tree(path=str(temp_output_dir), sort_by="name"))
        assert is_success(result)

    def test_sort_by_mtime(self, temp_output_dir):
        for i in range(3):
            (temp_output_dir / f"dir_{i}").mkdir()
        result = _run(tree(path=str(temp_output_dir), sort_by="mtime"))
        assert is_success(result)

    def test_nested_directories(self, temp_output_dir):
        deep = temp_output_dir / "a" / "b" / "c"
        deep.mkdir(parents=True)
        result = _run(tree(path=str(temp_output_dir)))
        assert is_success(result)
        tree_data = result["data"]["tree"]
        assert "children" in tree_data

    def test_empty_directory(self, temp_output_dir):
        result = _run(tree(path=str(temp_output_dir)))
        assert is_success(result)
        tree_node = result["data"]["tree"]
        assert tree_node["children"] == []


class TestTreeStatistics:
    """统计信息验证"""

    def test_statistics_exists(self, temp_output_dir):
        result = _run(tree(path=str(temp_output_dir)))
        data = result["data"]
        assert "statistics" in data
        stats = data["statistics"]
        assert "dir_count" in stats
        assert "file_count" in stats

    def test_statistics_counts(self, temp_output_dir):
        (temp_output_dir / "sub1").mkdir()
        (temp_output_dir / "sub2").mkdir()
        (temp_output_dir / "sub1" / "sub3").mkdir()
        result = _run(tree(path=str(temp_output_dir)))
        stats = result["data"]["statistics"]
        assert stats["dir_count"] >= 3

    def test_tree_name_matches_dirname(self, temp_output_dir):
        result = _run(tree(path=str(temp_output_dir)))
        tree_node = result["data"]["tree"]
        assert tree_node["name"] == temp_output_dir.name


class TestTreeEdgeCases:
    """边界情况"""

    def test_non_existent_directory(self):
        result = _run(tree(path="Z:/non_existent_dir_12345"))
        assert is_error(result)

    def test_file_path_instead_of_dir(self, temp_output_dir):
        f = temp_output_dir / "test.txt"
        f.write_text("hello")
        result = _run(tree(path=str(f)))
        assert is_error(result)

    def test_empty_path(self):
        result = _run(tree(path=""))
        assert is_error(result)

    def test_invalid_sort_by(self):
        result = _run(tree(path=".", sort_by="size"))
        assert is_error(result)
