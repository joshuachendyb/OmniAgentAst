"""
file类工具集成测试 - 基于运行中的服务
小健 2026-05-21
"""
import pytest
import time
import os
import uuid
from pathlib import Path
from tests.integration._helper import ToolClient, assert_success, assert_error, assert_data_key, assert_data_not_empty, TEMP_DIR

TOOL = ToolClient()
WORK = str(TEMP_DIR / "file_test")


def _ensure_workdir():
    os.makedirs(WORK, exist_ok=True)


def _unique_name(prefix="f", ext="txt"):
    return f"{prefix}_{uuid.uuid4().hex[:8]}.{ext}"


class TestWriteTextFile:
    """write_text_file 多场景测试"""

    def test_write_new_file(self):
        _ensure_workdir()
        fp = os.path.join(WORK, "test_write.txt")
        r = TOOL.call("write_text_file", {"file_path": fp, "text": "hello world"})
        assert_success(r)
        assert os.path.exists(fp), f"文件应存在: {fp}"

    def test_write_with_chinese(self):
        _ensure_workdir()
        fp = os.path.join(WORK, "test_chinese.txt")
        r = TOOL.call("write_text_file", {"file_path": fp, "text": "你好世界"})
        assert_success(r)

    def test_write_append(self):
        _ensure_workdir()
        fp = os.path.join(WORK, "test_append.txt")
        TOOL.call("write_text_file", {"file_path": fp, "text": "line1\n"})
        r = TOOL.call("write_text_file", {"file_path": fp, "text": "line2\n", "append": True})
        assert_success(r)
        read_r = TOOL.call("read_file", {"file_paths": [fp]})
        content = str(read_r.get("data", ""))
        assert "line1" in content, "append后应保留原内容"
        assert "line2" in content, "append后应有新内容"

    def test_write_create_parents(self):
        _ensure_workdir()
        fp = os.path.join(WORK, "subdir", "nested", "test.txt")
        r = TOOL.call("write_text_file", {"file_path": fp, "text": "nested", "create_parents": True})
        assert_success(r)

    def test_write_empty_content(self):
        _ensure_workdir()
        fp = os.path.join(WORK, "test_empty.txt")
        r = TOOL.call("write_text_file", {"file_path": fp, "text": ""})
        assert_success(r)


class TestReadFile:
    """read_file 多场景测试"""

    def test_read_existing_file(self):
        _ensure_workdir()
        fp = os.path.join(WORK, "read_test.txt")
        TOOL.call("write_text_file", {"file_path": fp, "text": "read me"})
        r = TOOL.call("read_file", {"file_paths": [fp]})
        assert_success(r)

    def test_read_nonexistent_file(self):
        r = TOOL.call("read_file", {"file_paths": ["/nonexistent/path/xyz.txt"]})
        assert_error(r)

    def test_read_multiple_files(self):
        _ensure_workdir()
        fp1 = os.path.join(WORK, "multi1.txt")
        fp2 = os.path.join(WORK, "multi2.txt")
        TOOL.call("write_text_file", {"file_path": fp1, "text": "file1"})
        TOOL.call("write_text_file", {"file_path": fp2, "text": "file2"})
        r = TOOL.call("read_file", {"file_paths": [fp1, fp2]})
        assert_success(r)

    def test_read_with_head(self):
        _ensure_workdir()
        fp = os.path.join(WORK, "head_test.txt")
        content = "\n".join([f"line {i}" for i in range(100)])
        TOOL.call("write_text_file", {"file_path": fp, "text": content})
        r = TOOL.call("read_file", {"file_paths": [fp], "head": 10})
        assert_success(r)

    def test_read_with_tail(self):
        _ensure_workdir()
        fp = os.path.join(WORK, "tail_test.txt")
        content = "\n".join([f"line {i}" for i in range(100)])
        TOOL.call("write_text_file", {"file_path": fp, "text": content})
        r = TOOL.call("read_file", {"file_paths": [fp], "tail": 10})
        assert_success(r)


class TestEditFile:
    """edit_file 多场景测试"""

    def test_edit_replace(self):
        _ensure_workdir()
        fp = os.path.join(WORK, "edit_test.txt")
        TOOL.call("write_text_file", {"file_path": fp, "text": "hello old world"})
        r = TOOL.call("edit_file", {"file_path": fp, "old_string": "old", "new_string": "new"})
        assert_success(r)

    def test_edit_nonexistent_old_string(self):
        _ensure_workdir()
        fp = os.path.join(WORK, "edit_nofind.txt")
        TOOL.call("write_text_file", {"file_path": fp, "text": "hello world"})
        r = TOOL.call("edit_file", {"file_path": fp, "old_string": "not_found_text", "new_string": "x"})
        assert_error(r)

    def test_edit_nonexistent_file(self):
        r = TOOL.call("edit_file", {
            "file_path": "/nonexistent/file.txt",
            "old_string": "a",
            "new_string": "b",
        })
        assert_error(r)

    def test_edit_replace_all(self):
        _ensure_workdir()
        fp = os.path.join(WORK, "edit_all.txt")
        TOOL.call("write_text_file", {"file_path": fp, "text": "aaa bbb aaa"})
        r = TOOL.call("edit_file", {
            "file_path": fp,
            "old_string": "aaa",
            "new_string": "ccc",
            "replace_all": True,
        })
        assert_success(r)

    def test_edit_dry_run(self):
        _ensure_workdir()
        fp = os.path.join(WORK, "edit_dry.txt")
        TOOL.call("write_text_file", {"file_path": fp, "text": "hello world"})
        r = TOOL.call("edit_file", {
            "file_path": fp,
            "old_string": "hello",
            "new_string": "hi",
            "dry_run": True,
        })
        assert_success(r)


class TestListDirectory:
    """list_directory 多场景测试"""

    def test_list_current_dir(self):
        r = TOOL.call("list_directory", {"dir_path": WORK})
        assert_success(r)

    def test_list_nonexistent_dir(self):
        r = TOOL.call("list_directory", {"dir_path": "/nonexistent/xyz_dir"})
        assert_error(r)

    def test_list_recursive(self):
        _ensure_workdir()
        os.makedirs(os.path.join(WORK, "sub"), exist_ok=True)
        TOOL.call("write_text_file", {"file_path": os.path.join(WORK, "sub", "f.txt"), "text": "x"})
        r = TOOL.call("list_directory", {"dir_path": WORK, "recursive": True})
        assert_success(r)

    def test_list_with_format_tree(self):
        _ensure_workdir()
        r = TOOL.call("list_directory", {"dir_path": WORK, "format": "tree"})
        assert_success(r)


class TestSearchFiles:
    """search_files 多场景测试"""

    def test_search_by_pattern(self):
        _ensure_workdir()
        TOOL.call("write_text_file", {"file_path": os.path.join(WORK, "search_target.py"), "text": "pass"})
        r = TOOL.call("search_files", {"pattern": "*.py", "search_dir": WORK})
        assert_success(r)

    def test_search_nonexistent_dir(self):
        r = TOOL.call("search_files", {"pattern": "*.txt", "search_dir": "/nonexistent/xyz"})
        assert_error(r)

    def test_search_no_match(self):
        _ensure_workdir()
        r = TOOL.call("search_files", {"pattern": "*.xyz_ext_123", "search_dir": WORK})
        assert_success(r)


class TestGrepFileContent:
    """grep_file_content 多场景测试"""

    def test_grep_existing_content(self):
        _ensure_workdir()
        fp = os.path.join(WORK, "grep_test.txt")
        TOOL.call("write_text_file", {"file_path": fp, "text": "hello world\nfoo bar"})
        r = TOOL.call("grep_file_content", {"pattern": "hello", "search_dir": WORK})
        assert_success(r)

    def test_grep_no_match(self):
        _ensure_workdir()
        r = TOOL.call("grep_file_content", {"pattern": "xyz_no_match_12345", "search_dir": WORK})
        assert_success(r)

    def test_grep_with_glob(self):
        _ensure_workdir()
        TOOL.call("write_text_file", {"file_path": os.path.join(WORK, "grep_glob.py"), "text": "import os"})
        r = TOOL.call("grep_file_content", {"pattern": "import", "search_dir": WORK, "glob": "*.py"})
        assert_success(r)


class TestRenameFile:
    """rename_file 多场景测试"""

    def test_rename_single(self):
        _ensure_workdir()
        src_name = _unique_name("rn_src")
        dst_name = _unique_name("rn_dst")
        fp = os.path.join(WORK, src_name)
        TOOL.call("write_text_file", {"file_path": fp, "text": "rename me"})
        r = TOOL.call("rename_file", {
            "mode": "single",
            "file_path": fp,
            "new_name": dst_name,
        })
        assert_success(r)

    def test_rename_nonexistent(self):
        r = TOOL.call("rename_file", {
            "mode": "single",
            "file_path": "/nonexistent/xyz.txt",
            "new_name": "dst.txt",
        })
        assert_error(r)

    def test_rename_batch(self):
        _ensure_workdir()
        for i in range(3):
            fp = os.path.join(WORK, f"batch_{i}.txt")
            TOOL.call("write_text_file", {"file_path": fp, "text": f"batch {i}"})
        r = TOOL.call("rename_file", {
            "mode": "batch",
            "directory": WORK,
            "pattern": "batch_(\\d+)",
            "replacement": "renamed_\\1",
        })
        assert_success(r)


class TestFileOperation:
    """file_operation 多场景测试"""

    def test_copy(self):
        _ensure_workdir()
        src = os.path.join(WORK, _unique_name("cp_src"))
        dst = os.path.join(WORK, _unique_name("cp_dst"))
        TOOL.call("write_text_file", {"file_path": src, "text": "copy me"})
        r = TOOL.call("file_operation", {"action": "copy", "source": src, "destination": dst})
        assert_success(r)

    def test_move(self):
        _ensure_workdir()
        src = os.path.join(WORK, _unique_name("mv_src"))
        dst = os.path.join(WORK, _unique_name("mv_dst"))
        TOOL.call("write_text_file", {"file_path": src, "text": "move me"})
        r = TOOL.call("file_operation", {"action": "move", "source": src, "destination": dst})
        assert_success(r)

    def test_delete(self):
        _ensure_workdir()
        fp = os.path.join(WORK, "del_target.txt")
        TOOL.call("write_text_file", {"file_path": fp, "text": "delete me"})
        r = TOOL.call("file_operation", {"action": "delete", "source": fp})
        assert_success(r)

    def test_delete_nonexistent_idempotent(self):
        """file_operation delete对不存在的文件返回SUCCESS (幂等设计P16)"""
        r = TOOL.call("file_operation", {"action": "delete", "source": "/nonexistent/xyz.txt"})
        assert_success(r)


class TestArchiveTool:
    """archive_tool 多场景测试"""

    def test_compress_and_extract(self):
        _ensure_workdir()
        src_file = os.path.join(WORK, _unique_name("arch", "txt"))
        TOOL.call("write_text_file", {"file_path": src_file, "text": "archive me"})
        archive_path = os.path.join(WORK, _unique_name("test", "zip"))
        extract_dir = os.path.join(WORK, f"extracted_{uuid.uuid4().hex[:8]}")
        r1 = TOOL.call("archive_tool", {
            "action": "compress",
            "source": WORK,
            "destination": archive_path,
            "overwrite": True,
        })
        assert_success(r1)
        r2 = TOOL.call("archive_tool", {
            "action": "extract",
            "source": archive_path,
            "destination": extract_dir,
        })
        assert_success(r2)


class TestDataFileFormat:
    """data_file_format 多场景测试"""

    def test_read_json(self):
        _ensure_workdir()
        fp = os.path.join(WORK, "test.json")
        TOOL.call("write_text_file", {"file_path": fp, "text": '{"key": "value"}'})
        r = TOOL.call("data_file_format", {"file_path": fp, "action": "read"})
        assert_success(r)

    def test_write_json(self):
        _ensure_workdir()
        fp = os.path.join(WORK, "write_test.json")
        r = TOOL.call("data_file_format", {
            "file_path": fp,
            "action": "write",
            "format": "json",
            "data": {"hello": "world"},
        })
        assert_success(r)

    def test_read_yaml(self):
        _ensure_workdir()
        fp = os.path.join(WORK, "test.yaml")
        TOOL.call("write_text_file", {"file_path": fp, "text": "key: value\nlist:\n  - a\n  - b"})
        r = TOOL.call("data_file_format", {"file_path": fp, "action": "read"})
        assert_success(r)
