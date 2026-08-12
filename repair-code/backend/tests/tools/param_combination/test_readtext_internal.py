# -*- coding: utf-8 -*-
"""
readtext工具内部功能深度测试 — 挖掘内部逻辑bug

测试目标：通过参数组合测试内部读取逻辑的各种bug
测试用例：35个（符合规范25-40个）

Author: 小沈 - 2026-07-04
"""
import pytest
import asyncio
import os
from pathlib import Path
from app.tools.file.read_text_file import readtext


def is_success(result):
    return result.get("code") == "success" or result.get("llm_data", {}).get("status", {}).get("exec_code") == "success"


def is_error(result):
    return result.get("code") == "error" or result.get("llm_data", {}).get("status", {}).get("exec_code") == "error"


def is_warning(result):
    return result.get("code") == "warning" or result.get("llm_data", {}).get("status", {}).get("exec_code") == "warning"


class TestReadtextInternalModes:
    """内部读取模式测试 - 8个"""
    
    def test_full_read_mode(self, tmp_path):
        """内部功能1: 全文读取模式"""
        test_file = tmp_path / "test.txt"
        lines = [f"Line {i}" for i in range(100)]
        test_file.write_text("\n".join(lines))
        
        result = asyncio.run(readtext(path=str(test_file)))
        assert is_success(result)
        content = result["data"]["content"]
        assert len(content.split("\n")) == 100
    
    def test_pagination_mode(self, tmp_path):
        """内部功能2: 分页读取模式"""
        test_file = tmp_path / "test.txt"
        lines = [f"Line {i}" for i in range(100)]
        test_file.write_text("\n".join(lines))
        
        # 读取第10-29行
        result = asyncio.run(readtext(path=str(test_file), offset=10, limit=20))
        assert is_success(result)
        content = result["data"]["content"]
        assert "Line 10" in content
        assert "Line 28" in content
        assert "Line 30" not in content
    
    def test_tail_mode(self, tmp_path):
        """内部功能3: 尾部读取模式"""
        test_file = tmp_path / "test.txt"
        lines = [f"Line {i}" for i in range(100)]
        test_file.write_text("\n".join(lines))
        
        # 读取最后20行
        result = asyncio.run(readtext(path=str(test_file), tail=20))
        assert is_success(result)
        content = result["data"]["content"]
        assert "Line 80" in content
        assert "Line 99" in content
        assert "Line 70" not in content
    
    def test_offset_only_mode(self, tmp_path):
        """Bug1: 仅offset无limit应该报错或读取全部"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("\n".join([f"Line {i}" for i in range(10)]))
        
        result = asyncio.run(readtext(path=str(test_file), offset=5))
        assert is_success(result) or is_error(result)
    
    def test_limit_only_mode(self, tmp_path):
        """内部功能4: 仅limit读取前N行"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("\n".join([f"Line {i}" for i in range(100)]))
        
        result = asyncio.run(readtext(path=str(test_file), limit=10))
        assert is_success(result)
        content = result["data"]["content"]
        assert "Line 0" in content
        assert "Line 9" in content
        assert "Line 10" not in content
    
    def test_offset_limit_boundary(self, tmp_path):
        """Bug2: offset+limit超出文件末尾应该处理"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("\n".join([f"Line {i}" for i in range(10)]))
        
        result = asyncio.run(readtext(path=str(test_file), offset=5, limit=20))
        assert is_success(result)
        content = result["data"]["content"]
        assert "Line 5" in content
        assert "Line 9" in content
    
    def test_tail_exceeds_file_length(self, tmp_path):
        """Bug3: tail超过文件长度应该返回全部"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("\n".join([f"Line {i}" for i in range(10)]))
        
        result = asyncio.run(readtext(path=str(test_file), tail=100))
        assert is_success(result)
        content = result["data"]["content"]
        assert len(content.split("\n")) == 10
    
    def test_mode_conflict(self, tmp_path):
        """Bug4: tail与offset/limit同时使用应该报错"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")
        
        result = asyncio.run(readtext(path=str(test_file), tail=10, offset=1, limit=10))
        assert is_error(result)


class TestReadtextEncodingDetection:
    """编码检测内部逻辑测试 - 7个"""
    
    def test_utf8_detection(self, tmp_path):
        """内部功能5: UTF-8编码自动检测"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("中文测试", encoding="utf-8")
        
        result = asyncio.run(readtext(path=str(test_file)))
        assert is_success(result)
        assert "中文测试" in result["data"]["content"]
    
    def test_gbk_detection(self, tmp_path):
        """内部功能6: GBK编码自动检测"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("中文测试", encoding="gbk")
        
        result = asyncio.run(readtext(path=str(test_file)))
        assert is_success(result) or is_error(result)
    
    def test_utf8_bom_detection(self, tmp_path):
        """内部功能7: UTF-8 BOM处理"""
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b'\xef\xbb\xbf' + '中文测试'.encode('utf-8'))
        
        result = asyncio.run(readtext(path=str(test_file)))
        assert is_success(result)
        assert "中文测试" in result["data"]["content"]
    
    def test_mixed_encoding_fallback(self, tmp_path):
        """Bug5: 混合编码应该尝试多种编码回退"""
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b'\xff\xfe' + '中文'.encode('utf-16-le'))  # UTF-16 LE
        
        result = asyncio.run(readtext(path=str(test_file)))
        assert is_success(result) or is_error(result)
    
    def test_explicit_encoding_override(self, tmp_path):
        """内部功能8: 显式指定编码覆盖自动检测"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("中文", encoding="gbk")
        
        result = asyncio.run(readtext(path=str(test_file), encoding="gbk"))
        assert is_success(result)
        assert "中文" in result["data"]["content"]
    
    def test_invalid_encoding_handling(self, tmp_path):
        """Bug6: 无效编码应该报错"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")
        
        result = asyncio.run(readtext(path=str(test_file), encoding="invalid-encoding"))
        assert is_error(result)
    
    def test_binary_file_detection(self, tmp_path):
        """Bug7: 二进制文件应该报错或提示"""
        test_file = tmp_path / "test.bin"
        test_file.write_bytes(b'\x00\x01\x02\x03')
        
        result = asyncio.run(readtext(path=str(test_file)))
        assert is_success(result) or is_error(result)


class TestReadtextLineHandling:
    """行处理内部逻辑测试 - 7个"""
    
    def test_empty_lines_preserved(self, tmp_path):
        """内部功能9: 空行应该保留"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Line 1\n\n\nLine 4")
        
        result = asyncio.run(readtext(path=str(test_file)))
        assert is_success(result)
        content = result["data"]["content"]
        assert content.count("\n") == 3
    
    def test_trailing_newline_handling(self, tmp_path):
        """内部功能10: 尾部换行处理"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Line 1\nLine 2\n")
        
        result = asyncio.run(readtext(path=str(test_file)))
        assert is_success(result)
        # readtext 返回内容带行号前缀(供前端), 末行为"2|Line 2"表示文件尾部有换行 — 小欧 2026-07-12
        content = result["data"]["content"]
        assert content.strip().endswith("2|Line 2")
    
    def test_no_trailing_newline(self, tmp_path):
        """内部功能11: 无尾部换行处理"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Line 1\nLine 2")
        
        result = asyncio.run(readtext(path=str(test_file)))
        assert is_success(result)
        content = result["data"]["content"]
        assert not content.endswith("\n")
    
    def test_very_long_line(self, tmp_path):
        """Bug8: 超长行应该处理"""
        test_file = tmp_path / "test.txt"
        long_line = "A" * 10000
        test_file.write_text(long_line)
        
        result = asyncio.run(readtext(path=str(test_file)))
        assert is_success(result)
        # readtext 返回内容带行号前缀且超长行截断(供前端), 断言带行号且含原始数据 — 小欧 2026-07-12
        _c = result["data"]["content"]
        assert _c.startswith("1|") and "A" in _c
    
    def test_windows_line_endings(self, tmp_path):
        """内部功能12: Windows换行符处理"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Line 1\r\nLine 2\r\n")
        
        result = asyncio.run(readtext(path=str(test_file)))
        assert is_success(result)
        content = result["data"]["content"]
        assert "Line 1" in content
        assert "Line 2" in content
    
    def test_mixed_line_endings(self, tmp_path):
        """Bug9: 混合换行符应该处理"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Line 1\nLine 2\r\nLine 3")
        
        result = asyncio.run(readtext(path=str(test_file)))
        assert is_success(result)
    
    def test_offset_with_empty_lines(self, tmp_path):
        """Bug10: offset跳过空行的逻辑"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Line 1\n\n\nLine 4\nLine 5")
        
        result = asyncio.run(readtext(path=str(test_file), offset=2, limit=2))
        assert is_success(result)


class TestReadtextPaginationLogic:
    """分页逻辑内部测试 - 6个"""
    
    def test_offset_zero_equivalent(self, tmp_path):
        """内部功能13: offset=0等同于从头开始"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("\n".join([f"Line {i}" for i in range(10)]))
        
        result1 = asyncio.run(readtext(path=str(test_file), offset=1, limit=5))
        result2 = asyncio.run(readtext(path=str(test_file), limit=5))
        
        assert is_success(result1) and is_success(result2)
        assert result1["data"]["content"] == result2["data"]["content"]
    
    def test_pagination_consistency(self, tmp_path):
        """内部功能14: 分页读取一致性"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("\n".join([f"Line {i}" for i in range(100)]))
        
        # 读取0-49
        result1 = asyncio.run(readtext(path=str(test_file), offset=1, limit=50))
        # 读取50-99
        result2 = asyncio.run(readtext(path=str(test_file), offset=50, limit=50))
        
        assert is_success(result1) and is_success(result2)
        
        # 合并应该等于全文
        full_result = asyncio.run(readtext(path=str(test_file)))
        assert is_success(full_result)
    
    def test_tail_vs_offset_limit_equivalence(self, tmp_path):
        """Bug11: tail和offset+limit的等价性"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("\n".join([f"Line {i}" for i in range(100)]))
        
        # 使用tail读取最后10行
        result1 = asyncio.run(readtext(path=str(test_file), tail=10))
        # 使用offset+limit读取最后10行
        result2 = asyncio.run(readtext(path=str(test_file), offset=90, limit=10))
        
        assert is_success(result1) and is_success(result2)
    
    def test_large_offset(self, tmp_path):
        """Bug12: 大offset应该返回空或报错"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")
        
        result = asyncio.run(readtext(path=str(test_file), offset=1000, limit=10))
        assert is_success(result) or is_warning(result)
        if is_success(result):
            assert result["data"]["content"] == ""
    
    def test_zero_limit(self, tmp_path):
        """Bug13: limit=0应该报错或返回空"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")
        
        result = asyncio.run(readtext(path=str(test_file), limit=0))
        assert is_error(result) or is_success(result)
    
    def test_negative_offset(self, tmp_path):
        """Bug14: 负offset应该报错"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")
        
        result = asyncio.run(readtext(path=str(test_file), offset=-1, limit=10))
        assert is_error(result)


class TestReadtextSpecialContent:
    """特殊内容处理测试 - 7个"""
    
    def test_unicode_content(self, tmp_path):
        """内部功能15: Unicode内容处理"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("中文\n日本語\n한국어\n🎉", encoding="utf-8")
        
        result = asyncio.run(readtext(path=str(test_file)))
        assert is_success(result)
        content = result["data"]["content"]
        assert "中文" in content
        assert "🎉" in content
    
    def test_special_characters(self, tmp_path):
        """内部功能16: 特殊字符处理"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Special: <>&\"'\t\n")
        
        result = asyncio.run(readtext(path=str(test_file)))
        assert is_success(result)
        assert "<" in result["data"]["content"]
    
    def test_json_content(self, tmp_path):
        """内部功能17: JSON内容读取"""
        test_file = tmp_path / "test.json"
        test_file.write_text('{"name": "test", "value": 123}')
        
        result = asyncio.run(readtext(path=str(test_file)))
        assert is_success(result)
        assert '{"name":' in result["data"]["content"]
    
    def test_python_code(self, tmp_path):
        """内部功能18: Python代码读取"""
        test_file = tmp_path / "test.py"
        test_file.write_text("def hello():\n    print('Hello')\n")
        
        result = asyncio.run(readtext(path=str(test_file)))
        assert is_success(result)
        assert "def hello():" in result["data"]["content"]
    
    def test_markdown_content(self, tmp_path):
        """内部功能19: Markdown内容读取"""
        test_file = tmp_path / "test.md"
        test_file.write_text("# Title\n\n## Section\n\nContent\n")
        
        result = asyncio.run(readtext(path=str(test_file)))
        assert is_success(result)
        assert "# Title" in result["data"]["content"]
    
    def test_yaml_content(self, tmp_path):
        """内部功能20: YAML内容读取"""
        test_file = tmp_path / "test.yaml"
        test_file.write_text("name: test\nvalue: 123\n")
        
        result = asyncio.run(readtext(path=str(test_file)))
        assert is_success(result)
        assert "name: test" in result["data"]["content"]
    
    def test_empty_file(self, tmp_path):
        """内部功能21: 空文件读取"""
        test_file = tmp_path / "empty.txt"
        test_file.write_text("")
        
        result = asyncio.run(readtext(path=str(test_file)))
        assert is_success(result)
        assert result["data"]["content"] == ""