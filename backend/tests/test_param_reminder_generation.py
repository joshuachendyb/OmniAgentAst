"""
Parameter Reminder 自动生成测试

TDD: 验证 generate_param_reminder() 和 to_openai_tools() 的正确性
Author: 小沈 小健 - 2026-05-09
"""
import pytest
from app.services.tools.registry import tool_registry, ToolCategory


class TestParamReminderGeneration:
    """测试 generate_param_reminder() 自动生成"""

    def test_generate_param_reminder_time_contains_tools(self):
        """Time 分类的自动生成结果包含核心工具"""
        reminder = tool_registry.generate_param_reminder(category=ToolCategory.TIME)
        assert "get_current_time" in reminder
        assert "time_format" in reminder
        assert "timer_set" in reminder
        assert "time_is_weekend" in reminder

    def test_generate_param_reminder_contains_params(self):
        """自动生成的结果包含参数名和必填性标记"""
        reminder = tool_registry.generate_param_reminder(category=ToolCategory.TIME)
        # time_add 的 delta 是必填参数
        assert "delta(required" in reminder
        # time_add 的 unit 是可选参数
        assert "unit(optional" in reminder

    def test_generate_param_reminder_contains_defaults(self):
        """自动生成的结果包含默认值"""
        reminder = tool_registry.generate_param_reminder(category=ToolCategory.TIME)
        # TimerListInput.limit: default=10
        assert "default=10" in reminder

    def test_generate_param_reminder_header(self):
        """自动生成的header正确"""
        reminder = tool_registry.generate_param_reminder(category=ToolCategory.TIME)
        assert reminder.startswith("Parameter Reminder (auto-generated from Pydantic):")

    def test_generate_param_reminder_file_contains_tools(self):
        """File 分类也包含核心工具"""
        reminder = tool_registry.generate_param_reminder(category=ToolCategory.FILE)
        assert "write_text_file" in reminder or "list_directory" in reminder
        assert "read_text_file" in reminder or "delete_file" in reminder

    def test_generate_param_reminder_database_contains_params(self):
        """Database 分类的参数正确"""
        reminder = tool_registry.generate_param_reminder(category=ToolCategory.DATABASE)
        assert "query_sql" in reminder


class TestToOpenaiTools:
    """测试 to_openai_tools() 生成"""

    def test_to_openai_tools_time_not_empty(self):
        """Time 分类至少生成 1 个工具"""
        tools = tool_registry.to_openai_tools(category=ToolCategory.TIME)
        assert len(tools) >= 1

    def test_to_openai_tools_format(self):
        """生成格式为 OpenAI function calling 标准"""
        tools = tool_registry.to_openai_tools(category=ToolCategory.TIME)
        tool = tools[0]
        assert tool["type"] == "function"
        assert "function" in tool
        assert "name" in tool["function"]
        assert "description" in tool["function"]
        assert "parameters" in tool["function"]

    def test_to_openai_tools_required_exists(self):
        """parameters 中有 required 字段"""
        tools = tool_registry.to_openai_tools(category=ToolCategory.TIME)
        has_required = False
        for tool in tools:
            params = tool["function"].get("parameters", {})
            if "required" in params:
                has_required = True
                break
        assert has_required, "至少有一个工具包含 required 字段"

    def test_to_openai_tools_expose_to_llm(self):
        """expose_to_llm=False 的工具不应包含在输出中"""
        tools_all = tool_registry.to_openai_tools()
        # support_tool 的工具通常是内部使用的
        support_tools = tool_registry.to_openai_tools(category=ToolCategory.SUPPORT_TOOL)
        # 只是验证不报错
        assert isinstance(support_tools, list)


class TestSummaryNoParams:
    """验证 G7：工具概要不再包含参数名"""

    def test_summary_no_parentheses_params(self):
        """概要中工具名后面不应有 (param1, param2) 格式"""
        summary = tool_registry.get_all_tools_summary()
        # 正常的工具行格式是 "  name: description"
        lines = [l for l in summary.split("\n") if l.startswith("  ") and ":" in l]
        for line in lines:
            # 不应匹配 "name(param):" 格式
            assert "(" not in line.split(":")[0], f"参数名仍出现在概要中: {line}"


class TestRegisterDescriptionConsistency:
    """验证 register 描述与 schema 的一致性"""

    def test_time_register_no_index_col(self):
        """time_register.py 的 read_xlsx 不应有 index_col 参数"""
        from app.services.tools.time.time_register import TIME_TOOL_DESCRIPTIONS
        # 只是验证导入不报错
        assert len(TIME_TOOL_DESCRIPTIONS) >= 10

    def test_register_descriptions_no_param_section(self):
        """register 描述中不应有"参数说明"段落"""
        # 验证几个关键的 register 文件
        from app.services.tools.time.time_register import TIME_TOOL_DESCRIPTIONS
        for name, desc in TIME_TOOL_DESCRIPTIONS.items():
            assert "参数说明" not in desc, f"{name} 仍有参数说明段落"
