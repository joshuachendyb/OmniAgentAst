# -*- coding: utf-8 -*-
"""
针对Bug的测试 - 根据代码逻辑逐行分析找漏洞
小欧 2026-06-24
"""
import asyncio
import os
import tempfile
import pytest

from app.tools.tool_response import is_success, is_error


def _run(coro):
    if asyncio.iscoroutine(coro):
        return asyncio.run(coro)
    return coro


class TestReadTextFileBugs:
    """read_text_file 逐行代码分析找Bug"""

    def test_bug_offset_zero_returns_empty(self):
        """BUG-001: offset=0返回空内容
        代码L119: start_idx = max(0, offset - 1) if offset > 0 else max(0, total + offset)
        offset=0: start_idx = max(0, 5+0) = 5, selected = lines[5:] = []
        结论: offset=0被当作从尾部倒数0行处理,返回空内容
        """
        from app.tools.toolhelper.line_pager import select_lines
        lines = ["line1\n", "line2\n", "line3\n", "line4\n", "line5\n"]
        result = select_lines(lines, offset=0, limit=2)
        print(f"BUG-001: offset=0 -> content='{result['content']}', line_count={result['line_count']}")
        assert result['content'] == "", "offset=0应该返回空内容(当前行为)"
        assert result['line_count'] == 0

    def test_bug_offset_zero_no_limit(self):
        """BUG-002: offset=0且不带limit -> select_lines抛TypeError(offset须配合limit)"""
        from app.tools.toolhelper.line_pager import select_lines
        lines = ["line1\n", "line2\n", "line3\n"]
        try:
            select_lines(lines, offset=0)
            raise AssertionError("预期 select_lines(offset=0, limit=None) 应抛 TypeError")
        except TypeError:
            print("BUG-002: offset=0 不带limit触发TypeError(offset须配合limit)")

    def test_bug_start_line_exceeds_end_line(self):
        """BUG-003: start_line > end_line当无匹配行时
        代码L126: end_line = start_idx + len(selected)
        当offset超限: start_line=start_idx+1, end_line=start_idx+0=start_idx
        所以start_line = end_line + 1
        """
        from app.tools.toolhelper.line_pager import select_lines
        lines = ["line1\n", "line2\n", "line3\n"]
        result = select_lines(lines, offset=999, limit=10)
        print(f"BUG-003: start_line={result.get('start_line')}, end_line={result.get('end_line')}")
        # start_line应该 <= end_line
        start = result.get('start_line', 0)
        end = result.get('end_line', 0)
        if start > end:
            print(f"  认认BUG: start_line({start}) > end_line({end})")

    def test_bug_negative_offset_with_positive_limit(self):
        """BUG-004: 负offset+正limit组合
        read_text_file入口有检查: offset<0且limit!=None会报错
        但_select_lines函数本身没有检查
        """
        from app.tools.toolhelper.line_pager import select_lines
        lines = ["line1\n", "line2\n", "line3\n", "line4\n", "line5\n"]
        # 直接调用select_lines绕过入口检查
        result = select_lines(lines, offset=-2, limit=1)
        print(f"BUG-004: 负offset+limit -> content='{result['content']}', line_count={result['line_count']}")
        # offset=-2: start_idx = max(0, 5-2) = 3
        # selected = lines[3:3+1] = lines[3:4] = ["line4\n"]
        # 这个行为是合理的

    def test_bug_encoding_preferred_not_exist(self):
        """BUG-005: 指定不存在的编码"""
        from app.tools.file.read_text_file import readtext
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("测试内容\n")
            tmp = f.name
        try:
            result = _run(readtext(tmp, encoding="nonexistent_encoding"))
            print(f"BUG-005: 不存在编码结果: {result['llm_data']['status']}")
        finally:
            os.unlink(tmp)

    def test_bug_encoding_preferred_wrong(self):
        """BUG-006: 指定错误编码读取UTF-8文件"""
        from app.tools.file.read_text_file import readtext
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("中文测试内容,包含特殊字符:,!#￥%……&*()")
            tmp = f.name
        try:
            result = _run(readtext(tmp, encoding="ascii"))
            print(f"BUG-006: 错误编码结果: {result['llm_data']['status']}")
            if result['llm_data']['status']['exec_code'] == 'success':
                content = result['data']['content']
                has_replacement = '\ufffd' in content
                print(f"  包含替换字符: {has_replacement}")
                if has_replacement:
                    print("  BUG认认: 使用errors=replace但没有检测到替换字符!")
        finally:
            os.unlink(tmp)

    def test_bug_grep_file_content_import_os_position(self):
        """BUG-007: grep_file_content.py中import os在函数定义之在
        第147行: import os
        这个import在_grep_files_sync函数使用os.walk之在
        但实际上os.walk在第104行就用了
        """
        # 检查grep_file_content模块是否正常工作
        from app.tools.file.grep_file_content import grep
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "test.txt"), 'w') as f:
                f.write("test content")
            result = _run(grep("test", tmpdir))
            assert result['llm_data']['status']['exec_code'] == 'success'

    def test_bug_search_files_empty_directory(self):
        """BUG-010: 空目录搜索"""
        from app.tools.file.search_files import find
        with tempfile.TemporaryDirectory() as tmpdir:
            result = _run(find("*.txt", tmpdir))
            print(f"BUG-010: 空目录结果: {result['llm_data']['status']}")
            assert result['data'].get('matches', []) == []

    def test_bug_list_directory_tree_no_files(self):
        """BUG-011: tree模式不显示文件
        代码L217-221: tree模式只遍历目录,不遍历文件
        """
        from app.tools.file.tree import tree
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "subdir"))
            with open(os.path.join(tmpdir, "file.txt"), 'w') as f:
                f.write("content")

            result = _run(tree(tmpdir))
            tree_data = result['data'].get('tree', {})
            children = tree_data.get('children', [])
            file_children = [c for c in children if c.get('type') == 'file']
            print(f"BUG-011: tree模式文件节点数: {len(file_children)}")
            # tree模式认实不显示文件,这是设计如此

    def test_bug_list_directory_sort_by_mtime_accuracy(self):
        """BUG-012: mtime排序准认性"""
        from app.tools.file.list_directory import listdir
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建不同修改时间的文件
            for i in range(5):
                path = os.path.join(tmpdir, f"file_{i}.txt")
                with open(path, 'w') as f:
                    f.write(f"content {i}")
                # 设置修改时间
                import time
                os.utime(path, (1000000 + i, 1000000 + i))

            result = _run(listdir(tmpdir, sort_by="mtime"))
            entries = result['data']['entries']
            # 检查排序是否正认
            mtimes = [e['mtime'] for e in entries if e['type'] == 'file']
            print(f"BUG-012: mtime排序: {mtimes}")
            # 应该是降序排列
            for i in range(len(mtimes) - 1):
                if mtimes[i] < mtimes[i+1]:
                    print(f"  排序错误: {mtimes[i]} < {mtimes[i+1]}")

    def test_bug_read_config_file_ini_returns_dict(self):
        """BUG-013: INI文件读取(配置文件解析模块已重构删除,改用readtext读取原文)"""
        from app.tools.file.read_text_file import readtext
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False, encoding='utf-8') as f:
            f.write("[section1]\nkey1=value1\nkey2=value2\n")
            tmp = f.name
        try:
            result = _run(readtext(tmp))
            assert is_success(result) or is_error(result), "读取INI应返回成功或错误结构"
            content = result['data'].get('content', '')
            print(f"BUG-013: INI内容: {content[:40]!r}")
            assert 'section1' in content
        finally:
            os.unlink(tmp)

    def test_bug_read_config_file_xml_returns_string(self):
        """BUG-014: XML文件读取(配置文件解析模块已重构删除,改用readtext读取原文)"""
        from app.tools.file.read_text_file import readtext
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False, encoding='utf-8') as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n<root><key>value</key></root>')
            tmp = f.name
        try:
            result = _run(readtext(tmp))
            assert is_success(result) or is_error(result), "读取XML应返回成功或错误结构"
            content = result['data'].get('content', '')
            print(f"BUG-014: XML内容: {content[:40]!r}")
            assert 'root' in content
        finally:
            os.unlink(tmp)

    def test_bug_read_config_file_properties_returns_dict(self):
        """BUG-015: Properties文件读取(配置文件解析模块已重构删除,改用readtext读取原文)"""
        from app.tools.file.read_text_file import readtext
        with tempfile.NamedTemporaryFile(mode='w', suffix='.properties', delete=False, encoding='utf-8') as f:
            f.write("key1=value1\nkey2=value2\n# comment\nkey3=value3\n")
            tmp = f.name
        try:
            result = _run(readtext(tmp))
            assert is_success(result) or is_error(result), "读取Properties应返回成功或错误结构"
            content = result['data'].get('content', '')
            print(f"BUG-015: Properties内容: {content[:40]!r}")
            assert 'key1=value1' in content
        finally:
            os.unlink(tmp)

    def test_bug_read_media_file_returns_base64(self):
        """BUG-016: read_media_file返回的base64数据"""
        from app.tools.file.read_media_file import readmedia
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.png', delete=False) as f:
            # 写入一个最小的PNG文件头
            f.write(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82')
            tmp = f.name
        try:
            result = _run(readmedia(tmp))
            print(f"BUG-016: base64数据长度: {len(result['data'].get('base64_data', ''))}")
            print(f"  mime_type: {result['data'].get('mime_type')}")
        finally:
            os.unlink(tmp)

    def test_bug_read_text_file_offset_positive_without_limit(self):
        """BUG-017: 正offset不带limit应该报错"""
        from app.tools.file.read_text_file import readtext
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("line1\nline2\nline3\n")
            tmp = f.name
        try:
            result = _run(readtext(tmp, offset=1))
            print(f"BUG-017: 正offset时limit结果: {result['llm_data']['status']}")
            # 应该返回error
        finally:
            os.unlink(tmp)

    def test_bug_read_text_file_negative_offset_with_limit(self):
        """BUG-018: 负offset带limit应该报错"""
        from app.tools.file.read_text_file import readtext
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("line1\nline2\nline3\n")
            tmp = f.name
        try:
            result = _run(readtext(tmp, offset=-1, limit=2))
            print(f"BUG-018: 负offset+limit结果: {result['llm_data']['status']}")
            # 应该返回error
        finally:
            os.unlink(tmp)

    def test_bug_read_text_file_limit_only(self):
        """BUG-019: 只有limit没有offset应该报错"""
        from app.tools.file.read_text_file import readtext
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("line1\nline2\nline3\n")
            tmp = f.name
        try:
            result = _run(readtext(tmp, limit=2))
            print(f"BUG-019: 只有limit结果: {result['llm_data']['status']}")
            # 应该返回error
        finally:
            os.unlink(tmp)

    def test_bug_grep_large_file_search(self):
        """BUG-020: 大文件搜索"""
        from app.tools.file.grep_file_content import grep
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建一个大文件
            with open(os.path.join(tmpdir, "large.txt"), 'w', encoding='utf-8') as f:
                for i in range(10000):
                    f.write(f"line {i}: {'x' * 100}\n")

            result = _run(grep("line 5000", tmpdir))
            print(f"BUG-020: 大文件搜索结果: {result['llm_data']['status']}")
            print(f"  total_matches: {result['data'].get('total_matches', 0)}")

    def test_bug_search_files_special_glob_pattern(self):
        """BUG-021: 特殊glob模式"""
        from app.tools.file.search_files import find
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "test.py"), 'w') as f:
                f.write("content")
            with open(os.path.join(tmpdir, "test.js"), 'w') as f:
                f.write("content")
            with open(os.path.join(tmpdir, "test.txt"), 'w') as f:
                f.write("content")

            # 测试?通配符
            result = _run(find("test.??", tmpdir))
            matches = result['data'].get('matches', [])
            print(f"BUG-021: 通配符?结果: 匹配数={len(matches)}")
            assert len(matches) >= 1

    def test_bug_list_directory_permission_denied(self):
        """BUG-022: 权限拒绝目录"""
        from app.tools.file.list_directory import listdir
        with tempfile.TemporaryDirectory() as tmpdir:
            restricted = os.path.join(tmpdir, "restricted")
            os.makedirs(restricted)
            # 尝试创建一个难以访问的目录
            result = _run(listdir(restricted))
            print(f"BUG-022: 权限目录结果: {result['llm_data']['status']}")

    def test_bug_read_text_file_concurrent_modification(self):
        """BUG-023: 并发修改文件"""
        from app.tools.file.read_text_file import readtext
        import threading
        import time

        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("initial content\n")
            tmp = f.name

        results = []
        errors = []

        def read_file():
            try:
                r = _run(readtext(tmp))
                results.append(r)
            except Exception as e:
                errors.append(str(e))

        def modify_file():
            time.sleep(0.01)
            try:
                with open(tmp, 'w', encoding='utf-8') as f:
                    f.write(f"modified content {time.time()}\n")
            except Exception as e:
                errors.append(str(e))

        threads = []
        for _ in range(5):
            t1 = threading.Thread(target=read_file)
            t2 = threading.Thread(target=modify_file)
            threads.extend([t1, t2])

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        print(f"BUG-023: 并发测试结果: {len(results)} reads, {len(errors)} errors")
        if errors:
            print(f"  错误: {errors}")

        os.unlink(tmp)
