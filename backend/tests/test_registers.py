"""
Register模块导入测试 - 验证2026-05-06以来的代码更新
验证13个register模块可以正确导入

Author: 小沈 - 2026-05-09
"""
import pytest


class TestRegisterImports:
    """验证register模块导入"""
    
    def test_file_register_import(self):
        """file_register可导入"""
        from app.services.tools.file import file_register
        assert file_register is not None
    
    def test_shell_register_import(self):
        """shell_register可导入"""
        from app.services.tools.shell import shell_register
        assert shell_register is not None
    
    def test_network_register_import(self):
        """network_register可导入"""
        from app.services.tools.network import network_register
        assert network_register is not None
    
    def test_time_register_import(self):
        """time_register可导入"""
        from app.services.tools.time import time_register
        assert time_register is not None
    
    def test_environment_register_import(self):
        """environment可导入"""
        from app.services.tools.environment import env_register
        assert env_register is not None
    
    def test_system_register_import(self):
        """system可导入"""
        from app.services.tools.system import system_register
        assert system_register is not None
    
    def test_data_format_register_import(self):
        """data_format可导入"""
        from app.services.tools.data_format import data_format_register
        assert data_format_register is not None
    
    def test_support_tool_register_import(self):
        """support_tool可导入"""
        from app.services.tools.support_tool import support_tool_register
        assert support_tool_register is not None


class TestToolRegistryIntegration:
    """测试工具注册表集成"""
    
    def test_tool_registry_has_tools(self):
        """验证工具注册表有工具"""
        from app.services.tools.registry import tool_registry
        tool_count = len(tool_registry._tools)
        assert tool_count > 0
    
    def test_get_all_tools_summary(self):
        """验证概要生成"""
        from app.services.tools.registry import tool_registry
        summary = tool_registry.get_all_tools_summary()
        assert "=== 可用工具列表 ===" in summary
    
    def test_generate_param_reminder(self):
        """验证参数提醒生成"""
        from app.services.tools.registry import tool_registry
        reminder = tool_registry.generate_param_reminder()
        assert "Parameter Reminder" in reminder
    
    def test_to_openai_tools(self):
        """验证OpenAI工具格式"""
        from app.services.tools.registry import tool_registry
        tools = tool_registry.to_openai_tools()
        assert isinstance(tools, list)
    
    def test_categories_exist(self):
        """验证分类定义存在"""
        from app.services.tools.registry import ToolCategory
        # 主要分类应该存在
        assert hasattr(ToolCategory, 'FILE')
        assert hasattr(ToolCategory, 'SHELL')
        assert hasattr(ToolCategory, 'NETWORK')
        assert hasattr(ToolCategory, 'TIME')
        assert hasattr(ToolCategory, 'ENVIRONMENT')
        assert hasattr(ToolCategory, 'SYSTEM')


class TestDescriptionsFormat:
    """验证description格式"""
    
    def test_file_descriptions(self):
        """file工���description存在"""
        from app.services.tools.file import file_register
        assert hasattr(file_register, 'FILE_TOOL_DESCRIPTIONS')
        assert len(file_register.FILE_TOOL_DESCRIPTIONS) > 0
    
    def test_shell_descriptions(self):
        """shell工具description存在"""
        from app.services.tools.shell import shell_register
        assert hasattr(shell_register, 'SHELL_TOOL_DESCRIPTIONS')
    
    def test_network_descriptions(self):
        """network工具description存在"""
        from app.services.tools.network import network_register
        assert hasattr(network_register, 'NETWORK_TOOL_DESCRIPTIONS')
    
    def test_time_descriptions(self):
        """time工具description存在"""
        from app.services.tools.time import time_register
        assert hasattr(time_register, 'TIME_TOOL_DESCRIPTIONS')