# -*- coding: utf-8 -*-
"""
read_text_file 边界测试 - 专门找边界bug
小欧 2026-06-24
"""
import asyncio
import os
import tempfile
import pytest


def _run(coro):
    return asyncio.run(coro)


class TestReadTextFileBoundaryBugs:
    """边界条件 - 专门找崩溃bug"""

    def test_offset_zero(self):
        """offset=0 会怎样? start_idx = max(0, 0-1) = max(0,-1) = 0"""
        from app.tools.file.read_text_file import readtext
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("line1\nline2\nline3\n")
            tmp = f.name
        try:
            result = _run(readtext(tmp, offset=0, limit=2))
            print(f"offset=0结果: {result['llm_data']['status']}")
            # offset=0应该报错还是返回全文?
        finally:
            os.unlink(tmp)

    def test_limit_zero(self):
        """limit=0 - 代码只检查>1"""
        from app.tools.file.read_text_file import readtext
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("line1\nline2\nline3\n")
            tmp = f.name
        try:
            result = _run(readtext(tmp, offset=1, limit=0))
            print(f"limit=0结果: {result['llm_data']['status']}")
        finally:
            os.unlink(tmp)

    def test_limit_negative(self):
        """limit=-5 - 代码只检查>1"""
        from app.tools.file.read_text_file import readtext
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("line1\nline2\nline3\n")
            tmp = f.name
        try:
            result = _run(readtext(tmp, offset=1, limit=-5))
            print(f"limit=-5结果: {result['llm_data']['status']}")
        finally:
            os.unlink(tmp)

    def test_offset_beyond_total_lines(self):
        """offset=999 远超文件行数"""
        from app.tools.file.read_text_file import readtext
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("line1\nline2\nline3\n")
            tmp = f.name
        try:
            result = _run(readtext(tmp, offset=999, limit=10))
            print(f"offset超限结果: {result['llm_data']['status']}")
            # 应该返回空内容?
            if result['llm_data']['status']['exec_code'] == 'success':
                content = result['data']['content']
                print(f"  content='{content}'")
        finally:
            os.unlink(tmp)

    def test_negative_offset_larger_than_file(self):
        """offset=-999 远超文件行数"""
        from app.tools.file.read_text_file import readtext
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("line1\nline2\nline3\n")
            tmp = f.name
        try:
            result = _run(readtext(tmp, offset=-999))
            print(f"负offset超限结果: {result['llm_data']['status']}")
        finally:
            os.unlink(tmp)

    def test_single_line_file_offset_negative(self):
        """单行文件 + 负offset"""
        from app.tools.file.read_text_file import readtext
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("only one line")
            tmp = f.name
        try:
            result = _run(readtext(tmp, offset=-1))
            print(f"单行负offset结果: {result['llm_data']['status']}")
            if result['llm_data']['status']['exec_code'] == 'success':
                print(f"  content='{result['data']['content']}'")
        finally:
            os.unlink(tmp)

    def test_empty_file_offset(self):
        """空文件 + offset"""
        from app.tools.file.read_text_file import readtext
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write('')
            tmp = f.name
        try:
            result = _run(readtext(tmp, offset=-5))
            print(f"空文件offset结果: {result['llm_data']['status']}")
        finally:
            os.unlink(tmp)

    def test_file_with_only_newlines(self):
        """只有换行符的文件"""
        from app.tools.file.read_text_file import readtext
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("\n\n\n\n\n")
            tmp = f.name
        try:
            result = _run(readtext(tmp))
            print(f"纯换行结果: {result['llm_data']['status']}")
            if result['llm_data']['status']['exec_code'] == 'success':
                lines = result['data']['content'].split('\n')
                print(f"   行数: {len(lines)}")
        finally:
            os.unlink(tmp)

    def test_file_with_crlf(self):
        """CRLF换行符"""
        from app.tools.file.read_text_file import readtext
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.txt', delete=False) as f:
            f.write(b"line1\r\nline2\r\nline3\r\n")
            tmp = f.name
        try:
            result = _run(readtext(tmp))
            print(f"CRLF结果: {result['llm_data']['status']}")
        finally:
            os.unlink(tmp)

    def test_file_with_lf(self):
        """LF换行符"""
        from app.tools.file.read_text_file import readtext
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.txt', delete=False) as f:
            f.write(b"line1\nline2\nline3\n")
            tmp = f.name
        try:
            result = _run(readtext(tmp))
            print(f"LF结果: {result['llm_data']['status']}")
        finally:
            os.unlink(tmp)

    def test_file_with_mixed_line_endings(self):
        """混合换行符"""
        from app.tools.file.read_text_file import readtext
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.txt', delete=False) as f:
            f.write(b"line1\r\nline2\nline3\r\n")
            tmp = f.name
        try:
            result = _run(readtext(tmp))
            print(f"混合换行结果: {result['llm_data']['status']}")
        finally:
            os.unlink(tmp)

    def test_file_with_null_bytes(self):
        """包含NULL字节的文件"""
        from app.tools.file.read_text_file import readtext
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.txt', delete=False) as f:
            f.write(b"line1\x00line2\x00line3")
            tmp = f.name
        try:
            result = _run(readtext(tmp))
            print(f"NULL字节结果: {result['llm_data']['status']}")
        finally:
            os.unlink(tmp)

    def test_file_with_very_long_line(self):
        """超长单行(1MB)"""
        from app.tools.file.read_text_file import readtext
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("A" * 1024 * 1024 + "\n")
            tmp = f.name
        try:
            result = _run(readtext(tmp))
            print(f"超长行结果: {result['llm_data']['status']}")
        finally:
            os.unlink(tmp)

    def test_file_content_outlimit_boundary(self):
        """内容长度接近OUTLIMIT_CHARS"""
        from app.tools.file.read_text_file import readtext
        from app.tools.tool_constants import READTEXT_OUTLIMIT_CHARS
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            # 写入接近outlimit的内容, 未超应全量返回
            content = "A" * (READTEXT_OUTLIMIT_CHARS - 100) + "\n"
            f.write(content)
            tmp = f.name
        try:
            result = _run(readtext(tmp))
            print(f"边界内容结果: {result['llm_data']['status']}")
        finally:
            os.unlink(tmp)

    def test_file_with_bom(self):
        """UTF-8 BOM头"""
        from app.tools.file.read_text_file import readtext
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.txt', delete=False) as f:
            f.write(b'\xef\xbb\xbfline1\nline2\n')
            tmp = f.name
        try:
            result = _run(readtext(tmp))
            print(f"BOM结果: {result['llm_data']['status']}")
            if result['llm_data']['status']['exec_code'] == 'success':
                print(f"  encoding={result['data'].get('encoding')}")
                print(f"  content='{result['data']['content'][:50]}'")
        finally:
            os.unlink(tmp)

    def test_special_path_characters(self):
        """路径包含特殊字符"""
        from app.tools.file.read_text_file import readtext
        with tempfile.TemporaryDirectory() as tmpdir:
            special_name = os.path.join(tmpdir, "file with spaces (1).txt")
            with open(special_name, 'w', encoding='utf-8') as f:
                f.write("content")
            result = _run(readtext(special_name))
            print(f"特殊路径结果: {result['llm_data']['status']}")

    def test_relative_path(self):
        """相对路径"""
        from app.tools.file.read_text_file import readtext
        result = _run(readtext("./nonexistent.txt"))
        print(f"相对路径结果: {result['llm_data']['status']}")

    def test_network_path(self):
        """网络路径"""
        from app.tools.file.read_text_file import readtext
        result = _run(readtext("//server/share/file.txt"))
        print(f"网络路径结果: {result['llm_data']['status']}")

    def test_concurrent_read_same_file(self):
        """并发读取同一文件"""
        from app.tools.file.read_text_file import readtext
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("line1\nline2\nline3\n")
            tmp = f.name
        try:
            # 同时读取多次
            results = []
            for i in range(5):
                r = _run(readtext(tmp))
                results.append(r)
            # 所有结果应该一致
            first = results[0]['data']['content']
            for r in results[1:]:
                assert r['data']['content'] == first
        finally:
            os.unlink(tmp)
