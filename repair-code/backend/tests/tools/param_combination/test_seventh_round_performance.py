"""第七轮测试 - 性能退化维度
目标:大文件/内存/超时/并发/ReDoS/O(n^2)算法
创建时间:2026-06-25
"""
import asyncio
import os
import re
import sys
import tempfile
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from app.services.task.task_context import _current_task_id


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


def _write_file(path, content, encoding="utf-8"):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(str(path), "w", encoding=encoding) as f:
        f.write(content)
    return path


# ============================================================
# list_directory 性能退化测试
# ============================================================
class TestListDirectoryPerformance:
    def test_tree_mode_no_timeout(self):
        """PERF-001(适配): tree工具无超时保护验证(原listdir tree=已拆分到独立tree工具)"""
        from app.tools.file.tree import tree
        with tempfile.TemporaryDirectory() as d:
            # 创建深度嵌套目录
            current = Path(d)
            for i in range(15):
                current = current / f"level_{i}"
                current.mkdir()
                for j in range(50):
                    (current / f"file_{j}.txt").write_text(f"content {j}")
            # tree模式应有超时保护
            start = time.time()
            r = _run(tree, path=d)
            elapsed = time.time() - start
            # 应在合理时间内完成
            if elapsed > 12:
                pytest.fail(
                    f"tree工具运行{elapsed:.1f}秒,"
                    f"超出合理时间.可能缺少超时保护."
                    f"目录结构: 15层x50文件/层=750个文件"
                )

    def test_tree_mode_sort_by_size_o_n2(self):
        """PERF-002(适配): tree工具sort_by_size性能(原listdir tree=已拆分到独立tree工具)"""
        from app.tools.file.tree import tree
        with tempfile.TemporaryDirectory() as d:
            # 创建多个子目录,每个有很多文件
            for i in range(10):
                subdir = Path(d) / f"dir_{i}"
                subdir.mkdir()
                for j in range(100):
                    (subdir / f"file_{j}.txt").write_text(f"content {j}" * 10)
            start = time.time()
            r = _run(tree, path=d, sort_by="size")
            elapsed = time.time() - start
            # O(n^2)在数据量大时会很慢
            if elapsed > 8:
                pytest.fail(
                    f"sort_by_size运行{elapsed:.1f}秒,"
                    f"可能存在O(n^2)性能问题."
                    f"目录: 10个子目录x100文件"
                )

    def test_list_5000_files_memory(self):
        """PERF-003: list_directory列出5000个文件的内存使用"""
        from app.tools.file.list_directory import listdir
        with tempfile.TemporaryDirectory() as d:
            for i in range(5000):
                (Path(d) / f"file_{i:04d}.txt").write_text(f"content {i}")
            r = _run(listdir, path=d)
            data = r.get("data", {})
            entries = data.get("entries", [])
            total = r.get("llm_data", {}).get("metrics", {}).get("total", {}).get("value", 0)
            # 门限治理后 truncated 仅反映 deadline 超时截断, 5000文件扫描不超时不标记 — 小欧 2026-07-20
            assert total == 5000, f"total应为5000: {total}"
            assert len(entries) == 5000, f"entries应返回全部: {len(entries)}"


# ============================================================
# grep_file_content 性能退化测试
# ============================================================
class TestGrepPerformance:
    def test_double_file_read(self):
        """PERF-004: grep_file_content大文件双重读取"""
        from app.tools.file.grep_file_content import grep
        with tempfile.TemporaryDirectory() as d:
            # 创建5MB文件
            lines = [f"line {i}: {'x' * 100}\n" for i in range(50000)]
            f = Path(d) / "big.txt"
            f.write_text("".join(lines), encoding="utf-8")
            start = time.time()
            r = _run(grep, pattern="line 1000", path=d)
            elapsed = time.time() - start
            data = r.get("data", {})
            assert data.get("total_matches", 0) >= 1, f"应找到匹配: {data}"
            # 如果双重读取,5MB文件应在1秒内完成
            if elapsed > 3:
                pytest.fail(
                    f"grep搜索5MB文件耗时{elapsed:.1f}秒,"
                    f"可能存在双重读取性能问题."
                )

    def test_grep_redos_pattern(self):
        """PERF-005: grep_file_content ReDoS正则"""
        from app.tools.file.grep_file_content import grep
        with tempfile.TemporaryDirectory() as d:
            # 创建包含大量'a'的文件
            content = "a" * 1000 + "b\n"
            f = Path(d) / "redos.txt"
            f.write_text(content, encoding="utf-8")
            # ReDoS pattern: (a+)+$
            start = time.time()
            r = _run(grep, pattern=r"(a+)+$", path=d)
            elapsed = time.time() - start
            # ReDoS应在超时前终止
            if elapsed > 10:
                pytest.fail(
                    f"ReDoS正则耗时{elapsed:.1f}秒,"
                    f"正则引擎无超时保护."
                    f"输入: 1000个'a' + pattern (a+)+$"
                )

    def test_grep_many_files_timeout(self):
        """PERF-006: grep_file_content搜索大量文件的超时"""
        from app.tools.file.grep_file_content import grep
        with tempfile.TemporaryDirectory() as d:
            for i in range(2000):
                f = Path(d) / f"file_{i:04d}.txt"
                f.write_text(f"content {i}\n" * 10, encoding="utf-8")
            start = time.time()
            r = _run(grep, pattern="content 500", path=d)
            elapsed = time.time() - start
            # 应有deadline保护
            if elapsed > 65:
                pytest.fail(
                    f"grep搜索2000个文件耗时{elapsed:.1f}秒,"
                    f"超出60秒deadline限制."
                )


# ============================================================
# edit_text_file 性能退化测试
# ============================================================
class TestEditPerformance:
    def test_replace_all_large_file(self):
        """PERF-007: edit_text_file replace_all大文件性能"""
        from app.tools.file.edit_text_file import edittext
        with tempfile.TemporaryDirectory() as d:
            # 创建5MB文件
            lines = [f"line {i}: replace_me\n" for i in range(50000)]
            f = Path(d) / "big_edit.txt"
            f.write_text("".join(lines), encoding="utf-8")
            start = time.time()
            r = _run(edittext, path=str(f),
                     old_string="replace_me", new_string="REPLACED", mode="all")
            elapsed = time.time() - start
            if elapsed > 5:
                pytest.fail(
                    f"replace_all处理5MB文件耗时{elapsed:.1f}秒,"
                    f"可能存在O(n*m)性能问题."
                )

    def test_replace_all_output_size_explosion(self):
        """PERF-008: edit_text_file replace_all输出膨胀"""
        from app.tools.file.edit_text_file import edittext
        with tempfile.TemporaryDirectory() as d:
            # 创建文件,每行包含要替换的短字符串
            content = "x\n" * 10000
            f = Path(d) / "expand.txt"
            f.write_text(content, encoding="utf-8")
            # 用很长的字符串替换很短的字符串
            new_str = "Y" * 100  # 100倍膨胀
            r = _run(edittext, path=str(f),
                     old_string="x", new_string=new_str, mode="all")
            # 检查输出文件大小
            if f.exists():
                size = f.stat().st_size
                # 10000行x100字节 = ~1MB,应该可接受
                if size > 2 * 1024 * 1024:  # 2MB
                    pytest.fail(
                        f"replace_all输出膨胀过大: {size}字节."
                        f"输入: 10000x'x\\n'={len(content)}字节"
                        f"输出: 10000x'Y'*100={size}字节"
                    )


# ============================================================
# copy_file/move_file 性能退化测试
# ============================================================
class TestCopyMovePerformance:
    def test_copy_no_timeout(self):
        """PERF-009: copy_file大目录复制无超时"""
        from app.tools.file.copy_file import copy
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "src"
            src.mkdir()
            # 创建1000个文件
            for i in range(1000):
                (src / f"file_{i:04d}.txt").write_text(f"content {i}" * 10)
            dst = Path(d) / "dst"
            start = time.time()
            r = _run(copy, path=str(src), dest=str(dst), recursive=True)
            elapsed = time.time() - start
            # 复制1000个小文件应很快
            if elapsed > 15:
                pytest.fail(
                    f"copy_file复制1000个文件耗时{elapsed:.1f}秒,"
                    f"可能缺少超时保护."
                )

    def test_move_no_timeout(self):
        """PERF-010: move_file大目录移动无超时"""
        from app.tools.file.move_file import move
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "src"
            src.mkdir()
            for i in range(1000):
                (src / f"file_{i:04d}.txt").write_text(f"content {i}" * 10)
            dst = Path(d) / "dst"
            start = time.time()
            r = _run(move, path=str(src), dest=str(dst))
            elapsed = time.time() - start
            if elapsed > 15:
                pytest.fail(
                    f"move_file移动1000个文件耗时{elapsed:.1f}秒,"
                    f"可能缺少超时保护."
                )


# ============================================================
# write_text_file 性能退化测试
# ============================================================
class TestWritePerformance:
    def test_write_large_content_no_limit(self):
        """PERF-011: write_text_file写入大内容无大小限制"""
        from app.tools.file.write_text_file import writetext
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "large.txt"
            # 尝试写入10MB内容
            content = "x" * (10 * 1024 * 1024)
            start = time.time()
            r = _run(writetext, path=str(f), content=content)
            elapsed = time.time() - start
            if is_success(r):
                # 检查是否真的写入了10MB
                if f.exists():
                    size = f.stat().st_size
                    if size < 10 * 1024 * 1024:
                        pytest.fail(f"写入内容被截断: 期望10MB, 实际{size}")
                    # 写入10MB应在合理时间内完成
                    if elapsed > 30:
                        pytest.fail(
                            f"write_text_file写入10MB耗时{elapsed:.1f}秒."
                            f"可能缺少内容大小限制."
                        )


# ============================================================
# read_text_file 性能退化测试
# ============================================================
class TestReadPerformance:
    def test_read_multiple_encoding_full_scan(self):
        """PERF-012: read_text_file多次编码尝试全量扫描"""
        from app.tools.file.read_text_file import readtext
        with tempfile.TemporaryDirectory() as d:
            # 创建5MB UTF-8文件
            lines = [f"line {i}: {'x' * 100}\n" for i in range(50000)]
            f = Path(d) / "multi_enc.txt"
            f.write_text("".join(lines), encoding="utf-8")
            start = time.time()
            r = _run(readtext, path=str(f), offset=0, limit=10)
            elapsed = time.time() - start
            if elapsed > 5:
                pytest.fail(
                    f"read_text_file读取5MB文件耗时{elapsed:.1f}秒,"
                    f"可能存在多次编码尝试全量扫描."
                )

    def test_read_offset_full_split(self):
        """PERF-013: read_text_file offset=100000 limit=10"""
        from app.tools.file.read_text_file import readtext
        with tempfile.TemporaryDirectory() as d:
            # 创建100000行文件
            lines = [f"line {i}\n" for i in range(100000)]
            f = Path(d) / "many_lines.txt"
            f.write_text("".join(lines), encoding="utf-8")
            start = time.time()
            r = _run(readtext, path=str(f), offset=99990, limit=10)
            elapsed = time.time() - start
            # 只读10行但可能需要分割100000行
            if elapsed > 5:
                pytest.fail(
                    f"read_text_file offset=99990 limit=10耗时{elapsed:.1f}秒,"
                    f"可能先分割全部行再取子集."
                )


# ============================================================
# shell 性能退化测试
# ============================================================
class TestShellPerformance:
    def test_background_process_no_limit(self):
        """PERF-014(适配): shell前台命令可重复调用无数量限制(原后台进程功能已移除)

        原background/cleanup参数已删除, 改为验证shell()前台可重复调用
        并返回结构化结果, 不崩溃 - 小欧 2026-07-12
        """
        from app.tools.fundamental.execute_shell_command import shell
        results = []
        for i in range(20):
            r = _run(shell, command="echo hi")
            results.append(r)
        # 所有调用应返回结构化结果(成功或错误), 不崩溃
        for r in results:
            assert is_success(r) or is_error(r), f"shell重复调用应返回结构化结果: {r}"


# ============================================================
# 辅助函数
# ============================================================
def is_error(result):
    if not result:
        return False
    return result.get("llm_data", {}).get("status", {}).get("exec_code") == "error"

def is_warning(result):
    if not result:
        return False
    return result.get("llm_data", {}).get("status", {}).get("exec_code") == "warning"

def is_success(result):
    if not result:
        return False
    return result.get("llm_data", {}).get("status", {}).get("exec_code") == "success"
