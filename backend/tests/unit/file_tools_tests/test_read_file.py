"""
read_file 工具深度测试 - 小健

【创建时间】2026-04-29 小健

测试内容：
1. 基础读取功能
2. 编码处理（UTF-8、GBK、Latin-1等）
3. 边界情况（空文件、大文件、特殊字符）
4. 偏移和限制
5. 错误处理（文件不存在、权限问题等）
"""

import pytest
import asyncio
import tempfile
from pathlib import Path


class TestReadFileTool:
    """测试 read_file 工具"""
    
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
    
    def test_read_basic(self, mock_file_tools, temp_dir):
        """测试基本读取"""
        test_file = temp_dir / "test.txt"
        test_file.write_text("Hello World")
        
        result = asyncio.run(mock_file_tools.read_file(file_paths=[str(test_file)]))
        
        assert result["code"] == "SUCCESS"
        assert "Hello World" in result["data"]["content"]
    
    def test_read_with_offset(self, mock_file_tools, temp_dir):
        """测试偏移读取"""
        test_file = temp_dir / "test.txt"
        test_file.write_text("Line1\nLine2\nLine3\nLine4\nLine5")
        
        result = asyncio.run(mock_file_tools.read_file(file_paths=[str(test_file)], offset=2))
        
        assert result["code"] == "SUCCESS"
    
    def test_read_with_limit(self, mock_file_tools, temp_dir):
        """测试限制行数"""
        test_file = temp_dir / "test.txt"
        test_file.write_text("Line1\nLine2\nLine3\nLine4\nLine5")
        
        result = asyncio.run(mock_file_tools.read_file(file_paths=[str(test_file)], limit=2))
        
        assert result["code"] == "SUCCESS"
    
    # ===== 编码测试 =====
    
    def test_read_utf8(self, mock_file_tools, temp_dir):
        """测试UTF-8编码"""
        test_file = temp_dir / "utf8.txt"
        test_file.write_text("你好世界", encoding="utf-8")
        
        result = asyncio.run(mock_file_tools.read_file(file_paths=[str(test_file)], encoding="utf-8"))
        
        assert result["code"] == "SUCCESS"
    
    def test_read_gbk(self, mock_file_tools, temp_dir):
        """测试GBK编码"""
        test_file = temp_dir / "gbk.txt"
        test_file.write_text("你好世界", encoding="gbk")
        
        result = asyncio.run(mock_file_tools.read_file(file_paths=[str(test_file)], encoding="gbk"))
        
        assert result["code"] == "SUCCESS"
    
    # ===== 边界情况测试 =====
    
    def test_read_empty_file(self, mock_file_tools, temp_dir):
        """测试读取空文件"""
        test_file = temp_dir / "empty.txt"
        test_file.write_text("")
        
        result = asyncio.run(mock_file_tools.read_file(file_paths=[str(test_file)]))
        
        assert result["code"] == "SUCCESS"
    
    def test_read_large_file(self, mock_file_tools, temp_dir):
        """测试读取较大文件"""
        test_file = temp_dir / "large.txt"
        content = "A" * 10000
        test_file.write_text(content)
        
        result = asyncio.run(mock_file_tools.read_file(file_paths=[str(test_file)]))
        
        assert result["code"] == "SUCCESS"
    
    def test_read_chinese_content(self, mock_file_tools, temp_dir):
        """测试中文内容"""
        test_file = temp_dir / "chinese.txt"
        content = "这是中文内容\n包含多行\n还有标点符号"
        test_file.write_text(content, encoding="utf-8")
        
        result = asyncio.run(mock_file_tools.read_file(file_paths=[str(test_file)]))
        
        assert result["code"] == "SUCCESS"
        assert "中文" in result["data"]["content"]
    
    # ===== 错误处理测试 =====
    
    def test_file_not_exists(self, mock_file_tools, temp_dir):
        """测试文件不存在"""
        result = asyncio.run(mock_file_tools.read_file(file_paths=[str(temp_dir / "nonexistent.txt")]))
        
        assert result["code"] == "ERR_FILE_NOT_FOUND"
    
    def test_path_is_directory(self, mock_file_tools, temp_dir):
        """测试路径是目录"""
        result = asyncio.run(mock_file_tools.read_file(file_paths=[str(temp_dir)]))
        
        assert result["code"] == "ERR_PATH_NOT_FILE"
    
    # ===== 路径测试 =====
    
    def test_read_with_spaces_in_path(self, mock_file_tools, temp_dir):
        """测试路径中包含空格"""
        test_file = temp_dir / "folder with spaces" / "file.txt"
        test_file.parent.mkdir()
        test_file.write_text("content")
        
        result = asyncio.run(mock_file_tools.read_file(file_paths=[str(test_file)]))
        
        assert result["code"] == "SUCCESS"
    
    def test_read_with_chinese_in_path(self, mock_file_tools, temp_dir):
        """测试路径中包含中文"""
        test_file = temp_dir / "中文文件夹" / "文件.txt"
        test_file.parent.mkdir()
        test_file.write_text("内容", encoding="utf-8")
        
        result = asyncio.run(mock_file_tools.read_file(file_paths=[str(test_file)]))
        
        assert result["code"] == "SUCCESS"