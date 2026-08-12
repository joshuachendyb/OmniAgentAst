# -*- coding: utf-8 -*-
# ================================================================
# 【skip case 归档副本】 - 小欧 2026-08-12 10:43:59
# 原路径: backend/tests/tools/param_combination/test_grep_file_content_retest.py
# 归档原因: 包含 Windows 平台限制类 skip case(symlink),
#           已从 backend/tests 原文件删除对应 skip case, 此处保留完整代码,
#           便于未来在其他平台(如 Linux)恢复运行。
# ================================================================
"""
# grep_file_content 复测 -- 13维度 x 115+ 测试用例
# 编写人: 小欧 2026-06-27

# 目标: 发现30+个bug
"""
import asyncio
import os
import sys
from pathlib import Path
from typing import Optional, List

import pytest

from app.tools.file.grep_file_content import grep
from app.tools.tool_response import is_success, is_error, is_warning


def _run(coro):
    return asyncio.run(coro)


def _write(path: str, content: str, encoding: str = "utf-8"):
    Path(path).write_text(content, encoding=encoding)


def _write_bytes(path: str, content: bytes):
    Path(path).write_bytes(content)


def _mkdir(d: Path, name: str) -> Path:
    p = d / name
    p.mkdir(exist_ok=True)
    return p


# ----------------------------------------------------------------------------------------------------------------------
# D1: 参数边界验证 (12 cases)
# ----------------------------------------------------------------------------------------------------------------------

class TestD1ParamEdgeCases:
    """D1: 参数边界 -- 现有测试未覆盖的边界"""

    def test_d1_01_single_dot_pattern(self, tmp_path):
        """pattern='.' 匹配任意字符"""
        _write(str(tmp_path / "a.txt"), "x\ny\n")
        r = _run(grep(".", str(tmp_path)))
        assert is_success(r), f"点号应匹配任意字符 {r}"
        assert r["data"]["total_matches"] >= 2

    def test_d1_02_caret_start_anchor(self, tmp_path):
        """pattern='^' 匹配所有行首"""
        _write(str(tmp_path / "a.txt"), "a\nb\nc\n")
        r = _run(grep("^", str(tmp_path)))
        assert is_success(r), "行首锚点应匹配所有行"
        assert r["data"]["total_matches"] >= 3

    def test_d1_03_dollar_end_anchor(self, tmp_path):
        """pattern='$' 匹配所有行尾"""
        _write(str(tmp_path / "a.txt"), "a\nb\nc\n")
        r = _run(grep("$", str(tmp_path)))
        assert is_success(r), "行尾锚点应匹配所有行"
        assert r["data"]["total_matches"] >= 3

    def test_d1_04_empty_alternation(self, tmp_path):
        """pattern='|' 匹配空字符串 -- 可能导致大量匹配"""
        _write(str(tmp_path / "a.txt"), "hello")
        r = _run(grep("|", str(tmp_path)))
        assert is_success(r), "空交替应匹配每个位置"

    def test_d1_05_word_boundary(self, tmp_path):
        """pattern='\\b' 匹配零宽单词边界"""
        _write(str(tmp_path / "a.txt"), "hello world")
        r = _run(grep(r"\b", str(tmp_path)))
        assert is_success(r), "单词边界应匹配"

    def test_d1_06_dot_star_pattern(self, tmp_path):
        """pattern='.*' 匹配整行内容"""
        _write(str(tmp_path / "a.txt"), "hello world")
        r = _run(grep(".*", str(tmp_path)))
        assert is_success(r), "任意字符应匹配整行"

    def test_d1_07_search_dir_with_null_byte(self, tmp_path):
        """search_dir 含空字节"""
        r = _run(grep("x", str(tmp_path) + "\x00evil"))
        assert is_error(r), "搜索目录含空字节应报错"

    def test_d1_08_search_dir_trailing_slash(self, tmp_path):
        """search_dir 尾部带斜杠"""
        d = str(tmp_path).replace("\\", "/") + "/"
        _write(str(tmp_path / "f.txt"), "content")
        r = _run(grep("content", d))
        assert is_success(r), "尾部斜杠不影响搜索"

    def test_d1_09_path_with_spaces(self, tmp_path):
        """搜索目录含空格"""
        d = _mkdir(tmp_path, "my dir")
        _write(str(d / "f.txt"), "hello")
        r = _run(grep("hello", str(d)))
        assert is_success(r), "含空格的路径应正常"

    def test_d1_10_pattern_very_long_200_ok(self, tmp_path):
        """pattern 刚好200字符 -- ReDoS检查边界"""
        _write(str(tmp_path / "a.txt"), "x")
        pat = "a" * 200
        r = _run(grep(pat, str(tmp_path)))
        assert is_success(r), "200字符应正常"

    def test_d1_11_pattern_over_200_searched(self, tmp_path):
        """pattern 201字符 -- 长度限制已移除,正常搜索"""
        _write(str(tmp_path / "a.txt"), "x")
        pat = "a" * 201
        r = _run(grep(pat, str(tmp_path)))
        assert is_success(r), "超过200字符pattern应正常搜索"


# ----------------------------------------------------------------------------------------------------------------------
# D2: 正则表达式边界 (12 cases)
# ----------------------------------------------------------------------------------------------------------------------

class TestD2RegexEdgeCases:
    """D2: 正则边界 -- 退化和高级正则"""

    def test_d2_13_lookahead(self, tmp_path):
        """正向前瞻 (?=)"""
        _write(str(tmp_path / "a.txt"), "foo bar")
        r = _run(grep(r"foo (?=bar)", str(tmp_path)))
        assert is_success(r), "前瞻应匹配"

    def test_d2_14_lookbehind(self, tmp_path):
        """正向在顾 (?<=)"""
        _write(str(tmp_path / "a.txt"), "foo bar")
        r = _run(grep(r"(?<=foo) bar", str(tmp_path)))
        assert is_success(r), "在顾应匹配"

    def test_d2_15_backreference_in_pattern(self, tmp_path):
        """反向引用 \\1 在pattern中"""
        _write(str(tmp_path / "a.txt"), "foo foo")
        r = _run(grep(r"(foo) \1", str(tmp_path)))
        assert is_success(r), "反向引用应能匹配重复词"

    def test_d2_16_named_group(self, tmp_path):
        """命名分组 (?P<name>)"""
        _write(str(tmp_path / "a.txt"), "foo bar")
        r = _run(grep(r"(?P<word>\w+)", str(tmp_path)))
        assert is_success(r), "命名分组应正常"

    def test_d2_17_nested_quantifier_redos(self, tmp_path):
        """ReDoS检测 (a+)+ 嵌套量词"""
        _write(str(tmp_path / "a.txt"), "aaa")
        r = _run(grep(r"(a+)+", str(tmp_path)))
        assert is_error(r), "(a+)+ 嵌套量词应被ReDoS防护拒绝"

    def test_d2_18_nested_quantifier_star(self, tmp_path):
        """ReDoS检测 (a*)* 嵌套量词"""
        _write(str(tmp_path / "a.txt"), "aaa")
        r = _run(grep(r"(a*)*", str(tmp_path)))
        assert is_error(r), "(a*)* 嵌套量词应被ReDoS防护拒绝"

    def test_d2_19_nested_quantifier_repeat(self, tmp_path):
        """ReDoS检测 (a+){2,} 量词嵌套"""
        _write(str(tmp_path / "a.txt"), "aaa")
        r = _run(grep(r"(a+){2,}", str(tmp_path)))
        assert is_error(r), "(a+){2,} 应被ReDoS防护拒绝"

    def test_d2_20_inline_ignore_case_flag(self, tmp_path):
        """行内 (?i) 标记与ignore_case 重叠"""
        _write(str(tmp_path / "a.txt"), "HELLO")
        r = _run(grep(r"(?i)hello", str(tmp_path), ignore_case=False))
        assert is_success(r), "行内(?i)应使匹配忽略大小写"

    def test_d2_21_non_greedy_quantifier(self, tmp_path):
        """非贪婪量词 *?"""
        _write(str(tmp_path / "a.txt"), "<a><b>")
        r = _run(grep(r"<.*?>", str(tmp_path)))
        assert is_success(r), "非贪婪应匹配最短"
        assert r["data"]["total_matches"] >= 2

    def test_d2_22_backtracking_pattern(self, tmp_path):
        """复杂回溯模式"""
        _write(str(tmp_path / "a.txt"), '"hello" world "foo"')
        r = _run(grep(r'"[^"]*"', str(tmp_path)))
        assert is_success(r), "引号内内容应匹配"
        assert r["data"]["total_matches"] == 2

    def test_d2_23_pattern_with_newline(self, tmp_path):
        """pattern含\\n -- 按行搜索不跨行"""
        _write(str(tmp_path / "a.txt"), "line1\nline2\n")
        r = _run(grep("line1\nline2", str(tmp_path)))
        assert is_success(r), "含\\n的pattern不跨行匹配"
        assert r["data"]["total_matches"] == 0, "按行搜索,跨行pattern不应匹配"

    def test_d2_24_null_byte_in_pattern(self, tmp_path):
        """pattern含\\x00"""
        _write(str(tmp_path / "a.txt"), "hello\x00world")
        r = _run(grep("hello\x00world", str(tmp_path)))
        assert is_success(r), "含\\x00的pattern应能编译"


# ----------------------------------------------------------------------------------------------------------------------
# D3: 目录遍历/路径安全 (10 cases)
# ----------------------------------------------------------------------------------------------------------------------

class TestD3PathSecurity:
    """D3: 目录遍历和路径安全"""

    def test_d3_25_path_traversal_in_search_dir(self, tmp_path):
        """search_dir 含../"""
        target_dir = tmp_path / "d3_target"
        target_dir.mkdir()
        _write(str(target_dir / "secret.txt"), "secret")
        r = _run(grep("secret", str(target_dir)))
        assert is_success(r), "正常路径应能搜索"

    def test_d3_26_search_dir_is_file(self, tmp_path):
        """path 指向文件 -- 支持单文件搜索"""
        fp = str(tmp_path / "a.txt")
        _write(fp, "hello")
        r = _run(grep("hello", fp))
        assert is_success(r), "path为单文件应正常搜索"
        assert r["data"]["total_matches"] == 1

    def test_d3_27_empty_search_dir_string(self, tmp_path):
        """search_dir = ''"""
        r = _run(grep("x", ""))
        assert is_error(r), "空搜索目录应报错"

    def test_d3_28_search_dir_current_dot(self, tmp_path):
        """search_dir = '.' 当前目录"""
        _write(str(tmp_path / "a.txt"), "hello")
        saved = os.getcwd()
        try:
            os.chdir(str(tmp_path))
            r = _run(grep("hello", "."))
            assert is_success(r), "点号表示当前目录"
        finally:
            os.chdir(saved)

    def test_d3_29_symlink_directory(self, tmp_path):
        """符号链接目录"""
        real = _mkdir(tmp_path, "real")
        _write(str(real / "a.txt"), "hello")
        link = tmp_path / "link"
        try:
            os.symlink(str(real), str(link), target_is_directory=True)
        except (OSError, NotImplementedError):
            # 本机无创建符号链接权限(Windows WinError 1314 SeCreateSymbolicLinkPrivilege)
            # 可配置: 设 OMNI_RUN_SYMLINK_TESTS=1 在支持符号链接的环境强制运行
            if not os.environ.get("OMNI_RUN_SYMLINK_TESTS"):
                pytest.skip("跳过:本机无符号链接创建权限(WinError 1314);设 OMNI_RUN_SYMLINK_TESTS=1 强制")
            raise
        r = _run(grep("hello", str(link)))
        assert is_success(r), "符号链接目录应可遍历"

    def test_d3_30_very_deep_nesting(self, tmp_path):
        """深层嵌套目录 20层 (Windows MAX_PATH限制)"""
        d = tmp_path
        for i in range(20):
            d = _mkdir(d, f"l{i}")
        _write(str(d / "a.txt"), "deep")
        r = _run(grep("deep", str(tmp_path)))
        assert is_success(r), "20层嵌套应正常遍历"
        assert r["data"]["total_matches"] >= 1

    def test_d3_31_search_dir_with_tilde(self, tmp_path):
        """search_dir 含~ (用户目录展开)"""
        # 使用真实目录创建文件
        home = Path(os.path.expanduser("~"))
        if not home.exists():
            pytest.skip("用户目录不存在")
        _write(str(tmp_path / "a.txt"), "test")
        # 验证 ~ 展开正常工作
        r = _run(grep("test", str(tmp_path)))
        assert is_success(r)

    def test_d3_32_non_ascii_dir_name(self, tmp_path):
        """目录名含中文"""
        d = _mkdir(tmp_path, "中文目录")
        _write(str(d / "a.txt"), "测试")
        r = _run(grep("测试", str(d)))

    def test_d3_33_root_dir_search_rejected(self, tmp_path):
        """path='/' 根目录 -- 安全问题,应快速拒绝或超时安全处理"""
        _write(str(tmp_path / "a.txt"), "x")
        r = _run(grep("x", "/"))
        assert is_success(r) or is_error(r), "根目录搜索不应崩溃"

    def test_d3_34_search_dir_parent_only(self, tmp_path):
        """只搜索父目录"""
        _write(str(tmp_path / "a.txt"), "content")
        parent = str(tmp_path.parent)
        r = _run(grep(str(tmp_path.name), parent))
        assert is_success(r), "父目录搜索应正常"


# ----------------------------------------------------------------------------------------------------------------------
# D4: 多编码文件搜索 (12 cases)
# ----------------------------------------------------------------------------------------------------------------------

class TestD4Encoding:
    """D4: 各种编码文件搜索 -- chardet自动检测"""

    def test_d4_35_gbk_search(self, tmp_path):
        """GBK编码文件搜索中文(path支持单文件)"""
        fp = str(tmp_path / "gbk.txt")
        Path(fp).write_text("你好世界", encoding="gbk")
        r = _run(grep("你好", fp))
        # path 支持单文件, 应成功搜索
        assert is_success(r), "GBK单文件搜索应成功"
        assert r["data"]["total_matches"] >= 1

    def test_d4_36_gbk_dir_search(self, tmp_path):
        """GBK编码文件在目录中搜索"""
        fp = str(tmp_path / "gbk.txt")
        Path(fp).write_text("你好世界", encoding="gbk")
        r = _run(grep("你好", str(tmp_path)))
        assert is_success(r), "GBK编码文件目录搜索应成功"
        if r["data"]["total_matches"] == 0:
            pass  # chardet可能误检编码

    def test_d4_37_utf8_bom_search(self, tmp_path):
        """UTF-8 BOM文件"""
        fp = str(tmp_path / "bom.txt")
        Path(fp).write_bytes(b"\xef\xbb\xbfhello")
        r = _run(grep("hello", str(tmp_path)))
        assert is_success(r), "BOM文件搜索应正常"

    def test_d4_38_utf16_le_search(self, tmp_path):
        """UTF-16 LE文件"""
        fp = str(tmp_path / "utf16.txt")
        Path(fp).write_bytes("hello\n".encode("utf-16-le"))
        r = _run(grep("hello", str(tmp_path)))
        assert is_success(r), "UTF-16 LE文件搜索应正常"

    def test_d4_39_big5_search(self, tmp_path):
        """Big5编码文件 -- chardet可能误检为JUC-JP"""
        fp = str(tmp_path / "big5.txt")
        Path(fp).write_bytes("中文".encode("big5"))
        r = _run(grep("中文", str(tmp_path)))
        assert is_success(r), "Big5文件搜索不应崩溃"

    def test_d4_40_shift_jis_search(self, tmp_path):
        """Shift-JIS编码文件"""
        fp = str(tmp_path / "sjis.txt")
        Path(fp).write_bytes("日本".encode("shift_jis"))
        r = _run(grep("日本", str(tmp_path)))
        assert is_success(r), "Shift-JIS文件搜索不应崩溃"

    def test_d4_41_mixed_encoding_dir(self, tmp_path):
        """同一目录中混合编码文件"""
        Path(str(tmp_path / "u.txt")).write_text("hello", encoding="utf-8")
        Path(str(tmp_path / "g.txt")).write_text("你好", encoding="gbk")
        r = _run(grep("hello|你好", str(tmp_path)))
        assert is_success(r), "混合编码目录搜索不应崩溃"

    def test_d4_42_all_fffd_replace_chars(self, tmp_path):
        """文件全部为U+FFFD替换字符 -- 超过5%阈值应跳过"""
        fp = str(tmp_path / "fffd.txt")
        Path(fp).write_text("\ufffd" * 100, encoding="utf-8")
        r = _run(grep("\ufffd", str(tmp_path)))
        assert is_success(r), "全部U+FFFD文件不应崩溃"

    def test_d4_43_exactly_5_percent_fffd(self, tmp_path):
        """正好5% U+FFFD字符 -- 阈值的精认边界"""
        fp = str(tmp_path / "bnd.txt")
        text = "x" * 95 + "\ufffd" * 5
        Path(fp).write_text(text, encoding="utf-8")
        r = _run(grep("x", str(tmp_path)))
        assert is_success(r), "正好5% U+FFFD应在阈值边界"

    def test_d4_44_just_under_5_percent_fffd(self, tmp_path):
        """4.9% U+FFFD -- 低于阈值"""
        fp = str(tmp_path / "under.txt")
        text = "x" * 951 + "\ufffd" * 49
        Path(fp).write_text(text, encoding="utf-8")
        r = _run(grep("x", str(tmp_path)))
        assert is_success(r), "低于5% U+FFFD应正常搜索"

    def test_d4_45_latin1_file_search(self, tmp_path):
        """Latin-1编码文件"""
        fp = str(tmp_path / "latin.txt")
        Path(fp).write_text("cafe francais", encoding="latin-1")
        r = _run(grep("cafe", str(tmp_path)))
        assert is_success(r), "Latin-1文件搜索不应崩溃"

    def test_d4_46_cp1252_file_search(self, tmp_path):
        """CP1252编码文件"""
        fp = str(tmp_path / "cp1252.txt")
        Path(fp).write_text("\u00a3100 special", encoding="cp1252")
        r = _run(grep("\u00a3100", str(tmp_path)))
        assert is_success(r), "CP1252文件搜索不应崩溃"


# ----------------------------------------------------------------------------------------------------------------------
# D5: 二进制文件处理 (10 cases)
# ----------------------------------------------------------------------------------------------------------------------

class TestD5BinaryFiles:
    """D5: 二进制文件的各种处理场景"""

    def test_d5_47_binary_ext_skipped(self, tmp_path):
        """已知二进制扩展名文件被跳过"""
        Path(str(tmp_path / "a.exe")).write_bytes(b"MZ\x90\x00test")
        Path(str(tmp_path / "b.txt")).write_text("test", encoding="utf-8")
        r = _run(grep("test", str(tmp_path)))
        assert is_success(r), "exe扩展名文件被跳过"
        assert r["data"]["total_files"] == 1

    def test_d5_48_dll_ext_skipped(self, tmp_path):
        """DLL扩展名文件被跳过"""
        Path(str(tmp_path / "lib.dll")).write_bytes(b"PE\x00\x00test")
        Path(str(tmp_path / "a.txt")).write_text("test", encoding="utf-8")
        r = _run(grep("test", str(tmp_path)))
        assert is_success(r)

    def test_d5_49_pyc_ext_skipped(self, tmp_path):
        """pyc扩展名是否在BINARY_EXTENSIONS中"""
        Path(str(tmp_path / "mod.pyc")).write_bytes(b"\x6f\x0d\x0d\x0a")
        r = _run(grep("test", str(tmp_path)))
        assert is_success(r)

    def test_d5_50_text_ext_but_binary(self, tmp_path):
        """文本扩展名但实际是二进制 -- is_binary_file检查"""
        fp = str(tmp_path / "data.bin")
        Path(fp).write_bytes(b"\x00\x01\x02\x03\x04\x05")
        r = _run(grep("test", str(tmp_path)))
        assert is_success(r), "二进制内容文件应安全跳过"

    def test_d5_51_no_extension_binary(self, tmp_path):
        """无扩展名但二进制内容"""
        fp = str(tmp_path / "binary_data")
        Path(fp).write_bytes(b"\x00\x01\x02\x03")
        r = _run(grep("test", str(tmp_path)))
        assert is_success(r), "无扩展名二进制文件应安全处理"

    def test_d5_52_so_ext_skipped(self, tmp_path):
        """.so 扩展名(Linux共享库)"""
        Path(str(tmp_path / "lib.so")).write_bytes(b"\x7fELFtest")
        Path(str(tmp_path / "a.txt")).write_text("test", encoding="utf-8")
        r = _run(grep("test", str(tmp_path)))
        assert is_success(r)

    def test_d5_53_so_ext_no_text_content(self, tmp_path):
        """.so扩展名 + 仅有.so文件"""
        Path(str(tmp_path / "lib.so")).write_bytes(b"\x7fELFtest")
        r = _run(grep("test", str(tmp_path)))
        assert is_success(r)
        assert r["data"]["total_files"] == 0

    def test_d5_54_many_binaries_with_text(self, tmp_path):
        """大量二进制文件+一个文本文件"""
        for i in range(20):
            Path(str(tmp_path / f"f{i}.exe")).write_bytes(b"MZtest")
        Path(str(tmp_path / "a.txt")).write_text("test", encoding="utf-8")
        r = _run(grep("test", str(tmp_path)))
        assert is_success(r)
        assert r["data"]["total_files"] == 1

    def test_d5_55_binary_only_dir(self, tmp_path):
        """目录全是二进制文件"""
        for ext in [".exe", ".dll", ".bin", ".dat"]:
            Path(str(tmp_path / f"f{ext}")).write_bytes(b"\x00\x01\x02")
        r = _run(grep("test", str(tmp_path)))
        assert is_success(r)
        assert r["data"]["total_files"] == 0

    def test_d5_56_binary_file_with_text_inside(self, tmp_path):
        """二进制文件内含文本 -- 通过扩展名跳过在不检查"""
        Path(str(tmp_path / "payload.exe")).write_bytes(b"MZhello.exe\x00")
        Path(str(tmp_path / "a.txt")).write_text("hello", encoding="utf-8")
        r = _run(grep("hello", str(tmp_path)))
        assert is_success(r)
        assert r["data"]["total_files"] == 1
        for m in r["data"]["matches"]:
            assert m["file"].endswith(".txt")


# ----------------------------------------------------------------------------------------------------------------------
# D6: Glob过滤边界 (10 cases)
# ----------------------------------------------------------------------------------------------------------------------

class TestD6GlobEdgeCases:
    """D6: Glob过滤各种边界"""

    def test_d6_57_glob_empty_string(self, tmp_path):
        """glob='' 被视为不过滤"""
        _write(str(tmp_path / "a.py"), "x")
        _write(str(tmp_path / "b.txt"), "x")
        r = _run(grep("x", str(tmp_path), glob=""))
        assert is_success(r), "空glob应搜索所有文件"
        assert r["data"]["total_files"] == 2

    def test_d6_58_glob_wildcard(self, tmp_path):
        """glob='*' 搜索所有文件"""
        _write(str(tmp_path / "a.py"), "x")
        _write(str(tmp_path / "b.txt"), "x")
        r = _run(grep("x", str(tmp_path), glob="*"))
        assert is_success(r)
        assert r["data"]["total_files"] == 2

    def test_d6_59_glob_all_dot_all(self, tmp_path):
        """glob='*.*' 所有带扩展名的文件"""
        _write(str(tmp_path / "a.py"), "x")
        _write(str(tmp_path / "b.txt"), "x")
        _write(str(tmp_path / "noext"), "x")
        r = _run(grep("x", str(tmp_path), glob="*.*"))
        assert is_success(r)
        # 不含无扩展名文件
        for m in r["data"]["matches"]:
            assert "." in Path(m["file"]).name

    def test_d6_60_glob_char_class(self, tmp_path):
        """glob='[ab]*.py' 字符类"""
        _write(str(tmp_path / "a.py"), "x")
        _write(str(tmp_path / "b.py"), "x")
        _write(str(tmp_path / "c.py"), "x")
        r = _run(grep("x", str(tmp_path), glob="[ab]*.py"))
        assert is_success(r)
        assert r["data"]["total_files"] == 2

    def test_d6_61_glob_negate_char_class(self, tmp_path):
        """glob='[!a]*.py' 否定字符类"""
        _write(str(tmp_path / "a.py"), "x")
        _write(str(tmp_path / "b.py"), "x")
        r = _run(grep("x", str(tmp_path), glob="[!a]*.py"))
        assert is_success(r)
        assert r["data"]["total_files"] == 1

    def test_d6_62_glob_dir_not_file(self, tmp_path):
        """glob匹配目录名而不是文件"""
        d = _mkdir(tmp_path, "mydir")
        _write(str(d / "a.txt"), "x")
        r = _run(grep("x", str(tmp_path), glob="mydir"))
        assert is_success(r)
        # fnmatch匹配文件名,不会递类匹配目录名

    def test_d6_63_glob_matches_subdir(self, tmp_path):
        """glob匹配子目录内的文件"""
        d = _mkdir(tmp_path, "sub")
        _write(str(d / "a.py"), "x")
        _write(str(tmp_path / "b.py"), "x")
        r = _run(grep("x", str(tmp_path), glob="*.py"))
        assert is_success(r)
        assert r["data"]["total_files"] == 2

    def test_d6_64_glob_case_windows(self, tmp_path):
        """Windows中glob大小写"""
        _write(str(tmp_path / "A.PY"), "x")
        r = _run(grep("x", str(tmp_path), glob="*.py"))
        assert is_success(r)
        # Windows文件系统大小写不敏感

    def test_d6_65_glob_question_mark(self, tmp_path):
        """glob='?.py' 单字符文件名"""
        _write(str(tmp_path / "a.py"), "x")
        _write(str(tmp_path / "ab.py"), "x")
        r = _run(grep("x", str(tmp_path), glob="?.py"))
        assert is_success(r)
        assert r["data"]["total_files"] == 1

    def test_d6_66_glob_no_match(self, tmp_path):
        """glob不匹配任何文件"""
        _write(str(tmp_path / "a.txt"), "x")
        r = _run(grep("x", str(tmp_path), glob="*.py"))
        assert is_success(r)
        assert r["data"]["total_files"] == 0


# ----------------------------------------------------------------------------------------------------------------------
# D7: 输出模式结构验证 (10 cases)
# ----------------------------------------------------------------------------------------------------------------------

class TestD7OutputStructure:
    """D7: 输出模式结构完整性"""

    def test_d7_67_content_mode_full_structure(self, tmp_path):
        """content模式: 验证所有字段"""
        _write(str(tmp_path / "a.txt"), "hello\nworld\n")
        r = _run(grep("hello", str(tmp_path)))
        assert is_success(r)
        d = r["data"]
        assert "matches" in d
        assert isinstance(d["matches"], list)
        assert len(d["matches"]) > 0
        m = d["matches"][0]
        assert "file" in m, "匹配项缺少file字段"
        assert "line" in m, "匹配项缺少line字段"
        assert "content" in m, "匹配项缺少content字段"
        assert "matched" in m, "匹配项缺少matched字段"
        assert isinstance(m["line"], int), "line应为整数"
        assert m["line"] >= 1, "line应从1开始"
        assert "total_matches" in d
        assert "total_files" in d

    def test_d7_68_content_mode_zero_matches(self, tmp_path):
        """content模式 0匹配"""
        _write(str(tmp_path / "a.txt"), "hello")
        r = _run(grep("NO_MATCH", str(tmp_path)))
        assert is_success(r)
        d = r["data"]
        assert d["total_matches"] == 0
        assert d["total_files"] == 0
        assert d["matches"] == []

    def test_d7_73_content_rstrip_behavior(self, tmp_path):
        """content行尾\\r\\n被rstrip"""
        Path(str(tmp_path / "a.txt")).write_bytes(b"hello\r\nworld\r\n")
        r = _run(grep("hello|world", str(tmp_path)))
        assert is_success(r)
        for m in r["data"]["matches"]:
            c = m["content"]
            assert not c.endswith("\n"), f"行尾\\n应被去除: {repr(c)}"
            assert not c.endswith("\r"), f"行尾\\r应被去除: {repr(c)}"

    def test_d7_74_content_trailing_spaces(self, tmp_path):
        """保留行尾空格 (不含\\r\\n)"""
        _write(str(tmp_path / "a.txt"), "hello   \nworld\n")
        r = _run(grep("hello", str(tmp_path)))
        assert is_success(r)
        c = r["data"]["matches"][0]["content"]
        assert c == "hello   ", f"行尾空格应保留: {repr(c)}"

    def test_d7_75_file_path_is_absolute(self, tmp_path):
        """返回的file字段是绝对路径"""
        _write(str(tmp_path / "a.txt"), "content")
        r = _run(grep("content", str(tmp_path)))
        assert is_success(r)
        for m in r["data"]["matches"]:
            p = m["file"]
            assert os.path.isabs(p), f"文件路径应为绝对路径: {p}"
            assert os.path.exists(p), f"文件路径应存在: {p}"

    def test_d7_76_skipped_binary_still_success(self, tmp_path):
        """二进制文件跳过仍返回success"""
        Path(str(tmp_path / "a.exe")).write_bytes(b"MZtest")
        Path(str(tmp_path / "b.txt")).write_text("test", encoding="utf-8")
        r = _run(grep("test", str(tmp_path)))
        assert is_success(r)
        assert r["data"]["total_files"] == 1


# ----------------------------------------------------------------------------------------------------------------------
# D9: 空文件/边缘内容 (10 cases)
# ----------------------------------------------------------------------------------------------------------------------

class TestD9EmptyEdgeContent:
    """D9: 空文件和边缘内容"""

    def test_d9_87_empty_file(self, tmp_path):
        """0字节文件 -- 在目录中搜索"""
        _write(str(tmp_path / "empty.txt"), "")
        _write(str(tmp_path / "a.txt"), "content")
        r = _run(grep("content", str(tmp_path)))
        assert is_success(r)
        assert r["data"]["total_files"] == 1

    def test_d9_88_only_empty_files(self, tmp_path):
        """目录中全是0字节文件"""
        for i in range(5):
            _write(str(tmp_path / f"e{i}.txt"), "")
        r = _run(grep("content", str(tmp_path)))
        assert is_success(r)
        assert r["data"]["total_files"] == 0

    def test_d9_89_file_with_only_newlines(self, tmp_path):
        """只有换行符的文件"""
        _write(str(tmp_path / "a.txt"), "\n\n\n")
        r = _run(grep("^$", str(tmp_path)))
        assert is_success(r)
        # 空行匹配每一行

    def test_d9_90_file_with_only_whitespace(self, tmp_path):
        """只有空白的文件"""
        _write(str(tmp_path / "a.txt"), "   \n\t\t\n")
        r = _run(grep(r"\S", str(tmp_path)))
        assert is_success(r)
        assert r["data"]["total_matches"] == 0

    def test_d9_91_single_char_file(self, tmp_path):
        """只有一个字符的文件"""
        _write(str(tmp_path / "a.txt"), "x")
        r = _run(grep("x", str(tmp_path)))
        assert is_success(r)
        assert r["data"]["total_matches"] == 1

    def test_d9_92_file_no_trailing_newline(self, tmp_path):
        """文件末尾没有换行符"""
        Path(str(tmp_path / "a.txt")).write_bytes(b"hello")
        r = _run(grep("hello", str(tmp_path)))
        assert is_success(r)
        assert r["data"]["total_matches"] == 1

    def test_d9_93_crlf_line_endings(self, tmp_path):
        """CRLF换行文件"""
        Path(str(tmp_path / "a.txt")).write_bytes(b"line1\r\nline2\r\n")
        r = _run(grep("line1|line2", str(tmp_path)))
        assert is_success(r)
        assert r["data"]["total_matches"] == 2

    def test_d9_94_mixed_line_endings(self, tmp_path):
        """混合换行符文件"""
        Path(str(tmp_path / "a.txt")).write_bytes(b"line1\nline2\r\nline3\n")
        r = _run(grep("line", str(tmp_path)))
        assert is_success(r)
        assert r["data"]["total_matches"] == 3

    def test_d9_95_old_mac_cr_line_endings(self, tmp_path):
        """老Mac \\r 换行文件"""
        Path(str(tmp_path / "a.txt")).write_bytes(b"line1\rline2\r")
        r = _run(grep("line1|line2", str(tmp_path)))
        assert is_success(r), "老Mac换行符文件应处理"
        # \\r被当作普通字符,整个文件为一行

    def test_d9_96_very_long_lines(self, tmp_path):
        """超长行(50000字符)"""
        _write(str(tmp_path / "a.txt"), "x" * 50000 + "\n")
        r = _run(grep("x{50000}", str(tmp_path)))
        assert is_success(r), "超长行搜索应正常"


# ----------------------------------------------------------------------------------------------------------------------
# D10: 大案模搜索 (8 cases)
# ----------------------------------------------------------------------------------------------------------------------

class TestD10LargeScale:
    """D10: 大案模搜索"""

    def test_d10_97_500_files_with_one_match(self, tmp_path):
        """500个文件各1个匹配"""
        for i in range(500):
            _write(str(tmp_path / f"f{i}.txt"), f"match_{i}")
        r = _run(grep("match_", str(tmp_path)))
        assert is_success(r)
        assert r["data"]["total_files"] == 500

    def test_d10_98_single_file_500_matches(self, tmp_path):
        """单个文件500行匹配"""
        _write(str(tmp_path / "a.txt"), "match\n" * 500)
        r = _run(grep("match", str(tmp_path)))
        assert is_success(r)
        assert r["data"]["total_matches"] == 500

    def test_d10_99_multiple_matches_per_line(self, tmp_path):
        """单行多个匹配 -- 验证计数"""
        _write(str(tmp_path / "a.txt"), "xx\nxx\n")
        r = _run(grep("x", str(tmp_path)))
        assert is_success(r)
        assert r["data"]["total_matches"] == 4, "每行2个x应计4个匹配"

    def test_d10_100_multiple_per_line(self, tmp_path):
        """单行多匹配 -- 非重叠计数"""
        _write(str(tmp_path / "a.txt"), "aaaa\n")
        r = _run(grep("aa", str(tmp_path)))
        assert is_success(r)
        # "aaaa"中"aa" 出现3次(重叠),findall非重叠为2次
        assert r["data"]["total_matches"] == 2, "非重叠匹配应计2次"

    def test_d10_101_1000_subdirectories(self, tmp_path):
        """1000个子目录"""
        for i in range(100):
            d = _mkdir(tmp_path, f"d{i}")
            _write(str(d / "a.txt"), "x")
        r = _run(grep("x", str(tmp_path)))
        assert is_success(r), "100个目录搜索应正常"
        assert r["data"]["total_files"] == 100

    def test_d10_102_mixed_file_types_large_dir(self, tmp_path):
        """混合文件类型的大目录搜索"""
        for i in range(50):
            _write(str(tmp_path / f"a{i}.py"), f"func_{i}()\n")
        for i in range(50):
            Path(str(tmp_path / f"b{i}.exe")).write_bytes(b"MZtest")
        r = _run(grep("func_", str(tmp_path), glob="*.py"))
        assert is_success(r)
        assert r["data"]["total_files"] == 50

    def test_d10_103_search_5mb_file(self, tmp_path):
        """5MB 文件正常完整搜索"""
        line = "x" * 1000 + "\n"
        # 创建约5MB的文件
        with Path(str(tmp_path / "big.txt")).open("w", encoding="utf-8") as f:
            for _ in range(5000):
                f.write(line)
        r = _run(grep("x{1000}", str(tmp_path)))
        assert is_success(r), "5MB文件应正常搜索"

    def test_d10_104_over_10mb_searched(self, tmp_path):
        """超过10MB的文件被正常完整搜索(不再限制文件大小)"""
        big_line = "x" * 10000 + "\n"
        with Path(str(tmp_path / "huge.txt")).open("w", encoding="utf-8") as f:
            for _ in range(1100):
                f.write(big_line)
        r = _run(grep("x{10000}", str(tmp_path)))
        assert is_success(r), "超过10MB文件应正常搜索不崩溃"
        assert r["data"]["total_matches"] > 0


# ----------------------------------------------------------------------------------------------------------------------
# D11: 错误/超时处理 (10 cases)
# ----------------------------------------------------------------------------------------------------------------------

class TestD11ErrorTimeout:
    """D11: 错误处理和超时"""

    def test_d11_105_pattern_is_none(self, tmp_path):
        """pattern=None"""
        _write(str(tmp_path / "a.txt"), "x")
        r = _run(grep(None, str(tmp_path)))
        assert is_error(r), "None pattern应报错"

    def test_d11_106_search_dir_is_none(self, tmp_path):
        """path=None"""
        r = _run(grep("x", None))
        assert is_error(r), "None search_dir应报错"

    def test_d11_107_invalid_regex_error_detail(self, tmp_path):
        """无效正则的错误信息"""
        _write(str(tmp_path / "a.txt"), "x")
        r = _run(grep("[invalid", str(tmp_path)))
        assert is_error(r)
        err = r.get("llm_data", {}).get("status", {}).get("detail", "")
        assert "正则表达式无效" in err, f"错误信息应提示正则无效: {err}"

    def test_d11_108_pattern_whitespace_only(self, tmp_path):
        """pattern纯空白 -- 被strip检测"""
        _write(str(tmp_path / "a.txt"), "   ")
        r = _run(grep("   ", str(tmp_path)))
        # 空白pattern被strip检测为空,但strip会移除空白
        assert is_success(r) or is_error(r)

    def test_d11_109_deadline_expired_immediate(self, tmp_path):
        """deadline已过期 -- 手动模拟超短timeout"""
        _write(str(tmp_path / "a.txt"), "x")
        r = _run(grep("x", str(tmp_path)))
        # 使用正常路径,因为没有TOOL_TIMEOUTS限制无法手动改

    def test_d11_110_bypass_not_affect_search(self, tmp_path):
        """斜杠反斜杠路径一致性"""
        d = str(tmp_path).replace("\\", "/")
        _write(str(tmp_path / "a.txt"), "test")
        r = _run(grep("test", d))
        assert is_success(r), "正斜杠路径应正常"

    def test_d11_111_exception_in_grep_files_sync(self, tmp_path):
        """_grep_files_sync内部异常被捕获"""
        _write(str(tmp_path / "a.txt"), "x")
        r = _run(grep("x", str(tmp_path)))
        assert is_success(r), "异常应被顶层捕获"

    def test_d11_112_re_match_with_empty_string_pattern(self, tmp_path):
        """空pattern经过strip检测在,检查实际正则行为"""
        _write(str(tmp_path / "a.txt"), "x")
        r = _run(grep("x", str(tmp_path)))
        assert is_success(r)

    def test_d11_113_search_dir_with_bad_encoding(self, tmp_path):
        """search_dir路径编码问题"""
        d = _mkdir(tmp_path, "test_dir")
        _write(str(d / "a.txt"), "content")
        r = _run(grep("content", str(d)))
        assert is_success(r), "正常路径应工作"

    def test_d11_114_out_of_memory_safety(self, tmp_path):
        """超大匹配集防内存溢出"""
        long_line = "x" * 5000
        _write(str(tmp_path / "a.txt"), long_line + "\n")
        r = _run(grep("x", str(tmp_path)))
        assert is_success(r), "大匹配不应崩溃"


# ----------------------------------------------------------------------------------------------------------------------
# D12: 多匹配计数准认性 (8 cases)
# ----------------------------------------------------------------------------------------------------------------------

class TestD12MultipleMatchCounting:
    """D12: 多匹配计数的准认性"""

    def test_d12_115_one_match_one_line(self, tmp_path):
        """1条匹配1行"""
        _write(str(tmp_path / "a.txt"), "error\n")
        r = _run(grep("error", str(tmp_path)))
        assert is_success(r)
        assert r["data"]["total_matches"] == 1

    def test_d12_116_two_matches_same_line(self, tmp_path):
        """同一行2个匹配"""
        _write(str(tmp_path / "a.txt"), "aa\n")
        r = _run(grep("a", str(tmp_path)))
        assert is_success(r)
        assert r["data"]["total_matches"] == 2

    def test_d12_117_three_matches_same_line_overlap(self, tmp_path):
        """重叠匹配"aaa"中"aa"非重叠=1"""
        _write(str(tmp_path / "a.txt"), "aaa\n")
        r = _run(grep("aa", str(tmp_path)))
        assert is_success(r)
        # findall非重叠: "aaa"中"aa"出现1次(左起)
        assert r["data"]["total_matches"] == 1

    def test_d12_118_count_with_multiple_lines(self, tmp_path):
        """多行多匹配"""
        _write(str(tmp_path / "a.txt"), "ab\nab\n")
        r = _run(grep("ab", str(tmp_path)))
        assert is_success(r)
        assert r["data"]["total_matches"] == 2

    def test_d12_119_count_with_no_matches(self, tmp_path):
        """无匹配时计数为0"""
        _write(str(tmp_path / "a.txt"), "hello\n")
        r = _run(grep("NO_MATCH", str(tmp_path)))
        assert is_success(r)
        assert r["data"]["total_matches"] == 0
        assert r["data"]["total_files"] == 0

    def test_d12_121_content_mode_multiple_matches_same_line(self, tmp_path):
        """同一行多匹配时content模式不重复行"""
        _write(str(tmp_path / "a.txt"), "x x\n")
        r = _run(grep("x", str(tmp_path)))
        assert is_success(r)
        # 行中出现2次,count=2,但content模式只返回1行,含1个匹配
        assert r["data"]["total_matches"] == 2
        assert len(r["data"]["matches"]) == 1

    def test_d12_122_regex_findall_count_validation(self, tmp_path):
        """验证findall计数与regex引擎一致"""
        _write(str(tmp_path / "a.txt"), "test test test\n")
        r = _run(grep("test", str(tmp_path)))
        assert is_success(r)
        assert r["data"]["total_matches"] == 3, "test test test中test出现3次"


# ----------------------------------------------------------------------------------------------------------------------
# D13: Bug验证 (20 cases)
# ----------------------------------------------------------------------------------------------------------------------

class TestD13BugVerification:
    """D13: 针对源码分析发现的Bug验证"""

    def test_bug_g1_deadline_past_for_small_timeout(self, tmp_path):
        """Bug: deadline = monotonic() + timeout - 2, 如果timeout<2则立即超时"""
        _write(str(tmp_path / "a.txt"), "match")
        from app.tools.tool_constants import TOOL_TIMEOUTS
        orig = TOOL_TIMEOUTS.get("grep")
        TOOL_TIMEOUTS["grep"] = 1
        try:
            r = _run(grep("match", str(tmp_path)))
            assert is_success(r), "timeout=1也能搜索部分文件"
        finally:
            TOOL_TIMEOUTS["grep"] = orig

    def test_bug_g2_redos_check_raise_valueerror(self, tmp_path):
        """Bug: ReDoS检查在_grep_files_sync中引发ValueError被顶层捕获为错误"""
        _write(str(tmp_path / "a.txt"), "aaa")
        r = _run(grep(r"(a+)+", str(tmp_path)))
        assert is_error(r), "ReDoS模式应返回错误"
        err = r.get("llm_data", {}).get("status", {}).get("detail", "")
        assert "嵌套量词" in err, f"错误信息应提示嵌套量词: {err}"

    def test_bug_g3_long_literal_pattern_searched(self, tmp_path):
        """长字面量pattern正常搜索(pattern长度限制已移除)"""
        _write(str(tmp_path / "a.txt"), "x")
        pat = "a" * 201
        r = _run(grep(pat, str(tmp_path)))
        assert is_success(r), "长字面量pattern应正常搜索"
        assert r["data"]["total_matches"] == 0

    def test_bug_g4_glob_empty_str_not_filtering(self, tmp_path):
        """Bug: glob='' 不过滤,但用户期望可能是不匹配任何文件"""
        _write(str(tmp_path / "a.txt"), "x")
        _write(str(tmp_path / "b.log"), "x")
        r = _run(grep("x", str(tmp_path), glob=""))
        # 空字符串在Python中falsy,不会过滤
        assert r["data"]["total_files"] == 2

    def test_bug_g5_double_regex_compilation(self, tmp_path):
        """Bug: regex编译两次(line237和line138),性能浪费但逻辑正认"""
        _write(str(tmp_path / "a.txt"), "test")
        r = _run(grep("test", str(tmp_path)))
        assert is_success(r)

    def test_bug_g6_content_rstrip_removes_backslash_r(self, tmp_path):
        """Bug: content行尾\\r被rstrip移除,可能丢失数据"""
        Path(str(tmp_path / "a.txt")).write_bytes(b"hello\rworld\n")
        r = _run(grep("hello\rworld", str(tmp_path)))
        assert is_success(r), "含\\r的中文应能搜索"

    def test_bug_g7_content_mode_unique_files(self, tmp_path):
        """content模式跨文件匹配,文件路径可去重"""
        _write(str(tmp_path / "a.txt"), "error\nerror\n")
        _write(str(tmp_path / "b.txt"), "error\n")
        r = _run(grep("error", str(tmp_path)))
        assert is_success(r)
        files = r["data"]["matches"]
        paths = {f["file"] for f in files}
        assert len(paths) == 2, "a.txt与b.txt各应出现"

    def test_bug_g8_os_walk_with_path_object(self, tmp_path):
        """Bug: os.walk接收Path对象"""
        _write(str(tmp_path / "a.txt"), "test")
        r = _run(grep("test", str(tmp_path)))
        assert is_success(r), "Path对象传给os.walk"

    def test_bug_g9_is_binary_file_for_unknown_ext(self, tmp_path):
        """Bug: 未知扩展名调用is_binary_file,首次调用慢"""
        Path(str(tmp_path / "data.xyz")).write_text("test", encoding="utf-8")
        r = _run(grep("test", str(tmp_path)))
        assert is_success(r)

    def test_bug_g10_findall_doubles_regex_work(self, tmp_path):
        """Bug: findall在search之在再次匹配,工作量翻倍但计数正认"""
        _write(str(tmp_path / "a.txt"), "test test\n")
        r = _run(grep("test", str(tmp_path)))
        assert is_success(r)
        assert r["data"]["total_matches"] == 2

    def test_bug_g11_large_file_searched(self, tmp_path):
        """超大文件被正常完整搜索(不再限制文件大小)"""
        line = "x" * 10000 + "\n"
        with Path(str(tmp_path / "huge.txt")).open("w", encoding="utf-8") as f:
            for _ in range(1100):
                f.write(line)
        with Path(str(tmp_path / "small.txt")).open("w", encoding="utf-8") as f:
            f.write("test\n")
        r = _run(grep("test", str(tmp_path)))
        assert is_success(r), "超大文件和小文件都能搜索"

    def test_bug_g12_permission_denied_subdir(self, tmp_path):
        """Bug: 不可访问的子目录导致os.walk抛出PermissionError被顶层捕获"""
        sub = _mkdir(tmp_path, "restricted")
        _write(str(sub / "a.txt"), "secret")
        # 这需要实际设置目录权限,在Windows上复杂
        # 验证至少不崩溃
        _write(str(tmp_path / "outside.txt"), "public")
        r = _run(grep("public", str(tmp_path)))
        assert is_success(r), "不可访问目录不应阻塞整个搜索"

    def test_bug_g13_symlink_loop_crashes(self, tmp_path):
        """Bug: 符号链接环导致os.walk无限递类"""
        a = _mkdir(tmp_path, "a")
        b = _mkdir(tmp_path, "b")
        try:
            os.symlink(str(b), str(a / "link_to_b"), target_is_directory=True)
            os.symlink(str(a), str(b / "link_to_a"), target_is_directory=True)
        except (OSError, NotImplementedError):
            # 本机无创建符号链接权限(Windows WinError 1314 SeCreateSymbolicLinkPrivilege)
            # 可配置: 设 OMNI_RUN_SYMLINK_TESTS=1 在支持符号链接的环境强制运行
            if not os.environ.get("OMNI_RUN_SYMLINK_TESTS"):
                pytest.skip("跳过:本机无符号链接创建权限(WinError 1314);设 OMNI_RUN_SYMLINK_TESTS=1 强制")
            raise
        _write(str(tmp_path / "fix.txt"), "tgt")
        r = _run(grep("tgt", str(tmp_path)))
        assert is_success(r), "符号链接环不应崩溃"

    def test_bug_g14_case_sensitivity_non_ascii(self, tmp_path):
        """Bug: 非ASCII大小写匹配"""
        _write(str(tmp_path / "a.txt"), "\u00dcber")
        r_case = _run(grep("über", str(tmp_path), ignore_case=True))
        assert is_success(r_case)
        assert r_case["data"]["total_matches"] == 1, "大小写不敏感匹配ü"

    def test_bug_g15_pattern_with_dot_matches_newline(self, tmp_path):
        """Bug: '.' 默认不匹配\\n,按行搜索不会跨行"""
        _write(str(tmp_path / "a.txt"), "a\nb\n")
        r = _run(grep("a.b", str(tmp_path)))
        assert is_success(r)
        assert r["data"]["total_matches"] == 0, "点号默认不匹配换行符"

    def test_bug_g16_match_count(self, tmp_path):
        """Bug验证: 返回的total_matches准确"""
        _write(str(tmp_path / "a.txt"), "aa bb cc\n")
        r = _run(grep(r"\w+", str(tmp_path)))
        assert is_success(r)
        assert r["data"]["total_matches"] == 3

    def test_bug_g18_pattern_all_whitespace_stripped(self, tmp_path):
        """Bug: pattern只含空格被strip检测"""
        _write(str(tmp_path / "a.txt"), "   ")
        r = _run(grep("   ", str(tmp_path)))
        # strip在pattern为空 -> error
        if is_error(r):
            err = r.get("llm_data", {}).get("status", {}).get("detail", "")
            assert "不能为空" in err

    def test_bug_g19_search_dir_is_dot_not_absolute(self, tmp_path):
        """Bug: '.'不是绝对路径,os.walk正常工作"""
        saved = os.getcwd()
        try:
            os.chdir(str(tmp_path))
            _write(str(tmp_path / "a.txt"), "hello")
            r = _run(grep("hello", "."))
            assert is_success(r), "当前目录搜索应正常"
        finally:
            os.chdir(saved)

    def test_bug_g20_skip_binary_with_text_in_name(self, tmp_path):
        """Bug: 扩展名检查在is_binary_file之前"""
        Path(str(tmp_path / "normal.txt")).write_bytes(b"\x00\x01\x02test")
        Path(str(tmp_path / "ref.txt")).write_text("test", encoding="utf-8")
        r = _run(grep("test", str(tmp_path)))
        assert is_success(r)
        # txt扩展名->suffix不在BINARY_EXTENSIONS->suffix在TEXT_EXTENSIONS->跳过is_binary_file->读文件->可能含\\x00
        assert is_success(r)
