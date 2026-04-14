"""
FileOperationPrompts 测试 - 小沈

测试文件操作Prompt模板的核心功能。

Author: 小沈 - 2026-03-21
"""

import pytest

from app.services.prompts.file.file_prompts import FileOperationPrompts
from app.services.prompts.BasePromptTemplate import BasePrompts


class TestFilePromptsInheritance:
    """测试FileOperationPrompts继承"""
    
    def test_inherits_base_prompts(self):
        """测试继承BasePrompts"""
        assert issubclass(FileOperationPrompts, BasePrompts)
    
    def test_can_instantiate(self):
        """测试可以实例化"""
        prompts = FileOperationPrompts()
        assert prompts is not None


class TestFilePromptsMethods:
    """测试FileOperationPrompts方法"""
    
    def test_get_system_prompt(self):
        """测试获取系统提示"""
        prompts = FileOperationPrompts()
        result = prompts.get_system_prompt()
        
        assert result is not None
        assert len(result) > 0
        assert "file management assistant" in result.lower()
    
    def test_get_available_tools_prompt(self):
        """测试获取可用工具提示"""
        prompts = FileOperationPrompts()
        result = prompts.get_available_tools_prompt()
        
        assert result is not None
    
    def test_get_task_prompt(self):
        """测试获取任务提示"""
        prompts = FileOperationPrompts()
        result = prompts.get_task_prompt("test task")
        
        assert "test task" in result
        assert "Task:" in result
    
    def test_get_task_prompt_with_context(self):
        """测试带上下文的任务提示"""
        prompts = FileOperationPrompts()
        result = prompts.get_task_prompt(
            "test task",
            context={"key": "value"}
        )
        
        assert "test task" in result
        assert "key" in result
    
    def test_get_observation_prompt(self):
        """测试获取观察结果提示"""
        prompts = FileOperationPrompts()
        # 传入JSON字符串格式的观察结果
        import json
        obs = json.dumps({"success": True, "result": {"operation_type": "read", "file_path": "test.txt"}})
        result = prompts.get_observation_prompt(obs)
        
        assert "Observation:" in result
    
    def test_get_safety_reminder(self):
        """测试获取安全提醒"""
        prompts = FileOperationPrompts()
        result = prompts.get_safety_reminder()
        
        assert result is not None
        assert len(result) > 0
        assert "Safety" in result or "safety" in result.lower()
    
    def test_get_parameter_reminder(self):
        """测试获取参数提醒"""
        prompts = FileOperationPrompts()
        result = prompts.get_parameter_reminder()
        
        assert result is not None
        assert len(result) > 0
        assert "Parameter" in result or "parameter" in result.lower()
    
    def test_get_rollback_instructions(self):
        """测试获取回滚说明"""
        prompts = FileOperationPrompts()
        result = prompts.get_rollback_instructions()
        
        assert result is not None
        assert len(result) > 0
        assert "rollback" in result.lower() or "undo" in result.lower()


class TestFilePromptsBuildFullSystemPrompt:
    """测试FileOperationPrompts构建完整系统提示"""
    
    def test_build_full_system_prompt(self):
        """测试构建完整系统提示"""
        prompts = FileOperationPrompts()
        result = prompts.build_full_system_prompt()
        
        assert result is not None
        assert len(result) > 0
        # 应该包含系统提示
        assert "file management assistant" in result.lower()
        # 应该包含参数提醒
        assert "parameter" in result.lower() or "Parameter" in result
        # 应应该包含回滚说明
        assert "rollback" in result.lower() or "undo" in result.lower()


class TestFilePromptsParameterNaming:
    """测试FileOperationPrompts参数命名规则"""
    
    def test_system_prompt_contains_parameter_rules(self):
        """测试系统提示包含参数命名规则"""
        prompts = FileOperationPrompts()
        result = prompts.get_system_prompt()
        
        # 检查包含正确的参数名
        assert "file_path" in result
        assert "dir_path" in result
        assert "source_path" in result
        assert "destination_path" in result
        
        # 检查包含禁止的参数名
        assert "directory_path" in result or "NOT directory_path" in result
        assert "filepath" in result or "NOT filepath" in result


class TestFilePromptsToolDescriptions:
    """测试FileOperationPrompts工具描述"""
    
    def test_system_prompt_contains_read_file(self):
        """测试系统提示包含read_file工具描述"""
        prompts = FileOperationPrompts()
        result = prompts.get_system_prompt()
        
        assert "read_file" in result
    
    def test_system_prompt_contains_write_file(self):
        """测试系统提示包含write_file工具描述"""
        prompts = FileOperationPrompts()
        result = prompts.get_system_prompt()
        
        assert "write_file" in result
    
    def test_system_prompt_contains_list_directory(self):
        """测试系统提示包含list_directory工具描述"""
        prompts = FileOperationPrompts()
        result = prompts.get_system_prompt()
        
        assert "list_directory" in result
    
    def test_system_prompt_contains_delete_file(self):
        """测试系统提示包含delete_file工具描述"""
        prompts = FileOperationPrompts()
        result = prompts.get_system_prompt()
        
        assert "delete_file" in result
    
    def test_system_prompt_contains_move_file(self):
        """测试系统提示包含move_file工具描述"""
        prompts = FileOperationPrompts()
        result = prompts.get_system_prompt()
        
        assert "move_file" in result
    
    def test_system_prompt_contains_search_files(self):
        """测试系统提示包含search_files工具描述"""
        prompts = FileOperationPrompts()
        result = prompts.get_system_prompt()
        
        assert "search_files" in result


class TestFilePromptsResponseFormat:
    """测试FileOperationPrompts响应格式"""
    
    def test_system_prompt_contains_response_format(self):
        """测试系统提示包含响应格式说明"""
        prompts = FileOperationPrompts()
        result = prompts.get_system_prompt()
        
        assert "JSON" in result or "json" in result.lower()
        assert "thought" in result
        assert "tool_name" in result
        assert "tool_params" in result


class TestLLMResponseSchema:
    """测试LLM响应Schema - 2026-04-14 新增"""
    
    def test_get_llm_response_schema_exists(self):
        """测试get_llm_response_schema方法存在"""
        prompts = FileOperationPrompts()
        assert hasattr(prompts, 'get_llm_response_schema')
    
    def test_get_llm_response_schema_returns_dict(self):
        """测试返回字典类型"""
        prompts = FileOperationPrompts()
        result = prompts.get_llm_response_schema()
        
        assert isinstance(result, dict)
    
    def test_get_llm_response_schema_name(self):
        """测试Schema名称"""
        prompts = FileOperationPrompts()
        result = prompts.get_llm_response_schema()
        
        assert result["name"] == "execute_tool"
    
    def test_get_llm_response_schema_description(self):
        """测试Schema描述"""
        prompts = FileOperationPrompts()
        result = prompts.get_llm_response_schema()
        
        assert "description" in result
        assert len(result["description"]) > 0
    
    def test_get_llm_response_schema_has_thought(self):
        """测试包含thought字段"""
        prompts = FileOperationPrompts()
        result = prompts.get_llm_response_schema()
        
        props = result["parameters"]["properties"]
        assert "thought" in props
        assert props["thought"]["type"] == "string"
    
    def test_get_llm_response_schema_has_reasoning(self):
        """测试包含reasoning字段"""
        prompts = FileOperationPrompts()
        result = prompts.get_llm_response_schema()
        
        props = result["parameters"]["properties"]
        assert "reasoning" in props
        assert props["reasoning"]["type"] == "string"
    
    def test_get_llm_response_schema_has_tool_name(self):
        """测试包含tool_name字段"""
        prompts = FileOperationPrompts()
        result = prompts.get_llm_response_schema()
        
        props = result["parameters"]["properties"]
        assert "tool_name" in props
        assert props["tool_name"]["type"] == "string"
    
    def test_get_llm_response_schema_has_tool_params(self):
        """测试包含tool_params字段"""
        prompts = FileOperationPrompts()
        result = prompts.get_llm_response_schema()
        
        props = result["parameters"]["properties"]
        assert "tool_params" in props
        assert props["tool_params"]["type"] == "object"
    
    def test_get_llm_response_schema_required_fields(self):
        """测试必填字段"""
        prompts = FileOperationPrompts()
        result = prompts.get_llm_response_schema()
        
        required = result["parameters"]["required"]
        assert "thought" in required
        assert "tool_name" in required
        # reasoning应该是可选的
        assert "reasoning" not in required


class TestExamplesWithReasoning:
    """测试Examples升级reasoning字段 - 2026-04-14 新增"""
    
    def test_system_prompt_contains_example_1_with_reasoning(self):
        """测试Example 1包含reasoning"""
        prompts = FileOperationPrompts()
        result = prompts.get_system_prompt()
        
        # 示例1：List directory
        assert "Example 1: List directory" in result
        assert "reasoning" in result
        assert "list_directory是列出目录的唯一工具" in result
    
    def test_system_prompt_contains_example_2_with_reasoning(self):
        """测试Example 2包含reasoning"""
        prompts = FileOperationPrompts()
        result = prompts.get_system_prompt()
        
        # 示例2：Read file
        assert "Example 2: Read file" in result
        assert "reasoning" in result
        assert "read_file是读取文件内容的唯一工具" in result
    
    def test_system_prompt_contains_example_3_with_reasoning(self):
        """测试Example 3包含reasoning"""
        prompts = FileOperationPrompts()
        result = prompts.get_system_prompt()
        
        # 示例3：Search file content
        assert "Example 3: Search file content" in result
        assert "reasoning" in result
        assert "search_file_content支持关键词搜索" in result
    
    def test_system_prompt_contains_example_4_with_reasoning(self):
        """测试Example 4包含reasoning"""
        prompts = FileOperationPrompts()
        result = prompts.get_system_prompt()
        
        # 示例4：Move file
        assert "Example 4: Move file" in result
        assert "reasoning" in result
        assert "move_file支持文件和目录移动" in result
    
    def test_system_prompt_contains_example_5_finish_with_result(self):
        """测试Example 5 finish包含result字段"""
        prompts = FileOperationPrompts()
        result = prompts.get_system_prompt()
        
        # 示例5：Task completed - finish
        assert "Example 5: Task completed" in result
        assert "finish" in result
        assert "result" in result
    
    def test_system_prompt_contains_finish_result_example(self):
        """测试finish的result示例"""
        prompts = FileOperationPrompts()
        result = prompts.get_system_prompt()
        
        # 验证finish示例中tool_params包含result字段
        assert '"tool_params": {"result":' in result or 'tool_params": {"result":' in result
