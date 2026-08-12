# -*- coding: utf-8 -*-
"""
第三批漏洞挖掘 - 深入隐蔽bug
小健 2026-06-24
"""
import asyncio
import os
import tempfile
import pytest

from app.tools.file.read_text_file import readtext
# 适配: read_config_file 模块已在重构中删除, 配置文件读取改为 readtext 读取原文 - 小欧 2026-07-12
read_config_file = readtext


def _run(coro):
    if asyncio.iscoroutine(coro):
        return asyncio.run(coro)
    return coro


# ========== BUG: read_text_file encoding检测逻辑 ==========

class TestEncodingDetectionLogic:
    """BUG-300: encoding检测逻辑漏洞"""

    def test_preferred_encoding_skips_detection(self):
        """BUG-300: 当指定encoding时,do_detect=False,跳过\ufffd检测
        read_text_file.py L85: do_detect = preferred is None
        指定encoding时即使有\ufffd也返回success
        """
        from app.tools.file.read_text_file import _try_read_file_with_encodings
        from pathlib import Path
        # 创建GBK编码文件
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.txt', delete=False) as f:
            f.write("中文GBK内容测试".encode('gbk'))
            tmp = f.name
        try:
            # 用utf-8去读GBK文件——应该产生\ufffd
            content, enc, error = _run(_try_read_file_with_encodings(Path(tmp), preferred="utf-8"))
            has_replacement = '\ufffd' in content if content else False
            print(f"BUG-300: preferred=utf-8读GBK → enc={enc}, \ufffd={has_replacement}, error={error}")
            # 因为do_detect=False,不会检测\ufffd
            if has_replacement:
                print("  BUG认认: 指定encoding时不检测\ufffd,返回乱码内容")
        finally:
            os.unlink(tmp)

    def test_auto_detection_rejects_replacement(self):
        """BUG-301: 自动检测会拒绝含\ufffd的结果
        但最终如果没有干净的编码,返回最在一个结果(含\ufffd)
        """
        from app.tools.file.read_text_file import _try_read_file_with_encodings
        from pathlib import Path
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.txt', delete=False) as f:
            f.write(b'\x80\x81\x82\x83\x84\x85')
            tmp = f.name
        try:
            content, enc, error = _run(_try_read_file_with_encodings(Path(tmp)))
            print(f"BUG-301: 垃圾文件编码检测 → enc={enc}, error={error}")
            # 所有编码都失败,返回最在一种编码的内容
            if enc and content:
                has_replacement = '\ufffd' in content
                print(f"  \\ufffd存在: {has_replacement}")
        finally:
            os.unlink(tmp)

    def test_gbk_file_with_preferred_utf8(self):
        """BUG-302: GBK文件指定UTF-8读取"""
        from app.tools.file.read_text_file import readtext
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.txt', delete=False) as f:
            f.write("测试GBK编码内容".encode('gbk'))
            tmp = f.name
        try:
            result = _run(readtext(tmp, encoding="utf-8"))
            content = result['data']['content']
            status = result['llm_data']['status']['exec_code']
            # 获取不含\u的显示
            has_repl = '\ufffd' in content
            print(f"BUG-302: GBK文件+preferred=utf-8 → status={status}, \\ufffd={has_repl}")
            if has_repl and status == 'success':
                print("  BUG认认: 返回乱码但标记为success")
        finally:
            os.unlink(tmp)

    def test_utf8_file_with_preferred_gbk(self):
        """BUG-303: UTF-8文件指定GBK读取"""
        from app.tools.file.read_text_file import readtext
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("测试UTF-8编码内容ABC")
            tmp = f.name
        try:
            result = _run(readtext(tmp, encoding="gbk"))
            content = result['data']['content']
            status = result['llm_data']['status']['exec_code']
            has_repl = '\ufffd' in content
            print(f"BUG-303: UTF-8文件+preferred=gbk → status={status}, \\ufffd={has_repl}")
            if has_repl and status == 'success':
                print("  BUG认认: 返回乱码但标记为success")
        finally:
            os.unlink(tmp)


# ========== BUG: grep_file_content 正则与glob交互 ==========

class TestGrepRegexGlobInteraction:
    """BUG-304: grep正则与glob的交互问题"""

    def test_grep_with_regex_special_in_glob(self):
        """BUG-305: glob模式中的特殊字符"""
        from app.tools.file.grep_file_content import grep
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "test[1].txt"), 'w') as f:
                f.write("pattern\n")
            # glob="test[1].txt"会被fnmatch解释为字符类
            result = _run(grep("pattern", tmpdir, glob="test[1].txt"))
            total = result['data'].get('total_matches', 0)
            print(f"BUG-305: glob含[] → total_matches={total}")
            # fnmatch.fnmatch("test[1].txt", "test[1].txt") → True (因为[]在fnmatch中是字符类)
            # 但实际上[1]就是匹配字符'1',所以应该能匹配

    def test_grep_with_dotglob(self):
        """BUG-306: glob模式中的.字符"""
        from app.tools.file.grep_file_content import grep
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "test.txt"), 'w') as f:
                f.write("pattern\n")
            with open(os.path.join(tmpdir, "testtxt"), 'w') as f:
                f.write("pattern\n")
            result = _run(grep("pattern", tmpdir, glob="test.txt"))
            total = result['data'].get('total_files', 0)
            print(f"BUG-306: glob=test.txt → total_files={total}")
            # fnmatch.fnmatch("testtxt", "test.txt") → False (.匹配任意字符)
            # fnmatch.fnmatch("test.txt", "test.txt") → True

    def test_grep_with_star_pattern(self):
        """BUG-307: glob用*匹配"""
        from app.tools.file.grep_file_content import grep
        with tempfile.TemporaryDirectory() as tmpdir:
            for name in ["a.py", "b.py", "c.js", "d.txt"]:
                with open(os.path.join(tmpdir, name), 'w') as f:
                    f.write("pattern\n")
            result = _run(grep("pattern", tmpdir, glob="*.py"))
            total = result['data'].get('total_files', 0)
            print(f"BUG-307: glob=*.py → total_files={total}")
            assert total == 2

    def test_grep_with_brace_pattern_fails(self):
        """BUG-308: glob用{py,js}失败"""
        from app.tools.file.grep_file_content import grep
        with tempfile.TemporaryDirectory() as tmpdir:
            for name in ["a.py", "b.js"]:
                with open(os.path.join(tmpdir, name), 'w') as f:
                    f.write("pattern\n")
            result = _run(grep("pattern", tmpdir, glob="*.{py,js}"))
            matches = result['data'].get('matches', [])
            total = len(matches)
            print(f"BUG-308: glob=*.{{py,js}} → total_files={total}")
            # fnmatch不支持{py,js},应匹配2个
            if total == 0:
                print("  BUG认认: fnmatch不支持brace模式,用户可能期望能用")


# ========== BUG: read_config_file 各种格式异常 ==========

class TestConfigFileEdgeCases:
    """BUG-309: 配置文件各种边界情况"""

    def test_json_large_value(self):
        """BUG-310: JSON包含超长字符串"""
        # REMOVED: from app.tools.file.read_config_file import read_config_file (module deleted in refactor)
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
            big_value = "x" * 100000
            f.write(f'{{"key": "{big_value}"}}')
            tmp = f.name
        try:
            result = _run(read_config_file(tmp))
            print(f"BUG-310: 超长JSON值 → {result['llm_data']['status']['exec_code']}")
        finally:
            os.unlink(tmp)

    def test_json_nested_deep(self):
        """BUG-311: JSON深层嵌套"""
        # REMOVED: from app.tools.file.read_config_file import read_config_file (module deleted in refactor)
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
            # 100层嵌套
            s = '{"a":' * 50 + '"deep"' + '}' * 50
            f.write(s)
            tmp = f.name
        try:
            result = _run(read_config_file(tmp))
            print(f"BUG-311: 100层嵌套JSON → {result['llm_data']['status']['exec_code']}")
        finally:
            os.unlink(tmp)

    def test_json_array_root(self):
        """BUG-312: JSON根节点是数组"""
        # REMOVED: from app.tools.file.read_config_file import read_config_file (module deleted in refactor)
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
            f.write('[1, 2, 3, "hello"]')
            tmp = f.name
        try:
            result = _run(read_config_file(tmp))
            if result['llm_data']['status']['exec_code'] == 'success':
                data = result['data'].get('content')
                print(f"BUG-312: JSON数组根节点 → type={type(data).__name__}, len={len(data) if data else 0}")
        finally:
            os.unlink(tmp)

    def test_yaml_empty(self):
        """BUG-313: 空YAML文件"""
        # REMOVED: from app.tools.file.read_config_file import read_config_file (module deleted in refactor)
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as f:
            f.write("")
            tmp = f.name
        try:
            result = _run(read_config_file(tmp))
            print(f"BUG-313: 空YAML → {result['llm_data']['status']}")
        finally:
            os.unlink(tmp)

    def test_yaml_with_tabs(self):
        """BUG-314: YAML使用Tab缩进(应该报错)"""
        # REMOVED: from app.tools.file.read_config_file import read_config_file (module deleted in refactor)
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as f:
            f.write("key:\n\tvalue: test\n")
            tmp = f.name
        try:
            result = _run(read_config_file(tmp))
            print(f"BUG-314: YAML Tab缩进 → {result['llm_data']['status']}")
        finally:
            os.unlink(tmp)

    def test_properties_special_chars(self):
        """BUG-315: Properties文件特殊字符"""
        # REMOVED: from app.tools.file.read_config_file import read_config_file (module deleted in refactor)
        with tempfile.NamedTemporaryFile(mode='w', suffix='.properties', delete=False, encoding='utf-8') as f:
            f.write("key1=value=with=equals\nkey2:value:with:colons\nkey3=normal\n")
            tmp = f.name
        try:
            result = _run(read_config_file(tmp))
            if result['llm_data']['status']['exec_code'] == 'success':
                data = result['data'].get('content')
                print(f"BUG-315: Properties特殊字符 → {data}")
                # key1的值应该是"with=equals"(split("=",1)取右边)
                # key2的值应该是"with:colons"(split(":",1)取右边)
        finally:
            os.unlink(tmp)

    def test_ini_special_chars_in_value(self):
        """BUG-316: INI值中的特殊字符"""
        # REMOVED: from app.tools.file.read_config_file import read_config_file (module deleted in refactor)
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False, encoding='utf-8') as f:
            f.write("[section]\nkey1=value with spaces\nkey2=value#with#hash\nkey3=val=ue\n")
            tmp = f.name
        try:
            result = _run(read_config_file(tmp))
            if result['llm_data']['status']['exec_code'] == 'success':
                data = result['data'].get('content')
                print(f"BUG-316: INI特殊字符 → {data}")
                # #在INI中是注释,所以key2的值可能是"value"
        finally:
            os.unlink(tmp)

    def test_xml_cdata(self):
        """BUG-317: XML包含CDATA"""
        # REMOVED: from app.tools.file.read_config_file import read_config_file (module deleted in refactor)
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False, encoding='utf-8') as f:
            f.write('<?xml version="1.0"?><root><data><![CDATA[<p>HTML content</p>]]></data></root>')
            tmp = f.name
        try:
            result = _run(read_config_file(tmp))
            if result['llm_data']['status']['exec_code'] == 'success':
                data = result['data'].get('content')
                print(f"BUG-317: XML CDATA → {data}")
        finally:
            os.unlink(tmp)

    def test_xml_attributes(self):
        """BUG-318: XML属性忽略"""
        # REMOVED: from app.tools.file.read_config_file import read_config_file (module deleted in refactor)
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False, encoding='utf-8') as f:
            f.write('<?xml version="1.0"?><root><item id="1" name="test">value</item></root>')
            tmp = f.name
        try:
            result = _run(read_config_file(tmp))
            if result['llm_data']['status']['exec_code'] == 'success':
                data = result['data'].get('content')
                print(f"BUG-318: XML属性 → {data}")
                # elem_to_dict不处理属性,id和name会丢失
        finally:
            os.unlink(tmp)


# ========== BUG: list_directory 边界情况 ==========

class TestListDirectoryEdgeCases:
    """BUG-319: list_directory各种边界情况"""

    def test_empty_directory(self):
        """BUG-320: 空目录"""
        from app.tools.file.list_directory import listdir
        with tempfile.TemporaryDirectory() as tmpdir:
            result = _run(listdir(tmpdir))
            total_val = result['llm_data']['metrics']['total']['value']
            print(f"BUG-320: 空目录 → total={total_val}")
            assert total_val == 0

    def test_directory_with_only_hidden_files(self):
        """BUG-321: 只有隐藏文件的目录"""
        from app.tools.file.list_directory import listdir
        with tempfile.TemporaryDirectory() as tmpdir:
            for name in [".hidden1", ".hidden2", ".config"]:
                with open(os.path.join(tmpdir, name), 'w') as f:
                    f.write("content")
            result_no = _run(listdir(tmpdir, include_hidden=False))
            result_yes = _run(listdir(tmpdir, include_hidden=True))
            print(f"BUG-321: 隐藏文件: hidden=False → {result_no['llm_data']['metrics']['total']['value']}, hidden=True → {result_yes['llm_data']['metrics']['total']['value']}")

    def test_sort_by_size_with_mixed_types(self):
        """BUG-322: sort_by=size目录和文件混合"""
        from app.tools.file.list_directory import listdir
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "adir"))
            with open(os.path.join(tmpdir, "small.txt"), 'w') as f:
                f.write("x")
            with open(os.path.join(tmpdir, "big.txt"), 'w') as f:
                f.write("x" * 10000)
            result = _run(listdir(tmpdir, sort_by="size"))
            entries = result['data']['entries']
            # size排序:目录(size=None)排在文件前面
            sizes = [(e['name'], e.get('size')) for e in entries]
            print(f"BUG-322: size排序混合 → {sizes}")

    def test_sort_by_mtime_same_time(self):
        """BUG-323: sort_by=mtime同时问文件"""
        from app.tools.file.list_directory import listdir
        with tempfile.TemporaryDirectory() as tmpdir:
            for i in range(5):
                with open(os.path.join(tmpdir, f"f{i}.txt"), 'w') as f:
                    f.write("content")
                os.utime(os.path.join(tmpdir, f"f{i}.txt"), (1000000, 1000000))
            result = _run(listdir(tmpdir, sort_by="mtime"))
            names = [e['name'] for e in result['data']['entries']]
            print(f"BUG-323: 同时问mtime排序 → {names}")

    def test_statistics_size_distribution(self):
        """BUG-324: size_distribution统计准认性"""
        from app.tools.file.list_directory import listdir
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建不同大小的文件
            sizes = [100, 1024, 5000, 50000, 500000, 2000000]
            for i, size in enumerate(sizes):
                with open(os.path.join(tmpdir, f"f{i}.txt"), 'w') as f:
                    f.write("x" * size)
            result = _run(listdir(tmpdir))
            # 当前size_distribution已移出data(不再暴露), 验证总文件数正确 - 小欧 2026-07-12
            total_val = result['llm_data']['metrics']['total']['value']
            print(f"BUG-324: total → {total_val}")

    def test_file_types_counter(self):
        """BUG-325: file_types统计"""
        from app.tools.file.list_directory import listdir
        with tempfile.TemporaryDirectory() as tmpdir:
            for ext in ['.py', '.py', '.js', '.txt', '.md', '.json']:
                with open(os.path.join(tmpdir, f"file{ext}"), 'w') as f:
                    f.write("content")
            result = _run(listdir(tmpdir))
            # 当前file_types已移出data(不再暴露), 验证总文件数正确 - 小欧 2026-07-12
            total_val = result['llm_data']['metrics']['total']['value']
            print(f"BUG-325: total → {total_val}")


# ========== BUG: read_text_file 错误信息质量 ==========

class TestReadTextFileErrorMessages:
    """BUG-326: read_text_file错误信息质量"""

    def test_symlink_file(self):
        """BUG-327: 符号链接文件"""
        from app.tools.file.read_text_file import readtext
        with tempfile.TemporaryDirectory() as tmpdir:
            real = os.path.join(tmpdir, "real.txt")
            link = os.path.join(tmpdir, "link.txt")
            with open(real, 'w') as f:
                f.write("real content")
            try:
                os.symlink(real, link)
                result = _run(readtext(link))
                print(f"BUG-327: 符号链接 → {result['llm_data']['status']['exec_code']}")
                if result['llm_data']['status']['exec_code'] == 'success':
                    print(f"  content: {result['data']['content']}")
            except OSError:
                print("  符号链接创建失败(可能需要管理员权限)")

    def test_read_only_permission(self):
        """BUG-328: 只读权限文件"""
        from app.tools.file.read_text_file import readtext
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("content")
            tmp = f.name
        try:
            result = _run(readtext(tmp))
            print(f"BUG-328: 正常文件 → {result['llm_data']['status']['exec_code']}")
        finally:
            os.unlink(tmp)

    def test_very_long_line(self):
        """BUG-329: 超长行"""
        from app.tools.file.read_text_file import readtext
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("x" * 100000 + "\n")
            tmp = f.name
        try:
            result = _run(readtext(tmp))
            print(f"BUG-329: 10万字符行 → {result['llm_data']['status']['exec_code']}, line_count={result['llm_data']['metrics']['lines']['value']}")
        finally:
            os.unlink(tmp)

    def test_many_lines(self):
        """BUG-330: 大量行"""
        from app.tools.file.read_text_file import readtext
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            for i in range(10000):
                f.write(f"line {i}\n")
            tmp = f.name
        try:
            result = _run(readtext(tmp))
            print(f"BUG-330: 1万行 → {result['llm_data']['status']['exec_code']}, total_lines={result['llm_data']['metrics']['total_lines']['value']}")
        finally:
            os.unlink(tmp)

    def test_windows_line_endings(self):
        """BUG-331: Windows换行符(CRLF)"""
        from app.tools.file.read_text_file import readtext
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.txt', delete=False) as f:
            f.write(b"line1\r\nline2\r\nline3\r\n")
            tmp = f.name
        try:
            result = _run(readtext(tmp))
            total = result['llm_data']['metrics']['total_lines']['value']
            content = result['data']['content']
            print(f"BUG-331: CRLF → total_lines={total}")
            print(f"  content repr前30字 {repr(content[:30])}")
        finally:
            os.unlink(tmp)

    def test_mixed_line_endings(self):
        """BUG-332: 混合换行符"""
        from app.tools.file.read_text_file import readtext
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.txt', delete=False) as f:
            f.write(b"line1\nline2\r\nline3\rline4\n")
            tmp = f.name
        try:
            result = _run(readtext(tmp))
            total = result['llm_data']['metrics']['total_lines']['value']
            print(f"BUG-332: 混合换行 → total_lines={total}")
        finally:
            os.unlink(tmp)

    def test_only_carriage_return(self):
        """BUG-333: 只有\\r的行"""
        from app.tools.file.read_text_file import readtext
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.txt', delete=False) as f:
            f.write(b"line1\rline2\rline3")
            tmp = f.name
        try:
            result = _run(readtext(tmp))
            total = result['llm_data']['metrics']['total_lines']['value']
            print(f"BUG-333: 只有CR → total_lines={total}")
        finally:
            os.unlink(tmp)

    def test_null_bytes_in_text(self):
        """BUG-334: 文本文件包含null字节"""
        from app.tools.file.read_text_file import readtext
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.txt', delete=False) as f:
            f.write(b"hello\x00world\x00\x00test\n")
            tmp = f.name
        try:
            result = _run(readtext(tmp))
            status = result['llm_data']['status']['exec_code']
            print(f"BUG-334: null字节 → status={status}")
            if status == 'success':
                content = result['data']['content']
                has_null = '\x00' in content
                print(f"  含null: {has_null}")
        finally:
            os.unlink(tmp)

    def test_utf16_file(self):
        """BUG-335: UTF-16编码文件"""
        from app.tools.file.read_text_file import readtext
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.txt', delete=False) as f:
            f.write("UTF16内容测试".encode('utf-16-le'))
            tmp = f.name
        try:
            result = _run(readtext(tmp))
            print(f"BUG-335: UTF-16 → enc={result['data'].get('encoding')}, status={result['llm_data']['status']['exec_code']}")
        finally:
            os.unlink(tmp)

    def test_file_not_exists(self):
        """BUG-336: 不存在的文件"""
        from app.tools.file.read_text_file import readtext
        result = _run(readtext("G:\\nonexistent_file.txt"))
        print(f"BUG-336: 不存在文件 → {result['llm_data']['status']['exec_code']}")

    def test_directory_not_file(self):
        """BUG-337: 路径是目录"""
        from app.tools.file.read_text_file import readtext
        with tempfile.TemporaryDirectory() as tmpdir:
            result = _run(readtext(tmpdir))
            print(f"BUG-337: 目录路径 → {result['llm_data']['status']['exec_code']}")
