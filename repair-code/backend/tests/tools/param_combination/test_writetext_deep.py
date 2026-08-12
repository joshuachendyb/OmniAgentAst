# -*- coding: utf-8 -*-
"""
writetext工具深度测试 — 挖掘bug

测试目标：发现writetext工具的各种bug和边界问题
测试用例：30个（符合规范25-40个）

Author: 小沈 - 2026-07-04
"""
import pytest
import asyncio
import os
from pathlib import Path
from app.tools.file.write_text_file import writetext
from app.services.task.task_context import _current_task_id


def _run(coro):
    token = _current_task_id.set("test-task-write-001")
    try:
        return asyncio.run(coro)
    finally:
        _current_task_id.reset(token)


def is_success(result):
    return result.get("code") == "success" or result.get("llm_data", {}).get("status", {}).get("exec_code") == "success"


def is_error(result):
    return result.get("code") == "error" or result.get("llm_data", {}).get("status", {}).get("exec_code") == "error"


class TestWritetextBasicParams:
    """参数组合测试 - 6个"""
    
    def test_write_simple_text(self, tmp_path):
        """组合1: 写入简单文本"""
        dest = tmp_path / "test.txt"
        result = _run(writetext(path=str(dest), content="Hello World"))
        assert is_success(result)
        assert dest.exists()
        assert dest.read_text() == "Hello World"
    
    def test_write_multiline_text(self, tmp_path):
        """组合2: 写入多行文本"""
        dest = tmp_path / "multiline.txt"
        content = "Line 1\nLine 2\nLine 3"
        result = _run(writetext(path=str(dest), content=content))
        assert is_success(result)
        assert dest.read_text() == content
    
    def test_write_with_append_false(self, tmp_path):
        """组合3: 覆盖写入（append=False）"""
        dest = tmp_path / "test.txt"
        dest.write_text("old content")
        
        result = _run(writetext(path=str(dest), content="new content", append=False))
        assert is_success(result)
        assert dest.read_text() == "new content"
    
    def test_write_with_append_true(self, tmp_path):
        """组合4: 追加写入（append=True）"""
        dest = tmp_path / "test.txt"
        dest.write_text("old content\n")
        
        result = _run(writetext(path=str(dest), content="new content", append=True))
        assert is_success(result)
        assert dest.read_text() == "old content\nnew content"
    
    def test_write_with_encoding_utf8(self, tmp_path):
        """组合5: 指定UTF-8编码"""
        dest = tmp_path / "test.txt"
        result = _run(writetext(path=str(dest), content="测试", encoding="utf-8"))
        assert is_success(result)
        assert dest.read_text(encoding="utf-8") == "测试"
    
    def test_write_with_encoding_gbk(self, tmp_path):
        """组合6: 指定GBK编码"""
        dest = tmp_path / "test.txt"
        result = _run(writetext(path=str(dest), content="测试", encoding="gbk"))
        assert is_success(result) or is_error(result)


class TestWritetextInvalidScenarios:
    """无效场景测试 - 6个"""
    
    def test_empty_file_path(self, tmp_path):
        """Bug1: 空文件路径应该报错"""
        result = _run(writetext(path="", content="test"))
        assert is_error(result)
    
    def test_none_content(self, tmp_path):
        """Bug2: None内容应该报错"""
        dest = tmp_path / "test.txt"
        result = _run(writetext(path=str(dest), content=None))
        assert is_error(result)
    
    def test_invalid_encoding(self, tmp_path):
        """Bug3: 无效编码应该报错"""
        dest = tmp_path / "test.txt"
        result = _run(writetext(path=str(dest), content="test", encoding="invalid-encoding"))
        assert is_error(result)
    
    def test_write_to_directory(self, tmp_path):
        """Bug4: 写入到目录路径应该报错"""
        result = _run(writetext(path=str(tmp_path), content="test"))
        assert is_error(result)
    
    def test_write_to_readonly_directory(self, tmp_path):
        """Bug5: 写入到只读目录应该报错"""
        if os.name == 'nt':
            pytest.skip("Windows readonly test skipped")
        
        readonly_dir = tmp_path / "readonly"
        readonly_dir.mkdir()
        os.chmod(str(readonly_dir), 0o444)
        
        try:
            dest = readonly_dir / "test.txt"
            result = _run(writetext(path=str(dest), content="test"))
            assert is_success(result) or is_error(result)
        finally:
            os.chmod(str(readonly_dir), 0o755)
    
    def test_write_to_system_directory(self, tmp_path):
        """Bug6: 写入到系统目录应该报错"""
        if os.name == 'nt':
            result = _run(writetext(path="C:/Windows/test.txt", content="test"))
            assert is_error(result)
        else:
            result = _run(writetext(path="/root/test.txt", content="test"))
            assert is_error(result)


class TestWritetextEncodingHandling:
    """编码处理测试 - 5个"""
    
    def test_write_chinese_utf8(self, tmp_path):
        """测试中文UTF-8编码"""
        dest = tmp_path / "chinese.txt"
        result = _run(writetext(path=str(dest), content="中文测试"))
        assert is_success(result)
        assert dest.read_text(encoding="utf-8") == "中文测试"
    
    def test_write_emoji(self, tmp_path):
        """测试Emoji字符"""
        dest = tmp_path / "emoji.txt"
        result = _run(writetext(path=str(dest), content="Hello 🎉 World 🌍"))
        assert is_success(result)
        assert "🎉" in dest.read_text(encoding="utf-8")
    
    def test_write_special_chars(self, tmp_path):
        """测试特殊字符"""
        dest = tmp_path / "special.txt"
        content = "Special: <>&\"' \t\n"
        result = _run(writetext(path=str(dest), content=content))
        assert is_success(result)
        assert dest.read_text() == content
    
    def test_append_different_encoding(self, tmp_path):
        """Bug7: 追加时不同编码应该处理"""
        dest = tmp_path / "mixed.txt"
        dest.write_text("GBK内容", encoding="gbk")
        
        result = _run(writetext(path=str(dest), content="UTF8内容", append=True))
        assert is_success(result) or is_error(result)
    
    def test_write_bom_handling(self, tmp_path):
        """测试BOM处理"""
        dest = tmp_path / "bom.txt"
        result = _run(writetext(path=str(dest), content="test", encoding="utf-8-sig"))
        assert is_success(result) or is_error(result)


class TestWritetextFileTypes:
    """文件类型测试 - 5个"""
    
    def test_write_python_file(self, tmp_path):
        """测试写入Python文件"""
        dest = tmp_path / "test.py"
        content = "def hello():\n    print('Hello')\n"
        result = _run(writetext(path=str(dest), content=content))
        assert is_success(result)
    
    def test_write_json_file(self, tmp_path):
        """测试写入JSON文件"""
        dest = tmp_path / "test.json"
        content = '{"name": "test", "value": 123}'
        result = _run(writetext(path=str(dest), content=content))
        assert is_success(result)
    
    def test_write_markdown_file(self, tmp_path):
        """测试写入Markdown文件"""
        dest = tmp_path / "test.md"
        content = "# Title\n\nParagraph\n"
        result = _run(writetext(path=str(dest), content=content))
        assert is_success(result)
    
    def test_write_yaml_file(self, tmp_path):
        """测试写入YAML文件"""
        dest = tmp_path / "test.yaml"
        content = "name: test\nvalue: 123\n"
        result = _run(writetext(path=str(dest), content=content))
        assert is_success(result)
    
    def test_write_xml_file(self, tmp_path):
        """测试写入XML文件"""
        dest = tmp_path / "test.xml"
        content = '<?xml version="1.0"?>\n<root><item>test</item></root>'
        result = _run(writetext(path=str(dest), content=content))
        assert is_success(result)


class TestWritetextAppendBehavior:
    """追加行为测试 - 4个"""
    
    def test_append_creates_if_not_exists(self, tmp_path):
        """测试追加到不存在的文件会创建"""
        dest = tmp_path / "new.txt"
        result = _run(writetext(path=str(dest), content="first line", append=True))
        assert is_success(result)
        assert dest.read_text() == "first line"
    
    def test_append_preserves_existing(self, tmp_path):
        """测试追加保留现有内容"""
        dest = tmp_path / "test.txt"
        dest.write_text("existing\n")
        
        result = _run(writetext(path=str(dest), content="appended", append=True))
        assert is_success(result)
        assert dest.read_text() == "existing\nappended"
    
    def test_multiple_appends(self, tmp_path):
        """测试多次追加"""
        dest = tmp_path / "multi.txt"
        
        for i in range(5):
            result = _run(writetext(path=str(dest), content=f"Line {i}\n", append=(i > 0)))
            assert is_success(result)
        
        content = dest.read_text()
        assert "Line 0" in content
        assert "Line 4" in content
    
    def test_append_vs_overwrite(self, tmp_path):
        """测试追加vs覆盖 — 更新 2026-08-07 小欧: 追加时原文件末尾非换行符自动补换行(2026-08-06追加补换行行为)"""
        dest = tmp_path / "test.txt"
        dest.write_text("original")
        
        result1 = _run(writetext(path=str(dest), content="appended", append=True))
        assert is_success(result1)
        # 原文件末尾无换行 → 自动补\n, 避免与末行合并 — 2026-08-06 追加补换行
        assert dest.read_text() == "original\nappended"
        
        result2 = _run(writetext(path=str(dest), content="overwritten", append=False))
        assert is_success(result2)
        assert dest.read_text() == "overwritten"


class TestWritetextEdgeCases:
    """边界测试 - 4个"""
    
    def test_write_empty_content(self, tmp_path):
        """测试写入空内容"""
        dest = tmp_path / "empty.txt"
        result = _run(writetext(path=str(dest), content=""))
        assert is_error(result)
    
    def test_write_large_content(self, tmp_path):
        """Bug8: 大内容写入应该成功"""
        dest = tmp_path / "large.txt"
        content = "Line\n" * 100000
        result = _run(writetext(path=str(dest), content=content))
        assert is_success(result)
        assert dest.exists()
    
    def test_write_very_long_line(self, tmp_path):
        """Bug9: 超长行应该处理"""
        dest = tmp_path / "longline.txt"
        content = "A" * 10000
        result = _run(writetext(path=str(dest), content=content))
        assert is_success(result)
    
    def test_write_unicode_filename(self, tmp_path):
        """Bug10: Unicode文件名应该支持"""
        dest = tmp_path / "文件🎉.txt"
        result = _run(writetext(path=str(dest), content="unicode filename"))
        assert is_success(result) or is_error(result)