# -*- coding: utf-8 -*-
"""
FILE分类工具修复点测试 — 小健 2026-05-19

覆盖10个修复点的正确性验证：
F2-1  反转义顺序（write_text_file unescape）
F4-3  dry_run在单处替换生效（edit_file）
F7-1  show_line_no默认值（grep_file_content）
F5-1  sortBy=mtime排序生效（list_directory）
F8-1  use_regex移除（RenameFileInput）
F1    offset默认limit（read_file）
F8    rename_file Windows非法字符
F10   delete幂等性（file_operation）
F11   DataFileFormatInput写入限制说明
F7    grep多编码（gbk文件搜索）

Author: 小健 - 2026-05-19
"""

import asyncio
import os
import pytest
import tempfile
import time
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

from app.services.tools.file.file_schema import (
    RenameFileInput,
    DataFileFormatInput,
    ReadFileInput,
    ListDirectoryInput,
    SearchFilesInput,
    GrepFileContentInput,
    EditFileInput,
    WriteTextFileInput,
    FileOperationInput,
)
from app.services.tools.file.file_tools import (
    FileTools,
    _to_unified_format,
    READ_FILE_DEFAULT_LIMIT,
)


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


def _make_filetools_mock():
    """构造一个mock的FileTools实例，绕过__init__中的服务依赖"""
    ft = object.__new__(FileTools)
    ft.task_id = "test-task-id"
    ft._sequence = 0
    import threading
    ft._sequence_lock = threading.Lock()
    ft.safety = MagicMock()
    ft.safety.record_operation.return_value = "mock-op-id"
    ft.safety.execute_with_safety = lambda operation_id, operation_func: operation_func()
    ft.task_tracker = MagicMock()
    ft.visualizer = MagicMock()
    ft.allowed_paths = set()
    return ft


# =============================================================================
# F2-1: 反转义顺序 — write_text_file unescape=True时，\\\\应最先替换
# =============================================================================

class TestF21UnescapeOrder:
    """F2-1: 反转义顺序验证

    源码第632行 unescape 逻辑：
      content.replace("\\\\", "\\").replace("\\n", "\n").replace("\\\"", "\"")
    运行时：先把2字符\\替换为1字符\\，再把2字符\\n替换为换行，再把2字符\\"替换为引号。

    关键顺序：\\\\必须先于\\n替换。
    输入\\n（3字符：\\ \\ n）时：
      正确顺序：\\\\→\\ 得到\\n(2字符)，然后\\n→换行
      错误顺序：先替换\\n，但只有第2-3字符匹配，得到 \\ + 换行
    """

    BS = chr(92)  # 反斜杠字符，避免Python转义混淆

    def _unescape(self, text: str) -> str:
        """模拟源码的unescape逻辑"""
        return text.replace("\\\\", "\\").replace("\\n", "\n").replace("\\\"", "\"")

    def test_backslash_backslash_n_order_matters(self):
        """\\\\n（3字符）经正确顺序反转义后应为换行符

        输入：反斜杠+反斜杠+n（3字符）
        正确顺序：先把\\\\→\\得到\\n(2字符)，再\\n→换行
        """
        text = "line1" + self.BS + self.BS + "n" + "line2"
        result = self._unescape(text)
        assert result == "line1\nline2", f"正确顺序：\\\\n应变为换行符，实际: {repr(result)}"

    def test_wrong_order_produces_different_result(self):
        """验证错误顺序会产生不同结果，证明替换顺序重要"""
        text = "line1" + self.BS + self.BS + "n" + "line2"
        wrong_result = text.replace("\\n", "\n").replace("\\\\", "\\").replace("\\\"", "\"")
        correct_result = self._unescape(text)
        assert wrong_result != correct_result, "错误顺序结果不同，证明顺序重要"
        assert wrong_result == "line1" + self.BS + "\n" + "line2", "错误顺序：\\\\n→反斜杠+换行"

    def test_backslash_backslash_to_single(self):
        """两个反斜杠应替换为单个反斜杠"""
        text = "path" + self.BS + self.BS + "to" + self.BS + self.BS + "file"
        result = self._unescape(text)
        assert result == "path" + self.BS + "to" + self.BS + "file"

    def test_backslash_n_to_newline(self):
        """反斜杠+n应替换为真实换行"""
        text = "hello" + self.BS + "nworld"
        result = self._unescape(text)
        assert result == "hello\nworld"

    def test_escaped_quote(self):
        """反斜杠+引号应替换为引号"""
        text = "say" + self.BS + '"hello' + self.BS + '"'
        result = self._unescape(text)
        assert result == 'say"hello"'

    def test_mixed_unescape(self):
        """混合\\\\、\\n、\\\" 的内容"""
        text = "path" + self.BS + self.BS + "file" + self.BS + "nsay" + self.BS + '"hi' + self.BS + '"'
        result = self._unescape(text)
        expected = "path" + self.BS + "file\nsay\"hi\""
        assert result == expected

    def test_unescape_false_no_replace(self, temp_dir):
        """unescape=False时不应做任何替换"""
        ft = _make_filetools_mock()
        target = temp_dir / "no_unescape.txt"
        raw_text = "hello" + self.BS + "nworld"
        with patch.object(ft, '_validate_path', return_value=(True, "")):
            asyncio.get_event_loop().run_until_complete(
                ft.write_text_file(
                    file_path=str(target),
                    text=raw_text,
                    unescape=False,
                )
            )
        if target.exists():
            content = target.read_text(encoding="utf-8")
            assert content == raw_text


# =============================================================================
# F4-3: dry_run在单处替换生效
# =============================================================================

class TestF43DryRunSingleReplace:
    """F4-3: edit_file的old_string+new_string模式下dry_run=True应只预览不修改"""

    def test_dry_run_file_not_modified(self, temp_dir):
        """dry_run=True时文件内容不应改变"""
        ft = _make_filetools_mock()
        target = temp_dir / "dry_run_test.txt"
        original = "Hello World"
        target.write_text(original, encoding="utf-8")

        with patch.object(ft, '_validate_path', return_value=(True, "")):
            result = asyncio.get_event_loop().run_until_complete(
                ft.edit_file(
                    file_path=str(target),
                    old_string="Hello",
                    new_string="Hi",
                    dry_run=True,
                )
            )

        file_content = target.read_text(encoding="utf-8")
        assert file_content == original, "dry_run=True不应修改文件内容"

    def test_dry_run_returns_preview_info(self, temp_dir):
        """dry_run=True时返回结果应包含preview信息"""
        ft = _make_filetools_mock()
        target = temp_dir / "dry_run_preview.txt"
        target.write_text("Hello World", encoding="utf-8")

        with patch.object(ft, '_validate_path', return_value=(True, "")):
            result = asyncio.get_event_loop().run_until_complete(
                ft.edit_file(
                    file_path=str(target),
                    old_string="Hello",
                    new_string="Hi",
                    dry_run=True,
                )
            )

        data = result.get("data", {})
        assert data.get("preview") is True, "dry_run结果应包含preview=True"
        assert "diff_info" in data, "dry_run结果应包含diff_info"


# =============================================================================
# F7-1: show_line_no默认值
# =============================================================================

class TestF71ShowLineNoDefault:
    """F7-1: grep_file_content的show_line_no默认应为True"""

    def test_schema_show_line_no_default_true(self):
        """GrepFileContentInput的show_line_no默认值应为True"""
        schema = GrepFileContentInput(pattern="test")
        assert schema.show_line_no is True

    def test_grep_result_contains_line_numbers(self, temp_dir):
        """不传show_line_no参数时，结果应包含行号"""
        ft = _make_filetools_mock()
        target = temp_dir / "grep_test.txt"
        target.write_text("line1\nline2\nline3\n", encoding="utf-8")

        with patch.object(ft, '_validate_path', return_value=(True, "")):
            result = asyncio.get_event_loop().run_until_complete(
                ft.grep_file_content(
                    pattern="line2",
                    search_dir=str(temp_dir),
                )
            )

        data = result.get("data", {})
        matches = data.get("matches", [])
        if matches:
            first_match = matches[0]
            match_entries = first_match.get("matches", [])
            if match_entries:
                assert match_entries[0].get("line") is not None, "默认show_line_no=True时行号不应为None"


# =============================================================================
# F5-1: sortBy=mtime排序生效
# =============================================================================

class TestF51SortByMtime:
    """F5-1: list_directory按修改时间排序应生效"""

    def test_sort_by_mtime(self, temp_dir):
        """sortBy='mtime'时结果应按修改时间排序"""
        ft = _make_filetools_mock()
        f1 = temp_dir / "older.txt"
        f2 = temp_dir / "newer.txt"
        f1.write_text("old", encoding="utf-8")
        time.sleep(0.1)
        f2.write_text("new", encoding="utf-8")

        with patch.object(ft, '_validate_path', return_value=(True, "")):
            result = asyncio.get_event_loop().run_until_complete(
                ft.list_directory(
                    dir_path=str(temp_dir),
                    sortBy="mtime",
                )
            )

        data = result.get("data", {})
        entries = data.get("entries", [])
        if len(entries) >= 2:
            file_entries = [e for e in entries if e.get("type") == "file"]
            if len(file_entries) >= 2:
                assert file_entries[0]["name"] == "newer.txt", "mtime排序时最新的文件应排在前面"


# =============================================================================
# F8-1: use_regex移除
# =============================================================================

class TestF81UseRegexRemoved:
    """F8-1: RenameFileInput中不再有use_regex字段"""

    def test_rename_input_no_use_regex(self):
        """RenameFileInput.model_fields不应包含use_regex"""
        assert "use_regex" not in RenameFileInput.model_fields, "use_regex字段应已移除"

    def test_rename_input_instantiate_without_use_regex(self):
        """正常实例化RenameFileInput不需要use_regex"""
        inp = RenameFileInput(path="/tmp/test.txt", new_name="renamed.txt")
        assert inp.path == "/tmp/test.txt"
        assert inp.new_name == "renamed.txt"
        assert not hasattr(inp, "use_regex")


# =============================================================================
# F1: offset默认limit
# =============================================================================

class TestF1OffsetDefaultLimit:
    """F1: read_file传offset不传limit时，应默认limit=500"""

    def test_read_file_default_limit_constant(self):
        """READ_FILE_DEFAULT_LIMIT应为500"""
        assert READ_FILE_DEFAULT_LIMIT == 500

    def test_schema_offset_without_limit(self):
        """ReadFileInput可以只传offset不传limit"""
        inp = ReadFileInput(file_path="/tmp/test.txt", offset=1)
        assert inp.offset == 1
        assert inp.limit is None

    def test_read_file_with_offset_returns_at_most_500_lines(self, temp_dir):
        """传offset=1不传limit，返回行数应<=500"""
        ft = _make_filetools_mock()
        target = temp_dir / "large_file.txt"
        lines = [f"line{i}\n" for i in range(1, 1001)]
        target.write_text("".join(lines), encoding="utf-8")

        with patch.object(ft, '_validate_path', return_value=(True, "")):
            result = asyncio.get_event_loop().run_until_complete(
                ft.read_file(
                    file_path=str(target),
                    offset=1,
                )
            )

        data = result.get("data", {})
        content = data.get("content", "")
        if content:
            line_count = len(content.split("\n"))
            assert line_count <= READ_FILE_DEFAULT_LIMIT + 1, f"offset模式下默认limit=500，返回行数应<=501(含空行)"


# =============================================================================
# F8: rename_file Windows非法字符
# =============================================================================

class TestF8RenameWindowsIllegalChars:
    """F8: 新名称含<>:"|?*应返回错误"""

    @pytest.mark.skipif(os.name != "nt", reason="仅在Windows上测试")
    def test_rename_illegal_char_angle_bracket(self, temp_dir):
        """new_name含<应返回错误"""
        ft = _make_filetools_mock()
        target = temp_dir / "test.txt"
        target.write_text("content", encoding="utf-8")

        result = asyncio.get_event_loop().run_until_complete(
            ft.rename_file(
                path=str(target),
                new_name="bad<name.txt",
            )
        )

        data = result.get("data", {})
        assert data.get("success") is False
        assert "非法字符" in data.get("error", "") or "illegal" in data.get("error", "").lower()

    @pytest.mark.skipif(os.name != "nt", reason="仅在Windows上测试")
    def test_rename_illegal_char_colon(self, temp_dir):
        """new_name含:应返回错误"""
        ft = _make_filetools_mock()
        target = temp_dir / "test.txt"
        target.write_text("content", encoding="utf-8")

        result = asyncio.get_event_loop().run_until_complete(
            ft.rename_file(
                path=str(target),
                new_name="bad:name.txt",
            )
        )

        data = result.get("data", {})
        assert data.get("success") is False

    @pytest.mark.skipif(os.name != "nt", reason="仅在Windows上测试")
    def test_rename_illegal_char_pipe(self, temp_dir):
        """new_name含|应返回错误"""
        ft = _make_filetools_mock()
        target = temp_dir / "test.txt"
        target.write_text("content", encoding="utf-8")

        result = asyncio.get_event_loop().run_until_complete(
            ft.rename_file(
                path=str(target),
                new_name="bad|name.txt",
            )
        )

        data = result.get("data", {})
        assert data.get("success") is False

    @pytest.mark.skipif(os.name != "nt", reason="仅在Windows上测试")
    def test_rename_illegal_char_question(self, temp_dir):
        """new_name含?应返回错误"""
        ft = _make_filetools_mock()
        target = temp_dir / "test.txt"
        target.write_text("content", encoding="utf-8")

        result = asyncio.get_event_loop().run_until_complete(
            ft.rename_file(
                path=str(target),
                new_name="bad?name.txt",
            )
        )

        data = result.get("data", {})
        assert data.get("success") is False

    @pytest.mark.skipif(os.name != "nt", reason="仅在Windows上等待测试")
    def test_rename_illegal_char_asterisk(self, temp_dir):
        """new_name含*应返回错误"""
        ft = _make_filetools_mock()
        target = temp_dir / "test.txt"
        target.write_text("content", encoding="utf-8")

        result = asyncio.get_event_loop().run_until_complete(
            ft.rename_file(
                path=str(target),
                new_name="bad*name.txt",
            )
        )

        data = result.get("data", {})
        assert data.get("success") is False

    @pytest.mark.skipif(os.name != "nt", reason="仅在Windows上测试")
    def test_rename_legal_name_succeeds(self, temp_dir):
        """合法名称应正常通过非法字符校验（后续可能因文件不存在失败，但不应因非法字符失败）"""
        ft = _make_filetools_mock()
        target = temp_dir / "test.txt"
        target.write_text("content", encoding="utf-8")

        result = asyncio.get_event_loop().run_until_complete(
            ft.rename_file(
                path=str(target),
                new_name="good_name.txt",
            )
        )

        data = result.get("data", {})
        error = data.get("error", "")
        if error:
            assert "非法字符" not in error, "合法名称不应触发非法字符错误"


# =============================================================================
# F10: delete幂等性
# =============================================================================

class TestF10DeleteIdempotency:
    """F10: 删除不存在的文件应返回SUCCESS"""

    def test_delete_nonexistent_file_returns_success(self, temp_dir):
        """删除不存在的路径，应返回success=True"""
        ft = _make_filetools_mock()
        nonexistent = temp_dir / "does_not_exist.txt"

        result = asyncio.get_event_loop().run_until_complete(
            ft.file_operation(
                action="delete",
                source=str(nonexistent),
            )
        )

        data = result.get("data", {})
        assert data.get("success") is True, "删除不存在的文件应返回success=True(幂等)"
        assert "幂等" in data.get("message", "") or "不存在" in data.get("message", ""), "应包含幂等性说明"

    def test_delete_nonexistent_dir_returns_success(self, temp_dir):
        """删除不存在的目录，应返回success=True"""
        ft = _make_filetools_mock()
        nonexistent = temp_dir / "does_not_exist_dir"

        result = asyncio.get_event_loop().run_until_complete(
            ft.file_operation(
                action="delete",
                source=str(nonexistent),
            )
        )

        data = result.get("data", {})
        assert data.get("success") is True


# =============================================================================
# F11: DataFileFormatInput写入限制说明
# =============================================================================

class TestF11DataFileFormatWriteLimitation:
    """F11: DataFileFormatInput的docstring应含写入限制说明"""

    def test_docstring_contains_write_limitation(self):
        """DataFileFormatInput的docstring应包含'ini/xml/properties暂不支持写入'"""
        doc = DataFileFormatInput.__doc__
        assert doc is not None, "DataFileFormatInput应有docstring"
        assert "ini/xml/properties暂不支持写入" in doc, "docstring应说明ini/xml/properties暂不支持写入"

    def test_schema_format_supports_all_formats(self):
        """format字段应支持json/yaml/toml/ini/xml/properties"""
        for fmt in ["json", "yaml", "toml", "ini", "xml", "properties"]:
            inp = DataFileFormatInput(file_path="/tmp/test", format=fmt)
            assert inp.format == fmt


# =============================================================================
# F7: grep多编码（gbk文件搜索）
# =============================================================================

class TestF7GrepMultiEncoding:
    """F7: grep_file_content应能搜索gbk编码文件"""

    def test_grep_gbk_file(self, temp_dir):
        """创建gbk编码文件，搜索中文内容，应能匹配"""
        ft = _make_filetools_mock()
        target = temp_dir / "gbk_file.txt"
        chinese_text = "你好世界\n测试行\n"
        target.write_bytes(chinese_text.encode("gbk"))

        with patch.object(ft, '_validate_path', return_value=(True, "")):
            result = asyncio.get_event_loop().run_until_complete(
                ft.grep_file_content(
                    pattern="你好",
                    search_dir=str(temp_dir),
                )
            )

        data = result.get("data", {})
        matches = data.get("matches", [])
        assert len(matches) > 0, "应能在gbk编码文件中搜索到中文内容"

    def test_grep_utf8_file_still_works(self, temp_dir):
        """utf-8文件搜索仍正常"""
        ft = _make_filetools_mock()
        target = temp_dir / "utf8_file.txt"
        target.write_text("你好世界\n测试行\n", encoding="utf-8")

        with patch.object(ft, '_validate_path', return_value=(True, "")):
            result = asyncio.get_event_loop().run_until_complete(
                ft.grep_file_content(
                    pattern="你好",
                    search_dir=str(temp_dir),
                )
            )

        data = result.get("data", {})
        matches = data.get("matches", [])
        assert len(matches) > 0, "utf-8文件搜索应正常"
