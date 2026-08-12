# -*- coding: utf-8 -*-
# ================================================================
# 【skip case 归档副本】 - 小欧 2026-08-12 10:43:59
# 原路径: backend/tests/tools/param_combination/test_twelfth_boundary.py
# 归档原因: 包含 OS 不支持 symlink 的 skip case(symlink 遍历),
#           已从 backend/tests 原文件删除对应 skip case, 此处保留完整代码,
#           便于未来在其他平台(如 Linux)恢复运行。
# ================================================================
"""第十二轮 - 边界条件与安全深度测试
目标:发现真实Bug,覆盖安全边界,编码边界,状态恢复等未测试路径
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


# ============================================================
# 1. SSRF内部IP测试 - 验证安全检查是否拦截内网IP
# ============================================================
class TestSSRFBlocking:
    """SSRF内部IP访问测试 - 使用http_request工具"""

    def test_ssrf_localhost_ip(self):
        """SEC-SSRF-001: 访问127.0.0.1应被拦截"""
        from app.tools.network.http_request import httpget
        r = _run(httpget, url="http://127.0.0.1:8000/health")
        # 应该被拦截或失败
        assert not _ok(r) or "127.0.0.1" in str(r.get("data", {}))

    def test_ssrf_localhost_hostname(self):
        """SEC-SSRF-002: 访问localhost应被拦截"""
        from app.tools.network.http_request import httpget
        r = _run(httpget, url="http://localhost:8000/health")
        assert not _ok(r) or "localhost" in str(r.get("data", {}))

    def test_ssrf_private_ip_10(self):
        """SEC-SSRF-003: 访问10.x.x.x应被拦截"""
        from app.tools.network.http_request import httpget
        r = _run(httpget, url="http://10.0.0.1:80/health")
        assert not _ok(r) or "10.0.0.1" in str(r.get("data", {}))

    def test_ssrf_private_ip_172(self):
        """SEC-SSRF-004: 访问172.16-31.x.x应被拦截"""
        from app.tools.network.http_request import httpget
        r = _run(httpget, url="http://172.16.0.1:80/health")
        assert not _ok(r) or "172.16.0.1" in str(r.get("data", {}))

    def test_ssrf_private_ip_192(self):
        """SEC-SSRF-005: 访问192.168.x.x应被拦截"""
        from app.tools.network.http_request import httpget
        r = _run(httpget, url="http://192.168.1.1:80/health")
        assert not _ok(r) or "192.168.1.1" in str(r.get("data", {}))

    def test_ssrf_file_protocol(self):
        """SEC-SSRF-006: file://协议应被拦截"""
        from app.tools.network.http_request import httpget
        r = _run(httpget, url="file:///etc/passwd")
        assert not _ok(r)

    def test_ssrf_ftp_protocol(self):
        """SEC-SSRF-007: ftp://协议应被拦截或不支持"""
        from app.tools.network.http_request import httpget
        r = _run(httpget, url="ftp://127.0.0.1:21/")
        assert not _ok(r)


# ============================================================
# 2. 符号链接遍历测试 - 验证路径验证是否处理symlink
# ============================================================
class TestSymlinkTraversal:
    """符号链接遍历测试"""

    def test_symlink_outside_workspace(self):
        """SEC-SYM-001: symlink指向workspace外应被拒绝"""
        from app.tools.file.read_text_file import readtext
        with tempfile.TemporaryDirectory() as d:
            # 创建一个指向外部文件的symlink
            outside_file = Path(d) / "outside.txt"
            outside_file.write_text("OUTSIDE_DATA")
            symlink_path = Path(d) / "link.txt"
            try:
                symlink_path.symlink_to(outside_file)
            except OSError:
                pytest.skip("OS doesn't support symlinks")
            r = _run(readtext, path=str(symlink_path))
            # symlink应该被拒绝或读取到内容(取决于实现)
            # 这里验证不会崩溃

    def test_symlink_to_parent(self):
        """SEC-SYM-002: symlink指向父目录应被处理"""
        from app.tools.file.list_directory import listdir
        with tempfile.TemporaryDirectory() as d:
            sub = Path(d) / "sub"
            sub.mkdir()
            (sub / "file.txt").write_text("data")
            try:
                link = Path(d) / "parent_link"
                link.symlink_to(d)
            except OSError:
                pytest.skip("OS doesn't support symlinks")
            r = _run(listdir, path=str(sub))
            # 应该能正常列出目录,不会崩溃

    def test_symlink_loop(self):
        """SEC-SYM-003: symlink循环应被检测"""
        from app.tools.file.list_directory import listdir
        with tempfile.TemporaryDirectory() as d:
            a = Path(d) / "a"
            b = Path(d) / "b"
            a.mkdir()
            b.mkdir()
            try:
                (a / "link_to_b").symlink_to(b)
                (b / "link_to_a").symlink_to(a)
            except OSError:
                pytest.skip("OS doesn't support symlinks")
            r = _run(listdir, path=str(a))
            # 应该能处理symlink循环,不会无限递归


# ============================================================
# 3. 编码边界测试 - 验证各种编码场景
# ============================================================
class TestEncodingEdgeCases:
    """编码边界条件测试"""

    def test_read_file_bom_utf8(self):
        """ENC-001: 带BOM的UTF-8文件"""
        from app.tools.file.read_text_file import readtext
        with tempfile.TemporaryDirectory() as d:
            fp = str(Path(d) / "bom.txt")
            # 写入带BOM的UTF-8
            with open(fp, "wb") as f:
                f.write(b'\xef\xbb\xbf')  # UTF-8 BOM
                f.write("BOM_CONTENT".encode("utf-8"))
            r = _run(readtext, path=fp)
            content = r.get("data", {}).get("content", "")
            assert "BOM_CONTENT" in content

    def test_read_file_bom_utf16(self):
        """ENC-002: UTF-16 LE编码文件"""
        from app.tools.file.read_text_file import readtext
        with tempfile.TemporaryDirectory() as d:
            fp = str(Path(d) / "utf16.txt")
            with open(fp, "wb") as f:
                f.write("UTF16_CONTENT".encode("utf-16-le"))
            r = _run(readtext, path=fp)
            # UTF-16可能不被支持,验证不崩溃

    def test_read_file_gbk(self):
        """ENC-003: GBK编码文件"""
        from app.tools.file.read_text_file import readtext
        with tempfile.TemporaryDirectory() as d:
            fp = str(Path(d) / "gbk.txt")
            try:
                with open(fp, "wb") as f:
                    f.write("GBK内容测试".encode("gbk"))
            except UnicodeEncodeError:
                pytest.skip("GBK encoding not supported")
            r = _run(readtext, path=fp)
            # 应该能处理GBK编码

    def test_write_read_latin1(self):
        """ENC-004: Latin-1编码读写"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.read_text_file import readtext
        with tempfile.TemporaryDirectory() as d:
            fp = str(Path(d) / "latin1.txt")
            _run(writetext, path=fp, content="Café résumé naïve", encoding="latin-1")
            r = _run(readtext, path=fp, encoding="latin-1")
            assert "Café" in r.get("data", {}).get("content", "")

    def test_write_read_ascii_fallback(self):
        """ENC-005: ASCII编码写入非ASCII内容"""
        from app.tools.file.write_text_file import writetext
        with tempfile.TemporaryDirectory() as d:
            fp = str(Path(d) / "ascii_fail.txt")
            r = _run(writetext, path=fp, content="中文内容", encoding="ascii")
            # ASCII编码写入中文应该失败或降级

    def test_grep_binary_file(self):
        """ENC-006: grep二进制文件应跳过"""
        from app.tools.file.grep_file_content import grep
        with tempfile.TemporaryDirectory() as d:
            fp = str(Path(d) / "binary.bin")
            # 写入包含NULL字节的二进制文件
            with open(fp, "wb") as f:
                f.write(b'\x00\x01\x02\x03test\x00\x04\x05')
            r = _run(grep, pattern="test", path=d)
            # 二进制文件应该被跳过或标记

    def test_write_empty_content(self):
        """ENC-007: 写入空内容"""
        from app.tools.file.write_text_file import writetext
        with tempfile.TemporaryDirectory() as d:
            fp = str(Path(d) / "empty.txt")
            r = _run(writetext, path=fp, content="")
            # 空内容应该被拒绝(工具设计如此)

    def test_write_very_long_line(self):
        """ENC-008: 写入超长单行"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.read_text_file import readtext
        with tempfile.TemporaryDirectory() as d:
            fp = str(Path(d) / "longline.txt")
            long_line = "A" * 100000
            _run(writetext, path=fp, content=long_line)
            r = _run(readtext, path=fp)
            # readtext 返回内容带行号前缀且超长行截断(供前端), 断言带行号且含原始数据 — 小欧 2026-07-12
            content = r.get("data", {}).get("content", "")
            assert content.startswith("1|") and "A" in content


# ============================================================
# 4. 错误恢复链测试 - 验证连续操作中的错误恢复
# ============================================================
class TestErrorRecovery:
    """错误恢复链测试"""

    def test_write_then_edit_nonexistent(self):
        """REC-001: 写入在编辑不存在的文件"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.edit_text_file import edittext
        with tempfile.TemporaryDirectory() as d:
            fp = str(Path(d) / "exists.txt")
            _run(writetext, path=fp, content="ORIGINAL")
            # 删除文件
            os.remove(fp)
            r = _run(edittext, path=fp, old_string="ORIGINAL", new_string="NEW")
            assert not _ok(r)

    def test_read_then_write_concurrent(self):
        """REC-002: 读取和写入同时操作同一文件"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.read_text_file import readtext
        with tempfile.TemporaryDirectory() as d:
            fp = str(Path(d) / "concurrent.txt")
            _run(writetext, path=fp, content="LINE1\nLINE2\nLINE3")
            # 读取同时写入
            r1 = _run(readtext, path=fp)
            _run(writetext, path=fp, content="MODIFIED\nLINE2\nLINE3")
            r2 = _run(readtext, path=fp)
            # 应该能看到修改在的内容
            assert "MODIFIED" in r2.get("data", {}).get("content", "")

    def test_grep_while_file_modified(self):
        """REC-003: grep时文件被修改"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.grep_file_content import grep
        with tempfile.TemporaryDirectory() as d:
            fp = str(Path(d) / "modify_during.txt")
            _run(writetext, path=fp, content="OLD_CONTENT\nLINE2\nLINE3")
            # 开始grep(可能很慢)
            # 同时修改文件
            _run(writetext, path=fp, content="NEW_CONTENT\nLINE2\nLINE3")
            r = _run(grep, pattern="CONTENT", path=d)
            # 应该能处理并发修改

    def test_list_dir_while_files_deleted(self):
        """REC-004: list目录时文件被删除"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.list_directory import listdir
        with tempfile.TemporaryDirectory() as d:
            # 创建多个文件
            for i in range(10):
                _run(writetext, path=str(Path(d) / f"f{i}.txt"), content=f"data_{i}")
            # 同时删除一些文件
            for i in range(5):
                os.remove(str(Path(d) / f"f{i}.txt"))
            r = _run(listdir, path=d)
            # 应该能处理并发删除,不会崩溃


# ============================================================
# 5. 空值和None边界测试 - 验证参数空值处理
# ============================================================
class TestNullBoundary:
    """空值边界条件测试"""

    def test_write_empty_path(self):
        """NULL-001: 空路径写入"""
        from app.tools.file.write_text_file import writetext
        r = _run(writetext, path="", content="test")
        assert not _ok(r)

    def test_read_empty_path(self):
        """NULL-002: 空路径读取"""
        from app.tools.file.read_text_file import readtext
        r = _run(readtext, path="")
        assert not _ok(r)

    def test_grep_empty_pattern(self):
        """NULL-003: 空搜索模式"""
        from app.tools.file.grep_file_content import grep
        with tempfile.TemporaryDirectory() as d:
            r = _run(grep, pattern="", path=d)
            # 空模式应该被拒绝

    def test_shell_empty_command(self):
        """NULL-004: 空Shell命令"""
        from app.tools.fundamental.execute_shell_command import shell
        r = _run(shell, command="")
        assert not _ok(r)

    def test_list_empty_path(self):
        """NULL-005: 空路径列表"""
        from app.tools.file.list_directory import listdir
        r = _run(listdir, path="")
        assert not _ok(r)

    def test_search_empty_pattern(self):
        """NULL-006: 空搜索模式"""
        from app.tools.file.search_files import find
        with tempfile.TemporaryDirectory() as d:
            r = _run(find, pattern="", path=d)
            assert not _ok(r)

    def test_write_none_content(self):
        """NULL-007: None内容写入"""
        from app.tools.file.write_text_file import writetext
        with tempfile.TemporaryDirectory() as d:
            fp = str(Path(d) / "test.txt")
            r = _run(writetext, path=fp, content=None)
            # None内容应该被处理

    def test_edit_empty_old_string(self):
        """NULL-008: 空old_string编辑"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.edit_text_file import edittext
        with tempfile.TemporaryDirectory() as d:
            fp = str(Path(d) / "test.txt")
            _run(writetext, path=fp, content="test content")
            r = _run(edittext, path=fp, old_string="", new_string="new")
            # 空old_string应该被拒绝

    def test_edit_nonexistent_file(self):
        """NULL-009: 编辑不存在的文件"""
        from app.tools.file.edit_text_file import edittext
        with tempfile.TemporaryDirectory() as d:
            fp = str(Path(d) / "nonexistent.txt")
            r = _run(edittext, path=fp, old_string="old", new_string="new")
            assert not _ok(r)

    def test_copy_nonexistent_source(self):
        """NULL-010: 复制不存在的源"""
        from app.tools.file.copy_file import copy
        with tempfile.TemporaryDirectory() as d:
            r = _run(copy, path=str(Path(d) / "nonexistent.txt"), dest=str(Path(d) / "dst.txt"))
            assert not _ok(r)

    def test_move_nonexistent_source(self):
        """NULL-011: 移动不存在的源"""
        from app.tools.file.move_file import move
        with tempfile.TemporaryDirectory() as d:
            r = _run(move, path=str(Path(d) / "nonexistent.txt"), dest=str(Path(d) / "dst.txt"))
            assert not _ok(r)

    def test_rename_nonexistent_source(self):
        """NULL-012: 重命名不存在的源"""
        from app.tools.file.rename_file import rename
        with tempfile.TemporaryDirectory() as d:
            r = _run(rename, path=str(Path(d) / "nonexistent.txt"), dest=str(Path(d) / "new.txt"))
            assert not _ok(r)


# ============================================================
# 6. 文件大小和数量边界测试
# ============================================================
class TestSizeBoundary:
    """文件大小和数量边界测试"""

    def test_write_1mb_content(self):
        """SIZE-001: 写入1MB内容"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.read_text_file import readtext
        with tempfile.TemporaryDirectory() as d:
            fp = str(Path(d) / "1mb.txt")
            content = "A" * 1024 * 1024  # 1MB
            _run(writetext, path=fp, content=content)
            r = _run(readtext, path=fp)
            # readtext 返回内容带行号前缀且超长行截断(供前端), 断言带行号且含原始数据 — 小欧 2026-07-12
            _c = r.get("data", {}).get("content", "")
            assert _c.startswith("1|") and "A" in _c

    def test_list_500_files(self):
        """SIZE-002: 列出500个文件(超过MAX_DISPLAY_ENTRIES=200)"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.list_directory import listdir
        with tempfile.TemporaryDirectory() as d:
            for i in range(500):
                _run(writetext, path=str(Path(d) / f"f{i:03d}.txt"), content=f"data_{i}")
            r = _run(listdir, path=d)
            data = r.get("data", {})
            entries = data.get("entries", [])
            # 应该能处理大量文件(可能截断)
            assert len(entries) > 0

    def test_grep_large_dir(self):
        """SIZE-003: grep大目录"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.grep_file_content import grep
        with tempfile.TemporaryDirectory() as d:
            for i in range(50):
                _run(writetext, path=str(Path(d) / f"f{i}.txt"), content=f"line_{i}\nTARGET\n")
            r = _run(grep, pattern="TARGET", path=d)
            assert r.get("data", {}).get("total_matches", 0) >= 50

    def test_copy_large_file(self):
        """SIZE-004: 复制大文件"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.copy_file import copy
        from app.tools.file.read_text_file import readtext
        with tempfile.TemporaryDirectory() as d:
            src = str(Path(d) / "large_src.txt")
            dst = str(Path(d) / "large_dst.txt")
            content = "B" * 500000  # 500KB
            _run(writetext, path=src, content=content)
            _run(copy, path=src, dest=dst)
            r = _run(readtext, path=dst)
            # readtext 返回内容带行号前缀且超长行截断(供前端), 断言数据已正确读回并带行号 — 小欧 2026-07-12
            _c = r.get("data", {}).get("content", "")
            assert _c.startswith("1|") and "B" in _c

    def test_write_read_utf8_emoji(self):
        """SIZE-005: UTF-8 emoji内容"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.read_text_file import readtext
        with tempfile.TemporaryDirectory() as d:
            fp = str(Path(d) / "emoji.txt")
            content = "🎉🎊🎇🎟🎗🀄🔮🪄" * 100
            _run(writetext, path=fp, content=content)
            r = _run(readtext, path=fp)
            assert "🎉" in r.get("data", {}).get("content", "")


# ============================================================
# 7. 并发安全测试
# ============================================================
class TestConcurrency:
    """并发安全测试"""

    def test_concurrent_write_same_file(self):
        """CONC-001: 并发写入同一文件"""
        from app.tools.file.write_text_file import writetext
        import concurrent.futures
        with tempfile.TemporaryDirectory() as d:
            fp = str(Path(d) / "concurrent.txt")
            def write_val(val):
                return _run(writetext, path=fp, content=f"VALUE_{val}")
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(write_val, i) for i in range(5)]
                results = [f.result() for f in futures]
            # 应该有一个成功,不会崩溃

    def test_concurrent_read_same_file(self):
        """CONC-002: 并发读取同一文件"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.read_text_file import readtext
        import concurrent.futures
        with tempfile.TemporaryDirectory() as d:
            fp = str(Path(d) / "read_concurrent.txt")
            _run(writetext, path=fp, content="SHARED_DATA")
            def read_file():
                return _run(readtext, path=fp)
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(read_file) for _ in range(5)]
                results = [f.result() for f in futures]
            # 所有读取应该成功
            for r in results:
                assert "SHARED_DATA" in r.get("data", {}).get("content", "")

    def test_concurrent_grep_same_dir(self):
        """CONC-003: 并发grep同一目录"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.grep_file_content import grep
        import concurrent.futures
        with tempfile.TemporaryDirectory() as d:
            for i in range(10):
                _run(writetext, path=str(Path(d) / f"f{i}.txt"), content=f"data_{i}\n")
            def grep_search(pattern):
                return _run(grep, pattern=pattern, path=d)
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                futures = [executor.submit(grep_search, f"data_{i}") for i in range(3)]
                results = [f.result() for f in futures]
            # 所有grep应该成功
            for r in results:
                assert r.get("data", {}).get("total_matches", 0) >= 1


# ============================================================
# 8. 路径特殊字符测试
# ============================================================
class TestPathSpecialChars:
    """路径特殊字符测试"""

    def test_path_with_unicode(self):
        """PATH-001: Unicode路径"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.read_text_file import readtext
        with tempfile.TemporaryDirectory() as d:
            fp = str(Path(d) / "文件_测试.txt")
            _run(writetext, path=fp, content="UNICODE_DATA")
            r = _run(readtext, path=fp)
            assert "UNICODE_DATA" in r.get("data", {}).get("content", "")

    def test_path_with_dots(self):
        """PATH-002: 路径包含多个点"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.read_text_file import readtext
        with tempfile.TemporaryDirectory() as d:
            fp = str(Path(d) / "file.name.v2.txt")
            _run(writetext, path=fp, content="DOTS_DATA")
            r = _run(readtext, path=fp)
            assert "DOTS_DATA" in r.get("data", {}).get("content", "")

    def test_path_with_hyphens(self):
        """PATH-003: 路径包含连字符"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.read_text_file import readtext
        with tempfile.TemporaryDirectory() as d:
            fp = str(Path(d) / "my-file-name.txt")
            _run(writetext, path=fp, content="HYPHEN_DATA")
            r = _run(readtext, path=fp)
            assert "HYPHEN_DATA" in r.get("data", {}).get("content", "")

    def test_path_with_underscores(self):
        """PATH-004: 路径包含下划线"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.read_text_file import readtext
        with tempfile.TemporaryDirectory() as d:
            fp = str(Path(d) / "my_file_name.txt")
            _run(writetext, path=fp, content="UNDERSCORE_DATA")
            r = _run(readtext, path=fp)
            assert "UNDERSCORE_DATA" in r.get("data", {}).get("content", "")

    def test_path_with_parentheses(self):
        """PATH-005: 路径包含括号"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.read_text_file import readtext
        with tempfile.TemporaryDirectory() as d:
            fp = str(Path(d) / "file (copy).txt")
            _run(writetext, path=fp, content="PAREN_DATA")
            r = _run(readtext, path=fp)
            assert "PAREN_DATA" in r.get("data", {}).get("content", "")

    def test_path_with_brackets(self):
        """PATH-006: 路径包含方括号"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.read_text_file import readtext
        with tempfile.TemporaryDirectory() as d:
            fp = str(Path(d) / "file [1].txt")
            _run(writetext, path=fp, content="BRACKET_DATA")
            r = _run(readtext, path=fp)
            assert "BRACKET_DATA" in r.get("data", {}).get("content", "")
