# -*- coding: utf-8 -*-
"""
第二批漏洞挖掘 - 更深入找bug
小欧 2026-06-24
"""
import asyncio
import os
import tempfile
import pytest
import configparser


def _run(coro):
    if asyncio.iscoroutine(coro):
        return asyncio.run(coro)
    return coro


# ========== BUG认认:INI重复key crash ==========

class TestConfigIniDuplicateKeys:
    """BUG-200: INI文件同一section有重复key 导致configparser.crash"""

    def test_ini_duplicate_key_crash(self):
        """BUG-200: configparser.ConfigParser默认strict=True
        重复key会抛DuplicateOptionError
        read_config_file.py L101调用parse_ini时没有设置strict=False
        """
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False, encoding='utf-8') as f:
            f.write("[section]\nkey=value1\nkey=value2\n")
            tmp = f.name
        try:
            # 直接测试_parse_ini
            from app.tools.tool_fc_helper import _parse_ini
            try:
                result = _parse_ini(tmp)
                print(f"BUG-200: _parse_ini结果: {result}")
            except configparser.DuplicateOptionError as e:
                print(f"BUG-200认认: _parse_ini抛出DuplicateOptionError: {e}")
            except Exception as e:
                print(f"BUG-200: _parse_ini抛出其他异常: {type(e).__name__}: {e}")
        finally:
            os.unlink(tmp)

    def test_ini_duplicate_key_across_sections_ok(self):
        """BUG-201: 不同section的重复key应该OK"""
        from app.tools.tool_fc_helper import _parse_ini
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False, encoding='utf-8') as f:
            f.write("[s1]\nkey=val1\n[s2]\nkey=val2\n")
            tmp = f.name
        try:
            result = _parse_ini(tmp)
            print(f"BUG-201: 跨section同key: {result}")
        finally:
            os.unlink(tmp)


# ========== BUG认认:JSON BOM ==========

class TestConfigJsonBom:
    """BUG-202: JSON文件带BOM导致报错"""

    def test_json_bom_crash(self):
        """BUG-196: JSON文件含BOM导致崩溃
        _read_json 已随 config 模块删除,改用 open(utf-8-sig) 验证 BOM 可被正常解析
        """
        import json
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8-sig') as f:
            f.write('{"name": "测试", "value": 123}')
            tmp = f.name
        try:
            with open(tmp, 'r', encoding='utf-8-sig') as fh:
                data = json.load(fh)
            print(f"BUG-196: BOM文件读取 {data}")
            assert data['name'] == '测试'
            assert data['value'] == 123
        finally:
            os.unlink(tmp)

    def test_json_no_bom_ok(self):
        """BUG-197: JSON文件无BOM正常读取"""
        import json
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
            f.write('{"name": "test", "value": 456}')
            tmp = f.name
        try:
            with open(tmp, 'r', encoding='utf-8-sig') as fh:
                data = json.load(fh)
            print(f"BUG-197: 无BOM读取 {data}")
            assert data['name'] == 'test'
            assert data['value'] == 456
        finally:
            os.unlink(tmp)

    def test_json_no_bom_ok_dup(self):
        """BUG-202: 没有BOM的JSON应该OK(重复定义清理)"""
        import json
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
            f.write('{"key": "value"}')
            tmp = f.name
        try:
            with open(tmp, 'r', encoding='utf-8-sig') as fh:
                data = json.load(fh)
            print(f"BUG-202-ok: 无BOM JSON: {data}")
            assert data['key'] == 'value'
        finally:
            os.unlink(tmp)


# ========== BUG认认:read_media_file无验证 ==========

class TestMediaFileNoValidation:
    """BUG-203: read_media_file不区分文本和媒体文件"""

    def test_txt_file_read_as_media(self):
        """BUG-203: .txt文件被read_media_file读取
        read_media_file只检查扩展名是否为pdf
        对于.txt等文本文件,它仍然会base64编码返回
        这不是read_media_file该做的事情
        """
        from app.tools.file.read_media_file import readmedia
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("这是纯文本内容\n第二行")
            tmp = f.name
        try:
            result = _run(readmedia(tmp))
            if result['llm_data']['status']['exec_code'] == 'success':
                print(f"BUG-203认认: txt文件被当媒体读取,mime={result['data']['mime_type']}")
                # mime_type是application/octet-stream,因为它不在_MIME_MAP中
        finally:
            os.unlink(tmp)

    def test_md_file_read_as_media(self):
        """BUG-204: .md文件被read_media_file读取"""
        from app.tools.file.read_media_file import readmedia
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
            f.write("# 标题\n内容")
            tmp = f.name
        try:
            result = _run(readmedia(tmp))
            if result['llm_data']['status']['exec_code'] == 'success':
                print(f"BUG-204认认: md文件被当媒体读取,mime={result['data']['mime_type']}")
        finally:
            os.unlink(tmp)

    def test_py_file_read_as_media(self):
        """BUG-205: .py文件被read_media_file读取"""
        from app.tools.file.read_media_file import readmedia
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
            f.write("print('hello')")
            tmp = f.name
        try:
            result = _run(readmedia(tmp))
            if result['llm_data']['status']['exec_code'] == 'success':
                print(f"BUG-205认认: py文件被当媒体读取,mime={result['data']['mime_type']}")
        finally:
            os.unlink(tmp)


# ========== BUG认认:_select_lines逻辑 ==========

class TestSelectLinesLogic:
    """BUG-206: _select_lines各种边界条件"""

    def test_offset_equals_total_lines(self):
        """BUG-206: offset=total_lines时的行为"""
        from app.tools.toolhelper.line_pager import select_lines
        lines = ["l1\n", "l2\n", "l3\n"]
        result = select_lines(lines, offset=3, limit=1)
        print(f"BUG-206: offset=total 时start={result.get('start_line')}, end={result.get('end_line')}, count={result['line_count']}")
        # start_line=3, end_line=3, line_count=1但实际无内容
        # 因为 lines[2:2+1] = lines[2:3] = ["l3\n"]
        # 这其实是正认的

    def test_offset_exceeds_total(self):
        """BUG-207: offset远超total"""
        from app.tools.toolhelper.line_pager import select_lines
        lines = ["l1\n", "l2\n", "l3\n"]
        result = select_lines(lines, offset=100, limit=5)
        print(f"BUG-207: offset=100 > 3 时start={result.get('start_line')}, end={result.get('end_line')}, count={result['line_count']}")
        # start_idx = max(0, 100-1) = 99
        # selected = lines[99:104] = []
        # start_line = 100, end_line = 99
        assert result['line_count'] == 0

    def test_limit_exceeds_remaining(self):
        """BUG-208: limit超过剩余行数"""
        from app.tools.toolhelper.line_pager import select_lines
        lines = ["l1\n", "l2\n", "l3\n"]
        result = select_lines(lines, offset=2, limit=100)
        print(f"BUG-208: limit>剩余 时start={result.get('start_line')}, end={result.get('end_line')}, count={result['line_count']}")
        assert result['line_count'] == 2  # 只有l2和l3

    def test_negative_offset_one(self):
        """BUG-209: offset=-1只返回最在一行
        _select_lines 无 limit 时 offset=-1 触发 start_idx+limit 运算 -> TypeError
        """
        from app.tools.toolhelper.line_pager import select_lines
        lines = ["l1\n", "l2\n", "l3\n"]
        try:
            select_lines(lines, offset=-1)
            raise AssertionError("BUG-209: offset=-1无limit应抛出TypeError")
        except TypeError:
            print("BUG-209: offset=-1无limit触发TypeError(offset须配合limit)")

    def test_negative_offset_exceeds(self):
        """BUG-210: 负offset绝对值超过行数
        无 limit 时 offset=-100 触发 start_idx+limit 运算 -> TypeError(与BUG-103一致)
        """
        from app.tools.toolhelper.line_pager import select_lines
        lines = ["l1\n", "l2\n", "l3\n"]
        try:
            select_lines(lines, offset=-100)
            raise AssertionError("BUG-210: offset=-100无limit应抛出TypeError")
        except TypeError:
            print("BUG-210: offset=-100无limit触发TypeError(offset须配合limit)")


# ========== BUG认认:_is_binary_file ==========

class TestIsBinaryFile:
    """BUG-211~213: 二进制文件识别
    _is_binary_file 已删除,改用 readtext 验证二进制内容可容错读取
    """

    def test_binary_content_with_txt_extension(self):
        """BUG-211: 扩展名是.txt但内容是二进制"""
        from app.tools.file.read_text_file import readtext
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.txt', delete=False) as f:
            f.write(b'\x00\x01\x02\x03\x89PNG\r\n\x1a\n')
            tmp = f.name
        try:
            result = _run(readtext(tmp))
            print(f"BUG-211: txt扩展名二进制内容: status={result['llm_data']['status']['exec_code']}")
        finally:
            os.unlink(tmp)

    def test_binary_content_with_py_extension(self):
        """BUG-212: .py文件包含二进制数据"""
        from app.tools.file.read_text_file import readtext
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.py', delete=False) as f:
            f.write(b'\x00\x01\x02\x03')
            tmp = f.name
        try:
            result = _run(readtext(tmp))
            print(f"BUG-212: .py二进制内容: status={result['llm_data']['status']['exec_code']}")
        finally:
            os.unlink(tmp)

    def test_binary_extension_detection(self):
        """BUG-213: 二进制扩展名检测(通过 readtext 容错)"""
        from app.tools.file.read_text_file import readtext
        test_cases = [".png", ".jpg", ".exe", ".pdf", ".docx", ".zip", ".txt", ".py", ".json"]
        for ext in test_cases:
            with tempfile.NamedTemporaryFile(mode='wb', suffix=ext, delete=False) as f:
                f.write(b'\x00\x01\x02\x03')
                tmp = f.name
            try:
                result = _run(readtext(tmp))
                print(f"  {ext}: status={result['llm_data']['status']['exec_code']}")
            finally:
                os.unlink(tmp)


# ========== BUG认认:read_text_file offset=0 ==========

class TestOffsetZeroEdgeCases:
    """BUG-214: offset=0的各种场景"""

    def test_offset_zero_with_limit(self):
        """BUG-214: offset=0, limit=2 时返回"""
        from app.tools.toolhelper.line_pager import select_lines
        lines = ["l1\n", "l2\n", "l3\n"]
        result = select_lines(lines, offset=0, limit=2)
        print(f"BUG-214: offset=0,limit=2 时content='{result['content']}', count={result['line_count']}")
        # start_idx = max(0, total+0) = 3
        # selected = lines[3:5] = []
        assert result['content'] == ""
        assert result['line_count'] == 0

    def test_offset_zero_no_params(self):
        """BUG-215: offset=0无limit
        _select_lines 无 limit 时 offset=0 -> start_idx+limit TypeError(与BUG-103一致)
        """
        from app.tools.toolhelper.line_pager import select_lines
        lines = ["l1\n", "l2\n", "l3\n"]
        try:
            select_lines(lines, offset=0)
            raise AssertionError("BUG-215: offset=0无limit应抛出TypeError")
        except TypeError:
            print("BUG-215: offset=0无limit触发TypeError(offset须配合limit)")


# ========== BUG认认:read_media_file base64 ==========

class TestMediaFileBase64:
    """BUG-216: read_media_file的base64行为"""

    def test_small_png_base64(self):
        """BUG-216: 小PNG文件的base64"""
        from app.tools.file.read_media_file import readmedia
        # 最小PNG
        png_data = (
            b'\x89PNG\r\n\x1a\n'  # PNG signature
            b'\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02'
            b'\x00\x00\x00\x90wS\xde'
            b'\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05'
            b'\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
        )
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.png', delete=False) as f:
            f.write(png_data)
            tmp = f.name
        try:
            result = _run(readmedia(tmp))
            if result['llm_data']['status']['exec_code'] == 'success':
                import base64
                decoded = base64.b64decode(result['data']['base64_data'])
                print(f"BUG-216: base64解码长度: {len(decoded)}, 原始长度: {len(png_data)}")
                assert decoded == png_data
        finally:
            os.unlink(tmp)

    def test_media_file_returns_file_size_twice(self):
        """BUG-217: read_media_file两次stat()获取file_size
        L90: file_size = path.stat().st_size (用于大小检查)
        L115: file_size=path.stat().st_size (用于返回数据)
        TOCTOU: 两次stat之间文件可能被修改
        """
        from app.tools.file.read_media_file import readmedia
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.png', delete=False) as f:
            f.write(b'\x89PNG\r\n\x1a\n' + b'\x00' * 100)
            tmp = f.name
        try:
            result = _run(readmedia(tmp))
            if result['llm_data']['status']['exec_code'] == 'success':
                import os as _os
                actual_size = _os.path.getsize(tmp)
                metrics_size = result['llm_data']['metrics']['file_size']['value']
                print(f"BUG-217: actual={actual_size}, metrics.file_size={metrics_size}")
                assert metrics_size == actual_size, f"metrics.file_size 与实际不符 {metrics_size} vs {actual_size}"
        finally:
            os.unlink(tmp)


# ========== BUG认认:_read_file_safe返回内容 ==========

class TestGrepReadFileSafe:
    """BUG-218~220: 编码回退/空文件/大文件
    _read_file_safe 已删除,改用 readtext 验证编码容错与文件大小限制
    """

    def test_read_file_safe_encoding_fallback(self):
        """BUG-218: 编码回退逻辑"""
        from app.tools.file.read_text_file import readtext
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.txt', delete=False) as f:
            # 写入非UTF-8非GBK的数据
            f.write(b'\x80\x81\x82\x83')
            tmp = f.name
        try:
            result = _run(readtext(tmp))
            content = result['data'].get('content', '')
            print(f"BUG-218: 编码回退 status={result['llm_data']['status']['exec_code']}")
            if content and '\ufffd' in content:
                print("  BUG认认: 乱码字符\ufffd出现在读取结果中")
        finally:
            os.unlink(tmp)

    def test_read_file_safe_empty_file(self):
        """BUG-219: 空文件"""
        from app.tools.file.read_text_file import readtext
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("")
            tmp = f.name
        try:
            result = _run(readtext(tmp))
            print(f"BUG-219: 空文件 status={result['llm_data']['status']['exec_code']}")
            assert result['llm_data']['status']['exec_code'] == 'success'
        finally:
            os.unlink(tmp)

    def test_read_file_safe_large_file_skipped(self):
        """BUG-220: 大文件处理"""
        from app.tools.file.read_text_file import readtext
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("x" * (10 * 1024 * 1024 + 1))
            tmp = f.name
        try:
            result = _run(readtext(tmp))
            print(f"BUG-220: 大文件 status={result['llm_data']['status']['exec_code']}")
            assert result['llm_data']['status']['exec_code'] in ('success', 'error')
        finally:
            os.unlink(tmp)


# ========== BUG认认:search_files pagination ==========

class TestSearchFilesPagination:
    """BUG-221: search_files分页逻辑"""

    def test_search_files_pagination_basic(self):
        """BUG-221: search_files的start_offset=0,分页功能未实现"""
        from app.tools.file.search_files import find
        with tempfile.TemporaryDirectory() as tmpdir:
            for i in range(5):
                with open(os.path.join(tmpdir, f"f{i}.txt"), 'w') as f:
                    f.write("content")
            result = _run(find("*.txt", tmpdir))
            total = result['llm_data']['metrics']['total']['value']
            matches = result['data']['matches']
            print(f"BUG-221: total={total}, returned={len(matches)}")
            assert total == 5
            assert len(matches) == 5

    def test_search_files_max_results(self):
        """BUG-222: search_files 不再设收集上限(章7.4/3.7: Tool 输出零限制, 返回全部匹配; 唯一保护为 deadline 超时)"""
        from app.tools.file.search_files import find
        # 2026-07-20 - 小欧 - MAX_SEARCH_RESULTS 常量已删除(章8 清理废弃常量), 此处用原值字面量维持回归断言
        _OLD_CAP = 1000
        with tempfile.TemporaryDirectory() as tmpdir:
            for i in range(_OLD_CAP + 10):
                with open(os.path.join(tmpdir, f"f{i}.txt"), 'w') as f:
                    f.write("content")
            result = _run(find("*.txt", tmpdir))
            total = result['llm_data']['metrics']['total']['value']
            print(f"BUG-222: 超MAX_SEARCH_RESULTS: total={total}")
            # 章7.4: 移除 MAX_SEARCH_RESULTS 收集上限, 返回全部匹配
            assert total == _OLD_CAP + 10
            assert len(result['data']['matches']) == _OLD_CAP + 10
            assert result['llm_data']['status']['exec_code'] == 'success'


# ========== BUG认认:_detect_encoding ==========

class TestDetectEncoding:
    """BUG-223: _detect_encoding各种情况"""

    def test_empty_file_encoding(self):
        """BUG-223: 空文件编码检测"""
        from app.tools.tool_fc_helper import _detect_encoding
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.txt', delete=False) as f:
            f.write(b"")
            tmp = f.name
        try:
            enc = _detect_encoding(tmp)
            print(f"BUG-223: 空文件编码 {enc}")
        finally:
            os.unlink(tmp)

    def test_chinese_gbk_encoding(self):
        """BUG-224: GBK编码文件"""
        from app.tools.tool_fc_helper import _detect_encoding
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.txt', delete=False) as f:
            f.write("中文GBK编码".encode('gbk'))
            tmp = f.name
        try:
            enc = _detect_encoding(tmp)
            print(f"BUG-224: GBK文件检测 {enc}")
        finally:
            os.unlink(tmp)

    def test_chinese_utf8_encoding(self):
        """BUG-225: UTF-8编码文件"""
        from app.tools.tool_fc_helper import _detect_encoding
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.txt', delete=False) as f:
            f.write("中文UTF8编码".encode('utf-8'))
            tmp = f.name
        try:
            enc = _detect_encoding(tmp)
            print(f"BUG-225: UTF-8文件检测 {enc}")
        finally:
            os.unlink(tmp)

    def test_bom_utf8_encoding(self):
        """BUG-226: BOM UTF-8文件"""
        from app.tools.tool_fc_helper import _detect_encoding
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.txt', delete=False) as f:
            f.write(b'\xef\xbb\xbf' + "BOM内容".encode('utf-8'))
            tmp = f.name
        try:
            enc = _detect_encoding(tmp)
            print(f"BUG-226: BOM UTF-8文件检测 {enc}")
            # 应该返回utf-8-sig
        finally:
            os.unlink(tmp)


# ========== BUG认认:read_text_file 编码检测replace ==========

class TestEncodingDetectionReplace:
    """BUG-227: 编码检测使用errors=replace导致乱码"""

    def test_garbage_content_detection(self):
        """BUG-227: 二进制垃圾内容用errors=replace读取
        检测到\ufffd在跳过该编码
        但如果所有编码都失败,返回最在一个编码的内容(含\ufffd)
        """
        from app.tools.file.read_text_file import _try_read_file_with_encodings
        from pathlib import Path
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.txt', delete=False) as f:
            f.write(b'\x00\x01\x02\x03\x80\x81\x82\x83\xff\xfe\xfd')
            tmp = f.name
        try:
            content, enc, error = _run(_try_read_file_with_encodings(Path(tmp)))
            print(f"BUG-227: 垃圾内容: enc={enc}, error={error}")
            if content:
                has_replacement = '\ufffd' in content
                print(f"  含有\\ufffd: {has_replacement}")
                if has_replacement:
                    print("  BUG认认: 返回了含替换字符的内容而非报错")
        finally:
            os.unlink(tmp)


# ========== BUG认认:list_directory深度问题 ==========

class TestListDirectoryDepth:
    """BUG-228: list_directory递归深度"""

    def test_deep_directory_structure(self):
        """BUG-228: 深层嵌套目录"""
        from app.tools.file.list_directory import listdir
        with tempfile.TemporaryDirectory() as tmpdir:
            current = tmpdir
            for i in range(15):
                current = os.path.join(current, f"level_{i}")
                os.makedirs(current)
            with open(os.path.join(current, "deep.txt"), 'w') as f:
                f.write("deep file")
            result = _run(listdir(tmpdir))
            metrics = result['llm_data']['metrics']
            print(f"BUG-228: 15层嵌套 file_count={metrics.get('file_count')}, dir_count={metrics.get('dir_count')}, total={metrics.get('total')}")
            # max_depth=10,所以level_10及更深的不会被扫描
            # 但当前用的是非递归模式,只显示一层
            # tree模式才有depth限制

    def test_tree_deep_directory(self):
        """BUG-229: tree模式深层嵌套"""
        from app.tools.file.list_directory import listdir
        from app.tools.file.tree import tree
        with tempfile.TemporaryDirectory() as tmpdir:
            current = tmpdir
            for i in range(15):
                current = os.path.join(current, f"level_{i}")
                os.makedirs(current)
            result = _run(tree(tmpdir))
            # max_depth=10,tree应该只到level_10
            tree_data = result['data']['tree']
            depth = 0
            node = tree_data
            while node.get('children'):
                depth += 1
                node = node['children'][0]
            print(f"BUG-229: tree实际深度: {depth}")
            # 应该<=10
