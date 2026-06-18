# -*- coding: utf-8 -*-
"""
Agent Step Classes 深度业务逻辑测试

覆盖 ReasoningStep 基类及所有子类：
- ReasoningStep (base)
- MetaStep (start/interrupted/paused/resumed/retrying/authorization_required)
- ToolStep (action_tool + observation)
- ChunkStep
- ThoughtStep
- FinalStep
- ErrorStep

Author: 小健 - 2026-06-09
Updated: 2026-06-13 适配重构后 Step API
"""

import pytest
from typing import Any, Dict

from app.services.agent.steps import (
    ReasoningStep, MetaStep, ToolStep, ChunkStep,
    ThoughtStep, FinalStep, ErrorStep,
)
from app.utils.time_utils import create_timestamp


class TestData:
    FIXED_TIMESTAMP = 1700000000000


# ============================================================
# 1. ReasoningStep (Base) - 抽象基类行为测试
# ============================================================

class TestReasoningStepBase:
    """ReasoningStep 抽象基类核心行为测试"""

    def test_timestamp_auto_created_on_init(self):
        step = ThoughtStep(step=1, content="test")
        assert step.timestamp > 0

    def test_timestamp_precision_is_milliseconds(self):
        step = ThoughtStep(step=1, content="test")
        assert step.timestamp >= 1_000_000_000_000

    def test_timestamp_custom_value_preserved(self):
        ts = TestData.FIXED_TIMESTAMP
        step = ThoughtStep(step=1, content="test", timestamp=ts)
        assert step.timestamp == ts

    def test_step_property_returns_correct_value(self):
        for i in range(5):
            step = ThoughtStep(step=i, content="test")
            assert step.step == i

    def test_get_type_returns_correct_type_string(self):
        assert ThoughtStep(step=1, content="t").get_type() == "thought"
        assert ToolStep(step=1, tool_name="t", tool_params={}).get_type() == "action_tool"
        assert ToolStep(step=1, tool_name="t", tool_params={}, step_type="observation").get_type() == "observation"
        assert ChunkStep(step=1, content="c").get_type() == "chunk"
        assert FinalStep(step=1, response="r").get_type() == "final"
        assert ErrorStep(step=1, error_type="err", error_message="e").get_type() == "error"
        assert MetaStep(step=1, type="interrupted", message="m").get_type() == "interrupted"
        assert MetaStep(step=1, type="start", message="um").get_type() == "start"

    def test_to_dict_includes_type_field(self):
        step = ThoughtStep(step=1, content="test")
        d = step.to_dict()
        assert d["type"] == "thought"

    def test_to_dict_includes_step_field(self):
        step = ThoughtStep(step=42, content="test")
        d = step.to_dict()
        assert d["step"] == 42

    def test_to_dict_includes_timestamp_field(self):
        step = ThoughtStep(step=1, content="test")
        d = step.to_dict()
        assert d["timestamp"] == step.timestamp

    def test_to_dict_includes_content_field(self):
        step = ThoughtStep(step=1, content="hello")
        d = step.to_dict()
        assert d["content"] == "hello"

    def test_to_dict_structure_correct(self):
        step = ThoughtStep(step=3, content="test content")
        d = step.to_dict()
        assert set(d.keys()).issuperset({"type", "step", "timestamp", "content"})

    def test_repr_contains_class_name(self):
        step = ThoughtStep(step=1, content="test")
        assert "ThoughtStep" in repr(step)

    def test_repr_contains_type(self):
        step = ThoughtStep(step=1, content="test")
        assert "thought" in repr(step)


# ============================================================
# 2. ThoughtStep - 思考步骤
# ============================================================

class TestThoughtStep:
    """ThoughtStep 业务逻辑测试"""

    def test_get_type_returns_thought(self):
        step = ThoughtStep(step=1, content="thinking")
        assert step.get_type() == "thought"

    def test_is_done_returns_false(self):
        step = ThoughtStep(step=1, content="thinking")
        assert step.is_done is False

    def test_content_stored_correctly(self):
        step = ThoughtStep(step=1, content="test content")
        assert step.get_content() == "test content"

    def test_thought_data_falls_back_to_content(self):
        step = ThoughtStep(step=1, content="default thought")
        assert step.thought == "default thought"

    def test_thought_explicit_value(self):
        step = ThoughtStep(step=1, content="summary", thought="detailed reasoning here")
        assert step.thought == "detailed reasoning here"

    def test_reasoning_stored_correctly(self):
        step = ThoughtStep(step=1, content="c", reasoning="step-by-step logic")
        assert step.reasoning == "step-by-step logic"

    def test_to_dict_includes_thought(self):
        step = ThoughtStep(step=1, content="c", thought="detailed thought")
        d = step.to_dict()
        assert d["thought"] == "detailed thought"

    def test_to_dict_includes_reasoning(self):
        step = ThoughtStep(step=1, content="c", reasoning="chain of thought")
        d = step.to_dict()
        assert d["reasoning"] == "chain of thought"

    def test_to_dict_includes_tool_name(self):
        step = ThoughtStep(step=1, content="c", tool_name="list_dir")
        d = step.to_dict()
        assert d["tool_name"] == "list_dir"

    def test_to_dict_includes_tool_params(self):
        step = ThoughtStep(step=1, content="c", tool_params={"a": 1})
        d = step.to_dict()
        assert d["tool_params"] == {"a": 1}


# ============================================================
# 3. ToolStep - 工具执行步骤 (action_tool模式)
# ============================================================

class TestToolStepActionTool:
    """ToolStep action_tool模式业务逻辑测试"""

    def test_get_type_returns_action_tool(self):
        step = ToolStep(step=1, tool_name="read", tool_params={})
        assert step.get_type() == "action_tool"

    def test_is_done_returns_false(self):
        step = ToolStep(step=1, tool_name="read", tool_params={})
        assert step.is_done is False

    def test_execution_result_in_to_dict(self):
        result = {"files": ["a.txt", "b.txt"]}
        step = ToolStep(step=1, tool_name="t", tool_params={}, execution_result=result)
        d = step.to_dict()
        assert d["execution_result"] == result

    def test_execution_result_none(self):
        step = ToolStep(step=1, tool_name="t", tool_params={}, execution_result=None)
        d = step.to_dict()
        assert d["execution_result"] is None

    def test_is_error_true_when_error(self):
        step = ToolStep(step=1, tool_name="t", tool_params={}, execution_status="error")
        assert step.is_error is True

    def test_is_error_false_when_success(self):
        step = ToolStep(step=1, tool_name="t", tool_params={}, execution_status="success")
        assert step.is_error is False

    def test_get_content_returns_summary(self):
        step = ToolStep(step=1, tool_name="t", tool_params={}, summary="done")
        assert step.get_content() == "done"

    def test_get_content_falls_back_to_error_message(self):
        step = ToolStep(step=1, tool_name="t", tool_params={}, summary="", error_message="failed")
        assert step.get_content() == "failed"

    def test_get_content_empty_when_both_empty(self):
        step = ToolStep(step=1, tool_name="t", tool_params={}, summary="", error_message="")
        assert step.get_content() == ""

    def test_to_dict_includes_all_fields(self):
        step = ToolStep(
            step=1, tool_name="read", tool_params={"path": "/x"},
            execution_status="success", summary="ok",
            execution_result={"data": 1}, error_message="",
            action_retry_count=0, execution_time_ms=50
        )
        d = step.to_dict()
        assert d["type"] == "action_tool"
        assert d["execution_status"] == "success"
        assert d["execution_result"] == {"data": 1}
        assert d["action_retry_count"] == 0
        assert d["execution_time_ms"] == 50

    def test_to_dict_has_key_fields(self):
        step = ToolStep(step=1, tool_name="t", tool_params={})
        d = step.to_dict()
        assert "execution_status" in d
        assert "execution_result" in d
        assert "action_retry_count" in d
        assert "execution_time_ms" in d


# ============================================================
# 3b. ToolStep - 工具执行步骤 (observation模式)
# ============================================================

class TestToolStepObservation:
    """ToolStep observation模式业务逻辑测试"""

    def test_get_type_returns_observation(self):
        step = ToolStep(step=1, tool_name="read", tool_params={}, step_type="observation")
        assert step.get_type() == "observation"

    def test_is_done_false_by_default(self):
        step = ToolStep(step=1, tool_name="read", tool_params={}, step_type="observation")
        assert step.is_done is False

    def test_observation_text_in_to_dict(self):
        step = ToolStep(step=1, tool_name="t", tool_params={}, step_type="observation", observation="file content here")
        obj = step.to_dict()["observation"]
        assert obj["summary"] == "file content here"

    def test_summary_in_observation(self):
        step = ToolStep(step=1, tool_name="t", tool_params={}, step_type="observation", summary="summary text")
        obj = step.to_dict()["observation"]
        assert obj["summary"] == "summary text"

    def test_error_message_in_observation(self):
        step = ToolStep(step=1, tool_name="t", tool_params={}, step_type="observation", error_message="permission denied")
        obj = step.to_dict()["observation"]
        assert "error_message" in obj
        assert obj["error_message"] == "permission denied"

    def test_code_in_to_dict(self):
        step = ToolStep(step=1, tool_name="t", tool_params={}, step_type="observation", code="E403")
        d = step.to_dict()
        assert d["code"] == "E403"

    def test_warning_in_observation(self):
        step = ToolStep(step=1, tool_name="t", tool_params={}, step_type="observation", warning="deprecated API")
        obj = step.to_dict()["observation"]
        assert "warning" in obj

    def test_attachment_in_observation(self):
        data = b"binary data"
        step = ToolStep(step=1, tool_name="t", tool_params={}, step_type="observation", attachment=data)
        obj = step.to_dict()["observation"]
        assert obj["attachment"] == data

    def test_next_actions_in_observation(self):
        actions = [{"action": "retry", "tool": "write_file"}]
        step = ToolStep(step=1, tool_name="t", tool_params={}, step_type="observation", next_actions=actions)
        obj = step.to_dict()["observation"]
        assert obj["next_actions"] == actions

    def test_get_content_returns_observation(self):
        step = ToolStep(step=1, tool_name="t", tool_params={}, step_type="observation", observation="obs text")
        assert step.get_content() == "obs text"

    def test_extra_fields_contains_observation_obj(self):
        step = ToolStep(step=1, tool_name="read_file", tool_params={"path": "/x"}, step_type="observation")
        obj = step._extra_fields()["observation"]
        assert obj["tool_name"] == "read_file"
        assert obj["tool_params"] == {"path": "/x"}

    def test_observation_summary_fallback(self):
        step = ToolStep(step=1, tool_name="t", tool_params={}, step_type="observation", observation="obs text")
        obj = step._extra_fields()["observation"]
        assert obj["summary"] == "obs text"

    def test_observation_summary_priority(self):
        step = ToolStep(step=1, tool_name="t", tool_params={}, step_type="observation", observation="obs", summary="sum")
        obj = step._extra_fields()["observation"]
        assert obj["summary"] == "obs"

    def test_observation_fallback_to_error_message(self):
        step = ToolStep(step=1, tool_name="t", tool_params={}, step_type="observation", error_message="err")
        obj = step._extra_fields()["observation"]
        assert obj["summary"] == "err"

    def test_observation_default_text(self):
        step = ToolStep(step=1, tool_name="t", tool_params={}, step_type="observation")
        obj = step._extra_fields()["observation"]
        assert obj["summary"] == "执行完成"

    def test_tool_name_unknown_default(self):
        step = ToolStep(step=1, tool_name="", tool_params={}, step_type="observation")
        obj = step._extra_fields()["observation"]
        assert obj["tool_name"] == "unknown"

    def test_tool_params_empty_dict_default(self):
        step = ToolStep(step=1, tool_name="t", tool_params=None, step_type="observation")
        obj = step._extra_fields()["observation"]
        assert obj["tool_params"] == {}

    def test_return_direct_in_observation(self):
        step = ToolStep(step=1, tool_name="t", tool_params={}, step_type="observation", return_direct=True)
        obj = step._extra_fields()["observation"]
        assert obj["return_direct"] is True

    def test_to_dict_includes_observation_nested(self):
        step = ToolStep(step=1, tool_name="read", tool_params={"p": 1}, step_type="observation")
        d = step.to_dict()
        assert "observation" in d
        assert isinstance(d["observation"], dict)

    def test_code_included_when_set(self):
        step = ToolStep(step=1, tool_name="t", tool_params={}, step_type="observation", code="E500")
        d = step.to_dict()
        assert d["code"] == "E500"

    def test_code_excluded_when_empty(self):
        step = ToolStep(step=1, tool_name="t", tool_params={}, step_type="observation")
        d = step.to_dict()
        assert "code" not in d


# ============================================================
# 5. FinalStep - 最终回答步骤
# ============================================================

class TestFinalStep:
    """FinalStep 业务逻辑测试"""

    def test_get_type_returns_final(self):
        step = FinalStep(step=1, response="done")
        assert step.get_type() == "final"

    def test_is_done_returns_true(self):
        step = FinalStep(step=1, response="done")
        assert step.is_done is True

    def test_response_stored_correctly(self):
        step = FinalStep(step=1, response="The answer is 42")
        assert step.response == "The answer is 42"

    def test_thought_stored_correctly(self):
        step = FinalStep(step=1, response="r", thought="after thought")
        assert step.thought == "after thought"

    def test_model_stored_correctly(self):
        step = FinalStep(step=1, response="r", model="gpt-4")
        assert step.model == "gpt-4"

    def test_provider_stored_correctly(self):
        step = FinalStep(step=1, response="r", provider="openai")
        assert step.provider == "openai"

    def test_is_finished_defaults_true(self):
        step = FinalStep(step=1, response="r")
        assert step.is_finished is True

    def test_is_finished_can_be_false(self):
        step = FinalStep(step=1, response="r", is_finished=False)
        assert step.is_finished is False

    def test_display_name_explicit(self):
        step = FinalStep(step=1, response="r", display_name="GPT-4 Turbo")
        assert step.display_name == "GPT-4 Turbo"

    def test_display_name_auto_from_provider_and_model(self):
        step = FinalStep(step=1, response="r", provider="openai", model="gpt-4")
        assert step.display_name == "openai (gpt-4)"

    def test_get_content_returns_response(self):
        step = FinalStep(step=1, response="final answer")
        assert step.get_content() == "final answer"

    def test_to_dict_includes_response_and_thought(self):
        step = FinalStep(step=1, response="ans", thought="t")
        d = step.to_dict()
        assert d["response"] == "ans"
        assert d["thought"] == "t"

    def test_to_dict_includes_all_final_fields(self):
        step = FinalStep(
            step=1, response="r", thought="t", model="gpt-4", provider="openai",
            is_finished=True, display_name="G4"
        )
        d = step.to_dict()
        expected_keys = {
            "type", "step", "timestamp", "content",
            "response", "thought", "model", "provider",
            "is_finished", "display_name"
        }
        assert expected_keys.issubset(d.keys())


# ============================================================
# 6. ErrorStep - 错误步骤
# ============================================================

class TestErrorStep:
    """ErrorStep 业务逻辑测试"""

    def test_get_type_returns_error(self):
        step = ErrorStep(step=1, error_type="ValueError", error_message="bad value")
        assert step.get_type() == "error"

    def test_is_done_returns_true(self):
        step = ErrorStep(step=1, error_type="err", error_message="msg")
        assert step.is_done is True

    def test_error_type_stored(self):
        step = ErrorStep(step=1, error_type="FileNotFoundError", error_message="no file")
        assert step.error_type == "FileNotFoundError"

    def test_error_message_stored(self):
        step = ErrorStep(step=1, error_type="err", error_message="disk full")
        assert step.error_message == "disk full"

    def test_recoverable_defaults_false(self):
        step = ErrorStep(step=1, error_type="err", error_message="msg")
        assert step.recoverable is False

    def test_recoverable_can_be_true(self):
        step = ErrorStep(step=1, error_type="err", error_message="msg", recoverable=True)
        assert step.recoverable is True

    def test_model_stored(self):
        step = ErrorStep(step=1, error_type="err", error_message="msg", model="gpt-4")
        assert step.model == "gpt-4"

    def test_provider_stored(self):
        step = ErrorStep(step=1, error_type="err", error_message="msg", provider="openai")
        assert step.provider == "openai"

    def test_get_content_returns_error_message(self):
        step = ErrorStep(step=1, error_type="err", error_message="msg")
        assert step.get_content() == "msg"

    def test_to_dict_includes_error_fields(self):
        step = ErrorStep(
            step=1, error_type="ValueError", error_message="bad",
            recoverable=True, model="gpt-4", provider="openai"
        )
        d = step.to_dict()
        assert d["error_type"] == "ValueError"
        assert d["error_message"] == "bad"
        assert d["recoverable"] is True

    def test_to_dict_has_base_fields(self):
        step = ErrorStep(step=2, error_type="err", error_message="msg")
        d = step.to_dict()
        assert d["type"] == "error"
        assert d["step"] == 2


# ============================================================
# 7. ChunkStep - 流式块步骤
# ============================================================

class TestChunkStep:
    """ChunkStep 业务逻辑测试"""

    def test_get_type_returns_chunk(self):
        step = ChunkStep(step=1, content="partial")
        assert step.get_type() == "chunk"

    def test_is_done_returns_false(self):
        step = ChunkStep(step=1, content="c")
        assert step.is_done is False

    def test_content_stored(self):
        step = ChunkStep(step=1, content="hello world")
        assert step.get_content() == "hello world"

    def test_is_reasoning_defaults_false(self):
        step = ChunkStep(step=1, content="c")
        assert step.is_reasoning is False

    def test_is_reasoning_can_be_true(self):
        step = ChunkStep(step=1, content="c", is_reasoning=True)
        assert step.is_reasoning is True

    def test_thought_stored(self):
        step = ChunkStep(step=1, content="c", thought="thinking...")
        assert step.thought == "thinking..."

    def test_reasoning_stored(self):
        step = ChunkStep(step=1, content="c", reasoning="because...")
        assert step.reasoning == "because..."

    def test_to_dict_includes_chunk_fields(self):
        step = ChunkStep(step=1, content="partial", is_reasoning=True, thought="th", reasoning="re")
        d = step.to_dict()
        assert d["is_reasoning"] is True
        assert d["thought"] == "th"
        assert d["reasoning"] == "re"

    def test_to_dict_has_base_fields(self):
        step = ChunkStep(step=5, content="chunk 5")
        d = step.to_dict()
        assert d["type"] == "chunk"
        assert d["step"] == 5
        assert d["content"] == "chunk 5"

    def test_to_dict_has_key_fields(self):
        step = ChunkStep(step=1, content="c", is_reasoning=True, thought="t", reasoning="r")
        d = step.to_dict()
        assert "is_reasoning" in d
        assert "thought" in d
        assert "reasoning" in d


# ============================================================
# 8. MetaStep - 运行时事件步骤
# ============================================================

class TestMetaStep:
    """MetaStep 业务逻辑测试"""

    def test_get_type_matches_meta_type(self):
        step = MetaStep(step=1, type="interrupted", message="stopped")
        assert step.get_type() == "interrupted"

    def test_is_done_returns_false_by_default(self):
        step = MetaStep(step=1, type="interrupted", message="msg")
        assert step.is_done is False

    def test_get_content_returns_message(self):
        step = MetaStep(step=1, type="interrupted", message="msg")
        assert step.get_content() == "msg"

    def test_all_event_types_supported(self):
        for val in ["interrupted", "paused", "resumed", "retrying", "authorization_required", "start"]:
            step = MetaStep(step=1, type=val, message=f"event {val}")
            assert step.get_type() == val

    def test_to_dict_includes_type_from_meta_type(self):
        step = MetaStep(step=1, type="interrupted", message="msg")
        d = step.to_dict()
        assert d["type"] == "interrupted"
        assert d["content"] == "msg"

    def test_to_dict_extra_kwargs_serialized(self):
        step = MetaStep(step=1, type="authorization_required", message="need confirm",
                         data={"tool_name": "read", "confirm_id": "abc"})
        d = step.to_dict()
        assert d["data"] == {"tool_name": "read", "confirm_id": "abc"}

    def test_start_step_shorthand(self):
        step = MetaStep(step=0, type="start", message="hello",
                         display_name="GPT-4", provider="openai", model="gpt-4",
                         task_id="task-1", security_check={"status": "passed"})
        d = step.to_dict()
        assert d["type"] == "start"
        assert d["content"] == "hello"
        assert d["display_name"] == "GPT-4"
        assert d["provider"] == "openai"
        assert d["model"] == "gpt-4"
        assert d["task_id"] == "task-1"
        assert d["security_check"] == {"status": "passed"}

    def test_to_dict_has_base_fields(self):
        step = MetaStep(step=3, type="paused", message="paused")
        d = step.to_dict()
        assert d["type"] == "paused"
        assert d["step"] == 3


# ============================================================
# 9. 时间戳跨类一致性测试
# ============================================================

class TestTimestampConsistency:
    """时间戳在各 Step 子类中的一致性验证"""

    def test_all_steps_auto_timestamp(self):
        steps = [
            ThoughtStep(step=1, content="t"),
            ToolStep(step=1, tool_name="t", tool_params={}),
            ToolStep(step=1, tool_name="t", tool_params={}, step_type="observation"),
            ChunkStep(step=1, content="c"),
            FinalStep(step=1, response="r"),
            ErrorStep(step=1, error_type="e", error_message="m"),
            MetaStep(step=1, type="interrupted", message="m"),
            MetaStep(step=1, type="start", message="u"),
        ]
        for s in steps:
            assert s.timestamp > 0

    def test_all_steps_custom_timestamp(self):
        ts = 999999999999
        steps = [
            ThoughtStep(step=1, content="t", timestamp=ts),
            ToolStep(step=1, tool_name="t", tool_params={}, timestamp=ts),
            ToolStep(step=1, tool_name="t", tool_params={}, step_type="observation", timestamp=ts),
            ChunkStep(step=1, content="c", timestamp=ts),
            FinalStep(step=1, response="r", timestamp=ts),
            ErrorStep(step=1, error_type="e", error_message="m", timestamp=ts),
            MetaStep(step=1, type="paused", message="m", timestamp=ts),
            MetaStep(step=1, type="start", message="u", timestamp=ts),
        ]
        for s in steps:
            assert s.timestamp == ts

    def test_all_steps_to_dict_contains_timestamp(self):
        steps = [
            ThoughtStep(step=1, content="t"),
            ToolStep(step=1, tool_name="t", tool_params={}),
            ToolStep(step=1, tool_name="t", tool_params={}, step_type="observation"),
            ChunkStep(step=1, content="c"),
            FinalStep(step=1, response="r"),
            ErrorStep(step=1, error_type="e", error_message="m"),
            MetaStep(step=1, type="resumed", message="m"),
            MetaStep(step=1, type="start", message="u"),
        ]
        for s in steps:
            d = s.to_dict()
            assert "timestamp" in d
            assert d["timestamp"] == s.timestamp


# ============================================================
# 10. to_dict 完整性汇总测试
# ============================================================

class TestToDictCompleteness:
    """to_dict() 方法完整性测试"""

    def test_all_to_dict_have_type_step_timestamp_content(self):
        steps = [
            ThoughtStep(step=1, content="t"),
            ToolStep(step=1, tool_name="t", tool_params={}),
            ToolStep(step=1, tool_name="t", tool_params={}, step_type="observation"),
            ChunkStep(step=1, content="c"),
            FinalStep(step=1, response="r"),
            ErrorStep(step=1, error_type="e", error_message="m"),
            MetaStep(step=1, type="retrying", message="m"),
            MetaStep(step=1, type="start", message="u"),
        ]
        required = {"type", "step", "timestamp", "content"}
        for s in steps:
            d = s.to_dict()
            assert required.issubset(d.keys())

    def test_tool_step_to_dict_count_action(self):
        step = ToolStep(step=1, tool_name="read", tool_params={"p": 1})
        d = step.to_dict()
        assert len(d) >= 7

    def test_final_step_to_dict_count(self):
        step = FinalStep(step=1, response="r")
        d = step.to_dict()
        assert len(d) >= 8

    def test_error_step_to_dict_count(self):
        step = ErrorStep(step=1, error_type="e", error_message="m")
        d = step.to_dict()
        assert len(d) >= 6

    def test_chunk_step_to_dict_count(self):
        step = ChunkStep(step=1, content="c")
        d = step.to_dict()
        assert len(d) >= 5

    def test_thought_step_to_dict_count(self):
        step = ThoughtStep(step=1, content="c")
        d = step.to_dict()
        assert len(d) >= 7
