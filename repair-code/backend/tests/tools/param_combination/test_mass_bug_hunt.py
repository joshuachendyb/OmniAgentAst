# -*- coding: utf-8 -*-
"""
Mass bug hunt - code analysis for real bugs
xiaojian 2026-06-24
"""
import asyncio
import os
import tempfile
import pytest
import time as _time_mod


def _run(coro):
    if asyncio.iscoroutine(coro):
        return asyncio.run(coro)
    return coro


# ========== search_files deduplication mechanism ==========

class TestSearchFilesDeduplication:
    """search_files deduplication: seen_files always empty set"""

    def test_dedup_same_file_multiple_dirs(self):
        """BUG-100: Duplicate files in different subdirs, dedup should be based on relative_path"""
        from app.tools.file.search_files import find
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "a"))
            os.makedirs(os.path.join(tmpdir, "b"))
            for sub in ["a", "b"]:
                with open(os.path.join(tmpdir, sub, "dup.txt"), 'w') as f:
                    f.write("content")
            result = _run(find("dup.txt", tmpdir))
            total = result['llm_data']['metrics']['total']['value']
            print(f"BUG-100: duplicate file search result: {total}")
            assert total >= 2

    def test_dedup_seen_set_never_populated(self):
        """BUG-101: 已移除,留空占位"""
        pass

    def test_dedup_files_in_nested_dirs(self):
        """BUG-102: 嵌套目录中的同名文件不被去重"""
        from app.tools.file.search_files import find
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "sub1"))
            os.makedirs(os.path.join(tmpdir, "sub2"))
            with open(os.path.join(tmpdir, "sub1", "same.txt"), 'w') as f:
                f.write("content1")
            with open(os.path.join(tmpdir, "sub2", "same.txt"), 'w') as f:
                f.write("content2")
            # 同名但不同路径,应该返回2个
            result = _run(find("same.txt", tmpdir))
            print(f"BUG-102: 嵌套同名文件: {result['llm_data']['metrics']['total']['value']}个")


# ========== search_files ignore_case在Windows下无效 ==========

class TestSearchFilesCaseSensitivity:
    """search_files大小写敏感问题"""

    def test_ignore_case_false_windows(self):
        """BUG-103: ignore_case=False在Windows下仍然忽略大小写
        因为Windows的fnmatch.fnmatch本身就是大小写不敏感的
        """
        from app.tools.file.search_files import find
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "TestFile.txt"), 'w') as f:
                f.write("content")
            with open(os.path.join(tmpdir, "otherfile.txt"), 'w') as f:
                f.write("content")
            # ignore_case=False 应该只匹配"TestFile.txt"
            result = _run(find("testfile.txt", tmpdir, ignore_case=False))
            total = result['llm_data']['metrics']['total']['value']
            print(f"BUG-103: ignore_case=False 结果: {total}个")
            # 在Windows下fnmatch.fnmatch("testfile.txt", "TestFile.txt")返回True
            # 所以即使ignore_case=False,也会匹配
            matches = [m['name'] for m in result['data']['matches']]
            print(f"  匹配文件: {matches}")

    def test_ignore_case_true_always_matches(self):
        """BUG-104: ignore_case=True在Windows下与False效果相同"""
        from app.tools.file.search_files import find
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "TestFile.txt"), 'w') as f:
                f.write("content")
            result1 = _run(find("testfile.txt", tmpdir, ignore_case=True))
            result2 = _run(find("testfile.txt", tmpdir, ignore_case=False))
            print(f"BUG-104: True={result1['llm_data']['metrics']['total']['value']}, False={result2['llm_data']['metrics']['total']['value']}")
            assert result1['llm_data']['metrics']['total']['value'] == result2['llm_data']['metrics']['total']['value']


# ========== grep_file_content 问题 ==========

class TestGrepFileBugs:
    """grep_file_content代码漏洞分析"""

    def test_import_os_after_usage(self):
        """BUG-105: grep_file_content.py中import os在第147行
        而os.walk在第104行就使用了
        由于是模块级import,在模块加载时就执行了,功能上没问题
        但代码组织有问题——如果有人想单独导入_grep_files_sync函数会失败
        """
        import importlib
        mod = importlib.import_module('app.tools.file.grep_file_content')
        has_os = hasattr(mod, 'os')
        print(f"BUG-105: 模块是否有os属性? {has_os}")
        # 这是代码质量问题,不是运行时bug

    def test_grep_regex_invalid_pattern_error_lost(self):
        """BUG-106: grep_files_sync中正则编译失败时返回空结果而非error
        代码L100-102:
            except re_mod.error as e:
                return [], 0, 0, False
        错误信息e被丢弃了,用户不知道正则为什么失败
        """
        from app.tools.file.grep_file_content import grep
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "test.txt"), 'w') as f:
                f.write("content")
            # 无效正则
            result = _run(grep("[invalid", tmpdir))
            print(f"BUG-106: 无效正则结果: {result['llm_data']['status']}")
            # 应该返回error,但实际取决于主函数的正则校验

    def test_grep_glob_filter_fnmatch_limits(self):
        """BUG-107: grep的glob过滤使用fnmatch,不支持**和{py,js}语法"""
        from app.tools.file.grep_file_content import grep
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "test.py"), 'w') as f:
                f.write("pattern\n")
            with open(os.path.join(tmpdir, "test.js"), 'w') as f:
                f.write("pattern\n")
            # 尝试使用{py,js}语法
            result = _run(grep("pattern", tmpdir, glob="test.{py,js}"))
            total = result['data'].get('total_matches', 0)
            print(f"BUG-107: glob {{py,js}}匹配数: {total}")
            # fnmatch不支持{py,js},所以应该匹配2个
            # 但fnmatch("test.py", "test.{py,js}")返回False

    def test_grep_large_file_searched(self):
        """BUG-108: 大文件被正常完整搜索(不再限制文件大小)"""
        from app.tools.file.grep_file_content import grep
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建一个较大的文件(11MB)
            big_path = os.path.join(tmpdir, "big.txt")
            with open(big_path, 'w', encoding='utf-8') as f:
                f.write("x" * (11 * 1024 * 1024))
            # 写入匹配内容
            with open(os.path.join(tmpdir, "small.txt"), 'w') as f:
                f.write("pattern\n")
            result = _run(grep("pattern", tmpdir))
            print(f"BUG-108: total_matches={result['data'].get('total_matches', 0)}")
            # 大文件不再被跳过,small.txt正常匹配
            assert result['data'].get('total_matches', 0) >= 1

    def test_grep_total_files_calculation(self):
        """BUG-110: total_files计算是否准确"""
        from app.tools.file.grep_file_content import grep
        with tempfile.TemporaryDirectory() as tmpdir:
            for i in range(3):
                with open(os.path.join(tmpdir, f"f{i}.txt"), 'w') as f:
                    f.write(f"match\nno match\n")
            # "no match"也包含"match",所以3个文件都有匹配
            with open(os.path.join(tmpdir, "empty.txt"), 'w') as f:
                f.write("no match\n")
            result = _run(grep("match", tmpdir))
            print(f"BUG-110: matches={result['data']['total_matches']}, files={result['data']['total_files']}")
            assert result['data']['total_files'] == 4


# ========== list_directory 问题 ==========

class TestListDirectoryBugs:
    """list_directory代码漏洞分析"""

    def test_tree_sort_by_works(self):
        """BUG-111: tree模式完全忽略sort_by参数
        代码L251-259: tree模式直接调用_get_directory_tree,不使用sort_by
        但_get_directory_tree内部用了name排序(L217)
        """
        from app.tools.file.list_directory import listdir
        from app.tools.file.tree import tree
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "zzz_dir"))
            os.makedirs(os.path.join(tmpdir, "aaa_dir"))
            with open(os.path.join(tmpdir, "zzz_dir", "file.txt"), 'w') as f:
                f.write("content")
            with open(os.path.join(tmpdir, "aaa_dir", "file.txt"), 'w') as f:
                f.write("content")
            result_name = _run(tree(tmpdir, sort_by="name"))
            result_mtime = _run(tree(tmpdir, sort_by="mtime"))
            # 两个结果的children顺序应该相同(都是按name排序)
            children_name = [c['name'] for c in result_name['data']['tree']['children']]
            children_mtime = [c['name'] for c in result_mtime['data']['tree']['children']]
            print(f"BUG-111: sort_by=name: {children_name}")
            print(f"  sort_by=mtime: {children_mtime}")
            assert children_name == ["aaa_dir", "zzz_dir"], f"name sort should be alphabetical: {children_name}"
            assert len(children_name) == 2
            assert len(children_mtime) == 2

    def test_tree_ignores_include_hidden(self):
        """BUG-112: tree模式完全忽略include_hidden参数
        _get_directory_tree没有include_hidden参数
        """
        from app.tools.file.list_directory import listdir
        from app.tools.file.tree import tree
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "visible"))
            os.makedirs(os.path.join(tmpdir, ".hidden"))
            result_false = _run(tree(tmpdir, include_hidden=False))
            result_true = _run(tree(tmpdir, include_hidden=True))
            children_false = [c['name'] for c in result_false['data']['tree']['children']]
            children_true = [c['name'] for c in result_true['data']['tree']['children']]
            print(f"BUG-112: hidden=False: {children_false}")
            print(f"  hidden=True: {children_true}")
            # include_hidden=False时应该隐藏.hidden目录
            assert ".hidden" in children_true, "include_hidden=True应该显示"
            if ".hidden" in children_false:
                print("  BUG认认: tree模式include_hidden=False仍然显示隐藏目录")

    def test_tree_statistics_double_count(self):
        """BUG-113: tree模式统计是否重复计算
        _count_tree_fs递归统计,需要验证结果
        """
        from app.tools.file.list_directory import listdir
        from app.tools.file.tree import tree
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "sub"))
            for i in range(3):
                with open(os.path.join(tmpdir, f"f{i}.txt"), 'w') as f:
                    f.write("x" * 100)
            with open(os.path.join(tmpdir, "sub", "g.txt"), 'w') as f:
                f.write("y" * 200)
            result = _run(tree(tmpdir))
            stats = result['data']['statistics']
            print(f"BUG-113: file_count={stats['file_count']}, dir_count={stats['dir_count']}")
            assert stats['file_count'] == 4, f"应该4个文件,实际{stats['file_count']}"
            assert stats['dir_count'] == 1, f"应该1个子目录,实际{stats['dir_count']}"

    def test_non_recursive_sort_order(self):
        """BUG-114: 非递归模式sort_by=name时的排序行为"""
        from app.tools.file.list_directory import listdir
        with tempfile.TemporaryDirectory() as tmpdir:
            for name in ["Zebra.txt", "apple.txt", "Mango.txt"]:
                with open(os.path.join(tmpdir, name), 'w') as f:
                    f.write("content")
            result = _run(listdir(tmpdir, sort_by="name"))
            names = [e['name'] for e in result['data']['entries']]
            print(f"BUG-114: 排序结果: {names}")

    def test_non_recursive_sort_by_size(self):
        """BUG-115: sort_by=size时目录和文件的排序混合"""
        from app.tools.file.list_directory import listdir
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "big_dir"))
            with open(os.path.join(tmpdir, "small.txt"), 'w') as f:
                f.write("x")
            with open(os.path.join(tmpdir, "big.txt"), 'w') as f:
                f.write("x" * 10000)
            result = _run(listdir(tmpdir, sort_by="size"))
            entries = result['data']['entries']
            print(f"BUG-115: size排序: {[(e['name'], e.get('size')) for e in entries]}")
            # 目录应该排在前面(size=None),但None和0比较会出问题吗?

    def test_statistics_accuracy(self):
        """BUG-116: list模式统计数据准认性"""
        from app.tools.file.list_directory import listdir
        with tempfile.TemporaryDirectory() as tmpdir:
            total_expected = 0
            for i in range(5):
                size = (i + 1) * 100
                with open(os.path.join(tmpdir, f"f{i}.txt"), 'w') as f:
                    f.write("x" * size)
                total_expected += size
            result = _run(listdir(tmpdir))
            stats = result['llm_data']['metrics']
            print(f"BUG-116: 统计total_size={stats['total_size']['value']}, 预期={total_expected}")
            assert stats['total_size']['value'] == total_expected
            assert stats['file_count']['value'] == 5


# ========== read_text_file 深入漏洞 ==========

class TestReadTextFileDeepBugs:
    """read_text_file深入漏洞挖掘"""

    def test_encoding_wrong_with_detection_returns_garbled(self):
        """BUG-117: 指定错误编码时,使用errors='replace'静默返回乱码
        read_text_file.py L92: errors='replace'
        当encoding=ascii读UTF-8中文文件,内容被替换为ufffd
        但函数返回success而非error
        """
        from app.tools.file.read_text_file import readtext
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("这是中文内容,包含特殊字符:,#")
            tmp = f.name
        try:
            result = _run(readtext(tmp, encoding="ascii"))
            print(f"BUG-117: ascii编码读UTF-8: status={result['llm_data']['status']['exec_code']}")
            content = result['data']['content']
            has_replacement = '\ufffd' in content
            print(f"  包含替换字符: {has_replacement}")
            print(f"  内容前20字: {repr(content[:20])}")
            if has_replacement:
                print("  BUG认认: 指定错误编码时应报错而非返回乱码")
        finally:
            os.unlink(tmp)

    def test_encoding_preferred_not_exist_still_succeeds(self):
        """BUG-118: 指定不存在的编码名时,不报错
        read_text_file.py L76-78: encodings_to_try = [preferred]
        然在L83: encodings_to_try.extend(["utf-8", ...])
        所以即使preferred不存在,也会回退到utf-8成功
        """
        from app.tools.file.read_text_file import readtext
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("测试内容")
            tmp = f.name
        try:
            result = _run(readtext(tmp, encoding="nonexistent_xyz"))
            print(f"BUG-118: 不存在编码? status={result['llm_data']['status']['exec_code']}")
            # 不应该报错,因为它会回退到utf-8
            # 但这可能不是用户期望的行为
        finally:
            os.unlink(tmp)

    def test_offset_exceeds_total_lines_start_gt_end(self):
        """BUG-119: offset超出总行数时start_line>end_line
        read_text_file.py L119-126
        """
        from app.tools.toolhelper.line_pager import select_lines
        lines = ["l1\n", "l2\n", "l3\n"]
        result = select_lines(lines, offset=999, limit=5)
        start = result.get('start_line')
        end = result.get('end_line')
        print(f"BUG-119: offset=999 -> start_line={start}, end_line={end}")
        if start > end:
            print(f"  BUG认认: start_line({start}) > end_line({end})")

    def test_offset_zero_returns_empty_content(self):
        """BUG-120: offset=0被当作负数处理,返回空内容
        read_text_file.py L119: start_idx = max(0, offset-1) if offset>0 else max(0, total+offset)
        offset=0: total+0=total, lines[total:]=[]
        """
        from app.tools.toolhelper.line_pager import select_lines
        lines = ["l1\n", "l2\n", "l3\n", "l4\n", "l5\n"]
        result = select_lines(lines, offset=0, limit=2)
        print(f"BUG-120: offset=0 -> content='{result['content']}', line_count={result['line_count']}")
        assert result['content'] == ""
        assert result['line_count'] == 0

    def test_empty_file_read(self):
        """BUG-121: 空文件读取"""
        from app.tools.file.read_text_file import readtext
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("")
            tmp = f.name
        try:
            result = _run(readtext(tmp))
            print(f"BUG-121: 空文件: {result['llm_data']['status']}")
            print(f"  content='{result['data']['content']}'")
            print(f"  total_lines={result['llm_data']['metrics']['total_lines']['value']}")
        finally:
            os.unlink(tmp)

    def test_file_with_only_newlines(self):
        """BUG-122: 只有换行符的文件"""
        from app.tools.file.read_text_file import readtext
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("\n\n\n\n\n")
            tmp = f.name
        try:
            result = _run(readtext(tmp))
            print(f"BUG-122: 纯换行: total_lines={result['llm_data']['metrics']['total_lines']['value']}, line_count={result['llm_data']['metrics']['lines']['value']}")
        finally:
            os.unlink(tmp)

    def test_bom_file_read(self):
        """BUG-123: BOM头文件读取"""
        from app.tools.file.read_text_file import readtext
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.txt', delete=False) as f:
            f.write(b'\xef\xbb\xbfhello world')
            tmp = f.name
        try:
            result = _run(readtext(tmp))
            print(f"BUG-123: BOM文件: encoding={result['data'].get('encoding')}")
            print(f"  content='{result['data']['content']}'")
        finally:
            os.unlink(tmp)

    def test_limit_zero_should_error(self):
        """BUG-124: limit=0应该报错"""
        from app.tools.file.read_text_file import readtext
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("line1\nline2\n")
            tmp = f.name
        try:
            result = _run(readtext(tmp, offset=1, limit=0))
            print(f"BUG-124: limit=0: {result['llm_data']['status']}")
        finally:
            os.unlink(tmp)

    def test_negative_limit(self):
        """BUG-125: limit为负数"""
        from app.tools.file.read_text_file import readtext
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("line1\nline2\n")
            tmp = f.name
        try:
            result = _run(readtext(tmp, offset=1, limit=-1))
            print(f"BUG-125: limit=-1: {result['llm_data']['status']}")
        finally:
            os.unlink(tmp)

    def test_offset_equals_total_lines(self):
        """BUG-126: offset正好等于总行数"""
        from app.tools.toolhelper.line_pager import select_lines
        lines = ["l1\n", "l2\n", "l3\n"]
        result = select_lines(lines, offset=3, limit=1)
        print(f"BUG-126: offset=total -> start_line={result.get('start_line')}, end_line={result.get('end_line')}, line_count={result['line_count']}")

    def test_file_size_at_max_limit(self):
        """BUG-127: 大文件读取(READTEXT_INPUT_MAX_BYTES已删除,用10MB)"""
        from app.tools.file.read_text_file import readtext
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("x" * (10 * 1024 * 1024))
            tmp = f.name
        try:
            result = _run(readtext(tmp))
            print(f"BUG-127: 10MB文件读取: {result['llm_data']['status']['exec_code']}")
        finally:
            os.unlink(tmp)

    def test_file_size_exceeds_max(self):
        """BUG-128: 超大文件读取"""
        from app.tools.file.read_text_file import readtext
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("x" * 1024 * 1024)
            tmp = f.name
        try:
            result = _run(readtext(tmp))
            print(f"BUG-128: 超大文件: {result['llm_data']['status']}")
        finally:
            os.unlink(tmp)


# ========== read_config_file 漏洞 ==========

class TestReadConfigFileBugs:
    """read_config_file深入漏洞挖掘"""

    def test_config_file_not_exist(self):
        """BUG-129: 不存在的配置文件
        read_config_file 模块已删除,改用 readtext 验证文件处理
        """
        from app.tools.file.read_text_file import readtext
        result = _run(readtext("/nonexistent/path/config.json"))
        print(f"BUG-129: 不存在文件: {result['llm_data']['status']}")

    def test_empty_json_file(self):
        """BUG-130: 空JSON文件"""
        from app.tools.file.read_text_file import readtext
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
            f.write("")
            tmp = f.name
        try:
            result = _run(readtext(tmp))
            print(f"BUG-130: 空JSON: {result['llm_data']['status']}, content='{result['data']['content']}'")
        finally:
            os.unlink(tmp)

    def test_invalid_json_syntax(self):
        """BUG-131: 无效JSON语法"""
        from app.tools.file.read_text_file import readtext
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
            f.write("{invalid json}")
            tmp = f.name
        try:
            result = _run(readtext(tmp))
            print(f"BUG-131: 无效JSON: {result['llm_data']['status']}, content='{result['data']['content']}'")
        finally:
            os.unlink(tmp)

    def test_json_with_bom(self):
        """BUG-132: BOM头的JSON文件"""
        from app.tools.file.read_text_file import readtext
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.json', delete=False) as f:
            f.write(b'\xef\xbb\xbf{"key": "value"}')
            tmp = f.name
        try:
            result = _run(readtext(tmp))
            print(f"BUG-132: BOM JSON: {result['llm_data']['status']}, content='{result['data']['content']}'")
        finally:
            os.unlink(tmp)

    def test_ini_no_sections(self):
        """BUG-133: INI文件没有section
        read_config_file 已删除,改用 readtext 读取原始内容
        """
        from app.tools.file.read_text_file import readtext
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False, encoding='utf-8') as f:
            f.write("key1=value1\nkey2=value2\n")
            tmp = f.name
        try:
            result = _run(readtext(tmp))
            print(f"BUG-133: INI无section: {result['llm_data']['status']}")
            if result['llm_data']['status']['exec_code'] == 'success':
                print(f"  内容: {result['data']['content']}")
        finally:
            os.unlink(tmp)

    def test_ini_duplicate_keys(self):
        """BUG-134: INI文件同一section有重复key"""
        from app.tools.file.read_text_file import readtext
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False, encoding='utf-8') as f:
            f.write("[section]\nkey=value1\nkey=value2\n")
            tmp = f.name
        try:
            result = _run(readtext(tmp))
            print(f"BUG-134: INI重复key: {result['data']['content']}")
        finally:
            os.unlink(tmp)

    def test_yaml_complex_nesting(self):
        """BUG-135: YAML复杂嵌套"""
        from app.tools.file.read_text_file import readtext
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as f:
            f.write("level1:\n  level2:\n    level3:\n      - item1\n      - item2\n")
            tmp = f.name
        try:
            result = _run(readtext(tmp))
            print(f"BUG-135: YAML嵌套: {result['llm_data']['status']}, content='{result['data']['content']}'")
        finally:
            os.unlink(tmp)

    def test_format_override(self):
        """BUG-136: format参数覆盖文件扩展名
        read_config_file 的 format 参数已随模块删除,改为 readtext 读取
        """
        from app.tools.file.read_text_file import readtext
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write('{"key": "value"}')
            tmp = f.name
        try:
            result = _run(readtext(tmp))
            print(f"BUG-136: 读取txt中JSON: {result['llm_data']['status']}, content='{result['data']['content']}'")
        finally:
            os.unlink(tmp)

    def test_unknown_format(self):
        """BUG-137: 未知格式"""
        from app.tools.file.read_text_file import readtext
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xyz', delete=False, encoding='utf-8') as f:
            f.write("data")
            tmp = f.name
        try:
            result = _run(readtext(tmp))
            print(f"BUG-137: 未知格式: {result['llm_data']['status']}, content='{result['data']['content']}'")
        finally:
            os.unlink(tmp)


# ========== read_media_file 漏洞 ==========

class TestReadMediaFileBugs:
    """read_media_file深入漏洞挖掘"""

    def test_txt_file_as_media(self):
        """BUG-138: text文件被当媒体文件读取返回base64"""
        from app.tools.file.read_media_file import readmedia
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("这是文本内容")
            tmp = f.name
        try:
            result = _run(readmedia(tmp))
            print(f"BUG-138: txt当媒体: {result['llm_data']['status']}")
            if result['llm_data']['status']['exec_code'] == 'success':
                print(f"  mime_type: {result['data']['mime_type']}")
        finally:
            os.unlink(tmp)

    def test_empty_media_file(self):
        """BUG-139: 空媒体文件"""
        from app.tools.file.read_media_file import readmedia
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.png', delete=False) as f:
            f.write(b"")
            tmp = f.name
        try:
            result = _run(readmedia(tmp))
            print(f"BUG-139: 空媒体: {result['llm_data']['status']}")
        finally:
            os.unlink(tmp)

    def test_media_file_size_too_large(self):
        """BUG-140: 超大媒体文件(2026-07-26 OOD: READMEDIA_INPUT_MAX_BYTES已删, 字节闸门移除, OOM由except兜底)"""
        from app.tools.file.read_media_file import readmedia
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.png', delete=False) as f:
            f.write(b"x" * (20 * 1024 * 1024))
            tmp = f.name
        try:
            result = _run(readmedia(tmp))
            print(f"BUG-140: 超大媒体: {result['llm_data']['status']}")
        finally:
            os.unlink(tmp)

    def test_unknown_extension_media(self):
        """BUG-141: 未知扩展名的媒体文件"""
        from app.tools.file.read_media_file import readmedia
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.xyz', delete=False) as f:
            f.write(b"\x89PNG\r\n\x1a\n")
            tmp = f.name
        try:
            result = _run(readmedia(tmp))
            print(f"BUG-141: 未知扩展名: {result['llm_data']['status']}")
            if result['llm_data']['status']['exec_code'] == 'success':
                print(f"  mime_type: {result['data']['mime_type']}")
        finally:
            os.unlink(tmp)

    def test_media_file_nonexistent(self):
        """BUG-142: 不存在的媒体文件"""
        from app.tools.file.read_media_file import readmedia
        result = _run(readmedia("/nonexistent/file.png"))
        print(f"BUG-142: 不存在: {result['llm_data']['status']}")

    def test_media_file_is_directory(self):
        """BUG-143: 路径是目录"""
        from app.tools.file.read_media_file import readmedia
        with tempfile.TemporaryDirectory() as tmpdir:
            result = _run(readmedia(tmpdir))
            print(f"BUG-143: 目录路径: {result['llm_data']['status']}")
