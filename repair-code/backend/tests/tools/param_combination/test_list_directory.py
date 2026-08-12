# -*- coding: utf-8 -*-
"""
list_directory参数组合测试 - 小欧 2026-06-24

测试类型:
1. 参数组合测试 - 8个组合(tree/sort_by/include_hidden)
2. 功能测试 - 各参数独立功能
3. 真实场景测试 - 项目目录/嵌套目录
4. 边界测试 - 空目录/符号链接
5. 负面测试 - 不存在/文件路径/无效sort_by
"""

import pytest
import asyncio
from pathlib import Path
from app.tools.file.list_directory import listdir
from app.tools.file.tree import tree
from app.tools.tool_response import is_success, is_error


class TestListDirectoryParamCombinations:
    """参数组合测试 - 穷举所有参数组合"""

    def test_default_params(self, temp_output_dir):
        """组合1: 仅dir_path(默认参数)"""
        (temp_output_dir / "a.txt").write_text("a", encoding="utf-8")
        (temp_output_dir / "b.txt").write_text("bb", encoding="utf-8")

        result = asyncio.run(
            listdir(str(temp_output_dir))
        )

        assert is_success(result)
        assert result["llm_data"]["metrics"]["total"]["value"] == 2
        names = [e["name"] for e in result["data"]["entries"]]
        assert "a.txt" in names
        assert "b.txt" in names

    def test_tree_mode(self, temp_output_dir):
        """组合2: tree=True(目录树模式)"""
        sub = temp_output_dir / "subdir"
        sub.mkdir()
        (sub / "child.txt").write_text("child", encoding="utf-8")
        (temp_output_dir / "root.txt").write_text("root", encoding="utf-8")

        result = asyncio.run(
            tree(str(temp_output_dir))
        )

        assert is_success(result)
        assert "tree" in result["data"]
        assert "statistics" in result["data"]
        assert result["data"]["statistics"]["file_count"] >= 1

    def test_sort_by_name(self, temp_output_dir):
        """组合3: sort_by='name'"""
        (temp_output_dir / "c.txt").write_text("c", encoding="utf-8")
        (temp_output_dir / "a.txt").write_text("a", encoding="utf-8")
        (temp_output_dir / "b.txt").write_text("b", encoding="utf-8")

        result = asyncio.run(
            listdir(str(temp_output_dir), sort_by="name")
        )

        assert is_success(result)
        names = [e["name"] for e in result["data"]["entries"]]
        assert names == sorted(names)

    def test_sort_by_size(self, temp_output_dir):
        """组合4: sort_by='size'"""
        (temp_output_dir / "small.txt").write_text("s", encoding="utf-8")
        (temp_output_dir / "large.txt").write_text("x" * 1000, encoding="utf-8")
        (temp_output_dir / "medium.txt").write_text("m" * 100, encoding="utf-8")

        result = asyncio.run(
            listdir(str(temp_output_dir), sort_by="size")
        )

        assert is_success(result)
        sizes = [e["size"] for e in result["data"]["entries"] if e["type"] == "file"]
        assert sizes == sorted(sizes, reverse=True)

    def test_sort_by_mtime(self, temp_output_dir):
        """组合5: sort_by='mtime'"""
        (temp_output_dir / "old.txt").write_text("old", encoding="utf-8")
        (temp_output_dir / "new.txt").write_text("new", encoding="utf-8")

        result = asyncio.run(
            listdir(str(temp_output_dir), sort_by="mtime")
        )

        assert is_success(result)
        assert result["llm_data"]["metrics"]["total"]["value"] == 2

    def test_include_hidden(self, temp_output_dir):
        """组合6: include_hidden=True"""
        (temp_output_dir / "visible.txt").write_text("v", encoding="utf-8")
        (temp_output_dir / ".hidden.txt").write_text("h", encoding="utf-8")

        result_with = asyncio.run(
            listdir(str(temp_output_dir), include_hidden=True)
        )
        result_without = asyncio.run(
            listdir(str(temp_output_dir), include_hidden=False)
        )

        assert is_success(result_with)
        assert is_success(result_without)
        names_with = [e["name"] for e in result_with["data"]["entries"]]
        names_without = [e["name"] for e in result_without["data"]["entries"]]
        assert ".hidden.txt" in names_with
        assert ".hidden.txt" not in names_without

    def test_tree_with_hidden(self, temp_output_dir):
        """组合7: tree=True + include_hidden=True"""
        sub = temp_output_dir / ".hidden_dir"
        sub.mkdir()
        (sub / "file.txt").write_text("f", encoding="utf-8")

        result = asyncio.run(
            tree(str(temp_output_dir), include_hidden=True)
        )

        assert is_success(result)
        assert "tree" in result["data"]

    def test_sort_by_size_with_dirs(self, temp_output_dir):
        """组合8: sort_by='size' + 目录混排"""
        sub = temp_output_dir / "subdir"
        sub.mkdir()
        (temp_output_dir / "file.txt").write_text("f", encoding="utf-8")

        result = asyncio.run(
            listdir(str(temp_output_dir), sort_by="size")
        )

        assert is_success(result)
        assert result["llm_data"]["metrics"]["total"]["value"] == 2
        types = [e["type"] for e in result["data"]["entries"]]
        assert "directory" in types
        assert "file" in types


class TestListDirectoryFeatures:
    """功能测试"""

    def test_empty_directory(self, temp_output_dir):
        """功能1: 空目录"""
        empty = temp_output_dir / "empty"
        empty.mkdir()

        result = asyncio.run(
            listdir(str(empty))
        )

        assert is_success(result)
        assert result["llm_data"]["metrics"]["total"]["value"] == 0
        assert result["data"]["entries"] == []

    def test_nested_subdirectories(self, temp_output_dir):
        """功能2: 多层嵌套目录(非tree模式只显示一层)"""
        l1 = temp_output_dir / "level1"
        l2 = l1 / "level2"
        l3 = l2 / "level3"
        l3.mkdir(parents=True)
        (l3 / "deep.txt").write_text("deep", encoding="utf-8")

        result = asyncio.run(
            listdir(str(temp_output_dir))
        )

        assert is_success(result)
        names = [e["name"] for e in result["data"]["entries"]]
        assert "level1" in names
        assert "deep.txt" not in names

    def test_file_type_detection(self, temp_output_dir):
        """功能3: 文件/目录类型识别"""
        (temp_output_dir / "file.txt").write_text("f", encoding="utf-8")
        (temp_output_dir / "subdir").mkdir()

        result = asyncio.run(
            listdir(str(temp_output_dir))
        )

        assert is_success(result)
        entries = {e["name"]: e["type"] for e in result["data"]["entries"]}
        assert entries["file.txt"] == "file"
        assert entries["subdir"] == "directory"

    def test_statistics_accuracy(self, temp_output_dir):
        """功能4: 统计数据准认性"""
        (temp_output_dir / "a.py").write_text("print('a')", encoding="utf-8")
        (temp_output_dir / "b.py").write_text("print('bb')", encoding="utf-8")
        (temp_output_dir / "c.txt").write_text("txt", encoding="utf-8")
        (temp_output_dir / "subdir").mkdir()

        result = asyncio.run(
            listdir(str(temp_output_dir))
        )

        assert is_success(result)
        metrics = result["llm_data"]["metrics"]
        assert metrics["file_count"]["value"] == 3
        assert metrics["dir_count"]["value"] == 1
        assert metrics["total_size"]["value"] > 0

    def test_tree_mode_only_dirs(self, temp_output_dir):
        """功能5: tree模式只显示目录"""
        (temp_output_dir / "file.txt").write_text("f", encoding="utf-8")
        sub = temp_output_dir / "subdir"
        sub.mkdir()
        (sub / "child.txt").write_text("c", encoding="utf-8")

        result = asyncio.run(
            tree(str(temp_output_dir))
        )

        assert is_success(result)
        tree_data = result["data"]["tree"]
        assert tree_data["type"] == "directory"
        child_names = [c["name"] for c in tree_data.get("children", [])]
        assert "subdir" in child_names


class TestListDirectoryRealScenarios:
    """真实业务场景测试"""

    def test_project_backend_directory(self, temp_output_dir):
        """场景1: 模拟项目在里目录结构"""
        (temp_output_dir / "main.py").write_text("# main entry", encoding="utf-8")
        (temp_output_dir / "config.yaml").write_text("app: test", encoding="utf-8")
        (temp_output_dir / "requirements.txt").write_text("fastapi", encoding="utf-8")
        app = temp_output_dir / "app"
        app.mkdir()
        (app / "__init__.py").write_text("", encoding="utf-8")
        (app / "api.py").write_text("# api", encoding="utf-8")
        tests = temp_output_dir / "tests"
        tests.mkdir()
        (tests / "test_main.py").write_text("# test", encoding="utf-8")

        result = asyncio.run(
            listdir(str(temp_output_dir))
        )

        assert is_success(result)
        assert result["llm_data"]["metrics"]["total"]["value"] == 5
        assert result["llm_data"]["metrics"]["file_count"]["value"] == 3
        assert result["llm_data"]["metrics"]["dir_count"]["value"] == 2

    def test_log_directory_with_various_sizes(self, temp_output_dir):
        """场景2: 不同大小文件的目录"""
        (temp_output_dir / "tiny.log").write_text("t", encoding="utf-8")
        (temp_output_dir / "small.log").write_text("s" * 500, encoding="utf-8")
        (temp_output_dir / "medium.log").write_text("m" * 5000, encoding="utf-8")
        (temp_output_dir / "large.log").write_text("l" * 50000, encoding="utf-8")

        result = asyncio.run(
            listdir(str(temp_output_dir), sort_by="size")
        )

        assert is_success(result)
        metrics = result["llm_data"]["metrics"]
        assert metrics["file_count"]["value"] >= 1

    def test_tree_nested_project(self, temp_output_dir):
        """场景3: 树状展示嵌套项目结构"""
        src = temp_output_dir / "src" / "components"
        src.mkdir(parents=True)
        (src / "Button.tsx").write_text("// button", encoding="utf-8")
        (src / "Modal.tsx").write_text("// modal", encoding="utf-8")
        test = temp_output_dir / "tests" / "unit"
        test.mkdir(parents=True)
        (test / "test_button.py").write_text("# test", encoding="utf-8")

        result = asyncio.run(
            tree(str(temp_output_dir))
        )

        assert is_success(result)
        tree_data = result["data"]["tree"]
        child_names = [c["name"] for c in tree_data.get("children", [])]
        assert "src" in child_names
        assert "tests" in child_names


class TestListDirectoryBoundary:
    """边界测试"""

    def test_directory_with_only_hidden(self, temp_output_dir):
        """边界1: 只有隐藏文件的目录"""
        (temp_output_dir / ".gitignore").write_text("*.pyc", encoding="utf-8")
        (temp_output_dir / ".env").write_text("KEY=val", encoding="utf-8")

        result_without = asyncio.run(
            listdir(str(temp_output_dir), include_hidden=False)
        )
        result_with = asyncio.run(
            listdir(str(temp_output_dir), include_hidden=True)
        )

        assert is_success(result_without)
        assert is_success(result_with)
        assert result_without["llm_data"]["metrics"]["total"]["value"] == 0
        assert result_with["llm_data"]["metrics"]["total"]["value"] == 1

    def test_special_name_files(self, temp_output_dir):
        """边界2: 特殊字符文件名"""
        (temp_output_dir / "文件名.txt").write_text("中文", encoding="utf-8")
        (temp_output_dir / "file with spaces.txt").write_text("space", encoding="utf-8")
        (temp_output_dir / "file-v2.0.txt").write_text("version", encoding="utf-8")

        result = asyncio.run(
            listdir(str(temp_output_dir))
        )

        assert is_success(result)
        assert result["llm_data"]["metrics"]["total"]["value"] == 3

    def test_single_item_directory(self, temp_output_dir):
        """边界3: 单个文件的目录"""
        (temp_output_dir / "only.txt").write_text("only", encoding="utf-8")

        result = asyncio.run(
            listdir(str(temp_output_dir))
        )

        assert is_success(result)
        assert result["llm_data"]["metrics"]["total"]["value"] == 1
        assert result["data"]["entries"][0]["name"] == "only.txt"


class TestListDirectoryNegative:
    """负面测试"""

    def test_directory_not_found(self, temp_output_dir):
        """负面1: 目录不存在"""
        result = asyncio.run(
            listdir(str(temp_output_dir / "nonexistent"))
        )

        assert is_error(result)
        assert result["llm_data"]["status"]["exec_code"] == "error"

    def test_file_instead_of_directory(self, temp_output_dir):
        """负面2: 传入文件路径"""
        file_path = temp_output_dir / "file.txt"
        file_path.write_text("content", encoding="utf-8")

        result = asyncio.run(
            listdir(str(file_path))
        )

        assert is_error(result)
        assert result["llm_data"]["status"]["exec_code"] == "error"

    def test_invalid_sort_by(self, temp_output_dir):
        """负面3: 无效的sort_by参数"""
        result = asyncio.run(
            listdir(str(temp_output_dir), sort_by="invalid")
        )

        assert is_error(result)
        assert result["llm_data"]["status"]["exec_code"] == "error"
        assert "sort_by" in result["llm_data"]["status"]["detail"]
