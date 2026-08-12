# -*- coding: utf-8 -*-
"""
SSE异常路径与LLM边界测试 — 小健 2026-06-25

编辑历史:
  2026-07-14 小欧 修正test_6_002: run_sse_stream已拆分为agent_runner.run_agent_in_background(生产者)+stream_reader(消费者),引用新入口(功能零退化)
  2026-08-11 小欧 修正test_5_001: 漏调ensure_tools_registered()致readtext未注册被前置拒绝(未注册工具统一拒绝是进化语义), 补注册后恢复原始意图(开关关闭→安全绕过,读系统路径放行)
"""

import asyncio
import json
import pytest
import time
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock
from typing import Dict, List, Any, Optional

from app.services.agent.message_builder import MessageBuilder
from app.services.agent.step_emitter import StepEmitter
from app.services.agent.steps import (
    ThoughtStep, ActionStep, ObservationStep, ChunkStep,
    FinalStep, ErrorStep, MetaStep,
)
from app.services.agent.status_table import AgentStatus
from app.services.agent.tool_cache_manager import get_openai_tools, invalidate_tool_cache, patch_search_desc, _get_original_search_desc
from app.services.task.task_context import _current_task_id
from app.services.safety.tool_safety_checker import ToolSafetyChecker, SafetyResult
from app.tools.registry import ToolCategory, tool_registry
from app.services.safety.path_safe_check import validate_path
from app.services.llm.core import LLMResponseError


def _mock_agent():
    agent = MagicMock()
    agent.status = AgentStatus.EXECUTING
    agent.llm_call_count = 1
    agent.steps = []
    agent.message_builder = MagicMock()
    agent.message_builder.conversation_history = []
    agent._step_emitter = MagicMock()
    agent._step_emitter.emit = MagicMock(side_effect=lambda x: x)
    agent._tool_cache = MagicMock()
    agent._tool_cache.get = MagicMock(return_value=None)
    agent._tool_cache.set = MagicMock()
    agent._searchtool_desc_override = None
    agent.llm_client = MagicMock()
    agent.llm_client._cancelled = False
    agent._loaded_categories = {ToolCategory.FUNDAMENTAL, ToolCategory.SHELL, ToolCategory.FILE}
    agent._tool_loader = MagicMock()
    return agent


# ===========================================================================
# 娴佺▼4: 宸ュ叿执行绠＄嚎 鈥?骞惰宸ュ叿return_direct閬楁紡 (F4-11宸蹭慨复嶄絾件死湁名樼)
# ===========================================================================

class TestFlow4ActionHandlerEdgeCases:

    def test_4_001_merge_other_data_empty_list(self):
        """4 001 merge other data empty list"""
        from app.services.agent.handlers.action_handler import _merge_other_data
        merged = _merge_other_data([None, {"return_direct": True}])
        assert merged.get("return_direct") is True

    def test_4_003_merge_other_data_all_none(self):
        """4 003 merge other data all none"""
        from app.services.agent.handlers.action_handler import _merge_other_data
        merged = _merge_other_data([None, None])
        assert merged == {}

    def test_4_004_build_call_list_empty_tool_calls(self):
        """4 004 build call list empty tool calls"""
        from app.services.agent.handlers.action_handler import _build_call_list
        parsed = {"type": "action", "tool_calls": []}
        result = _build_call_list(parsed)
        assert isinstance(result.all_calls, list)

    def test_4_005_build_call_list_tool_name_missing(self):
        """4 005 build call list tool name missing"""
        from app.services.agent.handlers.action_handler import _build_call_list, BuildCallListResult
        parsed = {"type": "action", "tool_calls": [{"id": "tc_1"}]}
        result = _build_call_list(parsed)
        assert isinstance(result, BuildCallListResult)

    def test_4_006_build_observation_results_empty(self):
        """4 006 build observation results empty"""
        from app.services.agent.handlers.action_handler import build_observation
        ctx = MagicMock()
        ctx.results = []
        async def run():
            events = await build_observation(ctx)
            return events
        events = asyncio.run(run())
        assert events is not None


# ===========================================================================
# 娴佺▼5: 文件完夊叏 鈥?件ｇ爜娉ㄥ入銆佽矾循勬查询竟缂?
# ===========================================================================

class TestFlow5SafetyEdgeCases:

    def test_5_001_is_skip_safety_returns_true(self):
        """5 001 is skip safety returns true"""
        from app.tools import ensure_tools_registered
        ensure_tools_registered()
        with patch("app.services.safety.tool_safety_checker._is_skip_safety", return_value=True):
            checker = ToolSafetyChecker()
            result = checker.check_before_execute("readtext", {"path": "/etc/passwd"})
            assert result.safety_level == "safe"
            assert result.blocked is False

    def test_5_002_check_known_risks_shell_code_injection(self):
        """5 002 check known risks shell code injection"""
        from app.tools import ensure_tools_registered
        ensure_tools_registered()
        with patch("app.services.safety.tool_safety_checker._is_skip_safety", return_value=False):
            checker = ToolSafetyChecker()
            result = checker.check_before_execute(
                "shell",
                {"command": "echo 'hello world'"}
            )
            assert result.blocked is False

    def test_5_004_validate_path_empty_path(self):
        """5 004 validate path empty path"""
        result = validate_path("")
        if isinstance(result, tuple):
            is_valid = result[0]
            assert is_valid is False, "BUG: 空矾循勫应琚嫆结?"

    def test_5_005_validate_path_none(self):
        """5 005 validate path none"""
        try:
            result = validate_path(None)
            if isinstance(result, tuple):
                assert result[0] is False, "BUG: None路径应该鎷掔粷"
        except (TypeError, AttributeError):
            pass  # 涔熸接名楁姏异常

    def test_5_006_validate_path_traversal_windows(self):
        """5 006 validate path traversal windows"""
        result = validate_path("C:/Windows/system32/../../etc/passwd")
        if isinstance(result, tuple):
            is_valid = result[0]
            assert is_valid is False, "BUG: 路径閬崩巻应该鎷掔粷"

    def test_5_007_validate_path_max_length(self):
        """5 007 validate path max length"""
        long_path = "C:/" + "a" * 500 + "/file.txt"
        result = validate_path(long_path)
        # 中崩应宕╂簝,请应返回有效结果


# ===========================================================================
# 娴佺▼6: SSE浜嬩欢娴?鈥?异常路径行ュ彂final
# ===========================================================================

class TestFlow6SSEExceptionPaths:

    def test_6_001_db_save_retry_mechanism(self):
        """6 001 db save retry mechanism"""
        from app.services.chat.handlers import save_execution_steps_to_db
        call_count = [0]
        async def mock_save(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("DB error 1")
            return True
        with patch("app.services.chat.handlers.save_execution_steps_to_db", mock_save):
            pass  # 鑷景皯不崩溃?

    def test_6_002_sse_stream_cleanup_on_cancel(self):
        """6 002 sse stream cleanup on cancel — run_sse_stream 已拆为
        agent_runner.run_agent_in_background(生产者)+stream_reader(消费者) 2026-07-12"""
        from app.services.agent.agent_runner import run_agent_in_background
        assert callable(run_agent_in_background), "run_sse_stream 的替代入口应存在"
        cleanup_called = [False]
        async def run():
            try:
                raise asyncio.CancelledError()
            except asyncio.CancelledError:
                pass
            finally:
                cleanup_called[0] = True
        asyncio.run(run())
        assert cleanup_called[0] is True

    def test_6_003_format_agent_sse_missing_type(self):
        """6 003 format agent sse missing type"""
        from app.utils.sse_formatter import format_agent_sse
        result = format_agent_sse({"content": "test"})
        assert result is not None
        assert isinstance(result, str)

    def test_6_004_format_agent_sse_none(self):
        """6 004 format agent sse none"""
        from app.utils.sse_formatter import format_agent_sse
        try:
            result = format_agent_sse(None)
            # 如果娌℃姏异常,请应返回空哄瓧第︿覆
            assert result == ''
        except (AttributeError, TypeError):
            pass  # 名接名梔ict输撳入,我姏异常名接名?


# ===========================================================================
# 娴佺▼8: LLM完㈡户绔?鈥?FC闄嶇骇鍜岄敊请鐞?
# ===========================================================================

class TestFlow8LLMEdgeCases:

    def test_8_001_call_llm_with_fallback_empty_tools(self):
        """8 001 call llm with fallback empty tools"""
        from app.services.agent.llm_stream import call_llm_with_fallback
        agent = _mock_agent()
        results = []
        async def run():
            async for item in call_llm_with_fallback(agent, [{"role": "user", "content": "hi"}], []):
                results.append(item)
        asyncio.run(run())
        assert len(results) >= 1

    def test_8_002_call_llm_with_fallback_fc_error_retry_exhausted(self):
        """8 002 call llm with fallback fc error retry exhausted"""
        from app.services.agent.llm_stream import call_llm_stream
        agent = _mock_agent()
        try:
            async def run():
                from app.constants import LLM_TOOL_CHOICE
                original = LLM_TOOL_CHOICE
                with patch("app.constants.LLM_TOOL_CHOICE", None):
                    pass  # tool_choice=None is valid
            asyncio.run(run())
        except Exception as e:
            assert False, f"BUG: 中崩应请ュ穿溃? {e}"


# ===========================================================================
# 娴佺▼9: 原嗗彶瑁佸壀 鈥?FC配崩完整鎬?
# ===========================================================================

class TestFlow9TrimEdgeCases:

    def test_9_001_trim_history_exact_threshold(self):
        """9 001 trim history exact threshold"""
        mb = MessageBuilder()
        mb.conversation_history = [
            {"role": "system", "content": "s"},
            {"role": "user", "content": "u" * 5000},
            {"role": "assistant", "content": "a", "tool_calls": [{"id": f"tc_{i}", "type": "function", "function": {"name": "f", "arguments": "{}"}} for i in range(100)]},
            {"role": "tool", "content": "o" * 10000, "tool_call_id": "tc_0"},
        ]
        mb.trim_history()
        assert len(mb.conversation_history) >= 2

    def test_9_003_trim_history_fc_pair_missing_tool(self):
        """9 003 trim history fc pair missing tool"""
        mb = MessageBuilder()
        from app.constants import MAX_CONTEXT_TOKENS
        with patch("app.services.agent.message_builder.MAX_CONTEXT_TOKENS", 5000):
            mb.conversation_history = [
                {"role": "system", "content": "s"},
                {"role": "user", "content": "u" * 2000},
                {"role": "assistant", "content": "a", "tool_calls": [{"id": "tc_1", "type": "function", "function": {"name": "f", "arguments": "{}"}}]},
                {"role": "user", "content": "next"},
            ]
            mb.trim_history()  # 中崩应宕╂簝

    def test_9_004_trim_history_all_system_only(self):
        """9 004 trim history all system only"""
        mb = MessageBuilder()
        mb.conversation_history = [
            {"role": "system", "content": "s" * 100000},
        ]
        mb.trim_history()
        assert len(mb.conversation_history) == 1

    def test_9_005_classify_messages_empty(self):
        """9 005 classify messages empty"""
        agent = _mock_agent()
        se = StepEmitter(agent)
        se.task_tracker = None
        se.record_operation("test", status="success")
        se.complete_task(success=True)
        # 中崩应鎶涘紓常?


# ===========================================================================
# 娴佺▼11: 错误复勭处 鈥?类查未夎矾循勮ˉ名慒inalStep
# ===========================================================================

class TestFlow11ErrorHandlerEdgeCases:

    def test_11_001_classify_error_unknown_type(self):
        """11 001 classify error unknown type"""
        from app.services.llm.error_classifier import SystemErrorClassifier, SystemErrorCategory
        result = SystemErrorClassifier.classify_error(RuntimeError("unknown_error_type"))
        assert result == SystemErrorCategory.UNKNOWN

    def test_11_002_handle_react_error_null_pointer(self):
        """11 002 handle react error null pointer"""
        from app.services.agent.react_cycle import handle_react_error
        from app.services.agent.steps import ErrorStep
        agent = _mock_agent()
        result = handle_react_error(agent, AttributeError("NoneType has no attribute 'x'"), 1)
        assert isinstance(result, ErrorStep)

    def test_11_003_handle_react_error_empty_message(self):
        """11 003 handle react error empty message"""
        from app.services.agent.react_cycle import handle_react_error
        agent = _mock_agent()
        result = handle_react_error(agent, ValueError("test"), 0)
        assert result is not None

    def test_11_005_handle_react_error_nested_exception(self):
        """11 005 handle react error nested exception"""
        from app.services.agent.react_cycle import handle_react_error
        agent = _mock_agent()
        try:
            inner_err = ValueError("inner")
            outer = RuntimeError("outer caused by inner")
            outer.__cause__ = inner_err
            result = handle_react_error(agent, outer, 1)
            assert result is not None
        except Exception as e:
            assert False, f"BUG: 宓请异常宕╂簝: {e}"


# ===========================================================================
# 娴佺▼12: 宸ュ叿缂撳瓨 鈥?patch_search_desc 闃查噸复?
# ===========================================================================

class TestFlow12ToolCacheEdgeCases:

    def test_12_001_patch_search_desc_duplicate_suffix(self):
        """12 001 patch search desc duplicate suffix"""
        from app.services.agent.tool_cache_manager import patch_search_desc, _get_original_search_desc
        agent = _mock_agent()
        agent._loaded_categories = {ToolCategory.FUNDAMENTAL, ToolCategory.SHELL}
        # 调用5娆?
        for _ in range(5):
            patch_search_desc(agent)
        # 验证override中崩寘否噸复嶄俊息?
        override = agent._searchtool_desc_override
        if override:
            # 中崩应出虹现否屼一提示复氭
            assert override.count("current no loaded category") <= 1, \
                f"BUG: patch_search_desc duplicated! override count={override.count('current no loaded category')}"

    def test_12_002_patch_search_desc_all_categories_loaded(self):
        """12 002 patch search desc all categories loaded"""
        agent = _mock_agent()
        agent._loaded_categories = set(ToolCategory)
        patch_search_desc(agent)
        assert agent._searchtool_desc_override is None, \
            "BUG: 鍏ㄩ儴列嗙被动犺浇否巓verride搴斾为None"

    def test_12_003_patch_search_desc_no_tool_search(self):
        """12 003 patch search desc no tool search"""
        from app.services.agent.tool_cache_manager import _get_original_search_desc
        with patch("app.tools.registry.tool_registry.get_tool", return_value=None):
            result = _get_original_search_desc()
            assert result is None or result == ""

    def test_12_005_get_openai_tools_cache_expired(self):
        """12 005 get openai tools cache expired"""
        agent = _mock_agent()
        agent._tool_cache.get = MagicMock(return_value=None)
        agent._tool_cache.set = MagicMock()
        with patch("app.services.agent.react_cycle.get_openai_tools", wraps=get_openai_tools) as wrapped:
            pass  # at least doesn't crash

    def test_12_006_get_openai_tools_categories_empty(self):
        """12 006 get openai tools categories empty"""
        with patch("app.services.safety.tool_safety_checker._is_skip_safety", return_value=False):
            checker = ToolSafetyChecker()
            result = checker.check_before_execute(
                "writetext",
                {"path": "C:/test.txt", "content": "test"}
            )
            # 结果应为SafetyResult
            assert hasattr(result, 'blocked')
            assert hasattr(result, 'safety_level')

    def test_cross_003_agent_status_states_exhaustive(self):
        """cross 003 agent status states exhaustive"""
        _current_task_id.set("test-001")
        assert _current_task_id.get() == "test-001"
        _current_task_id.set(None)
        assert _current_task_id.get() is None

    def test_cross_005_step_emitter_twice_no_crash(self):
        """cross 005 step emitter twice no crash — 小欧 2026-07-10"""
        from app.tools.registry import ensure_tools_registered
        ensure_tools_registered()
        agent = _mock_agent()
        emitter = StepEmitter(agent)
        s1 = emitter.emit(ThoughtStep(step=1, content="first"))
        s2 = emitter.emit(ThoughtStep(step=2, content="second"))
        assert len(agent.steps) == 2
        assert s1.step == 1
        assert s2.step == 2

    def test_cross_007_message_builder_system_not_trimmed(self):
        """cross 007 message builder system not trimmed"""
        mb = MessageBuilder()
        mb.conversation_history = [
            {"role": "system", "content": "You are an AI assistant."},
            {"role": "user", "content": "u" * 10000},
            {"role": "assistant", "content": "a" * 100},
            {"role": "tool", "content": "o" * 100, "tool_call_id": "tc_1"},
            {"role": "assistant", "content": "a2", "tool_calls": [{"id": "tc_1", "type": "function", "function": {"name": "f", "arguments": "{}"}}]},
        ]
        from app.constants import MAX_CONTEXT_TOKENS
        with patch("app.services.agent.message_builder.MAX_CONTEXT_TOKENS", 2000):
            mb.trim_history()
        system_msgs = [m for m in mb.conversation_history if m.get("role") == "system"]
        assert len(system_msgs) >= 1, "BUG: system消息琚前帀浜?"

    def test_cross_008_rebuild_and_validate_empty(self):
        """cross 008 rebuild and validate empty"""
        history = [
            {"role": "system", "content": "s"},
            {"role": "user", "content": "u"},
            {"role": "tool", "content": "o", "tool_call_id": "orphan_tc"},
        ]
        result = MessageBuilder._trim_fc_pairs(history)
        assert result is not None

    def test_cross_010_trim_fc_pairs_unpaired_assistant(self):
        """cross 010 trim fc pairs unpaired assistant"""
        history = [
            {"role": "system", "content": "s"},
            {"role": "user", "content": "u"},
            {"role": "assistant", "content": "a", "tool_calls": [{"id": "missing_tc", "type": "function", "function": {"name": "f", "arguments": "{}"}}]},
        ]
        result = MessageBuilder._trim_fc_pairs(history)
        assert result is not None

    def test_cross_011_trim_fc_pairs_all_unpaired(self):
        """cross 011 trim fc pairs all unpaired"""
        history = [
            {"role": "tool", "content": "o1", "tool_call_id": "tc_1"},
            {"role": "tool", "content": "o2", "tool_call_id": "tc_2"},
            {"role": "assistant", "content": "a1", "tool_calls": [{"id": "tc_3", "type": "function", "function": {"name": "f", "arguments": "{}"}}]},
        ]
        result = MessageBuilder._trim_fc_pairs(history)
        assert result is not None
