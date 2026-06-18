"""P2: agent.steps 所有Step类测试

作者: 小健 日期: 2026-06-08
Updated: 2026-06-13 适配重构后 Step API
"""

import pytest
from app.services.agent.steps import (
    ChunkStep, ThoughtStep, ToolStep, MetaStep,
    FinalStep, ErrorStep,
)


class TestChunkStep:
    def test_create(self):
        s = ChunkStep(step=1, content="text")
        assert s.get_type() == "chunk"
        assert s.get_content() == "text"
        assert s.is_done is False

    def test_to_dict(self):
        s = ChunkStep(step=1, content="text", is_reasoning=True)
        d = s.to_dict()
        assert d["type"] == "chunk"
        assert d["step"] == 1
        assert d["content"] == "text"


class TestThoughtStep:
    def test_create(self):
        s = ThoughtStep(step=1, content="thinking")
        assert s.get_type() == "thought"
        assert "thinking" in s.get_content()

    def test_to_dict(self):
        s = ThoughtStep(step=1, content="think", tool_name="read_file")
        d = s.to_dict()
        assert d["type"] == "thought"


class TestToolStep:
    def test_create_action(self):
        s = ToolStep(step=1, tool_name="read_file", tool_params={"path": "x"},
                      summary="summary text")
        assert s.get_type() == "action_tool"
        assert s.get_content() == "summary text"

    def test_to_dict_action(self):
        s = ToolStep(step=1, tool_name="read_file", tool_params={"path": "x"},
                      summary="summary text", execution_status="success")
        d = s.to_dict()
        assert d["type"] == "action_tool"
        assert d["execution_status"] == "success"
        assert d["content"] == "summary text"

    def test_error_message_action(self):
        s = ToolStep(step=1, tool_name="read_file", tool_params={},
                      error_message="timeout")
        assert s.get_content() == "timeout"
        assert s.is_error is False

    def test_execution_result_in_to_dict(self):
        s = ToolStep(step=1, tool_name="read_file", tool_params={},
                      execution_result={"data": "value"})
        d = s.to_dict()
        assert d["execution_result"] == {"data": "value"}

    def test_create_observation(self):
        s = ToolStep(step=1, tool_name="read_file", tool_params={"path": "x"},
                      step_type="observation", observation="result")
        assert s.get_type() == "observation"
        assert s.get_content() == "result"

    def test_to_dict_observation(self):
        s = ToolStep(step=1, tool_name="read_file", tool_params={"path": "x"},
                      step_type="observation", observation="result")
        d = s.to_dict()
        assert d["type"] == "observation"
        assert "observation" in d
        obs = d["observation"]
        assert obs["tool_name"] == "read_file"
        assert obs["tool_params"] == {"path": "x"}


class TestFinalStep:
    def test_create(self):
        s = FinalStep(step=1, response="done")
        assert s.get_type() == "final"
        assert s.get_content() == "done"
        assert s.is_done is True

    def test_to_dict(self):
        s = FinalStep(step=1, response="done", thought="thinking")
        d = s.to_dict()
        assert d["response"] == "done"
        assert d["thought"] == "thinking"


class TestErrorStep:
    def test_create(self):
        s = ErrorStep(step=1, error_type="runtime_error", error_message="oops")
        assert s.get_type() == "error"
        assert "oops" in s.get_content()
        assert s.is_done is True

    def test_to_dict(self):
        s = ErrorStep(step=1, error_type="timeout", error_message="timed out", recoverable=True)
        d = s.to_dict()
        assert d["error_type"] == "timeout"
        assert d["recoverable"] is True


class TestMetaStep:
    def test_create_interrupted(self):
        s = MetaStep(step=1, type="paused", message="user paused")
        assert s.get_type() == "paused"

    def test_to_dict_interrupted(self):
        s = MetaStep(step=1, type="resumed", message="resumed by user")
        d = s.to_dict()
        assert d["type"] == "resumed"
        assert d["content"] == "resumed by user"

    def test_start_step(self):
        s = MetaStep(step=1, type="start", message="hello",
                      display_name="test", provider="openai",
                      model="gpt-4", task_id="t-001",
                      security_check={"is_safe": True})
        assert s.get_type() == "start"

    def test_start_to_dict(self):
        s = MetaStep(step=1, type="start", message="hello",
                      display_name="openai (gpt-4)", provider="openai",
                      model="gpt-4", task_id="t-001",
                      security_check={"is_safe": True})
        d = s.to_dict()
        assert d["provider"] == "openai"
        assert d["model"] == "gpt-4"
        assert d["task_id"] == "t-001"


class TestStepInheritance:
    def test_all_inherit_base(self):
        from app.services.agent.steps import ReasoningStep
        for cls in [ChunkStep, ThoughtStep, ToolStep, MetaStep,
                     FinalStep, ErrorStep]:
            assert issubclass(cls, ReasoningStep)
