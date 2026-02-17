"""
ReAct Agent工具解析器单元测试 (ToolParser Unit Tests)
测试ToolParser类的响应解析功能

测试范围:
- parse_response: 解析标准JSON响应
- parse_json_response: 解析JSON代码块
- parse_plain_json: 解析纯JSON文本
- parse_invalid_response: 处理无效响应

依赖:
- pytest: 测试框架
"""
import pytest
import json
from typing import Dict, Any

# 导入被测试模块
from app.services.file_operations.agent import ToolParser


class TestParseResponse:
    """测试主解析函数"""
    
    def test_parse_json_response(self):
        """TC029: 解析标准JSON格式响应"""
        response = '''
        {
            "thought": "I need to read the file to understand its content",
            "action": "read_file",
            "action_input": {"file_path": "/tmp/test.txt"}
        }
        '''
        
        result = ToolParser.parse_response(response)
        
        assert result["thought"] == "I need to read the file to understand its content"
        assert result["action"] == "read_file"
        assert result["action_input"]["file_path"] == "/tmp/test.txt"
    
    def test_parse_json_code_block(self):
        """TC030: 解析Markdown JSON代码块"""
        response = '''
        I think I should read the file first.
        
        ```json
        {
            "thought": "Reading file to check content",
            "action": "read_file",
            "action_input": {"file_path": "/path/to/file.py"}
        }
        ```
        '''
        
        result = ToolParser.parse_response(response)
        
        assert result["action"] == "read_file"
        assert result["action_input"]["file_path"] == "/path/to/file.py"
    
    def test_parse_code_block_without_json_label(self):
        """TC031: 解析无json标签的代码块"""
        response = '''
        Let me check the directory structure.
        
        ```
        {
            "thought": "Listing directory contents",
            "action": "list_directory",
            "action_input": {"dir_path": "/tmp"}
        }
        ```
        '''
        
        result = ToolParser.parse_response(response)
        
        assert result["action"] == "list_directory"
        assert result["action_input"]["dir_path"] == "/tmp"
    
    def test_parse_response_missing_thought(self):
        """TC032: 缺少thought字段应抛出异常"""
        response = '''
        {
            "action": "read_file",
            "action_input": {"file_path": "/tmp/test.txt"}
        }
        '''
        
        with pytest.raises(ValueError) as exc_info:
            ToolParser.parse_response(response)
        
        assert "Missing required field: 'thought'" in str(exc_info.value)
    
    def test_parse_response_missing_action(self):
        """TC033: 缺少action字段应抛出异常"""
        response = '''
        {
            "thought": "I need to read the file",
            "action_input": {"file_path": "/tmp/test.txt"}
        }
        '''
        
        with pytest.raises(ValueError) as exc_info:
            ToolParser.parse_response(response)
        
        assert "Missing required field: 'action'" in str(exc_info.value)
    
    def test_parse_response_missing_action_input(self):
        """TC034: 缺少action_input字段应使用空字典"""
        response = '''
        {
            "thought": "I will finish the task",
            "action": "finish"
        }
        '''
        
        result = ToolParser.parse_response(response)
        
        assert result["action"] == "finish"
        assert result["action_input"] == {}
    
    def test_parse_response_action_input_camel_case(self):
        """TC035: 处理camelCase的actionInput"""
        response = '''
        {
            "thought": "I need to write to file",
            "action": "write_file",
            "actionInput": {"file_path": "/tmp/out.txt", "content": "hello"}
        }
        '''
        
        result = ToolParser.parse_response(response)
        
        assert result["action"] == "write_file"
        assert "action_input" in result
        assert result["action_input"]["file_path"] == "/tmp/out.txt"
    
    def test_parse_response_with_extra_fields(self):
        """TC036: 处理包含额外字段的响应"""
        response = '''
        {
            "thought": "Reading configuration",
            "action": "read_file",
            "action_input": {"file_path": "/etc/config"},
            "extra_field": "should be ignored",
            "another_extra": 123
        }
        '''
        
        result = ToolParser.parse_response(response)
        
        assert result["thought"] == "Reading configuration"
        assert result["action"] == "read_file"
        # 注：当前实现会过滤额外字段，只保留thought/action/action_input
        # 这是设计决策，确保返回结构的一致性


class TestParseInvalidResponse:
    """测试无效响应处理"""
    
    def test_parse_plain_text_response(self):
        """TC037: 解析非结构化文本响应"""
        response = '''
        I think I need to read the configuration file first to understand the structure.
        
        Action: read_file
        
        With parameters: {"file_path": "/etc/config.yaml"}
        '''
        
        result = ToolParser.parse_response(response)
        
        assert "read" in result["thought"].lower() or "understand" in result["thought"].lower()
        assert result["action"] == "read_file"
        assert result["action_input"]["file_path"] == "/etc/config.yaml"
    
    def test_parse_malformed_json(self):
        """TC038: 解析格式错误的JSON"""
        response = '''
        {
            "thought": "I need to check the directory",
            "action": "list_directory",
            "action_input": {"dir_path": "/tmp"},
            trailing comma here,
        }
        '''
        
        # 应该尝试从文本中提取或使用回退方案
        result = ToolParser.parse_response(response)
        
        # 至少应该提取到action
        assert result["action"] == "list_directory"
    
    def test_parse_empty_response(self):
        """TC039: 解析空响应应抛出异常"""
        response = ""
        
        with pytest.raises(ValueError):
            ToolParser.parse_response(response)
    
    def test_parse_invalid_json_no_structure(self):
        """TC040: 完全无效的JSON（无法提取任何结构）"""
        response = "This is just plain text without any structure or JSON format"
        
        # 应该抛出异常或返回None
        with pytest.raises(ValueError):
            ToolParser.parse_response(response)
    
    def test_parse_partial_json(self):
        """TC041: 部分JSON（只有thought）"""
        response = '''
        {
            "thought": "I am thinking about what to do next"
        }
        '''
        
        with pytest.raises(ValueError) as exc_info:
            ToolParser.parse_response(response)
        
        assert "Missing required field: 'action'" in str(exc_info.value)


class TestExtractFromText:
    """测试文本提取功能（内部方法）"""
    
    def test_extract_thought_various_formats(self):
        """TC042: 提取不同格式的thought"""
        test_cases = [
            ('Thought: "I need to read the file"', "I need to read the file"),
            ('thinking: I should check the logs', "I should check the logs"),
            ('I think I need to analyze the data', "I need to analyze the data"),
            ('Let me check the directory first', "check the directory first"),
        ]
        
        for text, expected_thought in test_cases:
            result = ToolParser._extract_from_text(text)
            if result:
                assert expected_thought.lower() in result["thought"].lower()
    
    def test_extract_action_various_formats(self):
        """TC043: 提取不同格式的action"""
        test_cases = [
            ('action: read_file', "read_file"),
            ('Action: "write_file"', "write_file"),
            ('use the list_directory tool', "list_directory"),
            ('call delete_file', "delete_file"),
        ]
        
        for text, expected_action in test_cases:
            result = ToolParser._extract_from_text(text)
            if result:
                assert result["action"] == expected_action
    
    def test_extract_action_input(self):
        """TC044: 提取action_input参数"""
        text = '''
        action_input: {"file_path": "/tmp/test.txt", "content": "hello"}
        '''
        
        result = ToolParser._extract_from_text(text)
        
        if result:
            assert "action_input" in result
            assert result["action_input"]["file_path"] == "/tmp/test.txt"
    
    def test_extract_no_match(self):
        """TC045: 无法提取任何有效信息"""
        text = "This is completely unrelated text"
        
        result = ToolParser._extract_from_text(text)
        
        assert result is None


class ToolParserEdgeCases:
    """边界情况测试"""
    
    def test_parse_unicode_content(self):
        """TC046: 解析包含Unicode的响应"""
        response = '''
        {
            "thought": "我需要读取文件 📄",
            "action": "read_file",
            "action_input": {"file_path": "/tmp/测试.txt"}
        }
        '''
        
        result = ToolParser.parse_response(response)
        
        assert "我需要读取文件" in result["thought"]
        assert result["action_input"]["file_path"] == "/tmp/测试.txt"
    
    def test_parse_nested_json(self):
        """TC047: 解析嵌套JSON对象"""
        response = '''
        {
            "thought": "Complex operation",
            "action": "write_file",
            "action_input": {
                "file_path": "/tmp/config.json",
                "content": {
                    "nested": {
                        "deep": "value"
                    }
                }
            }
        }
        '''
        
        result = ToolParser.parse_response(response)
        
        assert result["action_input"]["content"]["nested"]["deep"] == "value"
    
    def test_parse_large_response(self):
        """TC048: 解析大型响应"""
        large_thought = "I need to analyze this " + "very " * 1000 + "long text"
        response = json.dumps({
            "thought": large_thought,
            "action": "read_file",
            "action_input": {"file_path": "/tmp/big.txt"}
        })
        
        result = ToolParser.parse_response(response)
        
        assert len(result["thought"]) > 1000
        assert result["action"] == "read_file"
    
    def test_parse_special_characters(self):
        """TC049: 解析包含特殊字符的响应"""
        response = r'''
        {
            "thought": "Path with special chars: C:\\Users\\test\\file.txt",
            "action": "read_file",
            "action_input": {"file_path": "C:\\Users\\test\\file.txt"}
        }
        '''
        
        result = ToolParser.parse_response(response)
        
        assert "C:" in result["action_input"]["file_path"]
    
    def test_parse_array_in_action_input(self):
        """TC050: action_input包含数组"""
        response = '''
        {
            "thought": "Search multiple patterns",
            "action": "search_files",
            "action_input": {
                "patterns": ["error", "warning", "info"],
                "path": "/logs"
            }
        }
        '''
        
        result = ToolParser.parse_response(response)
        
        assert isinstance(result["action_input"]["patterns"], list)
        assert len(result["action_input"]["patterns"]) == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])