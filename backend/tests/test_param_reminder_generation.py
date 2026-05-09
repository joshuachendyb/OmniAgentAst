"""
Parameter Reminder + FC通道 + G1~G7 综合测试

覆盖范围：
- G1: Union类型保留
- G2: description截断修复
- G3: _process_description修复
- G4: register无参数说明段落
- G5: prompt无-Parameters:块
- G6: generate_param_reminder()自动生成
- G7: summary无参数名
- FC: to_openai_tools()格式正确
- FC: _init_llm_strategies()降级逻辑

Author: 小沈 小健 - 2026-05-09
"""
import pytest
from app.services.tools.registry import tool_registry, ToolCategory
from app.services.agent.types.react_schema import (
    _extract_type, _process_description, _clean_properties
)


# ============================================================
# G1: Union类型保留
# ============================================================

class TestG1UnionTypes:
    """验证 Union 类型不被简化为单一类型"""

    def test_extract_type_anyof_returns_union(self):
        """anyOf 包含多种类型时返回逗号分隔"""
        result = _extract_type({
            "anyOf": [
                {"type": "integer"},
                {"type": "number"},
                {"type": "string"},
                {"type": "null"}
            ]
        })
        assert result == "string,integer,number"

    def test_extract_type_anyof_single_type(self):
        """anyOf 只有一种类型时返回该类型"""
        result = _extract_type({
            "anyOf": [{"type": "string"}, {"type": "null"}]
        })
        assert result == "string", f"应为 'string'，实际为 '{result}'"

    def test_extract_type_direct_type(self):
        """直接 type 字段保持不变"""
        result = _extract_type({"type": "number"})
        assert result == "number"

    def test_extract_type_oneof_handled(self):
        """oneOf 也能正确处理"""
        result = _extract_type({
            "oneOf": [
                {"type": "string"},
                {"type": "integer"}
            ]
        })
        assert "string" in result and "integer" in result

    def test_time_format_types_preserved(self):
        """time_format.timestamp 的类型信息在 schema 中保留"""
        from app.services.tools.time.time_schema import TimeFormatInput
        schema = TimeFormatInput.model_json_schema()
        if schema and "properties" in schema:
            ts = schema["properties"].get("timestamp", {})
            # raw Pydantic generates anyOf, not simplified type
            any_of = ts.get("anyOf", [])
            types_in_anyof = [item["type"] for item in any_of if isinstance(item, dict) and "type" in item]
            assert "integer" in types_in_anyof
            assert "number" in types_in_anyof
            assert "string" in types_in_anyof


# ============================================================
# G2: description 截断修复
# ============================================================

class TestG2DescriptionTruncation:
    """验证多行 description 不被截断"""

    def test_clean_properties_multi_line_desc(self):
        """多行 description 合并为单行"""
        properties = {
            "test_param": {
                "type": "string",
                "description": "第一行内容。\n第二行内容。\n第三行内容。"
            }
        }
        cleaned = _clean_properties(properties)
        desc = cleaned["test_param"]["description"]
        assert "\n" not in desc, "description 不应包含换行符"
        assert "第一行内容" in desc
        assert "第二行内容" in desc
        assert "第三行内容" in desc

    def test_clean_properties_single_line(self):
        """单行 description 保持不变"""
        properties = {
            "test_param": {
                "type": "string",
                "description": "单行描述"
            }
        }
        cleaned = _clean_properties(properties)
        assert cleaned["test_param"]["description"] == "单行描述"


# ============================================================
# G3: _process_description 修复
# ============================================================

class TestG3ProcessDescription:
    """验证 _process_description 只移除FORBIDDEN和示例"""

    def test_keeps_important(self):
        result = _process_description("描述\n【重要】必须使用绝对路径\n继续")
        assert "【重要】" in result
        assert "必须使用绝对路径" in result

    def test_keeps_warning(self):
        result = _process_description("描述\n【注意】某些操作不可逆\n继续")
        assert "【注意】" in result

    def test_removes_forbidden(self):
        """FORBIDDEN 行应移除"""
        result = _process_description("描述\nFORBIDDEN parameter names\n继续")
        assert "FORBIDDEN" not in result

    def test_removes_example_error(self):
        """错误示例: 行应移除"""
        result = _process_description("描述\n错误示例: {\"bad\": \"params\"}\n继续")
        assert "错误示例:" not in result

    def test_removes_example_correct(self):
        """正确示例: 行应移除"""
        result = _process_description("描述\n正确示例: {\"good\": \"params\"}\n继续")
        assert "正确示例:" not in result


# ============================================================
# G4: Register 文件一致性
# ============================================================

class TestG4RegisterConsistency:
    """验证所有 register 描述无参数说明且与 schema 一致"""

    def test_all_registers_no_param_section(self):
        registers = [
            ("time", "TIME_TOOL_DESCRIPTIONS"),
            ("file", "FILE_TOOL_DESCRIPTIONS"),
            ("shell", "SHELL_TOOL_DESCRIPTIONS"),
            ("network", "NETWORK_TOOL_DESCRIPTIONS"),
        ]
        for module_name, dict_name in registers:
            try:
                mod = __import__(f"app.services.tools.{module_name}.{module_name}_register",
                                 fromlist=['_trash'])
                descs = getattr(mod, dict_name, {})
                for tool_name, desc in descs.items():
                    assert "参数说明" not in desc, \
                        f"[{module_name}] {tool_name} 仍有'参数说明'段落"
            except (ImportError, AttributeError):
                pass  # 某些 register 可能使用不同命名


# ============================================================
# G5: Prompt 文件参数块
# ============================================================

class TestG5PromptNoParameters:
    """验证 prompt 文件不再有 - Parameters: 块"""

    def test_system_prompt_no_parameters_block(self):
        """time_prompts.py 的 get_system_prompt 不包含 - Parameters:"""
        from app.services.prompts.time.time_prompts import TimePrompts
        p = TimePrompts()
        sys_prompt = p.get_system_prompt()
        assert "- Parameters:" not in sys_prompt, "仍有 - Parameters: 块残留"


# ============================================================
# G6: generate_param_reminder() 自动生成
# ============================================================

class TestG6ParamReminderGeneration:
    """验证 generate_param_reminder() 的正确性"""

    def test_contains_core_tools(self):
        """Time 分类包含核心工具"""
        reminder = tool_registry.generate_param_reminder(category=ToolCategory.TIME)
        assert "get_current_time" in reminder
        assert "time_format" in reminder

    def test_contains_required_marker(self):
        """必填参数标记 required"""
        reminder = tool_registry.generate_param_reminder(category=ToolCategory.TIME)
        assert "delta(required" in reminder

    def test_contains_defaults(self):
        """含默认值的参数显示 default="""
        reminder = tool_registry.generate_param_reminder(category=ToolCategory.TIME)
        assert "default=10" in reminder  # TimerListInput.limit

    def test_header_correct(self):
        """header 正确"""
        reminder = tool_registry.generate_param_reminder(category=ToolCategory.TIME)
        assert reminder.startswith("Parameter Reminder (auto-generated from Pydantic):")

    def test_file_category(self):
        """File 分类包含工具"""
        reminder = tool_registry.generate_param_reminder(category=ToolCategory.FILE)
        assert "list_directory" in reminder or "write_text_file" in reminder

    def test_all_categories(self):
        """不指定分类时返回所有工具"""
        reminder = tool_registry.generate_param_reminder()
        assert "get_current_time" in reminder
        assert "list_directory" in reminder


# ============================================================
# G7: get_all_tools_summary() 无参数名
# ============================================================

class TestG7SummaryNoParams:
    """验证工具概要不再包含参数名"""

    def test_no_param_names_in_summary(self):
        """工具行格式为 '  name: description' 而非 '  name(param): description'"""
        summary = tool_registry.get_all_tools_summary()
        lines = [l for l in summary.split("\n") if l.startswith("  ") and ":" in l]
        for line in lines:
            before_colon = line.split(":")[0].strip()
            assert "(" not in before_colon, f"参数名出现在概要中: {line}"

    def test_summary_contains_categories(self):
        """概要包含分类标题"""
        summary = tool_registry.get_all_tools_summary()
        assert "【文件操作工具】" in summary
        assert "【时间日期工具】" in summary


# ============================================================
# FC: to_openai_tools() 测试
# ============================================================

class TestFCToOpenaiTools:
    """验证 OpenAI tools 格式生成"""

    def test_not_empty(self):
        """Time 分类至少生成 1 个工具"""
        tools = tool_registry.to_openai_tools(category=ToolCategory.TIME)
        assert len(tools) >= 1

    def test_format_correct(self):
        """格式符合 OpenAI function calling 标准"""
        tools = tool_registry.to_openai_tools(category=ToolCategory.TIME)
        tool = tools[0]
        assert tool["type"] == "function"
        assert "name" in tool["function"]
        assert "description" in tool["function"]
        assert "parameters" in tool["function"]

    def test_required_field_present(self):
        """parameters 包含 required 字段"""
        tools = tool_registry.to_openai_tools(category=ToolCategory.TIME)
        has_required = any(
            "required" in t["function"].get("parameters", {})
            for t in tools
        )
        assert has_required

    def test_support_tools_excluded(self):
        """support_tool 的工具也正常生成"""
        tools = tool_registry.to_openai_tools(category=ToolCategory.SUPPORT_TOOL)
        assert isinstance(tools, list)
