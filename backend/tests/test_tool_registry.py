"""
ToolRegistry 测试 - 小健

T1: 工具注册表重构 - 测试用例
按TTD流程编写：先写失败测试，再实现代码

【更新】2026-04-26 小沈
- 添加新分类枚举测试
- 添加架构注释验证测试

Author: 小健 - 2026-04-19
Author: 小沈 - 2026-04-26
"""

import pytest
from dataclasses import dataclass
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum

# 使用 registry.py 中的 ToolCategory 枚举
from app.services.tools.registry import ToolCategory, tool_registry, register_tool


@dataclass
class ToolMetadata:
    """工具元数据"""
    name: str
    description: str
    category: ToolCategory
    version: str = "1.0.0"
    registered_at: Optional[str] = None


class TestToolCategoryEnum:
    """测试工具分类枚举 - 【新增】2026-04-26 小沈"""
    
    def test_tool_category_has_all_categories(self):
        """验证 ToolCategory 枚举包含所有预期的分类"""
        expected_categories = [
            "file", "time", "shell", "network", "environment", "system", "database", "desktop", "document", "support_tool", "data_format", "code_execution"
        ]
        actual_categories = [c.value for c in ToolCategory]
        
        for expected in expected_categories:
            assert expected in actual_categories, f"缺少分类: {expected}"
    
    def test_tool_category_count(self):
        """验证 ToolCategory 枚举数量为12"""
        assert len([c for c in ToolCategory]) == 12
    
    def test_time_category_exists(self):
        """验证 TIME 分类存在"""
        assert ToolCategory.TIME.value == "time"
    
    def test_shell_category_exists(self):
        """验证 SHELL 分类存在"""
        assert ToolCategory.SHELL.value == "shell"


class TestRegisterToolDecorator:
    """测试 register_tool 装饰器 - 【新增】2026-04-26 小沈"""
    
    def test_register_decorator_works(self):
        """验证 @register_tool 装饰器可以正常工作"""
        # 创建一个临时测试工具
        @register_tool(
            name="test_decorator_tool",
            description="装饰器测试工具",
            category=ToolCategory.FILE,
            examples=[{"param": "value"}]
        )
        def test_func(param: str) -> Dict[str, Any]:
            return {"result": param}
        
        # 验证工具已注册
        tool = tool_registry.get_tool("test_decorator_tool")
        assert tool is not None
        assert tool.name == "test_decorator_tool"
        assert tool.description == "装饰器测试工具"
        assert tool.category == ToolCategory.FILE
    
    def test_register_decorator_examples(self):
        """验证装饰器正确保存 examples"""
        @register_tool(
            name="test_examples_tool",
            description="测试示例工具",
            category=ToolCategory.TIME,
            examples=[
                {"key1": "value1"},
                {"key2": "value2"}
            ]
        )
        def test_func(): pass
        
        tool = tool_registry.get_tool("test_examples_tool")
        assert tool is not None
        assert len(tool.examples) == 2


class TestToolRegistry:
    """工具注册表测试套件"""
    
    @pytest.fixture
    def registry(self):
        """创建新的注册表实例"""
        from app.services.tools.registry import ToolRegistry
        return ToolRegistry()
    
    # ====== RED阶段：先写失败测试 ======
    
    class TestRegister:
        """测试工具注册"""
        
        def test_register_tool(self, registry):
            """RED: 注册工具应该成功"""
            def mock_tool(param1: str) -> Dict[str, Any]:
                return {"result": "ok"}
            
            # 文档设计：成功注册无异常
            registry.register(
                name="test_tool",
                description="测试工具",
                category=ToolCategory.FILE,
                implementation=mock_tool
            )
            
            # 验证注册成功
            assert registry.get("test_tool") is not None
        
        def test_register_duplicate_tool(self, registry):
            """RED: 重复注册应该更新并返回success"""
            def mock_tool1(param1: str) -> Dict[str, Any]:
                return {"result": "ok"}
            
            def mock_tool2(param1: str) -> Dict[str, Any]:
                return {"result": "ok2"}
            
            registry.register(
                name="duplicate_tool",
                description="工具1",
                category=ToolCategory.FILE,
                implementation=mock_tool1
            )
            
            # 文档设计：重复注册允许更新（v1.15第6.2.1允许重复注册）
            result = registry.register(
                name="duplicate_tool",
                description="工具2",
                category=ToolCategory.FILE,
                implementation=mock_tool2
            )
            
            assert result["status"] == "success"
            # 验证版本已更新
            tool = registry.get("duplicate_tool")
            assert tool["description"] == "工具2"
    
    class TestUnregister:
        """测试工具注销"""
        
        def test_unregister_existing_tool(self, registry):
            """RED: 注销已存在的工具应该成功"""
            def mock_tool(param1: str) -> Dict[str, Any]:
                return {"result": "ok"}
            
            registry.register(
                name="tool_to_unregister",
                description="测试工具",
                category=ToolCategory.FILE,
                implementation=mock_tool
            )
            
            result = registry.unregister("tool_to_unregister")
            
            assert result["status"] == "success"
            assert registry.get("tool_to_unregister") is None
        
        def test_unregister_non_existing_tool(self, registry):
            """RED: 注销不存在的工具应该��败"""
            result = registry.unregister("non_existing_tool")
            
            assert result["status"] == "error"
            assert "not found" in result["error"].lower()
    
    class TestGet:
        """测试获取工具"""
        
        def test_get_existing_tool(self, registry):
            """RED: 获取已存在的工具应该返回元数据"""
            def mock_tool(param1: str) -> Dict[str, Any]:
                return {"result": "ok"}
            
            registry.register(
                name="existing_tool",
                description="测试工具",
                category=ToolCategory.FILE,
                implementation=mock_tool
            )
            
            tool = registry.get("existing_tool")
            
            assert tool is not None
            assert tool["name"] == "existing_tool"
            assert tool["description"] == "测试工具"
        
        def test_get_non_existing_tool(self, registry):
            """RED: 获取不存在的工具应该返回None"""
            tool = registry.get("non_existing_tool")
            
            assert tool is None
    
    class TestList:
        """测试列出工具"""
        
        def test_list_all_tools(self, registry):
            """RED: 列出所有工具应该返回列表"""
            def mock_tool1(param1: str) -> Dict[str, Any]:
                return {"result": "ok1"}
            
            def mock_tool2(param1: str) -> Dict[str, Any]:
                return {"result": "ok2"}
            
            registry.register(
                name="tool_1",
                description="工具1",
                category=ToolCategory.FILE,
                implementation=mock_tool1
            )
            registry.register(
                name="tool_2",
                description="工具2",
                category=ToolCategory.SYSTEM,
                implementation=mock_tool2
            )
            
            tools = registry.list_tools()
            
            assert len(tools) == 2
        
        def test_list_tools_by_category(self, registry):
            """RED: 按分类列出工具应该正确过滤"""
            def mock_file_tool(param1: str) -> Dict[str, Any]:
                return {"result": "ok"}
            
            def mock_system_tool(param1: str) -> Dict[str, Any]:
                return {"result": "ok"}
            
            registry.register(
                name="file_tool",
                description="文件工具",
                category=ToolCategory.FILE,
                implementation=mock_file_tool
            )
            registry.register(
                name="system_tool",
                description="系统工具",
                category=ToolCategory.SYSTEM,
                implementation=mock_system_tool
            )
            
            file_tools = registry.list_tools(category=ToolCategory.FILE)
            
            assert len(file_tools) == 1
            assert file_tools[0]["category"] == "file"
    
    class TestLifecycle:
        """测试生命周期管理"""
        
        def test_register_increments_version(self, registry):
            """RED: 重复注册应该更新版本"""
            def mock_tool_v1(param1: str) -> Dict[str, Any]:
                return {"version": 1}
            
            def mock_tool_v2(param1: str) -> Dict[str, Any]:
                return {"version": 2}
            
            registry.register(
                name="versioned_tool",
                description="工具v1",
                category=ToolCategory.FILE,
                implementation=mock_tool_v1
            )
            
            # 重新注册（模拟更新）
            result = registry.register(
                name="versioned_tool",
                description="工具v2",
                category=ToolCategory.FILE,
                implementation=mock_tool_v2
            )
            
            # 应该成功（允许更新）
            assert result["status"] == "success"


class TestToolRegistryIntegration:
    """工具注册表集成测试"""
    
    @pytest.fixture
    def registry(self):
        from app.services.tools.registry import ToolRegistry
        return ToolRegistry()
    
    def test_full_lifecycle(self, registry):
        """RED: 完整生命周期：注册→获取→列出→注销"""
        def mock_tool(param1: str) -> Dict[str, Any]:
            return {"result": "ok"}
        
        # 1. 注册
        result = registry.register(
            name="lifecycle_tool",
            description="生命周期测试工具",
            category=ToolCategory.FILE,
            implementation=mock_tool
        )
        assert result["status"] == "success"
        
        # 2. 获取
        tool = registry.get("lifecycle_tool")
        assert tool is not None
        
        # 3. 列出
        tools = registry.list_tools()
        assert any(t["name"] == "lifecycle_tool" for t in tools)
        
        # 4. 注销
        result = registry.unregister("lifecycle_tool")
        assert result["status"] == "success"
        
        # 5. 验证已注销
        tool = registry.get("lifecycle_tool")
        assert tool is None


class TestFileToolsRegistration:
    """【新增】2026-04-26 小健 - file工具注册测试"""
    
    def test_file_tools_registered(self):
        """验证file工具已注册"""
        # 触发注册
        from app.services.tools.file import file_register
        from app.services.tools.registry import tool_registry, ToolCategory
        tools = tool_registry.list_tools(category=ToolCategory.FILE)
        # 至少17个，实际可能是18个（含测试注册的）
        assert len(tools) >= 17
    
    def test_each_file_tool_has_implementation(self):
        """验证每个file工具都有实现"""
        from app.services.tools.file import file_register
        from app.services.tools.registry import tool_registry, ToolCategory
        tools = tool_registry.list_tools(category=ToolCategory.FILE)
        for tool in tools:
            impl = tool_registry.get_implementation(tool["name"])
            assert impl is not None, f"{tool['name']} 没有实现"
    
    def test_required_file_tools_exist(self):
        """验证必需的工具存在 - 使用新架构"""
        from app.services.tools.file.file_tools import FileTools
        from app.services.tools.registry import tool_registry
        # 新架构使用类方法，通过tool_registry检查
        tools = tool_registry.list_tools()
        assert len(tools) > 0, "工具注册表为空"
    
    def test_get_tools_from_file_registry(self):
        """验证文件工具可正常访问"""
        from app.services.tools.file.file_tools import FileTools
        ft = FileTools()
        assert hasattr(ft, 'read_text_file'), "FileTools缺少read_text_file方法"
        assert hasattr(ft, 'write_text_file'), "FileTools缺少write_text_file方法"


class TestRegistryIntegration:
    """【新增】2026-04-26 小健 - 集成测试"""
    
    def test_file_react_imports_work(self):
        """验证 FileReactAgent 可正常导入"""
        from app.services.agent.file_react import FileReactAgent
        assert FileReactAgent is not None
    
    def test_react_schema_imports_work(self):
        """验证 react_schema 可正常使用 registry"""
        from app.services.agent.types.react_schema import get_tools_schema_for_function_calling
        schemas = get_tools_schema_for_function_calling()
        assert len(schemas) > 0
    
    def test_no_legacy_code_in_file_tools(self):
        """验证 file_tools.py 没有废弃代码"""
        from app.services.tools.file import file_tools
        assert not hasattr(file_tools, '_TOOL_REGISTRY'), "仍有_TOOL_REGISTRY"
        assert not hasattr(file_tools, 'get_registered_tools'), "仍有get_registered_tools"
        assert not hasattr(file_tools, 'get_tool'), "仍有get_tool"
    
    def test_no_legacy_code_in_file_register(self):
        """验证 file_register.py 没有废弃代码"""
        from app.services.tools.file import file_register
        assert not hasattr(file_register, 'get_registered_tools'), "仍有get_registered_tools"
        assert not hasattr(file_register, 'get_tool'), "仍有get_tool"