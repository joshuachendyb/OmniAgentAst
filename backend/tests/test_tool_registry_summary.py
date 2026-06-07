"""
ToolRegistry get_all_tools_summary 测试

TDD: RED阶段 - 测试先失败，再实现
Author: 小沈 - 2026-04-30
"""
import pytest
from app.services.tools.registry import (
    ToolCategory, ToolRegistry, ToolMetadata, tool_registry
)


class TestExtractRequiredParams:
    """测试 _extract_required_params 辅助方法"""

    def test_empty_schema_returns_empty_list(self):
        """空schema返回空列表"""
        registry = ToolRegistry()
        assert registry._extract_required_params({}) == []

    def test_no_required_field_returns_empty(self):
        """没有required字段返回空列表"""
        registry = ToolRegistry()
        schema = {"type": "object", "properties": {"name": {"type": "string"}}}
        assert registry._extract_required_params(schema) == []

    def test_required_params_returned_sorted(self):
        """必填参数返回排序后的列表"""
        registry = ToolRegistry()
        schema = {
            "type": "object",
            "properties": {
                "file_path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["file_path", "content"]
        }
        assert registry._extract_required_params(schema) == ["content", "file_path"]

    def test_partial_required_only_required_returned(self):
        """只返回required中的参数，不返回非必填"""
        registry = ToolRegistry()
        schema = {
            "type": "object",
            "properties": {
                "file_path": {"type": "string"},
                "encoding": {"type": "string"},
            },
            "required": ["file_path"]
        }
        assert registry._extract_required_params(schema) == ["file_path"]

    def test_none_schema_returns_empty(self):
        """None schema返回空列表"""
        registry = ToolRegistry()
        assert registry._extract_required_params(None) == []


class TestGetAllToolsSummary:
    """测试 get_all_tools_summary 方法"""

    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        """每个测试前备份注册表状态"""
        registry = tool_registry
        # 保存原始状态
        backup_tools = dict(registry._tools)
        backup_categories = dict(registry._categories)
        backup_impls = dict(registry._implementations)
        yield
        # 恢复原始状态
        registry._tools = backup_tools
        registry._categories = backup_categories
        registry._implementations = backup_impls

    def test_method_exists(self):
        """验证 get_all_tools_summary 方法存在"""
        assert hasattr(tool_registry, 'get_all_tools_summary')

    def test_empty_registry_returns_header_only(self):
        """空注册表只返回头部"""
        registry = ToolRegistry()
        result = registry.get_all_tools_summary()
        assert "=== 可用工具列表 ===" in result

    def test_single_tool_in_summary(self):
        """单个工具的概要显示（名称 + 描述，不显示参数详情）"""
        registry = ToolRegistry()
        meta = ToolMetadata(
            name="test_tool",
            description="测试工具",
            category=ToolCategory.FILE,
            input_schema={
                "type": "object",
                "properties": {"param1": {"type": "string"}},
                "required": ["param1"]
            }
        )
        registry._tools["test_tool"] = meta
        registry._categories[ToolCategory.FILE] = ["test_tool"]
    
        result = registry.get_all_tools_summary()
        assert "test_tool" in result
        assert "测试工具" in result
        # get_all_tools_summary() 只显示名称和描述，不显示参数详情
        # 参数详情请使用 generate_param_reminder() 或 to_openai_tools()

    def test_priority_category_first(self):
        """priority_category 分类排在第一位"""
        registry = ToolRegistry()
        # 添加两个分类的工具
        meta_file = ToolMetadata(
            name="file_tool", description="文件工具", category=ToolCategory.FILE
        )
        meta_shell = ToolMetadata(
            name="shell_tool", description="Shell工具", category=ToolCategory.SHELL
        )
        registry._tools["file_tool"] = meta_file
        registry._tools["shell_tool"] = meta_shell
        registry._categories[ToolCategory.FILE] = ["file_tool"]
        registry._categories[ToolCategory.SHELL] = ["shell_tool"]

        # 以SHELL为优先级
        result = registry.get_all_tools_summary(priority_category=ToolCategory.SHELL)
        lines = result.split("\n")
        shell_idx = next(i for i, l in enumerate(lines) if "Shell" in l)
        file_idx = next(i for i, l in enumerate(lines) if "文件" in l)
        assert shell_idx < file_idx, "Shell应在文件之前"

    def test_summary_includes_category_name(self):
        """概要包含分类中文名"""
        registry = ToolRegistry()
        meta = ToolMetadata(
            name="tool1", description="工具1", category=ToolCategory.META
        )
        registry._tools["tool1"] = meta
        registry._categories[ToolCategory.META] = ["tool1"]

        result = registry.get_all_tools_summary()
        assert "【时间/元工具】" in result

    def test_multiple_tools_same_category_sorted(self):
        """同一分类的多个工具按名称排序"""
        registry = ToolRegistry()
        tools = {
            "z_tool": ToolMetadata(name="z_tool", description="Z工具", category=ToolCategory.FILE),
            "a_tool": ToolMetadata(name="a_tool", description="A工具", category=ToolCategory.FILE),
            "m_tool": ToolMetadata(name="m_tool", description="M工具", category=ToolCategory.FILE),
        }
        for name, meta in tools.items():
            registry._tools[name] = meta
        registry._categories[ToolCategory.FILE] = sorted(tools.keys())

        result = registry.get_all_tools_summary()
        a_pos = result.index("a_tool")
        m_pos = result.index("m_tool")
        z_pos = result.index("z_tool")
        assert a_pos < m_pos < z_pos, "工具应排序"

    def test_tool_without_params_shows_no_brackets(self):
        """无参数工具不显示括号"""
        registry = ToolRegistry()
        meta = ToolMetadata(
            name="no_params_tool", description="无参工具", category=ToolCategory.FILE
        )
        registry._tools["no_params_tool"] = meta
        registry._categories[ToolCategory.FILE] = ["no_params_tool"]

        result = registry.get_all_tools_summary()
        line = [l for l in result.split("\n") if "no_params_tool" in l][0]
        assert "()" not in line, "无参工具不应显示空括号"
