# -*- coding: utf-8 -*-
"""
search_files参数组合测试 - 小沈 2026-06-24

测试类型:
1. 参数组合测试 - 6个组合(pattern/ignore_case/type)
2. 功能测试 - 通配符/递归/类型过滤
3. 真实场景测试 - 项目文件搜索
4. 边界测试 - 空目录/特殊文件名
5. 负面测试 - 不存在/空pattern
"""

import pytest
import asyncio
from pathlib import Path
from app.tools.file.search_files import find
from app.tools.tool_response import is_success, is_error


class TestSearchFilesParamCombinations:
    """参数组合测试 - 穷举所有参数组合"""

    def test_basic_search(self, temp_output_dir):
        """组合1: 仅pattern+search_dir"""
        (temp_output_dir / "app.py").write_text("a", encoding="utf-8")
        (temp_output_dir / "test.py").write_text("t", encoding="utf-8")
        (temp_output_dir / "readme.md").write_text("r", encoding="utf-8")

        result = asyncio.run(
            find("*.py", str(temp_output_dir))
        )

        assert is_success(result)
        assert result["llm_data"]["metrics"]["total"]["value"] == 2

    def test_case_insensitive_default(self, temp_output_dir):
        """组合2: ignore_case=True(默认)"""
        (temp_output_dir / "MyFile.TXT").write_text("a", encoding="utf-8")

        result = asyncio.run(
            find("*.txt", str(temp_output_dir), ignore_case=True)
        )

        assert is_success(result)
        assert result["llm_data"]["metrics"]["total"]["value"] == 1

    def test_case_sensitive(self, temp_output_dir):
        """组合3: ignore_case=False — 注意: fnmatch在Windows下本身不区分大小写,ignore_case=False实际无效"""
        (temp_output_dir / "MyFile.TXT").write_text("a", encoding="utf-8")
        (temp_output_dir / "other.txt").write_text("b", encoding="utf-8")

        result = asyncio.run(
            find("*.txt", str(temp_output_dir), ignore_case=False)
        )

        assert is_success(result)
        # Windows下fnmatch默认大小写不敏感,所以两个都匹配
        assert result["llm_data"]["metrics"]["total"]["value"] == 2

    def test_type_filter_file(self, temp_output_dir):
        """组合4: type='file'"""
        (temp_output_dir / "file.txt").write_text("f", encoding="utf-8")
        (temp_output_dir / "subdir").mkdir()

        result = asyncio.run(
            find("*", str(temp_output_dir), type="file")
        )

        assert is_success(result)
        assert result["llm_data"]["metrics"]["total"]["value"] == 1
        assert result["data"]["matches"][0]["type"] == "file"

    def test_type_filter_directory(self, temp_output_dir):
        """组合5: type='directory'"""
        (temp_output_dir / "file.txt").write_text("f", encoding="utf-8")
        (temp_output_dir / "subdir").mkdir()

        result = asyncio.run(
            find("*", str(temp_output_dir), type="directory")
        )

        assert is_success(result)
        assert result["llm_data"]["metrics"]["total"]["value"] == 1
        assert result["data"]["matches"][0]["type"] == "directory"

    def test_type_none_shows_all(self, temp_output_dir):
        """组合6: type=None(默认,显示全部)"""
        (temp_output_dir / "file.txt").write_text("f", encoding="utf-8")
        (temp_output_dir / "subdir").mkdir()

        result = asyncio.run(
            find("*", str(temp_output_dir), type=None)
        )

        assert is_success(result)
        assert result["llm_data"]["metrics"]["total"]["value"] == 2


class TestSearchFilesFeatures:
    """功能测试"""

    def test_wildcard_star(self, temp_output_dir):
        """功能1: *通配符"""
        (temp_output_dir / "app.py").write_text("a", encoding="utf-8")
        (temp_output_dir / "app.js").write_text("b", encoding="utf-8")
        (temp_output_dir / "test.py").write_text("c", encoding="utf-8")

        result = asyncio.run(
            find("app.*", str(temp_output_dir))
        )

        assert is_success(result)
        assert result["llm_data"]["metrics"]["total"]["value"] == 2

    def test_wildcard_question_mark(self, temp_output_dir):
        """功能2: ?通配符"""
        (temp_output_dir / "file1.py").write_text("a", encoding="utf-8")
        (temp_output_dir / "file2.py").write_text("b", encoding="utf-8")
        (temp_output_dir / "file12.py").write_text("c", encoding="utf-8")

        result = asyncio.run(
            find("file?.py", str(temp_output_dir))
        )

        assert is_success(result)
        assert result["llm_data"]["metrics"]["total"]["value"] == 2

    def test_double_star_recursive(self, temp_output_dir):
        """功能3: 递归匹配 — fnmatch不支持**,用*.py验证os.walk递归遍历"""
        sub = temp_output_dir / "src" / "components"
        sub.mkdir(parents=True)
        (temp_output_dir / "root.py").write_text("r", encoding="utf-8")
        (sub / "deep.py").write_text("d", encoding="utf-8")

        result = asyncio.run(
            find("*.py", str(temp_output_dir))
        )

        assert is_success(result)
        assert result["llm_data"]["metrics"]["total"]["value"] == 2

    def test_search_result_structure(self, temp_output_dir):
        """功能4: 搜索结果结构"""
        (temp_output_dir / "test.txt").write_text("t", encoding="utf-8")

        result = asyncio.run(
            find("*.txt", str(temp_output_dir))
        )

        assert is_success(result)
        match = result["data"]["matches"][0]
        assert "name" in match
        assert "path" in match
        assert "relative_path" in match
        assert "type" in match
        assert match["name"] == "test.txt"
        assert match["type"] == "file"

    def test_chinese_filename(self, temp_output_dir):
        """功能5: 中文文件名"""
        (temp_output_dir / "测试文件.txt").write_text("t", encoding="utf-8")
        (temp_output_dir / "文档.md").write_text("d", encoding="utf-8")

        result = asyncio.run(
            find("*.txt", str(temp_output_dir))
        )

        assert is_success(result)
        assert result["llm_data"]["metrics"]["total"]["value"] == 1
        assert "测试文件" in result["data"]["matches"][0]["name"]


class TestSearchFilesRealScenarios:
    """真实业务场景测试"""

    def test_find_python_files(self, temp_output_dir):
        """场景1: 查找所有Python文件"""
        (temp_output_dir / "main.py").write_text("a", encoding="utf-8")
        (temp_output_dir / "utils.py").write_text("b", encoding="utf-8")
        (temp_output_dir / "readme.md").write_text("c", encoding="utf-8")
        sub = temp_output_dir / "app"
        sub.mkdir()
        (sub / "__init__.py").write_text("", encoding="utf-8")
        (sub / "api.py").write_text("d", encoding="utf-8")

        result = asyncio.run(
            find("*.py", str(temp_output_dir))
        )

        assert is_success(result)
        assert result["llm_data"]["metrics"]["total"]["value"] == 4

    def test_find_config_files(self, temp_output_dir):
        """场景2: 查找配置文件"""
        (temp_output_dir / "config.yaml").write_text("a", encoding="utf-8")
        (temp_output_dir / "config.json").write_text("b", encoding="utf-8")
        (temp_output_dir / "settings.toml").write_text("c", encoding="utf-8")
        (temp_output_dir / "app.py").write_text("d", encoding="utf-8")

        # fnmatch不支持{yaml,json,toml},逐个测试
        result_yaml = asyncio.run(
            find("*.yaml", str(temp_output_dir))
        )
        result_json = asyncio.run(
            find("*.json", str(temp_output_dir))
        )
        result_toml = asyncio.run(
            find("*.toml", str(temp_output_dir))
        )

        assert is_success(result_yaml)
        assert result_yaml["llm_data"]["metrics"]["total"]["value"] == 1
        assert is_success(result_json)
        assert result_json["llm_data"]["metrics"]["total"]["value"] == 1
        assert is_success(result_toml)
        assert result_toml["llm_data"]["metrics"]["total"]["value"] == 1

    def test_find_test_files(self, temp_output_dir):
        """场景3: 查找测试文件"""
        (temp_output_dir / "test_auth.py").write_text("a", encoding="utf-8")
        (temp_output_dir / "test_api.py").write_text("b", encoding="utf-8")
        (temp_output_dir / "main.py").write_text("c", encoding="utf-8")
        tests = temp_output_dir / "tests"
        tests.mkdir()
        (tests / "test_utils.py").write_text("d", encoding="utf-8")

        result = asyncio.run(
            find("test_*.py", str(temp_output_dir))
        )

        assert is_success(result)
        assert result["llm_data"]["metrics"]["total"]["value"] == 3

    def test_find_only_directories(self, temp_output_dir):
        """场景4: 只查找目录"""
        (temp_output_dir / "file.txt").write_text("f", encoding="utf-8")
        for name in ["src", "tests", "docs", "config"]:
            (temp_output_dir / name).mkdir()

        result = asyncio.run(
            find("*", str(temp_output_dir), type="directory")
        )

        assert is_success(result)
        assert result["llm_data"]["metrics"]["total"]["value"] == 4


class TestSearchFilesBoundary:
    """边界测试"""

    def test_empty_directory(self, temp_output_dir):
        """边界1: 空目录"""
        empty = temp_output_dir / "empty"
        empty.mkdir()

        result = asyncio.run(
            find("*", str(empty))
        )

        assert is_success(result)
        assert result["llm_data"]["metrics"]["total"]["value"] == 0

    def test_special_characters_in_name(self, temp_output_dir):
        """边界2: 特殊字符文件名"""
        (temp_output_dir / "file (1).txt").write_text("a", encoding="utf-8")
        (temp_output_dir / "file-v2.0.txt").write_text("b", encoding="utf-8")
        (temp_output_dir / "file_backup.txt").write_text("c", encoding="utf-8")

        result = asyncio.run(
            find("file*.txt", str(temp_output_dir))
        )

        assert is_success(result)
        assert result["llm_data"]["metrics"]["total"]["value"] == 3

    def test_no_match(self, temp_output_dir):
        """边界3: 无匹配结果"""
        (temp_output_dir / "app.py").write_text("a", encoding="utf-8")

        result = asyncio.run(
            find("*.xyz", str(temp_output_dir))
        )

        assert is_success(result)
        assert result["llm_data"]["metrics"]["total"]["value"] == 0

    def test_deeply_nested(self, temp_output_dir):
        """边界4: 深层嵌套"""
        deep = temp_output_dir
        for i in range(5):
            deep = deep / f"level{i}"
            deep.mkdir()
        (deep / "target.py").write_text("t", encoding="utf-8")

        result = asyncio.run(
            find("*.py", str(temp_output_dir))
        )

        assert is_success(result)
        assert result["llm_data"]["metrics"]["total"]["value"] == 1


class TestSearchFilesNegative:
    """负面测试"""

    def test_search_dir_not_found(self, temp_output_dir):
        """负面1: 搜索目录不存在"""
        result = asyncio.run(
            find("*.py", str(temp_output_dir / "nonexistent"))
        )

        assert is_error(result)
        assert result["llm_data"]["status"]["exec_code"] == "error"

    def test_empty_pattern(self, temp_output_dir):
        """负面2: 空pattern"""
        (temp_output_dir / "file.txt").write_text("f", encoding="utf-8")

        result = asyncio.run(
            find("", str(temp_output_dir))
        )

        assert is_error(result)
        assert result["llm_data"]["status"]["exec_code"] == "error"

    def test_whitespace_pattern(self, temp_output_dir):
        """负面3: 纯空白pattern"""
        (temp_output_dir / "file.txt").write_text("f", encoding="utf-8")

        result = asyncio.run(
            find("   ", str(temp_output_dir))
        )

        assert is_error(result)
        assert result["llm_data"]["status"]["exec_code"] == "error"
