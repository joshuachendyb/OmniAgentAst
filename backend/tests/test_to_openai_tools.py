"""
to_openai_tools() 测试 - 验证2026-05-09修复

测试范围:
- to_openai_tools() 方法存在性
- 正确生成OpenAI格式tools定义
- 正确过滤expose_to_llm
- category参数过滤

Author: 小沈 - 2026-05-09
"""
import pytest
from app.services.tools.registry import ToolCategory, ToolRegistry, ToolMetadata, tool_registry


class TestToOpenAITools:
    """测试 to_openai_tools 方法"""

    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        """每个测试前备份注册表状态"""
        backup_tools = dict(tool_registry._tools)
        backup_categories = dict(tool_registry._categories)
        backup_impls = dict(tool_registry._implementations)
        yield
        tool_registry._tools = backup_tools
        tool_registry._categories = backup_categories
        tool_registry._implementations = backup_impls

    def test_method_exists(self):
        """验证 to_openai_tools 方法存在"""
        assert hasattr(tool_registry, 'to_openai_tools')

    def test_empty_registry_returns_empty_list(self):
        """空注册表返回空列表"""
        registry = ToolRegistry()
        result = registry.to_openai_tools()
        assert result == []

    def test_single_tool_format(self):
        """单个工具返回正确OpenAI格式"""
        registry = ToolRegistry()
        meta = ToolMetadata(
            name="test_tool",
            description="测试工具",
            category=ToolCategory.FILE,
            input_schema={
                "type": "object",
                "properties": {"param1": {"type": "string"}},
                "required": ["param1"]
            },
            expose_to_llm=True
        )
        # 直接操作内部存储
        registry._tools["test_tool"] = meta
        registry._categories[ToolCategory.FILE] = ["test_tool"]

        result = registry.to_openai_tools()
        assert len(result) == 1
        tool = result[0]
        assert tool["type"] == "function"
        assert tool["function"]["name"] == "test_tool"
        assert tool["function"]["description"] == "测试工具"
        assert "parameters" in tool["function"]

    def test_expose_to_llm_filter(self):
        """正确过滤expose_to_llm=False的工具"""
        registry = ToolRegistry()
        # 注册一个暴露的工具
        meta1 = ToolMetadata(
            name="exposed_tool", description="暴露工具",
            category=ToolCategory.FILE, expose_to_llm=True
        )
        # 注册一个不暴露的工具
        meta2 = ToolMetadata(
            name="hidden_tool", description="隐藏工具",
            category=ToolCategory.FILE, expose_to_llm=False
        )
        registry._tools["exposed_tool"] = meta1
        registry._tools["hidden_tool"] = meta2
        registry._categories[ToolCategory.FILE] = ["exposed_tool", "hidden_tool"]

        result = registry.to_openai_tools()
        assert len(result) == 1
        assert result[0]["function"]["name"] == "exposed_tool"

    def test_category_filter(self):
        """正确按category过滤"""
        registry = ToolRegistry()
        meta_file = ToolMetadata(
            name="file_tool", description="文件工具",
            category=ToolCategory.FILE, expose_to_llm=True
        )
        meta_shell = ToolMetadata(
            name="shell_tool", description="Shell工具",
            category=ToolCategory.SHELL, expose_to_llm=True
        )
        registry._tools["file_tool"] = meta_file
        registry._tools["shell_tool"] = meta_shell
        registry._categories[ToolCategory.FILE] = ["file_tool"]
        registry._categories[ToolCategory.SHELL] = ["shell_tool"]

        # 过滤FILE分类
        result = registry.to_openai_tools(category=ToolCategory.FILE)
        assert len(result) == 1
        assert result[0]["function"]["name"] == "file_tool"

        # 过滤SHELL分类
        result = registry.to_openai_tools(category=ToolCategory.SHELL)
        assert len(result) == 1
        assert result[0]["function"]["name"] == "shell_tool"

    def test_multiple_tools_sorted(self):
        """多个工具按名称排序"""
        registry = ToolRegistry()
        tools = [
            ("z_tool", ToolCategory.FILE),
            ("a_tool", ToolCategory.FILE),
            ("m_tool", ToolCategory.FILE),
        ]
        for name, cat in tools:
            meta = ToolMetadata(
                name=name, description=f"{name}描述",
                category=cat, expose_to_llm=True
            )
            registry._tools[name] = meta
        registry._categories[ToolCategory.FILE] = ["a_tool", "m_tool", "z_tool"]

        result = registry.to_openai_tools()
        names = [t["function"]["name"] for t in result]
        assert names == ["a_tool", "m_tool", "z_tool"]


class TestGenerateParamReminder:
    """测试 generate_param_reminder 方法"""

    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        """每个测试前备份注册表状态"""
        backup_tools = dict(tool_registry._tools)
        yield
        tool_registry._tools = backup_tools

    def test_method_exists(self):
        """验证 generate_param_reminder 方法存在"""
        assert hasattr(tool_registry, 'generate_param_reminder')

    def test_empty_result(self):
        """空注册表返回基础文本"""
        registry = ToolRegistry()
        result = registry.generate_param_reminder()
        assert "Parameter Reminder" in result

    def test_with_required_params(self):
        """必填参数正确显示"""
        registry = ToolRegistry()
        meta = ToolMetadata(
            name="test_tool",
            description="测试工具",
            category=ToolCategory.FILE,
            input_schema={
                "type": "object",
                "properties": {
                    "param1": {"type": "string", "default": "default_value"},
                    "param2": {"type": "integer"}
                },
                "required": ["param2"]
            },
            expose_to_llm=True
        )
        registry._tools["test_tool"] = meta
        registry._categories[ToolCategory.FILE] = ["test_tool"]

        result = registry.generate_param_reminder()
        assert "test_tool" in result
        assert "param2" in result
        assert "required" in result
        # param1有默认值应显示
        assert "param1" in result

    def test_category_filter(self):
        """正确按category过滤"""
        registry = ToolRegistry()
        meta_file = ToolMetadata(
            name="file_tool", description="文件工具",
            category=ToolCategory.FILE,
            input_schema={"type": "object", "properties": {"param1": {"type": "string"}}},
            expose_to_llm=True
        )
        meta_shell = ToolMetadata(
            name="shell_tool", description="Shell工具",
            category=ToolCategory.SHELL,
            input_schema={"type": "object", "properties": {"param2": {"type": "string"}}},
            expose_to_llm=True
        )
        registry._tools["file_tool"] = meta_file
        registry._tools["shell_tool"] = meta_shell
        registry._categories[ToolCategory.FILE] = ["file_tool"]
        registry._categories[ToolCategory.SHELL] = ["shell_tool"]

        result = registry.generate_param_reminder(category=ToolCategory.FILE)
        assert "file_tool" in result
        assert "shell_tool" not in result