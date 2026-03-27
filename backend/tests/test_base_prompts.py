"""
BasePrompts 测试 - 小沈

测试基础Prompt模板基类的核心功能。

Author: 小沈 - 2026-03-21
"""

import pytest

from app.services.prompts.BasePromptTemplate import BasePrompts


class ConcretePrompts(BasePrompts):
    """测试用的具体Prompt实现"""
    
    def get_system_prompt(self) -> str:
        return "You are a helpful assistant."
    
    def get_available_tools_prompt(self) -> str:
        return "Available tools: read_file, write_file"


class TestBasePromptsAbstract:
    """测试BasePrompts抽象类"""
    
    def test_cannot_instantiate_abstract_class(self):
        """测试不能直接实例化抽象类"""
        with pytest.raises(TypeError):
            BasePrompts()
    
    def test_concrete_class_can_instantiate(self):
        """测试具体类可以实例化"""
        prompts = ConcretePrompts()
        assert prompts is not None


class TestBasePromptsMethods:
    """测试BasePrompts方法"""
    
    def test_get_system_prompt(self):
        """测试获取系统提示"""
        prompts = ConcretePrompts()
        result = prompts.get_system_prompt()
        assert result == "You are a helpful assistant."
    
    def test_get_available_tools_prompt(self):
        """测试获取可用工具提示"""
        prompts = ConcretePrompts()
        result = prompts.get_available_tools_prompt()
        assert "read_file" in result
        assert "write_file" in result
    
    def test_get_task_prompt(self):
        """测试获取任务提示"""
        prompts = ConcretePrompts()
        result = prompts.get_task_prompt("test task")
        assert "test task" in result
        assert "Task:" in result
    
    def test_get_observation_prompt(self):
        """测试获取观察结果提示"""
        prompts = ConcretePrompts()
        result = prompts.get_observation_prompt("observation result")
        assert "Observation:" in result
        assert "observation result" in result
    
    def test_get_safety_reminder_default(self):
        """测试获取默认安全提醒"""
        prompts = ConcretePrompts()
        result = prompts.get_safety_reminder()
        assert result == ""
    
    def test_get_parameter_reminder_default(self):
        """测试获取默认参数提醒"""
        prompts = ConcretePrompts()
        result = prompts.get_parameter_reminder()
        assert result == ""
    
    def test_get_rollback_instructions(self):
        """测试获取回滚说明"""
        prompts = ConcretePrompts()
        result = prompts.get_rollback_instructions()
        assert "operation fails" in result.lower()
        assert "alternative approach" in result.lower()


class TestBasePromptsBuildFullSystemPrompt:
    """测试BasePrompts构建完整系统提示"""
    
    def test_build_full_system_prompt(self):
        """测试构建完整系统提示"""
        prompts = ConcretePrompts()
        result = prompts.build_full_system_prompt()
        
        # 包含系统提示
        assert "helpful assistant" in result
        # 包含工具列表
        assert "read_file" in result
        # 包含回滚说明
        assert "operation fails" in result.lower()
    
    def test_build_full_system_prompt_with_safety(self):
        """测试带安全提醒的完整系统提示"""
        class SafetyPrompts(ConcretePrompts):
            def get_safety_reminder(self) -> str:
                return "Safety: Be careful with file operations."
        
        prompts = SafetyPrompts()
        result = prompts.build_full_system_prompt()
        
        assert "Safety:" in result
        assert "Be careful" in result
    
    def test_build_full_system_prompt_with_parameter_reminder(self):
        """测试带参数提醒的完整系统提示"""
        class ParamPrompts(ConcretePrompts):
            def get_parameter_reminder(self) -> str:
                return "Parameters: Use correct parameter names."
        
        prompts = ParamPrompts()
        result = prompts.build_full_system_prompt()
        
        assert "Parameters:" in result
        assert "correct parameter names" in result


class TestBasePromptsInheritance:
    """测试BasePrompts继承"""
    
    def test_file_prompts_inherits_base(self):
        """测试FileOperationPrompts继承BasePrompts"""
        from app.services.prompts.file.file_prompts import FileOperationPrompts
        from app.services.prompts.BasePromptTemplate import BasePrompts
        
        assert issubclass(FileOperationPrompts, BasePrompts)
    
    def test_file_prompts_implements_abstract_methods(self):
        """测试FileOperationPrompts实现抽象方法"""
        from app.services.prompts.file.file_prompts import FileOperationPrompts
        
        prompts = FileOperationPrompts()
        
        # 应该可以调用抽象方法
        system_prompt = prompts.get_system_prompt()
        assert system_prompt is not None
        assert len(system_prompt) > 0
        
        tools_prompt = prompts.get_available_tools_prompt()
        assert tools_prompt is not None
