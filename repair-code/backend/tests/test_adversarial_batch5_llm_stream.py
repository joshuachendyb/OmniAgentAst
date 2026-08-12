"""test"""
import asyncio
import json
import pytest


# =============================================================================
# _build_tool_calls_response 鈥?对案姉鎬ц緭鍏?
# =============================================================================

class TestBuildToolCallsResponse:
    """test"""

    def _agent(self):
        return type("MockAgent", (), {
            "llm_call_count": 1,
            "_prompt_logger": None,
        })()

    def test_tool_params_none(self):
        """tool params none"""
        from app.services.agent.llm_stream import _build_tool_calls_response
        agent = self._agent()
        result = [
            {"tool_name": "search", "tool_params": None, "tool_call_id": "c1",
             "tool_calls": [{"name": "search"}]}
        ]
        tag, data = _build_tool_calls_response("ok", result, None, agent)
        assert tag == "response"
        assert data["type"] == "action", f"expected action, got {data['type']}"
        assert data["tool_params"] == {}, f"None should downgrade to {{}}, got {data['tool_params']}"

    def test_tool_call_id_is_none(self):
        """tool call id is none"""
        from app.services.agent.llm_stream import _build_tool_calls_response
        agent = self._agent()
        result = [
            {"tool_name": "search", "tool_params": {}, "tool_call_id": None,
             "tool_calls": [{"name": "search"}]}
        ]
        tag, data = _build_tool_calls_response("ok", result, None, agent)
        assert data["tool_call_id"] == "", f"未熸湜'', 实际={data['tool_call_id']!r}"

    def test_parallel_tool_params_none(self):
        """parallel tool params none"""
        from app.services.agent.llm_stream import _build_tool_calls_response
        agent = self._agent()
        result = [
            {"tool_name": "f1", "tool_params": {}, "tool_call_id": "c1",
             "tool_calls": [{"name": "f1"}]},
            {"tool_name": "f2", "tool_params": None, "tool_call_id": "c2",
             "tool_calls": [{"name": "f2"}]},
        ]
        tag, data = _build_tool_calls_response("ok", result, None, agent)
        assert tag == "response"
        assert data["type"] == "action", f"未熸湜action(闄嶇骇), 实际={data['type']}"
        assert data["_pending_calls"][0]["tool_params"] == {}, "pending_calls的凬one搴旈檷绾т为{}"

    def test_parallel_tool_call_id_none(self):
        """parallel tool call id none"""
        from app.services.agent.llm_stream import _build_tool_calls_response
        agent = self._agent()
        result = [
            {"tool_name": "f1", "tool_params": {}, "tool_call_id": "c1",
             "tool_calls": [{"name": "f1"}]},
            {"tool_name": "f2", "tool_params": {}, "tool_call_id": None,
             "tool_calls": [{"name": "f2"}]},
        ]
        tag, data = _build_tool_calls_response("ok", result, None, agent)
        pc = data["_pending_calls"][0]
        assert pc["_tool_call_id"] == "", f"未熸湜'', 实际={pc['_tool_call_id']!r}"

    def test_missing_all_keys(self):
        """missing all keys"""
        from app.services.agent.llm_stream import _build_tool_calls_response
        agent = self._agent()
        result = [
            {"tool_name": "f1", "tool_params": {}, "tool_call_id": "c1",
             "tool_calls": [None, "str", 123, {"name": "valid"}]}
        ]
        tag, data = _build_tool_calls_response("ok", result, None, agent)
        # Bug D修复: 死数据key"tool_calls"已删除，只保留fc_context.tool_calls — 小沈 2026-07-06
        assert len(data["fc_context"]["tool_calls"]) == 1

    def test_empty_full_content(self):
        """empty full content"""
        from app.services.agent.llm_stream import _build_tool_calls_response
        agent = self._agent()
        result = [
            {"tool_name": "f1", "tool_params": {}, "tool_call_id": "c1",
             "tool_calls": [{"name": "f1"}]}
        ]
        tag, data = _build_tool_calls_response("ok", result, None, agent)
        assert data["type"] == "action"


# =============================================================================
# _build_answer_response 鈥?对案姉鎬ц緭鍏?
# =============================================================================

class TestBuildAnswerResponse:
    def _agent(self):
        return type("MockAgent", (), {
            "llm_call_count": 1,
            "_prompt_logger": None,
        })()

    def test_empty_content(self):
        from app.services.agent.llm_stream import _build_answer_response
        agent = self._agent()
        tag, data = _build_answer_response("", "", None, agent)
        assert tag == "response"
        assert data["content"] == ""
        assert data.get("reasoning", "") == ""

    def test_usage_data_none(self):
        from app.services.agent.llm_stream import _build_answer_response
        agent = self._agent()
        tag, data = _build_answer_response("hello", "", None, agent)
        assert tag == "response"
        assert data["content"] == "hello"

    def test_long_content(self):
        from app.services.agent.llm_stream import _build_answer_response
        agent = self._agent()
        long = "x" * 100000
        tag, data = _build_answer_response(long, "", {"total_tokens": 100000}, agent)
        assert data["content"] == long

    def test_special_chars(self):
        from app.services.agent.llm_stream import _build_answer_response
        agent = self._agent()
        s = "中件/English/emoji馃槉/\"quotes\"/<html>"
        tag, data = _build_answer_response(s, "", None, agent)
        assert data["content"] == s


# =============================================================================
# _yield_error_response 鈥?对案姉鎬ц緭鍏?
# =============================================================================

class TestYieldErrorResponse:
    def _agent(self):
        return type("MockAgent", (), {
            "llm_call_count": 1,
            "_prompt_logger": None,
        })()

    def test_empty_msg(self):
        from app.services.agent.llm_stream import _yield_error_response
        agent = self._agent()
        tag, data = _yield_error_response("", agent)
        assert tag == "response"
        assert data["content"] == ""

    def test_long_msg(self):
        from app.services.agent.llm_stream import _yield_error_response
        agent = self._agent()
        long_msg = "x" * 5000
        tag, data = _yield_error_response(long_msg, agent)
        assert data["content"] == long_msg


# =============================================================================
# call_llm_stream 鈥?async用熸垚鍣ㄥ鎶楁查у満鏅紙mock LLM client,?
# =============================================================================

class MockAsyncStream:
    """MockAsyncStream"""
    def __init__(self, chunks):
        self._chunks = list(chunks)
        self._i = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._i >= len(self._chunks):
            raise StopAsyncIteration
        c = self._chunks[self._i]
        self._i += 1
        return c


def _make_chunk(content=None, tool_calls=None, stream_error=None,
                is_done=False, usage=None, is_reasoning=False):
    """create a mock chunk object"""
    from unittest.mock import MagicMock
    chunk = MagicMock()
    chunk.content = content
    chunk.tool_calls = tool_calls
    chunk.stream_error = stream_error
    chunk.is_done = is_done
    chunk.usage = usage
    chunk.is_reasoning = is_reasoning
    return chunk


def _make_stream_agent(chunks):
    """create a mock agent with mocked llm_client returning MockAsyncStream"""
    from unittest.mock import MagicMock
    client = MagicMock()
    client.request_stream = MagicMock(return_value=MockAsyncStream(chunks))
    client._cancelled = False
    return type("MockAgent", (), {
        "llm_call_count": 1,
        "llm_client": client,
        "_prompt_logger": None,
    })()


# =============================================================================
# call_llm_with_fallback 鈥?FC闄嶇骇在写櫙
# =============================================================================

class TestCallLlmWithFallback:
    """TestCallLlmWithFallback"""

    @pytest.mark.asyncio
    async def test_fc_success_first_attempt(self):
        """fc success first attempt"""
        from app.services.agent.llm_stream import call_llm_with_fallback as _fb
        agent = _make_stream_agent([
            _make_chunk(content="ok", is_done=True, usage={"total_tokens": 5}),
        ])
        items = [it async for it in _fb(agent, [], [{"name": "test"}])]
        tag, data = items[-1]
        assert data["content"] == "ok"

    @pytest.mark.asyncio
    async def test_fc_retry_then_success(self):
        """fc retry then success"""
        from app.services.agent.llm_stream import call_llm_with_fallback as _fb
        from app.services.llm.core import LLMResponseError
        call_count = [0]

        class FailThenOKStream:
            def __init__(self):
                self._chunks = [_make_chunk(content="ok", is_done=True, usage={"total_tokens": 3})]
                self._i = 0
            def __aiter__(self):
                call_count[0] += 1; self._i = 0
                return self
            async def __anext__(self):
                if call_count[0] <= 2:
                    raise LLMResponseError(message="parse failed")
                if self._i >= len(self._chunks):
                    raise StopAsyncIteration
                c = self._chunks[self._i]; self._i += 1
                return c

        from unittest.mock import MagicMock
        client = MagicMock()
        client.request_stream = MagicMock(return_value=FailThenOKStream())
        agent = type("MockAgent", (), {
            "llm_call_count": 1, "llm_client": client,
            "_prompt_logger": None,
        })()
        items = [it async for it in _fb(agent, [], [{"name": "test"}])]
        tag, data = items[-1]
        assert data["content"] == "ok"

    @pytest.mark.asyncio
    async def test_fc_all_retries_fail_then_fallback_to_text(self):
        """fc all retries fail then fallback to text"""
        from app.services.agent.llm_stream import call_llm_with_fallback as _fb
        from app.services.llm.core import LLMResponseError
        from app.constants import LLM_RESPONSE_RETRIES
        call_count = [0]

        class AlwaysFailThenOK:
            def __init__(self):
                self._chunks = [_make_chunk(content="fallback_ok", is_done=True, usage={"total_tokens": 3})]
                self._i = 0
                self._is_text = False
            def __aiter__(self):
                call_count[0] += 1; self._i = 0
                self._is_text = call_count[0] > LLM_RESPONSE_RETRIES
                return self
            async def __anext__(self):
                if not self._is_text:
                    raise LLMResponseError(message="always fail")
                if self._i >= len(self._chunks):
                    raise StopAsyncIteration
                c = self._chunks[self._i]; self._i += 1
                return c

        from unittest.mock import MagicMock
        client = MagicMock()
        client.request_stream = MagicMock(return_value=AlwaysFailThenOK())
        agent = type("MockAgent", (), {
            "llm_call_count": 1, "llm_client": client,
            "_prompt_logger": None,
        })()
        items = [it async for it in _fb(agent, [], [{"name": "test"}])]
        tag, data = items[-1]
        assert data["content"] == "fallback_ok"
