# -*- coding: utf-8 -*-
"""
grep_file_content + search_files 回归测试 - 专门找Bug
小欧 2026-06-24
"""
import asyncio
import os
import re
import tempfile
import pytest


def _run(coro):
    return asyncio.run(coro)


class TestGrepFileContentBugs:
    """grep_file_content 专门找Bug"""

    def test_pattern_with_special_regex_chars(self):
        """特殊正则字符 - 是否正认转义"""
        from app.tools.file.grep_file_content import grep
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建包含特殊字符的文件
            with open(os.path.join(tmpdir, "test.txt"), 'w', encoding='utf-8') as f:
                f.write("price: $100.00\n")
                f.write("path: C:\\Users\\test\n")
                f.write("regex: [a-z]+\\d+\n")

            # 搜索包含$的行 - $在正则中是行尾锚点
            result = _run(grep(r"\$100", tmpdir))
            print(f"搜索$100结果: {result['llm_data']['status']}")
            if result['llm_data']['status']['exec_code'] == 'success':
                print(f"  matches: {result['data'].get('total_matches', 0)}")

    def test_pattern_with_unicode(self):
        """Unicode搜索模式"""
        from app.tools.file.grep_file_content import grep
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "test.txt"), 'w', encoding='utf-8') as f:
                f.write("中文测试\n")
                f.write("日本語テスト\n")
                f.write("한글 테스트\n")

            result = _run(grep("中文", tmpdir))
            assert result['llm_data']['status']['exec_code'] == 'success'
            assert result['data']['total_matches'] == 1

    def test_pattern_with_emoji(self):
        """Emoji搜索"""
        from app.tools.file.grep_file_content import grep
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "test.txt"), 'w', encoding='utf-8') as f:
                f.write("Hello 🌍 World\n")
                f.write("No emoji here\n")

            result = _run(grep("🌍", tmpdir))
            print(f"Emoji搜索结果: {result['llm_data']['status']}")

    def test_empty_pattern(self):
        """空搜索模式"""
        from app.tools.file.grep_file_content import grep
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "test.txt"), 'w', encoding='utf-8') as f:
                f.write("content")

            result = _run(grep("", tmpdir))
            print(f"空模式结果: {result['llm_data']['status']}")

    def test_whitespace_pattern(self):
        """纯空白搜索模式"""
        from app.tools.file.grep_file_content import grep
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "test.txt"), 'w', encoding='utf-8') as f:
                f.write("content")

            result = _run(grep("   ", tmpdir))
            print(f"空白模式结果: {result['llm_data']['status']}")

    def test_invalid_regex(self):
        """无效正则表达式"""
        from app.tools.file.grep_file_content import grep
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "test.txt"), 'w', encoding='utf-8') as f:
                f.write("content")

            result = _run(grep("[invalid", tmpdir))
            print(f"无效正则结果: {result['llm_data']['status']}")

    def test_pattern_with_backslash(self):
        """反斜杠模式"""
        from app.tools.file.grep_file_content import grep
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "test.txt"), 'w', encoding='utf-8') as f:
                f.write("path: C:\\Users\\test\n")
                f.write("path: D:\\Data\n")

            result = _run(grep(r"C:\\Users", tmpdir))
            print(f"反斜杠搜索结果: {result['llm_data']['status']}")

    def test_glob_with_brace_expansion(self):
        """glob不支持{py,js}语法"""
        from app.tools.file.grep_file_content import grep
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "test.py"), 'w', encoding='utf-8') as f:
                f.write("import os\n")
            with open(os.path.join(tmpdir, "test.js"), 'w', encoding='utf-8') as f:
                f.write("const fs = require('fs');\n")

            # {py,js}不被fnmatch支持
            result = _run(grep("import|require", tmpdir, glob="*.{py,js}"))
            print(f"glob brace结果: {result['llm_data']['status']}")
            print(f"  total_files: {result['data'].get('total_files', 0)}")

    def test_search_in_binary_file(self):
        """在二进制文件中搜索"""
        from app.tools.file.grep_file_content import grep
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建一个假的二进制文件
            with open(os.path.join(tmpdir, "test.bin"), 'wb') as f:
                f.write(b'\x00\x01\x02\x03\x04\x05')

            result = _run(grep(r"\x00", tmpdir))
            print(f"二进制文件搜索结果: {result['llm_data']['status']}")

    def test_large_number_of_matches(self):
        """大量匹配结果"""
        from app.tools.file.grep_file_content import grep
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "test.txt"), 'w', encoding='utf-8') as f:
                for i in range(2000):
                    f.write(f"line {i}: match this\n")

            result = _run(grep("match this", tmpdir))
            print(f"大量匹配结果: {result['llm_data']['status']}")
            print(f"  total_matches: {result['data'].get('total_matches', 0)}")

    def test_pattern_with_lookahead(self):
        """正则前瞻断言"""
        from app.tools.file.grep_file_content import grep
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "test.txt"), 'w', encoding='utf-8') as f:
                f.write("foo bar\n")
                f.write("foo baz\n")
                f.write("bar foo\n")

            # 前瞻断言: foo在面跟着bar
            result = _run(grep(r"foo(?= bar)", tmpdir))
            print(f"前瞻断言结果: {result['llm_data']['status']}")
            if result['llm_data']['status']['exec_code'] == 'success':
                print(f"  total_matches: {result['data'].get('total_matches', 0)}")

    def test_pattern_with_backreference(self):
        """正则反向引用"""
        from app.tools.file.grep_file_content import grep
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "test.txt"), 'w', encoding='utf-8') as f:
                f.write("abc abc\n")
                f.write("abc xyz\n")

            # 反向引用: 匹配重复的单词
            result = _run(grep(r"(\w+)\s+\1", tmpdir))
            print(f"反向引用结果: {result['llm_data']['status']}")
            if result['llm_data']['status']['exec_code'] == 'success':
                print(f"  total_matches: {result['data'].get('total_matches', 0)}")

    def test_search_in_nested_dirs(self):
        """在嵌套目录中搜索"""
        from app.tools.file.grep_file_content import grep
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "sub1", "sub2"))
            with open(os.path.join(tmpdir, "a.txt"), 'w', encoding='utf-8') as f:
                f.write("found in root\n")
            with open(os.path.join(tmpdir, "sub1", "b.txt"), 'w', encoding='utf-8') as f:
                f.write("found in sub1\n")
            with open(os.path.join(tmpdir, "sub1", "sub2", "c.txt"), 'w', encoding='utf-8') as f:
                f.write("found in sub2\n")

            result = _run(grep("found", tmpdir))
            print(f"嵌套目录搜索结果: {result['llm_data']['status']}")
            print(f"  total_files: {result['data'].get('total_files', 0)}")

    def test_search_nonexistent_dir(self):
        """搜索不存在的目录"""
        from app.tools.file.grep_file_content import grep
        result = _run(grep("pattern", "Z:/nonexistent"))
        print(f"不存在目录结果: {result['llm_data']['status']}")

    def test_case_sensitive_search(self):
        """大小写敏感搜索"""
        from app.tools.file.grep_file_content import grep
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "test.txt"), 'w', encoding='utf-8') as f:
                f.write("Hello\nhello\nHELLO\n")

            result = _run(grep("Hello", tmpdir, ignore_case=False))
            print(f"大小写敏感结果: {result['llm_data']['status']}")
            if result['llm_data']['status']['exec_code'] == 'success':
                print(f"  total_matches: {result['data'].get('total_matches', 0)}")


class TestSearchFilesBugs:
    """search_files 专门找Bug"""

    def test_pattern_with_special_chars(self):
        """文件名包含特殊字符"""
        from app.tools.file.search_files import find
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建包含特殊字符的文件
            special_names = [
                "file with spaces.txt",
                "file-with-dashes.txt",
                "file_with_underscores.txt",
                "file.multiple.dots.txt",
                "file(1).txt",
                "file[1].txt",
            ]
            for name in special_names:
                with open(os.path.join(tmpdir, name), 'w') as f:
                    f.write("content")

            # 搜索包含空格的文件名
            result = _run(find("file with spaces*", tmpdir))
            print(f"特殊字符搜索结果: {result['llm_data']['status']}")
            print(f"  total: {result['data'].get('total', 0)}")

    def test_chinese_filename(self):
        """中文文件名"""
        from app.tools.file.search_files import find
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "测试文件.txt"), 'w', encoding='utf-8') as f:
                f.write("content")

            result = _run(find("*.txt", tmpdir))
            print(f"中文文件名结果: {result['llm_data']['status']}")
            print(f"  total: {result['data'].get('total', 0)}")

    def test_pattern_with_wildcard(self):
        """通配符模式"""
        from app.tools.file.search_files import find
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "test1.py"), 'w') as f:
                f.write("content")
            with open(os.path.join(tmpdir, "test2.py"), 'w') as f:
                f.write("content")
            with open(os.path.join(tmpdir, "test3.js"), 'w') as f:
                f.write("content")

            result = _run(find("test?.py", tmpdir))
            print(f"通配符搜索结果: {result['llm_data']['status']}")
            print(f"  total: {result['data'].get('total', 0)}")

    def test_empty_pattern(self):
        """空搜索模式"""
        from app.tools.file.search_files import find
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "test.txt"), 'w') as f:
                f.write("content")

            result = _run(find("", tmpdir))
            print(f"空模式结果: {result['llm_data']['status']}")

    def test_whitespace_pattern(self):
        """纯空白搜索模式"""
        from app.tools.file.search_files import find
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "test.txt"), 'w') as f:
                f.write("content")

            result = _run(find("   ", tmpdir))
            print(f"空白模式结果: {result['llm_data']['status']}")

    def test_type_filter_file(self):
        """type=file过滤"""
        from app.tools.file.search_files import find
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "subdir"))
            with open(os.path.join(tmpdir, "test.txt"), 'w') as f:
                f.write("content")

            result = _run(find("test*", tmpdir, type="file"))
            print(f"type=file结果: {result['llm_data']['status']}")
            print(f"  total: {result['data'].get('total', 0)}")

    def test_type_filter_directory(self):
        """type=directory过滤"""
        from app.tools.file.search_files import find
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "subdir"))
            with open(os.path.join(tmpdir, "test.txt"), 'w') as f:
                f.write("content")

            result = _run(find("sub*", tmpdir, type="directory"))
            print(f"type=directory结果: {result['llm_data']['status']}")
            print(f"  total: {result['data'].get('total', 0)}")

    def test_search_nonexistent_dir(self):
        """搜索不存在的目录"""
        from app.tools.file.search_files import find
        result = _run(find("*.txt", "Z:/nonexistent"))
        print(f"不存在目录结果: {result['llm_data']['status']}")

    def test_large_directory(self):
        """大目录搜索"""
        from app.tools.file.search_files import find
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建500个文件
            for i in range(500):
                with open(os.path.join(tmpdir, f"file_{i:04d}.txt"), 'w') as f:
                    f.write(f"content {i}")

            result = _run(find("*.txt", tmpdir))
            print(f"大目录搜索结果: {result['llm_data']['status']}")
            print(f"  total: {result['data'].get('total', 0)}")

    def test_search_with_dot_files(self):
        """搜索点文件(隐藏文件)"""
        from app.tools.file.search_files import find
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, ".hidden"), 'w') as f:
                f.write("content")
            with open(os.path.join(tmpdir, "visible.txt"), 'w') as f:
                f.write("content")

            result = _run(find(".*", tmpdir))
            print(f"点文件搜索结果: {result['llm_data']['status']}")
            print(f"  total: {result['data'].get('total', 0)}")

    def test_search_with_symlink(self):
        """符号链接搜索"""
        from app.tools.file.search_files import find
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建文件和符号链接
            real_file = os.path.join(tmpdir, "real.txt")
            with open(real_file, 'w') as f:
                f.write("content")

            try:
                link_file = os.path.join(tmpdir, "link.txt")
                os.symlink(real_file, link_file)
                result = _run(find("*.txt", tmpdir))
                print(f"符号链接搜索结果: {result['llm_data']['status']}")
                print(f"  total: {result['data'].get('total', 0)}")
            except OSError:
                # Windows可能不支持符号链接
                pass

    def test_case_sensitive_search(self):
        """大小写敏感搜索"""
        from app.tools.file.search_files import find
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "Test.TXT"), 'w') as f:
                f.write("content")
            with open(os.path.join(tmpdir, "test.txt"), 'w') as f:
                f.write("content")

            result = _run(find("test.txt", tmpdir, ignore_case=False))
            print(f"大小写敏感结果: {result['llm_data']['status']}")
            print(f"  total: {result['data'].get('total', 0)}")
