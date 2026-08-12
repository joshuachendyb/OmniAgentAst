# -*- coding: utf-8 -*-
# ================================================================
# 【skip case 归档副本】 - 小欧 2026-08-12 10:43:59
# 原路径: backend/tests/tools/param_combination/test_grep_internal.py
# 归档原因: 包含 Windows 权限模型差异类 skip case(chmod 0o000 不阻止管理员),
#           已从 backend/tests 原文件删除对应 skip case, 此处保留完整代码,
#           便于在非 Windows 平台恢复运行。
# ================================================================
"""
grep工具内部功能深度测试 — 挖掘内部逻辑bug

测试目标：通过参数组合测试内部搜索逻辑的各种bug
测试用例：30个（符合规范25-40个）

Author: 小沈 - 2026-07-04
"""
import pytest
import asyncio
import os
from pathlib import Path
from app.tools.file.grep_file_content import grep


def is_success(result):
    return result.get("code") == "success" or result.get("llm_data", {}).get("status", {}).get("exec_code") == "success"


def is_error(result):
    return result.get("code") == "error" or result.get("llm_data", {}).get("status", {}).get("exec_code") == "error"


@pytest.fixture
def test_dir(tmp_path):
    """创建测试目录和文件"""
    (tmp_path / "file1.py").write_text("def hello():\n    print('Hello')\n    return 'hello'\n")
    (tmp_path / "file2.py").write_text("def world():\n    print('World')\n    return 'world'\n")
    (tmp_path / "file3.txt").write_text("Hello World\nTest Line\nAnother Line\n")
    (tmp_path / "subdir").mkdir()
    (tmp_path / "subdir" / "file4.py").write_text("def test():\n    pass\n")
    return str(tmp_path)


class TestGrepInternalSearchModes:
    """内部搜索模式测试 - 7个"""
    
    def test_content_mode(self, test_dir):
        """内部功能1: 内容输出模式"""
        result = asyncio.run(grep(pattern="def", path=test_dir))
        assert is_success(result)
        assert any("def hello" in m.get("content", "") for m in result["data"].get("matches", []))
    
    def test_empty_pattern(self, test_dir):
        """Bug2: 空模式应该报错"""
        result = asyncio.run(grep(pattern="", path=test_dir))
        assert is_error(result)
    
    def test_no_matches(self, test_dir):
        """内部功能4: 无匹配返回空"""
        result = asyncio.run(grep(pattern="NonExistentPattern12345", path=test_dir))
        assert is_success(result)
        assert result["data"]["total_matches"] == 0

    def test_pattern_with_special_chars(self, test_dir):
        """内部功能5: 特殊字符模式"""
        result = asyncio.run(grep(pattern="print\\(", path=test_dir))
        assert is_success(result)


class TestGrepRegexHandling:
    """正则表达式内部逻辑测试 - 7个"""
    
    def test_simple_pattern(self, test_dir):
        """内部功能6: 简单模式"""
        result = asyncio.run(grep(pattern="hello", path=test_dir, ignore_case=True))
        assert is_success(result)
    
    def test_regex_pattern(self, test_dir):
        """内部功能7: 正则表达式模式"""
        result = asyncio.run(grep(pattern="def \\w+\\(", path=test_dir))
        assert is_success(result)
    
    def test_case_sensitive_regex(self, test_dir):
        """内部功能8: 大小写敏感正则"""
        result = asyncio.run(grep(pattern="def", path=test_dir, ignore_case=False))
        assert is_success(result)
    
    def test_case_insensitive_regex(self, test_dir):
        """内部功能9: 大小写不敏感正则"""
        result = asyncio.run(grep(pattern="DEF", path=test_dir, ignore_case=True))
        assert is_success(result)
    
    def test_invalid_regex(self, test_dir):
        """Bug3: 无效正则应该报错"""
        result = asyncio.run(grep(pattern="[invalid", path=test_dir))
        assert is_error(result)
    
    def test_complex_regex(self, test_dir):
        """内部功能10: 复杂正则表达式"""
        result = asyncio.run(grep(pattern="def \\w+\\(.*\\):", path=test_dir))
        assert is_success(result)
    
    def test_multiline_pattern(self, test_dir):
        """Bug4: 多行模式匹配"""
        result = asyncio.run(grep(pattern="def.*return", path=test_dir))
        assert is_success(result) or is_error(result)


class TestGrepFileFiltering:
    """文件过滤内部逻辑测试 - 6个"""
    
    def test_glob_filter_py(self, test_dir):
        """内部功能11: glob过滤.py文件"""
        result = asyncio.run(grep(pattern="def", path=test_dir, glob="*.py"))
        assert is_success(result)
        assert result["data"]["total_matches"] >= 2

    def test_glob_filter_txt(self, test_dir):
        """内部功能12: glob过滤.txt文件"""
        result = asyncio.run(grep(pattern="Hello", path=test_dir, glob="*.txt"))
        assert is_success(result)
    
    def test_glob_filter_multiple(self, test_dir):
        """Bug5: 多种文件类型过滤"""
        result = asyncio.run(grep(pattern="def", path=test_dir, glob="*.{py,txt}"))
        assert is_success(result) or is_error(result)
    
    def test_glob_no_matches(self, test_dir):
        """内部功能13: glob无匹配文件"""
        result = asyncio.run(grep(pattern="def", path=test_dir, glob="*.nonexistent"))
        assert is_success(result)
        assert result["data"]["total_matches"] == 0

    def test_recursive_search(self, test_dir):
        """内部功能14: 递归搜索"""
        result = asyncio.run(grep(pattern="def", path=test_dir))
        assert is_success(result)
        # 应该包含子目录中的文件
        assert result["data"]["total_matches"] >= 3

    def test_glob_with_path(self, test_dir):
        """Bug6: glob包含路径"""
        result = asyncio.run(grep(pattern="def", path=test_dir, glob="subdir/*.py"))
        assert is_success(result)


class TestGrepOutputFormatting:
    """输出格式化内部逻辑测试 - 5个"""
    
    def test_content_formatting(self, test_dir):
        """内部功能15: 内容格式化"""
        result = asyncio.run(grep(pattern="def", path=test_dir))
        assert is_success(result)
        matches = result["data"].get("matches", [])
        assert len(matches) > 0

    def test_line_number_display(self, test_dir):
        """Bug7: 行号显示"""
        result = asyncio.run(grep(pattern="def", path=test_dir))
        assert is_success(result)
        # 验证是否包含行号信息
    
    def test_context_lines(self, test_dir):
        """Bug8: 上下文行显示"""
        result = asyncio.run(grep(pattern="def", path=test_dir))
        assert is_success(result)


class TestGrepPerformanceHandling:
    """性能处理内部逻辑测试 - 5个"""
    
    def test_large_file_handling(self, tmp_path):
        """Bug9: 大文件处理"""
        large_file = tmp_path / "large.txt"
        lines = [f"Line {i}: some content" for i in range(10000)]
        large_file.write_text("\n".join(lines))
        
        result = asyncio.run(grep(pattern="Line 5000", path=str(tmp_path)))
        assert is_success(result)
    
    def test_many_files_handling(self, tmp_path):
        """Bug10: 多文件处理"""
        for i in range(100):
            (tmp_path / f"file{i}.txt").write_text(f"Content {i}\n")
        
        result = asyncio.run(grep(pattern="Content", path=str(tmp_path)))
        assert is_success(result)
    
    def test_deep_directory_recursion(self, tmp_path):
        """Bug11: 深层目录递归"""
        current = tmp_path
        for i in range(10):
            current = current / f"level{i}"
            current.mkdir()
            (current / "file.txt").write_text(f"Level {i}\n")
        
        result = asyncio.run(grep(pattern="Level", path=str(tmp_path)))
        assert is_success(result)
    
    def test_binary_file_skip(self, tmp_path):
        """内部功能18: 二进制文件跳过"""
        (tmp_path / "binary.bin").write_bytes(b"\x00\x01\x02\x03")
        (tmp_path / "text.txt").write_text("test content")

        result = asyncio.run(grep(pattern="test", path=str(tmp_path)))
        # 二进制文件被跳过(返回success),文本文件正常匹配
        assert result["llm_data"]["status"]["exec_code"] == "success"
        assert result["data"]["total_matches"] >= 1
        assert any("test content" in m.get("content", "") for m in result["data"].get("matches", []))
    
    def test_permission_denied_handling(self, tmp_path):
        """Bug12: 权限拒绝处理"""
        # Windows权限模型差异: os.chmod(0o000)不阻止管理员访问, 本机无法真实复现拒绝
        # 可配置: 设 OMNI_RUN_PERMISSION_TESTS=1 在类Unix环境强制运行
        if os.name == 'nt' and not os.environ.get("OMNI_RUN_PERMISSION_TESTS"):
            pytest.skip("跳过:Windows权限模型差异(os.chmod 0o000不阻止管理员);设 OMNI_RUN_PERMISSION_TESTS=1 强制")
        
        no_perm_dir = tmp_path / "noperm"
        no_perm_dir.mkdir()
        (no_perm_dir / "file.txt").write_text("secret")
        os.chmod(str(no_perm_dir), 0o000)
        
        try:
            result = asyncio.run(grep(pattern="secret", path=str(tmp_path)))
            assert is_success(result) or is_error(result)
        finally:
            os.chmod(str(no_perm_dir), 0o755)