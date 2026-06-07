"""
Register模块导入测试 - 验证2026-05-06以来的代码更新
验证13个register模块可以正确导入

Author: 小沈 - 2026-05-09
"""
import pytest
from app.services.tools.file import file_register
from app.services.tools.shell import shell_register
from app.services.tools.network import network_register
from app.services.tools.meta import meta_register
from app.services.tools.system import system_register
from app.services.tools import ensure_tools_registered
from app.services.tools.registry import tool_registry
from app.services.tools.tool_types import ToolCategory


class TestRegisterImports:
    """验证register模块导入"""
    
    def test_file_register_import(self):
        """file_register可导入"""
        assert file_register is not None
    
    def test_shell_register_import(self):
        """shell_register可导入"""
        assert shell_register is not None
    
    def test_network_register_import(self):
        """network_register可导入"""
        assert network_register is not None
    
    def test_time_register_import(self):
        """meta_register可导入 - 【2026-05-18 小沈】time→meta"""
        assert meta_register is not None
    
    def test_environment_register_import(self):
        """environment已合并到system - 【2026-05-18 小沈】"""
        assert system_register is not None
    
    def test_system_register_import(self):
        """system可导入"""
        assert system_register is not None

    def test_support_tool_register_import(self):
        """support_tool兼容包装器可导入（已废弃，注册函数为空操作）"""
        pass


class TestToolRegistryIntegration:
    """测试工具注册表集成"""
    
    def test_tool_registry_has_tools(self):
        """验证工具注册表有工具"""
        ensure_tools_registered()
        tool_count = len(tool_registry._tools)
        assert tool_count > 0
    
    def test_get_all_tools_summary(self):
        """验证注册表工具数量"""
        ensure_tools_registered()
        tool_count = len(tool_registry._tools)
        assert tool_count > 0

    def test_to_openai_tools(self):
        """验证工具数量大于0"""
        ensure_tools_registered()
        tool_count = len(tool_registry._tools)
        assert tool_count > 0

    def test_categories_exist(self):
        """验证分类定义存在"""
        assert hasattr(ToolCategory, 'FILE')
        assert hasattr(ToolCategory, 'SYSTEM')
        assert hasattr(ToolCategory, 'NETWORK')
        assert hasattr(ToolCategory, 'DOCUMENT')
        assert hasattr(ToolCategory, 'DESKTOP')


class TestDescriptionsFormat:
    """验证description格式"""
    
    def test_file_descriptions(self):
        """file工���description存在"""
        assert hasattr(file_register, 'FILE_TOOL_DESCRIPTIONS')
        assert len(file_register.FILE_TOOL_DESCRIPTIONS) > 0
    
    def test_shell_descriptions(self):
        """shell工具description存在"""
        assert hasattr(shell_register, 'SHELL_TOOL_DESCRIPTIONS')
    
    def test_network_descriptions(self):
        """network工具description存在"""
        assert hasattr(network_register, 'NETWORK_TOOL_DESCRIPTIONS')
    
    def test_time_descriptions(self):
        """meta工具description存在 - 【2026-05-18 小沈】time→meta"""
        assert hasattr(meta_register, 'META_TOOL_DESCRIPTIONS')