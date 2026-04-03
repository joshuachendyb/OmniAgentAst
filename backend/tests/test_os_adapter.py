"""
OSAdapter 测试 - 小沈

测试操作系统适配器的核心功能。

Author: 小沈 - 2026-03-21
"""

import pytest
from unittest.mock import patch

from app.services.agent.os_adapter import OSAdapter


class TestOSAdapterInitialization:
    """测试OSAdapter初始化"""
    
    def test_adapter_initialization(self):
        """测试适配器初始化"""
        adapter = OSAdapter()
        assert adapter.system in ["Windows", "Linux", "Darwin"]
    
    def test_adapter_has_system_property(self):
        """测试适配器有system属性"""
        adapter = OSAdapter()
        assert hasattr(adapter, 'system')


class TestOSAdapterProperties:
    """测试OSAdapter属性"""
    
    def test_is_windows_property(self):
        """测试is_windows属性"""
        with patch('platform.system', return_value='Windows'):
            adapter = OSAdapter()
            assert adapter.is_windows == True
            assert adapter.is_linux == False
            assert adapter.is_macos == False
    
    def test_is_linux_property(self):
        """测试is_linux属性"""
        with patch('platform.system', return_value='Linux'):
            adapter = OSAdapter()
            assert adapter.is_windows == False
            assert adapter.is_linux == True
            assert adapter.is_macos == False
    
    def test_is_macos_property(self):
        """测试is_macos属性"""
        with patch('platform.system', return_value='Darwin'):
            adapter = OSAdapter()
            assert adapter.is_windows == False
            assert adapter.is_linux == False
            assert adapter.is_macos == True
    
    def test_path_separator_windows(self):
        """测试Windows路径分隔符"""
        with patch('platform.system', return_value='Windows'):
            adapter = OSAdapter()
            assert adapter.path_separator == "\\"
    
    def test_path_separator_linux(self):
        """测试Linux路径分隔符"""
        with patch('platform.system', return_value='Linux'):
            adapter = OSAdapter()
            assert adapter.path_separator == "/"
    
    def test_path_separator_macos(self):
        """测试macOS路径分隔符"""
        with patch('platform.system', return_value='Darwin'):
            adapter = OSAdapter()
            assert adapter.path_separator == "/"


class TestOSAdapterCommands:
    """测试OSAdapter命令映射"""
    
    def test_windows_commands(self):
        """测试Windows命令映射"""
        with patch('platform.system', return_value='Windows'):
            adapter = OSAdapter()
            commands = adapter.commands
            
            assert commands["list"] == "dir"
            assert commands["copy"] == "copy"
            assert commands["move"] == "move"
            assert commands["delete"] == "del"
            assert commands["read"] == "type"
            assert commands["write"] == "echo"
    
    def test_linux_commands(self):
        """测试Linux命令映射"""
        with patch('platform.system', return_value='Linux'):
            adapter = OSAdapter()
            commands = adapter.commands
            
            assert commands["list"] == "ls"
            assert commands["copy"] == "cp"
            assert commands["move"] == "mv"
            assert commands["delete"] == "rm"
            assert commands["read"] == "cat"
            assert commands["write"] == "echo"
    
    def test_macos_commands(self):
        """测试macOS命令映射"""
        with patch('platform.system', return_value='Darwin'):
            adapter = OSAdapter()
            commands = adapter.commands
            
            assert commands["list"] == "ls"
            assert commands["copy"] == "cp"
            assert commands["move"] == "mv"
            assert commands["delete"] == "rm"
            assert commands["read"] == "cat"
            assert commands["write"] == "echo"


class TestOSAdapterMethods:
    """测试OSAdapter方法"""
    
    def test_get_system_prompt_windows(self):
        """测试Windows系统提示"""
        with patch('platform.system', return_value='Windows'):
            adapter = OSAdapter()
            prompt = adapter.get_system_prompt()
            
            assert "Windows" in prompt
            assert "dir" in prompt
            assert "C:\\Users" in prompt
    
    def test_get_system_prompt_linux(self):
        """测试Linux系统提示"""
        with patch('platform.system', return_value='Linux'):
            adapter = OSAdapter()
            prompt = adapter.get_system_prompt()
            
            assert "Linux" in prompt
            assert "ls" in prompt
            assert "/home" in prompt
    
    def test_get_tool_descriptions_windows(self):
        """测试Windows工具描述"""
        with patch('platform.system', return_value='Windows'):
            adapter = OSAdapter()
            desc = adapter.get_tool_descriptions()
            
            assert "C:\\Users" in desc["path"]
            assert "Windows" in desc["description"]
    
    def test_get_tool_descriptions_linux(self):
        """测试Linux工具描述"""
        with patch('platform.system', return_value='Linux'):
            adapter = OSAdapter()
            desc = adapter.get_tool_descriptions()
            
            assert "/home" in desc["path"]
            assert "Linux" in desc["description"] or "Mac" in desc["description"]
    
    def test_repr(self):
        """测试__repr__方法"""
        with patch('platform.system', return_value='Windows'):
            adapter = OSAdapter()
            repr_str = repr(adapter)
            
            assert "OSAdapter" in repr_str
            assert "Windows" in repr_str
