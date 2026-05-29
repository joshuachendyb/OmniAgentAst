# -*- coding: utf-8 -*-
"""
Step封装类测试模块 - TDD测试驱动开发

按照第15章Step封装设计，编写测试用例：
- ReasoningStep抽象基类
- ThoughtStep类
- ActionToolStep类
- ObservationStep类
- FinalStep类
- ErrorStep类
- StepFactory工厂类

创建时间: 2026-04-17 12:05:46
作者: 小资
"""

import pytest
from typing import Any, Dict
from app.services.agent.steps import ThoughtStep, ReasoningStep, ActionToolStep, ObservationStep, ChunkStep, FinalStep, ErrorStep, StepFactory


class TestReasoningStep:
    """测试ReasoningStep抽象基类"""

    def test_reasoning_step_has_step_property(self):
        """ReasoningStep应有step属性（通过ThoughtStep验证）"""
        step = ThoughtStep(step=1, content="test")
        assert step.step == 1

    def test_reasoning_step_has_timestamp_property(self):
        """ReasoningStep应有timestamp属性（通过ThoughtStep验证）"""
        step = ThoughtStep(step=1, content="test", timestamp=1000)
        assert step.timestamp == 1000

    def test_reasoning_step_get_type_is_abstract(self):
        """ReasoningStep的get_type是抽象方法"""
        with pytest.raises(TypeError):
            ReasoningStep(step=1)

    def test_reasoning_step_get_content_is_abstract(self):
        """ReasoningStep的get_content是抽象方法"""
        with pytest.raises(TypeError):
            ReasoningStep(step=1)

    def test_reasoning_step_is_done_is_abstract(self):
        """ReasoningStep的is_done是抽象方法"""
        with pytest.raises(TypeError):
            ReasoningStep(step=1)

    def test_reasoning_step_to_dict_returns_dict(self):
        """ReasoningStep的to_dict返回字典"""
        step = ThoughtStep(step=1, content="test content")
        result = step.to_dict()
        assert isinstance(result, dict)
        assert result["type"] == "thought"
        assert result["step"] == 1

    def test_reasoning_step_repr(self):
        """ReasoningStep的__repr__返回字符串"""
        step = ThoughtStep(step=1, content="test")
        repr_str = repr(step)
        assert "ThoughtStep" in repr_str
        assert "step=1" in repr_str


class TestThoughtStep:
    """测试ThoughtStep类"""

    def test_thought_step_creation(self):
        """创建ThoughtStep"""
        step = ThoughtStep(
            step=1,
            content="I need to read the file",
            tool_name="read_file",
            tool_params={"file_path": "/test.txt"}
        )
        assert step.step == 1
        assert step.get_type() == "thought"
        assert step.get_content() == "I need to read the file"
        assert step.tool_name == "read_file"
        assert step.tool_params == {"file_path": "/test.txt"}

    def test_thought_step_has_thought_property(self):
        """ThoughtStep有thought属性"""
        step = ThoughtStep(step=1, content="content", thought="detailed thought")
        assert step.thought == "detailed thought"

    def test_thought_step_has_reasoning_property(self):
        """ThoughtStep有reasoning属性"""
        step = ThoughtStep(step=1, content="content", reasoning="reasoning process")
        assert step.reasoning == "reasoning process"

    def test_thought_step_is_done_false(self):
        """ThoughtStep的is_done返回False"""
        step = ThoughtStep(step=1, content="test")
        assert step.is_done() is False

    def test_thought_step_to_dict(self):
        """ThoughtStep的to_dict包含所有字段"""
        step = ThoughtStep(
            step=1,
            content="content",
            tool_name="read_file",
            tool_params={"path": "/test.txt"},
            thought="thought text",
            reasoning="reasoning text"
        )
        result = step.to_dict()
        assert result["type"] == "thought"
        assert result["step"] == 1
        assert result["content"] == "content"
        assert result["tool_name"] == "read_file"
        assert result["tool_params"] == {"path": "/test.txt"}
        assert result["thought"] == "thought text"
        assert result["reasoning"] == "reasoning text"

    def test_thought_step_with_empty_tool(self):
        """ThoughtStep支持空tool_name（纯思考）"""
        step = ThoughtStep(step=1, content="thinking", tool_name="", tool_params={})
        assert step.tool_name == ""
        assert step.tool_params == {}


class TestActionToolStep:
    """测试ActionToolStep类"""

    def test_action_tool_step_creation(self):
        """创建ActionToolStep"""
        step = ActionToolStep(
            step=2,
            tool_name="read_file",
            tool_params={"path": "/test.txt"},
            execution_status="success",
            summary="File read successfully",
            execution_result={"content": "file content"},
            execution_time_ms=100
        )
        assert step.step == 2
        assert step.get_type() == "action_tool"
        assert step.tool_name == "read_file"
        assert step.execution_status == "success"
        assert step.summary == "File read successfully"
        assert step.execution_result == {"content": "file content"}
        assert step.execution_time_ms == 100

    def test_action_tool_step_error_status(self):
        """ActionToolStep支持error状态"""
        step = ActionToolStep(
            step=2,
            tool_name="read_file",
            tool_params={},
            execution_status="error",
            summary="File not found",
            error_message="File not found error"
        )
        assert step.execution_status == "error"
        assert step.is_error is True

    def test_action_tool_step_warning_status(self):
        """ActionToolStep支持warning状态"""
        step = ActionToolStep(
            step=2,
            tool_name="read_file",
            tool_params={},
            execution_status="warning",
            summary="Partial success"
        )
        assert step.execution_status == "warning"
        assert step.is_error is False

    def test_action_tool_step_is_done_false(self):
        """ActionToolStep的is_done返回False"""
        step = ActionToolStep(step=1, tool_name="test", tool_params={})
        assert step.is_done() is False

    def test_action_tool_step_to_dict(self):
        """ActionToolStep的to_dict包含所有字段"""
        step = ActionToolStep(
            step=1,
            tool_name="read_file",
            tool_params={"path": "/test.txt"},
            execution_status="success",
            summary="Success",
            execution_result={"data": "content"},
            error_message="",
            action_retry_count=0,
            execution_time_ms=50
        )
        result = step.to_dict()
        assert result["type"] == "action_tool"
        assert result["step"] == 1
        assert result["tool_name"] == "read_file"
        assert result["execution_status"] == "success"
        assert result["content"] == "Success"


class TestObservationStep:
    """测试ObservationStep类"""

    def test_observation_step_creation(self):
        """创建ObservationStep"""
        step = ObservationStep(
            step=3,
            tool_name="read_file",
            tool_params={"path": "/test.txt"},
            observation="File contains: Hello World",
            return_direct=False
        )
        assert step.step == 3
        assert step.get_type() == "observation"
        assert step.observation == "File contains: Hello World"
        assert step.return_direct is False

    def test_observation_step_is_done_false(self):
        """ObservationStep的is_done返回return_direct值（False）"""
        step = ObservationStep(step=1, tool_name="test", tool_params={}, return_direct=False)
        assert step.is_done() is False

    def test_observation_step_is_done_true(self):
        """ObservationStep的is_done返回return_direct值（True）"""
        step = ObservationStep(step=1, tool_name="test", tool_params={}, return_direct=True)
        assert step.is_done() is True

    def test_observation_step_to_dict(self):
        """ObservationStep的to_dict包含所有字段"""
        step = ObservationStep(
            step=1,
            tool_name="test",
            tool_params={"path": "/test"},
            observation="result",
            return_direct=True
        )
        result = step.to_dict()
        assert result["type"] == "observation"
        assert result["step"] == 1
        assert isinstance(result["observation"], dict)
        assert result["observation"]["summary"] == "result"
        assert result["observation"]["return_direct"] is True
        assert result["observation"]["tool_name"] == "test"


class TestChunkStep:
    """测试ChunkStep类（新增）"""

    def test_chunk_step_creation(self):
        """创建ChunkStep"""
        step = ChunkStep(
            step=10,
            content="Partial LLM response...",
            is_reasoning=True
        )
        assert step.step == 10
        assert step.get_type() == "chunk"
        assert step.get_content() == "Partial LLM response..."
        assert step.is_reasoning is True

    def test_chunk_step_is_done_false(self):
        """ChunkStep的is_done返回False"""
        step = ChunkStep(step=1, content="...")
        assert step.is_done() is False

    def test_chunk_step_to_dict(self):
        """ChunkStep的to_dict包含is_reasoning字段"""
        step = ChunkStep(
            step=1,
            content="content",
            is_reasoning=False
        )
        result = step.to_dict()
        assert result["type"] == "chunk"
        assert result["content"] == "content"
        assert result["is_reasoning"] is False


class TestFinalStep:
    """测试FinalStep类"""

    def test_final_step_creation(self):
        """创建FinalStep"""
        step = FinalStep(
            step=5,
            response="The file contains: Hello World",
            thought="Based on the file content",
            model="gpt-4",
            provider="openai"
        )
        assert step.step == 5
        assert step.get_type() == "final"
        assert step.response == "The file contains: Hello World"
        assert step.thought == "Based on the file content"
        assert step.model == "gpt-4"
        assert step.provider == "openai"

    def test_final_step_is_done_true(self):
        """FinalStep的is_done返回True"""
        step = FinalStep(step=1, response="answer")
        assert step.is_done() is True

    def test_final_step_to_dict(self):
        """FinalStep的to_dict包含所有字段"""
        step = FinalStep(
            step=1,
            response="final answer",
            thought="my thought",
            model="gpt-4",
            provider="openai"
        )
        result = step.to_dict()
        assert result["type"] == "final"
        assert result["step"] == 1
        assert result["response"] == "final answer"
        assert result["thought"] == "my thought"
        assert result["model"] == "gpt-4"
        assert result["provider"] == "openai"


class TestErrorStep:
    """测试ErrorStep类"""

    def test_error_step_creation(self):
        """创建ErrorStep"""
        step = ErrorStep(
            step=6,
            error_type="parse_error",
            error_message="Failed to parse response",
            recoverable=False
        )
        assert step.step == 6
        assert step.get_type() == "error"
        assert step.error_type == "parse_error"
        assert step.error_message == "Failed to parse response"
        assert step.recoverable is False

    def test_error_step_is_done_true(self):
        """ErrorStep的is_done返回True"""
        step = ErrorStep(step=1, error_type="test", error_message="error")
        assert step.is_done() is True

    def test_error_step_to_dict(self):
        """ErrorStep的to_dict包含所有字段"""
        step = ErrorStep(
            step=1,
            error_type="empty_response",
            error_message="AI returned empty response",
            recoverable=False
        )
        result = step.to_dict()
        assert result["type"] == "error"
        assert result["step"] == 1
        assert result["error_type"] == "empty_response"
        assert result["error_message"] == "AI returned empty response"
        assert result["recoverable"] is False


class TestStepFactory:
    """测试StepFactory工厂类"""

    def test_create_thought_step(self):
        """测试create_thought_step工厂方法"""
        step = StepFactory.create_thought_step(
            step=1,
            content="I need to read a file",
            tool_name="read_file",
            tool_params={"path": "/test.txt"}
        )
        assert step.get_type() == "thought"
        assert step.step == 1
        assert step.content == "I need to read a file"
        assert step.tool_name == "read_file"

    def test_create_action_tool_step(self):
        """测试create_action_tool_step工厂方法"""
        execution_result = {
            "status": "success",
            "summary": "File read",
            "data": {"content": "hello"}
        }
        step = StepFactory.create_action_tool_step(
            step=1,
            tool_name="read_file",
            tool_params={"path": "/test.txt"},
            execution_result=execution_result,
            execution_time_ms=100
        )
        assert step.get_type() == "action_tool"
        assert step.execution_status == "success"
        assert step.summary == "File read"
        assert step.error_message == ""

    def test_create_action_tool_step_with_error_message(self):
        """测试create_action_tool_step携带错误信息 — 统一格式后error走summary"""
        execution_result = {
            "status": "error",
            "summary": "Detailed error log",
        }
        step = StepFactory.create_action_tool_step(
            step=1,
            tool_name="test_tool",
            tool_params={},
            execution_result=execution_result
        )
        assert step.execution_status == "error"
        assert step.summary == "Detailed error log"

    def test_create_action_tool_step_with_error(self):
        """测试create_action_tool_step处理错误状态"""
        execution_result = {
            "status": "error",
            "summary": "File not found",
            "data": None
        }
        step = StepFactory.create_action_tool_step(
            step=1,
            tool_name="read_file",
            tool_params={"path": "/nonexistent.txt"},
            execution_result=execution_result
        )
        assert step.execution_status == "error"
        assert step.is_error is True

    def test_create_observation_step(self):
        """测试create_observation_step工厂方法
        
        【修复 2026-04-17 小沈】
        - 修复前：execution_result = {"data": "file content"}
        - 修复后：execution_result = {"summary": "file content"}
        - 原因：遵循设计文档 15.6.4
          - observation 字段只显示精简的 summary，不是完整的 data
          - display_text = execution_result.get('summary', '') 是设计规范
        """
        # 【修复 2026-04-17 小沈】使用 summary 而不是 data
        execution_result = {"summary": "file content"}
        step = StepFactory.create_observation_step(
            step=1,
            tool_name="read_file",
            tool_params={"path": "/test.txt"},
            execution_result=execution_result,
            return_direct=False
        )
        assert step.get_type() == "observation"
        # 【修复 2026-04-17 小沈】使用 summary 字段的值
        assert step.observation == "file content"
        assert step.return_direct is False

    def test_create_final_step(self):
        """测试create_final_step工厂方法"""
        step = StepFactory.create_final_step(
            step=1,
            response="Final answer",
            thought="My thought process"
        )
        assert step.get_type() == "final"
        assert step.response == "Final answer"
        assert step.is_done() is True

    def test_create_error_step(self):
        """测试create_error_step工厂方法"""
        step = StepFactory.create_error_step(
            step=1,
            error_type="parse_error",
            error_message="Failed to parse",
            recoverable=False
        )
        assert step.get_type() == "error"
        assert step.error_type == "parse_error"
        assert step.is_done() is True

    def test_create_chunk_step(self):
        """测试create_chunk_step工厂方法（新增）"""
        step = StepFactory.create_chunk_step(
            step=1,
            content="streaming chunk",
            is_reasoning=True
        )
        assert step.get_type() == "chunk"
        assert step.get_content() == "streaming chunk"
        assert step.is_reasoning is True


class TestToolMixin:
    """测试ToolMixin混入类"""

    def test_tool_mixin_get_tool_name_safe_empty(self):
        """ToolMixin的get_tool_name_safe空值返回finish"""
        step = ThoughtStep(step=1, content="test", tool_name="", tool_params={})
        assert step.get_tool_name_safe() == "finish"

    def test_tool_mixin_get_tool_name_safe_with_name(self):
        """ToolMixin的get_tool_name_safe有值返回值"""
        step = ThoughtStep(step=1, content="test", tool_name="read_file", tool_params={})
        assert step.get_tool_name_safe() == "read_file"


class TestStepIntegration:
    """集成测试：验证Step类在实际场景中的使用"""

    def test_full_agent_flow_steps(self):
        """模拟完整Agent流程，验证steps列表"""
        
        steps = []
        
        # 1. Thought step
        thought_step = StepFactory.create_thought_step(
            step=1,
            content="I need to read a file",
            tool_name="read_file",
            tool_params={"path": "/test.txt"}
        )
        steps.append(thought_step)
        
        # 2. Action tool step
        action_step = StepFactory.create_action_tool_step(
            step=2,
            tool_name="read_file",
            tool_params={"path": "/test.txt"},
            execution_result={"status": "success", "summary": "Success", "data": "content"},
            execution_time_ms=100
        )
        steps.append(action_step)
        
        # 3. Observation step
        obs_step = StepFactory.create_observation_step(
            step=3,
            tool_name="read_file",
            tool_params={"path": "/test.txt"},
            execution_result={"data": "file content"}
        )
        steps.append(obs_step)
        
        # 4. Final step
        final_step = StepFactory.create_final_step(
            step=4,
            response="The file contains: content"
        )
        steps.append(final_step)
        
        # 验证流程
        assert len(steps) == 4
        assert steps[0].get_type() == "thought"
        assert steps[1].get_type() == "action_tool"
        assert steps[2].get_type() == "observation"
        assert steps[3].get_type() == "final"
        
        # 验证循环终止
        for step in steps:
            if step.is_done():
                assert step.get_type() in ["final", "error"]

    def test_error_flow_steps(self):
        """测试错误流程"""
        
        steps = []
        
        # Thought
        thought_step = StepFactory.create_thought_step(
            step=1,
            content="I need to read a file",
            tool_name="read_file",
            tool_params={"path": "/nonexistent.txt"}
        )
        steps.append(thought_step)
        
        # Action with error
        action_step = StepFactory.create_action_tool_step(
            step=2,
            tool_name="read_file",
            tool_params={"path": "/nonexistent.txt"},
            execution_result={"status": "error", "summary": "File not found", "data": None}
        )
        steps.append(action_step)
        
        # Error step (when max retries exceeded)
        error_step = StepFactory.create_error_step(
            step=3,
            error_type="parse_error",
            error_message="Parse failed after retries",
            recoverable=False
        )
        steps.append(error_step)
        
        # 验证错误流程
        assert len(steps) == 3
        assert steps[-1].get_type() == "error"
        assert steps[-1].is_done() is True

    def test_steps_to_dict_for_sse(self):
        """验证steps可以直接转换为SSE格式"""
        
        step = StepFactory.create_thought_step(
            step=1,
            content="test content",
            tool_name="test_tool",
            tool_params={"key": "value"}
        )
        
        # 转换为字典
        step_dict = step.to_dict()
        
        # 验证包含SSE必需的字段
        assert "type" in step_dict
        assert "step" in step_dict
        assert "timestamp" in step_dict
        assert "content" in step_dict
