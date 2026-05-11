"""
测试 react_output_parser.py 的 2026-05-11 新增修复

1. parse_react_response 显式type(parse_error/answer)优先判断，避免被tool_name误判为action
2. _extract_json_block 中文引号(\u201c\u201d)修复

作者：小健
创建时间：2026-05-11
"""

import pytest
import json
from app.services.agent.react_output_parser import parse_react_response, _extract_json_block


# =====================================================================
# 测试1: parse_react_response 显式type优先判断
# =====================================================================

class TestParseReactResponseExplicitType:
    """测试显式type字段(parse_error/answer)优先于tool_name判断"""

    def test_parse_error_not_misread_as_action(self):
        """TC-PARSER-001: type=parse_error不应被误判为action"""
        input_data = json.dumps({
            "type": "parse_error",
            "error": "解析错误",
            "content": "some content",
            "thought": "thinking",
            "reasoning": "reasoning text"
        })
        result = parse_react_response(input_data)
        assert result["type"] == "parse_error"
        assert result["tool_name"] is None
        assert result["tool_params"] is None

    def test_parse_error_with_tool_name_coexistence(self):
        """TC-PARSER-002: type=parse_error与tool_name共存时parse_error优先"""
        input_data = json.dumps({
            "type": "parse_error",
            "error": "err",
            "tool_name": "some_tool",
            "tool_params": {"a": 1}
        })
        result = parse_react_response(input_data)
        assert result["type"] == "parse_error"
        assert result["tool_name"] is None

    def test_parse_error_fields_mapping(self):
        """TC-PARSER-003: parse_error返回字段映射正确"""
        input_data = json.dumps({
            "type": "parse_error",
            "error": "JSON格式错误",
            "content": "原始内容",
            "thought": "思考过程",
            "reasoning": "推理过程"
        })
        result = parse_react_response(input_data)
        assert result["error"] == "JSON格式错误"
        assert result["thought"] == "原始内容"
        assert result["content"] == "原始内容"
        assert result["reasoning"] == "推理过程"
        assert result["response"] == "原始内容"

    def test_answer_not_misread_as_action(self):
        """TC-PARSER-004: type=answer优先返回，不被tool_name误判"""
        input_data = json.dumps({
            "type": "answer",
            "thought": "我完成了",
            "content": "最终答案",
            "tool_name": "some_tool",
            "tool_params": {"a": 1}
        })
        result = parse_react_response(input_data)
        assert result["type"] == "answer"
        assert result["tool_name"] is None
        assert result["tool_params"] is None

    def test_answer_fields_mapping(self):
        """TC-PARSER-005: answer返回字段映射正确"""
        input_data = json.dumps({
            "type": "answer",
            "thought": "思考",
            "content": "内容",
            "reasoning": "推理",
            "response": "最终回复"
        })
        result = parse_react_response(input_data)
        assert result["thought"] == "思考"
        assert result["content"] == "内容"
        assert result["reasoning"] == "推理"
        assert result["response"] == "最终回复"

    def test_answer_response_fallback_to_content(self):
        """TC-PARSER-006: answer的response缺省回退到content"""
        input_data = json.dumps({
            "type": "answer",
            "thought": "思考",
            "content": "内容",
        })
        result = parse_react_response(input_data)
        assert result["response"] == "内容"

    def test_no_explicit_type_with_tool_name_is_action(self):
        """TC-PARSER-007: 无显式type但有tool_name→正常action"""
        input_data = json.dumps({
            "tool_name": "read_file",
            "tool_params": {"file_path": "/tmp/test.txt"},
            "thought": "需要读取文件"
        })
        result = parse_react_response(input_data)
        assert result["type"] == "action"
        assert result["tool_name"] == "read_file"

    def test_no_explicit_type_with_action_is_action(self):
        """TC-PARSER-008: 无显式type但有action字段→正常action(旧格式)"""
        input_data = json.dumps({
            "action": "write_file",
            "action_input": {"file_path": "/tmp/test.txt"},
            "thought": "需要写入"
        })
        result = parse_react_response(input_data)
        assert result["type"] == "action"
        assert result["tool_name"] == "write_file"


# =====================================================================
# 测试2: _extract_json_block 中文引号修复
# =====================================================================

class TestExtractJsonBlockChineseQuotes:
    """测试_extract_json_block中文引号(\u201c\u201d)修复"""

    def test_chinese_double_quotes_in_value(self):
        """TC-EXTRACT-001: value中含配对中文双引号"""
        content = '{"tool_name": "read_file", "thought": "查看\u201c穆里奇\u201d的数据"}'
        result = _extract_json_block(content)
        assert result is not None
        assert result["tool_name"] == "read_file"

    def test_chinese_quotes_in_mixed_text(self):
        """TC-EXTRACT-002: 混合前言文本+含中文引号JSON"""
        content = '这是前言\n\n{"tool_name": "read_file", "tool_params": {"file_path": "/tmp/test.txt"}, "thought": "查看\u201c穆里奇\u201d的数据"}'
        result = _extract_json_block(content)
        assert result is not None
        assert result["tool_name"] == "read_file"

    def test_chinese_quotes_removed_fallback(self):
        """TC-EXTRACT-003: 中文引号去掉后能解析"""
        content = '{"tool_name": "write_file", "thought": "写入\u201c重要\u201d内容"}'
        result = _extract_json_block(content)
        assert result is not None
        assert result["tool_name"] == "write_file"

    def test_normal_json_still_works(self):
        """TC-EXTRACT-004: 正常JSON(无中文引号)仍然正常"""
        content = '{"tool_name": "delete_file", "tool_params": {"file_path": "/tmp/a.txt"}}'
        result = _extract_json_block(content)
        assert result is not None
        assert result["tool_name"] == "delete_file"


# =====================================================================
# 测试3: _extract_json_block ToolsStrategy场景
# =====================================================================

class TestExtractJsonBlockToolsStrategyScenario:
    """测试_extract_json_block在ToolsStrategy中的使用场景"""

    def test_prefix_text_with_tool_name_json(self):
        """TC-STRAT-001: 前言文本+含tool_name的JSON"""
        content = '我来帮你查看文件内容\n\n{"tool_name": "read_file", "tool_params": {"file_path": "D:/test.txt"}, "thought": "读取文件"}'
        result = _extract_json_block(content)
        assert result is not None
        assert "tool_name" in result
        assert result["tool_name"] == "read_file"

    def test_pure_text_no_json_returns_none(self):
        """TC-STRAT-002: 纯文本无JSON→None"""
        result = _extract_json_block("这是纯文本回复，没有JSON")
        assert result is None

    def test_empty_string_returns_none(self):
        """TC-STRAT-003: 空字符串→None"""
        result = _extract_json_block("")
        assert result is None

    def test_none_input_returns_none(self):
        """TC-STRAT-004: None输入→None"""
        result = _extract_json_block(None)
        assert result is None

    def test_extracted_dict_has_tool_name_for_tools_strategy(self):
        """TC-STRAT-005: 提取结果含tool_name字段(ToolsStrategy判断条件)"""
        content = '好的\n{"tool_name": "search_files", "tool_params": {"pattern": "*.py"}}'
        result = _extract_json_block(content)
        assert result is not None
        assert isinstance(result, dict)
        assert "tool_name" in result

    def test_extracted_without_tool_name(self):
        """TC-STRAT-006: 提取结果不含tool_name(如answer/finish)"""
        content = '{"type": "answer", "content": "任务完成"}'
        result = _extract_json_block(content)
        assert result is not None
        assert isinstance(result, dict)
        # 不含tool_name，ToolsStrategy不会走tool_name分支
