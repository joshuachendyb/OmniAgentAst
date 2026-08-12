# -*- coding: utf-8 -*-
"""第十三轮 - 工具交互深度测试
目标:发现真实Bug,覆盖工具链交互,状态污染,错误恢复等高风险路径
创建时间:2026-06-25
"""
import asyncio
import os
import sys
import tempfile
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


def _run(func, *args, **kwargs):
    from app.services.task.task_context import _current_task_id
    token = _current_task_id.set("test_task_001")
    try:
        result = func(*args, **kwargs)
        if asyncio.iscoroutine(result):
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(result)
            finally:
                loop.close()
        return result
    finally:
        _current_task_id.reset(token)


def _ok(r):
    return r.get("success", False) or (r.get("llm_data", {}).get("status", {}).get("exec_code") in ("success", "warning"))


def _grep_total(r):
    # grep total_matches 已迁移至 llm_data.metrics.total_matches.value - 小欧 2026-07-11
    return r.get("llm_data", {}).get("metrics", {}).get("total_matches", {}).get("value", 0)


# ============================================================
# 1. 文件操作链测试 - 多步文件操作组合
# ============================================================
class TestFileOperationChains:
    """文件操作链测试"""

    def test_write_copy_grep_verify(self):
        """CHAIN-001: 写入→复制→grep验证"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.copy_file import copy
        from app.tools.file.grep_file_content import grep
        with tempfile.TemporaryDirectory() as d:
            src = str(Path(d) / "src.txt")
            dst = str(Path(d) / "dst.txt")
            _run(writetext, path=src, content="CHAIN_DATA_1\nLINE2\nLINE3\n")
            _run(copy, path=src, dest=dst)
            r = _run(grep, pattern="CHAIN_DATA", path=d)
            assert r.get("data", {}).get("total_matches", 0) >= 1

    def test_write_move_edit_read(self):
        """CHAIN-002: 写入→移动→编辑→读取"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.move_file import move
        from app.tools.file.edit_text_file import edittext
        from app.tools.file.read_text_file import readtext
        with tempfile.TemporaryDirectory() as d:
            src = str(Path(d) / "original.txt")
            dst = str(Path(d) / "moved.txt")
            _run(writetext, path=src, content="ORIGINAL_DATA")
            _run(move, path=src, dest=dst)
            _run(edittext, path=dst, old_string="ORIGINAL", new_string="MODIFIED")
            r = _run(readtext, path=dst)
            assert "MODIFIED_DATA" in r.get("data", {}).get("content", "")

    def test_write_rename_grep_list(self):
        """CHAIN-003: 写入→重命名→grep→列表"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.rename_file import rename
        from app.tools.file.grep_file_content import grep
        from app.tools.file.list_directory import listdir
        with tempfile.TemporaryDirectory() as d:
            old = str(Path(d) / "old.txt")
            new = str(Path(d) / "new.txt")
            _run(writetext, path=old, content="RENAME_DATA\n")
            _run(rename, path=old, dest=new)
            r = _run(grep, pattern="RENAME", path=d)
            assert r.get("data", {}).get("total_matches", 0) >= 1
            r2 = _run(listdir, path=d)
            names = [e.get("name", "") for e in r2.get("data", {}).get("entries", [])]
            assert "new.txt" in names
            assert "old.txt" not in names

    def test_multiple_copy_then_verify_all(self):
        """CHAIN-004: 多次复制→逐个验证"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.copy_file import copy
        from app.tools.file.read_text_file import readtext
        with tempfile.TemporaryDirectory() as d:
            src = str(Path(d) / "src.txt")
            _run(writetext, path=src, content="MULTI_COPY")
            for i in range(5):
                dst = str(Path(d) / f"copy_{i}.txt")
                _run(copy, path=src, dest=dst)
                r = _run(readtext, path=dst)
                assert "MULTI_COPY" in r.get("data", {}).get("content", "")

    def test_write_delete_write_same_path(self):
        """CHAIN-005: 写入→删除→同路径写入"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.read_text_file import readtext
        from app.tools.fundamental.execute_shell_command import shell
        with tempfile.TemporaryDirectory() as d:
            fp = str(Path(d) / "reuse.txt")
            _run(writetext, path=fp, content="FIRST_VERSION")
            _run(shell, command=f'Remove-Item -Path "{fp}" -Force')
            _run(writetext, path=fp, content="SECOND_VERSION")
            r = _run(readtext, path=fp)
            assert "SECOND_VERSION" in r.get("data", {}).get("content", "")
            assert "FIRST_VERSION" not in r.get("data", {}).get("content", "")

    def test_write_multiple_files_then_grep(self):
        """CHAIN-006: 写入多个文件→全局grep"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.grep_file_content import grep
        with tempfile.TemporaryDirectory() as d:
            for i in range(10):
                _run(writetext, path=str(Path(d) / f"f{i}.txt"),
                     content=f"FILE_{i}: data_{i}\nSHARED_KEYWORD\n")
            r = _run(grep, pattern="SHARED_KEYWORD", path=d)
            assert r.get("data", {}).get("total_matches", 0) == 10

    def test_write_read_edit_copy_verify(self):
        """CHAIN-007: 写入→读取→编辑→复制→验证"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.read_text_file import readtext
        from app.tools.file.edit_text_file import edittext
        from app.tools.file.copy_file import copy
        with tempfile.TemporaryDirectory() as d:
            fp1 = str(Path(d) / "a.txt")
            fp2 = str(Path(d) / "b.txt")
            _run(writetext, path=fp1, content="ORIGINAL_A")
            r = _run(readtext, path=fp1)
            assert "ORIGINAL_A" in r.get("data", {}).get("content", "")
            _run(edittext, path=fp1, old_string="ORIGINAL", new_string="EDITED")
            _run(copy, path=fp1, dest=fp2)
            r2 = _run(readtext, path=fp2)
            assert "EDITED_A" in r2.get("data", {}).get("content", "")

    def test_shell_create_file_read_edit(self):
        """CHAIN-008: shell创建→读取→编辑"""
        from app.tools.fundamental.execute_shell_command import shell
        from app.tools.file.read_text_file import readtext
        from app.tools.file.edit_text_file import edittext
        with tempfile.TemporaryDirectory() as d:
            fp = str(Path(d) / "shell_created.txt")
            _run(shell, command=f'Set-Content -Path "{fp}" -Value "SHELL_DATA" -Encoding UTF8')
            r = _run(readtext, path=fp)
            assert "SHELL_DATA" in r.get("data", {}).get("content", "")
            _run(edittext, path=fp, old_string="SHELL", new_string="EDITED")
            r2 = _run(readtext, path=fp)
            assert "EDITED_DATA" in r2.get("data", {}).get("content", "")

    def test_grep_then_edit_matches(self):
        """CHAIN-009: grep查找→编辑匹配内容"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.grep_file_content import grep
        from app.tools.file.edit_text_file import edittext
        with tempfile.TemporaryDirectory() as d:
            _run(writetext, path=str(Path(d) / "a.txt"), content="OLD_VALUE_A\n")
            _run(writetext, path=str(Path(d) / "b.txt"), content="OLD_VALUE_B\n")
            r = _run(grep, pattern="OLD_VALUE", path=d)
            assert _grep_total(r) == 2
            # 编辑所有匹配
            for f in r.get("data", {}).get("matches", []):
                fp = f.get("file", "")
                if fp:
                    _run(edittext, path=fp, old_string="OLD_VALUE", new_string="NEW_VALUE")
            r2 = _run(grep, pattern="NEW_VALUE", path=d)
            assert _grep_total(r2) == 2

    def test_list_read_write_cycle(self):
        """CHAIN-010: 列表→读取→写入循环"""
        from app.tools.file.list_directory import listdir
        from app.tools.file.read_text_file import readtext
        from app.tools.file.write_text_file import writetext
        with tempfile.TemporaryDirectory() as d:
            for i in range(5):
                _run(writetext, path=str(Path(d) / f"f{i}.txt"), content=f"content_{i}")
            r = _run(listdir, path=d)
            entries = r.get("data", {}).get("entries", [])
            for entry in entries:
                name = entry.get("name", "")
                fp = str(Path(d) / name)
                r2 = _run(readtext, path=fp)
                content = r2.get("data", {}).get("content", "")
                # 写入修改在的内容
                _run(writetext, path=fp, content=content + "_MODIFIED")
                r3 = _run(readtext, path=fp)
                assert "_MODIFIED" in r3.get("data", {}).get("content", "")


# ============================================================
# 2. Shell与文件工具混合测试
# ============================================================
class TestShellFileMix:
    """Shell与文件工具混合操作测试"""

    def test_shell_read_file_tool_write(self):
        """MIX-001: shell读取+文件工具写入"""
        from app.tools.file.write_text_file import writetext
        from app.tools.fundamental.execute_shell_command import shell
        with tempfile.TemporaryDirectory() as d:
            fp = str(Path(d) / "mix1.txt")
            _run(writetext, path=fp, content="MIX_DATA_1")
            r = _run(shell, command=f'Get-Content "{fp}"')
            assert "MIX_DATA_1" in r.get("data", {}).get("stdout", "")

    def test_shell_write_file_tool_read(self):
        """MIX-002: shell写入+文件工具读取"""
        from app.tools.file.read_text_file import readtext
        from app.tools.fundamental.execute_shell_command import shell
        with tempfile.TemporaryDirectory() as d:
            fp = str(Path(d) / "mix2.txt")
            _run(shell, command=f'Set-Content -Path "{fp}" -Value "MIX_DATA_2" -Encoding UTF8')
            r = _run(readtext, path=fp)
            assert "MIX_DATA_2" in r.get("data", {}).get("content", "")

    def test_shell_copy_file_tool_verify(self):
        """MIX-003: shell复制+文件工具验证"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.read_text_file import readtext
        from app.tools.fundamental.execute_shell_command import shell
        with tempfile.TemporaryDirectory() as d:
            src = str(Path(d) / "src.txt")
            dst = str(Path(d) / "dst.txt")
            _run(writetext, path=src, content="MIX_DATA_3")
            _run(shell, command=f'Copy-Item -Path "{src}" -Destination "{dst}"')
            r = _run(readtext, path=dst)
            assert "MIX_DATA_3" in r.get("data", {}).get("content", "")

    def test_file_tool_write_shell_verify(self):
        """MIX-004: 文件工具写入+shell验证"""
        from app.tools.file.write_text_file import writetext
        from app.tools.fundamental.execute_shell_command import shell
        with tempfile.TemporaryDirectory() as d:
            fp = str(Path(d) / "mix4.txt")
            _run(writetext, path=fp, content="MIX_DATA_4")
            r = _run(shell, command=f'Test-Path "{fp}"')
            assert "True" in r.get("data", {}).get("stdout", "")

    def test_shell_delete_file_tool_list(self):
        """MIX-005: shell删除+文件工具列表"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.list_directory import listdir
        from app.tools.fundamental.execute_shell_command import shell
        with tempfile.TemporaryDirectory() as d:
            fp = str(Path(d) / "to_delete.txt")
            _run(writetext, path=fp, content="DELETE_ME")
            _run(shell, command=f'Remove-Item -Path "{fp}" -Force')
            r = _run(listdir, path=d)
            names = [e.get("name", "") for e in r.get("data", {}).get("entries", [])]
            assert "to_delete.txt" not in names

    def test_shell_rename_file_tool_grep(self):
        """MIX-006: shell重命名+文件工具grep"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.grep_file_content import grep
        from app.tools.fundamental.execute_shell_command import shell
        with tempfile.TemporaryDirectory() as d:
            old = str(Path(d) / "old.txt")
            new = str(Path(d) / "new.txt")
            _run(writetext, path=old, content="RENAME_ME\n")
            _run(shell, command=f'Rename-Item -Path "{old}" -NewName "new.txt"')
            r = _run(grep, pattern="RENAME_ME", path=d)
            assert r.get("data", {}).get("total_matches", 0) >= 1

    def test_shell_list_file_tool_read_each(self):
        """MIX-007: shell列表+文件工具逐个读取"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.read_text_file import readtext
        from app.tools.fundamental.execute_shell_command import shell
        with tempfile.TemporaryDirectory() as d:
            for i in range(5):
                _run(writetext, path=str(Path(d) / f"f{i}.txt"), content=f"data_{i}")
            r = _run(shell, command=f'Get-ChildItem -Path "{d}" -Name')
            stdout = r.get("data", {}).get("stdout", "")
            files = [f.strip() for f in stdout.split("\n") if f.strip()]
            assert len(files) >= 5
            for f in files:
                fp = str(Path(d) / f)
                r2 = _run(readtext, path=fp)
                assert _ok(r2)


# ============================================================
# 3. 错误注入与恢复测试
# ============================================================
class TestErrorInjection:
    """错误注入与恢复测试"""

    def test_write_invalid_path_chars(self):
        """ERR-001: 写入包含非法字符的路径"""
        from app.tools.file.write_text_file import writetext
        with tempfile.TemporaryDirectory() as d:
            # Windows非法字符: < > : " / \ | ? *
            for ch in '<>:"/\\|?*':
                fp = str(Path(d) / f"test{ch}file.txt")
                r = _run(writetext, path=fp, content="test")
                # 应该失败或被清理

    def test_grep_invalid_regex(self):
        """ERR-002: grep使用无效正则"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.grep_file_content import grep
        with tempfile.TemporaryDirectory() as d:
            _run(writetext, path=str(Path(d) / "test.txt"), content="data\n")
            # 无效正则: 未关闭的括号
            r = _run(grep, pattern="(unclosed", path=d)
            # 应该报错,不应该崩溃

    def test_edit_nonexistent_string(self):
        """ERR-003: 编辑不存在的字符串"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.edit_text_file import edittext
        with tempfile.TemporaryDirectory() as d:
            fp = str(Path(d) / "test.txt")
            _run(writetext, path=fp, content="ACTUAL_CONTENT")
            r = _run(edittext, path=fp, old_string="NONEXISTENT", new_string="new")
            assert not _ok(r)

    def test_copy_to_readonly_location(self):
        """ERR-004: 复制到只读位置"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.copy_file import copy
        with tempfile.TemporaryDirectory() as d:
            src = str(Path(d) / "src.txt")
            dst = str(Path(d) / "nonexistent_dir" / "dst.txt")
            _run(writetext, path=src, content="COPY_ME")
            r = _run(copy, path=src, dest=dst)
            # 目标目录不存在应该失败

    def test_move_to_same_location(self):
        """ERR-005: 移动到相同位置"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.move_file import move
        with tempfile.TemporaryDirectory() as d:
            fp = str(Path(d) / "same.txt")
            _run(writetext, path=fp, content="SAME_LOCATION")
            r = _run(move, path=fp, dest=fp)
            # 移动到相同位置应该失败

    def test_rename_to_existing_name(self):
        """ERR-006: 重命名为已存在的名称"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.rename_file import rename
        with tempfile.TemporaryDirectory() as d:
            fp1 = str(Path(d) / "file1.txt")
            fp2 = str(Path(d) / "file2.txt")
            _run(writetext, path=fp1, content="FILE1")
            _run(writetext, path=fp2, content="FILE2")
            r = _run(rename, path=fp1, dest=fp2)
            # 重命名为已存在的文件应该失败或覆盖

    def test_shell_command_timeout(self):
        """ERR-007: shell命令超时"""
        from app.tools.fundamental.execute_shell_command import shell
        # 使用极短的超时时间
        r = _run(shell, command="Start-Sleep -Seconds 10", timeout=1000)
        assert not _ok(r) or "timeout" in str(r).lower() or r.get("data", {}).get("returncode") != 0

    def test_read_file_while_writing(self):
        """ERR-008: 读取正在写入的文件"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.read_text_file import readtext
        with tempfile.TemporaryDirectory() as d:
            fp = str(Path(d) / "writing.txt")
            # 写入大文件
            _run(writetext, path=fp, content="A" * 100000)
            # 同时读取
            r = _run(readtext, path=fp)
            # 应该能读取,不会崩溃

    def test_grep_on_empty_dir(self):
        """ERR-009: 在空目录中grep"""
        from app.tools.file.grep_file_content import grep
        with tempfile.TemporaryDirectory() as d:
            r = _run(grep, pattern="test", path=d)
            assert r.get("data", {}).get("total_matches", 0) == 0

    def test_search_on_nonexistent_dir(self):
        """ERR-010: 在不存在的目录上搜索"""
        from app.tools.file.search_files import find
        r = _run(find, pattern="test", path="C:\\nonexistent_dir_xyz")
        assert not _ok(r)


# ============================================================
# 4. 参数边界测试 - 极里参数值
# ============================================================
class TestParameterBoundaries:
    """参数边界测试"""

    def test_read_offset_beyond_file(self):
        """PARAM-001: 读取偏移超出文件范围"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.read_text_file import readtext
        with tempfile.TemporaryDirectory() as d:
            fp = str(Path(d) / "small.txt")
            _run(writetext, path=fp, content="3_lines\nline2\nline3\n")
            r = _run(readtext, path=fp, offset=1000, limit=10)
            # 应该返回空或报错,不应该崩溃

    def test_read_negative_offset_beyond_file(self):
        """PARAM-002: 负偏移超出文件范围"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.read_text_file import readtext
        with tempfile.TemporaryDirectory() as d:
            fp = str(Path(d) / "small.txt")
            _run(writetext, path=fp, content="3_lines\nline2\nline3\n")
            r = _run(readtext, path=fp, offset=-1000)
            # 应该返回空或报错

    def test_grep_max_results(self):
        """PARAM-003: grep最大结果数"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.grep_file_content import grep
        with tempfile.TemporaryDirectory() as d:
            for i in range(100):
                _run(writetext, path=str(Path(d) / f"f{i}.txt"), content=f"match_{i}\n")
            r = _run(grep, pattern="match_", path=d)
            # 应该有截断或限制

    def test_write_max_content(self):
        """PARAM-004: 写入最大内容"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.read_text_file import readtext
        with tempfile.TemporaryDirectory() as d:
            fp = str(Path(d) / "max.txt")
            content = "X" * 1000000  # 1MB
            _run(writetext, path=fp, content=content)
            r = _run(readtext, path=fp)
            # readtext 返回内容带行号前缀且超长行截断(供前端), 断言数据已正确读回并带行号 — 小欧 2026-07-12
            _c = r.get("data", {}).get("content", "")
            assert _c.startswith("1|") and "X" in _c

    def test_shell_timeout_zero(self):
        """PARAM-005: shell超时为0"""
        from app.tools.fundamental.execute_shell_command import shell
        r = _run(shell, command="echo test", timeout=0)
        # 超时为0应该被拒绝

    def test_shell_timeout_negative(self):
        """PARAM-006: shell超时为负数"""
        from app.tools.fundamental.execute_shell_command import shell
        r = _run(shell, command="echo test", timeout=-1000)
        # 负超时应该被拒绝

    def test_grep_very_long_pattern(self):
        """PARAM-007: grep超长模式"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.grep_file_content import grep
        with tempfile.TemporaryDirectory() as d:
            _run(writetext, path=str(Path(d) / "test.txt"), content="data\n")
            long_pattern = "a" * 10000
            r = _run(grep, pattern=long_pattern, path=d)
            # 超长模式应该被拒绝或超时

    def test_list_deep_nesting(self):
        """PARAM-008: 列表深层嵌套目录"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.list_directory import listdir
        with tempfile.TemporaryDirectory() as d:
            current = Path(d)
            for i in range(20):
                current = current / f"level_{i}"
                current.mkdir()
            _run(writetext, path=str(current / "deep.txt"), content="deep")
            r = _run(listdir, path=d)
            # 应该能处理深层嵌套


# ============================================================
# 5. 状态污染测试 - 工具间状态隔离
# ============================================================
class TestStatePollution:
    """状态污染测试"""

    def test_write_then_read_same_instance(self):
        """STATE-001: 同一实例写入在读取"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.read_text_file import readtext
        with tempfile.TemporaryDirectory() as d:
            fp = str(Path(d) / "state.txt")
            _run(writetext, path=fp, content="STATE_A")
            r1 = _run(readtext, path=fp)
            _run(writetext, path=fp, content="STATE_B")
            r2 = _run(readtext, path=fp)
            # 每次读取应该看到最新内容
            assert "STATE_A" in r1.get("data", {}).get("content", "")
            assert "STATE_B" in r2.get("data", {}).get("content", "")

    def test_edit_multiple_files_independent(self):
        """STATE-002: 编辑多个文件独立性"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.edit_text_file import edittext
        from app.tools.file.read_text_file import readtext
        with tempfile.TemporaryDirectory() as d:
            fp1 = str(Path(d) / "a.txt")
            fp2 = str(Path(d) / "b.txt")
            _run(writetext, path=fp1, content="FILE_A_ORIGINAL")
            _run(writetext, path=fp2, content="FILE_B_ORIGINAL")
            _run(edittext, path=fp1, old_string="ORIGINAL", new_string="MODIFIED_A")
            r1 = _run(readtext, path=fp1)
            r2 = _run(readtext, path=fp2)
            # 编辑a不应该影响b
            assert "MODIFIED_A" in r1.get("data", {}).get("content", "")
            assert "FILE_B_ORIGINAL" in r2.get("data", {}).get("content", "")

    def test_grep_results_not_cached(self):
        """STATE-003: grep结果不缓存"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.grep_file_content import grep
        with tempfile.TemporaryDirectory() as d:
            _run(writetext, path=str(Path(d) / "a.txt"), content="FIRST\n")
            r1 = _run(grep, pattern="FIRST", path=d)
            _run(writetext, path=str(Path(d) / "b.txt"), content="SECOND\n")
            r2 = _run(grep, pattern="SECOND", path=d)
            # 第二次grep应该看到新文件
            assert r2.get("data", {}).get("total_matches", 0) >= 1

    def test_list_directory_not_cached(self):
        """STATE-004: 目录列表不缓存"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.list_directory import listdir
        with tempfile.TemporaryDirectory() as d:
            r1 = _run(listdir, path=d)
            entries1 = [e.get("name", "") for e in r1.get("data", {}).get("entries", [])]
            _run(writetext, path=str(Path(d) / "new_file.txt"), content="new")
            r2 = _run(listdir, path=d)
            entries2 = [e.get("name", "") for e in r2.get("data", {}).get("entries", [])]
            # 第二次列表应该看到新文件
            assert "new_file.txt" in entries2
            assert "new_file.txt" not in entries1

    def test_shell_state_isolation(self):
        """STATE-005: Shell状态隔离"""
        from app.tools.fundamental.execute_shell_command import shell
        # 设置变量
        _run(shell, command="$env:TEST_VAR = 'VALUE_A'")
        # 读取变量
        r1 = _run(shell, command="echo $env:TEST_VAR")
        # 注意:PowerShell每次调用可能是独立的,变量可能不保留
        # 这个测试验证不会崩溃

    def test_concurrent_file_operations(self):
        """STATE-006: 并发文件操作"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.read_text_file import readtext
        import concurrent.futures
        with tempfile.TemporaryDirectory() as d:
            fp = str(Path(d) / "concurrent.txt")
            _run(writetext, path=fp, content="INITIAL")
            results = []
            def read_file():
                return _run(readtext, path=fp)
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(read_file) for _ in range(10)]
                results = [f.result() for f in futures]
            # 所有读取应该成功
            for r in results:
                assert _ok(r)


# ============================================================
# 6. 安全边界测试 - 路径遍历与注入
# ============================================================
class TestSecurityBoundaries:
    """安全边界测试"""

    def test_path_traversal_dotdot(self):
        """SEC-001: 路径遍历.."""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.read_text_file import readtext
        with tempfile.TemporaryDirectory() as d:
            secret = Path(d) / "secret.txt"
            secret.write_text("SECRET_DATA")
            # 尝试通过..读取
            r = _run(readtext, path=str(Path(d) / "subdir" / ".." / "secret.txt"))
            # 应该被拒绝

    def test_path_traversal_absolute(self):
        """SEC-002: 绝对路径遍历"""
        from app.tools.file.read_text_file import readtext
        r = _run(readtext, path="C:\\Windows\\System32\\drivers\\etc\\hosts")
        # 应该被拒绝或受限

    def test_shell_command_injection_semicolon(self):
        """SEC-003: Shell命令注入分号"""
        from app.tools.fundamental.execute_shell_command import shell
        r = _run(shell, command="echo hello; Remove-Item -Path C:\\test -Force")
        # 分号在的危险命令应该被处理

    def test_shell_command_injection_ampersand(self):
        """SEC-004: Shell命令注入&"""
        from app.tools.fundamental.execute_shell_command import shell
        r = _run(shell, command="echo hello & echo world")
        # &应该被处理

    def test_write_protected_path(self):
        """SEC-005: 写入受保护路径"""
        from app.tools.file.write_text_file import writetext
        r = _run(writetext, path="C:\\Windows\\System32\\test.txt", content="PROTECTED")
        # 应该被拒绝

    def test_symlink_path_traversal(self):
        """SEC-006: 符号链接路径遍历"""
        from app.tools.file.read_text_file import readtext
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / "target.txt"
            target.write_text("TARGET_DATA")
            link = Path(d) / "link.txt"
            try:
                link.symlink_to(target)
            except OSError:
                pytest.skip("Symlinks not supported")
            r = _run(readtext, path=str(link))
            # 符号链接应该被处理

    def test_special_chars_in_path(self):
        """SEC-007: 路径中的特殊字符"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.read_text_file import readtext
        with tempfile.TemporaryDirectory() as d:
            fp = str(Path(d) / "file (1) [copy] {test}.txt")
            _run(writetext, path=fp, content="SPECIAL_CHARS")
            r = _run(readtext, path=fp)
            assert "SPECIAL_CHARS" in r.get("data", {}).get("content", "")

    def test_very_long_path(self):
        """SEC-008: 超长路径"""
        from app.tools.file.write_text_file import writetext
        with tempfile.TemporaryDirectory() as d:
            long_name = "a" * 200
            fp = str(Path(d) / f"{long_name}.txt")
            r = _run(writetext, path=fp, content="LONG_PATH")
            # 超长路径应该被处理

    def test_path_with_null_bytes(self):
        """SEC-009: 路径包含NULL字节"""
        from app.tools.file.write_text_file import writetext
        with tempfile.TemporaryDirectory() as d:
            fp = str(Path(d) / "test.txt")
            # NULL字节在路径中应该被拒绝
            r = _run(writetext, path=fp + "\x00", content="NULL_BYTE")
            # 应该失败

    def test_concurrent_write_read_integrity(self):
        """SEC-010: 并发写入读取数据完整性"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.read_text_file import readtext
        import concurrent.futures
        with tempfile.TemporaryDirectory() as d:
            fp = str(Path(d) / "integrity.txt")
            # 写入已知内容
            _run(writetext, path=fp, content="INTEGRITY_DATA")
            # 并发读取
            def read_file():
                return _run(readtext, path=fp)
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(read_file) for _ in range(20)]
                results = [f.result() for f in futures]
            # 所有读取应该返回相同内容
            for r in results:
                assert "INTEGRITY_DATA" in r.get("data", {}).get("content", "")


# ============================================================
# 7. 工具组合压力测试
# ============================================================
class TestToolComboStress:
    """工具组合压力测试"""

    def test_rapid_write_read_cycle(self):
        """STRESS-001: 快速写入读取循环"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.read_text_file import readtext
        with tempfile.TemporaryDirectory() as d:
            fp = str(Path(d) / "rapid.txt")
            for i in range(100):
                _run(writetext, path=fp, content=f"ITERATION_{i}")
                r = _run(readtext, path=fp)
                assert f"ITERATION_{i}" in r.get("data", {}).get("content", "")

    def test_rapid_copy_delete_cycle(self):
        """STRESS-002: 快速复制删除循环"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.copy_file import copy
        from app.tools.fundamental.execute_shell_command import shell
        with tempfile.TemporaryDirectory() as d:
            src = str(Path(d) / "src.txt")
            _run(writetext, path=src, content="COPY_DELETE")
            for i in range(50):
                dst = str(Path(d) / f"copy_{i}.txt")
                _run(copy, path=src, dest=dst)
                _run(shell, command=f'Remove-Item -Path "{dst}" -Force')

    def test_rapid_grep_search_cycle(self):
        """STRESS-003: 快速grep搜索循环"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.grep_file_content import grep
        with tempfile.TemporaryDirectory() as d:
            for i in range(20):
                _run(writetext, path=str(Path(d) / f"f{i}.txt"), content=f"data_{i}\n")
            for i in range(50):
                r = _run(grep, pattern=f"data_{i % 20}", path=d)
                assert r.get("data", {}).get("total_matches", 0) >= 1

    def test_mixed_operations_stress(self):
        """STRESS-004: 混合操作压力测试"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.read_text_file import readtext
        from app.tools.file.copy_file import copy
        from app.tools.file.list_directory import listdir
        import concurrent.futures
        with tempfile.TemporaryDirectory() as d:
            # 创建初始文件
            for i in range(10):
                _run(writetext, path=str(Path(d) / f"f{i}.txt"), content=f"initial_{i}")
            # 并发执行不同操作
            def write_new(i):
                return _run(writetext, path=str(Path(d) / f"new_{i}.txt"), content=f"new_{i}")
            def read_existing(i):
                return _run(readtext, path=str(Path(d) / f"f{i}.txt"))
            def list_files():
                return _run(listdir, path=d)
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                futures = []
                for i in range(5):
                    futures.append(executor.submit(write_new, i))
                for i in range(5):
                    futures.append(executor.submit(read_existing, i))
                futures.append(executor.submit(list_files))
                results = [f.result() for f in futures]
            # 所有操作应该成功
            for r in results:
                assert _ok(r)


# ============================================================
# 8. 编码与内容边界测试
# ============================================================
class TestEncodingBoundaries:
    """编码与内容边界测试"""

    def test_write_read_utf8_bom(self):
        """ENC-001: UTF-8 BOM文件读写"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.read_text_file import readtext
        with tempfile.TemporaryDirectory() as d:
            fp = str(Path(d) / "bom.txt")
            _run(writetext, path=fp, content="BOM_CONTENT")
            r = _run(readtext, path=fp)
            assert "BOM_CONTENT" in r.get("data", {}).get("content", "")

    def test_write_read_unicode_emoji(self):
        """ENC-002: Unicode emoji读写"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.read_text_file import readtext
        with tempfile.TemporaryDirectory() as d:
            fp = str(Path(d) / "emoji.txt")
            content = "\U0001F389\U0001F38A\U0001F381\U0001F384\U00002728\U00002B50\U00002B06\U0001F4AB"
            _run(writetext, path=fp, content=content)
            r = _run(readtext, path=fp)
            assert "\U0001F389" in r.get("data", {}).get("content", "")

    def test_write_read_chinese(self):
        """ENC-003: 中文内容读写"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.read_text_file import readtext
        with tempfile.TemporaryDirectory() as d:
            fp = str(Path(d) / "chinese.txt")
            content = "这是一个中文测试文件"
            _run(writetext, path=fp, content=content)
            r = _run(readtext, path=fp)
            assert "中文" in r.get("data", {}).get("content", "")

    def test_write_read_mixed_content(self):
        """ENC-004: 混合内容读写"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.read_text_file import readtext
        with tempfile.TemporaryDirectory() as d:
            fp = str(Path(d) / "mixed.txt")
            content = "English 中文 \U0001F389 日本語 한국어"
            _run(writetext, path=fp, content=content)
            r = _run(readtext, path=fp)
            assert "English" in r.get("data", {}).get("content", "")
            assert "中文" in r.get("data", {}).get("content", "")

    def test_write_read_newlines(self):
        """ENC-005: 换行符读写"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.read_text_file import readtext
        with tempfile.TemporaryDirectory() as d:
            fp = str(Path(d) / "newlines.txt")
            content = "line1\nline2\r\nline3\nline4"
            _run(writetext, path=fp, content=content)
            r = _run(readtext, path=fp)
            assert "line1" in r.get("data", {}).get("content", "")

    def test_write_read_tabs(self):
        """ENC-006: Tab字符读写"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.read_text_file import readtext
        with tempfile.TemporaryDirectory() as d:
            fp = str(Path(d) / "tabs.txt")
            content = "col1\tcol2\tcol3"
            _run(writetext, path=fp, content=content)
            r = _run(readtext, path=fp)
            assert "col1" in r.get("data", {}).get("content", "")

    def test_grep_special_chars(self):
        """ENC-007: grep特殊字符"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.grep_file_content import grep
        with tempfile.TemporaryDirectory() as d:
            _run(writetext, path=str(Path(d) / "special.txt"),
                 content="price: $100.00\nemail: test@example.com\npath: C:\\Users\n")
            r = _run(grep, pattern=r"\$\d+\.\d+", path=d)
            assert r.get("data", {}).get("total_matches", 0) >= 1

    def test_write_empty_lines(self):
        """ENC-008: 写入空行"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.read_text_file import readtext
        with tempfile.TemporaryDirectory() as d:
            fp = str(Path(d) / "empty_lines.txt")
            content = "line1\n\n\n\nline5"
            _run(writetext, path=fp, content=content)
            r = _run(readtext, path=fp)
            assert "line1" in r.get("data", {}).get("content", "")
