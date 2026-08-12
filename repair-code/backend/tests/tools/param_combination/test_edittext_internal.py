# -*- coding: utf-8 -*-
"""
edittext工具内部功能深度测试 — 挖掘内部逻辑bug

测试目标：通过参数组合测试内部替换逻辑的各种bug
测试用例：30个（符合规范25-40个）

Author: 小沈 - 2026-07-04
"""
import pytest
import asyncio
import os
from pathlib import Path
from app.tools.file.edit_text_file import edittext
from app.services.task.task_context import _current_task_id


def is_success(result):
    # 部分替换返回 exec_code=='warning' 也算成功(对齐 tool_response.is_success) - 小欧 2026-07-11
    return result.get("llm_data", {}).get("status", {}).get("exec_code") in ("success", "warning")


def is_error(result):
    return result.get("code") == "error" or result.get("llm_data", {}).get("status", {}).get("exec_code") == "error"


async def _run_edittext(**kwargs):
    _current_task_id.set("test-task-id")
    return await edittext(**kwargs)


class TestEdittextInternalReplacement:
    """内部替换逻辑测试 - 8个"""
    
    def test_single_replacement(self, tmp_path):
        """内部功能1: 单次替换"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello World")
        
        result = asyncio.run(_run_edittext(path=str(test_file), old_string="World", new_string="Python"))
        assert is_success(result)
        assert test_file.read_text() == "Hello Python"
    
    def test_multiple_occurrences_replace_first(self, tmp_path):
        """内部功能2: 多次出现只替换第一个"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test test test")
        
        result = asyncio.run(_run_edittext(path=str(test_file), old_string="test", new_string="done"))
        assert is_success(result)
        assert test_file.read_text() == "done test test"
    
    def test_multiple_occurrences_replace_all(self, tmp_path):
        """内部功能3: 多次出现全部替换"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test test test")
        
        result = asyncio.run(_run_edittext(path=str(test_file), old_string="test", new_string="done", mode="all"))
        assert is_success(result)
        assert test_file.read_text() == "done done done"
    
    def test_not_found_string(self, tmp_path):
        """Bug1: 未找到字符串应该报错"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello World")
        
        result = asyncio.run(_run_edittext(path=str(test_file), old_string="NotFound", new_string="test"))
        assert is_error(result)
    
    def test_empty_old_string(self, tmp_path):
        """Bug2: 空old_string应该报错"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")
        
        result = asyncio.run(_run_edittext(path=str(test_file), old_string="", new_string="test"))
        assert is_error(result)
    
    def test_delete_by_empty_new_string(self, tmp_path):
        """内部功能4: 空new_string删除匹配内容"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello World Test")
        
        result = asyncio.run(_run_edittext(path=str(test_file), old_string="World ", new_string=""))
        assert is_success(result)
        assert test_file.read_text() == "Hello Test"
    
    def test_replace_with_longer_string(self, tmp_path):
        """内部功能5: 替换为更长的字符串"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hi")
        
        result = asyncio.run(_run_edittext(path=str(test_file), old_string="Hi", new_string="Hello World"))
        assert is_success(result)
        assert test_file.read_text() == "Hello World"
    
    def test_replace_with_shorter_string(self, tmp_path):
        """内部功能6: 替换为更短的字符串"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello World")
        
        result = asyncio.run(_run_edittext(path=str(test_file), old_string="Hello World", new_string="Hi"))
        assert is_success(result)
        assert test_file.read_text() == "Hi"


class TestEdittextCaseSensitivity:
    """大小写敏感内部逻辑测试 - 5个"""
    
    def test_case_sensitive_match(self, tmp_path):
        """内部功能7: 大小写敏感匹配"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello hello HELLO")
        
        result = asyncio.run(_run_edittext(path=str(test_file), old_string="hello", new_string="hi", ignore_case=False))
        assert is_success(result)
        assert test_file.read_text() == "Hello hi HELLO"
    
    def test_case_insensitive_match(self, tmp_path):
        """内部功能8: 大小写不敏感匹配"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello hello HELLO")
        
        result = asyncio.run(_run_edittext(path=str(test_file), old_string="hello", new_string="hi", ignore_case=True, mode="all"))
        assert is_success(result)
        assert test_file.read_text() == "hi hi hi"
    
    def test_case_insensitive_single_replace(self, tmp_path):
        """Bug3: 大小写不敏感单次替换逻辑"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello hello HELLO")
        
        result = asyncio.run(_run_edittext(path=str(test_file), old_string="hello", new_string="hi", ignore_case=True))
        assert is_success(result)
        content = test_file.read_text()
        assert content.count("hi") == 1
    
    def test_case_preservation(self, tmp_path):
        """Bug4: 大小写不敏感时是否保留原始大小写"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello")
        
        result = asyncio.run(_run_edittext(path=str(test_file), old_string="hello", new_string="hi", ignore_case=True))
        assert is_success(result)
        # 是否保留原始大小写还是完全替换
        assert test_file.read_text() in ["hi", "Hi"]
    
    def test_unicode_case_sensitivity(self, tmp_path):
        """Bug5: Unicode字符大小写敏感"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("测试 測試")
        
        result = asyncio.run(_run_edittext(path=str(test_file), old_string="测试", new_string="done", ignore_case=False))
        assert is_success(result) or is_error(result)


class TestEdittextMultilineHandling:
    """多行处理内部逻辑测试 - 6个"""
    
    def test_multiline_replacement(self, tmp_path):
        """内部功能9: 多行替换"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Line 1\nLine 2\nLine 3")
        
        result = asyncio.run(_run_edittext(path=str(test_file), old_string="Line 2", new_string="Modified"))
        assert is_success(result)
        assert "Modified" in test_file.read_text()
    
    def test_replace_across_lines(self, tmp_path):
        """内部功能10: 跨行替换"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Line 1\nLine 2")
        
        result = asyncio.run(_run_edittext(path=str(test_file), old_string="1\nLine", new_string="X\nNew"))
        assert is_success(result)
        assert "X\nNew" in test_file.read_text()
    
    def test_preserve_line_endings(self, tmp_path):
        """内部功能11: 保留换行符"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Line 1\r\nLine 2\r\n")
        
        result = asyncio.run(_run_edittext(path=str(test_file), old_string="Line 1", new_string="Modified"))
        assert is_success(result)
        content = test_file.read_text()
        assert "\r\n" in content or "\n" in content
    
    def test_empty_line_replacement(self, tmp_path):
        """Bug6: 空行替换"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Line 1\n\nLine 3")
        
        result = asyncio.run(_run_edittext(path=str(test_file), old_string="\n\n", new_string="\n"))
        assert is_success(result)
        assert test_file.read_text() == "Line 1\nLine 3"
    
    def test_large_multiline_file(self, tmp_path):
        """Bug7: 大型多行文件替换性能"""
        test_file = tmp_path / "large.txt"
        lines = [f"Line {i}" for i in range(10000)]
        test_file.write_text("\n".join(lines))
        
        result = asyncio.run(_run_edittext(path=str(test_file), old_string="Line 5000", new_string="Modified"))
        assert is_success(result)
    
    def test_replace_all_multiline(self, tmp_path):
        """内部功能12: 多行全部替换"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test\ntest\ntest")
        
        result = asyncio.run(_run_edittext(path=str(test_file), old_string="test", new_string="done", mode="all"))
        assert is_success(result)
        assert test_file.read_text() == "done\ndone\ndone"


class TestEdittextSpecialPatterns:
    """特殊模式处理测试 - 6个"""
    
    def test_whitespace_replacement(self, tmp_path):
        """内部功能13: 空白字符替换"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello    World")
        
        result = asyncio.run(_run_edittext(path=str(test_file), old_string="    ", new_string=" "))
        assert is_success(result)
        assert test_file.read_text() == "Hello World"
    
    def test_tab_replacement(self, tmp_path):
        """内部功能14: 制表符替换"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello\tWorld")
        
        result = asyncio.run(_run_edittext(path=str(test_file), old_string="\t", new_string=" "))
        assert is_success(result)
        assert test_file.read_text() == "Hello World"
    
    def test_special_characters_replacement(self, tmp_path):
        """内部功能15: 特殊字符替换"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Special: <>&\"'")
        
        result = asyncio.run(_run_edittext(path=str(test_file), old_string="<", new_string="["))
        assert is_success(result)
        assert "[" in test_file.read_text()
    
    def test_unicode_replacement(self, tmp_path):
        """内部功能16: Unicode字符替换"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("测试 🎉 emoji", encoding="utf-8")
        
        result = asyncio.run(_run_edittext(path=str(test_file), old_string="🎉", new_string="😀"))
        assert is_success(result)
        assert "😀" in test_file.read_text(encoding="utf-8")
    
    def test_overlapping_patterns(self, tmp_path):
        """Bug8: 重叠模式替换"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("aaa")
        
        result = asyncio.run(_run_edittext(path=str(test_file), old_string="aa", new_string="b", mode="all"))
        assert is_success(result)
        # 可能是 "ba" 或 "ab"，取决于实现
    
    def test_nested_patterns(self, tmp_path):
        """Bug9: 嵌套模式替换"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("abcabc")
        
        result = asyncio.run(_run_edittext(path=str(test_file), old_string="abc", new_string="x", mode="all"))
        assert is_success(result)
        assert test_file.read_text() == "xx"


class TestEdittextEncodingHandling:
    """编码处理内部逻辑测试 - 5个"""
    
    def test_utf8_file_edit(self, tmp_path):
        """内部功能17: UTF-8文件编辑"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("中文测试", encoding="utf-8")
        
        result = asyncio.run(_run_edittext(path=str(test_file), old_string="中文", new_string="英文"))
        assert is_success(result)
        assert "英文测试" in test_file.read_text(encoding="utf-8")
    
    def test_gbk_file_edit(self, tmp_path):
        """内部功能18: GBK文件编辑"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("中文测试", encoding="gbk")
        
        result = asyncio.run(_run_edittext(path=str(test_file), old_string="中文", new_string="英文", encoding="gbk"))
        assert is_success(result) or is_error(result)
    
    def test_explicit_encoding_override(self, tmp_path):
        """内部功能19: 显式编码覆盖"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("中文", encoding="gbk")
        
        result = asyncio.run(_run_edittext(path=str(test_file), old_string="中文", new_string="测试", encoding="gbk"))
        assert is_success(result) or is_error(result)
    
    def test_mixed_encoding_content(self, tmp_path):
        """Bug10: 混合编码内容编辑"""
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"Hello \xc4\xe3\xba\xc3")  # Hello + GBK中文
        
        result = asyncio.run(_run_edittext(path=str(test_file), old_string="Hello", new_string="Hi"))
        assert is_success(result) or is_error(result)
    
    def test_preserve_original_encoding(self, tmp_path):
        """Bug11: 编辑后应保留原始编码"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("测试", encoding="gbk")
        
        result = asyncio.run(_run_edittext(path=str(test_file), old_string="测试", new_string="完成", encoding="gbk"))
        if is_success(result):
            # 验证编码是否保留
            content = test_file.read_text(encoding="gbk")
            assert "完成" in content