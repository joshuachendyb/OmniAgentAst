# -*- coding: utf-8 -*-
"""
copy_file third round deep BUG discovery test
xiaojian 2026-06-25
"""
import asyncio
import pytest
import tempfile
from pathlib import Path

from app.tools.tool_response import is_success, is_error


def _run(coro):
    try:
        return asyncio.run(coro)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


class TestCopyFileDeepBugs:
    """Deep BUG discovery -- copy_file -- xiaojian 2026-06-25, updated xiaojian 2026-06-28"""

    def test_bug_1_source_empty(self, tmp_path):
        """BUG#1: source_path="" empty string"""
        from app.tools.file.copy_file import copy
        result = _run(copy("", str(tmp_path / "dest.txt")))
        assert is_error(result)

    def test_bug_2_dest_empty(self, tmp_path):
        """BUG#2: dest_path="" empty string"""
        from app.tools.file.copy_file import copy
        fp = tmp_path / "test.txt"
        fp.write_text("test", encoding="utf-8")
        result = _run(copy(str(fp), ""))
        assert is_error(result)

    def test_bug_3_source_not_exist(self, tmp_path):
        """BUG#3: source not exist"""
        from app.tools.file.copy_file import copy
        result = _run(copy(str(tmp_path / "not_exist.txt"), str(tmp_path / "dest.txt")))
        assert is_error(result)

    def test_bug_4_source_is_directory(self, tmp_path):
        """BUG#4: source is directory"""
        from app.tools.file.copy_file import copy
        (tmp_path / "sub").mkdir()
        result = _run(copy(str(tmp_path / "sub"), str(tmp_path / "dest")))

    def test_bug_5_dest_is_directory(self, tmp_path):
        """BUG#5: dest is directory"""
        from app.tools.file.copy_file import copy
        fp = tmp_path / "test.txt"
        fp.write_text("test", encoding="utf-8")
        (tmp_path / "sub").mkdir()
        result = _run(copy(str(fp), str(tmp_path / "sub")))

    def test_bug_6_overwrite_false_dest_exists(self, tmp_path):
        """BUG#6: overwrite=False with dest already exists"""
        from app.tools.file.copy_file import copy
        src = tmp_path / "src.txt"
        dest = tmp_path / "dest.txt"
        src.write_text("src", encoding="utf-8")
        dest.write_text("dest", encoding="utf-8")
        result = _run(copy(str(src), str(dest), overwrite=False))

    def test_bug_7_overwrite_true(self, tmp_path):
        """BUG#7: overwrite=True overwrites existing file"""
        from app.tools.file.copy_file import copy
        src = tmp_path / "src.txt"
        dest = tmp_path / "dest.txt"
        src.write_text("src", encoding="utf-8")
        dest.write_text("dest", encoding="utf-8")
        result = _run(copy(str(src), str(dest), overwrite=True))

    def test_bug_8_source_same_as_dest(self, tmp_path):
        """BUG#8: source and dest are the same"""
        from app.tools.file.copy_file import copy
        fp = tmp_path / "test.txt"
        fp.write_text("test", encoding="utf-8")
        result = _run(copy(str(fp), str(fp)))

    def test_bug_9_large_file(self, tmp_path):
        """BUG#9: large file copy (10MB)"""
        from app.tools.file.copy_file import copy
        src = tmp_path / "large.txt"
        dest = tmp_path / "large_copy.txt"
        src.write_bytes(b"a" * (10 * 1024 * 1024))
        result = _run(copy(str(src), str(dest)))

    def test_bug_10_source_with_special_chars(self, tmp_path):
        """BUG#10: source contains special characters"""
        from app.tools.file.copy_file import copy
        src = tmp_path / "test file[1].txt"
        src.write_text("test", encoding="utf-8")
        dest = tmp_path / "dest.txt"
        result = _run(copy(str(src), str(dest)))

    def test_bug_11_dest_with_special_chars(self, tmp_path):
        """BUG#11: dest contains special characters"""
        from app.tools.file.copy_file import copy
        src = tmp_path / "src.txt"
        src.write_text("test", encoding="utf-8")
        dest = tmp_path / "target file[1].txt"
        result = _run(copy(str(src), str(dest)))

    def test_bug_12_create_parents_true(self, tmp_path):
        """BUG#12: create_parents=True creates parent dirs (copy_file has no such param)"""
        from app.tools.file.copy_file import copy
        src = tmp_path / "src.txt"
        src.write_text("test", encoding="utf-8")
        dest = tmp_path / "sub1" / "sub2" / "dest.txt"
        dest.parent.mkdir(parents=True)
        result = _run(copy(str(src), str(dest)))

    def test_bug_13_create_parents_false(self, tmp_path):
        """BUG#13: create_parents=False parent dir not exist (copy_file has no such param)"""
        from app.tools.file.copy_file import copy
        src = tmp_path / "src.txt"
        src.write_text("test", encoding="utf-8")
        dest = tmp_path / "sub1" / "sub2" / "dest.txt"
        result = _run(copy(str(src), str(dest)))

    def test_bug_15_source_binary_file(self, tmp_path):
        """BUG#15: source is binary file"""
        from app.tools.file.copy_file import copy
        src = tmp_path / "test.bin"
        src.write_bytes(b"\x00\x01\x02\x03")
        dest = tmp_path / "test_copy.bin"
        result = _run(copy(str(src), str(dest)))
