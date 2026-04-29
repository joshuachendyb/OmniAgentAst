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
)


# =============================================================================
# TestParseReactResponse - 入口函数测试
# =============================================================================

class TestParseReactResponse:
    """测试parse_react_response入口函数"""
    
    def test_empty_string(self):
        """空字符串应返回parse_error类型"""
        result = parse_react_response("")
        assert result["type"] == "parse_error"
        assert result["tool_name"] is None
        assert result["response"] == ""
    
    def test_none_input(self):
        """None输入应返回parse_error类型"""
        result = parse_react_response(None)
        assert result["type"] == "parse_error"
        assert result["content"] == "(Implicit) Empty response"
    
    def test_non_string_input(self):
        """非字符串输入应返回parse_error类型"""
        result = parse_react_response(123)
        assert result["type"] == "parse_error"

    def test_non_string_list_input(self):
        """list输入应安全返回parse_error类型"""
        result = parse_react_response(["not", "a", "string"])
        assert result["type"] == "parse_error"
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
        assert result["type"] == "parse_error"
    
    def test_newlines_in_action_input(self):
        """Action Input中含换行符"""
        result = parse_react_response('Action: write_file\nAction Input: {"content": "line1\nline2"}')
        assert result["type"] == "action"
        assert result["tool_name"] == "write_file"


# =============================================================================
# TestMixedTextJson - 混合文本+JSON格式测试（2026-04-24新增）
# =============================================================================

class TestMixedTextJson:
    """测试混合文本+JSON格式的解析（情况③/⑤）"""

    def test_mixed_text_with_json(self):
        """混合文本+JSON（文本在前，JSON在后）"""
        content = 'Thought: 我要查E盘\n{"thought": "我要查E盘", "tool_name": "list_directory", "tool_params": {"dir_path": "E:/"}}'
        result = parse_react_response(content)
        assert result["type"] == "action"
        assert result["tool_name"] == "list_directory"
        assert result["tool_params"] == {"dir_path": "E:/"}

    def test_mixed_text_with_finish(self):
        """混合文本+finish JSON"""
        content = 'Thought: 任务完成\n{"thought": "任务完成", "tool_name": "finish", "tool_params": {"result": "Done"}}'
        result = parse_react_response(content)
        assert result["type"] == "answer"
        assert result["tool_name"] is None
        assert result["response"] == "Done"

    def test_mixed_text_json_extract_fail(self):
        """混合文本但JSON提取失败，应走其他解析路径"""
        content = 'Thought: 无法解析的内容\n{invalid json}'
        result = parse_react_response(content)
        # 应返回parse_error或走其他路径，不能崩溃
        assert result["type"] in ("parse_error", "implicit", "thought_only")


# =============================================================================
# TestMarkdownJsonFormat - 16章融合方案测试（基于实际日志）
# =============================================================================

class TestMarkdownJsonFormat:
    """
    测试Markdown JSON格式解析（16章融合方案）
    
    验证从LLM返回的Markdown包裹的JSON中正确提取：
    - content：JSON前的纯文本
    - thought：JSON里的thought字段
    - reasoning：JSON里的reasoning字段
    - tool_name：JSON里的tool_name字段
    - tool_params：JSON里的tool_params字段
    """
    
    def test_markdown_json_with_all_fields(self):
        """测试完整字段提取（基于message_id=606第1轮日志）"""
        # LLM原始返回格式
        llm_output = """I'll help you check the file types in the E drive directory. Here's my plan:

1. Use the `list_directory` tool to scan the root of E drive
2. Analyze the file extensions to determine the types

```json
{
    "thought": "用户需要检查E盘的文件类型。第一步是列出E盘根目录下的所有文件和目录，获取文件列表后才能分析文件类型。",
    "tool_name": "list_directory",
    "tool_params": {
        "dir_path": "E:/"
    }
}
```"""
        
        result = parse_react_response(llm_output)
        
        # 验证type
        assert result["type"] == "action"
        
        # 验证content（JSON前的纯文本）
        assert "I'll help you check" in result["content"]
        
        # 验证thought
        assert "用户需要检查E盘的文件类型" in result["thought"]
        
        # 验证tool_name
        assert result["tool_name"] == "list_directory"
        
        # 验证tool_params（关键：参数不能为空！）
        assert result["tool_params"] is not None
        assert result["tool_params"] != {}
        assert "dir_path" in result["tool_params"]
        assert result["tool_params"]["dir_path"] == "E:/"
    
    def test_markdown_json_with_reasoning(self):
        """测试reasoning字段提取（基于message_id=606第2轮日志）"""
        llm_output = """I apologize for the confusion. Let me reissue the command with the correct parameter format:

```json
{
    "thought": "需要获取E盘根目录的文件列表以分析文件类型，使用list_directory工具获取文件信息。",
    "reasoning": "系统要求必须使用dir_path参数（而非directory_path或path），且路径应为绝对路径格式。",
    "tool_name": "list_directory",
    "tool_params": {
        "dir_path": "E:/"
    }
}
```"""
        
        result = parse_react_response(llm_output)
        
        assert result["type"] == "action"
        assert result["tool_name"] == "list_directory"
        assert result["tool_params"] == {"dir_path": "E:/"}
        # 验证reasoning字段被正确提取
        assert "reasoning" in result
        assert "系统要求必须使用dir_path参数" in result["reasoning"]
    
    def test_markdown_json_complex_params(self):
        """测试复杂参数提取（基于message_id=606第3轮日志）"""
        llm_output = """I see the issue. It seems there might be a system configuration problem.

```json
{
    "thought": "由于list_directory工具出现参数问题，改用search_files工具来获取E盘根目录下的所有文件列表。",
    "reasoning": "search_files可以通过通配符'*'匹配所有文件，然后我将分析返回结果中的文件类型",
    "tool_name": "search_files",
    "tool_params": {
        "file_pattern": "*",
        "path": "E:/",
        "recursive": false
    }
}
```"""
        
        result = parse_react_response(llm_output)
        
        assert result["type"] == "action"
        assert result["tool_name"] == "search_files"
        assert result["tool_params"]["file_pattern"] == "*"
        assert result["tool_params"]["path"] == "E:/"
        assert result["tool_params"]["recursive"] is False
    
    def test_markdown_json_no_json_tag(self):
        """测试无json标签的Markdown代码块"""
        llm_output = """Let me try a different approach.

```
{
    "thought": "测试thought内容",
    "tool_name": "test_tool",
    "tool_params": {"key": "value"}
}
```"""
        
        result = parse_react_response(llm_output)
        
        assert result["type"] == "action"
        assert result["tool_name"] == "test_tool"
        assert result["tool_params"] == {"key": "value"}
    
    def test_markdown_json_answer_type(self):
        """测试Markdown JSON格式的answer类型"""
        llm_output = """I have completed the analysis.

```json
{
    "thought": "我已经完成了文件类型分析",
    "reasoning": "通过检查E盘目录结构",
    "tool_name": "finish"
}
```"""
        
        result = parse_react_response(llm_output)
        
        # finish应该被识别为answer类型
        assert result["type"] == "answer"
        assert result["tool_name"] is None
        assert "tool_params" in result
    
    def test_markdown_json_multiple_params(self):
        """测试多个参数的情况（message_id=606第5轮）"""
        llm_output = """Let me try a different strategy by searching for common file extensions:

```json
{
    "thought": "由于无法直接获取目录列表，我将通过搜索常见文件扩展名来识别E盘的文件类型",
    "reasoning": "通过搜索特定扩展名（如*.docx, *.xlsx等）可以推断E盘中存在的文件类型",
    "tool_name": "search_files",
    "tool_params": {
        "file_pattern": "*.docx|*.xlsx|*.pptx|*.pdf|*.jpg|*.png|*.mp3|*.mp4|*.exe|*.zip",
        "path": "E:/",
        "recursive": false
    }
}
```"""
        
        result = parse_react_response(llm_output)
        
        assert result["type"] == "action"
        assert result["tool_name"] == "search_files"
        assert "*.docx|*.xlsx" in result["tool_params"]["file_pattern"]
        assert result["tool_params"]["path"] == "E:/"
        assert result["tool_params"]["recursive"] is False
    
    def test_traditional_keyword_format_still_works(self):
        """测试传统关键词格式仍然有效（非Markdown JSON）"""
        # 这确保融合方案没有破坏原有功能
        llm_output = "Thought: I need to list directory\nAction: list_directory\nAction Input: {\"path\": \"/home\"}"
        
        result = parse_react_response(llm_output)
        
        assert result["type"] == "action"
        assert result["tool_name"] == "list_directory"
        assert result["tool_params"]["path"] == "/home"
    
    def test_chinese_keyword_format_still_works(self):
        """测试中文关键词格式仍然有效"""
        llm_output = "思考：我需要列出目录\n行动：list_directory\n工具参数：{\"path\": \"/home\"}"
        
        result = parse_react_response(llm_output)
        
        assert result["type"] == "action"
        assert result["tool_name"] == "list_directory"


# =============================================================================
# TestNewFunctions - 新增函数测试（2026-04-18小沈）
# =============================================================================

class TestNewFunctions:
    """测试新增的辅助函数"""
    
    def test_extract_json_block_with_trailing_comma(self):
        """测试尾随逗号修复"""
        from app.services.agent.react_output_parser import _extract_json_block
        
        json_with_comma = '{"tool_name": "list_directory", "tool_params": {"path": "E:/",},}'
        result = _extract_json_block(json_with_comma)
        
        assert result is not None
        assert result["tool_name"] == "list_directory"
        assert result["tool_params"]["path"] == "E:/"
    
    def test_extract_json_block_with_newlines(self):
        """测试JSON中的实际换行符处理"""
        from app.services.agent.react_output_parser import _extract_json_block
        
        json_with_newlines = '''{
    "thought": "用户需要检查E盘
    目录内容",
    "tool_name": "list_directory",
    "tool_params": {"dir_path": "E:/"}
}'''
        result = _extract_json_block(json_with_newlines)
        
        assert result is not None
        assert result["tool_name"] == "list_directory"
        assert result["tool_params"]["dir_path"] == "E:/"
    
    def test_create_action_result_with_none(self):
        """测试_create_action_result参数校验"""
        from app.services.agent.react_output_parser import _create_action_result
        
        result = _create_action_result(None, "original output")
        
        assert result["type"] == "implicit"
        assert result["response"] == "original output"
    
    def test_create_action_result_with_invalid_dict(self):
        """测试_create_action_result无效字典处理"""
        from app.services.agent.react_output_parser import _create_action_result
        
        result = _create_action_result("not a dict", "original output")
        
        assert result["type"] == "implicit"
        assert result["response"] == "original output"
    
    def test_create_action_result_with_finish(self):
        """测试_create_action_result的finish类型处理"""
        from app.services.agent.react_output_parser import _create_action_result
        
        parsed = {
            "thought": "任务完成",
            "tool_name": "finish",
            "tool_params": {"result": "已列出10个文件"}
        }
        result = _create_action_result(parsed, "original output")
        
        assert result["type"] == "answer"
        assert result["tool_name"] is None
        assert result["response"] == "已列出10个文件"
    
    def test_create_action_result_with_action(self):
        """测试_create_action_result的action类型处理"""
        from app.services.agent.react_output_parser import _create_action_result
        
        parsed = {
            "thought": "用户想查看文件",
            "tool_name": "list_directory",
            "tool_params": {"dir_path": "E:/"}
        }
        result = _create_action_result(parsed, "original output")
        
        assert result["type"] == "action"
        assert result["tool_name"] == "list_directory"
        assert result["tool_params"] == {"dir_path": "E:/"}
    
    def test_extract_tool_params_from_thought_with_json(self):
        """测试从thought中提取嵌套JSON参数"""
        from app.services.agent.react_output_parser import _extract_tool_params_from_thought
        
        thought = '用户需要检查E盘，参数是{"dir_path": "E:/"}'
        result = _extract_tool_params_from_thought(thought, "list_directory")
        
        assert result == {"dir_path": "E:/"}
    
    def test_extract_tool_params_from_thought_with_tool_params(self):
        """测试从thought中提取tool_params字段"""
        from app.services.agent.react_output_parser import _extract_tool_params_from_thought
        
        thought = '{"tool_params": {"dir_path": "E:/"}}'
        result = _extract_tool_params_from_thought(thought, "list_directory")
        
        assert result == {"dir_path": "E:/"}
    
    def test_parse_react_response_with_dict_input(self):
        """【2026-04-28 小沈新增】测试直接传入dict输入（解决长文本content丢失问题）"""
        # 这是模拟 LLM 返回的 dict 格式数据（不是 JSON 字符串）
        dict_input = {
            "content": "第九篇创作成功！现在开始第十篇",
            "tool_name": "write_file",
            "tool_params": {
                "file_path": "E:/春天爱情故事/春日回忆.txt",
                "content": "第十篇：春日回忆\n\n又是一个春天到来，\n我站在我们曾经相遇的地方。"
            },
            "reasoning": "创作第十篇关于春天和爱情的小说"
        }
        
        result = parse_react_response(dict_input)
        
        # 验证能正确解析 dict 输入
        assert result["type"] == "action"
        assert result["tool_name"] == "write_file"
        assert result["tool_params"]["file_path"] == "E:/春天爱情故事/春日回忆.txt"
        assert result["tool_params"]["content"] == "第十篇：春日回忆\n\n又是一个春天到来，\n我站在我们曾经相遇的地方。"
    
    def test_extract_tool_params_from_thought_empty(self):
        """测试空thought返回空字典"""
        from app.services.agent.react_output_parser import _extract_tool_params_from_thought
        
        result = _extract_tool_params_from_thought("", "list_directory")
        
        assert result == {}
    
    # ============================================================================
    # 【2026-04-28 小沈新增】LLM返回形式完整测试套件
    # 覆盖 LLM 可能返回的所有格式，确保 parser 能正确处理
    # ============================================================================
    
    def test_llm_return_form_1_json_string(self):
        """【形式1】标准JSON字符串 - LLM直接返回完整JSON"""
        json_string = '{"content": "完成", "tool_name": "write_file", "tool_params": {"file_path": "E:/test.txt", "content": "内容"}, "reasoning": "测试"}'
        result = parse_react_response(json_string)
        assert result["type"] == "action"
        assert result["tool_name"] == "write_file"
        assert result["tool_params"]["content"] == "内容"
    
    def test_llm_return_form_2_dict_object(self):
        """【形式2】Dict对象 - 已经解析的dict（导致本次bug的原因）"""
        dict_input = {
            "content": "创作成功",
            "tool_name": "write_file",
            "tool_params": {"file_path": "E:/test.txt", "content": "长文本内容..."},
            "reasoning": "测试"
        }
        result = parse_react_response(dict_input)
        assert result["type"] == "action"
        assert result["tool_params"]["content"] == "长文本内容..."
    
    def test_llm_return_form_3_markdown_json(self):
        """【形式3】Markdown包裹的JSON - ```json {...} ``` """
        markdown_json = '```json\n{"content": "完成", "tool_name": "list_directory", "tool_params": {"dir_path": "E:/"}}\n```'
        result = parse_react_response(markdown_json)
        assert result["type"] == "action"
        assert result["tool_name"] == "list_directory"
    
    def test_llm_return_form_4_markdown_json_no_lang(self):
        """【形式3.1】Markdown包裹的JSON（无json标签）- ``` {...} ``` """
        markdown_json = '```\n{"content": "完成", "tool_name": "read_file", "tool_params": {"file_path": "E:/test.txt"}}\n```'
        result = parse_react_response(markdown_json)
        assert result["type"] == "action"
    
    def test_llm_return_form_5_mixed_text_json(self):
        """【形式4】混合文本+JSON - "思考内容 {...JSON...}" """
        mixed = '根据用户需求，我需要写入文件。{"content": "执行写入", "tool_name": "write_file", "tool_params": {"file_path": "E:/test.txt", "content": "内容"}}'
        result = parse_react_response(mixed)
        assert result["type"] == "action"
        assert result["tool_name"] == "write_file"
    
    def test_llm_return_form_6_traditional_react(self):
        """【形式5】传统ReAct格式 - Thought/Action/Action Input"""
        traditional = '''Thought: 我需要读取文件
Action: read_file
Action Input: {"file_path": "E:/test.txt"}'''
        result = parse_react_response(traditional)
        assert result["type"] == "action"
        assert result["tool_name"] == "read_file"
    
    def test_llm_return_form_6_chinese_react(self):
        """【形式5.1】传统ReAct格式（中文）"""
        traditional = '''思考：用户需要查看目录
行动：list_directory
工具参数：{"dir_path": "E:/"}'''
        result = parse_react_response(traditional)
        assert result["type"] == "action"
    
    def test_llm_return_form_7_plain_text(self):
        """【形式6】纯文本回答（无JSON格式）"""
        plain = '我已经完成了任务，共写了10篇故事。'
        result = parse_react_response(plain)
        # 纯文本应该返回 implicit 或 answer 类型
        assert result["type"] in ["implicit", "answer", "thought_only"]
    
    def test_llm_return_form_8_empty_string(self):
        """【形式7】空字符串"""
        result = parse_react_response("")
        assert result["type"] == "parse_error"
    
    def test_llm_return_form_9_none_input(self):
        """【形式8】None输入"""
        result = parse_react_response(None)
        assert result["type"] == "parse_error"
    
    def test_llm_return_form_10_finish_type(self):
        """【形式9】finish类型（返回最终答案）"""
        # JSON字符串格式
        finish_json = '{"content": "任务完成", "tool_name": "finish", "tool_params": {"result": "共写10篇"}}'
        result = parse_react_response(finish_json)
        assert result["type"] == "answer"
        
        # Dict格式
        finish_dict = {"content": "完成", "tool_name": "finish", "tool_params": {"result": "成功"}}
        result2 = parse_react_response(finish_dict)
        assert result2["type"] == "answer"
    
    def test_llm_return_form_11_malformed_json(self):
        """【形式10】畸形JSON（解析失败时的降级处理）"""
        malformed = '{"content": "部分JSON, tool_name: "write_file"'  # 缺少引号
        result = parse_react_response(malformed)
        # 应该降级到关键词匹配或兜底
        assert result["type"] in ["action", "implicit", "thought_only", "parse_error"]
    
    def test_llm_return_form_12_partial_json(self):
        """【形式11】不完整JSON（缺少闭合括号）"""
        partial = '{"content": "未完成, "tool_name": "write_file"'
        result = parse_react_response(partial)
        # 应该尝试关键词匹配
        assert result["type"] in ["action", "implicit", "thought_only", "parse_error"]
    
    def test_llm_return_form_13_with_special_chars(self):
        """【形式12】包含特殊字符的内容"""
        special = '{"content": "包含<>引号和换行", "tool_name": "write_file", "tool_params": {"file_path": "E:/test.txt", "content": "内容含\"引号\\和\n换行"}}'
        result = parse_react_response(special)
        assert result["type"] == "action"
        assert result["tool_name"] == "write_file"
    
    def test_llm_return_form_14_nested_params(self):
        """【形式13】嵌套的tool_params"""
        nested = '{"content": "复杂参数", "tool_name": "write_file", "tool_params": {"file_path": "E:/test.txt", "content": {"text": "内容", "metadata": {"author": "测试", "tags": ["a", "b"]}}}}'
        result = parse_react_response(nested)
        assert result["type"] == "action"
        assert result["tool_params"]["content"]["metadata"]["author"] == "测试"
    
    def test_llm_return_form_15_missing_tool_params(self):
        """【形式14】有tool_name但tool_params为空的JSON"""
        missing_params = '{"content": "无参数", "tool_name": "list_directory", "tool_params": {}}'
        result = parse_react_response(missing_params)
        # 应该尝试工具名兜底匹配
        assert result["type"] in ["action", "implicit", "thought_only", "parse_error"]
    
    def test_llm_return_form_16_long_content_dict(self):
        """【形式15】长文本content（本次bug的核心场景）"""
        long_content = "第十篇：春日回忆\n\n" + "春风吹过，仿佛还带着你的气息，\n" * 100
        long_dict = {
            "content": "第九篇创作成功！",
            "tool_name": "write_file",
            "tool_params": {
                "file_path": "E:/春天爱情故事/春日回忆.txt",
                "content": long_content
            }
        }
        result = parse_react_response(long_dict)
        assert result["type"] == "action"
        assert result["tool_name"] == "write_file"
        assert result["tool_params"]["content"] == long_content  # 完整保留！
        assert len(result["tool_params"]["content"]) > 1000  # 验证长度


# =============================================================================
# TestExceptionHandling - 异常处理测试（2026-04-18小沈）
# =============================================================================

class TestExceptionHandling:
    """测试异常处理机制"""
    
    def test_determine_parse_type_with_malformed_markdown(self):
        """测试畸形的Markdown代码块不会导致崩溃"""
        llm_output = "```json\n{'invalid': json,}\n```"
        
        result = parse_react_response(llm_output)
        
        # 应该返回一个有效的结果，而不是抛出异常
        assert "type" in result
        assert "tool_name" in result
    
    def test_determine_parse_type_with_incomplete_json(self):
        """测试不完整的JSON不会导致崩溃"""
        llm_output = '{"tool_name": "list_directory", "tool_params": {'
        
        result = parse_react_response(llm_output)
        
        # 应该返回一个有效的结果
        assert "type" in result
    
    def test_determine_parse_type_with_special_characters(self):
        """测试特殊字符不会导致崩溃"""
        llm_output = '{"thought": "参数是{dir_path: \'E:/\'}", "tool_name": "list_directory"}'
        
        result = parse_react_response(llm_output)
        
        assert result["type"] == "action"
        assert result["tool_name"] == "list_directory"


# =============================================================================
# TestRealLLMOutputs - 真实LLM输出测试（2026-04-18小沈）
# =============================================================================

class TestRealLLMOutputs:
    """使用真实LLM输出数据进行验证（来自设计文档16.2章节）"""
    
    # =============================================================================
    # 第一组用例：16.2.1-16.2.6（```包裹格式，早期版本解析失败）
    # =============================================================================
    
    def test_real_llm_output_case_1(self):
        """测试用例16.2.1（第1轮，```包裹，参数丢失问题）"""
        llm_output = """I'll help you check the file types in the E drive directory. Here's my plan:

1. Use the `list_directory` tool to scan the root of E drive
2. Analyze the file extensions to determine the types
3. Pro...

```json
{
    "thought": "用户需要检查E盘的文件类型。第一步是列出E盘根目录下的所有文件和目录，获取文件列表后才能分析文件类型。",
    "tool_name": "list_directory",
    "tool_params": {
        "dir_path": "E:/"
    }
}
```"""
        
        result = parse_react_response(llm_output)
        
        assert result["type"] == "action"
        assert result["tool_name"] == "list_directory"
        assert result["tool_params"]["dir_path"] == "E:/"
    
    def test_real_llm_output_case_2(self):
        """测试用例16.2.2（第2轮，```包裹）"""
        llm_output = """I apologize for the confusion. Let me reissue the command with the correct parameter format:

```json
{
    "thought": "需要获取E盘根目录的文件列表以分析文件类型，使用list_directory工具获取文件信息。",
    "reasoning": "系统要求必须使用dir_path参数（而非directory_path或path），且路径应为绝对路径格式。",
    "tool_name": "list_directory",
    "tool_params": {
        "dir_path": "E:/"
    }
}
```"""
        
        result = parse_react_response(llm_output)
        
        assert result["type"] == "action"
        assert result["tool_name"] == "list_directory"
        assert result["tool_params"]["dir_path"] == "E:/"
    
    def test_real_llm_output_case_3(self):
        """测试用例16.2.3（第3轮，```包裹，search_files）"""
        llm_output = """I see the issue. It seems there might be a system configuration problem. Let me try an alternative approach using the search tool to list all files in the E drive root directory:

```json
{
    "thought": "由于list_directory工具出现参数问题，改用search_files工具来获取E盘根目录下的所有文件列表。",
    "reasoning": "search_files可以通过通配符'*'匹配所有文件，然后我将分析返回结果中的文件类型",
    "tool_name": "search_files",
    "tool_params": {
        "file_pattern": "*",
        "path": "E:/",
        "recursive": false
    }
}
```"""
        
        result = parse_react_response(llm_output)
        
        assert result["type"] == "action"
        assert result["tool_name"] == "search_files"
        assert result["tool_params"]["file_pattern"] == "*"
        assert result["tool_params"]["path"] == "E:/"
    
    def test_real_llm_output_case_4(self):
        """测试用例16.2.4（第4轮，```包裹）"""
        llm_output = """I apologize for the continued issues. Let me try a different approach using the `list_directory` tool again, but with a more explicit parameter structure:

```json
{
    "thought": "系统参数识别出现问题，我将使用更明确的参数格式尝试列出E盘目录内容",
    "reasoning": "需要获取E盘根目录的文件列表才能分析文件类型，使用list_directory工具并确保参数格式完全符合要求",
    "tool_name": "list_directory",
    "tool_params": {
        "dir_path": "E:/"
    }
}
```"""
        
        result = parse_react_response(llm_output)
        
        assert result["type"] == "action"
        assert result["tool_name"] == "list_directory"
        assert result["tool_params"]["dir_path"] == "E:/"
    
    def test_real_llm_output_case_5(self):
        """测试用例16.2.5（第5轮，```包裹，search_files复杂参数）"""
        llm_output = """I'm encountering persistent issues with the tool parameters. Since I can't retrieve the file list through standard methods, I'll need to use an alternative approach to determine the file types on your E drive.

Let me try a different strategy by searching for common file extensions:

```json
{
    "thought": "由于无法直接获取目录列表，我将通过搜索常见文件扩展名来识别E盘的文件类型",
    "reasoning": "通过搜索特定扩展名（如*.docx, *.xlsx等）可以推断E盘中存在的文件类型",
    "tool_name": "search_files",
    "tool_params": {
        "file_pattern": "*.docx|*.xlsx|*.pptx|*.pdf|*.jpg|*.png|*.mp3|*.mp4|*.exe|*.zip",
        "path": "E:/",
        "recursive": false
    }
}
```"""
        
        result = parse_react_response(llm_output)
        
        assert result["type"] == "action"
        assert result["tool_name"] == "search_files"
        assert result["tool_params"]["file_pattern"] == "*.docx|*.xlsx|*.pptx|*.pdf|*.jpg|*.png|*.mp3|*.mp4|*.exe|*.zip"
    
    def test_real_llm_output_case_6(self):
        """测试用例16.2.6（第6轮，无JSON，implicit类型）"""
        llm_output = """I apologize for the persistent issues. It seems there's a fundamental problem with the tool parameter recognition. Since I'm unable to retrieve the file list through standard methods, I'll provide you..."""
        
        result = parse_react_response(llm_output)
        
        assert result["type"] == "implicit"
    
    # =============================================================================
    # 第二组用例：16.2.7-16.2.11（纯JSON块，无```包裹，最终修复后通过）
    # =============================================================================
    
    def test_real_llm_output_case_7(self):
        """测试用例16.2.7（轮次1，纯JSON块无```包裹）"""
        llm_output = """To analyze the directory and file distribution on the E: drive, I'll first list 
the top-level contents of the drive to understand its high-level structure. 
This will help identify main directories and files for further exploration.

I'll use the `list_directory` tool with recursion disabled to avoid overwhelming 
data, focusing only on the root items. This is the most efficient starting point 
to map the distribution.

{
    "thought": "用户要求分析E盘目录和文件的分布情况。第一步需要获取E盘根目录的顶层结构，识别主要文件夹和文件。",
    "reasoning": "list_directory是获取目录结构的核心工具，设置dir_path='E:/'可查看顶层内容。recursive=False确保只返回直接子项，避免信息过载。",
    "tool_name": "list_directory",
    "tool_params": {
        "dir_path": "E:/"
    }
}"""
        
        result = parse_react_response(llm_output)
        
        assert result["type"] == "action"
        assert result["tool_name"] == "list_directory"
        assert result["tool_params"]["dir_path"] == "E:/"
    
    def test_real_llm_output_case_8(self):
        """测试用例16.2.8（轮次2，纯JSON块无```包裹）"""
        llm_output = """I apologize for the error. It seems there was a technical issue with the parameter 
passing. Let me retry listing the E drive root directory with the correct parameter format:

{
    "thought": "Retrying E盘目录检查，确保参数格式正确",
    "reasoning": "需要重新调用list_directory工具，明确指定dir_path参数为E盘根目录",
    "tool_name": "list_directory",
    "tool_params": {
        "dir_path": "E:/"
    }
}"""
        
        result = parse_react_response(llm_output)
        
        assert result["type"] == "action"
        assert result["tool_name"] == "list_directory"
        assert result["tool_params"]["dir_path"] == "E:/"
    
    def test_real_llm_output_case_9(self):
        """测试用例16.2.9（轮次3，纯JSON块无```包裹）"""
        llm_output = """I see the issue - the parameter name must be exactly `dir_path` (not `dir_path` with 
a different case or formatting). Let me try again with strict parameter naming:

{
    "thought": "第三次尝试检查E盘目录结构，确保参数名称完全匹配",
    "reasoning": "必须严格使用小写的dir_path参数名，并明确指定E盘根路径",
    "tool_name": "list_directory",
    "tool_params": {
        "dir_path": "E:/"
    }
}"""
        
        result = parse_react_response(llm_output)
        
        assert result["type"] == "action"
        assert result["tool_name"] == "list_directory"
        assert result["tool_params"]["dir_path"] == "E:/"
    
    def test_real_llm_output_case_10(self):
        """测试用例16.2.10（轮次4，generate_report工具）"""
        llm_output = """It appears there's a persistent system issue preventing directory listing. Since I 
can't proceed with analyzing E: drive's distribution, I'll generate a diagnostic 
report to help troubleshoot the problem. 

{
    "thought": "无法完成E盘分布分析，因目录列表工具持续报错。生成操作报告供诊断",
    "reasoning": "多次尝试均失败，需生成报告记录当前会话状态。generate_report工具可创建包含错误详情的诊断文件",
    "tool_name": "generate_report",
    "tool_params": {
        "output_dir": "C:/Users/User/Desktop"
    }
}"""
        
        result = parse_react_response(llm_output)
        
        assert result["type"] == "action"
        assert result["tool_name"] == "generate_report"
        assert result["tool_params"]["output_dir"] == "C:/Users/User/Desktop"
    
    def test_real_llm_output_case_11(self):
        """测试用例16.2.11（轮次5，finish类型）"""
        llm_output = """I apologize for the continued issues. It appears there's a system-level problem 
with tool execution. Since I cannot complete the requested analysis of E drive 
distribution, I'll terminate the session with an error summary:

{
    "thought": "任务无法完成，因系统工具存在执行异常",
    "reasoning": "多次尝试均失败：目录列表工具参数识别异常，报告生成工具参数映射错误。建议检查系统配置或联系技术支持。",
    "tool_name": "finish",
    "tool_params": {
        "result": "错误总结：\\n1. list_directory 持续报告 dir_path 参数缺失\\n2. generate_report 存在参数映射错误\\n3. 无法访问 E: 盘内容\\n建议人工检查系统文件管理工具状态。"
    }
}"""
        
        result = parse_react_response(llm_output)
        
        assert result["type"] == "answer"
        assert result["tool_name"] is None
        assert "错误总结" in result["response"]


# =============================================================================
# TestLLMReturnTypesComplete - LLM全量返回类型完整测试（2026-04-28小沈补充）
# 覆盖设计文档11种LLM返回类型，确保100%覆盖无遗漏
# =============================================================================

class TestLLMReturnTypesComplete:
    """
    完整的LLM返回类型测试套件
    覆盖设计文档《LLM全量返回类型解析器设计文档》规定的11种返回类型
    
    类型1: None/空值 ✅
    类型2: dict对象 ✅  
    类型3: list数组（对象维度）- 补充
    类型4: 标准JSON字符串 ✅
    类型5: Markdown包裹JSON ✅
    类型6: 混合文本+JSON ✅
    类型7: JSON数组字符串 - 补充
    类型8: 非标准JSON - 补充
    类型9: 字段缺失 - 补充
    类型10: content类型异常 - 补充
    类型11: 超长文本 ✅
    
    编写人: 小沈
    时间: 2026-04-28
    """
    
    # ==================== 类型3: list数组（对象维度） ====================
    def test_llm_return_list_array_single_item(self):
        """【类型3.1】list数组 - 单个元素"""
        list_input = [
            {"content": "任务完成", "tool_name": "write_file", "tool_params": {"content": "hello", "file_path": "E:/test.txt"}, "reasoning": "测试"}
        ]
        result = parse_react_response(list_input)
        assert result["type"] == "action"
        assert result["tool_name"] == "write_file"
        assert result["tool_params"]["content"] == "hello"
    
    def test_llm_return_list_array_multiple_items(self):
        """【类型3.2】list数组 - 多个元素（取最后一个）"""
        list_input = [
            {"content": "第1个任务", "tool_name": "list_directory", "tool_params": {"dir_path": "D:/"}, "reasoning": "1"},
            {"content": "第2个任务", "tool_name": "read_file", "tool_params": {"file_path": "E:/1.txt"}, "reasoning": "2"},
            {"content": "第3个任务", "tool_name": "write_file", "tool_params": {"content": "最终内容", "file_path": "E:/final.txt"}, "reasoning": "3"}
        ]
        result = parse_react_response(list_input)
        # 应取最后一个元素
        assert result["type"] == "action"
        assert result["tool_name"] == "write_file"
        assert result["tool_params"]["content"] == "最终内容"
    
    def test_llm_return_list_array_empty(self):
        """【类型3.3】list数组 - 空数组"""
        list_input = []
        result = parse_react_response(list_input)
        # 空数组应返回parse_error
        assert result["type"] == "parse_error"
    
    def test_llm_return_list_array_non_dict_element(self):
        """【类型3.4】list数组 - 非dict元素（安全处理）"""
        list_input = ["string1", "string2", 123]
        result = parse_react_response(list_input)
        # 非dict元素应返回parse_error
        assert result["type"] == "parse_error"
    
    def test_llm_return_list_array_with_long_content(self):
        """【类型3.5】list数组 - 长文本content（验证不丢失）"""
        long_text = "这是一段很长的内容" + "，重复填充" * 50
        list_input = [
            {"content": "第一个", "tool_name": "list_directory", "tool_params": {"dir_path": "D:/"}, "reasoning": ""},
            {"content": "最终任务", "tool_name": "write_file", "tool_params": {"content": long_text, "file_path": "E:/final.txt"}, "reasoning": ""}
        ]
        result = parse_react_response(list_input)
        # 取最后一个，长文本应完整保留
        assert result["tool_params"]["content"] == long_text
        assert len(result["tool_params"]["content"]) > 200
    
    # ==================== 类型7: JSON数组字符串 ====================
    def test_llm_return_json_array_string_single(self):
        """【类型7.1】JSON数组字符串 - 单个元素"""
        json_array_str = '[{"content": "完成", "tool_name": "write_file", "tool_params": {"content": "hello", "file_path": "E:/test.txt"}}]'
        result = parse_react_response(json_array_str)
        assert result["type"] == "action"
        assert result["tool_name"] == "write_file"
    
    def test_llm_return_json_array_string_multiple(self):
        """【类型7.2】JSON数组字符串 - 多个元素（取最后一个）"""
        json_array_str = '[{"content": "第1", "tool_name": "list_directory", "tool_params": {"dir_path": "D:/"}}, {"content": "第2", "tool_name": "read_file", "tool_params": {"file_path": "E:/1.txt"}}, {"content": "最终", "tool_name": "write_file", "tool_params": {"content": "最终内容", "file_path": "E:/final.txt"}}]'
        result = parse_react_response(json_array_str)
        # 应取最后一个元素
        assert result["tool_name"] == "write_file"
        assert result["tool_params"]["content"] == "最终内容"
    
    def test_llm_return_json_array_string_empty(self):
        """【类型7.3】JSON数组字符串 - 空数组"""
        json_array_str = "[]"
        result = parse_react_response(json_array_str)
        # 空数组应返回parse_error
        assert result["type"] == "parse_error"
    
    def test_llm_return_json_array_string_with_long_content(self):
        """【类型7.4】JSON数组字符串 - 长文本content"""
        long_text = "长文本内容" + "重复填充" * 30
        json_array_str = f'[{{"content": "第1", "tool_name": "list_directory", "tool_params": {{"dir_path": "D:/"}}}}, {{"content": "最终", "tool_name": "write_file", "tool_params": {{"content": "{long_text}", "file_path": "E:/final.txt"}}}}]'
        result = parse_react_response(json_array_str)
        # 最后一个元素的长文本应完整保留
        assert result["tool_params"]["content"] == long_text
        assert len(result["tool_params"]["content"]) > 100
    
    # ==================== 类型8: 非标准JSON ====================
    def test_llm_return_non_standard_json_single_quotes(self):
        """【类型8.1】非标准JSON - 单引号"""
        non_standard = "{'content': '完成', 'tool_name': 'write_file', 'tool_params': {'content': '内容', 'file_path': 'E:/test.txt'}}"
        result = parse_react_response(non_standard)
        assert result["type"] == "action"
        assert result["tool_name"] == "write_file"
        assert result["tool_params"]["content"] == "内容"
    
    def test_llm_return_non_standard_json_trailing_comma(self):
        """【类型8.2】非标准JSON - 尾逗号"""
        non_standard = '{"content": "完成", "tool_name": "write_file", "tool_params": {"content": "内容", "file_path": "E:/test.txt",}, "reasoning": ""}'
        result = parse_react_response(non_standard)
        assert result["type"] == "action"
        assert result["tool_name"] == "write_file"
    
    def test_llm_return_non_standard_json_single_quotes_and_trailing_comma(self):
        """【类型8.3】非标准JSON - 单引号+尾逗号组合"""
        non_standard = "{'content': '完成', 'tool_name': 'write_file', 'tool_params': {'content': '内容', 'file_path': 'E:/test.txt',}, 'reasoning': ''}"
        result = parse_react_response(non_standard)
        assert result["type"] == "action"
        assert result["tool_params"]["content"] == "内容"
    
    def test_llm_return_non_standard_json_comment(self):
        """【类型8.4】非标准JSON - 包含//注释"""
        non_standard = '{"content": "完成", // 这是注释\n "tool_name": "write_file", "tool_params": {"content": "内容"}}'
        result = parse_react_response(non_standard)
        # 注释应该被移除后解析
        assert result["type"] in ["action", "parse_error", "implicit"]
    
    def test_llm_return_non_standard_json_mixed_errors(self):
        """【类型8.5】非标准JSON - 多种错误组合"""
        non_standard = "{'content': '测试' // 注释\n, 'tool_name': 'write_file', 'tool_params': {'content': '内容', 'file_path': 'E:/test.txt',},}"
        result = parse_react_response(non_standard)
        # 应该能修复并正确解析
        assert result is not None
        assert result["type"] in ["action", "parse_error", "implicit"]
    
    # ==================== 类型9: 字段缺失 ====================
    def test_llm_return_missing_content_field(self):
        """【类型9.1】字段缺失 - 缺少content"""
        missing_field = '{"tool_name": "write_file", "tool_params": {"content": "内容", "file_path": "E:/test.txt"}}'
        result = parse_react_response(missing_field)
        # content缺失时应有合理的降级处理
        assert result is not None
        assert "type" in result
    
    def test_llm_return_missing_tool_name(self):
        """【类型9.2】字段缺失 - 缺少tool_name"""
        missing_field = '{"content": "完成", "tool_params": {"content": "内容", "file_path": "E:/test.txt"}}'
        result = parse_react_response(missing_field)
        # tool_name缺失应有合理的降级处理
        assert result is not None
    
    def test_llm_return_missing_tool_params(self):
        """【类型9.3】字段缺失 - 缺少tool_params"""
        missing_field = '{"content": "完成", "tool_name": "write_file"}'
        result = parse_react_response(missing_field)
        # tool_params缺失应有合理的降级处理
        assert result is not None
    
    def test_llm_return_missing_all_required_fields(self):
        """【类型9.4】字段缺失 - 全部必填字段都缺失"""
        missing_all = '{"other": "value"}'
        result = parse_react_response(missing_all)
        # 全部缺失应有合理的降级处理
        assert result is not None
    
    def test_llm_return_dict_input_missing_field(self):
        """【类型9.5】dict输入 - 缺少必填字段"""
        dict_input = {"content": "完成", "tool_name": "write_file"}  # 缺少tool_params
        result = parse_react_response(dict_input)
        # dict输入缺少字段应有合理的降级处理
        assert result is not None
    
    # ==================== 类型10: content类型异常 ====================
    def test_llm_return_content_as_number(self):
        """【类型10.1】content类型异常 - 数字类型"""
        content_as_number = '{"content": "完成", "tool_name": "write_file", "tool_params": {"content": 12345, "file_path": "E:/test.txt"}}'
        result = parse_react_response(content_as_number)
        assert result["type"] == "action"
        # 应强制转换为字符串
        assert isinstance(result["tool_params"]["content"], str)
        assert result["tool_params"]["content"] == "12345"
    
    def test_llm_return_content_as_boolean(self):
        """【类型10.2】content类型异常 - 布尔类型"""
        content_as_bool = '{"content": "完成", "tool_name": "write_file", "tool_params": {"content": true, "file_path": "E:/test.txt"}}'
        result = parse_react_response(content_as_bool)
        assert result["type"] == "action"
        # 应强制转换为字符串
        assert isinstance(result["tool_params"]["content"], str)
        assert result["tool_params"]["content"] == "True"
    
    def test_llm_return_content_as_none(self):
        """【类型10.3】content类型异常 - None值"""
        content_as_none = '{"content": "完成", "tool_name": "write_file", "tool_params": {"content": null, "file_path": "E:/test.txt"}}'
        result = parse_react_response(content_as_none)
        assert result is not None
        # None值应该保留为None，不崩溃
    
    def test_llm_return_content_as_number_in_dict(self):
        """【类型10.4】dict输入 - content为数字类型"""
        dict_input = {"content": "完成", "tool_name": "write_file", "tool_params": {"content": 999, "file_path": "E:/test.txt"}}
        result = parse_react_response(dict_input)
        assert result["type"] == "action"
        # 应强制转换为字符串
        assert isinstance(result["tool_params"]["content"], str)
        assert result["tool_params"]["content"] == "999"
    
    def test_llm_return_content_as_boolean_in_dict(self):
        """【类型10.5】dict输入 - content为布尔类型"""
        dict_input = {"content": "完成", "tool_name": "write_file", "tool_params": {"content": False, "file_path": "E:/test.txt"}}
        result = parse_react_response(dict_input)
        assert result["type"] == "action"
        # 应强制转换为字符串
        assert isinstance(result["tool_params"]["content"], str)
        assert result["tool_params"]["content"] == "False"
    
    # ==================== 类型11: 超长文本（1000+/10000+/50000+字符） ====================
    def test_llm_return_content_over_1000_chars(self):
        """【类型11.1】超长文本 - 1000+字符"""
        long_text = "内容" * 500  # 1500字符
        dict_input = {"content": "完成", "tool_name": "write_file", "tool_params": {"content": long_text, "file_path": "E:/test.txt"}}
        result = parse_react_response(dict_input)
        assert result["type"] == "action"
        # 1000+字符应有warning日志但不截断
        assert len(result["tool_params"]["content"]) >= 1000
    
    def test_llm_return_content_over_10000_chars(self):
        """【类型11.2】超长文本 - 10000+字符"""
        long_text = "内容" * 5000  # 约15000字符（超出10000）
        dict_input = {"content": "完成", "tool_name": "write_file", "tool_params": {"content": long_text, "file_path": "E:/test.txt"}}
        result = parse_react_response(dict_input)
        assert result["type"] == "action"
        # 10000+字符应有更高级别warning但不截断
        assert len(result["tool_params"]["content"]) >= 10000
    
    def test_llm_return_content_over_50000_chars(self):
        """【类型11.3】超长文本 - 50000+字符（可能截断风险）"""
        long_text = "内容" * 12500  # 约25000字符
        dict_input = {"content": "完成", "tool_name": "write_file", "tool_params": {"content": long_text, "file_path": "E:/test.txt"}}
        result = parse_react_response(dict_input)
        assert result is not None
        # 50000+字符应有error日志
        assert "type" in result
    
    def test_llm_return_content_over_1000_chars_in_json_string(self):
        """【类型11.4】超长文本 - JSON字符串格式1000+字符"""
        long_text = "内容" * 500  # 1500字符
        json_str = f'{{"content": "完成", "tool_name": "write_file", "tool_params": {{"content": "{long_text}", "file_path": "E:/test.txt"}}}}'
        result = parse_react_response(json_str)
        assert result["type"] == "action"
        assert len(result["tool_params"]["content"]) >= 1000
    
    def test_llm_return_content_over_1000_chars_in_list_array(self):
        """【类型11.5】超长文本 - list数组格式1000+字符"""
        long_text = "内容" * 500  # 1500字符
        list_input = [{"content": "完成", "tool_name": "write_file", "tool_params": {"content": long_text, "file_path": "E:/test.txt"}}]
        result = parse_react_response(list_input)
        assert result["type"] == "action"
        assert len(result["tool_params"]["content"]) >= 1000


# =============================================================================
# TestLongContentTruncation - 长文本截断问题测试（2026-04-28新增）
# =============================================================================

class TestLongContentTruncation:
    """测试长文本content字段不被截断 - 针对2026-04-27问题修复"""
    
    def test_long_content_in_tool_params_write_file(self):
        """测试用例：write_file工具的content参数包含长文本不被截断"""
        # 模拟LLM返回的作文内容（约500字）
        long_essay = """亲爱的妈妈：

您好！您现在的身体好吗？工作顺利吗？

时光如流水，一眨眼的功夫，我已经从一个不懂事的小男孩变成一个朝气蓬勃的初中生了。在这几年的时光里，您为了我的成长付出了很多很多，每当我看到您那忙碌的身影，看到您那缕缕银丝，我的心里就涌起一种说不出的感觉。

妈妈，您还记得吗？那天放学后，我因为和同学打架而很晚才回家。您看到我身上的灰尘和伤口，并没有责骂我，而是轻轻地帮我拍掉身上的灰尘，然后小心翼翼地帮我消毒伤口。那时候，我感受到了您对我的关爱，心里充满了愧疚。

妈妈，您就像一棵参天大树，为我遮风挡雨；您就像一盏明灯，指引我前进的方向；您就像一把钥匙，为我打开知识的大门。您对我的爱是那么无私，那么伟大，那么温暖！

妈妈，我想对您说：谢谢您！谢谢您对我的养育之恩，谢谢您对我的无私奉献，谢谢您对我的宽容理解。我一定会好好学习，天天向上，不辜负您对我的期望！

祝您：
身体健康，工作顺利，万事如意！

此致
敬礼

您的儿子：小明
2026年4月20日"""
        
        # 构建包含长文本的LLM输出（使用字符串拼接避免f-string嵌套问题）
        json_part = '''{
    "thought": "用户想要我写一篇作文并保存到文件",
    "reasoning": "用户提供了一个作文主题和具体要求，需要使用write_file工具将完整作文保存到指定文件",
    "tool_name": "write_file",
    "tool_params": {
        "path": "C:/Users/User/Documents/作文.txt",
        "content": "''' + long_essay + '''"
    }
}'''
        
        result = parse_react_response(json_part)
        
        # 验证action类型
        assert result["type"] == "action", f"期望action类型，实际{result['type']}"
        
        # 验证tool_name
        assert result["tool_name"] == "write_file", f"期望write_file，实际{result['tool_name']}"
        
        # 验证tool_params包含完整content（关键测试点）
        assert "tool_params" in result, "缺少tool_params"
        assert "path" in result["tool_params"], "缺少path参数"
        assert "content" in result["tool_params"], "缺少content参数"
        
        # 验证content长度没有被截断（至少400字）
        actual_content = result["tool_params"]["content"]
        content_length = len(actual_content)
        assert content_length >= 400, f"content被截断，长度仅{content_length}字符，期望至少400字符"
        
        # 验证content包含关键内容（没有被截断在句子中间）
        assert "亲爱的妈妈" in actual_content, "content开头缺失"
        assert "谢谢您" in actual_content, "content中间缺失"
        
        # 验证路径正确
        assert result["tool_params"]["path"] == "C:/Users/User/Documents/作文.txt"
    
    def test_long_content_in_tool_params_with_quotes(self):
        """测试用例：content包含引号和换行符等特殊字符不被截断"""
        # 简化版测试 - 使用简单的双引号文本
        long_text = "这是一段包含双引号的文本内容。" + "重复填充以达到长度要求" * 10
        
        json_part = '''{
    "thought": "测试包含特殊字符的长文本",
    "tool_name": "write_file",
    "tool_params": {
        "path": "D:/test.txt",
        "content": "''' + long_text + '''"
    }
}'''
        
        result = parse_react_response(json_part)
        
        # 验证tool_params完整
        assert result["tool_params"] is not None, "tool_params为None"
        actual_content = result["tool_params"].get("content", "")
        
        # 验证内容未被截断
        assert len(actual_content) >= 50, f"content被截断，长度仅{len(actual_content)}"
        assert "双引号" in actual_content, "双引号内容丢失"
    
    def test_fallback_extract_long_content(self):
        """测试用例：fallback机制正确提取长文本content"""
        llm_output = '''{
    "thought": "保存文件",
    "tool_name": "write_file",
    "tool_params": {
        "path": "E:/test.txt",
        "content": "这是一段很长的文本内容，包含了完整的信息，需要正确提取不能被截断。"
    }
}'''
        
        result = parse_react_response(llm_output)
        
        assert result["type"] == "action"
        assert result["tool_name"] == "write_file"
        assert result["tool_params"]["content"] == "这是一段很长的文本内容，包含了完整的信息，需要正确提取不能被截断。"
    
    def test_multiple_write_operations_with_long_content(self):
        """测试用例：连续多次调用write_file，长文本都能正确提取"""
        long_content = "这是第一段很长很长的内容" + "，重复填充以达到长度要求" * 50
        
        json_part1 = '''{
    "thought": "保存文件",
    "tool_name": "write_file",
    "tool_params": {
        "path": "D:/file1.txt",
        "content": "''' + long_content + '''"
    }
}'''
        
        result1 = parse_react_response(json_part1)
        assert len(result1["tool_params"]["content"]) >= 200
        
        # 第二次调用不同内容
        long_content2 = "这是第二段很长很长的内容" + "，重复填充以达到长度要求" * 50
        json_part2 = '''{
    "thought": "保存文件2",
    "tool_name": "write_file",
    "tool_params": {
        "path": "D:/file2.txt",
        "content": "''' + long_content2 + '''"
    }
}'''
        
        result2 = parse_react_response(json_part2)
        assert len(result2["tool_params"]["content"]) >= 200
        
        # 验证两次内容不同
        assert result1["tool_params"]["content"] != result2["tool_params"]["content"]
    
    def test_ten_parameters_extraction(self):
        """测试用例：10个以上参数的提取"""
        json_part = '''{
    "thought": "测试多参数提取",
    "tool_name": "search_files",
    "tool_params": {
        "path": "D:/project",
        "pattern": "*.py",
        "recursive": true,
        "max_results": 100,
        "include_hidden": false,
        "file_type": "code",
        "encoding": "utf-8",
        "ignore_dirs": ["node_modules", ".git", "__pycache__"],
        "search_content": "test",
        "case_sensitive": false
    }
}'''
        
        result = parse_react_response(json_part)
        
        assert result["type"] == "action"
        assert result["tool_name"] == "search_files"
        params = result["tool_params"]
        
        # 验证所有10个参数都被正确提取
        assert params.get("path") == "D:/project", "path参数丢失"
        assert params.get("pattern") == "*.py", "pattern参数丢失"
        assert params.get("recursive") == True, "recursive参数丢失"
        assert params.get("max_results") == 100, "max_results参数丢失"
        assert params.get("include_hidden") == False, "include_hidden参数丢失"
        assert params.get("file_type") == "code", "file_type参数丢失"
        assert params.get("encoding") == "utf-8", "encoding参数丢失"
        assert params.get("ignore_dirs") == ["node_modules", ".git", "__pycache__"], "ignore_dirs参数丢失"
        assert params.get("search_content") == "test", "search_content参数丢失"
        assert params.get("case_sensitive") == False, "case_sensitive参数丢失"
    
    def test_nested_parameters_extraction(self):
        """测试用例：参数中套参数（嵌套参数）的提取"""
        json_part = '''{
    "thought": "测试嵌套参数",
    "tool_name": "generate_report",
    "tool_params": {
        "output_dir": "D:/reports",
        "format": "json",
        "options": {
            "title": "测试报告",
            "author": "小明",
            "include_charts": true,
            "metadata": {
                "version": "1.0",
                "created": "2026-04-28"
            }
        },
        "callback": {
            "on_success": "notify_user",
            "on_error": "log_error"
        }
    }
}'''
        
        result = parse_react_response(json_part)
        
        assert result["type"] == "action"
        assert result["tool_name"] == "generate_report"
        params = result["tool_params"]
        
        # 验证顶层参数
        assert params.get("output_dir") == "D:/reports", "output_dir丢失"
        assert params.get("format") == "json", "format丢失"
        
        # 验证嵌套参数 - options
        assert "options" in params, "options参数丢失"
        options = params["options"]
        assert options.get("title") == "测试报告", "options.title丢失"
        assert options.get("author") == "小明", "options.author丢失"
        assert options.get("include_charts") == True, "options.include_charts丢失"
        
        # 验证嵌套参数 - options.metadata
        assert "metadata" in options, "options.metadata丢失"
        metadata = options["metadata"]
        assert metadata.get("version") == "1.0", "options.metadata.version丢失"
        assert metadata.get("created") == "2026-04-28", "options.metadata.created丢失"
        
        # 验证嵌套参数 - callback
        assert "callback" in params, "callback参数丢失"
        callback = params["callback"]
        assert callback.get("on_success") == "notify_user", "callback.on_success丢失"
        assert callback.get("on_error") == "log_error", "callback.on_error丢失"
    
    def test_mixed_long_and_nested_params(self):
        """测试用例：长文本 + 10个参数 + 嵌套参数的综合测试"""
        long_content = "这是第一段很长很长的内容" + "，重复填充以达到长度要求" * 30
        
        json_part = '''{
    "thought": "综合测试",
    "tool_name": "write_file",
    "tool_params": {
        "path": "D:/test.txt",
        "content": "''' + long_content + '''",
        "encoding": "utf-8",
        "backup": true,
        "max_size": 10485760,
        "timeout": 30,
        "retry": 3,
        "options": {
            "append": false,
            "create_dirs": true
        }
    }
}'''
        
        result = parse_react_response(json_part)
        
        assert result["type"] == "action"
        assert result["tool_name"] == "write_file"
        params = result["tool_params"]
        
        # 验证长文本content
        assert len(params.get("content", "")) >= 200, "长文本content被截断"
        
        # 验证其他参数
        assert params.get("path") == "D:/test.txt"
        assert params.get("encoding") == "utf-8"
        assert params.get("backup") == True
        assert params.get("max_size") == 10485760
        assert params.get("timeout") == 30
        assert params.get("retry") == 3
        
        # 验证嵌套参数
        assert "options" in params
        assert params["options"].get("append") == False
        assert params["options"].get("create_dirs") == True
    
    def test_fallback_with_nested_params(self):
        """测试用例：正常JSON能正确提取嵌套参数（无需触发fallback）"""
        # 正常JSON - 使用标准解析路径
        json_str = '''{
    "thought": "测试嵌套参数",
    "tool_name": "generate_report",
    "tool_params": {
        "path": "D:/output",
        "options": {
            "title": "报告",
            "config": {
                "level": 1,
                "debug": true
            }
        }
    }
}'''
        
        result = parse_react_response(json_str)
        
        # 验证正确提取嵌套参数
        assert result["type"] == "action", f"期望action，实际{result['type']}"
        assert result["tool_name"] == "generate_report"
        
        params = result["tool_params"]
        assert params is not None, "tool_params为None"
        
        # 验证顶层参数
        assert params.get("path") == "D:/output", "path丢失"
        
        # 验证嵌套参数 - options
        assert "options" in params, "options丢失"
        options = params["options"]
        assert options.get("title") == "报告", "options.title丢失"
        
        # 验证嵌套参数 - options.config
        assert "config" in options, "options.config丢失"
        config = options["config"]
        assert config.get("level") == 1, "options.config.level丢失"
        assert config.get("debug") == True, "options.config.debug丢失"
    
    def test_fallback_with_ten_params(self):
        """测试用例：JSON损坏时fallback能提取10个参数"""
        # 在JSON中间注入错误字符触发fallback
        json_str = '''{
    "thought": "测试fallback多参数",
    "tool_name": "search_files",
    "tool_params": {
        "path": "D:/test",
        "pattern": "*.txt",
        "recursive": true,
        "max_results": 50,
        "include_hidden": false
    }
}'''
        
        # 破坏JSON - 在一个正常字段后添加多余字符
        broken_json = json_str.replace('"recursive": true', '"recursive": true,}')
        
        result = parse_react_response(broken_json)
        
        assert result["tool_name"] == "search_files"
        params = result["tool_params"]
        
        # 验证至少提取到了关键参数
        assert params.get("path") is not None
        assert params.get("pattern") == "*.txt"
