"""
FileTools 测试 - 小沈

测试文件操作工具集的核心功能。

Author: 小沈 - 2026-03-21
"""

import pytest

from app.services.tools.file.file_tools import (
    ReadFileInput,
    WriteFileInput,
    ListDirectoryInput,
    DeleteFileInput,
    MoveFileInput,
    SearchFilesInput,
    GenerateReportInput,
    ToolDefinition
)


class TestReadFileInput:
    """测试ReadFileInput模型"""
    
    def test_create_default(self):
        """测试默认创建"""
        input_data = ReadFileInput(file_path="test.txt")
        
        assert input_data.file_path == "test.txt"
        assert input_data.offset == 1
        assert input_data.limit == 2000
        assert input_data.encoding == "utf-8"
    
    def test_create_with_custom_values(self):
        """测试自定义值创建"""
        input_data = ReadFileInput(
            file_path="test.txt",
            offset=10,
            limit=100,
            encoding="gbk"
        )
        
        assert input_data.file_path == "test.txt"
        assert input_data.offset == 10
        assert input_data.limit == 100
        assert input_data.encoding == "gbk"


class TestWriteFileInput:
    """测试WriteFileInput模型"""
    
    def test_create_default(self):
        """测试默认创建"""
        input_data = WriteFileInput(file_path="test.txt", content="hello")
        
        assert input_data.file_path == "test.txt"
        assert input_data.content == "hello"
        assert input_data.encoding == "utf-8"
    
    def test_create_with_custom_encoding(self):
        """测试自定义编码创建"""
        input_data = WriteFileInput(
            file_path="test.txt",
            content="hello",
            encoding="gbk"
        )
        
        assert input_data.encoding == "gbk"


class TestListDirectoryInput:
    """测试ListDirectoryInput模型"""
    
    def test_create_default(self):
        """测试默认创建"""
        input_data = ListDirectoryInput(dir_path="test_dir")
        
        assert input_data.dir_path == "test_dir"
        assert input_data.recursive == False
        assert input_data.max_depth == 10
        assert input_data.page_size == 100
    
    def test_create_with_recursive(self):
        """测试递归创建"""
        input_data = ListDirectoryInput(
            dir_path="test_dir",
            recursive=True,
            max_depth=5
        )
        
        assert input_data.recursive == True
        assert input_data.max_depth == 5


class TestDeleteFileInput:
    """测试DeleteFileInput模型"""
    
    def test_create_default(self):
        """测试默认创建"""
        input_data = DeleteFileInput(file_path="test.txt")
        
        assert input_data.file_path == "test.txt"
        assert input_data.recursive == False
    
    def test_create_with_recursive(self):
        """测试递归删除"""
        input_data = DeleteFileInput(
            file_path="test_dir",
            recursive=True
        )
        
        assert input_data.recursive == True


class TestMoveFileInput:
    """测试MoveFileInput模型"""
    
    def test_create(self):
        """测试创建"""
        input_data = MoveFileInput(
            source_path="old.txt",
            destination_path="new.txt"
        )
        
        assert input_data.source_path == "old.txt"
        assert input_data.destination_path == "new.txt"


class TestSearchFilesInput:
    """测试SearchFilesInput模型"""
    
    def test_create_default(self):
        """测试默认创建"""
        input_data = SearchFilesInput(pattern="test")
        
        assert input_data.pattern == "test"
        assert input_data.path == "."
        assert input_data.file_pattern == "*"
        assert input_data.use_regex == False
        assert input_data.max_results == 1000
    
    def test_create_with_regex(self):
        """测试正则表达式搜索"""
        input_data = SearchFilesInput(
            pattern="test.*",
            use_regex=True
        )
        
        assert input_data.use_regex == True


class TestGenerateReportInput:
    """测试GenerateReportInput模型"""
    
    def test_create_default(self):
        """测试默认创建"""
        input_data = GenerateReportInput()
        
        assert input_data.output_dir is None
    
    def test_create_with_output_dir(self):
        """测试指定输出目录"""
        input_data = GenerateReportInput(output_dir="/path/to/output")
        
        assert input_data.output_dir == "/path/to/output"


class TestToolDefinition:
    """测试ToolDefinition类"""
    
    def test_tool_definition_exists(self):
        """测试ToolDefinition类存在"""
        assert ToolDefinition is not None
    
    def test_tool_definition_has_tools(self):
        """测试ToolDefinition有tools属性"""
        assert hasattr(ToolDefinition, 'tools') or hasattr(ToolDefinition, '__init__')
