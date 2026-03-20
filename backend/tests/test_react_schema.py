"""
Function Calling Structured Outputs - Schema 生成测试

【测试编写】小健 - 2026-03-20
【参考】Structured-Outputs-实现方案-小沈-2026-03-20.md

测试范围：
1. get_tools_schema_for_function_calling 函数测试
2. get_tool_schema 单个工具 Schema 测试
3. validate_tool_call 工具调用验证测试
4. get_available_tools 可用工具列表测试
5. get_finish_tool_schema finish 工具 Schema 测试
6. _process_description 描述处理测试
7. _clean_properties 属性清理测试
8. OpenAI Function Calling 格式验证

依赖：
- pytest
"""

import pytest
import json
import sys
from pathlib import Path

# 确保可以导入被测试模块
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.file_operations.react_schema import (
    get_tools_schema_for_function_calling,
    get_tool_schema,
    validate_tool_call,
    get_available_tools,
    get_finish_tool_schema,
    _process_description,
    _clean_properties,
    _generate_example_hints
)


class TestGetToolsSchemaForFunctionCalling:
    """测试 get_tools_schema_for_function_calling 函数"""

    def test_returns_list(self):
        """测试返回类型是列表"""
        schema = get_tools_schema_for_function_calling()
        assert isinstance(schema, list), "应返回列表"

    def test_not_empty(self):
        """测试返回非空列表"""
        schema = get_tools_schema_for_function_calling()
        assert len(schema) > 0, "应返回至少一个工具"

    def test_tool_count(self):
        """测试工具数量（应有7个核心工具 + finish）"""
        schema = get_tools_schema_for_function_calling()
        # 7个核心工具 + finish = 8
        assert len(schema) >= 7, f"应至少有7个工具，当前: {len(schema)}"

    def test_each_tool_has_required_fields(self):
        """测试每个工具都有必需字段"""
        schema = get_tools_schema_for_function_calling()
        required_fields = ["type", "function"]
        
        for i, tool in enumerate(schema):
            for field in required_fields:
                assert field in tool, f"工具{i}缺少必需字段: {field}"
            
            func = tool["function"]
            assert "name" in func, f"工具{i}缺少function.name"
            assert "description" in func, f"工具{i}缺少function.description"
            assert "parameters" in func, f"工具{i}缺少function.parameters"

    def test_type_is_function(self):
        """测试每个工具的type是function"""
        schema = get_tools_schema_for_function_calling()
        for tool in schema:
            assert tool.get("type") == "function", "type应为function"

    def test_parameters_type(self):
        """测试parameters的type是object"""
        schema = get_tools_schema_for_function_calling()
        for tool in schema:
            params = tool.get("function", {}).get("parameters", {})
            assert params.get("type") == "object", "parameters.type应为object"

    def test_parameters_has_properties(self):
        """测试parameters有properties字段"""
        schema = get_tools_schema_for_function_calling()
        for tool in schema:
            params = tool.get("function", {}).get("parameters", {})
            assert "properties" in params, "parameters应有properties字段"
            assert isinstance(params["properties"], dict), "properties应为字典"

    def test_tool_names(self):
        """测试包含所有核心工具名称"""
        schema = get_tools_schema_for_function_calling()
        tool_names = [t.get("function", {}).get("name") for t in schema]
        
        expected_tools = [
            "read_file", "write_file", "list_directory",
            "delete_file", "move_file", "search_files", "generate_report"
        ]
        
        for expected in expected_tools:
            assert expected in tool_names, f"缺少工具: {expected}"

    def test_list_directory_has_dir_path(self):
        """测试list_directory工具有dir_path参数"""
        schema = get_tools_schema_for_function_calling()
        
        list_dir = None
        for tool in schema:
            if tool.get("function", {}).get("name") == "list_directory":
                list_dir = tool
                break
        
        assert list_dir is not None, "应包含list_directory工具"
        
        properties = list_dir.get("function", {}).get("parameters", {}).get("properties", {})
        assert "dir_path" in properties, "list_directory应有dir_path参数"
        assert "recursive" in properties, "list_directory应有recursive参数"

    def test_read_file_has_file_path(self):
        """测试read_file工具有file_path参数"""
        schema = get_tools_schema_for_function_calling()
        
        read_file = None
        for tool in schema:
            if tool.get("function", {}).get("name") == "read_file":
                read_file = tool
                break
        
        assert read_file is not None, "应包含read_file工具"
        
        properties = read_file.get("function", {}).get("parameters", {}).get("properties", {})
        assert "file_path" in properties, "read_file应有file_path参数"
        assert "offset" in properties, "read_file应有offset参数"
        assert "limit" in properties, "read_file应有limit参数"

    def test_move_file_has_correct_params(self):
        """测试move_file工具有source_path和destination_path参数"""
        schema = get_tools_schema_for_function_calling()
        
        move_file = None
        for tool in schema:
            if tool.get("function", {}).get("name") == "move_file":
                move_file = tool
                break
        
        assert move_file is not None, "应包含move_file工具"
        
        properties = move_file.get("function", {}).get("parameters", {}).get("properties", {})
        assert "source_path" in properties, "move_file应有source_path参数"
        assert "destination_path" in properties, "move_file应有destination_path参数"

    def test_required_fields_present(self):
        """测试必需参数字段存在"""
        schema = get_tools_schema_for_function_calling()
        
        for tool in schema:
            params = tool.get("function", {}).get("parameters", {})
            assert "required" in params, "parameters应有required字段"
            assert isinstance(params["required"], list), "required应为列表"


class TestGetToolSchema:
    """测试 get_tool_schema 函数"""

    def test_get_existing_tool(self):
        """测试获取已存在的工具"""
        schema = get_tool_schema("list_directory")
        assert schema is not None, "应返回list_directory的Schema"
        assert schema.get("function", {}).get("name") == "list_directory"

    def test_get_nonexistent_tool(self):
        """测试获取不存在的工具"""
        schema = get_tool_schema("nonexistent_tool_xyz")
        assert schema is None, "不存在应返回None"

    def test_all_core_tools(self):
        """测试可以获取所有核心工具"""
        tools = ["read_file", "write_file", "list_directory", "delete_file", 
                 "move_file", "search_files", "generate_report"]
        
        for tool_name in tools:
            schema = get_tool_schema(tool_name)
            assert schema is not None, f"应能获取{tool_name}的Schema"


class TestValidateToolCall:
    """测试 validate_tool_call 函数"""

    def test_valid_tool_call(self):
        """测试有效的工具调用"""
        tool_call = {
            "id": "call_abc123",
            "type": "function",
            "function": {
                "name": "list_directory",
                "arguments": '{"dir_path": "D:/", "recursive": false}'
            }
        }
        
        result = validate_tool_call(tool_call)
        
        assert result["tool_name"] == "list_directory"
        assert result["arguments"]["dir_path"] == "D:/"
        assert result["arguments"]["recursive"] == False
        assert result["error"] is None

    def test_missing_tool_name(self):
        """测试缺少工具名称"""
        tool_call = {
            "id": "call_abc123",
            "type": "function",
            "function": {
                "arguments": '{"dir_path": "D:/"}'
            }
        }
        
        result = validate_tool_call(tool_call)
        
        assert result["tool_name"] is None
        assert result["error"] is not None
        assert "Missing tool name" in result["error"]

    def test_invalid_json_arguments(self):
        """测试无效的JSON参数"""
        tool_call = {
            "id": "call_abc123",
            "type": "function",
            "function": {
                "name": "list_directory",
                "arguments": "not valid json {"
            }
        }
        
        result = validate_tool_call(tool_call)
        
        assert result["tool_name"] == "list_directory"
        assert result["error"] is not None
        assert "Failed to parse" in result["error"]

    def test_arguments_as_dict(self):
        """测试参数已经是字典格式"""
        tool_call = {
            "id": "call_abc123",
            "type": "function",
            "function": {
                "name": "read_file",
                "arguments": {"file_path": "/test/file.txt", "offset": 1}
            }
        }
        
        result = validate_tool_call(tool_call)
        
        assert result["tool_name"] == "read_file"
        assert result["arguments"]["file_path"] == "/test/file.txt"
        assert result["error"] is None

    def test_raw_arguments_preserved(self):
        """测试原始参数字符串被保留"""
        raw_args = '{"dir_path": "C:/test"}'
        tool_call = {
            "id": "call_abc123",
            "type": "function",
            "function": {
                "name": "list_directory",
                "arguments": raw_args
            }
        }
        
        result = validate_tool_call(tool_call)
        
        assert result["raw_arguments"] == raw_args


class TestGetAvailableTools:
    """测试 get_available_tools 函数"""

    def test_returns_list(self):
        """测试返回类型是列表"""
        tools = get_available_tools()
        assert isinstance(tools, list)

    def test_not_empty(self):
        """测试返回非空列表"""
        tools = get_available_tools()
        assert len(tools) > 0

    def test_contains_expected_tools(self):
        """测试包含预期的工具"""
        tools = get_available_tools()
        
        expected = ["read_file", "write_file", "list_directory", 
                    "delete_file", "move_file", "search_files", "generate_report"]
        
        for tool in expected:
            assert tool in tools, f"应包含工具: {tool}"

    def test_all_are_strings(self):
        """测试所有元素都是字符串"""
        tools = get_available_tools()
        for tool in tools:
            assert isinstance(tool, str), f"工具名应为字符串: {tool}"


class TestGetFinishToolSchema:
    """测试 get_finish_tool_schema 函数"""

    def test_returns_schema(self):
        """测试返回Schema"""
        schema = get_finish_tool_schema()
        assert isinstance(schema, dict)
        assert schema.get("type") == "function"

    def test_has_name(self):
        """测试有name字段"""
        schema = get_finish_tool_schema()
        assert schema.get("function", {}).get("name") == "finish"

    def test_has_description(self):
        """测试有description字段"""
        schema = get_finish_tool_schema()
        assert "description" in schema.get("function", {})

    def test_has_result_param(self):
        """测试有result参数"""
        schema = get_finish_tool_schema()
        properties = schema.get("function", {}).get("parameters", {}).get("properties", {})
        assert "result" in properties

    def test_result_is_required(self):
        """测试result是必需参数"""
        schema = get_finish_tool_schema()
        required = schema.get("function", {}).get("parameters", {}).get("required", [])
        assert "result" in required


class TestProcessDescription:
    """测试 _process_description 函数"""

    def test_empty_string(self):
        """测试空字符串"""
        result = _process_description("")
        assert result == ""

    def test_passes_through(self):
        """测试正常文本通过"""
        text = "这是一个正常的描述文本"
        result = _process_description(text)
        assert result == text

    def test_removes_forbidden_rules(self):
        """测试移除FORBIDDEN规则"""
        text = """这是一个描述
        【重要】必须使用 dir_path
        错误示例: {"path": "..."}
        正确示例: {"dir_path": "..."}
        更多内容"""
        
        result = _process_description(text)
        
        assert "【重要】必须使用" not in result
        assert "错误示例:" not in result
        assert "正确示例:" not in result
        assert "这是一个描述" in result
        assert "更多内容" in result


class TestCleanProperties:
    """测试 _clean_properties 函数"""

    def test_empty_properties(self):
        """测试空属性"""
        result = _clean_properties({})
        assert result == {}

    def test_preserves_type(self):
        """测试保留type字段"""
        props = {
            "name": {
                "type": "string",
                "description": "名称"
            }
        }
        result = _clean_properties(props)
        assert result["name"]["type"] == "string"

    def test_preserves_description(self):
        """测试保留description字段"""
        props = {
            "name": {
                "type": "string",
                "description": "这是描述"
            }
        }
        result = _clean_properties(props)
        assert "description" in result["name"]

    def test_removes_extra_fields(self):
        """测试移除额外字段"""
        props = {
            "name": {
                "type": "string",
                "description": "描述",
                "title": "标题",  # 应被移除
                "$schema": "http://..."  # 应被移除
            }
        }
        result = _clean_properties(props)
        
        assert "title" not in result["name"]
        assert "$schema" not in result["name"]

    def test_preserves_default(self):
        """测试保留default字段"""
        props = {
            "recursive": {
                "type": "boolean",
                "default": False
            }
        }
        result = _clean_properties(props)
        assert result["recursive"]["default"] == False


class TestGenerateExampleHints:
    """测试 _generate_example_hints 函数"""

    def test_empty_examples(self):
        """测试空示例"""
        result = _generate_example_hints("test", [])
        assert result == ""

    def test_generates_hints(self):
        """测试生成示例提示"""
        examples = [
            {"dir_path": "D:/", "recursive": False},
            {"dir_path": "C:/test", "recursive": True}
        ]
        
        result = _generate_example_hints("list_directory", examples)
        
        assert "使用示例" in result
        assert "示例1" in result
        assert "dir_path" in result

    def test_limits_examples(self):
        """测试限制示例数量（最多2个）"""
        examples = [
            {"dir_path": f"path{i}"} for i in range(5)
        ]
        
        result = _generate_example_hints("list_directory", examples)
        
        # 应该有"示例1"和"示例2"，但没有"示例3"
        assert "示例1" in result
        assert "示例2" in result
        assert "示例3" not in result


class TestOpenAIFormatValidation:
    """测试 OpenAI Function Calling 格式验证"""

    def test_complete_schema_structure(self):
        """测试完整的Schema结构符合OpenAI规范"""
        schema = get_tools_schema_for_function_calling()
        
        for tool in schema:
            # 顶层结构
            assert "type" in tool
            assert tool["type"] == "function"
            
            # function 对象
            assert "function" in tool
            func = tool["function"]
            
            assert "name" in func
            assert "description" in func
            assert "parameters" in func
            
            # parameters 对象
            params = func["parameters"]
            assert params["type"] == "object"
            assert "properties" in params
            assert isinstance(params["properties"], dict)
            
            # properties 结构
            for prop_name, prop_schema in params["properties"].items():
                assert "type" in prop_schema, f"{func['name']}.{prop_name}缺少type"

    def test_string_params_have_type(self):
        """测试字符串参数有正确的type"""
        schema = get_tools_schema_for_function_calling()
        
        read_file = get_tool_schema("read_file")
        assert read_file is not None
        
        properties = read_file.get("function", {}).get("parameters", {}).get("properties", {})
        
        if "file_path" in properties:
            assert properties["file_path"].get("type") == "string"

    def test_boolean_params_have_type(self):
        """测试布尔参数有正确的type"""
        schema = get_tools_schema_for_function_calling()
        
        list_dir = get_tool_schema("list_directory")
        assert list_dir is not None
        
        properties = list_dir.get("function", {}).get("parameters", {}).get("properties", {})
        
        if "recursive" in properties:
            assert properties["recursive"].get("type") == "boolean"

    def test_integer_params_have_type(self):
        """测试整数参数有正确的type"""
        schema = get_tools_schema_for_function_calling()
        
        read_file = get_tool_schema("read_file")
        assert read_file is not None
        
        properties = read_file.get("function", {}).get("parameters", {}).get("properties", {})
        
        if "offset" in properties:
            assert properties["offset"].get("type") == "integer"

    def test_can_be_used_in_api_request(self):
        """测试生成的Schema可以用于API请求"""
        schema = get_tools_schema_for_function_calling()
        
        # 模拟API请求结构
        request = {
            "model": "test-model",
            "messages": [
                {"role": "user", "content": "List files in D:/"}
            ],
            "tools": schema,
            "tool_choice": "auto"
        }
        
        # 验证结构正确
        assert "tools" in request
        assert isinstance(request["tools"], list)
        assert len(request["tools"]) > 0
        
        # 验证可以序列化为JSON
        json_str = json.dumps(request)
        assert json_str is not None
        
        # 验证可以反序列化
        parsed = json.loads(json_str)
        assert len(parsed["tools"]) == len(schema)


class TestEndToEndFunctionCalling:
    """端到端 Function Calling 测试"""

    def test_full_workflow(self):
        """测试完整工作流"""
        # 1. 获取 Schema
        schema = get_tools_schema_for_function_calling()
        assert len(schema) > 0
        
        # 2. 模拟 LLM 返回的 tool_call
        tool_call = {
            "id": "call_001",
            "type": "function",
            "function": {
                "name": "list_directory",
                "arguments": '{"dir_path": "D:/", "recursive": false}'
            }
        }
        
        # 3. 验证 tool_call
        validated = validate_tool_call(tool_call)
        assert validated["tool_name"] == "list_directory"
        assert validated["error"] is None
        assert validated["arguments"]["dir_path"] == "D:/"
        assert validated["arguments"]["recursive"] == False
        
        # 4. 验证 arguments 可以直接用于工具调用
        # 不需要任何参数映射
        tool_args = validated["arguments"]
        assert tool_args["dir_path"] == "D:/"  # 正确！不需要映射

    def test_no_param_mapping_needed(self):
        """测试参数名无需映射（Function Calling 的核心价值）"""
        # 模拟 LLM 在 Function Calling 模式下返回的参数
        tool_call = {
            "id": "call_002",
            "type": "function",
            "function": {
                "name": "read_file",
                "arguments": '{"file_path": "C:/test.txt", "offset": 1, "limit": 100}'
            }
        }
        
        # 验证返回的参数
        validated = validate_tool_call(tool_call)
        
        # 直接使用，无需映射！
        assert validated["arguments"]["file_path"] == "C:/test.txt"
        assert validated["arguments"]["offset"] == 1
        assert validated["arguments"]["limit"] == 100
        
        # 对比三层防御策略（需要映射）：
        # - agent.py 中的参数映射代码
        # - prompts.py 中的 FORBIDDEN 规则
        # - tools.py 中的 description 提示
        # 
        # Function Calling 模式下，这些都不需要了！
