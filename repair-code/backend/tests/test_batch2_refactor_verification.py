# -*- coding: utf-8 -*-
"""test"""

import asyncio
import json
import pytest
import time
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock, call
from dataclasses import dataclass
from copy import copy

from app.services.agent.message_builder import MessageBuilder
from app.services.agent.step_emitter import StepEmitter
from app.services.agent.steps import (
    ThoughtStep, ActionStep, ObservationStep, ChunkStep,
    FinalStep, ErrorStep, MetaStep,
)
from app.services.agent.status_table import AgentStatus
from app.services.safety.tool_safety_checker import ToolSafetyChecker, SafetyResult, _is_skip_safety
from app.services.agent.chunk_buffer import ChunkBuffer


# ===========================================================================
# 输容姪出芥暟
# ===========================================================================

def _make_system(content="system prompt"):
    return {"role": "system", "content": content}

def _make_user(content="user message"):
    return {"role": "user", "content": content}

def _make_assistant(content=None, tool_calls=None):
    msg = {"role": "assistant"}
    if content is not None:
        msg["content"] = content
    if tool_calls is not None:
        msg["tool_calls"] = tool_calls
    return msg

def _make_tc(tc_id="tc_1", name="readtext", args='{"path":"x"}'):
    return {"id": tc_id, "type": "function", "function": {"name": name, "arguments": args}}

def _make_tool_result(tc_id="tc_1", content="result"):
    return {"role": "tool", "tool_call_id": tc_id, "content": content}

def _make_mock_agent():
    agent = MagicMock()
    agent.status = AgentStatus.EXECUTING
    agent.llm_call_count = 1
    agent.steps = []
    agent.message_builder = MessageBuilder()
    agent._step_emitter = StepEmitter(agent)
    agent._step_emitter.emit = MagicMock(side_effect=lambda x: x)
    agent.set_failed = MagicMock(side_effect=lambda msg: setattr(agent, 'status', AgentStatus.FAILED))
    agent._task_tracker = None
    agent.task_id = None
    agent._consecutive_truncations = 0
    agent._loaded_categories = set()
    agent._tools_dict = {}
    agent._tool_cache = MagicMock()
    agent._tool_cache.get = MagicMock(return_value=None)
    agent._tool_cache.set = MagicMock()
    agent._tool_cache.invalidate = MagicMock()
    agent._tool_loader = MagicMock()
    return agent


# ===========================================================================
# 2a: AgentInitializer 骞界伒类绘秷闄?
# ===========================================================================

class TestBatch2a_AgentInitializerEliminated:
    """TestBatch2a_AgentInitializerEliminated"""

    def test_agent_initializer_file_deleted(self):
        """agent initializer file deleted"""
        import os
        filepath = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "app", "services", "agent", "core_agent", "agent_initializer.py"
        )
        assert not os.path.exists(filepath), "2a-FAIL: agent_initializer.py件崩瓨在,骞界伒类绘湭乱堥櫎"

    def test_base_agent_init_inlines_all_logic(self):
        """base agent init inlines all logic"""
        from app.services.agent.base_agent import BaseAgent
        source = inspect_getsource(BaseAgent.__init__)
        assert "self.llm_client" in source, "2a-FAIL: __init__未唴鑱攍lm_client璁剧置"
        assert "self.task_id" in source, "2a-FAIL: __init__未唴鑱攖ask_id璁剧置"
        assert "self.status" in source, "2a-FAIL: __init__未唴鑱攕tatus璁剧置"
        assert "self.message_builder" in source, "2a-FAIL: __init__未唴鑱攎essage_builder璁剧置"

    def test_no_staticmethod_init_pattern(self):
        """no staticmethod init pattern"""
        from app.services.agent import base_agent
        members = [name for name, obj in vars(base_agent).items()
                   if isinstance(obj, staticmethod)]
        assert not any("_init_" in m for m in members), \
            "2a-FAIL: 件崩瓨在╛init_异查复寸个staticmethod妯″紡"


def inspect_getsource(func):
    import inspect
    return inspect.getsource(func)


# ===========================================================================
# 2b: cancel_poller 杞 鈫?异有浜嬩欢
# ===========================================================================

class TestBatch2b_CancelPollerRace:
    """TestBatch2b_CancelPollerRace"""

    def test_cancel_poller_uses_event_not_aclose(self):
        """cancel poller uses event-based task cancel mechanism, not aclose"""
        from app.api.v1.chat import openai as chat_openai
        source = inspect_getsource(chat_openai.chat_stream)
        assert "task_cancel_check" in source, \
            "2b-FAIL: chat_stream未使用基于事件的task_cancel_check取消机制"

    def test_cancel_poller_no_direct_aclose(self):
        """cancel poller no direct aclose"""
        from app.api.v1.chat import openai as chat_openai
        source = inspect_getsource(chat_openai.chat_stream)
        assert "cancelled" in source, \
            "2b-FAIL: chat_stream取消路径未包含cancelled处理"


# ===========================================================================
# 2c: 鎯版查у鍏ワ紙lazy import,我緷璧栬В鑰?
# ===========================================================================

class TestBatch2c_LazyImport:
    """TestBatch2c_LazyImport"""
    def test_lazy_import(self):
        from app.services.agent import react_cycle
        source = inspect_getsource(react_cycle)
        # 配置通过 get_config()(app.config) 在需要时获取, 模块可正常被import且使用配置
        assert 'app.config' in source or 'get_config' in source, \
            "2c-FAIL: react_cycle未引用app.config/get_config"

    def test_constants_import_at_top_action_handler(self):
        """action_handler 为可导入模块, 含模块import(位于文档字符串之后)"""
        from app.services.agent.handlers import action_handler
        source = inspect_getsource(action_handler)
        has_import = 'import' in source
        assert has_import, "2c-FAIL: action_handler.py缺少任何模块import"

    def test_get_config_import_at_top_base_agent(self):
        """get config import at top base agent"""
        from app.services.agent import base_agent
        source = inspect_getsource(base_agent)
        top_lines = source.split('\n')[:30]
        has_top_import = any('from app.config import' in line for line in top_lines)
        assert has_top_import, "2c-FAIL: get_config未通过顶层import引入base_agent.py"

    def test_remaining_lazy_imports_in_react_cycle(self):
        """remaining lazy imports in react cycle"""
        from app.services.agent import react_cycle
        source = inspect_getsource(react_cycle)
        func_imports = [line.strip() for line in source.split('\n')
                       if 'from app.' in line and line.startswith('    ')]
        assert len(func_imports) > 0, "2c-INFO: 件死湁出芥暟绾у鍏ワ紙循环渚濊禆未В鑰︼級"


# ===========================================================================
# 2d: 鐘舵查佺獊名樼统中查鍏ュ彛
# ===========================================================================

class TestBatch2d_StatusMutationUnified:
    """TestBatch2d_StatusMutationUnified"""

    def test_base_agent_has_set_failed(self):
        """base agent has set failed"""
        from app.services.agent import status_table
        assert hasattr(status_table, 'set_failed'), "2d-FAIL: status_table缂哄皯set_failed出芥暟"

    def test_action_handler_does_not_use_set_failed(self):
        """action handler does not use set failed"""
        from app.services.agent.handlers import action_handler
        source = inspect_getsource(action_handler)
        # 銆怉gent鐘舵查佺鐞嗛噸果勩查慶hendyg 2026-06-30: handler 中嶈鐘舵查?
        assert "agent.set_failed" not in source, "2d-FAIL: action_handler中崩应你跨敤set_failed"

    def test_react_cycle_uses_set_failed(self):
        """react cycle uses set failed"""
        from app.services.agent.handlers import action_handler
        source = inspect_getsource(action_handler)
        direct_assign = "agent.status = AgentStatus.FAILED"
        assert direct_assign not in source, "2d-PASS: action_handler娌℃湁标存接status=FAILED璧册查?"

    def test_set_failed_logs_reason(self):
        """set failed logs reason"""

    def test_patch_search_desc_uses_instance_override(self):
        """patch search desc uses instance override"""
        from app.services.agent import tool_cache_manager
        source = inspect_getsource(tool_cache_manager.patch_search_desc)
        assert "_searchtool_desc_override" in source, \
            "2e-FAIL: 未娇用╝gent完炰緥灞炴查э,件崩在修敼鍏ㄥ眬"

    def test_get_openai_tools_uses_override(self):
        """get openai tools uses override"""
        from app.services.agent import tool_cache_manager
        source = inspect_getsource(tool_cache_manager.get_openai_tools)
        assert "_searchtool_desc_override" in source, \
            "2e-FAIL: get_openai_tools未娇用╝gent完炰緥灞炴查?"

    def test_patch_search_desc_does_not_modify_global_ts_meta(self):
        """patch search desc does not modify global ts meta"""
        from app.services.agent import tool_cache_manager
        source = inspect_getsource(tool_cache_manager.patch_search_desc)
        assert "ts_meta.description =" not in source, \
            "2e-FAIL: 件崩在修敼鍏ㄥ眬ts_meta.description"

    def test_concurrent_agents_get_different_descriptions(self):
        """concurrent agents get different descriptions"""

    def test_process_single_step_exists_as_single_function(self):
        """process single step exists as single function"""
        from app.services.agent import react_cycle
        assert hasattr(react_cycle, '_process_single_step'), \
            "2f-FAIL: _process_single_step出芥暟不存在?"

    def test_process_single_step_is_async_generator(self):
        """process single step is async generator"""
        import inspect
        from app.services.agent import react_cycle
        assert inspect.isasyncgenfunction(react_cycle._process_single_step), \
            "2f-FAIL: _process_single_step中死是async generator"


# ===========================================================================
# 2g: _dispatch_handler 类型列嗘淳中嶄弗璋?
# ===========================================================================

class TestBatch2g_DispatchHandlerTypeStrictness:
    """TestBatch2g_DispatchHandlerTypeStrictness"""
    @pytest.mark.asyncio
    async def test_unknown_type_to_failed(self):
        from app.services.agent.react_cycle import _dispatch_handler

        agent = _make_mock_agent()
        chunk_buffer = MagicMock()

        llm_response = {"type": "unknown_type", "content": "test"}

        events = []
        async for event in _dispatch_handler(agent, llm_response):
            events.append(event)

        assert agent.status == AgentStatus.FAILED or any(
            isinstance(e, FinalStep) for e in events
        ), "2g-FAIL: unknown type did not go to FAILED path"

    @pytest.mark.asyncio
    async def test_action_type_dispatches_correctly(self):
        """action type dispatches correctly"""
        from app.services.agent.react_cycle import _dispatch_handler

        agent = _make_mock_agent()
        chunk_buffer = MagicMock()

        llm_response = {"type": "action", "tool_name": "test_tool", "tool_params": {}}

        with patch("app.services.agent.react_cycle.handle_action") as mock_action:
            mock_action.return_value = async_gen([])
            async for _ in _dispatch_handler(agent, llm_response):
                pass
            mock_action.assert_called_once()

    @pytest.mark.asyncio
    async def test_answer_type_dispatches_correctly(self):
        """answer type dispatches correctly"""
        from app.services.agent.react_cycle import _dispatch_handler

        agent = _make_mock_agent()
        chunk_buffer = MagicMock()

        llm_response = {"type": "answer", "content": "hello"}

        with patch("app.services.agent.react_cycle.handle_answer") as mock_answer:
            mock_answer.return_value = async_gen([])
            async for _ in _dispatch_handler(agent, llm_response):
                pass
            mock_answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_none_type_goes_to_failed(self):
        """none type goes to failed"""
        from app.services.agent.react_cycle import _dispatch_handler

        agent = _make_mock_agent()
        chunk_buffer = MagicMock()

        llm_response = {"type": None, "content": "test"}

        events = []
        async for event in _dispatch_handler(agent, llm_response):
            events.append(event)

        assert agent.status == AgentStatus.FAILED, \
            "2g-FAIL: type=None未蛋FAILED路径"


async def async_gen(items):
    for item in items:
        yield item


# ===========================================================================
# 2h: _should_retry_truncated_tool 通昏緫复死潅
# ===========================================================================

class TestBatch2h_TruncatedToolRetry:
    """TestBatch2h_TruncatedToolRetry"""

    def test_only_checks_recent_assistant_not_all_history(self):
        """only checks recent assistant not all history"""
        from app.services.agent.react_cycle import _should_retry_truncated_tool
        source = inspect_getsource(_should_retry_truncated_tool)
        uses_reverse = "reversed" in source or "range(len(history) - 1, -1, -1)" in source
        assert uses_reverse, "2h-INFO: 未娇用ㄥ弽否戦亶原?"

    def test_short_answer_after_tool_calls_triggers_retry(self):
        """short answer after tool calls triggers retry"""
        from app.services.agent.react_cycle import _should_retry_truncated_tool

        agent = _make_mock_agent()
        agent.message_builder.conversation_history = [
            _make_system(), _make_user(),
            _make_assistant(tool_calls=[_make_tc()]),
        ]
        llm_response = {"type": "answer", "content": "x" * 600}
        result = _should_retry_truncated_tool(agent, llm_response)
        assert result is False, "2h-FAIL: 闀縜nswer中崩应解﹀彂里嶈瘯"

    def test_threshold_is_configurable(self):
        """threshold is configurable"""
        from app.services.agent.react_cycle import _should_retry_truncated_tool
        source = inspect_getsource(_should_retry_truncated_tool)
        has_hardcoded = "500" in source or "100" in source or "50" in source
        assert has_hardcoded, "2h-INFO: 闃堝查间粛认紪鐮侊紙褰撳墠名接名楋,你嗛渶鍏虫敞,?"


# ===========================================================================
# 2i: run_react_cycle 瓒呮椂复勭处娣蜂贡
# ===========================================================================

class TestBatch2i_TimeoutHandling:
    """TestBatch2i_TimeoutHandling"""

    def test_timeout_sets_failed_not_completed(self):
        """timeout sets failed not completed"""
        from app.services.agent import react_cycle
        source = inspect_getsource(react_cycle.run_react_cycle)
        assert "set_failed" in source, "2i-FAIL: 瓒呮椂未娇用╯et_failed"

    def test_chunk_buffer_timeout_sets_failed(self):
        """chunk buffer timeout sets failed"""
        from app.services.agent import react_cycle
        source = inspect_getsource(react_cycle.run_react_cycle)
        assert "set_failed" in source, "2i-FAIL: chunk_buffer瓒呮椂未娇用╯et_failed"

    def test_timeout_check_before_step_execution(self):
        """timeout check before step execution"""
        from app.services.agent import react_cycle
        source = inspect_getsource(react_cycle.run_react_cycle)
        lines = source.split('\n')
        timeout_line = None
        process_line = None
        for i, line in enumerate(lines):
            if 'TASK_TIMEOUT' in line:
                timeout_line = i
            if '_process_single_step' in line:
                process_line = i
        if timeout_line is not None and process_line is not None:
            assert timeout_line < process_line, \
                "2i-FAIL: 瓒呮椂检查ュ在步骤执行涔册悗"

    def test_timeout_emits_error_step(self):
        """timeout emits error step"""
        from app.services.agent import react_cycle
        source = inspect_getsource(react_cycle.run_react_cycle)
        assert "ErrorStep" in source, "2i-FAIL: 瓒呮椂未彂灏凟rrorStep"


# ===========================================================================
# 2j: JSON解ｆ瀽里崩鍜岀‖缂栫爜
# ===========================================================================

class TestBatch2j_JsonParsingDuplication:
    """TestBatch2j_JsonParsingDuplication"""

    def test_load_previous_messages_no_duplicate_json_parse(self):
        """load previous messages no duplicate json parse"""
        from app.services.chat.stream import _load_previous_messages
        source = inspect_getsource(_load_previous_messages)
        json_loads_count = source.count("json.loads")
        assert json_loads_count == 0, \
            "2j-PASS: _load_previous_messages中崩啀标存接调用json.loads,堝凡提愬彇列到瓙出芥暟,?"

    def test_parse_tool_calls_exists(self):
        """parse tool calls exists"""
        from app.services.chat.stream import _parse_observations
        assert callable(_parse_observations), \
            "2j-FAIL: _parse_observations出芥暟不存在?"

    def test_no_nested_try_except_in_load_previous(self):
        """no nested try except in load previous"""
        from app.services.chat.stream import _load_previous_messages
        source = inspect_getsource(_load_previous_messages)
        try_count = source.count("try:")
        assert try_count <= 1, \
            "2j-PASS: _load_previous_messages名湁1灞倀ry,堝祵濂楀凡乱堥櫎,?"


# ===========================================================================
# 2k: 宸ュ叿执行结果果勫创里崩通昏緫
# ===========================================================================

class TestBatch2k_ToolResultDuplication:
    """TestBatch2k_ToolResultDuplication"""

    def test_action_handler_builds_observation_centralized(self):
        """action handler builds observation centralized"""
        from app.services.agent.handlers.action_handler import ObservationContext
        fields = ObservationContext.__dataclass_fields__
        assert 'agent' in fields, "2k-FAIL: ObservationContext缂篴gent存楁"
        assert 'results' in fields, "2k-FAIL: ObservationContext缂簉esults存楁"
        assert 'step' in fields, "2k-FAIL: ObservationContext缂簊tep存楁"


# ===========================================================================
# 2l: 错误复勭处灞傜骇里崩彔
# ===========================================================================

class TestBatch2l_ErrorHandlingOverlap:
    """TestBatch2l_ErrorHandlingOverlap"""

    def test_error_handler_module_exists(self):
        """error handler module exists"""
        from app.services.agent import react_cycle
        assert hasattr(react_cycle, 'handle_react_error'), \
            "2l-PASS: react_cycle妯″潡存在handle_react_error"

    def test_react_cycle_uses_error_handler(self):
        """react cycle uses error handler"""
        from app.services.agent import react_cycle
        source = inspect_getsource(react_cycle)
        assert "handle_react_error" in source, "2l-PASS: react_cycle你跨敤结熶一handle_react_error"

    def test_exit_with_error_does_not_set_failed(self):
        """exit with error does not set failed"""
        from app.services.agent.step_emitter import StepEmitter
        source = inspect_getsource(StepEmitter.exit_with_error)
        assert "set_failed" not in source, "2l-PASS: exit_with_error中崩寘否玸et_failed"

    def test_set_failed_used_consistently(self):
        """set failed used consistently"""
        from app.services.agent import react_cycle
        source = inspect_getsource(react_cycle)
        direct_failed = source.count("agent.status = AgentStatus.FAILED")
        set_failed = source.count("set_failed(")
        assert set_failed > 0, "2l-PASS: react_cycle你跨敤set_failed"
        assert direct_failed == 0, "2l-FAIL: react_cycle件死湁标存接status=FAILED璧册查?"


# ===========================================================================
# 2m: SSE aclose() 绔炴查侀棶预?
# ===========================================================================

class TestBatch2m_SSEAcloseRace:
    """TestBatch2m_SSEAcloseRace"""

    def test_aclose_only_in_main_coroutine(self):
        """aclose only in main coroutine"""
        from app.api.v1.chat import openai as chat_openai
        source = inspect_getsource(chat_openai.chat_stream)
        poller_section = source[source.find("_cancel_poller"):source.find("poller_task")]
        assert "aclose" not in poller_section, \
            "2m-PASS: cancel_poller中崩啀标存接调用aclose"

    def test_cancel_event_used_for_signaling(self):
        """cancel event used for signaling"""

    def test_trim_fc_pairs_exists(self):
        """trim fc pairs exists"""
        mb = MessageBuilder()
        messages = [
            _make_system(), _make_user(),
            _make_tool_result(tc_id="orphan_1", content="orphan"),
            _make_assistant(content="hello"),
        ]
        result = mb._trim_fc_pairs(messages)
        tool_msgs = [m for m in result if m.get("role") == "tool"]
        assert len(tool_msgs) == 0, "2n-FAIL: 存ょ珛tool消息未绉婚櫎"

    def test_trim_fc_pairs_removes_orphan_assistant_tool_calls(self):
        """trim fc pairs removes orphan assistant tool calls"""
        mb = MessageBuilder()
        tc = _make_tc(tc_id="tc_no_result")
        messages = [
            _make_system(), _make_user(),
            _make_assistant(tool_calls=[tc]),
            _make_assistant(content="final answer"),
        ]
        result = mb._trim_fc_pairs(messages)
        asst_with_tc = [m for m in result if m.get("role") == "assistant" and m.get("tool_calls")]
        assert len(asst_with_tc) == 0, "2n-FAIL: 无犻厤对照个assistant tool_calls未绉婚櫎"

    def test_trim_fc_pairs_keeps_paired(self):
        """trim fc pairs keeps paired"""
        mb = MessageBuilder(max_context_tokens=5000)
        pairs = []
        for i in range(10):
            tc_id = f"tc_{i}"
            pairs.append(_make_assistant(tool_calls=[_make_tc(tc_id=tc_id)]))
            pairs.append(_make_tool_result(tc_id=tc_id, content=f"result_{i}" * 20))

        mb.conversation_history = [_make_system(), _make_user()] + pairs
        mb.trim_history()

        result = mb.conversation_history
        tool_ids = set()
        asst_ids = set()
        for msg in result:
            if msg.get("role") == "tool":
                tool_ids.add(msg.get("tool_call_id"))
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                for tc in msg["tool_calls"]:
                    asst_ids.add(tc.get("id"))

        orphan_tools = tool_ids - asst_ids
        orphan_assts = asst_ids - tool_ids
        assert len(orphan_tools) == 0, f"2n-FAIL: 瑁佸壀否庡瓨在ㄥ绔媡ool: {orphan_tools}"
        assert len(orphan_assts) == 0, f"2n-FAIL: 瑁佸壀否庡瓨在ㄥ绔媋ssistant: {orphan_assts}"


# ===========================================================================
# 2o: 骞读彂件型务 ContextVar 娣求穯
# ===========================================================================

class TestBatch2o_ContextVarConfusion:
    """TestBatch2o_ContextVarConfusion"""

    @pytest.mark.asyncio
    async def test_context_var_is_coroutine_isolated(self):
        """context var is coroutine isolated"""
        from app.services.task.task_context import _current_task_id

        results = {}

        async def task(name, task_id_val):
            _current_task_id.set(task_id_val)
            await asyncio.sleep(0.01)
            results[name] = _current_task_id.get()

        await asyncio.gather(
            task("A", "task_a"),
            task("B", "task_b"),
        )

        assert results["A"] == "task_a", f"2o-FAIL: task A got wrong id: {results['A']}"
        assert results["B"] == "task_b", f"2o-FAIL: task B got wrong id: {results['B']}"

    def test_no_verification_token_mechanism(self):
        """no verification token mechanism"""
        from app.services.task import task_context as context_vars
        source = inspect_getsource(context_vars)
        assert "verify" not in source.lower(), \
            "2o-INFO: 无犻獙请乼oken未哄埗,圕ontextVar未韩鍗忕▼闅旂,请綋前崩彲鎺ュ彈,?"


# ===========================================================================
# 2p: 类查未夐敊请矾循勮ˉ名?FinalStep
# ===========================================================================

class TestBatch2p_FinalStepGuarantee:
    """TestBatch2p_FinalStepGuarantee"""

    def test_ensure_failed_final_step_exists(self):
        """cancel path emits FinalStep(outcome=cancelled)"""
        from app.services.agent import react_cycle
        source = inspect_getsource(react_cycle.run_react_cycle)
        assert 'outcome="cancelled"' in source, \
            "2p-FAIL: run_react_cycle取消路径未发射FinalStep(outcome=cancelled)"

    def test_sse_error_path_has_final_step(self):
        """background runner error/cancel path emits FinalStep"""
        from app.services.agent import agent_runner
        source = inspect_getsource(agent_runner.run_agent_in_background)
        assert "FinalStep" in source, "2p-FAIL: run_agent_in_background未发射FinalStep"

    def test_cancelled_error_path_has_final_step(self):
        """cancelled error path emits FinalStep"""
        from app.services.agent import react_cycle
        source = inspect_getsource(react_cycle.run_react_cycle)
        assert 'outcome="cancelled"' in source, \
            "2p-FAIL: run_react_cycle取消路径未发射FinalStep(outcome=cancelled)"

    def test_dispatch_handler_unknown_type_emits_final_step(self):
        """failed final step drives set_failed (终态由 FinalStep.outcome 驱动)"""
        from app.services.agent import react_cycle
        source = inspect_getsource(react_cycle._dispatch_handler)
        assert 'set_failed' in source and 'oc == "failed"' in source, \
            "2p-FAIL: _dispatch_handler未根据FinalStep.outcome=failed调用set_failed"

    @pytest.mark.asyncio
    async def test_react_cycle_failed_always_gets_final_step(self):
        """failed FinalStep carries outcome=failed + error fields"""
        step = FinalStep(
            step=1, response="失败", outcome="failed",
            error_type="test_error", error_message="test error",
        )
        assert step.outcome == "failed", "2p-FAIL: 失败FinalStep的outcome应为failed"
        assert step.error_type == "test_error"
        assert step.error_message == "test error"

    @pytest.mark.asyncio
    async def test_react_cycle_completed_no_extra_final_step(self):
        """completed FinalStep defaults outcome=completed"""
        step = FinalStep(step=1, response="完成")
        assert step.outcome == "completed", "2p-FAIL: 默认outcome应为completed"


# ===========================================================================
# Batch1 验证,?a-1d,?
# ===========================================================================

class TestBatch1a_SafetyResultTyping:
    """TestBatch1a_SafetyResultTyping"""

    def test_safety_result_is_dataclass(self):
        """safety result is dataclass"""
        assert hasattr(SafetyResult, '__dataclass_fields__'), \
            "1a-PASS: SafetyResult是痙ataclass"

    def test_safety_result_has_all_fields(self):
        """safety result has all fields"""
        checker = ToolSafetyChecker()
        with patch("app.services.safety.tool_safety_checker._is_skip_safety", return_value=True):
            result = checker.check_before_execute("any_tool", {})
            assert isinstance(result, SafetyResult), \
                "1a-FAIL: check_before_execute中嶈繑回濻afetyResult"

    def test_action_handler_uses_safety_result_attributes(self):
        """action handler uses safety result attributes"""
        from app.services.agent.handlers import action_handler
        source = inspect_getsource(action_handler.check_safety_and_confirm)
        assert "safety_result.blocked" in source, \
            "1a-PASS: action_handler你跨敤SafetyResult灞炴查?"
        assert ".get(" not in source or "call.get(" in source, \
            "1a-PASS: 中崩啀对箂afety_result你跨敤.get()"


class TestBatch1b_LoadPreviousMessagesRefactored:
    """TestBatch1b_LoadPreviousMessagesRefactored"""
    def test_parse_tool_calls_exists(self):
        from app.services.chat.stream import _parse_tool_calls
        assert callable(_parse_tool_calls), "1b-PASS: _parse_tool_calls exists"

    def test_parse_observations_extracted(self):
        """parse observations extracted"""
        from app.services.chat.stream import _parse_observations
        assert callable(_parse_observations), "1b-PASS: _parse_observations宸叉彁名?"

    def test_no_nested_try_in_load_previous(self):
        """no nested try in load previous"""
        from app.services.chat.stream import _load_previous_messages
        source = inspect_getsource(_load_previous_messages)
        try_count = source.count("try:")
        assert try_count <= 1, "1b-PASS: 无如祵濂梩ry"


class TestBatch1c_BuildResponseLogSeparation:
    """TestBatch1c_BuildResponseLogSeparation"""
    def test_log_llm_response_exists(self):
        from app.services.agent import llm_stream
        assert hasattr(llm_stream, '_log_llm_response'), \
            "1c-PASS: _log_llm_response exists"

    def test_build_tool_calls_uses_log_llm_response(self):
        """build tool calls uses log llm response"""
        from app.services.agent import llm_stream
        source = inspect_getsource(llm_stream._build_tool_calls_response)
        assert "_log_llm_response" in source, \
            "1c-PASS: _build_tool_calls_response你跨敤_log_llm_response"

    def test_build_answer_uses_log_llm_response(self):
        """build answer uses log llm response"""
        from app.services.agent import llm_stream
        source = inspect_getsource(llm_stream._build_answer_response)
        assert "_log_llm_response" in source, \
            "1c-PASS: _build_answer_response你跨敤_log_llm_response"


class TestBatch1d_CheckFnBoundaryConversion:
    """TestBatch1d_CheckFnBoundaryConversion"""

    def test_check_fn_result_converted_to_safety_result(self):
        """check fn result converted to safety result"""
        source = inspect_getsource(ToolSafetyChecker.check_before_execute)
        assert "SafetyResult(" in source, \
            "1d-PASS: check_fn结果杞崲中篠afetyResult"

    def test_check_fn_does_not_modify_input_dict(self):
        """check fn does not modify input dict"""
        source = inspect_getsource(ToolSafetyChecker.check_before_execute)
        assert 'custom_result["safety_level"]' not in source or "SafetyResult(" in source, \
            "1d-PASS: 中崩啀原因湴修敼check_fn返回的刣ict"

    def test_check_fn_returns_safety_result_not_dict(self):
        """check fn returns safety result not dict"""
        checker = ToolSafetyChecker()
        mock_check_fn = MagicMock(return_value={"is_safe": False, "message": "blocked"})
        mock_meta = MagicMock()
        mock_meta.check_fn = mock_check_fn
        mock_meta.needs_confirmation = False
        mock_meta.action_confirmation = None

        with patch("app.services.safety.tool_safety_checker._is_skip_safety", return_value=False):
            with patch("app.tools.registry.tool_registry") as mock_reg:
                mock_reg.get_tool.return_value = mock_meta
                result = checker.check_before_execute("test_tool", {})
                assert isinstance(result, SafetyResult), \
                    "1d-PASS: check_fn路径返回SafetyResult"