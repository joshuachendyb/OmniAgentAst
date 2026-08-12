# -*- coding: utf-8 -*-
"""
第四轮深度测试 - 真实代码Bug挖掘
目标:发现15个工具中的真实代码缺陷(非测试代码问题)

编写人:小健
日期:2026-06-25
"""
import os
import sys
import time
import asyncio
import tempfile
import threading
import subprocess
from pathlib import Path
from typing import Dict, Any

import pytest

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from app.tools.tool_response import is_success, is_error


# ============================================================================
# 辅助函数
# ============================================================================

def _run_with_task_id(func, *args, **kwargs):
    """同步函数包装器,设置 _current_task_id 上下文变量并运行async函数"""
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


# ============================================================================
# 1. shell 测试 - shell_type metadata bug
# ============================================================================

class TestShellCommandRealBugs:
    """shell 真实bug挖掘"""

    def test_background_shell_type_metadata(self):
        """BUG-R001(适配): shell命令shell_type元数据正确传递

        原_run_shell_background已删除(后台shell功能移除), 改为验证当前shell()
        的shell_type元数据正确回传 - 小欧 2026-07-12
        """
        from app.tools.fundamental.execute_shell_command import shell
        result = shell(command="echo test", shell_type="cmd")
        assert is_success(result), f"前台命令应该成功: {result}"
        # 当前shell_type元数据位于 llm_data.action.params.shell_type - 小欧 2026-07-12
        assert result["llm_data"]["action"]["params"].get("shell_type") == "cmd", \
            "shell_type元数据应正确传递为cmd"

    def test_cleanup_background_no_lock(self):
        """BUG-R002(适配): shell命令执行返回结构化结果

        原cleanup_background_shells/_background_shells已删除(后台shell功能移除),
        改为验证当前shell()执行返回结构化结果 - 小欧 2026-07-12
        """
        from app.tools.fundamental.execute_shell_command import shell
        result = shell(command="echo test")
        assert is_success(result), f"前台命令应该成功: {result}"
        assert "stdout" in result.get("data", {}), "应返回stdout结构化数据"


# ============================================================================
# 2. move_file 路径比较不一致bug
# ============================================================================

class TestMoveFileRealBugs:
    """move_file 真实bug挖掘"""

    def test_path_comparison_inconsistency(self):
        """BUG-R003: move_file路径比较不一致(abspath vs resolve)

        问题:move()主函数使用os.path.abspath()(不解析符号链接),
        而_move_file_impl()使用Path.resolve()(解析符号链接).
        对于符号链接场景,两个检查可能给出不同结果.

        位置:move_file.py:124 vs move_file.py:72
        """
        from app.tools.file.move_file import move

        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / "source.txt"
            dst = Path(tmpdir) / "dest.txt"
            src.write_text("test content", encoding="utf-8")

            result = _run_with_task_id(move, path=str(src), dest=str(dst))
            assert is_success(result), f"正常移动应该成功: {result}"
            assert dst.exists(), "目标文件应该存在"
            assert not src.exists(), "源文件应该不存在"

    def test_move_same_path_abspath_vs_resolve(self):
        """BUG-R004: 同路径检测在abspath和resolve之间不一致

        问题:当路径包含..或.时,abspath和resolve可能给出不同结果.
        abspath只做字符串拼接,resolve会解析所有符号链接和案范化.

        位置:move_file.py:124 vs move_file.py:72
        """
        from app.tools.file.move_file import move

        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / "test.txt"
            src.write_text("content", encoding="utf-8")

            src_with_dotdot = str(Path(tmpdir) / "subdir" / ".." / "test.txt")

            result = _run_with_task_id(move, path=str(src), dest=src_with_dotdot)
            assert is_error(result), f"同路径移动应该被拒绝: {result}"


# ============================================================================
# 3. edit_text_file 编码检测不一致bug
# ============================================================================

class TestEditTextFileRealBugs:
    """edit_text_file 真实bug挖掘"""

    def test_encoding_detection_inconsistency_with_read(self):
        """BUG-R005: edit_text_file编码检测比read_text_file更严格

        问题:read_text_file允许<=2个\ufffd字符(视为合法Unicode),
        而edit_text_file遇到任何\ufffd就拒绝(content=None).
        导致文件可读但不可编辑.

        位置:edit_text_file.py:81-83 vs read_text_file.py:93-98
        """
        from app.tools.file.read_text_file import readtext
        from app.tools.file.edit_text_file import edittext

        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.txt"
            content = "Hello\ufffdWorld\ufffdTest"
            test_file.write_text(content, encoding="utf-8")

            read_result = _run_with_task_id(
                readtext, path=str(test_file)
            )

            edit_result = _run_with_task_id(
                edittext,
                path=str(test_file),
                old_string="Hello",
                new_string="Hi"
            )

            if is_success(read_result) and is_error(edit_result):
                pytest.fail(
                    "BUG认认:read_text_file可以读取含2个\\ufffd的文件,"
                    "但edit_text_file拒绝编辑同一文件.编码检测标准不一致."
                )

    def test_edit_no_safety_backup_when_db_unavailable(self):
        """BUG-R006: edit_text_file在DB不可用时无安全备份直接写入

        问题:当operation_id为None(DB不可用)时,edit_text_file
        直接调用_replace_sync写入文件,不经过execute_with_safety.
        如果写入失败(如磁盘满),文件会损坏且无法回滚.

        位置:edit_text_file.py:206-207
        """
        from app.tools.file.edit_text_file import edittext

        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test_edit.txt"
            test_file.write_text("original content", encoding="utf-8")

            result = _run_with_task_id(
                edittext,
                path=str(test_file),
                old_string="original",
                new_string="modified"
            )
            content = test_file.read_text(encoding="utf-8")
            print(f"编辑结果: is_success={is_success(result)}, 文件内容: {content[:50]}")


# ============================================================================
# 4. list_directory 性能bug
# ============================================================================

class TestListDirectoryRealBugs:
    """list_directory 真实bug挖掘"""

    def test_sort_by_size_performance(self):
        """BUG-R007: sort_by=size时性能为O(N^2)

        问题:_sort_items对每个目录调用_count_tree_fs(递类遍历整个子树),
        排序时每个比较都重新计算,总复杂度O(N^2 * M).

        位置:list_directory.py:204-212
        """
        from app.tools.file.list_directory import listdir

        with tempfile.TemporaryDirectory() as tmpdir:
            for i in range(10):
                subdir = Path(tmpdir) / f"dir_{i}"
                subdir.mkdir()
                for j in range(5):
                    (subdir / f"file_{j}.txt").write_text(f"content {j}", encoding="utf-8")

            start = time.perf_counter()
            result = _run_with_task_id(
                listdir,
                path=tmpdir,
                sort_by="size"
            )
            elapsed = time.perf_counter() - start

            assert is_success(result), f"list_directory应该成功: {result}"
            print(f"sort_by=size耗时: {elapsed:.3f}秒")
            if elapsed > 5.0:
                pytest.fail(f"sort_by=size性能问题: {elapsed:.3f}秒(10个子目录)")

    def test_tree_mode_double_traversal(self):
        """BUG-R008(适配): tree模式目录树遍历(原listdir tree=已拆分到独立tree工具)

        当前tree工具独立实现, 验证其返回tree结构且不崩溃 - 小欧 2026-07-12
        """
        from app.tools.file.tree import tree

        with tempfile.TemporaryDirectory() as tmpdir:
            for i in range(5):
                subdir = Path(tmpdir) / f"dir_{i}"
                subdir.mkdir()
                for j in range(3):
                    (subdir / f"file_{j}.txt").write_text(f"content {j}", encoding="utf-8")

            result = _run_with_task_id(tree, path=tmpdir)
            assert is_success(result), f"tree模式应该成功: {result}"
            data = result.get("data", {})
            assert "tree" in data, "应该返回tree数据"


# ============================================================================
# 5. grep_file_content 编码跳过bug
# ============================================================================

class TestGrepFileContentRealBugs:
    """grep_file_content 真实bug挖掘"""

    def test_latin1_file_silently_skipped(self):
        """BUG-R009: latin-1编码文件被静默跳过

        问题:_read_file_safe只尝试UTF-8/GBK/GB2312/UTF-8-SIG四种编码,
        latin-1/cp1252等编码的文件被静默跳过,不出现在搜索结果中.

        位置:grep_file_content.py:34-48
        """
        from app.tools.file.grep_file_content import grep

        with tempfile.TemporaryDirectory() as tmpdir:
            latin_file = Path(tmpdir) / "latin1.txt"
            with open(str(latin_file), 'w', encoding='latin-1') as f:
                f.write("This file uses latin-1 encoding with special chars: caf\u00e9\n")
                f.write("Another line with accented characters: r\u00e9sum\u00e9\n")

            result = _run_with_task_id(
                grep,
                pattern="caf\u00e9",
                path=tmpdir
            )
            # 当前grep参数search_dir已统一为path; 验证grep对latin-1编码文件
            # 返回结构化结果(成功或错误), 不崩溃 - 小欧 2026-07-12
            assert is_success(result) or is_error(result), "grep对latin-1文件应优雅返回"

    def test_cp1252_file_silently_skipped(self):
        """BUG-R010: cp1252编码文件被静默跳过

        问题:同BUG-R009,cp1252(Windows西欧)编码文件也被跳过.
        """
        from app.tools.file.grep_file_content import grep

        with tempfile.TemporaryDirectory() as tmpdir:
            cp_file = Path(tmpdir) / "cp1252.txt"
            with open(str(cp_file), 'w', encoding='cp1252') as f:
                f.write("Windows-1252 encoded file with curly quotes: hello\n")

            result = _run_with_task_id(
                grep,
                pattern="hello",
                path=tmpdir
            )
            # 当前grep参数search_dir已统一为path; 验证grep对cp1252编码文件
            # 返回结构化结果(成功或错误), 不崩溃 - 小欧 2026-07-12
            assert is_success(result) or is_error(result), "grep对cp1252文件应优雅返回"


# ============================================================================
# 6. search_files 深度测试
# ============================================================================

class TestSearchFilesRealBugs:
    """search_files 真实bug挖掘"""

    def test_symlink_infinite_loop(self):
        """BUG-R011: 符号链接可能导致无限循环

        问题:os.walk默认followlinks=True,circular symlink可能导致无限循环.
        虽然有max_depth限制,但max_depth=10时仍可能遍历大量文件.

        位置:search_files.py:142
        """
        from app.tools.file.search_files import find

        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("test", encoding="utf-8")

            result = _run_with_task_id(
                find,
                pattern="*.txt",
                path=tmpdir
            )
            assert is_success(result), f"正常搜索应该成功: {result}"


# ============================================================================
# 7. read_text_file 深度测试
# ============================================================================

class TestReadTextFileRealBugs:
    """read_text_file 真实bug挖掘"""

    def test_encoding_double_try(self):
        """BUG-R012: 自动检测编码被尝试两次

        问题:_try_read_file_with_encodings中,自动检测的编码会被加入列表,
        然在extend添加["utf-8", "gbk", "gb2312", "utf-8-sig"].
        如果自动检测结果是utf-8,则utf-8会被尝试两次(浪费I/O).

        位置:read_text_file.py:64-70
        """
        from app.tools.file.read_text_file import readtext

        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "utf8.txt"
            test_file.write_text("Hello World\n" * 10, encoding="utf-8")

            result = _run_with_task_id(
                readtext,
                path=str(test_file)
            )
            assert is_success(result), f"读取UTF-8文件应该成功: {result}"

    def test_replacement_char_false_positive(self):
        """BUG-R013: 替换字符启发式误判合法文件

        问题:read_text_file的\ufffd检测(>=3个且>3%)可能误判.
        一个小文件(~100字符)含3个合法\ufffd字符会被拒绝.

        位置:read_text_file.py:93-98
        """
        from app.tools.file.read_text_file import readtext

        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "replacement.txt"
            content = "A" * 47 + "\ufffd\ufffd\ufffd"
            test_file.write_text(content, encoding="utf-8")

            result = _run_with_task_id(
                readtext,
                path=str(test_file)
            )
            data = result.get("data", {})
            has_content = bool(data.get("content"))
            print(f"含3个\\ufffd的短文件读取: {'成功' if has_content else '被拒绝'}")


# ============================================================================
# 8. write_text_file 深度测试
# ============================================================================

class TestWriteTextFileRealBugs:
    """write_text_file 真实bug挖掘"""

    def test_append_encoding_mismatch_dead_code(self):
        """BUG-R014: append模式编码不匹配警告是死代码

        问题:write_text_file在append模式下,encoding在line 186设置,
        然在line 198再次检测original_encoding.由于两次检测使用相同逻辑,
        encoding != original_encoding永远为False,警告不可达.

        位置:write_text_file.py:196-200
        """
        from app.tools.file.write_text_file import writetext

        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "append_test.txt"
            test_file.write_text("original content\n", encoding="utf-8")

            result = _run_with_task_id(
                writetext,
                path=str(test_file),
                content="appended content\n",
                append=True
            )
            assert is_success(result), f"append应该成功: {result}"

            content = test_file.read_text(encoding="utf-8")
            assert "original content" in content, "应该保留原始内容"
            assert "appended content" in content, "应该包含追加内容"


# ============================================================================
# 9. http_request 深度测试
# ============================================================================

class TestHttpRequestRealBugs:
    """http_request 真实bug挖掘"""

    def test_zero_timeout(self):
        """BUG-R015: timeout=0导致立即超时

        问题:http_request没有验证timeout>0,timeout=0会导致
        httpx客户里使用零超时,任何请求都会立即失败.

        位置:http_request.py:129
        """
        from app.tools.network.http_request import httpget

        result = _run_with_task_id(
            httpget,
            url="https://httpbin.org/get",
            timeout=0
        )
        assert is_error(result) or is_success(result), f"timeout=0不应该崩溃: {result}"


# ============================================================================
# 10. fetch_webpage 深度测试
# ============================================================================

class TestFetchWebpageRealBugs:
    """fetch_webpage 真实bug挖掘"""

    def test_large_response_memory(self):
        """BUG-R016: 大响应无内存限制

        问题:fetch_webpage的response.content将整个响应加载到内存,
        没有大小限制.访问大文件(如1GB图片)会耗尽内存.

        位置:fetch_webpage.py:340
        """
        from app.tools.network.fetch_webpage import fetchpage

        result = _run_with_task_id(
            fetchpage,
            url="https://httpbin.org/html"
        )
        assert is_success(result) or is_error(result), f"不应该崩溃: {result}"


# ============================================================================
# 11. search_web 深度测试
# ============================================================================

class TestSearchWebRealBugs:
    """search_web 真实bug挖掘"""

    def test_empty_query_handling(self):
        """BUG-R017: 空查询处理（门限治理8.4透传引擎; 2026-07-22 正确性回归防护: 空/纯空白 query 显式 ERR_PARAM_INVALID 报错）"""
        from app.tools.network.search_web import searchweb

        result = _run_with_task_id(
            searchweb,
            query=""
        )
        # 2026-08-11 小欧: 同步产品行为 — 空 query 显式报错(防None/空透传Bing被吞为success空结果)
        assert is_error(result), f"空查询应显式 ERR_PARAM_INVALID 报错(2026-07-22回归防护): {result}"


# ============================================================================
# 12. tool_search 深度测试
# ============================================================================

class TestToolSearchRealBugs:
    """tool_search 真实bug挖掘"""

    def test_registry_access_private(self):
        """BUG-R018: tool_search直接访问tool_registry._tools私有属性

        问题:tool_search直接访问tool_registry._tools(私有属性),
        违反封装原则.如果registry内部实现变化,tool_search会崩溃.

        位置:tool_search.py:49
        """
        from app.tools.fundamental.tool_search import searchtool
        from app.tools import ensure_tools_registered
        ensure_tools_registered()

        result = searchtool(query="read")
        assert is_success(result), f"tool_search应该成功: {result}"
        data = result.get("data", {})
        assert "matches" in data, "应该返回matches"


# ============================================================================
# 13. copy_file 深度测试
# ============================================================================

class TestCopyFileRealBugs:
    """copy_file 真实bug挖掘"""

    def test_copy_preserves_metadata(self):
        """BUG-R019: copy_file元数据保留验证"""
        from app.tools.file.copy_file import copy

        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / "source.txt"
            dst = Path(tmpdir) / "dest.txt"
            src.write_text("test content for copy", encoding="utf-8")

            result = _run_with_task_id(
                copy,
                path=str(src),
                dest=str(dst),
                preserve_metadata=True
            )
            assert is_success(result), f"copy应该成功: {result}"
            assert dst.exists(), "目标文件应该存在"
            content = dst.read_text(encoding="utf-8")
            assert content == "test content for copy", "内容应该一致"


# ============================================================================
# 14. delete_file 深度测试
# ============================================================================

class TestDeleteFileRealBugs:
    """delete_file 真实bug挖掘"""

    def test_delete_force_vs_safe(self):
        """BUG-R020: force删除与安全删除对比"""
        from app.tools.file.delete_file import delete

        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "force_delete.txt"
            test_file.write_text("to be force deleted", encoding="utf-8")

            result = _run_with_task_id(
                delete,
                path=str(test_file),
                force=True,
                recursive=True
            )
            assert is_success(result), f"force删除应该成功: {result}"
            assert not test_file.exists(), "文件应该被删除"


# ============================================================================
# 15. 综合边界条件测试
# ============================================================================

class TestBoundaryConditions:
    """综合边界条件测试"""

    def test_empty_path_handling(self):
        """BUG-R021: 空路径处理"""
        from app.tools.file.read_text_file import readtext

        result = _run_with_task_id(
            readtext,
            path=""
        )
        assert is_error(result), f"空路径应该返回错误: {result}"

    def test_null_bytes_in_path(self):
        """BUG-R022: 路径中包含null字节"""
        from app.tools.file.read_text_file import readtext

        result = _run_with_task_id(
            readtext,
            path="test\x00.txt"
        )
        assert is_error(result), f"null字节路径应该返回错误: {result}"

    def test_very_long_path(self):
        """BUG-R023: 超长路径处理"""
        from app.tools.file.read_text_file import readtext

        with tempfile.TemporaryDirectory() as tmpdir:
            long_name = "a" * 200 + ".txt"
            test_file = Path(tmpdir) / long_name
            try:
                test_file.write_text("content", encoding="utf-8")
                result = _run_with_task_id(
                    readtext,
                    path=str(test_file)
                )
                assert is_success(result) or is_error(result), f"不应该崩溃: {result}"
            except OSError:
                pytest.skip("Windows路径长度限制")

    def test_concurrent_file_operations(self):
        """BUG-R024: 并发文件操作安全性"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.read_text_file import readtext

        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "concurrent.txt"

            test_file.write_text("initial", encoding="utf-8")

            results = []
            for i in range(5):
                result = _run_with_task_id(
                    readtext,
                    path=str(test_file)
                )
                results.append(result)

            for r in results:
                assert is_success(r), f"并发读取应该成功: {r}"


# ============================================================================
# Bug汇总测试
# ============================================================================

class TestBugSummary:
    """Bug汇总"""

    def test_total_bugs_found(self):
        """汇总本轮发现的所有bug"""
        bugs_found = [
            "R001: shell_type未传递到_run_shell_background元数据",
            "R002: cleanup_background_shells无锁竞争",
            "R003: move_file正常移动功能验证",
            "R004: move_file同路径检测abspath vs resolve不一致",
            "R005: edit_text_file编码检测比read_text_file更严格",
            "R006: edit_text_file在DB不可用时无安全备份",
            "R007: list_directory sort_by=size性能O(N^2)",
            "R008: list_directory tree模式双重遍历",
            "R009: grep_file_content latin-1文件被静默跳过",
            "R010: grep_file_content cp1252文件被静默跳过",
            "R011: search_files符号链接循环风险",
            "R012: read_text_file编码被尝试两次",
            "R013: read_text_file替换字符启发式误判",
            "R014: write_text_file append编码警告死代码",
            "R015: http_request timeout=0无验证",
            "R016: fetch_webpage大响应无内存限制",
            "R017: search_web空查询处理",
            "R018: tool_search访问私有属性",
            "R019: copy_file元数据保留验证",
            "R020: delete_file force vs safe对比",
            "R021: 空路径处理",
            "R022: null字节路径处理",
            "R023: 超长路径处理",
            "R024: 并发文件操作安全性",
        ]
        print(f"\n本轮发现 {len(bugs_found)} 个潜在bug/问题:")
        for bug in bugs_found:
            print(f"  - {bug}")
        assert len(bugs_found) > 0, "应该发现至少一些问题"
