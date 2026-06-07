"""
write_file 工具深度测试 - 小健

【创建时间】2026-04-29 小健
"""

import pytest
import asyncio
import tempfile
import os
from pathlib import Path


class TestWriteFileTool:
    """测试 write_file 工具"""
    
    @pytest.fixture
    def mock_file_tools(self):
        from app.services.tools.file.file_tools import FileTools
        tool = FileTools(task_id='test_task')
        return tool
    
    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    # ===== 基础功能测试 =====
    
    def test_write_basic(self, mock_file_tools, temp_dir):
        """测试基本写入"""
        test_file = temp_dir / "test.txt"
        
        result = asyncio.run(mock_file_tools.write_text_file(
            str(test_file),
            "Hello World"
        ))
        
        assert result["code"] == "SUCCESS"
        assert test_file.exists()
        assert test_file.read_text() == "Hello World"
    
    def test_write_overwrite(self, mock_file_tools, temp_dir):
        """测试覆盖写入"""
        test_file = temp_dir / "test.txt"
        test_file.write_text("original")
        
        result = asyncio.run(mock_file_tools.write_text_file(
            str(test_file),
            "new content"
        ))
        
        assert result["code"] == "SUCCESS"
        assert test_file.read_text() == "new content"
    
    def test_write_new_file(self, mock_file_tools, temp_dir):
        """测试写入新文件"""
        test_file = temp_dir / "new.txt"
        
        result = asyncio.run(mock_file_tools.write_text_file(
            str(test_file),
            "new content"
        ))
        
        assert result["code"] == "SUCCESS"
        assert test_file.exists()
    
    def test_write_creates_parent_dirs(self, mock_file_tools, temp_dir):
        """测试自动创建父目录"""
        test_file = temp_dir / "subdir" / "new.txt"
        
        result = asyncio.run(mock_file_tools.write_text_file(
            str(test_file),
            "content"
        ))
        
        assert result["code"] == "SUCCESS"
        assert test_file.exists()
    
    # ===== 编码测试 =====
    
    def test_write_utf8(self, mock_file_tools, temp_dir):
        """测试UTF-8编码"""
        test_file = temp_dir / "utf8.txt"
        
        result = asyncio.run(mock_file_tools.write_text_file(
            str(test_file),
            "你好世界",
            encoding="utf-8"
        ))
        
        assert result["code"] == "SUCCESS"
        assert test_file.read_text(encoding="utf-8") == "你好世界"
    
    def test_write_gbk(self, mock_file_tools, temp_dir):
        """测试GBK编码"""
        test_file = temp_dir / "gbk.txt"
        
        result = asyncio.run(mock_file_tools.write_text_file(
            str(test_file),
            "你好",
            encoding="gbk"
        ))
        
        assert result["code"] == "SUCCESS"
    
    # ===== 内容类型测试 =====
    
    def test_write_empty_string(self, mock_file_tools, temp_dir):
        """测试写入空字符串"""
        test_file = temp_dir / "empty.txt"
        
        result = asyncio.run(mock_file_tools.write_text_file(str(test_file), ""))
        
        assert result["code"] == "SUCCESS"
    
    def test_write_whitespace(self, mock_file_tools, temp_dir):
        """测试写入空白字符"""
        test_file = temp_dir / "whitespace.txt"
        
        result = asyncio.run(mock_file_tools.write_text_file(
            str(test_file),
            "  spaces  \n\ttabs  "
        ))
        
        assert result["code"] == "SUCCESS"
    
    def test_write_chinese(self, mock_file_tools, temp_dir):
        """测试写入中文"""
        test_file = temp_dir / "chinese.txt"
        
        result = asyncio.run(mock_file_tools.write_text_file(
            str(test_file),
            "这是中文内容\n包含多行\n测试"
        ))
        
        assert result["code"] == "SUCCESS"
    
    def test_write_emoji(self, mock_file_tools, temp_dir):
        """测试写入Emoji"""
        test_file = temp_dir / "emoji.txt"
        
        result = asyncio.run(mock_file_tools.write_text_file(
            str(test_file),
            "Hello 👋 World 🌍"
        ))
        
        assert result["code"] == "SUCCESS"
    
    def test_write_special_chars(self, mock_file_tools, temp_dir):
        """测试写入特殊字符"""
        test_file = temp_dir / "special.txt"
        
        result = asyncio.run(mock_file_tools.write_text_file(
            str(test_file),
            "!@#$%^&*()_+-={}[]|\\:;'\",<>?/`"
        ))
        
        assert result["code"] == "SUCCESS"
    
    def test_write_multiline(self, mock_file_tools, temp_dir):
        """测试写入多行"""
        test_file = temp_dir / "multiline.txt"
        content = "Line1\nLine2\nLine3\nLine4\nLine5"
        
        result = asyncio.run(mock_file_tools.write_text_file(str(test_file), content))
        
        assert result["code"] == "SUCCESS"
    
    def test_write_large_content(self, mock_file_tools, temp_dir):
        """测试写入大内容"""
        test_file = temp_dir / "large.txt"
        content = "A" * 100000
        
        result = asyncio.run(mock_file_tools.write_text_file(str(test_file), content))
        
        assert result["code"] == "SUCCESS"
    
    # ===== 路径测试 =====
    
    def test_write_with_spaces(self, mock_file_tools, temp_dir):
        """测试路径中包含空格"""
        test_file = temp_dir / "folder with spaces" / "file.txt"
        
        result = asyncio.run(mock_file_tools.write_text_file(str(test_file), "content"))
        
        assert result["code"] == "SUCCESS"
    
    def test_write_with_chinese_path(self, mock_file_tools, temp_dir):
        """测试路径中包含中文"""
        test_file = temp_dir / "中文文件夹" / "文件.txt"
        
        result = asyncio.run(mock_file_tools.write_text_file(str(test_file), "内容"))
        
        assert result["code"] == "SUCCESS"
    
    # ===== 错误处理测试 =====
    
    def test_write_to_directory(self, mock_file_tools, temp_dir):
        """测试写入到目录"""
        result = asyncio.run(mock_file_tools.write_text_file(str(temp_dir), "content"))
        
        assert result["code"] in ["SUCCESS", "ERR_FILE_WRITE_FAILED"]
