"""
第?娉写鎶楁查ф试请?鈥?message_builder 前╀綑出芥暟 + step_emitter + tool_safety_checker 等?
"""
import pytest


# =============================================================================
# MessageBuilder 鈥?前╀綑出芥暟
# =============================================================================

# =============================================================================
# MessageBuilder 鈥?_trim_fc_pairs 鍜?_cap_temp_history
# =============================================================================

class TestTrimFCPairs:
    def test_empty(self):
        from app.services.agent.message_builder import MessageBuilder
        result = MessageBuilder._trim_fc_pairs([])
        assert result == []

    def test_single_user(self):
        from app.services.agent.message_builder import MessageBuilder
        result = MessageBuilder._trim_fc_pairs([
            {"role": "user", "content": "hi"},
        ])
        assert len(result) == 1

    def test_unmatched_tool_removed(self):
        from app.services.agent.message_builder import MessageBuilder
        result = MessageBuilder._trim_fc_pairs([
            {"role": "tool", "tool_call_id": "orphan", "content": "alone"},
        ])
        assert len(result) == 0  # 存ょ珛tool琚Щ闄?

    def test_unmatched_assistant_removed(self):
        from app.services.agent.message_builder import MessageBuilder
        result = MessageBuilder._trim_fc_pairs([
            {"role": "assistant", "tool_calls": [{"id": "c1"}], "content": ""},
        ])
        assert len(result) == 0  # 存ょ珛assistant琚Щ闄?

    def test_complete_pair(self):
        from app.services.agent.message_builder import MessageBuilder
        result = MessageBuilder._trim_fc_pairs([
            {"role": "assistant", "tool_calls": [{"id": "c1"}], "content": ""},
            {"role": "tool", "tool_call_id": "c1", "content": "r1"},
        ])
        assert len(result) == 2


class TestCapTempHistory:
    def test_empty(self):
        from app.services.agent.message_builder import MessageBuilder
        mb = MessageBuilder()
        mb._cap_temp_history()
        assert len(mb.conversation_history) == 0

    def test_one_message(self):
        from app.services.agent.message_builder import MessageBuilder
        mb = MessageBuilder()
        mb.conversation_history = [{"role": "user", "content": "hi"}]
        mb._cap_temp_history()
        assert len(mb.conversation_history) == 1





# =============================================================================
# Step类?鈥?输照晫鍊煎拰to_dict
# =============================================================================

class TestStepEdgeCases:
    def test_thought_step_none_content(self):
        from app.services.agent.steps import ThoughtStep
        ts = ThoughtStep(step=0, content=None)
        d = ts.to_dict()
        assert d is not None

    def test_action_step_empty_params(self):
        from app.services.agent.steps import ActionStep
        as_ = ActionStep(step=0, tool_name="read", tool_params={})
        d = as_.to_dict()
        assert d["tool_name"] == "read"

    def test_final_step_empty_response(self):
        from app.services.agent.steps import FinalStep
        fs = FinalStep(step=0, response="", thought="")
        d = fs.to_dict()
        assert d is not None

    def test_error_step_empty_message(self):
        from app.services.agent.steps import ErrorStep
        es = ErrorStep(step=0, error_type="crash", error_message="")
        d = es.to_dict()
        assert d is not None

    def test_chunk_step_content_none(self):
        from app.services.agent.steps import ChunkStep
        cs = ChunkStep(step=0, content=None)
        d = cs.to_dict()
        assert d is not None

    def test_chunk_step_empty(self):
        from app.services.agent.steps import ChunkStep
        cs = ChunkStep(step=0, content="")
        d = cs.to_dict()
        assert d["content"] == ""


# =============================================================================
# StepEmitter 鈥?输照晫误′欢
# =============================================================================


# =============================================================================
# ToolSafetyChecker 鈥?鍩虹
# =============================================================================

# =============================================================================
# ToolSafetyChecker
# =============================================================================

class TestToolSafetyChecker:
    def test_check_none_tool_name(self):
        from app.services.safety.tool_safety_checker import ToolSafetyChecker
        checker = ToolSafetyChecker()
        result = checker.check_before_execute(None, {})
        assert result is not None

    def test_check_empty_tool_name(self):
        from app.services.safety.tool_safety_checker import ToolSafetyChecker
        checker = ToolSafetyChecker()
        result = checker.check_before_execute("", {})
        assert result is not None

    def test_check_params_none(self):
        from app.services.safety.tool_safety_checker import ToolSafetyChecker
        checker = ToolSafetyChecker()
        result = checker.check_before_execute("read", None)
        assert result is not None


# =============================================================================
# FC标煎紡错误 鈥?完整瑕嗙洊
# =============================================================================
# LLM StreamParser
# =============================================================================

class TestStreamParser:
    @pytest.mark.skip(reason="parse_sse_line宸茶里死瀯绉婚櫎")
    def test_parse_empty(self):
        pass

    @pytest.mark.skip(reason="parse_sse_line宸茶里死瀯绉婚櫎")
    def test_parse_basic_data(self):
        pass

    @pytest.mark.skip(reason="parse_sse_line宸茶里死瀯绉婚櫎")
    def test_parse_no_prefix(self):
        pass

    @pytest.mark.skip(reason="parse_sse_line宸茶里死瀯绉婚櫎")
    def test_parse_done(self):
        pass

    @pytest.mark.skip(reason="parse_sse_line宸茶里死瀯绉婚櫎")
    def test_parse_empty_data(self):
        pass


# =============================================================================
# FC标煎紡错误 鈥?完整瑕嗙洊
# =============================================================================

class TestLLMResponseErrorSubclass:
    """闆嗘垚LLM的凢CFormatError 鈥?测试错误杞瑂tep通昏緫"""
    def test_error_is_exception(self):
        from app.services.llm.core import LLMResponseError
        e = LLMResponseError(message="bad fc format")
        assert isinstance(e, Exception)
        assert str(e) == "bad fc format"

    def test_error_empty_message(self):
        from app.services.llm.core import LLMResponseError
        e = LLMResponseError(message="")
        assert str(e) == ""


# =============================================================================
# SSE标煎紡鍖?鈥?输照晫鍊?
# =============================================================================

class TestFormatSSE:
    def test_none_data(self):
        from app.utils.sse_formatter import format_agent_sse
        try:
            result = format_agent_sse(None)
            assert result == ""
        except (AttributeError, TypeError):
            pass  # 名接名梔ict输撳入,我姏异常名接名?

    def test_empty_dict(self):
        from app.utils.sse_formatter import format_agent_sse
        result = format_agent_sse({})
        assert result is not None

    def test_deeply_nested(self):
        from app.utils.sse_formatter import format_agent_sse
        data = {"a": {"b": {"c": {"d": "deep"}}}}
        result = format_agent_sse(data)
        assert result is not None

    def test_list_values(self):
        from app.utils.sse_formatter import format_agent_sse
        data = {"items": [1, 2, 3]}
        result = format_agent_sse(data)
        assert result is not None

    def test_bool_values(self):
        from app.utils.sse_formatter import format_agent_sse
        data = {"flag": True, "no": False}
        result = format_agent_sse(data)
        assert result is not None

    def test_int_keys(self):
        from app.utils.sse_formatter import format_agent_sse
        data = {1: "one", 2: "two"}
        result = format_agent_sse(data)
        assert result is not None
