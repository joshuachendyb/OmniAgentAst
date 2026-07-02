"""
第2波对抗性测试 — 覆盖react_cycle/error_handler/retry_engine等剩余路径
"""
import asyncio
import pytest
from typing import Dict, Any


# =============================================================================
# react_cycle — 核心函数
# =============================================================================

class TestShouldRetryTruncatedTool:
    def test_not_answer_type(self):
        from app.services.agent.core_agent.react_cycle import _should_retry_truncated_tool
        agent = _make_truncation_agent([])
        assert not _should_retry_truncated_tool(agent, {"type": "action", "content": "x"})

    def test_empty_content(self):
        from app.services.agent.core_agent.react_cycle import _should_retry_truncated_tool
        agent = _make_truncation_agent([])
        assert not _should_retry_truncated_tool(agent, {"type": "answer", "content": ""})

    def test_long_content(self):
        from app.services.agent.core_agent.react_cycle import _should_retry_truncated_tool
        agent = _make_truncation_agent([])
        assert not _should_retry_truncated_tool(agent, {"type": "answer", "content": "x" * 501})

    def test_no_tool_calls_in_history(self):
        from app.services.agent.core_agent.react_cycle import _should_retry_truncated_tool
        agent = _make_truncation_agent([])
        assert not _should_retry_truncated_tool(agent, {"type": "answer", "content": "hello"})

    def test_tool_already_executed(self):
        from app.services.agent.core_agent.react_cycle import _should_retry_truncated_tool
        history = [
            {"role": "assistant", "tool_calls": [{"id": "c1", "function": {"name": "r"}}], "content": ""},
            {"role": "tool", "tool_call_id": "c1", "content": "done"},
        ]
        agent = _make_truncation_agent(history)
        assert not _should_retry_truncated_tool(agent, {"type": "answer", "content": "ok"})

    def test_tool_not_executed_triggers_retry(self):
        from app.services.agent.core_agent.react_cycle import _should_retry_truncated_tool
        history = [
            {"role": "assistant", "tool_calls": [{"id": "c1", "function": {"name": "r"}}], "content": ""},
        ]
        agent = _make_truncation_agent(history)
        assert _should_retry_truncated_tool(agent, {"type": "answer", "content": "ok"})


class TestEnsureFailedFinalStep:
    def test_not_failed_returns_none(self):
        from app.services.agent.core_agent.react_cycle import _ensure_failed_final_step
        from app.services.agent.types import AgentStatus
        agent = _make_agent_with_steps([])
        agent.status = AgentStatus.COMPLETED
        assert _ensure_failed_final_step(agent) is None

    def test_failed_without_errors(self):
        from app.services.agent.core_agent.react_cycle import _ensure_failed_final_step
        from app.services.agent.types import AgentStatus
        agent = _make_agent_with_steps([])
        agent.status = AgentStatus.FAILED
        result = _ensure_failed_final_step(agent)
        assert result is not None
        # response="" 触发前端空响应守卫 — 小欧 2026-06-30
        assert result.response == ""

    def test_failed_with_error_message(self):
        from app.services.agent.core_agent.react_cycle import _ensure_failed_final_step
        from app.services.agent.types import AgentStatus
        from app.services.agent.steps import ErrorStep
        err = ErrorStep(step=0, error_type="crash", error_message="磁盘空间不足")
        agent = _make_agent_with_steps([err])
        agent.status = AgentStatus.FAILED
        result = _ensure_failed_final_step(agent)
        # response="" 触发前端空响应守卫 — 小欧 2026-06-30
        assert result.response == ""

    def test_failed_step_has_no_error_message(self):
        from app.services.agent.core_agent.react_cycle import _ensure_failed_final_step
        from app.services.agent.types import AgentStatus
        agent = _make_agent_with_steps([{"type": "thought", "step": 0}])
        agent.status = AgentStatus.FAILED
        result = _ensure_failed_final_step(agent)
        assert result is not None


class TestDispatchHandler:
    @pytest.mark.asyncio
    async def test_unknown_type_no_content(self):
        from app.services.agent.core_agent.react_cycle import _dispatch_handler
        agent = _make_truncation_agent([])
        agent.llm_call_count = 1
        events = []
        async for ev in _dispatch_handler(agent, {"type": "unknown_type", "content": ""}, None):
            events.append(ev)
        # 未知类型应设FAILED
        assert len(events) >= 1

    @pytest.mark.asyncio
    async def test_unknown_type_with_content(self):
        from app.services.agent.core_agent.react_cycle import _dispatch_handler
        agent = _make_truncation_agent([])
        agent.llm_call_count = 1
        events = []
        async for ev in _dispatch_handler(agent, {"type": "unknown_type", "content": "invalid response"}, None):
            events.append(ev)
        assert len(events) >= 1


# =============================================================================
# error_handler — 全路径覆盖
# =============================================================================

class TestErrorHandler:
    def test_unknown_error(self):
        from app.services.agent.core_agent.react_cycle import handle_react_error
        agent = _make_error_agent()
        step = handle_react_error(agent, ValueError("bad value"), 5)
        assert step.error_type == "unknown"
        assert step.recoverable is False

    def test_fc_format_error(self):
        from app.services.agent.core_agent.react_cycle import handle_react_error
        from app.services.llm.core import FCFormatError
        agent = _make_error_agent()
        step = handle_react_error(agent, FCFormatError(message="format fail"), 3)
        assert step.error_type == "unknown"
        assert step.recoverable is True  # FCFormatError为可恢复错误(系统重试层优化)

    def test_classify_unknown(self):
        from app.utils.sys_error_classifier import SystemErrorClassifier, SystemErrorCategory
        assert SystemErrorClassifier.classify_error(RuntimeError("something")) == SystemErrorCategory.UNKNOWN


class TestFinalizeCycle:
    def test_finalize_cycle_ok(self):
        from app.services.agent.core_agent.react_cycle import _finalize_cycle
        agent = _make_finalize_agent()
        # 不应崩溃
        _finalize_cycle(agent)

    def test_finalize_cycle_failed(self):
        from app.services.agent.core_agent.react_cycle import _finalize_cycle
        agent = _make_finalize_agent()
        agent.status = "FAILED"
        _finalize_cycle(agent)


# =============================================================================
# ChunkBuffer — 边界条件
# =============================================================================

class TestChunkBufferAdversarial:
    def test_append_empty_string(self):
        from app.services.agent.chunk_buffer import ChunkBuffer
        cb = ChunkBuffer(max_consecutive=5)
        cb.append("")
        assert cb.buffer == ""
        assert cb.consecutive_count == 1

    def test_append_none(self):
        from app.services.agent.chunk_buffer import ChunkBuffer
        cb = ChunkBuffer(max_consecutive=5)
        with pytest.raises(TypeError):
            cb.append(None)

    def test_should_promote_exact_threshold(self):
        from app.services.agent.chunk_buffer import ChunkBuffer
        cb = ChunkBuffer(max_consecutive=3)
        cb.append("a")
        cb.append("b")
        cb.append("c")
        assert cb.should_promote()

    def test_should_promote_under_threshold(self):
        from app.services.agent.chunk_buffer import ChunkBuffer
        cb = ChunkBuffer(max_consecutive=5)
        cb.append("a")
        cb.append("b")
        assert not cb.should_promote()

    def test_should_force_stop_exact(self):
        from app.services.agent.chunk_buffer import ChunkBuffer
        cb = ChunkBuffer(max_consecutive=5, max_without_promote=10)
        for i in range(10):
            cb.append(str(i))
        assert cb.should_force_stop()

    def test_flush_and_clear(self):
        from app.services.agent.chunk_buffer import ChunkBuffer
        cb = ChunkBuffer(max_consecutive=5)
        cb.append("hello ")
        cb.append("world")
        content = cb.flush()
        assert content == "hello world"
        assert cb.buffer == ""
        assert cb.consecutive_count == 0

    def test_clear_empty(self):
        from app.services.agent.chunk_buffer import ChunkBuffer
        cb = ChunkBuffer()
        cb.clear()
        assert cb.buffer == ""
        assert cb.consecutive_count == 0


# =============================================================================
# initialize_run_state — 边界
# =============================================================================

class TestInitializeRunState:
    def _make_inject_agent(self):
        mb = _make_mb()
        agent = type("MockAgent", (), {
            "message_builder": mb,
        })()
        return agent, mb

    def test_inject_conversation_history_none(self):
        from app.services.agent.core_agent.initialize_run_state import _inject_conversation_history
        agent, mb = self._make_inject_agent()
        _inject_conversation_history(agent, None)
        assert len(mb.conversation_history) == 0

    def test_inject_empty_prev(self):
        from app.services.agent.core_agent.initialize_run_state import _inject_conversation_history
        agent, mb = self._make_inject_agent()
        _inject_conversation_history(agent, {"previous_messages": []})
        assert len(mb.conversation_history) == 0

    def test_inject_tool_message(self):
        from app.services.agent.core_agent.initialize_run_state import _inject_conversation_history
        agent, mb = self._make_inject_agent()
        _inject_conversation_history(agent, {"previous_messages": [
            {"role": "tool", "tool_call_id": "c1", "content": "result"},
        ]})
        assert len(mb.conversation_history) == 1
        assert mb.conversation_history[0]["role"] == "tool"

    def test_inject_assistant_with_tool_calls(self):
        from app.services.agent.core_agent.initialize_run_state import _inject_conversation_history
        agent, mb = self._make_inject_agent()
        _inject_conversation_history(agent, {"previous_messages": [
            {"role": "assistant", "tool_calls": [{"id": "c1"}], "content": ""},
        ]})
        assert len(mb.conversation_history) == 1
        assert "tool_calls" in mb.conversation_history[0]

    def test_inject_assistant_without_tool_calls(self):
        from app.services.agent.core_agent.initialize_run_state import _inject_conversation_history
        agent, mb = self._make_inject_agent()
        _inject_conversation_history(agent, {"previous_messages": [
            {"role": "assistant", "content": "answer"},
        ]})
        assert len(mb.conversation_history) == 1
        assert mb.conversation_history[0]["content"] == "answer"

    def test_inject_assistant_no_content_no_tc(self):
        from app.services.agent.core_agent.initialize_run_state import _inject_conversation_history
        agent, mb = self._make_inject_agent()
        # 既无tool_calls也无content → 被跳过
        _inject_conversation_history(agent, {"previous_messages": [
            {"role": "assistant", "content": ""},
        ]})
        assert len(mb.conversation_history) == 0


# =============================================================================
# FC格式错误处理 — error_handler
# =============================================================================

class TestFCFormatError:
    def test_fc_format_error_sets_failed(self):
        from app.services.agent.core_agent.react_cycle import handle_react_error
        from app.services.llm.core import FCFormatError
        agent = _make_error_agent()
        step = handle_react_error(agent, FCFormatError(message="bad"), 2)
        assert step.error_type == "unknown"
        assert step.recoverable is True  # FCFormatError为可恢复错误(系统重试层优化)


# =============================================================================
# _classify_messages — 空列表/混合
# =============================================================================

class TestClassifyMessages:
    def test_empty(self):
        from app.services.agent.message_builder import MessageBuilder
        mb = MessageBuilder()
        result = mb._classify_messages()
        assert result == ([], [], [], [])

    def test_all_types(self):
        from app.services.agent.message_builder import MessageBuilder
        mb = MessageBuilder()
        mb.conversation_history = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "usr"},
            {"role": "assistant", "content": "asst"},
            {"role": "tool", "tool_call_id": "c1", "content": "tool"},
        ]
        sys, usr, obs, asst = mb._classify_messages()
        assert len(sys) == 1
        assert len(usr) == 1
        assert len(obs) == 1
        assert len(asst) == 1


# =============================================================================
# _append_observation — 各种fc_context情况
# =============================================================================

class TestAppendObservation:
    def test_with_tool_calls_no_existing(self):
        from app.services.agent.message_builder import MessageBuilder
        mb = MessageBuilder()
        fc = {
            "tool_call_id": "c1",
            "tool_calls": [{
                "id": "c1", "type": "function",
                "function": {"name": "t", "arguments": "{}"},
            }],
        }
        mb._append_observation("obs text", fc)
        roles = [m["role"] for m in mb.conversation_history]
        assert roles == ["assistant", "tool"]

    def test_without_tool_call_id(self):
        from app.services.agent.message_builder import MessageBuilder
        mb = MessageBuilder()
        fc = {"tool_call_id": "", "tool_calls": []}
        mb._append_observation("obs text", fc)
        roles = [m["role"] for m in mb.conversation_history]
        assert roles == ["assistant", "tool"]

    def test_with_llm_content(self):
        from app.services.agent.message_builder import MessageBuilder
        mb = MessageBuilder()
        fc = {"tool_call_id": "", "tool_calls": [], "llm_content": "LLM text"}
        mb._append_observation("obs text", fc)
        asst = [m for m in mb.conversation_history if m["role"] == "assistant"][0]
        assert asst["content"] == "LLM text"


# =============================================================================
# _merge_llm_data — 完整覆盖
# =============================================================================

class TestMergeLlmDataFull:
    def test_metrics_with_different_tools(self):
        from app.services.agent.core_agent.handlers.action_handler import _merge_llm_data
        result = _merge_llm_data([
            {"metrics": {"a": 1}, "status": {"exec_code": "success"}, "action": {"tool": "read"}, "summary": "r", "duration_ms": 1},
            {"metrics": {"b": 2}, "status": {"exec_code": "success"}, "action": {"tool": "write"}, "summary": "w", "duration_ms": 2},
        ])
        assert "read.a" in result["metrics"]
        assert "write.b" in result["metrics"]

    def test_severity_ordering(self):
        from app.services.agent.core_agent.handlers.action_handler import _merge_llm_data
        result = _merge_llm_data([
            {"status": {"exec_code": "success"}, "action": {"tool": "a"}, "summary": "ok", "duration_ms": 1},
            {"status": {"exec_code": "error"}, "action": {"tool": "b"}, "summary": "err", "duration_ms": 2},
            {"status": {"exec_code": "warning"}, "action": {"tool": "c"}, "summary": "warn", "duration_ms": 3},
        ])
        # error > warning > success
        assert result["action"]["tool"] == "b"
        assert result["status"]["exec_code"] == "error"
        assert result["duration_ms"] == 3


# =============================================================================
# _parse_tool_calls — 各种JSON格式
# =============================================================================

class TestParseToolCallsAdversarial:
    def test_exec_steps_with_missing_type(self):
        from app.services.react_sse_wrapper.run_sse_stream import _parse_tool_calls
        result = _parse_tool_calls(1, '[{"step": 0, "tool_name": "read", "tool_params": {}}]')
        # 缺type字段，不匹配action_tool
        assert len(result) == 0

    def test_exec_steps_with_extra_fields(self):
        from app.services.react_sse_wrapper.run_sse_stream import _parse_tool_calls
        result = _parse_tool_calls(1, '[{"type": "action_tool", "tool_name": "read", "tool_params": {"file": "x"}}]')
        assert len(result) == 1
        assert "file" in result[0]["function"]["arguments"]


# =============================================================================
# _normalize_observation_prefix — 全部边界
# =============================================================================

class TestNormalizeObsFull:
    def test_prefix_with_newline(self):
        from app.services.agent.message_builder import MessageBuilder
        result = MessageBuilder._normalize_observation_prefix("Observation:\ndetail")
        assert result.startswith("[Observation]")

    def test_multiple_colon_prefixes(self):
        from app.services.agent.message_builder import MessageBuilder
        result = MessageBuilder._normalize_observation_prefix("Observation: observation: text")
        assert result.startswith("[Observation]")


# =============================================================================
# _build_call_list — P1-10/P1-11覆盖
# =============================================================================

class TestBuildCallListEdge:
    def test_tool_name_empty_but_pending_has_name(self):
        from app.services.agent.core_agent.handlers.action_handler import _build_call_list
        parsed = {
            "tool_name": "",
            "tool_params": {},
            "fc_context": {},
            "_pending_calls": [{"tool_name": "real_tool", "tool_params": {"k": "v"}, "_tool_call_id": "pc1"}],
        }
        _, _, _, _, all_calls, is_parallel = _build_call_list(parsed)
        assert len(all_calls) == 2  # 主调用(空名) + pending(有名字)

    def test_pending_call_with_null_tool_params(self):
        from app.services.agent.core_agent.handlers.action_handler import _build_call_list
        parsed = {
            "tool_name": "read",
            "tool_params": {},
            "_pending_calls": [{"tool_name": "write", "tool_params": None}],
        }
        _, _, _, _, all_calls, _ = _build_call_list(parsed)
        assert len(all_calls) == 2
        assert all_calls[1]["tool_params"] == {}


# =============================================================================
# 辅助函数
# =============================================================================

def _make_truncation_agent(history):
    from app.services.agent.types import AgentStatus
    mb = type("MockMB", (), {
        "conversation_history": history,
        "add_assistant_message": lambda self, msg: None,
    })()
    return type("MockAgent", (), {
        "message_builder": mb,
        "steps": [],
        "status": AgentStatus.IDLE,
        "llm_call_count": 0,
        "set_failed": lambda self, msg: setattr(self, "status", AgentStatus.FAILED),
        "_step_emitter": type("MockEmitter", (), {
            "emit": lambda self, s: s,
            "complete_task": lambda self, s: None,
        })(),
    })()


def _make_agent_with_steps(steps):
    from app.services.agent.types import AgentStatus
    return type("MockAgent", (), {
        "steps": steps,
        "status": AgentStatus.IDLE,
        "llm_call_count": 0,
    })()


def _make_error_agent():
    from app.services.agent.types import AgentStatus
    def _sf(self, msg):
        self.status = AgentStatus.FAILED
    return type("MockAgent", (), {
        "set_failed": _sf,
        "status": AgentStatus.IDLE,
    })()


def _make_finalize_agent():
    from app.services.agent.types import AgentStatus
    return type("MockAgent", (), {
        "_on_after_loop": lambda self: None,
        "status": AgentStatus.COMPLETED,
        "_step_emitter": type("MockEmitter", (), {
            "complete_task": lambda self, s: None,
        })(),
    })()


def _make_mb():
    def _inject_history(self, history_msgs):
        if not history_msgs:
            return
        if len(self.conversation_history) >= 2:
            self.conversation_history = self.conversation_history[:1] + history_msgs + self.conversation_history[1:]
        else:
            self.conversation_history = history_msgs + self.conversation_history
    mb_type = type("MockMB", (), {
        "conversation_history": [],
        "trim_history": lambda self: None,
        "inject_history": _inject_history,
    })
    return mb_type()
