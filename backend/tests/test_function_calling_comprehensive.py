"""
Function Calling Structured Outputs - 全面深度测试

【测试编写】小查 - 2026-03-20
【目标】扎扎实实、完整全面地测试所有功能点

测试范围：
1. react_schema.py 全部函数深度测试
2. base.py chat_with_tools 方法测试
3. agent.py Function Calling 集成测试
4. 参数类型提取（anyOf/oneOf）测试
5. 边界情况和异常处理测试
6. 与 tools.py 的集成测试

依赖：
- pytest
- pytest-asyncio
"""

import pytest
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.file_operations.react_schema import (
    get_tools_schema_for_function_calling,
    get_tool_schema,
    validate_tool_call,
    get_available_tools,
    get_finish_tool_schema,
    _process_description,
    _clean_properties,
    _extract_type,
    _generate_example_hints
)
from app.services.file_operations.tools import (
    ReadFileInput,
    WriteFileInput,
    ListDirectoryInput,
    DeleteFileInput,
    MoveFileInput,
    SearchFilesInput,
    GenerateReportInput
)


# ============================================================
# 第一部分：_extract_type 深度测试
# ============================================================

class TestExtractType:
    """深度测试 _extract_type 函数 - 处理各种 JSON Schema 类型格式"""

    def test_direct_string_type(self):
        """测试直接 string 类型"""
        schema = {"type": "string"}
        assert _extract_type(schema) == "string"

    def test_direct_integer_type(self):
        """测试直接 integer 类型"""
        schema = {"type": "integer"}
        assert _extract_type(schema) == "integer"

    def test_direct_boolean_type(self):
        """测试直接 boolean 类型"""
        schema = {"type": "boolean"}
        assert _extract_type(schema) == "boolean"

    def test_direct_number_type(self):
        """测试直接 number 类型"""
        schema = {"type": "number"}
        assert _extract_type(schema) == "number"

    def test_direct_object_type(self):
        """测试直接 object 类型"""
        schema = {"type": "object"}
        assert _extract_type(schema) == "object"

    def test_direct_array_type(self):
        """测试直接 array 类型"""
        schema = {"type": "array"}
        assert _extract_type(schema) == "array"

    def test_any_of_string_null(self):
        """测试 anyOf: [string, null] - Pydantic Optional[str]"""
        schema = {
            "anyOf": [
                {"type": "string"},
                {"type": "null"}
            ]
        }
        assert _extract_type(schema) == "string"

    def test_any_of_integer_null(self):
        """测试 anyOf: [integer, null]"""
        schema = {
            "anyOf": [
                {"type": "integer"},
                {"type": "null"}
            ]
        }
        assert _extract_type(schema) == "integer"

    def test_any_of_boolean_null(self):
        """测试 anyOf: [boolean, null]"""
        schema = {
            "anyOf": [
                {"type": "boolean"},
                {"type": "null"}
            ]
        }
        assert _extract_type(schema) == "boolean"

    def test_one_of_string_null(self):
        """测试 oneOf: [string, null]"""
        schema = {
            "oneOf": [
                {"type": "string"},
                {"type": "null"}
            ]
        }
        assert _extract_type(schema) == "string"

    def test_one_of_integer_null(self):
        """测试 oneOf: [integer, null]"""
        schema = {
            "oneOf": [
                {"type": "integer"},
                {"type": "null"}
            ]
        }
        assert _extract_type(schema) == "integer"

    def test_one_of_boolean_null(self):
        """测试 oneOf: [boolean, null]"""
        schema = {
            "oneOf": [
                {"type": "boolean"},
                {"type": "null"}
            ]
        }
        assert _extract_type(schema) == "boolean"

    def test_any_of_with_extra_types(self):
        """测试 anyOf 包含多个类型"""
        schema = {
            "anyOf": [
                {"type": "string"},
                {"type": "number"},
                {"type": "null"}
            ]
        }
        # string 优先
        assert _extract_type(schema) == "string"

    def test_empty_any_of(self):
        """测试空 anyOf"""
        schema = {"anyOf": []}
        assert _extract_type(schema) is None

    def test_empty_one_of(self):
        """测试空 oneOf"""
        schema = {"oneOf": []}
        assert _extract_type(schema) is None

    def test_no_type_specified(self):
        """测试没有指定 type"""
        schema = {
            "description": "这是一个参数",
            "default": None
        }
        assert _extract_type(schema) is None

    def test_type_in_nested_any_of(self):
        """测试 anyOf 中的嵌套结构"""
        schema = {
            "anyOf": [
                {"type": "string"},
                {"type": "null"}
            ]
        }
        # 只处理第一层
        result = _extract_type(schema)
        assert result in ["string", "integer", "boolean", "number", "object", "array"]


# ============================================================
# 第二部分：所有工具 Schema 完整性测试
# ============================================================

class TestAllToolsSchemaCompleteness:
    """测试所有 7 个核心工具的 Schema 完整性"""

    def test_read_file_schema_complete(self):
        """测试 read_file 工具 Schema 完整性"""
        schema = get_tool_schema("read_file")
        assert schema is not None
        
        props = schema["function"]["parameters"]["properties"]
        required = schema["function"]["parameters"]["required"]
        
        # 必需参数
        assert "file_path" in required
        assert "file_path" in props
        assert props["file_path"]["type"] == "string"
        
        # 可选参数
        assert "offset" in props
        assert props["offset"]["type"] == "integer"
        assert props["offset"].get("default") == 1
        
        assert "limit" in props
        assert props["limit"]["type"] == "integer"
        assert props["limit"].get("default") == 2000
        
        assert "encoding" in props
        assert props["encoding"]["type"] == "string"

    def test_write_file_schema_complete(self):
        """测试 write_file 工具 Schema 完整性"""
        schema = get_tool_schema("write_file")
        assert schema is not None
        
        props = schema["function"]["parameters"]["properties"]
        required = schema["function"]["parameters"]["required"]
        
        # 必需参数
        assert "file_path" in required
        assert "file_path" in props
        assert props["file_path"]["type"] == "string"
        
        assert "content" in required
        assert "content" in props
        
        # 可选参数
        assert "encoding" in props
        assert props["encoding"].get("default") == "utf-8"

    def test_list_directory_schema_complete(self):
        """测试 list_directory 工具 Schema 完整性"""
        schema = get_tool_schema("list_directory")
        assert schema is not None
        
        props = schema["function"]["parameters"]["properties"]
        required = schema["function"]["parameters"]["required"]
        
        # 必需参数
        assert "dir_path" in required
        assert "dir_path" in props
        assert props["dir_path"]["type"] == "string"
        
        # 可选参数
        assert "recursive" in props
        assert props["recursive"]["type"] == "boolean"
        assert props["recursive"].get("default") == False
        
        assert "max_depth" in props
        assert props["max_depth"]["type"] == "integer"
        assert props["max_depth"].get("minimum") == 1
        assert props["max_depth"].get("maximum") == 50
        
        assert "page_token" in props
        assert props["page_token"].get("default") is None
        
        assert "page_size" in props
        assert props["page_size"]["type"] == "integer"
        assert props["page_size"].get("minimum") == 1
        assert props["page_size"].get("maximum") == 500

    def test_delete_file_schema_complete(self):
        """测试 delete_file 工具 Schema 完整性"""
        schema = get_tool_schema("delete_file")
        assert schema is not None
        
        props = schema["function"]["parameters"]["properties"]
        required = schema["function"]["parameters"]["required"]
        
        # 必需参数
        assert "file_path" in required
        assert "file_path" in props
        assert props["file_path"]["type"] == "string"
        
        # 可选参数
        assert "recursive" in props
        assert props["recursive"]["type"] == "boolean"
        assert props["recursive"].get("default") == False

    def test_move_file_schema_complete(self):
        """测试 move_file 工具 Schema 完整性"""
        schema = get_tool_schema("move_file")
        assert schema is not None
        
        props = schema["function"]["parameters"]["properties"]
        required = schema["function"]["parameters"]["required"]
        
        # 必需参数
        assert "source_path" in required
        assert "source_path" in props
        assert props["source_path"]["type"] == "string"
        
        assert "destination_path" in required
        assert "destination_path" in props
        assert props["destination_path"]["type"] == "string"

    def test_search_files_schema_complete(self):
        """测试 search_files 工具 Schema 完整性"""
        schema = get_tool_schema("search_files")
        assert schema is not None
        
        props = schema["function"]["parameters"]["properties"]
        required = schema["function"]["parameters"]["required"]
        
        # 必需参数
        assert "pattern" in required
        assert "pattern" in props
        assert props["pattern"]["type"] == "string"
        
        # 可选参数
        assert "path" in props
        assert props["path"]["type"] == "string"
        assert props["path"].get("default") == "."
        
        assert "file_pattern" in props
        assert props["file_pattern"]["type"] == "string"
        assert props["file_pattern"].get("default") == "*"
        
        assert "use_regex" in props
        assert props["use_regex"]["type"] == "boolean"
        assert props["use_regex"].get("default") == False
        
        assert "max_results" in props
        assert props["max_results"]["type"] == "integer"
        assert props["max_results"].get("minimum") == 1
        assert props["max_results"].get("maximum") == 10000

    def test_generate_report_schema_complete(self):
        """测试 generate_report 工具 Schema 完整性"""
        schema = get_tool_schema("generate_report")
        assert schema is not None
        
        props = schema["function"]["parameters"]["properties"]
        required = schema["function"]["parameters"]["required"]
        
        # 所有参数都是可选的
        assert len(required) == 0 or required == [] or required is None
        
        # 可选参数
        assert "output_dir" in props
        # output_dir 可能是 Optional[str]，type 提取后应该是 string


# ============================================================
# 第三部分：validate_tool_call 深度测试
# ============================================================

class TestValidateToolCallDeep:
    """深度测试 validate_tool_call 函数"""

    def test_list_directory_with_all_params(self):
        """测试 list_directory 完整参数"""
        tool_call = {
            "id": "call_001",
            "type": "function",
            "function": {
                "name": "list_directory",
                "arguments": json.dumps({
                    "dir_path": "D:/test",
                    "recursive": True,
                    "max_depth": 5,
                    "page_size": 50
                })
            }
        }
        
        result = validate_tool_call(tool_call)
        
        assert result["tool_name"] == "list_directory"
        assert result["error"] is None
        assert result["arguments"]["dir_path"] == "D:/test"
        assert result["arguments"]["recursive"] == True
        assert result["arguments"]["max_depth"] == 5
        assert result["arguments"]["page_size"] == 50

    def test_read_file_with_optional_params(self):
        """测试 read_file 包含可选参数"""
        tool_call = {
            "id": "call_002",
            "type": "function",
            "function": {
                "name": "read_file",
                "arguments": json.dumps({
                    "file_path": "/test/file.txt",
                    "offset": 10,
                    "limit": 100,
                    "encoding": "utf-8"
                })
            }
        }
        
        result = validate_tool_call(tool_call)
        
        assert result["tool_name"] == "read_file"
        assert result["error"] is None
        assert result["arguments"]["file_path"] == "/test/file.txt"
        assert result["arguments"]["offset"] == 10
        assert result["arguments"]["limit"] == 100
        assert result["arguments"]["encoding"] == "utf-8"

    def test_move_file_with_full_params(self):
        """测试 move_file 完整参数"""
        tool_call = {
            "id": "call_003",
            "type": "function",
            "function": {
                "name": "move_file",
                "arguments": json.dumps({
                    "source_path": "/old/path.txt",
                    "destination_path": "/new/path.txt"
                })
            }
        }
        
        result = validate_tool_call(tool_call)
        
        assert result["tool_name"] == "move_file"
        assert result["error"] is None
        assert result["arguments"]["source_path"] == "/old/path.txt"
        assert result["arguments"]["destination_path"] == "/new/path.txt"

    def test_search_files_with_regex(self):
        """测试 search_files 使用正则表达式"""
        tool_call = {
            "id": "call_004",
            "type": "function",
            "function": {
                "name": "search_files",
                "arguments": json.dumps({
                    "pattern": "^class\\s+\\w+",
                    "path": "/src",
                    "file_pattern": "*.py",
                    "use_regex": True,
                    "max_results": 500
                })
            }
        }
        
        result = validate_tool_call(tool_call)
        
        assert result["tool_name"] == "search_files"
        assert result["error"] is None
        assert result["arguments"]["pattern"] == "^class\\s+\\w+"
        assert result["arguments"]["use_regex"] == True
        assert result["arguments"]["max_results"] == 500

    def test_empty_arguments(self):
        """测试空参数"""
        tool_call = {
            "id": "call_005",
            "type": "function",
            "function": {
                "name": "list_directory",
                "arguments": "{}"
            }
        }
        
        result = validate_tool_call(tool_call)
        
        # list_directory 需要 dir_path 是必需参数
        assert result["tool_name"] == "list_directory"
        assert result["error"] is not None
        assert "Missing required parameters" in result["error"]

    def test_extra_params_allowed(self):
        """测试允许额外的参数（不应报错）"""
        tool_call = {
            "id": "call_006",
            "type": "function",
            "function": {
                "name": "read_file",
                "arguments": json.dumps({
                    "file_path": "/test.txt",
                    "extra_param": "should_be_ignored",
                    "another": 123
                })
            }
        }
        
        result = validate_tool_call(tool_call)
        
        assert result["tool_name"] == "read_file"
        assert result["error"] is None
        assert result["arguments"]["file_path"] == "/test.txt"
        assert "extra_param" in result["arguments"]

    def test_invalid_tool_name(self):
        """测试无效的工具名称"""
        tool_call = {
            "id": "call_007",
            "type": "function",
            "function": {
                "name": "invalid_tool_name",
                "arguments": "{}"
            }
        }
        
        result = validate_tool_call(tool_call)
        
        # invalid_tool_name 不存在，验证会跳过
        assert result["tool_name"] == "invalid_tool_name"
        assert result["error"] is None  # 不验证不存在的工具

    def test_arguments_number_string(self):
        """测试数值参数作为字符串"""
        tool_call = {
            "id": "call_008",
            "type": "function",
            "function": {
                "name": "read_file",
                "arguments": json.dumps({
                    "file_path": "/test.txt",
                    "offset": "10",  # 字符串形式
                    "limit": "100"
                })
            }
        }
        
        result = validate_tool_call(tool_call)
        
        # JSON 解析后仍是字符串，不会报错
        assert result["tool_name"] == "read_file"
        assert result["arguments"]["offset"] == "10"

    def test_boolean_case_sensitivity(self):
        """测试布尔值大小写"""
        # JSON 中 true/false 是小写
        tool_call = {
            "id": "call_009",
            "type": "function",
            "function": {
                "name": "list_directory",
                "arguments": json.dumps({
                    "dir_path": "/test",
                    "recursive": True  # JSON boolean
                })
            }
        }
        
        result = validate_tool_call(tool_call)
        
        assert result["arguments"]["recursive"] == True
        assert isinstance(result["arguments"]["recursive"], bool)


# ============================================================
# 第四部分：base.py chat_with_tools 方法测试
# ============================================================

class TestBaseChatWithTools:
    """测试 base.py 的 chat_with_tools 方法"""

    @pytest.mark.asyncio
    async def test_chat_with_tools_success_with_tool_calls(self):
        """测试成功返回 tool_calls"""
        from app.services.base import BaseAIService
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "id": "call_001",
                            "type": "function",
                            "function": {
                                "name": "list_directory",
                                "arguments": '{"dir_path": "D:/"}'
                            }
                        }
                    ]
                }
            }]
        }
        
        mock_post = AsyncMock(return_value=mock_response)
        
        service = BaseAIService(
            api_key="test-key",
            model="test-model",
            api_base="https://api.test.com",
            provider="test"
        )
        service.client.post = mock_post
        
        tools = get_tools_schema_for_function_calling()
        response = await service.chat_with_tools(
            message="List files in D:/",
            tools=tools
        )
        
        assert response.content != ""
        assert response.error is None
        
        # 验证返回的是 tool_calls JSON
        tool_calls = json.loads(response.content)
        assert isinstance(tool_calls, list)
        assert len(tool_calls) == 1
        assert tool_calls[0]["function"]["name"] == "list_directory"

    @pytest.mark.asyncio
    async def test_chat_with_tools_text_response(self):
        """测试返回普通文本响应（LLM 选择不调用工具）"""
        from app.services.base import BaseAIService
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": "Hello, how can I help you?"
                },
                "finish_reason": "stop"
            }]
        }
        
        mock_post = AsyncMock(return_value=mock_response)
        
        service = BaseAIService(
            api_key="test-key",
            model="test-model",
            api_base="https://api.test.com",
            provider="test"
        )
        service.client.post = mock_post
        
        response = await service.chat_with_tools(
            message="Hello",
            tools=get_tools_schema_for_function_calling()
        )
        
        assert response.content == "Hello, how can I help you?"
        assert response.error is None

    @pytest.mark.asyncio
    async def test_chat_with_tools_api_error(self):
        """测试 API 返回错误"""
        from app.services.base import BaseAIService
        
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        
        mock_post = AsyncMock(return_value=mock_response)
        
        service = BaseAIService(
            api_key="test-key",
            model="test-model",
            api_base="https://api.test.com",
            provider="test"
        )
        service.client.post = mock_post
        
        response = await service.chat_with_tools(
            message="Test",
            tools=get_tools_schema_for_function_calling()
        )
        
        assert response.content == ""
        assert response.error is not None
        assert "API Error: 400" in response.error

    @pytest.mark.asyncio
    async def test_chat_with_tools_no_choices(self):
        """测试响应没有 choices"""
        from app.services.base import BaseAIService
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        
        mock_post = AsyncMock(return_value=mock_response)
        
        service = BaseAIService(
            api_key="test-key",
            model="test-model",
            api_base="https://api.test.com",
            provider="test"
        )
        service.client.post = mock_post
        
        response = await service.chat_with_tools(
            message="Test",
            tools=get_tools_schema_for_function_calling()
        )
        
        assert response.content == ""
        assert response.error == "No response from API"

    @pytest.mark.asyncio
    async def test_chat_with_tools_exception(self):
        """测试异常处理"""
        from app.services.base import BaseAIService
        
        mock_post = AsyncMock(side_effect=Exception("Network error"))
        
        service = BaseAIService(
            api_key="test-key",
            model="test-model",
            api_base="https://api.test.com",
            provider="test"
        )
        service.client.post = mock_post
        
        response = await service.chat_with_tools(
            message="Test",
            tools=get_tools_schema_for_function_calling()
        )
        
        assert response.content == ""
        assert response.error is not None
        assert "Exception" in response.error

    @pytest.mark.asyncio
    async def test_chat_with_tools_without_tools(self):
        """测试不提供 tools 参数"""
        from app.services.base import BaseAIService
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": "Response without tools"
                }
            }]
        }
        
        mock_post = AsyncMock(return_value=mock_response)
        
        service = BaseAIService(
            api_key="test-key",
            model="test-model",
            api_base="https://api.test.com",
            provider="test"
        )
        service.client.post = mock_post
        
        # 不传 tools 参数
        response = await service.chat_with_tools(message="Test")
        
        assert response.content == "Response without tools"


# ============================================================
# 第五部分：agent.py Function Calling 集成测试
# ============================================================

class TestAgentFunctionCallingIntegration:
    """测试 agent.py 与 Function Calling 的集成"""

    def test_format_tool_calls_for_agent(self):
        """测试 _format_tool_calls_for_agent 方法"""
        from app.services.file_operations.agent import FileOperationAgent
        
        # 创建 mock llm_client
        mock_client = MagicMock()
        
        agent = FileOperationAgent(
            llm_client=mock_client,
            session_id="test-session"
        )
        
        # 测试格式化
        tool_calls = [
            {
                "id": "call_001",
                "type": "function",
                "function": {
                    "name": "list_directory",
                    "arguments": '{"dir_path": "D:/", "recursive": true}'
                }
            }
        ]
        
        formatted = agent._format_tool_calls_for_agent(tool_calls)
        result = json.loads(formatted)
        
        assert result["action_tool"] == "list_directory"
        assert result["params"]["dir_path"] == "D:/"
        assert result["params"]["recursive"] == True
        assert "thought" in result

    def test_agent_with_function_calling_disabled(self):
        """测试默认不使用 Function Calling"""
        from app.services.file_operations.agent import FileOperationAgent
        
        mock_client = MagicMock()
        
        agent = FileOperationAgent(
            llm_client=mock_client,
            session_id="test-session"
        )
        
        assert agent.use_function_calling == False
        assert agent.tools == []

    def test_agent_with_function_calling_enabled(self):
        """测试启用 Function Calling"""
        from app.services.file_operations.agent import FileOperationAgent
        
        mock_client = MagicMock()
        tools = get_tools_schema_for_function_calling()
        
        agent = FileOperationAgent(
            llm_client=mock_client,
            session_id="test-session",
            use_function_calling=True,
            tools=tools
        )
        
        assert agent.use_function_calling == True
        assert len(agent.tools) >= 7

    def test_format_empty_tool_calls(self):
        """测试格式化空的 tool_calls"""
        from app.services.file_operations.agent import FileOperationAgent
        
        mock_client = MagicMock()
        
        agent = FileOperationAgent(
            llm_client=mock_client,
            session_id="test-session"
        )
        
        formatted = agent._format_tool_calls_for_agent([])
        assert formatted == ""

    def test_format_multiple_tool_calls(self):
        """测试格式化多个 tool_calls（只取第一个）"""
        from app.services.file_operations.agent import FileOperationAgent
        
        mock_client = MagicMock()
        
        agent = FileOperationAgent(
            llm_client=mock_client,
            session_id="test-session"
        )
        
        tool_calls = [
            {"id": "1", "function": {"name": "tool1", "arguments": "{}"}},
            {"id": "2", "function": {"name": "tool2", "arguments": "{}"}}
        ]
        
        formatted = agent._format_tool_calls_for_agent(tool_calls)
        result = json.loads(formatted)
        
        # 应该只取第一个
        assert result["action_tool"] == "tool1"


# ============================================================
# 第六部分：与 tools.py Pydantic 模型集成测试
# ============================================================

class TestIntegrationWithPydanticModels:
    """测试与 tools.py Pydantic 模型的集成"""

    def test_pydantic_model_to_schema(self):
        """测试 Pydantic 模型可以转换为 Schema"""
        schema = ListDirectoryInput.model_json_schema()
        
        assert "properties" in schema
        assert "dir_path" in schema["properties"]
        assert schema["properties"]["dir_path"]["type"] == "string"

    def test_pydantic_optional_fields(self):
        """测试 Pydantic Optional 字段"""
        schema = ListDirectoryInput.model_json_schema()
        
        # page_token 是 Optional[str]，应该是 anyOf 格式
        props = schema["properties"]
        
        # 验证 Optional 字段存在
        assert "page_token" in props
        assert "page_size" in props
        assert "recursive" in props
        assert "max_depth" in props

    def test_pydantic_required_fields(self):
        """测试 Pydantic 必需字段"""
        schema = ListDirectoryInput.model_json_schema()
        
        # dir_path 是必需参数
        required = schema.get("required", [])
        assert "dir_path" in required

    def test_all_input_models(self):
        """测试所有输入模型都能生成 Schema"""
        models = [
            ReadFileInput,
            WriteFileInput,
            ListDirectoryInput,
            DeleteFileInput,
            MoveFileInput,
            SearchFilesInput,
            GenerateReportInput
        ]
        
        for model in models:
            schema = model.model_json_schema()
            assert "properties" in schema
            assert "type" in schema
            assert schema["type"] == "object"


# ============================================================
# 第七部分：边界情况和异常处理测试
# ============================================================

class TestBoundaryConditions:
    """边界条件和异常处理测试"""

    def test_very_long_description(self):
        """测试非常长的描述"""
        long_desc = "A" * 10000
        result = _process_description(long_desc)
        assert len(result) > 0

    def test_unicode_in_description(self):
        """测试描述中的 Unicode 字符"""
        desc = "这是一个测试描述，包含中文、emoji 🚀 和特殊字符 é ü"
        result = _process_description(desc)
        assert "中文" in result
        assert "emoji" in result

    def test_special_chars_in_tool_args(self):
        """测试工具参数中的特殊字符"""
        tool_call = {
            "id": "call_001",
            "function": {
                "name": "read_file",
                "arguments": json.dumps({
                    "file_path": "C:/Users/用户名/Documents/测试文件.txt",
                    "encoding": "utf-8"
                })
            }
        }
        
        result = validate_tool_call(tool_call)
        assert result["error"] is None
        assert "测试文件" in result["arguments"]["file_path"]

    def test_json_with_unicode_escape(self):
        """测试包含 Unicode 转义的 JSON"""
        tool_call = {
            "id": "call_001",
            "function": {
                "name": "read_file",
                "arguments": '{"file_path": "C:\\\\u7528\\\\u6237\\\\u540D", "offset": 1}'
            }
        }
        
        result = validate_tool_call(tool_call)
        assert result["tool_name"] == "read_file"

    def test_empty_tool_name(self):
        """测试空工具名称"""
        tool_call = {
            "id": "call_001",
            "function": {
                "name": "",
                "arguments": "{}"
            }
        }
        
        result = validate_tool_call(tool_call)
        assert result["error"] is not None

    def test_whitespace_only_description(self):
        """测试只有空白字符的描述"""
        result = _process_description("   \n\t  ")
        assert result == ""

    def test_json_with_trailing_comma(self):
        """测试带尾部逗号的 JSON（无效 JSON）"""
        tool_call = {
            "id": "call_001",
            "function": {
                "name": "read_file",
                "arguments": '{"file_path": "/test.txt",}'  # 尾部逗号
            }
        }
        
        result = validate_tool_call(tool_call)
        # 无效 JSON 应该报错
        assert result["error"] is not None

    def test_example_hints_with_empty_values(self):
        """测试示例提示包含空值"""
        examples = [
            {"dir_path": "", "recursive": False},
        ]
        
        result = _generate_example_hints("test", examples)
        assert "示例1" in result
        assert "dir_path" in result

    def test_clean_properties_with_non_dict_item(self):
        """测试清理 properties 遇到非字典项"""
        props = {
            "valid_field": {"type": "string"},
            "invalid_field": "not a dict"
        }
        
        result = _clean_properties(props)
        assert "valid_field" in result
        assert "invalid_field" not in result


# ============================================================
# 第八部分：API 请求格式验证测试
# ============================================================

class TestAPIRequestFormat:
    """测试 API 请求格式验证"""

    def test_complete_api_request_structure(self):
        """测试完整的 API 请求结构"""
        tools = get_tools_schema_for_function_calling()
        
        request = {
            "model": "longcat-flash-thinking-2601",
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "List files in D:/"}
            ],
            "tools": tools,
            "tool_choice": "auto"
        }
        
        # 序列化验证
        json_str = json.dumps(request, ensure_ascii=False)
        parsed = json.loads(json_str)
        
        assert parsed["model"] == "longcat-flash-thinking-2601"
        assert len(parsed["messages"]) == 2
        assert len(parsed["tools"]) >= 7
        assert parsed["tool_choice"] == "auto"

    def test_tool_choice_required(self):
        """测试 tool_choice 为 required 的情况"""
        tools = get_tools_schema_for_function_calling()
        
        request = {
            "model": "test",
            "messages": [{"role": "user", "content": "test"}],
            "tools": tools,
            "tool_choice": "required"  # 强制使用工具
        }
        
        json_str = json.dumps(request)
        parsed = json.loads(json_str)
        
        assert parsed["tool_choice"] == "required"

    def test_tool_choice_specific(self):
        """测试指定特定工具"""
        tools = get_tools_schema_for_function_calling()
        
        request = {
            "model": "test",
            "messages": [{"role": "user", "content": "test"}],
            "tools": tools,
            "tool_choice": {
                "type": "function",
                "function": {"name": "list_directory"}
            }
        }
        
        json_str = json.dumps(request)
        parsed = json.loads(json_str)
        
        assert parsed["tool_choice"]["function"]["name"] == "list_directory"

    def test_schema_can_be_reused(self):
        """测试 Schema 可以被多次使用"""
        tools1 = get_tools_schema_for_function_calling()
        tools2 = get_tools_schema_for_function_calling()
        
        # 两次调用应该返回相同结果
        assert len(tools1) == len(tools2)
        
        for t1, t2 in zip(tools1, tools2):
            assert t1["function"]["name"] == t2["function"]["name"]


# ============================================================
# 第九部分：性能和安全测试
# ============================================================

class TestPerformanceAndSecurity:
    """性能和安全性测试"""

    def test_large_example_list(self):
        """测试大量示例"""
        large_examples = [
            {"dir_path": f"path_{i}", "recursive": i % 2 == 0}
            for i in range(100)
        ]
        
        result = _generate_example_hints("test_tool", large_examples)
        
        # 应该只保留前 2 个示例
        assert "示例1" in result
        assert "示例2" in result
        assert "path_0" in result
        assert "path_1" in result
        assert "path_2" not in result

    def test_special_characters_in_tool_name(self):
        """测试工具名称中的特殊字符"""
        # 模拟恶意输入
        tool_call = {
            "id": "call_001",
            "function": {
                "name": "<script>alert('xss')</script>",
                "arguments": "{}"
            }
        }
        
        result = validate_tool_call(tool_call)
        
        # 应该不报错，但工具名包含特殊字符
        assert result["tool_name"] is not None

    def test_deeply_nested_json(self):
        """测试深层嵌套 JSON"""
        nested_json = json.dumps({
            "file_path": "/test",
            "metadata": {
                "level1": {
                    "level2": {
                        "level3": "deep_value"
                    }
                }
            }
        })
        
        tool_call = {
            "id": "call_001",
            "function": {
                "name": "read_file",
                "arguments": nested_json
            }
        }
        
        result = validate_tool_call(tool_call)
        assert result["error"] is None
        assert result["arguments"]["metadata"]["level1"]["level2"]["level3"] == "deep_value"

    def test_rapid_validation_calls(self):
        """测试快速连续调用验证"""
        tool_call = {
            "id": "call_001",
            "function": {
                "name": "list_directory",
                "arguments": '{"dir_path": "/test"}'
            }
        }
        
        # 快速调用 1000 次
        for _ in range(1000):
            result = validate_tool_call(tool_call)
            assert result["tool_name"] == "list_directory"


# ============================================================
# 第十部分：文档和注释测试
# ============================================================

class TestDocumentation:
    """文档和注释测试"""

    def test_get_tools_schema_has_docstring(self):
        """测试主函数有文档字符串"""
        doc = get_tools_schema_for_function_calling.__doc__
        assert doc is not None
        assert len(doc) > 0

    def test_get_tool_schema_has_docstring(self):
        """测试单个工具函数有文档字符串"""
        doc = get_tool_schema.__doc__
        assert doc is not None

    def test_validate_tool_call_has_docstring(self):
        """测试验证函数有文档字符串"""
        doc = validate_tool_call.__doc__
        assert doc is not None

    def test_all_helper_functions_documented(self):
        """测试所有辅助函数都有文档字符串"""
        functions = [
            _process_description,
            _clean_properties,
            _extract_type,
            _generate_example_hints
        ]
        
        for func in functions:
            assert func.__doc__ is not None, f"{func.__name__} 缺少文档字符串"
            assert len(func.__doc__) > 0, f"{func.__name__} 文档字符串为空"
