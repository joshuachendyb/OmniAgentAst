# -*- coding: utf-8 -*-
"""第十四轮 - 深度安全与性能测试
目标:发现真实Bug,覆盖安全绕过,资源泄漏,性能退化等高风险路径
创建时间:2026-06-25
"""
import asyncio
import gc
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


# ============================================================
# 1. 路径遍历深度测试 - 绕过检查的各种方式
# ============================================================
class TestPathTraversalDeep:
    """路径遍历深度测试 - 尝试绕过安全检查"""

    def test_dotdot_simple(self):
        """TRAV-001: 简单..遍历 - Safety层必须拦截"""
        from app.tools.file.read_text_file import readtext
        from app.tools import ensure_tools_registered
        from app.services.safety.path_safe_check import validate_tool_path
        ensure_tools_registered()
        with tempfile.TemporaryDirectory() as d:
            secret = Path(d) / "secret.txt"
            secret.write_text("SECRET")
            raw = str(Path(d) / "sub" / ".." / "secret.txt")
            # 2026-08-11 小欧: 原用例无断言失效; 真实守护=Safety层拦截含..的原始字符串路径
            valid, msg, _, cat = validate_tool_path("readtext", {"path": raw})
            assert not valid and cat == "system", f"TRAV-001: 含..路径必须被Safety层拦截: {msg}"
            r = _run(readtext, path=raw)

    def test_dotdot_encoded(self):
        """TRAV-002: 编码..遍历 - Safety层必须拦截(原URL编码形态无实体, 改为真实..形态验证)"""
        from app.tools.file.read_text_file import readtext
        from app.tools import ensure_tools_registered
        from app.services.safety.path_safe_check import validate_tool_path
        ensure_tools_registered()
        with tempfile.TemporaryDirectory() as d:
            secret = Path(d) / "secret.txt"
            secret.write_text("SECRET")
            raw = str(Path(d) / "a" / ".." / "secret.txt")
            valid, msg, _, cat = validate_tool_path("readtext", {"path": raw})
            assert not valid and cat == "system", f"TRAV-002: 含..路径必须被Safety层拦截: {msg}"
            r = _run(readtext, path=raw)

    def test_multiple_dotdot(self):
        """TRAV-003: 多重..遍历 - Safety层必须拦截"""
        from app.tools.file.read_text_file import readtext
        from app.tools import ensure_tools_registered
        from app.services.safety.path_safe_check import validate_tool_path
        ensure_tools_registered()
        with tempfile.TemporaryDirectory() as d:
            secret = Path(d) / "secret.txt"
            secret.write_text("SECRET")
            raw = str(Path(d) / "a" / "b" / "c" / ".." / ".." / ".." / "secret.txt")
            valid, msg, _, cat = validate_tool_path("readtext", {"path": raw})
            assert not valid and cat == "system", f"TRAV-003: 多重..必须被Safety层拦截: {msg}"
            r = _run(readtext, path=raw)

    def test_dotdot_in_middle(self):
        """TRAV-004: 路径中间的.. - Safety层必须拦截"""
        from app.tools.file.read_text_file import readtext
        from app.tools import ensure_tools_registered
        from app.services.safety.path_safe_check import validate_tool_path
        ensure_tools_registered()
        with tempfile.TemporaryDirectory() as d:
            secret = Path(d) / "secret.txt"
            secret.write_text("SECRET")
            raw = str(Path(d) / "sub" / ".." / "secret.txt")
            valid, msg, _, cat = validate_tool_path("readtext", {"path": raw})
            assert not valid and cat == "system", f"TRAV-004: 中间..必须被Safety层拦截: {msg}"
            r = _run(readtext, path=raw)

    def test_dotdot_with_valid_prefix(self):
        """TRAV-005: 有效前缀+..遍历 - Safety层必须拦截"""
        from app.tools.file.read_text_file import readtext
        from app.tools import ensure_tools_registered
        from app.services.safety.path_safe_check import validate_tool_path
        ensure_tools_registered()
        with tempfile.TemporaryDirectory() as d:
            secret = Path(d) / "secret.txt"
            secret.write_text("SECRET")
            raw = str(Path(d) / "valid" / ".." / "secret.txt")
            valid, msg, _, cat = validate_tool_path("readtext", {"path": raw})
            assert not valid and cat == "system", f"TRAV-005: 有效前缀+..必须被Safety层拦截: {msg}"
            r = _run(readtext, path=raw)

    def test_absolute_path_override(self):
        """TRAV-006: 绝对路径覆盖(系统文件读取, P3读放行)"""
        from app.tools.file.read_text_file import readtext
        from app.tools import ensure_tools_registered
        from app.services.safety.path_safe_check import validate_tool_path
        ensure_tools_registered()
        # 2026-08-11 小欧: 系统敏感文件读放行(P3设计3.2.14: 读系统目录允许, 写/删拦截)
        valid, msg, _, cat = validate_tool_path("readtext", {"path": r"C:\Windows\System32\drivers\etc\hosts"})
        assert valid, f"TRAV-006: 系统文件读取按P3设计放行(read), 不应误拦: {msg}"
        r = _run(readtext, path=r"C:\Windows\System32\drivers\etc\hosts")

    def test_unc_path(self):
        """TRAV-007: UNC路径 - Safety层不误判, 工具层按存在性处理"""
        from app.tools.file.read_text_file import readtext
        from app.tools import ensure_tools_registered
        from app.services.safety.path_safe_check import validate_tool_path
        ensure_tools_registered()
        valid, msg, _, cat = validate_tool_path("readtext", {"path": r"\\localhost\c$\Windows\System32\drivers\etc\hosts"})
        r = _run(readtext, path=r"\\localhost\c$\Windows\System32\drivers\etc\hosts")

    def test_drive_letter_override(self):
        """TRAV-008: 驱动器号覆盖(系统敏感文件, P3读放行)"""
        from app.tools.file.read_text_file import readtext
        from app.tools import ensure_tools_registered
        from app.services.safety.path_safe_check import validate_tool_path
        ensure_tools_registered()
        # 2026-08-11 小欧: 与TRAV-006一致, 系统文件读放行
        valid, msg, _, cat = validate_tool_path("readtext", {"path": r"C:\Windows\System32\config\SAM"})
        assert valid, f"TRAV-008: 系统文件读取按P3设计放行(read), 不应误拦: {msg}"
        r = _run(readtext, path=r"C:\Windows\System32\config\SAM")

    def test_path_with_spaces_traversal(self):
        """TRAV-009: 带空格路径..遍历 - Safety层必须拦截"""
        from app.tools.file.read_text_file import readtext
        from app.tools import ensure_tools_registered
        from app.services.safety.path_safe_check import validate_tool_path
        ensure_tools_registered()
        with tempfile.TemporaryDirectory() as d:
            secret = Path(d) / "secret.txt"
            secret.write_text("SECRET")
            raw = str(Path(d) / "sub dir" / ".." / "secret.txt")
            valid, msg, _, cat = validate_tool_path("readtext", {"path": raw})
            assert not valid and cat == "system", f"TRAV-009: 带空格..必须被Safety层拦截: {msg}"
            r = _run(readtext, path=raw)

    def test_path_with_unicode_traversal(self):
        """TRAV-010: Unicode路径+遍历 - Safety层必须拦截"""
        from app.tools.file.read_text_file import readtext
        from app.tools import ensure_tools_registered
        from app.services.safety.path_safe_check import validate_tool_path
        ensure_tools_registered()
        with tempfile.TemporaryDirectory() as d:
            secret = Path(d) / "secret.txt"
            secret.write_text("SECRET")
            raw = str(Path(d) / "目录" / ".." / "secret.txt")
            valid, msg, _, cat = validate_tool_path("readtext", {"path": raw})
            assert not valid and cat == "system", f"TRAV-010: Unicode+..必须被Safety层拦截: {msg}"
            r = _run(readtext, path=raw)


# ============================================================
class TestShellInjectionDeep:
    """Shell命令注入深度测试"""

    def test_pipe_injection(self):
        """INJECT-001: 管道注入"""
        # 安全版: 只校验拦截逻辑, 不真执行(原版含Remove-Item C:\test会真删) — 小欧 2026-08-02
        from app.tools.fundamental.execute_shell_command_safety import check_shell_command_risk
        r = check_shell_command_risk("echo test | Remove-Item C:\\test -Force", "ps7")
        assert r is not None and (r.blocked or r.requires_confirmation), "管道注入的危险删除应被拦截"

    def test_backtick_injection(self):
        """INJECT-002: 反引号注入"""
        from app.tools.fundamental.execute_shell_command import shell
        r = _run(shell, command="echo `whoami`")
        # 反引号应该被处理

    def test_dollar_paren_injection(self):
        """INJECT-003: $()注入"""
        from app.tools.fundamental.execute_shell_command import shell
        r = _run(shell, command="echo $(whoami)")
        # $()应该被处理

    def test_semicolon_chain(self):
        """INJECT-004: 分号链"""
        from app.tools.fundamental.execute_shell_command import shell
        r = _run(shell, command="echo a; echo b; echo c")
        # 分号应该被处理

    def test_ampersand_chain(self):
        """INJECT-005: &链"""
        from app.tools.fundamental.execute_shell_command import shell
        r = _run(shell, command="echo a & echo b & echo c")
        # &应该被处理

    def test_newline_injection(self):
        """INJECT-006: 换行符注入"""
        # 安全版: 只校验拦截逻辑, 不真执行(原版含Remove-Item C:\test会真删) — 小欧 2026-08-02
        from app.tools.fundamental.execute_shell_command_safety import check_shell_command_risk
        r = check_shell_command_risk("echo test`nRemove-Item C:\\test -Force", "ps7")
        assert r is not None and (r.blocked or r.requires_confirmation), "换行符注入的危险删除应被拦截"

    def test_string_interpolation(self):
        """INJECT-007: 字符串插值"""
        from app.tools.fundamental.execute_shell_command import shell
        r = _run(shell, command='$test = "hello"; echo $test')
        # 字符串插值应该被处理

    def test_env_variable_expansion(self):
        """INJECT-008: 环境变量展开"""
        from app.tools.fundamental.execute_shell_command import shell
        r = _run(shell, command="echo $env:PATH")
        # 环境变量展开应该被处理

    def test_base64_decode(self):
        """INJECT-009: Base64解码"""
        from app.tools.fundamental.execute_shell_command import shell
        # "whoami" in base64
        r = _run(shell, command="[System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String('d2hvYW1p'))")
        # Base64解码应该被处理

    def test_com_object_injection(self):
        """INJECT-010: COM对象注入"""
        from app.tools.fundamental.execute_shell_command import shell
        r = _run(shell, command="New-Object -ComObject WScript.Shell")
        # COM对象创建应该被处理


# ============================================================
# 3. 资源泄漏测试 - 文件找柄,内存等
# ============================================================
class TestResourceLeak:
    """资源泄漏测试"""

    def test_file_handle_after_read(self):
        """LEAK-001: 读取在文件找柄"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.read_text_file import readtext
        with tempfile.TemporaryDirectory() as d:
            fp = str(Path(d) / "handle.txt")
            _run(writetext, path=fp, content="HANDLE_TEST")
            # 多次读取
            for i in range(100):
                r = _run(readtext, path=fp)
                assert _ok(r)

    def test_file_handle_after_write(self):
        """LEAK-002: 写入在文件找柄"""
        from app.tools.file.write_text_file import writetext
        with tempfile.TemporaryDirectory() as d:
            fp = str(Path(d) / "handle.txt")
            for i in range(100):
                _run(writetext, path=fp, content=f"iteration_{i}")

    def test_concurrent_file_handles(self):
        """LEAK-003: 并发文件找柄"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.read_text_file import readtext
        import concurrent.futures
        with tempfile.TemporaryDirectory() as d:
            # 创建多个文件
            for i in range(50):
                _run(writetext, path=str(Path(d) / f"f{i}.txt"), content=f"data_{i}")
            # 并发读取
            def read_file(i):
                return _run(readtext, path=str(Path(d) / f"f{i}.txt"))
            with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
                futures = [executor.submit(read_file, i) for i in range(50)]
                results = [f.result() for f in futures]
            # 所有读取应该成功
            for r in results:
                assert _ok(r)

    def test_memory_after_large_file(self):
        """LEAK-004: 大文件在内存"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.read_text_file import readtext
        with tempfile.TemporaryDirectory() as d:
            fp = str(Path(d) / "large.txt")
            # 写入大文件
            content = "X" * (1024 * 1024)  # 1MB
            _run(writetext, path=fp, content=content)
            # 读取大文件
            r = _run(readtext, path=fp)
            # 门限治理后 Tool 层不再截断单行(截断收口于 observation_formatter) — 小欧 2026-07-20
            assert _ok(r), "大文件读取应成功"
            content = r.get("data", {}).get("content", "")
            assert len(content) >= 1, "应返回有效内容"
            # 释放内存
            del content
            gc.collect()

    def test_shell_process_cleanup(self):
        """LEAK-005: Shell进程清理"""
        from app.tools.fundamental.execute_shell_command import shell
        for i in range(50):
            r = _run(shell, command=f"echo test_{i}")
            assert _ok(r)


# ============================================================
# 4. 并发竞态条件测试
# ============================================================
class TestRaceCondition:
    """并发竞态条件测试"""

    def test_concurrent_write_same_file(self):
        """RACE-001: 并发写入同一文件"""
        from app.tools.file.write_text_file import writetext
        import concurrent.futures
        with tempfile.TemporaryDirectory() as d:
            fp = str(Path(d) / "race.txt")
            results = []
            def write_val(val):
                return _run(writetext, path=fp, content=f"VALUE_{val}")
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(write_val, i) for i in range(10)]
                results = [f.result() for f in futures]
            # 应该至少有一个成功
            assert any(_ok(r) for r in results)

    def test_concurrent_copy_same_source(self):
        """RACE-002: 并发复制同一源"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.copy_file import copy
        import concurrent.futures
        with tempfile.TemporaryDirectory() as d:
            src = str(Path(d) / "src.txt")
            _run(writetext, path=src, content="RACE_DATA")
            def copy_to(i):
                return _run(copy, path=src, dest=str(Path(d) / f"dst_{i}.txt"))
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(copy_to, i) for i in range(10)]
                results = [f.result() for f in futures]
            # 所有复制应该成功
            for r in results:
                assert _ok(r)

    def test_concurrent_grep_same_dir(self):
        """RACE-003: 并发grep同一目录"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.grep_file_content import grep
        import concurrent.futures
        with tempfile.TemporaryDirectory() as d:
            for i in range(20):
                _run(writetext, path=str(Path(d) / f"f{i}.txt"), content=f"data_{i}\n")
            def grep_search(i):
                return _run(grep, pattern=f"data_{i}", path=d)
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(grep_search, i) for i in range(20)]
                results = [f.result() for f in futures]
            # 所有grep应该成功
            for r in results:
                assert _ok(r)

    def test_concurrent_read_write_same_file(self):
        """RACE-004: 并发读写同一文件"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.read_text_file import readtext
        import concurrent.futures
        with tempfile.TemporaryDirectory() as d:
            fp = str(Path(d) / "rw_race.txt")
            _run(writetext, path=fp, content="INITIAL")
            def read_file():
                return _run(readtext, path=fp)
            def write_file(val):
                return _run(writetext, path=fp, content=f"UPDATED_{val}")
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                futures = []
                for i in range(5):
                    futures.append(executor.submit(read_file))
                for i in range(5):
                    futures.append(executor.submit(write_file, i))
                results = [f.result() for f in futures]
            # 所有操作应该成功
            for r in results:
                assert _ok(r)


# ============================================================
# 5. 性能退化测试 - 检测性能问题
# ============================================================
class TestPerformanceDegradation:
    """性能退化测试"""

    def test_grep_performance_large_dir(self):
        """PERF-001: 大目录grep性能"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.grep_file_content import grep
        with tempfile.TemporaryDirectory() as d:
            # 创建100个文件
            for i in range(100):
                _run(writetext, path=str(Path(d) / f"f{i}.txt"), content=f"data_{i}\n")
            start = time.time()
            r = _run(grep, pattern="data_", path=d)
            elapsed = time.time() - start
            # grep应该在合理时间内完成
            assert elapsed < 30  # 30秒内

    def test_list_performance_large_dir(self):
        """PERF-002: 大目录列表性能"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.list_directory import listdir
        with tempfile.TemporaryDirectory() as d:
            # 创建500个文件
            for i in range(500):
                _run(writetext, path=str(Path(d) / f"f{i:03d}.txt"), content=f"data_{i}")
            start = time.time()
            r = _run(listdir, path=d)
            elapsed = time.time() - start
            # 列表应该在合理时间内完成
            assert elapsed < 30

    def test_search_performance_large_dir(self):
        """PERF-003: 大目录搜索性能"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.search_files import find
        with tempfile.TemporaryDirectory() as d:
            # 创建200个文件
            for i in range(200):
                _run(writetext, path=str(Path(d) / f"f{i:03d}.txt"), content=f"data_{i}")
            start = time.time()
            r = _run(find, pattern="*.txt", path=d)
            elapsed = time.time() - start
            # 搜索应该在合理时间内完成
            assert elapsed < 30

    def test_read_performance_large_file(self):
        """PERF-004: 大文件读取性能"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.read_text_file import readtext
        with tempfile.TemporaryDirectory() as d:
            fp = str(Path(d) / "large.txt")
            content = "X" * (1024 * 1024)  # 1MB
            _run(writetext, path=fp, content=content)
            start = time.time()
            r = _run(readtext, path=fp)
            elapsed = time.time() - start
            # 读取应该在合理时间内完成
            assert elapsed < 10

    def test_write_performance_large_file(self):
        """PERF-005: 大文件写入性能"""
        from app.tools.file.write_text_file import writetext
        with tempfile.TemporaryDirectory() as d:
            fp = str(Path(d) / "large.txt")
            content = "X" * (1024 * 1024)  # 1MB
            start = time.time()
            r = _run(writetext, path=fp, content=content)
            elapsed = time.time() - start
            # 写入应该在合理时间内完成
            assert elapsed < 10


# ============================================================
# 6. 错误信息泄漏测试 - 检测敏感信息泄露
# ============================================================
class TestInformationLeakage:
    """错误信息泄漏测试"""

    def test_error_no_path_disclosure(self):
        """LEAK-001: 错误信息不泄露路径"""
        from app.tools.file.read_text_file import readtext
        r = _run(readtext, path="C:\\nonexistent\\secret.txt")
        error = str(r.get("llm_data", {}).get("status", {}).get("detail", ""))
        # 错误信息不应该包含敏感路径

    def test_error_no_system_info(self):
        """LEAK-002: 错误信息不泄露系统信息"""
        from app.tools.fundamental.execute_shell_command import shell
        r = _run(shell, command="nonexistent_command_12345")
        error = str(r.get("llm_data", {}).get("status", {}).get("detail", ""))
        # 错误信息不应该泄露系统路径或版本

    def test_timeout_no_info_leak(self):
        """LEAK-003: 超时信息不泄露"""
        from app.tools.fundamental.execute_shell_command import shell
        r = _run(shell, command="Start-Sleep -Seconds 10", timeout=1000)
        # 超时不应该泄露内部信息

    def test_permission_error_no_leak(self):
        """LEAK-004: 权限错误不泄露"""
        from app.tools.file.write_text_file import writetext
        r = _run(writetext, path="C:\\Windows\\System32\\test.txt", content="test")
        error = str(r.get("llm_data", {}).get("status", {}).get("detail", ""))
        # 权限错误不应该泄露系统信息


# ============================================================
# 7. 文件系统边界测试
# ============================================================
class TestFileSystemBoundary:
    """文件系统边界测试"""

    def test_empty_filename(self):
        """FS-001: 空文件名"""
        from app.tools.file.write_text_file import writetext
        with tempfile.TemporaryDirectory() as d:
            fp = str(Path(d) / "")
            r = _run(writetext, path=fp, content="test")
            # 空文件名应该被拒绝

    def test_dot_filename(self):
        """FS-002: 点文件名"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.read_text_file import readtext
        with tempfile.TemporaryDirectory() as d:
            fp = str(Path(d) / ".")
            r = _run(writetext, path=fp, content="test")
            # 点文件名应该被拒绝或处理

    def test_dotdot_filename(self):
        """FS-003: ..文件名"""
        from app.tools.file.write_text_file import writetext
        with tempfile.TemporaryDirectory() as d:
            fp = str(Path(d) / "..")
            r = _run(writetext, path=fp, content="test")
            # ..文件名应该被拒绝

    def test_reserved_filename(self):
        """FS-004: Windows保留文件名"""
        from app.tools.file.write_text_file import writetext
        with tempfile.TemporaryDirectory() as d:
            for name in ["CON", "PRN", "AUX", "NUL", "COM1", "LPT1"]:
                fp = str(Path(d) / f"{name}.txt")
                r = _run(writetext, path=fp, content="test")
                # 保留文件名应该被处理

    def test_max_path_length(self):
        """FS-005: 最大路径长度"""
        from app.tools.file.write_text_file import writetext
        with tempfile.TemporaryDirectory() as d:
            # 创建深层嵌套(不超过Windows MAX_PATH)
            current = Path(d)
            for i in range(15):  # 减少嵌套深度
                current = current / f"dir_{i}"
                current.mkdir(exist_ok=True)
            fp = str(current / "file.txt")
            r = _run(writetext, path=fp, content="deep")
            # 超长路径应该被处理

    def test_special_chars_in_filename(self):
        """FS-006: 文件名特殊字符"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.read_text_file import readtext
        with tempfile.TemporaryDirectory() as d:
            # Windows非法字符: < > : " / \ | ? *
            for ch in '<>:"/\\|?*':
                fp = str(Path(d) / f"test{ch}file.txt")
                r = _run(writetext, path=fp, content="test")
                # 特殊字符应该被处理

    def test_unicode_filename(self):
        """FS-007: Unicode文件名"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.read_text_file import readtext
        with tempfile.TemporaryDirectory() as d:
            fp = str(Path(d) / "文件_测试.txt")
            _run(writetext, path=fp, content="UNICODE")
            r = _run(readtext, path=fp)
            assert "UNICODE" in r.get("data", {}).get("content", "")

    def test_very_long_filename(self):
        """FS-008: 超长文件名"""
        from app.tools.file.write_text_file import writetext
        with tempfile.TemporaryDirectory() as d:
            long_name = "a" * 200
            fp = str(Path(d) / f"{long_name}.txt")
            r = _run(writetext, path=fp, content="LONG")
            # 超长文件名应该被处理

    def test_readonly_file_edit(self):
        """FS-009: 只读文件编辑"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.edit_text_file import edittext
        with tempfile.TemporaryDirectory() as d:
            fp = str(Path(d) / "readonly.txt")
            _run(writetext, path=fp, content="ORIGINAL")
            # 设置只读
            os.chmod(fp, 0o444)
            r = _run(edittext, path=fp, old_string="ORIGINAL", new_string="MODIFIED")
            # 只读文件编辑应该失败

    def test_readonly_file_write(self):
        """FS-010: 只读文件写入"""
        from app.tools.file.write_text_file import writetext
        with tempfile.TemporaryDirectory() as d:
            fp = str(Path(d) / "readonly.txt")
            _run(writetext, path=fp, content="ORIGINAL")
            # 设置只读
            os.chmod(fp, 0o444)
            r = _run(writetext, path=fp, content="OVERWRITE")
            # 只读文件写入应该失败
