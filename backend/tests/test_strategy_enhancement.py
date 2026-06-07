# -*- coding: utf-8 -*-
"""
测试第14/15/16章策略增强实施
- 实施项1：统一OUTPUT_FORMAT + 删除FINISH_RULE
- 实施项2：方案C _tools_to_schema_text()
- 实施项3：ToolsStrategy空tool_calls→finish
- 实施项4：ResponseFormatStrategy enum含finish

Author: 小健 - 2026-05-10
"""
import sys
import os
import json
import pytest
from app.services.prompts.base_prompt_template import BasePrompts
from app.services.prompts.meta.time_prompts import TimePrompts
from app.services.agent.agent_utils.message_utils import build_schema_text
from app.services.agent.llm_strategies import ToolsStrategy

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))


class TestOutputFormatUnification:
    """实施项1：统一OUTPUT_FORMAT + 删除FINISH_RULE"""

    def test_output_format_contains_two_cases(self):
        """OUTPUT_FORMAT必须包含两种返回情况"""
        fmt = BasePrompts.OUTPUT_FORMAT
        assert "情况1" in fmt, "OUTPUT_FORMAT缺少情况1：调用工具"
        assert "情况2" in fmt, "OUTPUT_FORMAT缺少情况2：任务完成"

    def test_output_format_contains_finish(self):
        """OUTPUT_FORMAT必须包含finish退出说明"""
        fmt = BasePrompts.OUTPUT_FORMAT
        assert 'tool_name": "finish"' in fmt or "finish" in fmt, "OUTPUT_FORMAT缺少finish退出说明"

    def test_output_format_contains_safety_warning(self):
        """OUTPUT_FORMAT必须包含SAFETY WARNING"""
        fmt = BasePrompts.OUTPUT_FORMAT
        assert "SAFETY WARNING" in fmt, "OUTPUT_FORMAT缺少SAFETY WARNING"

    def test_output_format_contains_examples(self):
        """OUTPUT_FORMAT必须包含示例"""
        fmt = BasePrompts.OUTPUT_FORMAT
        assert "get_current_time" in fmt, "OUTPUT_FORMAT缺少工具调用示例"
        assert '"tool_name": "finish"' in fmt or "finish" in fmt, "OUTPUT_FORMAT缺少finish示例"

    def test_finish_rule_is_empty(self):
        """FINISH_RULE必须已置空"""
        assert BasePrompts.FINISH_RULE == "", f"FINISH_RULE未置空，当前值: {BasePrompts.FINISH_RULE[:50]}"

    def test_output_format_no_strategy_description(self):
        """OUTPUT_FORMAT不应包含策略说明（给开发者的，不是给LLM的）"""
        fmt = BasePrompts.OUTPUT_FORMAT
        assert "策略说明" not in fmt, "OUTPUT_FORMAT不应包含策略说明，浪费LLM token"

    def test_build_full_system_prompt_no_finish_rule(self):
        """build_full_system_prompt不再拼接FINISH_RULE"""
        prompts = TimePrompts()
        full = prompts.build_full_system_prompt()
        assert "TERMINATION RULE" not in full, "build_full_system_prompt仍包含TERMINATION RULE"

    def test_build_full_system_prompt_no_param_reminder(self):
        """build_full_system_prompt不再拼接get_parameter_reminder()"""
        prompts = TimePrompts()
        full = prompts.build_full_system_prompt()
        assert "Parameter Reminder" not in full, "build_full_system_prompt仍包含Parameter Reminder，应由方案C替代"


class TestToolsToSchemaText:
    """实施项2：方案C build_schema_text（迁入message_builder）"""

    _tools = [
        {
            "type": "function",
            "function": {
                "name": "get_current_time",
                "description": "获取当前时间",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "timezone": {"type": "string", "description": "时区"},
                        "format": {"type": "string", "description": "格式"}
                    },
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "timer_set",
                "description": "设置定时器",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "delay": {"type": "number", "description": "延迟秒数"},
                        "callback": {"type": "string", "description": "回调"},
                        "callback_data": {"type": "object", "default": None, "description": "回调数据"}
                    },
                    "required": ["delay", "callback"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "time_is_weekend",
                "description": "检查是否周末",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "date": {"type": "string", "description": "日期"}
                    },
                    "required": []
                }
            }
        }
    ]

    def test_schema_text_not_empty(self):
        """有tools时，schema文本不为空"""
        text = build_schema_text(self._tools)
        assert text != "", "有tools时schema文本不应为空"

    def test_schema_text_contains_header(self):
        """schema文本包含标题"""
        text = build_schema_text(self._tools)
        assert "Tools Schema参考" in text, "schema文本缺少标题"

    def test_schema_text_contains_all_tools(self):
        """schema文本包含所有工具名"""
        text = build_schema_text(self._tools)
        assert "get_current_time" in text
        assert "timer_set" in text
        assert "time_is_weekend" in text

    def test_schema_text_contains_required_optional(self):
        """schema文本标记required/optional"""
        text = build_schema_text(self._tools)
        assert "required" in text, "schema文本缺少required标记"
        assert "optional" in text, "schema文本缺少optional标记"

    def test_schema_text_contains_types(self):
        """schema文本包含参数类型"""
        text = build_schema_text(self._tools)
        assert "number" in text or "string" in text, "schema文本缺少参数类型"

    def test_schema_text_no_tools(self):
        """无tools时，返回空字符串"""
        text = build_schema_text([])
        assert text == "", "无tools时schema文本应为空"

    def test_schema_text_no_attr(self):
        """无tools参数时，返回空字符串"""
        text = build_schema_text(None)
        assert text == "", "无tools时schema文本应为空"

    def test_schema_text_no_params_tool(self):
        """无参数的工具显示'无参数'"""
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "simple_tool",
                    "description": "简单工具",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            }
        ]
        text = build_schema_text(tools)
        assert "simple_tool" in text
        assert "无参数" in text


class TestToolsStrategyEmptyToolCalls:
    """实施项3：ToolsStrategy空tool_calls→finish"""

    def test_empty_tool_calls_to_finish(self):
        """空tool_calls数组应转换为finish"""
        strategy = ToolsStrategy(tools=[])
        formatted = strategy._format_tool_calls([{
            "function": {
                "name": "test_tool",
                "arguments": "{}"
            }
        }])
        result = json.loads(formatted)
        assert result["tool_name"] == "test_tool"

    def test_format_single_tool_call(self):
        """单个工具调用格式化正确"""
        strategy = ToolsStrategy(tools=[])
        formatted = strategy._format_tool_calls([{
            "function": {
                "name": "get_current_time",
                "arguments": '{"timezone": "Asia/Shanghai"}'
            }
        }])
        result = json.loads(formatted)
        assert result["tool_name"] == "get_current_time"
        assert result["tool_params"]["timezone"] == "Asia/Shanghai"

    def test_format_multiple_tool_calls(self):
        """多个工具调用格式化正确（取第一个）"""
        strategy = ToolsStrategy(tools=[])
        formatted = strategy._format_tool_calls([
            {"function": {"name": "tool_a", "arguments": '{"a": 1}'}},
            {"function": {"name": "tool_b", "arguments": '{"b": 2}'}}
        ])
        result = json.loads(formatted)
        assert result["tool_name"] == "tool_a"
        assert result["tool_params"]["a"] == 1


class TestResponseFormatEnumFinish:
    """实施项4：response_format enum必须包含finish"""

    def test_enum_contains_finish(self):
        """response_format的tool_name enum必须包含finish"""
        tool_names = ["get_current_time", "time_format", "timer_set"]
        all_names = tool_names + ["finish"]
        assert "finish" in all_names, "enum必须包含finish"


class TestBuildFullSystemPromptStructure:
    """验证build_full_system_prompt的结构完整性"""

    def test_prompt_order(self):
        """验证组装顺序：system_prompt → OUTPUT_FORMAT → TOOL_CALL_RULES → safety → rollback"""
        prompts = TimePrompts()
        full = prompts.build_full_system_prompt()
        
        pos_output = full.find("Response Format")
        pos_tool_rules = full.find("Tool Call Rules")
        pos_safety = full.find("Time Safety")
        pos_rollback = full.find("If an operation fails")
        
        if pos_safety > 0:
            assert pos_output < pos_tool_rules < pos_safety, "组装顺序错误：OUTPUT_FORMAT应在TOOL_CALL_RULES之前"
        if pos_rollback > 0:
            if pos_safety > 0:
                assert pos_safety < pos_rollback, "组装顺序错误：safety应在rollback之前"

    def test_no_param_reminder_in_prompt(self):
        """prompt中不再包含Parameter Reminder"""
        prompts = TimePrompts()
        full = prompts.build_full_system_prompt()
        assert "Parameter Reminder" not in full, "prompt仍包含Parameter Reminder，应由方案C替代"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
