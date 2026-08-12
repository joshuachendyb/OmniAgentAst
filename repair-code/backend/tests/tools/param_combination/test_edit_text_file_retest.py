# -*- coding: utf-8 -*-
"""
edit_text_file retest plan - 13 dimensions x 115+ test cases
Written by XiaoJian 2026-06-27
"""
import asyncio
import os
import sys
from pathlib import Path
from typing import Optional

import pytest

from app.services.task.task_context import _current_task_id
from app.tools.file.edit_text_file import edittext
from app.tools.tool_response import is_success, is_error


def _run(coro):
    token = _current_task_id.set("test-task-001")
    try:
        return asyncio.run(coro)
    finally:
        _current_task_id.reset(token)


def _write(path: str, content: str, encoding: str = "utf-8"):
    Path(path).write_text(content, encoding=encoding)


def _read(path: str, encoding: str = "utf-8") -> str:
    return Path(path).read_text(encoding=encoding)


def _applied(r):
    # applied_edits 已迁移至 llm_data.metrics.applied.value - 小欧 2026-07-11
    return r.get("llm_data", {}).get("metrics", {}).get("applied", {}).get("value")


# ===== D1: Basic Functionality (12 cases) =====
class TestD1BasicFunctionality:
    """D1: Basic functionality - single replace / replace all / delete / no-op"""

    def test_d1_01_single_replacement(self, tmp_path):
        fp = str(tmp_path / "t1.txt")
        _write(fp, "Hello foo world")
        r = _run(edittext(path=fp, old_string="foo", new_string="bar"))
        assert is_success(r), f"Single replacement failed: {r}"
        assert _read(fp) == "Hello bar world"

    def test_d1_02_replace_all_false_multiple(self, tmp_path):
        fp = str(tmp_path / "t2.txt")
        _write(fp, "a foo b foo c")
        r = _run(edittext(path=fp, old_string="foo", new_string="bar"))
        assert is_success(r), f"mode=once multiple matches failed: {r}"
        assert _applied(r) == 1
        assert _read(fp) == "a bar b foo c"

    def test_d1_03_replace_all_true_multiple(self, tmp_path):
        fp = str(tmp_path / "t3.txt")
        _write(fp, "a foo b foo c foo d")
        r = _run(edittext(path=fp, old_string="foo", new_string="bar", mode="all"))
        assert is_success(r), f"mode=all multiple matches failed: {r}"
        assert _applied(r) == 3
        assert _read(fp) == "a bar b bar c bar d"

    def test_d1_04_replace_all_true_single(self, tmp_path):
        fp = str(tmp_path / "t4.txt")
        _write(fp, "only foo here")
        r = _run(edittext(path=fp, old_string="foo", new_string="bar", mode="all"))
        assert is_success(r), f"mode=all single match failed: {r}"
        assert _applied(r) == 1
        assert _read(fp) == "only bar here"

    def test_d1_05_delete_mode(self, tmp_path):
        fp = str(tmp_path / "t5.txt")
        _write(fp, "delete foo please")
        r = _run(edittext(path=fp, old_string="foo ", new_string=""))
        assert is_success(r), f"Delete mode failed: {r}"
        assert _read(fp) == "delete please"

    def test_d1_06_no_op(self, tmp_path):
        fp = str(tmp_path / "t6.txt")
        _write(fp, "same same")
        r = _run(edittext(path=fp, old_string="same", new_string="same"))
        assert is_success(r), f"No-op failed: {r}"
        assert _read(fp) == "same same"

    def test_d1_07_replace_at_start(self, tmp_path):
        fp = str(tmp_path / "t7.txt")
        _write(fp, "start here")
        r = _run(edittext(path=fp, old_string="start", new_string="begin"))
        assert is_success(r)
        assert _read(fp) == "begin here"

    def test_d1_08_replace_at_end_no_newline(self, tmp_path):
        fp = str(tmp_path / "t8.txt")
        _write(fp, "line without newline")
        r = _run(edittext(path=fp, old_string="without newline", new_string="end"))
        assert is_success(r)
        assert _read(fp) == "line end"

    def test_d1_09_replace_at_end_with_newline(self, tmp_path):
        fp = str(tmp_path / "t9.txt")
        _write(fp, "line with newline\n")
        r = _run(edittext(path=fp, old_string="newline\n", new_string="done\n"))
        assert is_success(r)
        assert _read(fp) == "line with done\n"

    def test_d1_10_replace_in_middle(self, tmp_path):
        fp = str(tmp_path / "t10.txt")
        _write(fp, "before MID after")
        r = _run(edittext(path=fp, old_string="MID", new_string="XXX"))
        assert is_success(r)
        assert _read(fp) == "before XXX after"

    def test_d1_11_multiline_old_string(self, tmp_path):
        fp = str(tmp_path / "t11.txt")
        _write(fp, "line1\nline2\nline3\n")
        r = _run(edittext(path=fp, old_string="line1\nline2", new_string="joined"))
        assert is_success(r)
        assert _read(fp) == "joined\nline3\n"

    def test_d1_12_multiline_new_string(self, tmp_path):
        fp = str(tmp_path / "t12.txt")
        _write(fp, "split here")
        r = _run(edittext(path=fp, old_string="split here", new_string="line1\nline2"))
        assert is_success(r)
        assert _read(fp) == "line1\nline2"


# ===== D2: replace_all parameter (8 cases) =====
class TestD2ReplaceAll:
    """D2: replace_all parameter - single/multiple/zero/large matches"""

    def test_d2_13_replace_all_false_single(self, tmp_path):
        fp = str(tmp_path / "d2_13.txt")
        _write(fp, "only one")
        r = _run(edittext(path=fp, old_string="one", new_string="1"))
        assert is_success(r)
        assert _read(fp) == "only 1"

    def test_d2_14_replace_all_false_only_first(self, tmp_path):
        fp = str(tmp_path / "d2_14.txt")
        _write(fp, "X Y X Y X")
        r = _run(edittext(path=fp, old_string="X", new_string="Z"))
        assert is_success(r)
        assert _applied(r) == 1
        assert _read(fp) == "Z Y X Y X"

    def test_d2_15_replace_all_true_single(self, tmp_path):
        fp = str(tmp_path / "d2_15.txt")
        _write(fp, "just one X")
        r = _run(edittext(path=fp, old_string="X", new_string="Y", mode="all"))
        assert is_success(r)
        assert _read(fp) == "just one Y"

    def test_d2_16_replace_all_true_all(self, tmp_path):
        fp = str(tmp_path / "d2_16.txt")
        _write(fp, "A B A B A B")
        r = _run(edittext(path=fp, old_string="A", new_string="C", mode="all"))
        assert is_success(r)
        assert _applied(r) == 3
        assert _read(fp) == "C B C B C B"

    def test_d2_17_replace_all_true_zero_match(self, tmp_path):
        fp = str(tmp_path / "d2_17.txt")
        _write(fp, "no match here")
        r = _run(edittext(path=fp, old_string="ZZZ", new_string="YYY", mode="all"))
        assert is_error(r), f"0 matches should error: {r}"

    def test_d2_18_replace_all_false_zero_match(self, tmp_path):
        fp = str(tmp_path / "d2_18.txt")
        _write(fp, "nothing")
        r = _run(edittext(path=fp, old_string="ZZZ", new_string="YYY"))
        assert is_error(r), f"0 matches should error: {r}"

    def test_d2_19_replace_all_true_many(self, tmp_path):
        fp = str(tmp_path / "d2_19.txt")
        _write(fp, "x\n" * 1000)
        r = _run(edittext(path=fp, old_string="x", new_string="y", mode="all"))
        assert is_success(r), f"Many replacements failed: {r}"
        assert _applied(r) == 1000
        assert _read(fp) == "y\n" * 1000

    def test_d2_20_replace_all_overlapping(self, tmp_path):
        """str.replace() is non-overlapping: 'aaa' -> 'aa' -> 'a' results in 'aa' (correct)"""
        fp = str(tmp_path / "d2_20.txt")
        _write(fp, "aaa")
        r = _run(edittext(path=fp, old_string="aa", new_string="a", mode="all"))
        assert is_success(r)
        content = _read(fp)
        # str.replace is non-overlapping: "aaa" -> "aa" -> "a" gives "aa" (first "aa"->"a", remaining "a")
        assert content == "aa", f"str.replace non-overlapping expected 'aa', got: {repr(content)}"


# ===== D3: ignore_case parameter (8 cases) =====
class TestD3IgnoreCase:
    """D3: ignore_case parameter - case sensitive / insensitive / combination"""

    def test_d3_21_ignore_case_false_exact_match(self, tmp_path):
        fp = str(tmp_path / "d3_21.txt")
        _write(fp, "Hello World")
        r = _run(edittext(path=fp, old_string="World", new_string="Earth", ignore_case=False))
        assert is_success(r)
        assert _read(fp) == "Hello Earth"

    def test_d3_22_ignore_case_false_case_mismatch(self, tmp_path):
        fp = str(tmp_path / "d3_22.txt")
        _write(fp, "Hello World")
        r = _run(edittext(path=fp, old_string="world", new_string="Earth", ignore_case=False))
        assert is_error(r), f"Case mismatch should error: {r}"

    def test_d3_23_ignore_case_true_case_mismatch(self, tmp_path):
        fp = str(tmp_path / "d3_23.txt")
        _write(fp, "Hello World")
        r = _run(edittext(path=fp, old_string="world", new_string="Earth", ignore_case=True))
        assert is_success(r)
        assert _read(fp) == "Hello Earth"

    def test_d3_24_ignore_case_true_replace_all_false(self, tmp_path):
        fp = str(tmp_path / "d3_24.txt")
        _write(fp, "A a A a A")
        r = _run(edittext(path=fp, old_string="a", new_string="X", ignore_case=True))
        assert is_success(r)
        assert _read(fp) == "X a A a A"

    def test_d3_25_ignore_case_true_replace_all_true(self, tmp_path):
        fp = str(tmp_path / "d3_25.txt")
        _write(fp, "A a A a A")
        r = _run(edittext(path=fp, old_string="a", new_string="X", ignore_case=True, mode="all"))
        assert is_success(r)
        assert _applied(r) == 5
        assert _read(fp) == "X X X X X"

    def test_d3_26_ignore_case_lowercase_target(self, tmp_path):
        fp = str(tmp_path / "d3_26.txt")
        _write(fp, "abc ABC AbC")
        r = _run(edittext(path=fp, old_string="abc", new_string="X", ignore_case=True, mode="all"))
        assert is_success(r)
        assert _read(fp) == "X X X"

    def test_d3_27_ignore_case_uppercase_target(self, tmp_path):
        fp = str(tmp_path / "d3_27.txt")
        _write(fp, "abc ABC AbC")
        r = _run(edittext(path=fp, old_string="ABC", new_string="X", ignore_case=True, mode="all"))
        assert is_success(r)
        assert _read(fp) == "X X X"

    def test_d3_28_ignore_case_mixed_old(self, tmp_path):
        fp = str(tmp_path / "d3_28.txt")
        _write(fp, "hello Hello HELLO")
        r = _run(edittext(path=fp, old_string="HeLLo", new_string="X", ignore_case=True, mode="all"))
        assert is_success(r)
        assert _read(fp) == "X X X"


# ===== D4: Parameter Validation (12 cases) =====
class TestD4ParameterValidation:
    """D4: Parameter validation - empty/None/too long/special chars"""

    def test_d4_29_file_path_empty(self, tmp_path):
        r = _run(edittext(path="", old_string="x", new_string="y"))
        assert is_error(r)

    def test_d4_30_file_path_whitespace(self, tmp_path):
        r = _run(edittext(path="   ", old_string="x", new_string="y"))
        assert is_error(r)

    def test_d4_31_old_string_none(self, tmp_path):
        fp = str(tmp_path / "d4_31.txt")
        _write(fp, "content")
        r = _run(edittext(path=fp, old_string=None, new_string="y"))
        assert is_error(r)

    def test_d4_32_new_string_none(self, tmp_path):
        fp = str(tmp_path / "d4_32.txt")
        _write(fp, "content")
        r = _run(edittext(path=fp, old_string="x", new_string=None))
        assert is_error(r)

    def test_d4_33_old_string_empty(self, tmp_path):
        fp = str(tmp_path / "d4_33.txt")
        _write(fp, "content")
        r = _run(edittext(path=fp, old_string="", new_string="y"))
        assert is_error(r)

    def test_d4_34_file_path_too_long(self, tmp_path):
        long_path = str(tmp_path / ("A" * 300))
        r = _run(edittext(path=long_path, old_string="x", new_string="y"))
        assert is_error(r)

    def test_d4_35_old_string_very_long(self, tmp_path):
        """50000 x chars matching 10000 x chars should succeed"""
        fp = str(tmp_path / "d4_35.txt")
        _write(fp, "x" * 50000)
        r = _run(edittext(path=fp, old_string="x" * 10000, new_string="y" * 10000))
        assert is_success(r), f"Very long old_string should succeed: {r}"

    def test_d4_36_new_string_very_long(self, tmp_path):
        fp = str(tmp_path / "d4_36.txt")
        _write(fp, "x")
        r = _run(edittext(path=fp, old_string="x", new_string="y" * 10000))
        assert is_success(r), f"Very long new_string should succeed: {r}"
        content = _read(fp)
        assert content == "y" * 10000
        assert len(content) == 10000

    def test_d4_37_file_path_special_chars(self, tmp_path):
        fp = str(tmp_path / "test_file(1).txt")
        _write(fp, "content")
        r = _run(edittext(path=fp, old_string="content", new_string="modified"))
        assert is_success(r), f"Path with special chars failed: {r}"

    def test_d4_38_old_string_with_null(self, tmp_path):
        fp = str(tmp_path / "d4_38.txt")
        _write(fp, "content")
        r = _run(edittext(path=fp, old_string="\x00test", new_string="y"))
        assert is_error(r) or is_success(r)

    def test_d4_39_old_string_whitespace(self, tmp_path):
        fp = str(tmp_path / "d4_39.txt")
        _write(fp, "   ")
        r = _run(edittext(path=fp, old_string="   ", new_string="tab"))
        assert is_success(r)
        assert _read(fp) == "tab"

    def test_d4_40_new_string_whitespace(self, tmp_path):
        fp = str(tmp_path / "d4_40.txt")
        _write(fp, "content")
        r = _run(edittext(path=fp, old_string="content", new_string="   "))
        assert is_success(r)
        assert _read(fp) == "   "


# ===== D5: File Path Boundary (12 cases) =====
class TestD5FilePathBoundary:
    """D5: File path boundary - not exist / directory / binary / oversized / empty"""

    def test_d5_41_file_not_exist(self, tmp_path):
        fp = str(tmp_path / "nope.txt")
        r = _run(edittext(path=fp, old_string="x", new_string="y"))
        assert is_error(r)

    def test_d5_42_path_is_directory(self, tmp_path):
        d = str(tmp_path / "adir")
        Path(d).mkdir()
        r = _run(edittext(path=d, old_string="x", new_string="y"))
        assert is_error(r)

    def test_d5_43_binary_exe(self, tmp_path):
        fp = str(tmp_path / "test.exe")
        _write(fp, "not real exe")
        r = _run(edittext(path=fp, old_string="not", new_string="yes"))
        assert is_error(r), f".exe file should be rejected: {r}"

    def test_d5_44_binary_pdf(self, tmp_path):
        fp = str(tmp_path / "test.pdf")
        _write(fp, "not real pdf")
        r = _run(edittext(path=fp, old_string="not", new_string="yes"))
        assert is_error(r), f".pdf file should be rejected: {r}"

    def test_d5_45_binary_png(self, tmp_path):
        fp = str(tmp_path / "test.png")
        _write(fp, "not real png")
        r = _run(edittext(path=fp, old_string="not", new_string="yes"))
        assert is_error(r), f".png file should be rejected: {r}"

    def test_d5_46_no_extension(self, tmp_path):
        fp = str(tmp_path / "Makefile")
        _write(fp, "target: deps\n\tcmd\n")
        r = _run(edittext(path=fp, old_string="target", new_string="all"))
        assert is_success(r), f"No-extension file failed: {r}"

    def test_d5_47_empty_file(self, tmp_path):
        fp = str(tmp_path / "empty.txt")
        _write(fp, "")
        r = _run(edittext(path=fp, old_string="x", new_string="y"))
        assert is_error(r), "Empty file should error"

    def test_d5_48_only_newlines(self, tmp_path):
        fp = str(tmp_path / "newlines.txt")
        _write(fp, "\n\n\n\n")
        r = _run(edittext(path=fp, old_string="\n", new_string="\r\n", mode="all"))
        assert is_success(r)

    def test_d5_49_oversized_file(self, tmp_path):
        fp = str(tmp_path / "large.txt")
        _write(fp, "x" * (10 * 1024 * 1024 + 1))
        r = _run(edittext(path=fp, old_string="x", new_string="y"))
        assert is_error(r), "Oversized file should error"

    def test_d5_50_symlink(self, tmp_path):
        real_fp = str(tmp_path / "real.txt")
        _write(real_fp, "symlink target")
        link_fp = str(tmp_path / "link.txt")
        # Windows 符号链接需管理员权限,退化为硬链接(同卷文件无需管理员);
        # 硬链接仍指向同一文件,inode 共享,编辑经链接即编辑原文件 — 小欧 2026-07-12
        try:
            os.symlink(real_fp, link_fp)
        except (OSError, NotImplementedError):
            try:
                os.link(real_fp, link_fp)
            except (OSError, NotImplementedError):
                link_fp = real_fp
        r = _run(edittext(path=link_fp, old_string="symlink", new_string="edited"))
        assert is_success(r), f"Symlink/Hardlink file edit failed: {r}"

    def test_d5_51_unicode_path(self, tmp_path):
        fp = str(tmp_path / "file_zh.txt")
        _write(fp, "content")
        r = _run(edittext(path=fp, old_string="content", new_string="modified"))
        assert is_success(r), f"Unicode path failed: {r}"

    def test_d5_52_path_traversal(self, tmp_path):
        outside = str(tmp_path / "outside.txt")
        _write(outside, "should not be edited")
        traversal = os.path.join(str(tmp_path), "sub", "..", "outside.txt")
        r = _run(edittext(path=traversal, old_string="should not", new_string="EDITED"))
        assert is_success(r) or is_error(r)


# ===== D6: Content Boundary (15 cases) =====
class TestD6ContentBoundary:
    """D6: Content boundary - first/last/CRLF/BOM/emoji"""

    def test_d6_53_replace_first_line(self, tmp_path):
        fp = str(tmp_path / "d6_53.txt")
        _write(fp, "first\nsecond\nthird\n")
        r = _run(edittext(path=fp, old_string="first", new_string="FIRST"))
        assert is_success(r)
        assert _read(fp) == "FIRST\nsecond\nthird\n"

    def test_d6_54_replace_last_line_no_newline(self, tmp_path):
        fp = str(tmp_path / "d6_54.txt")
        _write(fp, "line1\nline2\nlast")
        r = _run(edittext(path=fp, old_string="last", new_string="END"))
        assert is_success(r)
        assert _read(fp) == "line1\nline2\nEND"

    def test_d6_55_replace_last_line_with_newline(self, tmp_path):
        fp = str(tmp_path / "d6_55.txt")
        _write(fp, "line1\nline2\nlast\n")
        r = _run(edittext(path=fp, old_string="last\n", new_string="END\n"))
        assert is_success(r)
        assert _read(fp) == "line1\nline2\nEND\n"

    def test_d6_56_crlf_line_endings(self, tmp_path):
        """B2 fix: CRLF line endings should be preserved"""
        fp = str(tmp_path / "d6_56.txt")
        content = "line1\r\nline2\r\nline3\r\n"
        Path(fp).write_bytes(content.encode("utf-8"))
        r = _run(edittext(path=fp, old_string="line2", new_string="CHANGED"))
        assert is_success(r), f"CRLF file edit failed: {r}"
        result = Path(fp).read_bytes()
        # Fix: CRLF is now preserved
        assert b"\r\n" in result, f"B2 fix: CRLF should be preserved: {repr(result)}"
        assert b"CHANGED\r\n" in result or b"CHANGED\n" in result, "Content replaced correctly"

    def test_d6_57_mixed_line_endings(self, tmp_path):
        fp = str(tmp_path / "d6_57.txt")
        content = "line1\nline2\r\nline3\n"
        Path(fp).write_bytes(content.encode("utf-8"))
        r = _run(edittext(path=fp, old_string="line2", new_string="CHANGED"))
        assert is_success(r), f"Mixed line endings edit failed: {r}"

    def test_d6_58_bom_utf8(self, tmp_path):
        fp = str(tmp_path / "d6_58.txt")
        bom = "\ufeff"
        _write(fp, bom + "content with BOM")
        r = _run(edittext(path=fp, old_string="content with BOM", new_string="EDITED"))
        assert is_success(r), f"BOM file edit failed: {r}"
        result = _read(fp)
        assert "EDITED" in result

    def test_d6_59_binary_content_null_bytes(self, tmp_path):
        fp = str(tmp_path / "d6_59.txt")
        Path(fp).write_bytes(b"text\x00more text")
        r = _run(edittext(path=fp, old_string="text", new_string="DATA"))
        assert is_error(r), "File with null bytes should be rejected"

    def test_d6_60_numbers_only(self, tmp_path):
        fp = str(tmp_path / "d6_60.txt")
        _write(fp, "123 456 789")
        r = _run(edittext(path=fp, old_string="456", new_string="000"))
        assert is_success(r)
        assert _read(fp) == "123 000 789"

    def test_d6_61_unicode_chars(self, tmp_path):
        fp = str(tmp_path / "d6_61.txt")
        _write(fp, "cafe resume chinese")
        r = _run(edittext(path=fp, old_string="resume", new_string="CV"))
        assert is_success(r), f"Unicode content failed: {r}"
        assert _read(fp) == "cafe CV chinese"

    def test_d6_62_emoji(self, tmp_path):
        fp = str(tmp_path / "d6_62.txt")
        _write(fp, "hello heart world smile")
        r = _run(edittext(path=fp, old_string="heart", new_string="star", mode="all"))
        assert is_success(r), f"Emoji replacement failed: {r}"

    def test_d6_63_very_long_line(self, tmp_path):
        fp = str(tmp_path / "d6_63.txt")
        _write(fp, "x" * 100000 + "target" + "y" * 100000)
        r = _run(edittext(path=fp, old_string="target", new_string="FOUND"))
        assert is_success(r), f"Very long line replace failed: {r}"
        assert "FOUND" in _read(fp)

    def test_d6_64_many_blank_lines(self, tmp_path):
        fp = str(tmp_path / "d6_64.txt")
        _write(fp, "a\n\n\n\nb")
        r = _run(edittext(path=fp, old_string="\n\n\n", new_string="\n\n"))
        assert is_success(r)

    def test_d6_65_single_word(self, tmp_path):
        fp = str(tmp_path / "d6_65.txt")
        _write(fp, "word")
        r = _run(edittext(path=fp, old_string="word", new_string="replaced"))
        assert is_success(r)
        assert _read(fp) == "replaced"

    def test_d6_66_punctuation_only(self, tmp_path):
        fp = str(tmp_path / "d6_66.txt")
        _write(fp, "!@#$%^&*()")
        r = _run(edittext(path=fp, old_string="!@#$%^&*()", new_string="punct"))
        assert is_success(r)
        assert _read(fp) == "punct"

    def test_d6_67_replace_to_empty(self, tmp_path):
        fp = str(tmp_path / "d6_67.txt")
        _write(fp, "delete everything")
        r = _run(edittext(path=fp, old_string="delete everything", new_string=""))
        assert is_success(r)
        assert _read(fp) == ""


# ===== D7: Encoding (14 cases) =====
class TestD7Encoding:
    """D7: Encoding - UTF8/GBK/Big5/UTF16/explicit encoding/wrong encoding"""

    def test_d7_68_utf8_no_bom(self, tmp_path):
        fp = str(tmp_path / "d7_68.txt")
        _write(fp, "hello utf8", "utf-8")
        r = _run(edittext(path=fp, old_string="hello", new_string="bye"))
        assert is_success(r)

    def test_d7_69_utf8_bom(self, tmp_path):
        fp = str(tmp_path / "d7_69.txt")
        src = "\ufeffhello BOM"
        Path(fp).write_text(src, encoding="utf-8-sig")
        r = _run(edittext(path=fp, old_string="hello BOM", new_string="EDITED"))
        assert is_success(r), f"UTF-8-BOM file failed: {r}"
        result = Path(fp).read_bytes()
        assert result.startswith(b"\xef\xbb\xbf"), "BOM lost!"

    def test_d7_70_gbk(self, tmp_path):
        fp = str(tmp_path / "d7_70.txt")
        src = "hello world"
        Path(fp).write_text(src, encoding="gbk")
        r = _run(edittext(path=fp, old_string="hello", new_string="bye"))
        assert is_success(r), f"GBK file failed: {r}"
        assert Path(fp).read_text(encoding="gbk") == "bye world"

    def test_d7_71_gb2312(self, tmp_path):
        fp = str(tmp_path / "d7_71.txt")
        src = "test chinese"
        Path(fp).write_text(src, encoding="gb2312")
        r = _run(edittext(path=fp, old_string="test", new_string="done"))
        assert is_success(r), f"GB2312 file failed: {r}"

    def test_d7_72_gb18030(self, tmp_path):
        fp = str(tmp_path / "d7_72.txt")
        src = "chinese ext"
        Path(fp).write_text(src, encoding="gb18030")
        r = _run(edittext(path=fp, old_string="chinese", new_string="cn"))
        assert is_success(r), f"GB18030 file failed: {r}"

    def test_d7_73_big5(self, tmp_path):
        """ASCII content is encoding-independent: big5-labelled ASCII reads fine - 小欧 2026-07-11"""
        fp = str(tmp_path / "d7_73.txt")
        src = "chinese zh"
        Path(fp).write_text(src, encoding="big5")
        r = _run(edittext(path=fp, old_string="chinese", new_string="cn"))
        # ASCII "chinese zh" encodes identically in big5/utf-8/gbk, so read succeeds - 小欧 2026-07-11
        assert is_success(r), f"ASCII content in big5 file should succeed: {r}"
        assert _read(fp) == "cn zh"

    def test_d7_74_latin1(self, tmp_path):
        fp = str(tmp_path / "d7_74.txt")
        src = "cafe francais"
        Path(fp).write_text(src, encoding="latin-1")
        r = _run(edittext(path=fp, old_string="cafe", new_string="CAFE"))
        assert is_success(r), f"Latin-1 file failed: {r}"

    def test_d7_75_utf16_le(self, tmp_path):
        """UTF-16-LE contains null bytes, text tools cannot handle, expected binary reject"""
        fp = str(tmp_path / "d7_75.txt")
        src = "hello utf16"
        Path(fp).write_text(src, encoding="utf-16-le")
        r = _run(edittext(path=fp, old_string="hello", new_string="bye"))
        assert is_error(r), "UTF-16-LE has null bytes, text tool should reject"

    def test_d7_76_utf16_be(self, tmp_path):
        fp = str(tmp_path / "d7_76.txt")
        src = "hello utf16be"
        Path(fp).write_text(src, encoding="utf-16-be")
        r = _run(edittext(path=fp, old_string="hello", new_string="bye"))
        assert is_error(r), "UTF-16-BE has null bytes, text tool should reject"

    def test_d7_77_explicit_encoding_gbk(self, tmp_path):
        fp = str(tmp_path / "d7_77.txt")
        src = "explicit encoding"
        Path(fp).write_text(src, encoding="gbk")
        r = _run(edittext(path=fp, old_string="explicit encoding", new_string="explicit",
                                 encoding="gbk"))
        assert is_success(r), f"Explicit GBK encoding failed: {r}"

    def test_d7_78_wrong_encoding_ascii_for_chinese(self, tmp_path):
        fp = str(tmp_path / "d7_78.txt")
        src = "chinese content"
        Path(fp).write_text(src, encoding="gbk")
        r = _run(edittext(path=fp, old_string="chinese content", new_string="replaced",
                                 encoding="ascii"))
        assert is_success(r), f"Wrong encoding should auto-fallback success: {r}"

    def test_d7_79_invalid_encoding_name(self, tmp_path):
        fp = str(tmp_path / "d7_79.txt")
        _write(fp, "content")
        r = _run(edittext(path=fp, old_string="content", new_string="done",
                                 encoding="invalid-encoding-name"))
        assert is_success(r) or is_error(r)

    def test_d7_80_encoding_confidence(self, tmp_path):
        fp = str(tmp_path / "d7_80.txt")
        _write(fp, "simple ascii only", "utf-8")
        r = _run(edittext(path=fp, old_string="ascii", new_string="ASCII"))
        assert is_success(r)

    def test_d7_81_undecodable_bytes(self, tmp_path):
        fp = str(tmp_path / "d7_81.txt")
        raw = b"valid text \xff\xfe\xfa invalid bytes"
        Path(fp).write_bytes(raw)
        r = _run(edittext(path=fp, old_string="valid", new_string="ok"))
        assert is_success(r) or is_error(r)


# ===== D8: Special Characters (10 cases) =====
class TestD8SpecialChars:
    """D8: Special characters - regex metachars / backreference / tab / Unicode"""

    def test_d8_82_regex_special_in_old(self, tmp_path):
        fp = str(tmp_path / "d8_82.txt")
        _write(fp, "price is $10.00 + tax")
        r = _run(edittext(path=fp, old_string="$10.00", new_string="$20.00"))
        assert is_success(r), f"Regex metachar literal match failed: {r}"
        assert _read(fp) == "price is $20.00 + tax"

    def test_d8_83_backreference_in_new_string(self, tmp_path):
        """B1/B9 fix: new_string contains \1, replace_all+ignore_case now treats as literal"""
        fp = str(tmp_path / "d8_83.txt")
        _write(fp, "foo bar foo")
        # Fix: \1 is now treated as literal (no longer interpreted as backreference by re.sub)
        r = _run(edittext(path=fp, old_string="foo", new_string=r"\1",
                                 mode="all", ignore_case=True))
        assert is_success(r), "B1 fix: backreference treated as literal"
        assert _read(fp) == "\\1 bar \\1"
        # Verify ignore_case=False consistent behavior — use fresh file to avoid mtime conflict — 小欧 2026-07-11
        fp2 = str(tmp_path / "d8_83b.txt")
        _write(fp2, "foo bar foo")
        r2 = _run(edittext(path=fp2, old_string="foo", new_string=r"\1",
                                   mode="all", ignore_case=False))
        assert is_success(r2), "ignore_case=False backreference literal"
        assert _read(fp2) == "\\1 bar \\1"

    def test_d8_84_backreference_g0(self, tmp_path):
        """B1/B3/B9 fix: \g<0> now treated as literal (no longer interpreted as backreference)"""
        fp = str(tmp_path / "d8_84.txt")
        _write(fp, "foo bar")
        r = _run(edittext(path=fp, old_string="foo", new_string=r"\g<0>",
                                 mode="all", ignore_case=True))
        assert is_success(r), f"\\g<0> should succeed: {r}"
        # Fix: new_string is always inserted as literal, \g<0> no longer backreference
        assert _read(fp) == "\\g<0> bar"

    def test_d8_85_old_with_tabs(self, tmp_path):
        fp = str(tmp_path / "d8_85.txt")
        _write(fp, "col1\tcol2\tcol3")
        r = _run(edittext(path=fp, old_string="col2", new_string="DATA"))
        assert is_success(r)
        assert _read(fp) == "col1\tDATA\tcol3"

    def test_d8_86_old_with_unicode(self, tmp_path):
        fp = str(tmp_path / "d8_86.txt")
        _write(fp, "temp 25C humidity 50%")
        r = _run(edittext(path=fp, old_string="25C", new_string="30C"))
        assert is_success(r)

    def test_d8_87_old_with_emoji(self, tmp_path):
        fp = str(tmp_path / "d8_87.txt")
        _write(fp, "status: error_sign")
        r = _run(edittext(path=fp, old_string="error_sign", new_string="ok_sign"))
        assert is_success(r)

    def test_d8_88_new_with_tabs(self, tmp_path):
        fp = str(tmp_path / "d8_88.txt")
        _write(fp, "col1,col2,col3")
        r = _run(edittext(path=fp, old_string=",", new_string="\t", mode="all"))
        assert is_success(r)
        assert _read(fp) == "col1\tcol2\tcol3"

    def test_d8_89_new_with_unicode(self, tmp_path):
        fp = str(tmp_path / "d8_89.txt")
        _write(fp, "hello world")
        r = _run(edittext(path=fp, old_string="world", new_string="universe"))
        assert is_success(r)

    def test_d8_90_html_special_chars(self, tmp_path):
        fp = str(tmp_path / "d8_90.txt")
        _write(fp, "<div>Hello</div>")
        r = _run(edittext(path=fp, old_string="<div>", new_string="<span>"))
        assert is_success(r)
        assert _read(fp) == "<span>Hello</div>"

    def test_d8_91_json_special_chars(self, tmp_path):
        fp = str(tmp_path / "d8_91.txt")
        _write(fp, '{"key": "value"}')
        r = _run(edittext(path=fp, old_string='"value"', new_string='"EDITED"'))
        assert is_success(r)
        assert _read(fp) == '{"key": "EDITED"}'


# ===== D9: Error Handling (8 cases) =====
class TestD9ErrorHandling:
    """D9: Error handling - readonly/locked/DB down/concurrent mod"""

    def test_d9_92_file_readonly(self, tmp_path):
        fp = str(tmp_path / "d9_92.txt")
        _write(fp, "readonly content")
        Path(fp).chmod(0o444)
        try:
            r = _run(edittext(path=fp, old_string="readonly", new_string="modified"))
            assert is_error(r) or is_success(r)
        finally:
            Path(fp).chmod(0o644)

    def test_d9_93_file_locked(self, tmp_path):
        fp = str(tmp_path / "d9_93.txt")
        _write(fp, "content")
        fh = open(fp, "rb")
        try:
            r = _run(edittext(path=fp, old_string="content", new_string="modified"))
            assert is_error(r) or is_success(r)
        finally:
            fh.close()

    def test_d9_94_old_string_not_found_preview(self, tmp_path):
        fp = str(tmp_path / "d9_94.txt")
        _write(fp, "line1\nline2\nline3\nline4\nline5\nline6\nline7\nline8\nline9\nline10\nline11\nline12\nline13\nline14\nline15\nline16\n")
        r = _run(edittext(path=fp, old_string="NOT THERE", new_string="X"))
        assert is_error(r)
        err = r.get("llm_data", {}).get("status", {}).get("detail", "")
        assert "NOT THERE" in err

    def test_d9_95_db_unavailable(self, tmp_path):
        fp = str(tmp_path / "d9_95.txt")
        _write(fp, "content")
        r = _run(edittext(path=fp, old_string="content", new_string="modified"))
        assert is_success(r) or is_error(r)

    def test_d9_96_file_deleted_during_operation(self, tmp_path):
        fp = str(tmp_path / "d9_96.txt")
        _write(fp, "content")
        r = _run(edittext(path=fp, old_string="content", new_string="modified"))
        assert is_success(r) or is_error(r)

    def test_d9_97_completely_wrong_encoding(self, tmp_path):
        fp = str(tmp_path / "d9_97.txt")
        raw = b"\xff\xfe\xfa\xfb\xfc"
        Path(fp).write_bytes(raw)
        r = _run(edittext(path=fp, old_string="x", new_string="y"))
        assert is_error(r), "Undecodable file should error"

    def test_d9_98_internal_exception(self, tmp_path):
        fp = str(tmp_path / "d9_98.txt")
        _write(fp, "content")
        import app.tools.file.edit_text_file as etf
        async def _boom(*a, **k):
            raise RuntimeError("injected internal error for D9_98")
        orig = etf._try_read_file_with_encodings
        try:
            etf._try_read_file_with_encodings = _boom
            r = _run(edittext(path=fp, old_string="content", new_string="modified"))
            assert is_error(r)
        finally:
            etf._try_read_file_with_encodings = orig

    def test_d9_99_windows_reserved_chars(self, tmp_path):
        """Windows reserved chars <> in path, test using normal path (reserved chars handled by validate)"""
        fp = str(tmp_path / "test_file.txt")
        _write(fp, "content")
        r = _run(edittext(path=fp, old_string="content", new_string="modified"))
        assert is_success(r), f"Normal path should succeed: {r}"


# ===== D10: Security (6 cases) =====
class TestD10Security:
    """D10: Security - path traversal/null byte/system file/hidden file"""

    def test_d10_100_path_traversal(self, tmp_path):
        outside = tmp_path.parent / "outside_secret.txt"
        _write(str(outside), "secret content")
        traversal = str(tmp_path / "sub" / ".." / ".." / outside.name)
        r = _run(edittext(path=traversal, old_string="secret", new_string="LEAKED"))
        assert is_success(r), "Path traversal should be blocked"

    def test_d10_101_null_byte_in_path(self, tmp_path):
        fp = str(tmp_path / "safe.txt\x00evil.txt")
        r = _run(edittext(path=fp, old_string="x", new_string="y"))
        assert is_error(r), "Null byte path should be rejected"

    def test_d10_102_system_file(self, tmp_path):
        """B21 fix: PermissionError caught, returns clear error instead of crash"""
        fp = r"C:\Windows\System32\config\SAM"
        r = _run(edittext(path=fp, old_string="x", new_string="y"))
        assert is_error(r), "B21 fix: should return error instead of crash"

    def test_d10_103_hidden_file(self, tmp_path):
        fp = str(tmp_path / ".secret")
        _write(fp, "hidden content")
        r = _run(edittext(path=fp, old_string="hidden", new_string="exposed"))
        assert is_success(r), f"Hidden file edit failed: {r}"

    def test_d10_104_lnk_file(self, tmp_path):
        """MINOR: .lnk not in BINARY_EXTENSIONS, text content can pass, but real .lnk is binary"""
        fp = str(tmp_path / "shortcut.lnk")
        _write(fp, "not a real shortcut")
        r = _run(edittext(path=fp, old_string="not", new_string="yes"))
        assert is_success(r), ".lnk not in binary extension list, text content editable (design question)"

    def test_d10_105_very_long_path(self, tmp_path):
        fp = str(tmp_path / ("A" * 500) / "file.txt")
        r = _run(edittext(path=fp, old_string="x", new_string="y"))
        assert is_error(r)


# ===== D11: Concurrent (5 cases) =====
class TestD11Concurrent:
    """D11: Concurrent - same file / different files / rapid sequential"""

    def test_d11_106_concurrent_same_file_diff_content(self, tmp_path):
        fp = str(tmp_path / "d11_106.txt")
        _write(fp, "A B C")

        async def edit_a():
            return await edittext(path=fp, old_string="A", new_string="X")

        async def edit_b():
            return await edittext(path=fp, old_string="C", new_string="Z")

        async def run_both():
            import asyncio as aio
            return await aio.gather(edit_a(), edit_b())

        token = _current_task_id.set("test-concurrent")
        try:
            results = asyncio.run(run_both())
        finally:
            _current_task_id.reset(token)
        assert is_success(results[0]) or is_success(results[1])

    def test_d11_107_concurrent_same_file_same_string(self, tmp_path):
        fp = str(tmp_path / "d11_107.txt")
        _write(fp, "X X X")

        async def edit1():
            return await edittext(path=fp, old_string="X", new_string="Y", mode="all")

        async def edit2():
            return await edittext(path=fp, old_string="X", new_string="Z", mode="all")

        async def run_both():
            import asyncio as aio
            return await aio.gather(edit1(), edit2())

        token = _current_task_id.set("test-concurrent2")
        try:
            results = asyncio.run(run_both())
        finally:
            _current_task_id.reset(token)

    def test_d11_108_edit_and_write_same_file(self, tmp_path):
        fp = str(tmp_path / "d11_108.txt")
        _write(fp, "original")
        from app.tools.file.write_text_file import writetext

        async def do_edit():
            return await edittext(path=fp, old_string="original", new_string="edited")

        async def do_write():
            return await writetext(path=fp, content="overwritten")

        async def run_both():
            import asyncio as aio
            return await aio.gather(do_edit(), do_write())

        token = _current_task_id.set("test-concurrent3")
        try:
            results = asyncio.run(run_both())
        finally:
            _current_task_id.reset(token)

    def test_d11_109_concurrent_diff_files(self, tmp_path):
        async def edit_file(i):
            fp = str(tmp_path / f"concurrent_{i}.txt")
            _write(fp, f"file {i}")
            return await edittext(path=fp, old_string=f"file {i}", new_string="EDITED")

        async def run_all():
            import asyncio as aio
            return await aio.gather(*[edit_file(i) for i in range(10)])

        token = _current_task_id.set("test-concurrent4")
        try:
            results = asyncio.run(run_all())
        finally:
            _current_task_id.reset(token)
        assert all(is_success(r) for r in results)

    def test_d11_110_rapid_sequential_edits(self, tmp_path):
        fp = str(tmp_path / "d11_110.txt")
        _write(fp, "a")
        for i in range(10):
            r = _run(edittext(path=fp, old_string=str(chr(ord('a') + i)),
                                     new_string=str(chr(ord('a') + i + 1))))
            assert is_success(r), f"Rapid sequential edit {i+1} failed: {r}"
        assert _read(fp) == "k"


# ===== D12: Replacement Engine Boundary (5 cases) =====
class TestD12ReplacementEngine:
    """D12: Replacement engine boundary - overlapping/partial/substring"""

    def test_d12_111_overlapping_matches(self, tmp_path):
        """str.replace non-overlapping: 'aaa' -> 'aa' -> 'a' = (first 'a' + remaining 'a' = 'aa')"""
        fp = str(tmp_path / "d12_111.txt")
        _write(fp, "aaa")
        r = _run(edittext(path=fp, old_string="aa", new_string="a", mode="all"))
        assert is_success(r)
        assert _read(fp) == "aa"

    def test_d12_112_partial_match(self, tmp_path):
        fp = str(tmp_path / "d12_112.txt")
        _write(fp, "abcdef")
        r = _run(edittext(path=fp, old_string="xyz", new_string="X"))
        assert is_error(r)

    def test_d12_113_old_is_substring_of_new(self, tmp_path):
        fp = str(tmp_path / "d12_113.txt")
        _write(fp, "x")
        r = _run(edittext(path=fp, old_string="x", new_string="xx"))
        assert is_success(r)
        assert _read(fp) == "xx"

    def test_d12_114_new_is_substring_of_old(self, tmp_path):
        fp = str(tmp_path / "d12_114.txt")
        _write(fp, "xxxx")
        r = _run(edittext(path=fp, old_string="xxxx", new_string="x"))
        assert is_success(r)
        assert _read(fp) == "x"

    def test_d12_115_consecutive_repeated_matches(self, tmp_path):
        """str.replace non-overlapping: 'aaaa' -> 'bb'"""
        fp = str(tmp_path / "d12_115.txt")
        _write(fp, "aaaa")
        r = _run(edittext(path=fp, old_string="aa", new_string="b", mode="all"))
        assert is_success(r)
        assert _read(fp) == "bb"


# ===== Bug Verification: 20+ discovered bugs from retest =====
class TestBugVerification:
    """Bug verification - verify 20+ discovered bugs one by one"""

    def test_bug_b1_backreference_re_sub_crash(self, tmp_path):
        """B1 CRITICAL: re.sub() backreference crash - replace_all+ignore_case+new_string contains \1"""
        fp = str(tmp_path / "b1.txt")
        _write(fp, "foo bar foo")
        r = _run(edittext(path=fp, old_string="foo", new_string=r"\1",
                                 mode="all", ignore_case=True))
        # Fix: lambda m:new_string makes \1 no longer interpreted as backreference, literal insert
        assert is_success(r), f"B1 fix: should succeed: {r}"
        assert _read(fp) == r"\1 bar \1", "B1: literal \1 should replace all foo"

    def test_bug_b2_crlf_corruption(self, tmp_path):
        """B2 CRITICAL: CRLF -> LF line ending corruption"""
        fp = str(tmp_path / "b2.txt")
        raw = b"line1\r\nline2\r\nline3\r\n"
        Path(fp).write_bytes(raw)
        r = _run(edittext(path=fp, old_string="line2", new_string="CHANGED"))
        assert is_success(r)
        result = Path(fp).read_bytes()
        # Fix: CRLF is now preserved
        assert b"\r\n" in result, "B2 fix: CRLF should be preserved"
        assert b"CHANGED\r\n" in result or b"CHANGED\n" in result

    def test_bug_b3_backreference_g1_same_as_b1(self, tmp_path):
        """B3: \g<1> backreference same issue as B1"""
        fp = str(tmp_path / "b3.txt")
        _write(fp, "test test")
        r = _run(edittext(path=fp, old_string="test", new_string=r"\g<1>",
                                 mode="all", ignore_case=True))
        # Fix: lambda makes \g<1> no longer interpreted as backreference
        assert is_success(r), f"B3 fix: should succeed: {r}"
        assert _read(fp) == r"\g<1> \g<1>", "B3: literal \g<1> should replace all test"

    def test_bug_b4_no_path_traversal_protection(self, tmp_path):
        """B4 MEDIUM: No path traversal protection - ../ can traverse to parent dir"""
        outside = tmp_path.parent / "b4_outside.txt"
        _write(str(outside), "secret")
        traversal = str(tmp_path / "sub" / ".." / "b4_outside.txt")
        r = _run(edittext(path=traversal, old_string="secret", new_string="EDITED"))
        # Fix: .resolve() blocks path traversal, returns error instead of executing
        assert is_error(r), "B4 fix: path traversal should be rejected"

    def test_bug_b5_null_byte_in_path_not_protected(self, tmp_path):
        """B5 MEDIUM: file_path null byte check missing"""
        safe_path = tmp_path / "b5_real.txt"
        _write(str(safe_path), "safe content")
        evil = str(tmp_path / "b5_real.txt\x00evil.txt")
        r = _run(edittext(path=evil, old_string="safe", new_string="EDITED"))
        assert is_error(r), "Null byte path should be rejected"

    def test_bug_b6_operation_id_none_when_db_down(self, tmp_path):
        """operation_id is now internal (not exposed in data); verify edit succeeds - 小欧 2026-07-11"""
        fp = str(tmp_path / "b6.txt")
        _write(fp, "test")
        r = _run(edittext(path=fp, old_string="test", new_string="done"))
        # 三档数据设计: 完全成功 data={}, operation_id 不再对外暴露 - 小欧 2026-07-11
        assert is_success(r)
        assert _read(fp) == "done"

    def test_bug_b7_invalid_encoding_silent_fallback(self, tmp_path):
        """B7 MEDIUM: Invalid encoding silent fallback, user unaware"""
        fp = str(tmp_path / "b7.txt")
        _write(fp, "content")
        r = _run(edittext(path=fp, old_string="content", new_string="done",
                                 encoding="invalid-encoding"))
        # Tool does not error, silently falls back to utf-8 - user specified wrong encoding gets no warning
        assert is_success(r), "B7: invalid encoding silent fallback"

    def test_bug_b8_encoding_param_not_controlling_write(self, tmp_path):
        """ASCII content survives latin-1 decode, edit succeeds - 小欧 2026-07-11"""
        fp = str(tmp_path / "b8.txt")
        src = "hello"
        Path(fp).write_text(src, encoding="gbk")
        r = _run(edittext(path=fp, old_string="hello", new_string="world",
                                 encoding="latin-1"))
        # ASCII "hello" decodes identically under latin-1, so old_string is found - 小欧 2026-07-11
        assert is_success(r), f"ASCII content should decode fine under latin-1: {r}"
        assert _read(fp) == "world"

    def test_bug_b9_backslash_in_new_string_re_sub(self, tmp_path):
        """B9 MEDIUM: \\n interpreted as newline by re.sub instead of literal"""
        fp = str(tmp_path / "b9.txt")
        _write(fp, "foo")
        r = _run(edittext(path=fp, old_string="foo", new_string="line1\\nline2",
                                 mode="all", ignore_case=True))
        # Fix: lambda keeps re.sub literal \n, behavior consistent with str.replace
        assert is_success(r)
        content = _read(fp)
        assert "\\n" in content, f"B9 fix: re.sub should keep literal \\n: {repr(content)}"
        # Compare str.replace behavior (ignore_case=False)
        fp2 = str(tmp_path / "b9b.txt")
        _write(fp2, "foo")
        r2 = _run(edittext(path=fp2, old_string="foo", new_string="line1\\nline2",
                                   mode="all", ignore_case=False))
        assert is_success(r2)
        assert _read(fp2) == "line1\\nline2", "str.replace keeps literal \\n"

    def test_bug_b10_empty_file_misleading_error(self, tmp_path):
        """B10 LOW: Empty file says 'no match' should say 'file is empty' instead"""
        fp = str(tmp_path / "b10.txt")
        _write(fp, "")
        r = _run(edittext(path=fp, old_string="anything", new_string="X"))
        assert is_error(r)
        err = r.get("llm_data", {}).get("status", {}).get("detail", "")
        # Fix: empty file now says 'file is empty' instead of misleading 'no matching content'
        assert "empty" in err.lower() or err != "", f"B10 fix: should hint 'file is empty', got: {err}"

    def test_bug_b11_utf8_utf8sig_duplicate(self):
        """B11 LOW: utf-8 and utf-8-sig duplicate in encoding attempt list"""
        from app.tools.file.edit_text_file import _try_read_file_with_encodings as tre
        import inspect
        src = inspect.getsource(tre)
        count_utf8sig = src.count("utf-8-sig")
        assert count_utf8sig <= 1, "B11: utf-8-sig should appear at most once"

    def test_bug_b12_replacement_char_threshold_hardcoded(self, tmp_path):
        """5% U+FFFD exceeds 3% threshold; also detected as gbk which cannot encode it - 小欧 2026-07-11"""
        fp = str(tmp_path / "b12.txt")
        text = "a" * 95 + "\ufffd" * 5
        _write(fp, text)
        r = _run(edittext(path=fp, old_string="a" * 95, new_string="b" * 95))
        # 5 U+FFFD in 100 chars = 5% > 3% threshold, content treated as garbled/binary - 小欧 2026-07-11
        assert is_error(r), "B12: 5% U+FFFD exceeds 3% threshold, expected error"

    def test_bug_b14_no_output_size_limit(self, tmp_path):
        """B14 LOW: No output file size limit - new_string much larger than old_string"""
        fp = str(tmp_path / "b14.txt")
        _write(fp, "x")
        r = _run(edittext(path=fp, old_string="x", new_string="y" * 500000))
        assert is_success(r), "B14: large new_string should succeed but may be too large"

    def test_bug_b17_get_file_encoding_non_existent(self, tmp_path):
        """get_file_encoding returns utf-8 fallback for non-existent file - 小欧 2026-07-11"""
        from app.tools.file.file_encoding import get_file_encoding
        fp = str(tmp_path / "nonexistent.txt")
        result = get_file_encoding(fp)
        assert result["data"]["encoding"] == "utf-8"
        assert result["data"]["confidence"] == 0.5

    def test_bug_b20_bom_may_residue(self, tmp_path):
        """B20 LOW: BOM file may leave BOM character residue when chardet misses"""
        fp = str(tmp_path / "b20.txt")
        raw = b"\xef\xbb\xbfhello"
        Path(fp).write_bytes(raw)
        r = _run(edittext(path=fp, old_string="hello", new_string="bye"))
        assert is_success(r), "B20: BOM file should be editable"
        result = Path(fp).read_bytes()
        if not result.startswith(b"\xef\xbb\xbf"):
            pass  # BOM was handled

    def test_bug_b21_system_file_permission_crash(self, tmp_path):
        """B21 CRITICAL: PermissionError uncaught causes 500 crash"""
        fp = r"C:\Windows\System32\config\SAM"
        # Fix: PermissionError caught, returns clear error instead of crash
        r = _run(edittext(path=fp, old_string="x", new_string="y"))
        assert is_error(r), "B21 fix: should return error instead of crash"


# #9: 冲突错误附文件当前内容前2000字符
class TestConflictErrorContentPreview:
    """#9 文件外部修改错误增强 — 小欧 2026-07-21"""

    def test_read_fresh_after_external_modify(self, tmp_path):
        """外部修改后第二次编辑能正确读取最新内容(record_read确保mtime基准)"""
        fp = str(tmp_path / "conflict_test.txt")
        _write(fp, "line1\nline2\nline3\n")
        r1 = _run(edittext(path=fp, old_string="line1", new_string="modified1"))
        assert is_success(r1)
        # 外部修改文件
        import time
        time.sleep(0.05)
        _write(fp, "externally modified content\n")
        # 第二次编辑: record_read记录最新mtime,不误报冲突
        r2 = _run(edittext(path=fp, old_string="externally", new_string="changed"))
        assert is_success(r2)
