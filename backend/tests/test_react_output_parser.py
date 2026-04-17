# -*- coding: utf-8 -*-
"""
ReAct输出统一解析器单元测试

测试覆盖：
- 四种type类型：action/answer/implicit/thought_only
- 中英文关键词：Thought/思考、Action/行动、Answer/回答
- 五级降级策略：第0级Markdown、第1级标准JSON、第2级平衡括号、第3级单引号、第4级字段提取
- 边界情况：空字符串、None值、极长文本、特殊字符
- P0工具名兜底匹配
- ToolParser兼容层

Author: 小沈
Date: 2026-04-16
"""

import pytest
from app.services.agent.react_output_parser import (
    parse_react_response,
    _determine_parse_type,
    _parse_action,
    _parse_answer,
    _parse_action_input,
    _extract_by_known_tools,
    _extract_json_with_balanced_braces,
    _extract_key_value_pairs,
    REACT_KEYWORDS,
    KNOWN_TOOLS,
    ToolParser,
)


# =============================================================================
# TestParseReactResponse - 入口函数测试
# =============================================================================

class TestParseReactResponse:
    """测试parse_react_response入口函数"""
    
    def test_empty_string(self):
        """空字符串应返回implicit类型"""
        result = parse_react_response("")
        assert result["type"] == "implicit"
        assert result["tool_name"] is None
        assert result["response"] == ""
    
    def test_none_input(self):
        """None输入应返回implicit类型"""
        result = parse_react_response(None)
        assert result["type"] == "implicit"
        assert result["content"] == "(Implicit) Empty response"
    
    def test_non_string_input(self):
        """非字符串输入应返回implicit类型"""
        result = parse_react_response(123)
        assert result["type"] == "implicit"

    def test_non_string_list_input(self):
        """list输入应安全返回implicit类型"""
        result = parse_react_response(["not", "a", "string"])
        assert result["type"] == "implicit"
        assert result["tool_name"] is None
    
    def test_action_type_returns_all_fields(self):
        """action类型应返回完整字段"""
        result = parse_react_response("Thought: I need to search\nAction: list_directory\nAction Input: {}")
        assert result["type"] == "action"
        assert "tool_name" in result
        assert "tool_params" in result
        assert "thought" in result
        assert "content" in result  # 兼容性字段
        assert "reasoning" in result  # 兼容性字段
        assert result["response"] is None


# =============================================================================
# TestDetermineParseType - 四种类型判断测试
# =============================================================================

class TestDetermineParseType:
    """测试四种类型判断逻辑"""
    
    def test_action_type_english(self):
        """英文Action格式"""
        result = parse_react_response("Thought: I need to search\nAction: list_directory\nAction Input: {}")
        assert result["type"] == "action"
        assert result["tool_name"] == "list_directory"
        assert result["tool_params"] == {}
    
    def test_action_type_chinese(self):
        """中文Action格式"""
        result = parse_react_response("思考: 我需要查询\n行动: list_directory\n工具参数: {}")
        assert result["type"] == "action"
    
    def test_answer_type_english(self):
        """英文Answer格式"""
        result = parse_react_response("Thought: I have the answer\nAnswer: The result is 42")
        assert result["type"] == "answer"
        assert result["response"] == "The result is 42"
    
    def test_answer_type_chinese(self):
        """中文Answer格式"""
        result = parse_react_response("思考: 我有答案了\n回答: 结果是42")
        assert result["type"] == "answer"
        assert result["response"] == "结果是42"
    
    def test_implicit_type_no_keywords(self):
        """无关键词匹配 - 隐式回答"""
        result = parse_react_response("The answer is 42")
        assert result["type"] == "implicit"
        assert result["response"] == "The answer is 42"
    
    def test_thought_only_type(self):
        """只有Thought标记"""
        result = parse_react_response("Thought: I should think about this more")
        assert result["type"] == "thought_only"
        assert "I should think about this more" in result["thought"]
    
    def test_action_priority_over_answer(self):
        """Action优先规则：Action在Answer之前"""
        result = parse_react_response("Thought: Let me check\nAction: read_file\nAction Input: {}\nAnswer: Done")
        assert result["type"] == "action"
        assert result["tool_name"] == "read_file"


# =============================================================================
# TestExtractByKnownTools - P0工具名兜底匹配测试
# =============================================================================

class TestExtractByKnownTools:
    """测试P0工具名兜底匹配"""
    
    def test_known_tool_match(self):
        """匹配已知工具名"""
        result = _extract_by_known_tools("I will list_directory the files")
        assert result is not None
        assert result["tool_name"] == "list_directory"
    
    def test_known_tool_with_path(self):
        """匹配工具名并提取路径参数"""
        result = _extract_by_known_tools("Let me read_file C:\\Users\\test\\file.txt")
        assert result is not None
        assert result["tool_name"] == "read_file"
        assert "path" in result["tool_params"]
    
    def test_no_known_tool_match(self):
        """无匹配返回None"""
        result = _extract_by_known_tools("Hello world")
        assert result is None
    
    def test_known_tool_case_insensitive(self):
        """大小写不敏感"""
        result = _extract_by_known_tools("I will LIST_DIRECTORY the files")
        assert result is not None
        assert result["tool_name"] == "list_directory"
    
    def test_known_tool_in_determine_parse_type(self):
        """工具名兜底在_determine_parse_type中作为pre-check"""
        # 即使没有Action关键词，只要包含已知工具名就应返回action
        result = parse_react_response("I need to list_directory the files")
        assert result["type"] == "action"
        assert result["tool_name"] == "list_directory"


# =============================================================================
# TestParseAction - Action解析测试
# =============================================================================

class TestParseAction:
    """测试_parse_action函数"""
    
    def test_basic_action(self):
        """基本Action格式"""
        result = parse_react_response("Thought: I need to search\nAction: some_tool\nAction Input: {}")
        assert result["type"] == "action"
        assert result["tool_name"] == "some_tool"
        assert result["thought"] == "I need to search"
    
    def test_action_with_json_params(self):
        """Action带JSON参数"""
        result = parse_react_response("Thought: Search files\nAction: search_files\nAction Input: {\"path\": \"/home\"}")
        assert result["type"] == "action"
        assert result["tool_name"] == "search_files"
        assert result["tool_params"] == {"path": "/home"}
    
    def test_action_without_thought(self):
        """Action无Thought前缀"""
        result = parse_react_response("Action: read_file\nAction Input: {}")
        assert result["type"] == "action"
        assert result["tool_name"] == "read_file"
    
    def test_action_without_input(self):
        """Action无Action Input"""
        result = parse_react_response("Thought: Done\nAction: finish")
        assert result["type"] == "action"
        assert result["tool_name"] == "finish"
        assert result["tool_params"] == {}

    def test_action_empty_tool_name_not_crash(self):
        """Action为空时不应抛异常"""
        result = parse_react_response("Thought: Done\nAction:\nAction Input: {}")
        assert result["type"] == "action"
        assert result["tool_name"] == ""
        assert result["tool_params"] == {}


# =============================================================================
# TestParseThoughtOnly - 纯思考提取测试（14.5节要求）
# =============================================================================

class TestParseThoughtOnly:
    """测试_parse_thought_only独立函数"""
    
    def test_basic_thought_only(self):
        """基本thought_only格式"""
        result = parse_react_response("Thought: I need to think about this")
        assert result["type"] == "thought_only"
        assert result["thought"] == "I need to think about this"
        assert result["tool_name"] is None
        assert result["tool_params"] is None
        assert result["response"] is None
    
    def test_thought_multiline(self):
        """多行thought内容"""
        text = "Thought: First line\nSecond line\nThird line"
        result = parse_react_response(text)
        assert result["type"] == "thought_only"
        assert "First line" in result["thought"]
        assert "Second line" in result["thought"]
    
    def test_thought_chinese(self):
        """中文thought内容"""
        result = parse_react_response("思考: 我需要分析一下文件结构")
        assert result["type"] == "thought_only"
        assert "分析" in result["thought"]
    
    def test_thought_compatibility_fields(self):
        """thought_only包含兼容性字段"""
        result = parse_react_response("Thought: reasoning content")
        assert result["content"] == result["thought"]
        assert result["reasoning"] == result["thought"]


# =============================================================================
# TestParseAnswer - Answer解析测试
# =============================================================================

class TestParseAnswer:
    """测试_parse_answer函数"""
    
    def test_basic_answer(self):
        """基本Answer格式"""
        result = parse_react_response("Thought: I found it\nAnswer: The file exists")
        assert result["type"] == "answer"
        assert result["response"] == "The file exists"
        assert result["thought"] == "I found it"
    
    def test_answer_without_thought(self):
        """Answer无Thought前缀"""
        result = parse_react_response("Answer: Hello world")
        assert result["type"] == "answer"
        assert result["response"] == "Hello world"
        assert result["thought"] == ""
    
    def test_answer_multiline(self):
        """Answer多行回答"""
        result = parse_react_response("Thought: Done\nAnswer: Line 1\nLine 2\nLine 3")
        assert result["type"] == "answer"
        assert "Line 1" in result["response"]
        assert "Line 2" in result["response"]


# =============================================================================
# TestParseActionInput - 五级降级策略测试
# =============================================================================

class TestParseActionInput:
    """测试_parse_action_input五级降级策略"""
    
    def test_level1_standard_json(self):
        """第1级：标准JSON解析"""
        result = _parse_action_input('{"path": "/home", "recursive": true}')
        assert result == {"path": "/home", "recursive": True}
    
    def test_level0_markdown_removal(self):
        """第0级：Markdown代码块去除"""
        result = _parse_action_input('```json\n{"path": "/home"}\n```')
        assert result == {"path": "/home"}
    
    def test_level0_markdown_without_json_tag(self):
        """第0级：无json标签的Markdown"""
        result = _parse_action_input('```\n{"path": "/home"}\n```')
        assert result == {"path": "/home"}
    
    def test_level3_single_quotes(self):
        """第3级：单引号替换"""
        result = _parse_action_input("{'path': '/home'}")
        assert result == {"path": "/home"}
    
    def test_level4_field_extraction(self):
        """第4级：截断JSON字段提取"""
        result = _parse_action_input('{"tool_name": "read_file", "tool_params": {"path')
        assert result["tool_name"] == "read_file"
    
    def test_level5_key_value_fallback(self):
        """第5级：key:value兜底"""
        result = _parse_action_input('path: /home, recursive: true')
        assert result.get("path") == "/home"
        assert result.get("recursive") is True
    
    def test_empty_input(self):
        """空输入返回空字典"""
        result = _parse_action_input("")
        assert result == {}
    
    def test_none_input(self):
        """None输入返回空字典"""
        result = _parse_action_input(None)
        assert result == {}


# =============================================================================
# TestExtractJsonWithBalancedBraces - 平衡括号匹配测试
# =============================================================================

class TestExtractJsonWithBalancedBraces:
    """测试_extract_json_with_balanced_braces函数"""
    
    def test_complete_json(self):
        """完整JSON提取"""
        json_text, content_before = _extract_json_with_balanced_braces('Some text {"key": "value"} more text')
        assert json_text == '{"key": "value"}'
        assert content_before == "Some text"
    
    def test_truncated_json(self):
        """截断JSON检测"""
        json_text, content_before = _extract_json_with_balanced_braces('Some text {"key": "val')
        assert json_text == '{"key": "val'
        assert content_before == "Some text"
    
    def test_no_json(self):
        """无JSON返回None"""
        json_text, content_before = _extract_json_with_balanced_braces("No JSON here")
        assert json_text is None
        assert content_before == "No JSON here"
    
    def test_nested_json(self):
        """嵌套JSON提取"""
        json_text, content_before = _extract_json_with_balanced_braces('{"outer": {"inner": "value"}}')
        assert json_text == '{"outer": {"inner": "value"}}'


# =============================================================================
# TestExtractKeyValuePairs - key:value提取测试
# =============================================================================

class TestExtractKeyValuePairs:
    """测试_extract_key_value_pairs函数"""
    
    def test_basic_key_value(self):
        """基本key:value提取"""
        result = _extract_key_value_pairs('name: John, age: 30')
        assert result.get("name") == "John"
        assert result.get("age") == 30
    
    def test_boolean_values(self):
        """布尔值转换"""
        result = _extract_key_value_pairs('active: true, deleted: false')
        assert result.get("active") is True
        assert result.get("deleted") is False
    
    def test_float_values(self):
        """浮点数值转换"""
        result = _extract_key_value_pairs('score: 3.14')
        assert result.get("score") == 3.14
    
    def test_string_values(self):
        """字符串值"""
        result = _extract_key_value_pairs('name: John')
        assert result.get("name") == "John"


# =============================================================================
# TestReactKeywords - 关键词正则测试
# =============================================================================

class TestReactKeywords:
    """测试REACT_KEYWORDS关键词映射"""
    
    def test_thought_keywords(self):
        """Thought关键词匹配"""
        import re
        assert re.search(REACT_KEYWORDS["thought"], "Thought: hello", re.IGNORECASE)
        assert re.search(REACT_KEYWORDS["thought"], "思考: hello", re.IGNORECASE)
        assert re.search(REACT_KEYWORDS["thought"], "推理: hello", re.IGNORECASE)
    
    def test_action_keywords(self):
        """Action关键词匹配 - 覆盖设计文档步骤1.1全部模式"""
        import re
        # 英文模式
        assert re.search(REACT_KEYWORDS["action"], "Action: hello", re.IGNORECASE)
        # 中文直接模式
        assert re.search(REACT_KEYWORDS["action"], "行动: hello", re.IGNORECASE)
        assert re.search(REACT_KEYWORDS["action"], "工具调用: hello", re.IGNORECASE)
        # 中文动词+空格+冒号模式（设计文档14.0分析新增）
        assert re.search(REACT_KEYWORDS["action"], "调用 : list_directory", re.IGNORECASE)
        assert re.search(REACT_KEYWORDS["action"], "使用 : read_file", re.IGNORECASE)
        assert re.search(REACT_KEYWORDS["action"], "执行 : write_file", re.IGNORECASE)
        # 工具/函数为模式
        assert re.search(REACT_KEYWORDS["action"], "工具为: list_directory", re.IGNORECASE)
        assert re.search(REACT_KEYWORDS["action"], "函数为: read_file", re.IGNORECASE)
    
    def test_answer_keywords(self):
        """Answer关键词匹配"""
        import re
        assert re.search(REACT_KEYWORDS["answer"], "Answer: hello", re.IGNORECASE)
        assert re.search(REACT_KEYWORDS["answer"], "回答: hello", re.IGNORECASE)
        assert re.search(REACT_KEYWORDS["answer"], "最终答案: hello", re.IGNORECASE)
        assert re.search(REACT_KEYWORDS["answer"], "结论: hello", re.IGNORECASE)
    
    def test_known_tools_not_empty(self):
        """KNOWN_TOOLS列表非空"""
        assert len(KNOWN_TOOLS) > 0
        assert "list_directory" in KNOWN_TOOLS
        assert "read_file" in KNOWN_TOOLS


# =============================================================================
# TestEdgeCases - 边界情况测试
# =============================================================================

class TestEdgeCases:
    """测试边界情况"""
    
    def test_very_long_text(self):
        """极长文本处理"""
        long_text = "A" * 10000 + "\nAction: read_file\nAction Input: {}"
        result = parse_react_response(long_text)
        assert result["type"] == "action"
        assert result["tool_name"] == "read_file"
    
    def test_special_characters(self):
        """特殊字符处理"""
        result = parse_react_response("Thought: Special chars: @#$%\nAction: read_file\nAction Input: {}")
        assert result["type"] == "action"
    
    def test_mixed_chinese_english(self):
        """中英文混合"""
        result = parse_react_response("思考: I need to search\n行动: list_directory\n工具参数: {}")
        assert result["type"] == "action"
    
    def test_whitespace_only(self):
        """纯空白字符"""
        result = parse_react_response("   \n\t  ")
        assert result["type"] == "implicit"
    
    def test_newlines_in_action_input(self):
        """Action Input中含换行符"""
        result = parse_react_response('Action: write_file\nAction Input: {"content": "line1\nline2"}')
        assert result["type"] == "action"
        assert result["tool_name"] == "write_file"


# =============================================================================
# TestToolParserCompatibility - ToolParser兼容层测试
# =============================================================================

class TestToolParserCompatibility:
    """测试ToolParser兼容层"""
    
    def test_action_to_old_format(self):
        """action类型转换为旧格式"""
        result = ToolParser.parse_response("Thought: Search\nAction: list_directory\nAction Input: {}")
        assert result["tool_name"] == "list_directory"
        assert result["content"]  # content字段存在
        assert "thought" in result
    
    def test_answer_to_old_format(self):
        """answer类型转换为旧格式（tool_name=finish）"""
        result = ToolParser.parse_response("Thought: Done\nAnswer: The result is 42")
        assert result["tool_name"] == "finish"
        assert result["content"] == "The result is 42"
    
    def test_implicit_to_old_format(self):
        """implicit类型转换为旧格式（tool_name=finish）"""
        result = ToolParser.parse_response("Hello world")
        assert result["tool_name"] == "finish"
    
    def test_thought_only_to_old_format(self):
        """thought_only类型转换为旧格式（tool_name=finish）"""
        result = ToolParser.parse_response("Thought: I should think")
        assert result["tool_name"] == "finish"
    
    def test_empty_to_old_format(self):
        """空输入转换为旧格式"""
        result = ToolParser.parse_response("")
        assert result["tool_name"] == "finish"
    
    def test_error_handling(self):
        """错误处理（ValueError异常时）"""
        # 正常情况下不应抛ValueError，但测试兼容层能处理
        result = ToolParser.parse_response("Test content")
        assert "tool_name" in result
        assert "content" in result
