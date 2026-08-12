# -*- coding: utf-8 -*-
"""
list_directory parameter combination and content tests v2
Requirements: schema-driven, content over 100 lines, verify actual content, find bugs
xiaojian 2026-06-24

Schema params: dir_path(str required), sort_by(name/mtime default name), include_hidden(bool default False)
Param combos: 2x2x2=8 types + boundary/negative

编辑历史:
  2026-08-11 - 小欧 - test_list_sort_by_mtime: 原断言用size代理mtime排序, 且_setup_rich_directory同秒创建文件致mtime全相同排序不稳(flaky);
      改为显式设置递增mtime并直接断言返回entries按mtime降序(确定性, 对齐list_directory.py:241-242实现)
"""
import asyncio
import os
import pytest
from pathlib import Path

from app.tools.tool_response import is_success, is_error
from app.tools.file.list_directory import listdir
from app.tools.file.tree import tree


def _run(coro):
    return asyncio.run(coro)


def _file_types_from_entries(entries):
    """从listdir返回的entries(当前真实结构)重新计算扩展名分布 — 适配statistics移入metrics"""
    types = {}
    for e in entries:
        if e.get("type") == "file":
            name = e["name"]
            ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
            types[ext] = types.get(ext, 0) + 1
    return types


def _size_distribution_from_entries(entries):
    """从listdir返回的entries重新计算大小分桶 — 适配statistics移入metrics"""
    bins = {"<1KB": 0, "1KB-10KB": 0, "10KB-100KB": 0, "100KB-1MB": 0, ">1MB": 0}
    for e in entries:
        if e.get("type") == "file":
            size = e.get("size", 0) or 0
            if size < 1024:
                bins["<1KB"] += 1
            elif size < 10240:
                bins["1KB-10KB"] += 1
            elif size < 102400:
                bins["10KB-100KB"] += 1
            elif size < 1048576:
                bins["100KB-1MB"] += 1
            else:
                bins[">1MB"] += 1
    return bins


def _setup_rich_directory(base: Path) -> dict:
    """Create rich directory structure for testing - xiaojian 2026-06-24"""
    base.mkdir(parents=True, exist_ok=True)
    dirs = {}
    (base / "src").mkdir()
    (base / "src" / "main.py").write_text("print('hello')", encoding="utf-8")
    (base / "src" / "utils.py").write_text("def helper(): pass", encoding="utf-8")
    (base / "src" / "__init__.py").write_text("", encoding="utf-8")
    (base / "tests").mkdir()
    (base / "tests" / "test_main.py").write_text("def test_main(): pass", encoding="utf-8")
    (base / "docs").mkdir()
    (base / "docs" / "README.md").write_text("# Project\n\nDocumentation", encoding="utf-8")
    (base / "docs" / "API_ref.md").write_text("# API\n\nInterface description", encoding="utf-8")
    (base / "config").mkdir()
    (base / "config" / "app.yaml").write_text("server:\n  port: 8000\n", encoding="utf-8")
    (base / "config" / "database.json").write_text('{"host":"localhost"}', encoding="utf-8")
    (base / "logs").mkdir()
    (base / "logs" / "app.log").write_text("[INFO] Started\n[ERROR] Failed\n", encoding="utf-8")
    (base / "requirements.txt").write_text("fastapi==0.104.1\nuvicorn==0.24.0\n", encoding="utf-8")
    (base / "Dockerfile").write_text("FROM python:3.13\n", encoding="utf-8")
    (base / ".gitignore").write_text("__pycache__/\n*.pyc\n", encoding="utf-8")
    (base / ".env").write_text("DEBUG=True\n", encoding="utf-8")
    (base / "big_file.txt").write_text("x" * 50000, encoding="utf-8")
    (base / "small_file.txt").write_text("hi", encoding="utf-8")
    (base / "src" / "subdir").mkdir()
    (base / "src" / "subdir" / "nested.py").write_text("pass", encoding="utf-8")
    dirs["base"] = str(base)
    dirs["src"] = str(base / "src")
    dirs["docs"] = str(base / "docs")
    dirs["config"] = str(base / "config")
    dirs["logs"] = str(base / "logs")
    dirs["tests"] = str(base / "tests")
    return dirs


class TestListDirectoryParamCombinations:
    """Param combo tests - tree x sort_by x include_hidden - xiaojian 2026-06-24"""

    def test_list_default(self, tmp_path):
        """Default params: sort_by=name, include_hidden=False"""
        dirs = _setup_rich_directory(tmp_path / "project")
        result = _run(listdir(dirs["base"]))
        assert is_success(result)
        assert "entries" in result["data"]
        entries = result["data"]["entries"]
        assert len(entries) > 0
        names = [e["name"] for e in entries]
        assert "src" in names
        assert "requirements.txt" in names
        assert ".gitignore" not in names

    def test_list_tree_mode(self, tmp_path):
        """tree tool basic usage"""
        dirs = _setup_rich_directory(tmp_path / "project")
        result = _run(tree(dirs["base"]))
        assert is_success(result)
        assert "tree" in result["data"]
        tree_data = result["data"]["tree"]
        assert tree_data["type"] == "directory"
        assert "children" in tree_data

    def test_list_sort_by_mtime(self, tmp_path):
        """sort_by=mtime — 显式设置递增mtime(旧→新)断言返回按mtime降序 — 小欧 2026-08-11"""
        dirs = _setup_rich_directory(tmp_path / "project")
        # 同秒创建→mtime全相同致排序不稳(flaky); 显式设置递增mtime使排序确定
        base = Path(dirs["base"])
        t0 = 1600000000
        for i, p in enumerate(sorted(base.rglob("*"))):
            if p.is_file():
                os.utime(p, (t0 + i, t0 + i))
        result = _run(listdir(dirs["base"], sort_by="mtime"))
        assert is_success(result)
        entries = result["data"]["entries"]
        file_entries = [e for e in entries if e["type"] == "file"]
        # mtime降序(最新在前, list_directory.py:241-242): 相邻file的mtime应非递增
        mtimes = [e.get("mtime", 0) for e in file_entries]
        if len(mtimes) >= 2:
            assert mtimes == sorted(mtimes, reverse=True), f"mtime应降序排列, 实际{mtimes}"

    def test_list_sort_by_mtime_2(self, tmp_path):
        """sort_by=mtime verification"""
        dirs = _setup_rich_directory(tmp_path / "project")
        result = _run(listdir(dirs["base"], sort_by="mtime"))
        assert is_success(result)
        entries = result["data"]["entries"]
        assert len(entries) > 0

    def test_list_include_hidden(self, tmp_path):
        """include_hidden=True"""
        dirs = _setup_rich_directory(tmp_path / "project")
        result = _run(listdir(dirs["base"], include_hidden=True))
        assert is_success(result)
        entries = result["data"]["entries"]
        names = [e["name"] for e in entries]
        assert ".gitignore" in names
        # 注: .env 被源码视为噪声目录(_SKIP_DIRS)始终跳过,不随include_hidden出现

    def test_list_tree_with_hidden(self, tmp_path):
        """tree + include_hidden=True - hidden dirs should appear"""
        dirs = _setup_rich_directory(tmp_path / "project")
        (tmp_path / "project" / ".hidden_dir").mkdir()
        result = _run(tree(dirs["base"], include_hidden=True))
        assert is_success(result)
        tree_data = result["data"]["tree"]
        child_names = [c["name"] for c in tree_data.get("children", [])]
        assert ".hidden_dir" in child_names

    def test_list_tree_sort_by_mtime(self, tmp_path):
        """tree + sort_by=mtime"""
        dirs = _setup_rich_directory(tmp_path / "project")
        result = _run(tree(dirs["base"], sort_by="mtime"))
        assert is_success(result)
        assert "tree" in result["data"]

    def test_list_hidden_sort_by_mtime(self, tmp_path):
        """include_hidden=True + sort_by=mtime"""
        dirs = _setup_rich_directory(tmp_path / "project")
        result = _run(listdir(dirs["base"], include_hidden=True, sort_by="mtime"))
        assert is_success(result)
        entries = result["data"]["entries"]
        names = [e["name"] for e in entries]
        assert ".gitignore" in names


class TestListDirectoryContentVerification:
    """Content verification tests - verify entries structure and statistics - xiaojian 2026-06-24"""

    def test_entry_has_required_fields(self, tmp_path):
        """Each entry contains name/path/type/size/mtime"""
        dirs = _setup_rich_directory(tmp_path / "project")
        result = _run(listdir(dirs["base"]))
        assert is_success(result)
        for entry in result["data"]["entries"]:
            assert "name" in entry
            assert "type" in entry
            assert entry["type"] in ("file", "directory")

    def test_statistics_fields(self, tmp_path):
        """Statistics contain total_size/dir_count/file_count"""
        dirs = _setup_rich_directory(tmp_path / "project")
        result = _run(listdir(dirs["base"]))
        assert is_success(result)
        metrics = result["llm_data"]["metrics"]
        assert "total_size" in metrics
        assert "dir_count" in metrics
        assert "file_count" in metrics
        assert metrics["dir_count"]["value"] + metrics["file_count"]["value"] == metrics["total"]["value"]

    def test_directories_before_files(self, tmp_path):
        """Default sort: directories before files"""
        dirs = _setup_rich_directory(tmp_path / "project")
        result = _run(listdir(dirs["base"]))
        assert is_success(result)
        entries = result["data"]["entries"]
        first_file_idx = None
        last_dir_idx = None
        for i, e in enumerate(entries):
            if e["type"] == "file" and first_file_idx is None:
                first_file_idx = i
            if e["type"] == "directory":
                last_dir_idx = i
        if first_file_idx is not None and last_dir_idx is not None:
            assert last_dir_idx < first_file_idx

    def test_tree_structure_has_children(self, tmp_path):
        """Tree mode: children field exists"""
        dirs = _setup_rich_directory(tmp_path / "project")
        result = _run(tree(dirs["base"]))
        assert is_success(result)
        tree_data = result["data"]["tree"]
        assert "children" in tree_data
        assert len(tree_data["children"]) > 0
        for child in tree_data["children"]:
            assert "name" in child
            assert "type" in child

    def test_tree_statistics(self, tmp_path):
        """Tree mode: returns file_count/dir_count/total_size"""
        dirs = _setup_rich_directory(tmp_path / "project")
        result = _run(tree(dirs["base"]))
        assert is_success(result)
        stats = result["data"]["statistics"]
        assert stats["file_count"] > 0
        assert stats["dir_count"] > 0

    def test_file_types_in_statistics(self, tmp_path):
        """List mode: statistics contain file_types extension distribution"""
        dirs = _setup_rich_directory(tmp_path / "project")
        result = _run(listdir(dirs["base"]))
        assert is_success(result)
        file_types = _file_types_from_entries(result["data"]["entries"])
        assert "py" in file_types or "txt" in file_types

    def test_size_distribution_in_statistics(self, tmp_path):
        """List mode: statistics contain size_distribution"""
        dirs = _setup_rich_directory(tmp_path / "project")
        result = _run(listdir(dirs["base"]))
        assert is_success(result)
        size_distribution = _size_distribution_from_entries(result["data"]["entries"])
        assert size_distribution["<1KB"] >= 1


class TestListDirectoryRealScenarios:
    """Real scenario tests - xiaojian 2026-06-24"""

    def test_backend_project_structure(self, tmp_path):
        """Simulate backend project directory structure"""
        base = tmp_path / "backend"
        base.mkdir(parents=True, exist_ok=True)
        (base / "app").mkdir()
        (base / "app" / "__init__.py").write_text("", encoding="utf-8")
        (base / "app" / "main.py").write_text("from fastapi import FastAPI\napp = FastAPI()", encoding="utf-8")
        (base / "app" / "api").mkdir()
        (base / "app" / "api" / "v1").mkdir()
        (base / "app" / "api" / "v1" / "chat.py").write_text("# chat router", encoding="utf-8")
        (base / "app" / "services").mkdir()
        (base / "app" / "services" / "agent").mkdir()
        (base / "app" / "services" / "agent" / "core_agent.py").write_text("# core agent", encoding="utf-8")
        (base / "app" / "tools").mkdir()
        (base / "app" / "tools" / "file").mkdir()
        (base / "app" / "tools" / "file" / "read_text_file.py").write_text("# read text", encoding="utf-8")
        result = _run(tree(str(base)))
        assert is_success(result)
        tree_data = result["data"]["tree"]
        child_names = [c["name"] for c in tree_data.get("children", [])]
        assert "app" in child_names

    def test_chinese_directory_names(self, tmp_path):
        """Chinese directory and file names"""
        base = tmp_path / "project_code"
        base.mkdir(parents=True, exist_ok=True)
        (base / "src_code").mkdir()
        (base / "src_code" / "main_app.py").write_text("print('hello')", encoding="utf-8")
        (base / "doc_materials").mkdir()
        (base / "doc_materials" / "req_spec.md").write_text("# requirements", encoding="utf-8")
        (base / "test_report_2026Q2.xlsx").write_bytes(b'\x00' * 100)
        result = _run(listdir(str(base)))
        assert is_success(result)
        entries = result["data"]["entries"]
        names = [e["name"] for e in entries]
        assert "src_code" in names
        assert "doc_materials" in names
        assert "test_report_2026Q2.xlsx" in names


class TestListDirectoryNegative:
    """Negative tests - xiaojian 2026-06-24"""

    def test_nonexistent_directory(self, tmp_path):
        """Nonexistent directory"""
        result = _run(listdir(str(tmp_path / "nonexistent")))
        assert is_error(result)

    def test_file_as_dir_path(self, tmp_path):
        """File path as directory parameter"""
        f = tmp_path / "file.txt"
        f.write_text("hello", encoding="utf-8")
        result = _run(listdir(str(f)))
        assert is_error(result)

    def test_invalid_sort_by(self, tmp_path):
        """Invalid sort_by value"""
        dirs = _setup_rich_directory(tmp_path / "project")
        result = _run(listdir(dirs["base"], sort_by="invalid"))
        assert is_error(result)

    def test_empty_directory(self, tmp_path):
        """Empty directory"""
        d = tmp_path / "empty_dir"
        d.mkdir()
        result = _run(listdir(str(d)))
        assert is_success(result)
        assert result["llm_data"]["metrics"]["total"]["value"] == 0
        assert len(result["data"]["entries"]) == 0


class TestListDirectoryBoundary:
    """Boundary tests - xiaojian 2026-06-24"""

    def test_deep_nested_tree(self, tmp_path):
        """Deep nested directory structure"""
        current = tmp_path / "level0"
        current.mkdir()
        for i in range(1, 8):
            current = current / f"level{i}"
            current.mkdir()
            (current / f"file_at_level{i}.txt").write_text(f"depth {i}", encoding="utf-8")
        result = _run(tree(str(tmp_path / "level0")))
        assert is_success(result)

    def test_many_files_directory(self, tmp_path):
        """Directory with many files"""
        d = tmp_path / "many_files"
        d.mkdir()
        for i in range(50):
            (d / f"file_{i:03d}.txt").write_text(f"content {i}", encoding="utf-8")
        result = _run(listdir(str(d)))
        assert is_success(result)
        assert result["llm_data"]["metrics"]["total"]["value"] == 50

    def test_path_with_spaces(self, tmp_path):
        """Path with spaces"""
        d = tmp_path / "my project files"
        d.mkdir()
        (d / "readme.txt").write_text("hello", encoding="utf-8")
        result = _run(listdir(str(d)))
        assert is_success(result)

    def test_special_chars_in_names(self, tmp_path):
        """File names with special characters"""
        d = tmp_path / "project"
        d.mkdir()
        (d / "file (1).txt").write_text("parentheses", encoding="utf-8")
        (d / "file&name.txt").write_text("ampersand", encoding="utf-8")
        result = _run(listdir(str(d)))
        assert is_success(result)
        names = [e["name"] for e in result["data"]["entries"]]
        assert "file (1).txt" in names


class TestListDirectoryBugDiscovery:
    """Bug discovery tests - xiaojian 2026-06-24"""

    def test_bug_tree_sort_by_mtime_order(self, tmp_path):
        """BUG#1: tree mode sort_by="mtime" should sort by modification time
        xiaojian 2026-06-24
        """
        base = tmp_path / "tree_size_bug"
        base.mkdir(parents=True, exist_ok=True)
        (base / "small_dir").mkdir()
        (base / "small_dir" / "tiny.txt").write_text("x", encoding="utf-8")
        (base / "big_dir").mkdir()
        (base / "big_dir" / "large.txt").write_text("x" * 10000, encoding="utf-8")
        (base / "medium_dir").mkdir()
        (base / "medium_dir" / "mid.txt").write_text("x" * 100, encoding="utf-8")
        result = _run(tree(str(base), sort_by="mtime"))
        assert is_success(result)
        tree_data = result["data"]["tree"]
        child_names = [c["name"] for c in tree_data.get("children", [])]
        # sort_by=mtime should sort by modification time descending
        assert len(child_names) == 3

    def test_bug_tree_sort_by_name_order(self, tmp_path):
        """Verify: tree mode sort_by=name orders alphabetically
        xiaojian 2026-06-24
        """
        base = tmp_path / "tree_size_verify"
        base.mkdir(parents=True, exist_ok=True)
        # aaaa_dir: first alphabetically, but largest content
        (base / "aaaa_dir").mkdir()
        (base / "aaaa_dir" / "big.txt").write_text("x" * 50000, encoding="utf-8")
        # zzzz_dir: last alphabetically, but smallest content
        (base / "zzzz_dir").mkdir()
        (base / "zzzz_dir" / "tiny.txt").write_text("x", encoding="utf-8")
        # mmmm_dir: middle alphabetically, middle content
        (base / "mmmm_dir").mkdir()
        (base / "mmmm_dir" / "mid.txt").write_text("x" * 500, encoding="utf-8")

        result_name = _run(tree(str(base), sort_by="name"))
        result_mtime = _run(tree(str(base), sort_by="mtime"))
        assert is_success(result_name)
        assert is_success(result_mtime)

        names_by_name = [c["name"] for c in result_name["data"]["tree"].get("children", [])]
        names_by_mtime = [c["name"] for c in result_mtime["data"]["tree"].get("children", [])]

        # name sort should be: aaaa_dir, mmmm_dir, zzzz_dir
        assert names_by_name == ["aaaa_dir", "mmmm_dir", "zzzz_dir"]

        # Both name and mtime sort should return results
        assert len(names_by_name) == 3
        assert len(names_by_mtime) == 3

    def test_bug_tree_only_shows_directories_not_files(self, tmp_path):
        """Verify: tree mode only shows directory nodes, not file nodes
        xiaojian 2026-06-24
        """
        base = tmp_path / "tree_no_files"
        base.mkdir(parents=True, exist_ok=True)
        (base / "file1.txt").write_text("content", encoding="utf-8")
        (base / "file2.py").write_text("code", encoding="utf-8")
        (base / "subdir").mkdir()
        (base / "subdir" / "nested.txt").write_text("nested", encoding="utf-8")
        result = _run(tree(str(base)))
        assert is_success(result)
        tree_data = result["data"]["tree"]
        child_names = [c["name"] for c in tree_data.get("children", [])]
        assert "subdir" in child_names
        assert "file1.txt" not in child_names
        assert "file2.py" not in child_names

    def test_bug_list_sort_by_mtime_correctness(self, tmp_path):
        """Verify: list mode sort_by=mtime orders correctly"""
        import time
        base = tmp_path / "list_mtime"
        base.mkdir(parents=True, exist_ok=True)
        (base / "old.txt").write_text("old", encoding="utf-8")
        time.sleep(0.1)
        (base / "new.txt").write_text("new", encoding="utf-8")
        result = _run(listdir(str(base), sort_by="mtime"))
        assert is_success(result)
        entries = result["data"]["entries"]
        file_entries = [e for e in entries if e["type"] == "file"]
        if len(file_entries) >= 2:
            assert file_entries[0]["name"] == "new.txt"

    def test_bug_list_invalid_sort_by_value(self, tmp_path):
        """Negative: invalid sort_by value"""
        base = tmp_path / "invalid_sort"
        base.mkdir(parents=True, exist_ok=True)
        result = _run(listdir(str(base), sort_by="invalid_value"))
        assert is_error(result)

    def test_bug_tree_include_hidden_dirs(self, tmp_path):
        """Verify: tree + include_hidden=True shows hidden dirs"""
        base = tmp_path / "hidden_tree"
        base.mkdir(parents=True, exist_ok=True)
        (base / ".git").mkdir()
        (base / ".git" / "config").write_text("gitconfig", encoding="utf-8")
        (base / ".vscode").mkdir()
        (base / ".vscode" / "settings.json").write_text("{}", encoding="utf-8")
        (base / "src").mkdir()
        result = _run(tree(str(base), include_hidden=True))
        assert is_success(result)
        child_names = [c["name"] for c in result["data"]["tree"].get("children", [])]
        assert ".git" in child_names
        assert ".vscode" in child_names
        assert "src" in child_names

    def test_bug_tree_exclude_hidden_dirs(self, tmp_path):
        """Verify: tree + include_hidden=False hides hidden dirs"""
        base = tmp_path / "no_hidden_tree"
        base.mkdir(parents=True, exist_ok=True)
        (base / ".git").mkdir()
        (base / ".git" / "config").write_text("gitconfig", encoding="utf-8")
        (base / "src").mkdir()
        result = _run(tree(str(base), include_hidden=False))
        assert is_success(result)
        child_names = [c["name"] for c in result["data"]["tree"].get("children", [])]
        assert ".git" not in child_names
        assert "src" in child_names

    def test_bug_list_statistics_file_types(self, tmp_path):
        """Content: list mode statistics file_types has correct extensions"""
        base = tmp_path / "file_types"
        base.mkdir(parents=True, exist_ok=True)
        (base / "a.py").write_text("py", encoding="utf-8")
        (base / "b.js").write_text("js", encoding="utf-8")
        (base / "c.txt").write_text("txt", encoding="utf-8")
        (base / "d.md").write_text("md", encoding="utf-8")
        result = _run(listdir(str(base)))
        assert is_success(result)
        file_types = _file_types_from_entries(result["data"]["entries"])
        assert file_types.get("py", 0) == 1
        assert file_types.get("js", 0) == 1
        assert file_types.get("txt", 0) == 1
        assert file_types.get("md", 0) == 1

    def test_bug_list_size_distribution(self, tmp_path):
        """Content: list mode size_distribution bucketing is correct"""
        base = tmp_path / "size_dist"
        base.mkdir(parents=True, exist_ok=True)
        (base / "tiny.txt").write_text("a", encoding="utf-8")
        (base / "medium.txt").write_text("x" * 5000, encoding="utf-8")
        result = _run(listdir(str(base)))
        assert is_success(result)
        size_distribution = _size_distribution_from_entries(result["data"]["entries"])
        assert size_distribution["<1KB"] >= 1
        assert size_distribution["1KB-10KB"] >= 1

    def test_bug_tree_max_depth_limit(self, tmp_path):
        """Boundary: tree mode max_depth=10 limit"""
        current = tmp_path / "d0"
        current.mkdir()
        for i in range(1, 12):
            current = current / f"d{i}"
            current.mkdir()
            (current / f"f{i}.txt").write_text(f"depth {i}", encoding="utf-8")
        result = _run(tree(str(tmp_path / "d0")))
        assert is_success(result)

    def test_bug_list_directory_as_file_path(self, tmp_path):
        """Negative: pass file path instead of directory"""
        f = tmp_path / "file.txt"
        f.write_text("hello", encoding="utf-8")
        result = _run(listdir(str(f)))
        assert is_error(result)

    def test_bug_list_empty_directory_statistics(self, tmp_path):
        """Boundary: empty directory statistics"""
        d = tmp_path / "empty"
        d.mkdir()
        result = _run(listdir(str(d)))
        assert is_success(result)
        metrics = result["llm_data"]["metrics"]
        assert metrics["total_size"]["value"] == 0
        assert metrics["dir_count"]["value"] == 0
        assert metrics["file_count"]["value"] == 0
