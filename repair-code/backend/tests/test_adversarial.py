# 编辑历史: 2026-07-18 小健 修正record_operation签名(新增operation_id) 对齐当前实现
"""test"""
import json
import pytest


# =============================================================================
# SSE标煎紡鍖栧櫒 鈥?息舵剰输撳入
# =============================================================================

class TestSseFormatterAdversarial:
    def test_none_data(self):
        from app.utils.sse_formatter import format_sse_event
        with pytest.raises((TypeError, AttributeError)):
            format_sse_event("test", 0, None)

    def test_empty_step_dict_no_type(self):
        from app.utils.sse_formatter import format_agent_sse
        result = format_agent_sse({})
        assert result == ""

    def test_step_dict_with_tool_calls_none(self):
        from app.utils.sse_formatter import format_agent_sse
        d = {"type": "thought", "step": 1, "tool_calls": None}
        result = format_agent_sse(d)
        assert result.startswith("data:")

    def test_sse_oversized_data(self):
        from app.utils.sse_formatter import format_sse_event
        d = {"key": "x" * 100000}
        result = format_sse_event("test", 0, d)
        assert result.startswith("data:")

    def test_sse_recursive_structure(self):
        from app.utils.sse_formatter import format_sse_event
        d = {}
        d["self"] = d
        result = format_sse_event("test", 0, d)
        assert result.startswith("data:")

    def test_format_agent_no_step(self):
        from app.utils.sse_formatter import format_agent_sse
        d = {"type": "final", "response": "hello"}
        result = format_agent_sse(d)
        assert "step" in json.loads(result[5:].strip())


# =============================================================================
# Observation标煎紡鍖栧櫒 鈥?息舵剰数据
# =============================================================================

class TestObservationFormatterAdversarial:
    def test_data_is_none(self):
        from app.services.agent.observation_formatter import format_llm_observation
        result = format_llm_observation(None, {"status": {"exec_code": "success"}, "action": {}, "summary": "ok"})
        assert isinstance(result, str)

    def test_data_has_no_valid_keys(self):
        from app.services.agent.observation_formatter import format_data_detail
        result = format_data_detail({"unknown_key": "value"})
        assert isinstance(result, str)

    def test_data_with_circular_ref(self):
        from app.services.agent.observation_formatter import format_data_detail
        d = {"key": "value"}
        d["self"] = d
        result = format_data_detail(d)
        assert isinstance(result, str)

    def test_llm_data_missing_status(self):
        from app.services.agent.observation_formatter import format_llm_observation
        result = format_llm_observation({}, {})
        assert isinstance(result, str)

    def test_table_row_type_mismatch(self):
        from app.services.agent.observation_formatter import _format_table
        result = _format_table(["a", "b", "c"], [{"x": 1, "y": 2}])
        assert isinstance(result, str)

    def test_items_with_circular(self):
        from app.services.agent.observation_formatter import _format_items
        item = {"name": "test"}
        item["self"] = item
        result = _format_items([item])
        assert isinstance(result, str)

    def test_format_llm_empty_action_with_summary(self):
        from app.services.agent.observation_formatter import format_llm_observation
        r = format_llm_observation(None, {"status": {"exec_code": "success"}, "action": {}, "summary": "ok"})
        # 旧版: assert "结果:" in r — 小沈 2026-07-06 精简改版去掉"结果:"行
        assert "观察:" in r
        assert "ok" in r

    def test_format_key_value_with_nested(self):
        from app.services.agent.observation_formatter import format_data_detail
        r = format_data_detail({"a": {"b": 1, "c": 2}, "d": [1, 2, 3], "e": "simple"})
        assert "a:" in r
        assert "d:" in r
        assert "e: simple" in r


# =============================================================================
# Steps 鈥?缂哄け存楁/None鍊?# =============================================================================

class TestStepsAdversarial:
    def test_step_no_content(self):
        from app.services.agent.steps import ThoughtStep, FinalStep, ChunkStep
        t = ThoughtStep(step=0, content="")
        assert "content" in t.to_dict()
        f = FinalStep(step=0, response="")
        d2 = f.to_dict()
        assert "content" in d2
        c = ChunkStep(step=0, content="")
        d3 = c.to_dict()
        assert "content" in d3

    def test_meta_step_empty_message(self):
        from app.services.agent.steps import MetaStep
        m = MetaStep(step=0, type="start", message="")
        assert m.to_dict()["type"] == "start"

    def test_meta_step_with_kwargs_none(self):
        from app.services.agent.steps import MetaStep
        m = MetaStep(step=0, type="authorization_required", message="confirm",
                     data={"confirm_id": None, "tool_name": None, "params": None})
        d = m.to_dict()
        assert d["data"]["confirm_id"] is None

    def test_action_step_null_params(self):
        from app.services.agent.steps import ActionStep
        a = ActionStep(step=1, tool_name="test", tool_params=None)
        d = a.to_dict()
        assert d["tool_params"] == {}

    def test_observation_step_null_llm_data(self):
        from app.services.agent.steps import ObservationStep
        o = ObservationStep(step=1, llm_data=None, tool_result=None, other_data=None)
        assert isinstance(o.to_dict(), dict)

    def test_error_step_no_message(self):
        from app.services.agent.steps import ErrorStep
        e = ErrorStep(step=0, error_type="crash", error_message="")
        assert e.to_dict()["error_message"] == ""

    def test_final_step_with_display_name(self):
        from app.services.agent.steps import FinalStep
        f = FinalStep(step=0, response="ok", model=None, provider=None)
        assert "display_name" in f.to_dict()

    def test_action_step_get_content(self):
        from app.services.agent.steps import ActionStep
        a = ActionStep(step=1, tool_name="test", tool_params={})
        assert a.get_content() == ""

    def test_total_chars_with_none_content(self):
        from app.services.agent.message_builder import MessageBuilder
        result = MessageBuilder._total_chars([{"role": "assistant", "content": None, "tool_calls": []}])
        assert result == 0

    def test_total_chars_with_tool_calls(self):
        from app.services.agent.message_builder import MessageBuilder
        result = MessageBuilder._total_chars([
            {"role": "assistant", "content": "hello", "tool_calls": [{"id": "x", "function": {"name": "f"}}]}
        ])
        assert result > len("hello")


# =============================================================================
# SSE连愯鍣?鈥?load / parse
# =============================================================================

class TestSseRunnerAdversarial:
    def test_load_previous_empty_session(self):
        from app.services.chat.stream import _load_previous_messages
        result = _load_previous_messages("nonexistent_session_id_12345")
        assert result == []

    def test_parse_tool_calls_malformed_json(self):
        from app.services.chat.stream import _parse_tool_calls
        result = _parse_tool_calls(1, "{not valid json!!!}")
        assert result == []

    def test_parse_tool_calls_empty(self):
        from app.services.chat.stream import _parse_tool_calls
        result = _parse_tool_calls(1, "[]")
        assert result == []

    def test_parse_tool_calls_not_list(self):
        from app.services.chat.stream import _parse_tool_calls
        result = _parse_tool_calls(1, '{"type": "action_tool"}')
        assert result == []

    def test_parse_observations_malformed(self):
        from app.services.chat.stream import _parse_observations
        result = _parse_observations(1, "{bad}")
        assert result == []

    def test_parse_observations_none_observation(self):
        from app.services.chat.stream import _parse_observations
        result = _parse_observations(1, '[{"type": "observation", "observation": null}]')
        assert len(result) == 0

    def test_parse_observations_empty_observation(self):
        from app.services.chat.stream import _parse_observations
        result = _parse_observations(1, '[{"type": "observation", "observation": ""}]')
        assert len(result) == 0

    def test_parse_tool_calls_missing_fields(self):
        from app.services.chat.stream import _parse_tool_calls
        result = _parse_tool_calls(1, '[{"type": "action_tool"}]')
        assert len(result) == 1
        assert result[0]["function"]["name"] == ""


# =============================================================================
# 消息果勫缓鍣?鈥?息舵剰输撳入
# =============================================================================

class TestMessageBuilderAdversarial:
    def test_init_empty_task(self):
        from app.services.agent.message_builder import MessageBuilder
        mb = MessageBuilder()
        with pytest.raises(ValueError):
            mb.init_history("system", "")

    def test_init_whitespace_task(self):
        from app.services.agent.message_builder import MessageBuilder
        mb = MessageBuilder()
        with pytest.raises(ValueError):
            mb.init_history("system", "   ")

    def test_trim_to_budget_empty_lists(self):
        from app.services.agent.message_builder import MessageBuilder
        mb = MessageBuilder()
        result = mb._trim_to_budget([], [], 1000)
        assert result == []

    def test_trim_to_budget_all_obs(self):
        from app.services.agent.message_builder import MessageBuilder
        mb = MessageBuilder()
        obs = [{"role": "tool", "tool_call_id": "c1", "content": "a"}]
        result = mb._trim_to_budget(obs, [], 1000)
        assert len(result) == 1

    def test_trim_to_budget_break_early(self):
        from app.services.agent.message_builder import MessageBuilder
        mb = MessageBuilder()
        obs = [
            {"role": "tool", "tool_call_id": "c3", "content": "x" * 500},
            {"role": "tool", "tool_call_id": "c2", "content": "b"},
        ]
        asst = [
            {"role": "assistant", "tool_calls": [{"id": "c2"}], "content": "a2"},
            {"role": "assistant", "tool_calls": [{"id": "c3"}], "content": "a3"},
        ]
        result = mb._trim_to_budget(obs, asst, 100)
        assert isinstance(result, list)

    def test_build_call_list_empty_parsed(self):
        from app.services.agent.handlers.action_handler import _build_call_list
        r = _build_call_list({})
        assert r.tool_name == ""
        assert len(r.all_calls) == 1

    def test_build_call_list_pending_calls_no_names(self):
        from app.services.agent.handlers.action_handler import _build_call_list
        parsed = {"tool_name": "read", "tool_params": {}, "_pending_calls": [{"tool_params": {}}]}
        r = _build_call_list(parsed)
        assert len(r.all_calls) == 1

    def test_trim_fc_pairs_no_messages(self):
        from app.services.agent.message_builder import MessageBuilder
        result = MessageBuilder._trim_fc_pairs([])
        assert result == []

    def test_trim_fc_pairs_unpaired_tool(self):
        from app.services.agent.message_builder import MessageBuilder
        msgs = [{"role": "tool", "tool_call_id": "orphan", "content": "no pair"}]
        result = MessageBuilder._trim_fc_pairs(msgs)
        assert result == []

    def test_trim_fc_pairs_unpaired_assistant(self):
        from app.services.agent.message_builder import MessageBuilder
        msgs = [{"role": "assistant", "tool_calls": [{"id": "orphan", "function": {"name": "x"}}], "content": ""}]
        result = MessageBuilder._trim_fc_pairs(msgs)
        # 类查未塼ool_calls鍧囨棤配崩无讹,整存潯assistant消息琚Щ闄?鈥?小欧 2026-06-26
        assert len(result) == 0


# =============================================================================
# _merge_llm_data 鈥?异常数据
# =============================================================================

class TestMergeLlmDataAdversarial:
    def test_empty_list(self):
        from app.services.agent.handlers.action_handler import _merge_llm_data
        result = _merge_llm_data([])
        assert result == {}

    def test_all_non_dict(self):
        from app.services.agent.handlers.action_handler import _merge_llm_data
        result = _merge_llm_data([None, "string", 123])
        assert result == {}

    def test_mixed_status(self):
        from app.services.agent.handlers.action_handler import _merge_llm_data
        result = _merge_llm_data([
            {"status": {"exec_code": "success"}, "summary": "ok", "action": {"tool": "a"}, "duration_ms": 10},
            {"status": {"exec_code": "error"}, "summary": "fail", "action": {"tool": "b"}, "duration_ms": 20},
        ])
        assert result["action"]["tool"] == "b"
        assert result["status"]["exec_code"] == "error"

    def test_status_not_dict(self):
        from app.services.agent.handlers.action_handler import _merge_llm_data
        result = _merge_llm_data([{"status": "bad", "summary": "test", "action": {"tool": "t"}, "duration_ms": 5}])
        assert isinstance(result, dict)

    def test_summary_is_none(self):
        from app.services.agent.handlers.action_handler import _merge_llm_data
        # Bug 6修: _safe_str(None) 鈫?"" 鑰岄潪 "None" 鈥?小欧 2026-06-26
        result = _merge_llm_data([
            {"summary": None, "status": {"exec_code": "success"}, "action": {"tool": "a"}, "duration_ms": 0},
            {"summary": "real", "status": {"exec_code": "success"}, "action": {"tool": "b"}, "duration_ms": 0},
        ])
        assert result["summary"] == "\n\nreal"


# =============================================================================
# _merge_other_data 鈥?异常数据
# =============================================================================

class TestMergeOtherDataAdversarial:
    def test_empty_list(self):
        from app.services.agent.handlers.action_handler import _merge_other_data
        result = _merge_other_data([])
        assert result == {}

    def test_none_list(self):
        from app.services.agent.handlers.action_handler import _merge_other_data
        result = _merge_other_data([None, None])
        assert result == {}

    def test_warning_not_string(self):
        from app.services.agent.handlers.action_handler import _merge_other_data
        # Bug 5修: non-string warning鑷姩str(),屼不宕╂簝 鈥?小欧 2026-06-26
        result = _merge_other_data([{"warning": ["warn1", "warn2"]}])
        assert result["warning"] == "['warn1', 'warn2']"

    def test_warning_not_string_mixed(self):
        from app.services.agent.handlers.action_handler import _merge_other_data
        result = _merge_other_data([
            {"warning": "simple warn"},
            {"warning": {"complex": "warning"}},
        ])
        assert "simple warn" in result["warning"]
        assert "{'complex': 'warning'}" in result["warning"]

    def test_attachment_consolidation(self):
        from app.services.agent.handlers.action_handler import _merge_other_data
        result = _merge_other_data([{"attachment": {"id": 1}}, {"attachment": {"id": 2}}])
        assert isinstance(result["attachment"], list)

    def test_single_attachment(self):
        from app.services.agent.handlers.action_handler import _merge_other_data
        result = _merge_other_data([{"attachment": {"id": 1}}])
        assert isinstance(result["attachment"], dict)

    def test_return_direct_only_first(self):
        from app.services.agent.handlers.action_handler import _merge_other_data
        result = _merge_other_data([{"return_direct": True, "retry_count": 3}])
        assert result.get("return_direct") is True
        assert result.get("retry_count") == 3


# =============================================================================
# _normalize_observation_prefix 鈥?输照晫
# =============================================================================

class TestNormalizeObservationPrefix:
    def test_no_prefix(self):
        from app.services.agent.message_builder import MessageBuilder
        result = MessageBuilder._normalize_observation_prefix("just text")
        assert result == "[Observation] just text"

    def test_already_has_observation_prefix(self):
        from app.services.agent.message_builder import MessageBuilder
        result = MessageBuilder._normalize_observation_prefix("[Observation] text")
        assert result == "[Observation] text"

    def test_observation_colon_prefix(self):
        from app.services.agent.message_builder import MessageBuilder
        result = MessageBuilder._normalize_observation_prefix("Observation: text")
        assert result == "[Observation] text"

    def test_double_observation_prefix(self):
        from app.services.agent.message_builder import MessageBuilder
        result = MessageBuilder._normalize_observation_prefix("[Observation] [Observation] text")
        assert result == "[Observation] text" or "[Observation] [Observation] text"

    def test_empty_string(self):
        from app.services.agent.message_builder import MessageBuilder
        result = MessageBuilder._normalize_observation_prefix("")
        assert result == "[Observation] "


# =============================================================================
# tool_executor 鈥?输照晫
# =============================================================================

class TestToolExecutorAdversarial:
    def test_auto_inject_no_matches(self):
        from app.services.agent.tool_executor import auto_inject_from_search
        agent = type("MockAgent", (), {"_loaded_categories": set()})()
        auto_inject_from_search(agent, {"data": {}})
        assert len(agent._loaded_categories) == 0

    def test_auto_inject_unknown_category(self):
        from app.services.agent.tool_executor import auto_inject_from_search
        agent = type("MockAgent", (), {"_loaded_categories": set()})()
        auto_inject_from_search(agent, {"data": {"matches": [{"category": "nonexistent_category"}]}})
        assert len(agent._loaded_categories) == 0


# =============================================================================
# observation 果勫缓 鈥?异常在写櫙
# =============================================================================

class TestBuildObservationAdversarial:
    @pytest.mark.asyncio
    async def test_observation_context_with_errors(self):
        from app.services.agent.handlers.action_handler import (
            ObservationContext, build_observation
        )
        agent = type("MockAgent", (), {
            "steps": [], "status": None, "llm_call_count": 0, "task_id": "test",
            "_step_emitter": type("MockEmitter", (), {"emit": lambda self, s: s})(),
            "message_builder": type("MockMB", (), {
                "add_observation": lambda self, text, fc: None,
            })(),
            "record_operation": lambda self, tool, status=None, error=None, operation_id=None: None,
        })()
        ctx = ObservationContext(
            agent=agent,
            all_calls=[{"tool_name": "failing_tool", "tool_params": {}, "_tool_call_id": "c1"}],
            results=[Exception("妯℃嫙异常")],
            step=0, tool_name="failing_tool", tool_params={},
            is_parallel=False, pending_calls=[],
            fc_context={"tool_call_id": "c1", "tool_calls": []},
        )
        events = await build_observation(ctx)
        assert len(events) >= 1


# =============================================================================
# handle_answer 鈥?输照晫鎯容喌
# =============================================================================

class TestHandleAnswerEdgeCases:
    @pytest.mark.asyncio
    async def test_answer_with_empty_content_yields_retrying_step(self):
        from app.services.agent.handlers.answer_handler import handle_answer
        from app.services.agent.status_table import AgentStatus
        agent = type("MockAgent", (), {
            "llm_call_count": 0, "status": AgentStatus.EXECUTING,
            "_step_emitter": type("MockEmitter", (), {"emit": lambda self, s: s})(),
            "message_builder": type("MockMb", (), {"add_assistant_message": lambda self, c: None, "pop_temp_messages": lambda self: 0})(),
        })()
        events = []
        async for ev in handle_answer(agent, {"type": "answer", "content": ""}):
            events.append(ev)
        # 小欧 2026-07-13: 空内容(真·空)不再 yield ErrorStep, 改为 MetaStep(retrying) 驱动系统重试
        assert agent.status == AgentStatus.EXECUTING  # 状态未改变(重试由编排层except处理)
        assert len(events) == 1
        assert "retrying" in str(events[0].type)

    @pytest.mark.asyncio
    async def test_answer_with_content_yields_steps(self):
        from app.services.agent.handlers.answer_handler import handle_answer
        from app.services.agent.status_table import AgentStatus
        agent = type("MockAgent", (), {
            "llm_call_count": 0, "status": AgentStatus.EXECUTING,
            "_step_emitter": type("MockEmitter", (), {"emit": lambda self, s: s})(),
            "message_builder": type("MockMb", (), {"add_assistant_message": lambda self, c: None, "pop_temp_messages": lambda self: 0})(),
        })()
        events = []
        async for ev in handle_answer(agent, {"type": "answer", "content": "hello world", "thought": "thinking"}):
            events.append(ev)
        assert agent.status == AgentStatus.EXECUTING  # 鐘舵查佹湭鏀瑰彉
        assert len(events) == 2
        assert "thought" in str(events[0].type)
        assert "final" in str(events[1].type)
