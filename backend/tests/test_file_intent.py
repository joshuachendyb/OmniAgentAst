"""
FileIntent 测试 - 小沈

测试file意图定义的核心功能。

Author: 小沈 - 2026-03-21
"""

import pytest

from app.services.intents.definitions.file.file_intent import FileIntent


class TestFileIntentCreation:
    """测试FileIntent创建"""
    
    def test_create_default(self):
        """测试默认创建"""
        intent = FileIntent()
        
        assert intent.name == "file"
        assert intent.description == "文件读写、目录管理、文件搜索等文件操作"
        assert intent.safety_checker == "file_safety"
    
    def test_create_with_custom_values(self):
        """测试自定义值创建"""
        intent = FileIntent(
            name="custom_file",
            description="自定义文件操作",
            safety_checker="custom_safety"
        )
        
        assert intent.name == "custom_file"
        assert intent.description == "自定义文件操作"
        assert intent.safety_checker == "custom_safety"


class TestFileIntentFields:
    """测试FileIntent字段"""
    
    def test_has_name_field(self):
        """测试有name字段"""
        intent = FileIntent()
        assert hasattr(intent, 'name')
        assert intent.name == "file"
    
    def test_has_description_field(self):
        """测试有description字段"""
        intent = FileIntent()
        assert hasattr(intent, 'description')
        assert len(intent.description) > 0
    
    def test_has_keywords_field(self):
        """测试有keywords字段"""
        intent = FileIntent()
        assert hasattr(intent, 'keywords')
        assert isinstance(intent.keywords, list)
        assert len(intent.keywords) > 0
    
    def test_has_tools_field(self):
        """测试有tools字段"""
        intent = FileIntent()
        assert hasattr(intent, 'tools')
        assert isinstance(intent.tools, list)
        assert len(intent.tools) > 0
    
    def test_has_safety_checker_field(self):
        """测试有safety_checker字段"""
        intent = FileIntent()
        assert hasattr(intent, 'safety_checker')
        assert intent.safety_checker == "file_safety"
    
    def test_has_prompt_template_field(self):
        """测试有prompt_template字段"""
        intent = FileIntent()
        assert hasattr(intent, 'prompt_template')
        assert intent.prompt_template is None


class TestFileIntentKeywords:
    """测试FileIntent关键词"""
    
    def test_contains_chinese_keywords(self):
        """测试包含中文关键词"""
        intent = FileIntent()
        
        assert "文件" in intent.keywords
        assert "读取" in intent.keywords
        assert "写入" in intent.keywords
        assert "删除" in intent.keywords
        assert "移动" in intent.keywords
        assert "搜索" in intent.keywords
    
    def test_contains_english_keywords(self):
        """测试包含英文关键词"""
        intent = FileIntent()
        
        assert "file" in intent.keywords
        assert "read" in intent.keywords
        assert "write" in intent.keywords
        assert "delete" in intent.keywords
        assert "move" in intent.keywords
        assert "search" in intent.keywords
    
    def test_custom_keywords(self):
        """测试自定义关键词"""
        intent = FileIntent(keywords=["自定义1", "自定义2"])
        
        assert intent.keywords == ["自定义1", "自定义2"]


class TestFileIntentTools:
    """测试FileIntent工具"""
    
    def test_contains_all_required_tools(self):
        """测试包含所有必需工具"""
        intent = FileIntent()
        
        required_tools = [
            "read_file",
            "write_file",
            "list_directory",
            "delete_file",
            "move_file",
            "search_files",
            "generate_report"
        ]
        
        for tool in required_tools:
            assert tool in intent.tools, f"缺少工具: {tool}"
    
    def test_tools_count(self):
        """测试工具数量"""
        intent = FileIntent()
        assert len(intent.tools) == 7
    
    def test_custom_tools(self):
        """测试自定义工具"""
        intent = FileIntent(tools=["tool1", "tool2"])
        
        assert intent.tools == ["tool1", "tool2"]


class TestFileIntentSerialization:
    """测试FileIntent序列化"""
    
    def test_to_dict(self):
        """测试转换为字典"""
        intent = FileIntent()
        data = intent.model_dump()
        
        assert isinstance(data, dict)
        assert data["name"] == "file"
        assert data["safety_checker"] == "file_safety"
    
    def test_to_json(self):
        """测试转换为JSON"""
        import json
        intent = FileIntent()
        json_str = intent.model_dump_json()
        
        data = json.loads(json_str)
        assert data["name"] == "file"
        assert data["safety_checker"] == "file_safety"
    
    def test_from_dict(self):
        """测试从字典创建"""
        data = {
            "name": "custom",
            "description": "自定义描述",
            "keywords": ["kw1"],
            "tools": ["tool1"],
            "safety_checker": "custom_safety"
        }
        
        intent = FileIntent(**data)
        assert intent.name == "custom"
        assert intent.description == "自定义描述"
