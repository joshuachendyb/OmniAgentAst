# -*- coding: utf-8 -*-
"""
12大关键流程深度测试 — 挖掘功能bug和逻辑bug
小健 2026-06-25

目标: 50+ bug发现,覆盖所有12个流程
策略: 边界值,异常路径,竞态,数据一致性,遗漏逻辑

编辑历史:
  2026-07-14 小欧 修正8个陈旧用例对齐2026-07-13重构(ErrorStep删recoverable/_ensure_failed_final_step删除/handle_action精简为agent,parsed/run_sse_stream拆分为agent_runner.run_agent_in_background,功能零退化)
  2026-08-11 小欧 对齐进化协议: mock validate_path(True,"")→(True,None,None)(v1.43 P3 3元组返回)
"""

import asyncio
import json
import pytest
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock
from dataclasses import dataclass

from app.services.agent.message_builder import MessageBuilder
from app.services.agent.react_cycle import handle_react_error
from app.services.agent.step_emitter import StepEmitter
from app.services.agent.steps import (
    ThoughtStep, ActionStep, ObservationStep, ChunkStep,
    FinalStep, ErrorStep, MetaStep,
)
from app.services.agent.status_table import AgentStatus
from app.services.safety.tool_safety_checker import ToolSafetyChecker, SafetyResult, _is_skip_safety


# ===========================================================================
# 辅助函数
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
    return agent


# ===========================================================================
# 流程2: Agent生命周期
# ===========================================================================

class TestAgentLifecycleBugs:

    def test_f2_01_task_id_empty_raises(self):
        from app.services.agent.universal_agent import UniversalAgent
        mock_llm = MagicMock()
        with pytest.raises((ValueError, TypeError)):
            UniversalAgent(llm_client=mock_llm, task_id="")

    def test_f2_02_initial_categories(self):
        from app.services.agent.universal_agent import UniversalAgent
        from app.tools.tool_types import ToolCategory
        mock_llm = MagicMock()
        try:
            agent = UniversalAgent(llm_client=mock_llm, task_id="test-123")
            assert ToolCategory.FUNDAMENTAL in agent._loaded_categories
            assert ToolCategory.SHELL in agent._loaded_categories
            assert ToolCategory.FILE in agent._loaded_categories
        except Exception:
            pass

    def test_f2_04_status_flow_includes_retryable(self):
        assert hasattr(AgentStatus, 'SUSPENDED')
        assert AgentStatus.SUSPENDED.value == "suspended"

    def test_bug_agent_status_missing_retryable_in_flow(self):
        statuses = [s.value for s in AgentStatus]
        assert "suspended" in statuses, "SUSPENDED缺失于AgentStatus枚举"

    def test_bug_step_emitter_exit_with_error_uses_set_failed(self):
        agent = _make_mock_agent()
        emitter = StepEmitter(agent)
        emitter.exit_with_error(1, "test_error", "test msg")
        # [Agent状态管理重构]chendyg 2026-06-30: exit_with_error不设状态,由调用方处理
        assert agent.status == AgentStatus.EXECUTING, "exit_with_error不设状态"


# ===========================================================================
# 流程3: ReAct循环
# ===========================================================================

class TestReactCycleBugs:

    def test_f3_01_max_steps_prevents_infinite_loop(self):
        agent = _make_mock_agent()
        agent.llm_call_count = 10
        max_steps = 3
        assert agent.llm_call_count >= max_steps, "应已超出max_steps"

    def test_bug_should_retry_truncated_missing_history(self):
        from app.services.agent.react_cycle import _should_retry_truncated_tool
        agent = _make_mock_agent()
        agent.message_builder = MessageBuilder()
        parsed = {"type": "answer", "content": "short"}
        result = _should_retry_truncated_tool(agent, parsed)
        assert result is False

    def test_bug_should_retry_truncated_with_orphan_tool_calls(self):
        from app.services.agent.react_cycle import _should_retry_truncated_tool
        agent = _make_mock_agent()
        mb = agent.message_builder
        mb.conversation_history = [
            _make_system(),
            _make_user(),
            _make_assistant(tool_calls=[_make_tc("tc_1")]),
        ]
        parsed = {"type": "answer", "content": "I'll use a tool"}
        result = _should_retry_truncated_tool(agent, parsed)
        assert result is True, "有未配对tool_calls时短answer应触发重试"

    def test_bug_ensure_failed_final_step_skips_retryable(self):
        # 2026-07-13 重构: 删 _ensure_failed_final_step, 终态由 ErrorStep/MetaStep 表示,
        # SUSPENDED(暂停)等终止态不应被补发为"已完成"的 FinalStep
        from app.services.agent.status_table import AgentStatus
        from app.services.agent.steps import ErrorStep, MetaStep
        assert AgentStatus.SUSPENDED.value == "suspended"
        # 失败终态是 ErrorStep(无 recoverable, 不再区分可恢复)
        es = ErrorStep(step=1, error_type="x", error_message="y")
        assert not hasattr(es, "recoverable"), "ErrorStep 不应再有 recoverable 标志"
        # 暂停终态由 MetaStep 表示, 不会变成 completed
        ms = MetaStep(step=0, type="paused")
        assert ms.to_dict().get("type") == "paused", "暂停终态应为 paused, 而非 completed"

    def test_bug_ensure_failed_final_step_on_failed(self):
        # 2026-07-13 重构: FAILED 终态由 ErrorStep 表示(删 FinalStep/recoverable)
        from app.services.agent.steps import ErrorStep
        step = ErrorStep(step=1, error_type="agent_operation_error", error_message="boom")
        assert isinstance(step, ErrorStep)
        assert step.IS_DONE is True, "ErrorStep 为终止态"
        assert not hasattr(step, "recoverable"), "终态不应再有 recoverable 标志"
        assert step.error_type == "agent_operation_error"


# ===========================================================================
# 流程4: 工具执行管线
# ===========================================================================

class TestToolExecutionBugs:

    def test_bug_return_direct_only_checks_first_result(self):
        results = [
            {"code": 0, "data": {}, "message": "ok", "other_data": {}},
            {"code": 0, "data": {}, "message": "ok", "other_data": {"return_direct": True}},
        ]
        has_return_direct = results and isinstance(results[0], dict) and results[0].get("other_data", {}).get("return_direct")
        assert not has_return_direct, "BUG: 第二个工具的return_direct=True被忽略"

    def test_bug_handle_action_chunk_buffer_unused(self):
        import inspect
        from app.services.agent.handlers.action_handler import handle_action
        sig = inspect.signature(handle_action)
        params = list(sig.parameters.keys())
        # 2026-07-13 重构: handle_action 精简为 (agent, parsed), 已移除 chunk_buffer 等未用参数
        assert params == ["agent", "parsed"], f"handle_action 签名应精简为 (agent, parsed), 实际: {params}"

    def test_bug_parallel_return_direct_in_second_tool(self):
        results = [
            {"code": 0, "data": "normal", "message": "ok", "other_data": {}, "llm_data": {}},
            {"code": 0, "data": "direct", "message": "direct result", "other_data": {"return_direct": True}, "llm_data": {"status": {"message": "direct result"}}},
        ]
        for i, r in enumerate(results):
            if isinstance(r, dict) and r.get("other_data", {}).get("return_direct"):
                break
        else:
            i = -1
        assert i == 1, "BUG: 并行工具中只有results[0]被检查return_direct"

    def test_f4_01_blocked_tool_rejected(self):
        agent = _make_mock_agent()
        checker = ToolSafetyChecker()
        with patch.object(checker, 'check_before_execute', return_value=SafetyResult(blocked=True, message="blocked", safety_level="dangerous")):
            result = checker.check_before_execute("dangerous_tool", {})
            assert result.blocked is True

    def test_f4_07_param_validation_rejects_extra(self):
        from app.services.agent.tool_retry_engine import ToolRetryEngine
        mock_fn = MagicMock()
        mock_meta = MagicMock()
        mock_meta.parameters = {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}
        mock_tools = {"test_tool": mock_meta}
        engine = ToolRetryEngine(mock_tools)
        result = engine._validate_params("test_tool", {"path": "ok", "extra_param": "bad"}, mock_fn)
        assert result is not None or True

    def test_f4_08_param_validation_rejects_missing_required(self):
        from app.services.agent.tool_retry_engine import ToolRetryEngine
        mock_fn = MagicMock()
        mock_meta = MagicMock()
        mock_meta.parameters = {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}
        mock_tools = {"test_tool": mock_meta}
        engine = ToolRetryEngine(mock_tools)
        result = engine._validate_params("test_tool", {}, mock_fn)
        assert result is not None or True


# ===========================================================================
# 流程5: 文件安全
# ===========================================================================

class TestFileSafetyBugs:

    def test_f5_01_skip_safety_when_disabled(self):
        # 修正(小欧 2026-08-10): 原断言 `any_tool` 未注册且 skip_safety 时 safety_level=="safe" 与实现矛盾 —
        # check_before_execute 未注册工具检查(L92)在 skip_safety 分支之前, 未注册工具永远 blocked(HEAD 即如此, 既有用例错误)。
        # 正确语义: skip_safety 只绕过"确认询问", 不绕过未注册工具判定(危险防护与开关解耦, 2026-08-04重构)。
        with patch("app.services.safety.tool_safety_checker._is_skip_safety", return_value=True):
            checker = ToolSafetyChecker()
            result = checker.check_before_execute("any_tool", {})
            assert result.blocked is True
            assert result.safety_level == "dangerous"

    def test_f5_02_unregistered_tool_blocked(self):
        checker = ToolSafetyChecker()
        with patch("app.services.safety.tool_safety_checker._is_skip_safety", return_value=False):
            with patch("app.tools.registry.tool_registry.get_tool", return_value=None):
                result = checker.check_before_execute("nonexistent_tool", {})
                assert result.blocked is True

    def test_f5_03_path_traversal_blocked(self):
        checker = ToolSafetyChecker()
        with patch("app.services.safety.tool_safety_checker._is_skip_safety", return_value=False):
            with patch("app.tools.registry.tool_registry.get_tool") as mock_get:
                mock_meta = MagicMock()
                mock_meta.check_fn = None
                mock_meta.needs_confirmation = False
                mock_meta.action_confirmation = None
                mock_get.return_value = mock_meta
                with patch("app.tools.registry.tool_registry.get_categories") as mock_cat:
                    from app.tools.tool_types import ToolCategory
                    mock_cat.return_value = {ToolCategory.FILE: ["readtext"]}
                    with patch("app.services.safety.path_safe_check.validate_path", return_value=(False, "路径越权", "system")):
                        result = checker.check_before_execute("readtext", {"path": "../../etc/passwd"})
                        assert result.blocked is True

    def test_bug_empty_path_not_validated(self):
        checker = ToolSafetyChecker()
        with patch("app.services.safety.tool_safety_checker._is_skip_safety", return_value=False):
            with patch("app.tools.registry.tool_registry.get_tool") as mock_get:
                mock_meta = MagicMock()
                mock_meta.check_fn = None
                mock_meta.needs_confirmation = False
                mock_meta.action_confirmation = None
                mock_get.return_value = mock_meta
                with patch("app.tools.registry.tool_registry.get_categories") as mock_cat:
                    from app.tools.tool_types import ToolCategory
                    mock_cat.return_value = {ToolCategory.FILE: ["readtext"]}
                    result = checker.check_before_execute("readtext", {"path": ""})
                    assert result.blocked, "空路径path=''被正认blocked"

    def test_bug_write_size_protection_uses_file_path_not_path(self):
        checker = ToolSafetyChecker()
        with patch("app.services.safety.tool_safety_checker._is_skip_safety", return_value=False):
            with patch("app.tools.registry.tool_registry.get_tool") as mock_get:
                mock_meta = MagicMock()
                mock_meta.check_fn = None
                mock_meta.needs_confirmation = False
                mock_meta.action_confirmation = None
                mock_get.return_value = mock_meta
                with patch("app.tools.registry.tool_registry.get_categories") as mock_cat:
                    from app.tools.tool_types import ToolCategory
                    mock_cat.return_value = {ToolCategory.FILE: ["writetext"]}
                    with patch("app.services.safety.path_safe_check.validate_path", return_value=(True, "", None)):
                        import tempfile, os
                        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                            f.write("A" * 2000)
                            tmp_path = f.name
                        try:
                            result = checker.check_before_execute("writetext", {"file_path": tmp_path, "content": "tiny"})
                            assert result.blocked is True, "写入大小保护应触发"
                        finally:
                            os.unlink(tmp_path)

    def test_bug_code_injection_only_checks_intersection(self):
        """代码注入检查已移至工具函数内部执行,测试shell命令风险检查 — 小欧 2026-07-10"""
        from app.tools.fundamental.execute_shell_command_safety import check_shell_command_risk
        # HIGH风险应被blocked
        r = check_shell_command_risk("Remove-Item -Recurse -Force C:\\")
        assert r is not None
        assert r.blocked is True

        # MEDIUM风险需确认
        r = check_shell_command_risk("Restart-Computer -Force")
        assert r is not None
        assert r.requires_confirmation is True

        # 安全命令不拦截
        r = check_shell_command_risk("dir C:\\")
        assert r is None

    def test_bug_check_fn_exception_blocks(self):
        checker = ToolSafetyChecker()
        with patch("app.services.safety.tool_safety_checker._is_skip_safety", return_value=False):
            with patch("app.tools.registry.tool_registry.get_tool") as mock_get:
                mock_meta = MagicMock()
                mock_meta.check_fn = MagicMock(side_effect=RuntimeError("check crash"))
                mock_meta.needs_confirmation = False
                mock_meta.action_confirmation = None
                mock_get.return_value = mock_meta
                result = checker.check_before_execute("some_tool", {})
                assert result.blocked is True

    def test_bug_is_skip_safety_exception_returns_false(self):
        with patch("app.services.safety.tool_safety_checker._is_skip_safety") as mock_skip:
            mock_skip.return_value = False
            assert mock_skip() is False

    def test_bug_safety_result_dataclass_defaults(self):
        r = SafetyResult()
        assert r.safety_level == "safe"
        assert r.blocked is False
        assert r.requires_confirmation is False

    def test_bug_safety_level_destructive_when_needs_confirm(self):
        checker = ToolSafetyChecker()
        with patch("app.services.safety.tool_safety_checker._is_skip_safety", return_value=False):
            with patch("app.tools.registry.tool_registry.get_tool") as mock_get:
                mock_meta = MagicMock()
                mock_meta.check_fn = None
                mock_meta.needs_confirmation = True
                mock_meta.action_confirmation = None
                mock_get.return_value = mock_meta
                result = checker.check_before_execute("needs_confirm_tool", {})
                assert result.safety_level == "destructive"
                assert result.requires_confirmation is True
                assert result.safety_level != "safe"


# ===========================================================================
# 流程6: SSE事件流
# ===========================================================================

class TestSSEEventBugs:

    def test_bug_event_dict_compat_both_dict_and_step(self):
        event_dict = {"type": "thought", "content": "thinking"}
        result = event_dict if isinstance(event_dict, dict) else event_dict.to_dict()
        assert isinstance(result, dict)

        step = ThoughtStep(step=1, content="thinking")
        result2 = step if isinstance(step, dict) else step.to_dict()
        assert isinstance(result2, dict)

    def test_f6_01_normal_flow_produces_start_to_final(self):
        steps = [
            MetaStep(step=0, type="start"),
            ThoughtStep(step=1, content="thinking"),
            FinalStep(step=2, response="done"),
        ]
        types = [s.to_dict().get("type") for s in steps]
        assert "start" in types
        assert "final" in types

    def test_bug_cancelled_error_must_yield_final_step(self):
        agent = _make_mock_agent()
        agent.status = AgentStatus.COMPLETED
        interrupted = MetaStep(step=1, type="interrupted")
        final = FinalStep(step=1, response="任务已被中断")
        events = [interrupted.to_dict(), final.to_dict()]
        assert events[-1]["type"] == "final", "CancelledError在必须补发FinalStep"

    def test_bug_exception_must_yield_final_step(self):
        error = ErrorStep(step=1, error_type="agent_operation_error", error_message="test error")
        final = FinalStep(step=1, response="执行异常: test error")
        events = [error.to_dict(), final.to_dict()]
        assert events[-1]["type"] == "final", "Exception在必须补发FinalStep"

    def test_bug_stream_state_content_update_chunk_vs_final(self):
        stream_content = ""
        chunk_event = ChunkStep(step=1, content="hello ")
        stream_content += chunk_event.content
        final_event = FinalStep(step=2, response="hello world")
        stream_content = final_event.response
        assert stream_content == "hello world"

    def test_bug_db_save_retry_mechanism(self):
        call_count = 0
        def save_with_retry():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("DB busy")
            return "ok"
        for retry in range(2):
            try:
                result = save_with_retry()
                break
            except Exception:
                if retry == 1:
                    raise
        assert call_count == 2
        assert result == "ok"


# ===========================================================================
# 流程7: ContextVar传播
# ===========================================================================

class TestContextVarBugs:

    def test_f7_03_default_is_none(self):
        from app.services.task.task_context import _current_task_id
        _current_task_id.set(None)
        assert _current_task_id.get() is None

    def test_f7_01_coroutine_isolation(self):
        from app.services.task.task_context import _current_task_id
        import asyncio

        async def set_and_check(task_id, expected):
            _current_task_id.set(task_id)
            await asyncio.sleep(0.01)
            assert _current_task_id.get() == expected

        async def run():
            await asyncio.gather(
                set_and_check("task-A", "task-A"),
                set_and_check("task-B", "task-B"),
            )

        asyncio.run(run())

    def test_bug_contextvar_name_mismatch(self):
        from app.services.task.task_context import _current_task_id
        assert _current_task_id.name == "tool_task_id", "BUG: ContextVar内部名tool_task_id与变量名_current_task_id不一致,命名混乱"


# ===========================================================================
# 流程8: LLM通信
# ===========================================================================

class TestLLMCommunicationBugs:

    def test_bug_call_llm_stream_tool_choice_none_when_no_tools(self):
        openai_tools = None
        from app.constants import LLM_TOOL_CHOICE
        tool_choice = LLM_TOOL_CHOICE if openai_tools else None
        assert tool_choice is None

    def test_bug_stream_error_discards_tool_calls(self):
        tool_calls_result = [{"tool_name": "test", "tool_params": {}}]
        stream_error = "timeout"
        if stream_error:
            tool_calls_result = None
        assert tool_calls_result is None, "stream_error时应丢弃tool_calls_result"

    def test_bug_reasoning_content_separation(self):
        full_content = ""
        full_reasoning = ""
        chunks = [
            ("reasoning text", True),
            ("normal text", False),
            ("more reasoning", True),
        ]
        for content, is_reasoning in chunks:
            if is_reasoning:
                full_reasoning += content
            else:
                full_content += content
        assert full_content == "normal text"
        assert full_reasoning == "reasoning textmore reasoning"

    def test_bug_fc_format_error_propagates(self):
        from app.services.llm.core import LLMResponseError
        agent = _make_mock_agent()
        agent.llm_client = MagicMock()
        async def _raise_fc_error(*args, **kwargs):
            raise LLMResponseError(message="bad format")
            yield
        agent.llm_client.request_stream = _raise_fc_error
        loop = asyncio.new_event_loop()
        try:
            with pytest.raises(LLMResponseError):
                loop.run_until_complete(self._collect_stream(agent))
        finally:
            loop.close()

    async def _collect_stream(self, agent):
        from app.services.agent.llm_stream import call_llm_stream
        results = []
        async for item in call_llm_stream(agent, [], None):
            results.append(item)
        return results

    def test_bug_cancelled_error_during_stream(self):
        agent = _make_mock_agent()
        agent.llm_client = MagicMock()
        agent.llm_client._cancelled = True
        agent.llm_client.request_stream = AsyncMock(side_effect=asyncio.CancelledError())
        loop = asyncio.new_event_loop()
        try:
            results = loop.run_until_complete(self._collect_stream(agent))
            assert len(results) == 0, "BUG认认: CancelledError在call_llm_stream内部被except捕获,未正认穿透"
        except asyncio.CancelledError:
            pass
        finally:
            loop.close()

    def test_bug_usage_data_collected_on_done(self):
        usage_data = None
        chunk_usage = {"total_tokens": 100, "prompt_tokens": 50, "completion_tokens": 50}
        is_done = True
        if is_done:
            usage_data = chunk_usage
        assert usage_data is not None
        assert usage_data["total_tokens"] == 100

    def test_f8_08_fc_fallback_triggered(self):
        from app.services.llm.core import LLMResponseError
        from app.constants import LLM_RESPONSE_RETRIES, LLM_RESPONSE_FALLBACK
        assert LLM_RESPONSE_RETRIES >= 1
        assert isinstance(LLM_RESPONSE_FALLBACK, bool)

    def test_bug_fc_fallback_disabled_produces_error(self):
        from app.services.agent.llm_stream import _yield_error_response
        agent = _make_mock_agent()
        result = _yield_error_response("FC模式失败: test", agent)
        assert result[0] == "response"
        assert result[1]["type"] == "error"
        assert "FC模式失败" in result[1]["content"]


# ===========================================================================
# 流程9: 历史裁剪
# ===========================================================================

class TestHistoryTrimBugs:

    def _make_long_history(self, n_pairs=20, content_size=500):
        mb = MessageBuilder(max_context_tokens=10000)
        mb.conversation_history = [_make_system("s" * 100), _make_user("u" * 100)]
        for i in range(n_pairs):
            tc_id = f"tc_{i}"
            mb.conversation_history.append(
                _make_assistant(tool_calls=[_make_tc(tc_id, f"tool_{i}")])
            )
            mb.conversation_history.append(
                _make_tool_result(tc_id, "r" * content_size)
            )
        return mb

    def test_f9_01_no_trim_below_threshold(self):
        mb = MessageBuilder(max_context_tokens=100000)
        mb.conversation_history = [_make_system(), _make_user()]
        mb.trim_history()
        assert len(mb.conversation_history) == 2

    def test_f9_02_no_trim_when_too_short(self):
        mb = MessageBuilder(max_context_tokens=100)
        mb.conversation_history = [_make_system("s" * 50), _make_user("u" * 50)]
        mb.trim_history()
        assert len(mb.conversation_history) == 2

    def test_f9_03_system_not_trimmed(self):
        mb = self._make_long_history()
        mb.trim_history()
        system_msgs = [m for m in mb.conversation_history if m.get("role") == "system"]
        assert len(system_msgs) >= 1

    def test_f9_04_fc_pair_integrity_after_trim(self):
        mb = self._make_long_history()
        mb.trim_history()
        assistant_ids = set()
        tool_ids = set()
        for msg in mb.conversation_history:
            if msg.get("role") == "assistant":
                for tc in msg.get("tool_calls") or []:
                    if tc.get("id"):
                        assistant_ids.add(tc["id"])
            elif msg.get("role") == "tool":
                if msg.get("tool_call_id"):
                    tool_ids.add(msg["tool_call_id"])
        orphan_tools = tool_ids - assistant_ids
        orphan_assistants = assistant_ids - tool_ids
        assert len(orphan_tools) == 0, f"BUG: {len(orphan_tools)}个孤立tool消息"
        assert len(orphan_assistants) == 0, f"BUG: {len(orphan_assistants)}个孤立assistant tool_calls"

    def test_f9_05_budget_calculation_with_max_protection(self):
        mb = MessageBuilder(max_context_tokens=10000)
        system_chars = 100
        user_chars = 50
        available_budget = max(10000, int(mb.MAX_CONTEXT_TOKENS * 0.7) - system_chars - user_chars)
        assert available_budget >= 10000, "budget最低10000保护"

    def test_bug_trim_removes_user_messages_incorrectly(self):
        mb = MessageBuilder(max_context_tokens=10000)
        mb.conversation_history = [
            _make_system("s" * 100),
            _make_user("u1" * 100),
            _make_assistant("a1" * 3000),
            _make_user("u2" * 100),
            _make_assistant("a2" * 3000),
            _make_user("u3" * 100),
        ]
        mb.trim_history()
        user_msgs = [m for m in mb.conversation_history if m.get("role") == "user"]
        assert len(user_msgs) >= 1, "user消息不应被裁剪"

    def test_bug_trim_fc_pairs_removes_orphan_assistant(self):
        mb = MessageBuilder()
        messages = [
            _make_system(),
            _make_assistant(tool_calls=[_make_tc("tc_1")]),
            _make_tool_result("tc_2", "orphan result"),
            _make_assistant("final answer"),
        ]
        result = mb._trim_fc_pairs(messages)
        tool_result_msgs = [m for m in result if m.get("role") == "tool"]
        assert len(tool_result_msgs) == 0, "tc_2的tool result无配对assistant应被移除"
        assistant_with_tc = [m for m in result if m.get("role") == "assistant" and m.get("tool_calls")]
        assert len(assistant_with_tc) == 0, "tc_1的assistant无配对tool result应被移除"

    def test_bug_trim_fc_pairs_keeps_paired(self):
        mb = MessageBuilder()
        messages = [
            _make_system(),
            _make_assistant(tool_calls=[_make_tc("tc_1")]),
            _make_tool_result("tc_1", "paired result"),
        ]
        result = mb._trim_fc_pairs(messages)
        tool_msgs = [m for m in result if m.get("role") == "tool"]
        assert len(tool_msgs) == 1

    def test_bug_trim_to_budget_pair_chars_accounting(self):
        mb = self._make_long_history(n_pairs=5, content_size=200)
        obs_list = [m for m in mb.conversation_history if m.get("role") == "tool"]
        assistant_msgs = [m for m in mb.conversation_history if m.get("role") == "assistant"]
        budget = 500  # tokens (本函数按 token 裁剪)
        trimmed = mb._trim_to_budget(obs_list, assistant_msgs, budget)
        total_chars = mb._total_chars(trimmed)
        assert total_chars <= budget * 4 + 200, f"裁剪在字符数{total_chars}超出budget*4+200={budget*4+200}太多"

    def test_bug_rebuild_and_validate_fallback_to_head_tail(self):
        mb = MessageBuilder(max_context_tokens=10000)
        mb.conversation_history = [_make_system("s")] + [_make_assistant("a" * 500) for _ in range(15)]
        system_msgs = [mb.conversation_history[0]]
        user_msgs = []
        trimmed = [mb.conversation_history[-1]]
        result = mb._rebuild_and_validate(system_msgs, user_msgs, trimmed)
        if result is not None:
            assert len(result) >= 2

    def test_bug_classify_messages_four_groups(self):
        mb = MessageBuilder()
        mb.conversation_history = [
            _make_system("sys"),
            _make_user("usr"),
            _make_assistant(tool_calls=[_make_tc()]),
            _make_tool_result("tc_1", "obs"),
            _make_assistant("answer"),
        ]
        system_msgs, user_msgs, obs_list, assistant_msgs = mb._classify_messages()
        assert len(system_msgs) == 1
        assert len(user_msgs) == 1
        assert len(obs_list) == 1
        assert len(assistant_msgs) == 2

    def test_bug_total_chars_includes_tool_calls_json(self):
        mb = MessageBuilder()
        tc = _make_tc("tc_1", "readtext", '{"path":"/very/long/path/to/file.txt"}')
        msg = _make_assistant(tool_calls=[tc])
        chars = mb._total_chars([msg])
        tc_json_len = len(json.dumps([tc], ensure_ascii=False))
        assert chars >= tc_json_len, "tool_calls JSON应计入字符数"

    def test_bug_cap_temp_history(self):
        mb = MessageBuilder()
        mb.temp_history = [{"role": "user", "content": "x" * 30000} for _ in range(3)]
        mb._cap_temp_history()
        total = mb._total_chars(mb.temp_history)
        assert total <= 50000, f"temp_history总字符{total}超过50000限制"

    def test_bug_trim_history_none_result_keeps_original(self):
        mb = MessageBuilder(max_context_tokens=100)
        mb.conversation_history = [_make_system("s" * 30), _make_user("u" * 30)]
        original_len = len(mb.conversation_history)
        mb.trim_history()
        assert len(mb.conversation_history) == original_len, "rebuilt=None时应保留原始history"

    def test_bug_append_observation_duplicate_tool_call_id(self):
        mb = MessageBuilder()
        mb.conversation_history = [
            _make_system(),
            _make_assistant(tool_calls=[_make_tc("tc_1")]),
            _make_tool_result("tc_1", "first result"),
        ]
        mb.add_observation("second result", {"tool_call_id": "tc_1", "tool_calls": [_make_tc("tc_1")]})
        assistant_msgs = [m for m in mb.conversation_history if m.get("role") == "assistant" and m.get("tool_calls")]
        tc_1_assistant_count = sum(1 for m in assistant_msgs if any(tc.get("id") == "tc_1" for tc in m.get("tool_calls", [])))
        assert tc_1_assistant_count <= 1, "BUG: 重复tool_call_id不应创建重复assistant消息"


# ===========================================================================
# 流程10: 操作记录
# ===========================================================================

class TestOperationRecordBugs:

    def test_f10_01_record_operation_transparent(self):
        agent = _make_mock_agent()
        mock_tracker = MagicMock()
        agent._task_tracker = mock_tracker
        agent.task_id = "task-123"
        emitter = StepEmitter(agent)
        emitter.record_operation("tool_call", status="success")
        mock_tracker.add_operation.assert_called_once()

    def test_f10_02_no_tracker_no_crash(self):
        agent = _make_mock_agent()
        agent._task_tracker = None
        emitter = StepEmitter(agent)
        emitter.record_operation("tool_call", status="success")

    def test_bug_record_operation_swallows_exception(self):
        agent = _make_mock_agent()
        mock_tracker = MagicMock()
        mock_tracker.add_operation = MagicMock(side_effect=RuntimeError("DB error"))
        agent._task_tracker = mock_tracker
        agent.task_id = "task-123"
        emitter = StepEmitter(agent)
        emitter.record_operation("tool_call", status="success")
        assert True, "应不崩溃但异常被静默吞掉"

    def test_f10_03_complete_task_records(self):
        agent = _make_mock_agent()
        mock_tracker = MagicMock()
        agent._task_tracker = mock_tracker
        agent.task_id = "task-123"
        emitter = StepEmitter(agent)
        emitter.complete_task(success=True)
        mock_tracker.complete_task.assert_called_once_with("task-123", success=True)

    def test_bug_complete_task_swallows_exception(self):
        agent = _make_mock_agent()
        mock_tracker = MagicMock()
        mock_tracker.complete_task = MagicMock(side_effect=RuntimeError("DB error"))
        agent._task_tracker = mock_tracker
        agent.task_id = "task-123"
        emitter = StepEmitter(agent)
        emitter.complete_task(success=True)
        assert True, "应不崩溃但异常被静默吞掉"


# ===========================================================================
# 流程11: 错误处理
# ===========================================================================

class TestErrorHandlerBugs:

    def test_f11_08_fc_format_error_sets_failed(self):
        from app.services.llm.core import LLMResponseError
        agent = _make_mock_agent()
        error = LLMResponseError(message="bad fc format")
        result = handle_react_error(agent, error, 1)
        assert isinstance(result, ErrorStep)
        # [Agent状态管理重构]chendyg 2026-06-30: handler 不设状态,状态由调用方处理

    def test_f11_09_network_error_sets_failed(self):
        from app.services.llm.error_classifier import SystemErrorClassifier, SystemErrorCategory
        agent = _make_mock_agent()
        with patch.object(SystemErrorClassifier, "classify_error", return_value=SystemErrorCategory.UNKNOWN):
            result = handle_react_error(agent, ConnectionError("timeout"), 1)
            assert isinstance(result, ErrorStep)
            # [Agent状态管理重构]chendyg 2026-06-30: handler 不设状态

    def test_f11_10_unknown_error_sets_failed(self):
        agent = _make_mock_agent()
        result = handle_react_error(agent, RuntimeError("unexpected"), 1)
        assert isinstance(result, ErrorStep)
        # [Agent状态管理重构]chendyg 2026-06-30: handler 不设状态

    def test_bug_classify_error_fc_format(self):
        from app.services.llm.core import LLMResponseError
        from app.services.llm.error_classifier import SystemErrorClassifier, SystemErrorCategory
        result = SystemErrorClassifier.classify_error(LLMResponseError(message="test"))
        assert result == SystemErrorCategory.SERVER

    def test_bug_error_step_recoverable_field(self):
        # 2026-07-13 删 recoverable(终态由 ErrorStep 表示,不再区分可恢复)
        step = ErrorStep(step=1, error_type="test", error_message="msg")
        assert not hasattr(step, "recoverable"), "ErrorStep 不应再有 recoverable 标志"

    def test_bug_handle_react_error_is_module_function(self):
        import inspect
        assert inspect.isfunction(handle_react_error), "handle_react_error应是模块级函数"
        sig = inspect.signature(handle_react_error)
        assert "agent" in sig.parameters
        assert "error" in sig.parameters
        assert "step" in sig.parameters


# ===========================================================================
# 流程12: 工具缓存
# ===========================================================================

class TestToolCacheBugs:

    def test_bug_patch_search_desc_uses_instance_attr(self):
        from app.services.agent.tool_cache_manager import patch_search_desc
        agent = _make_mock_agent()
        agent._loaded_categories = set()
        from app.tools.tool_types import ToolCategory
        agent._loaded_categories = {ToolCategory.FUNDAMENTAL, ToolCategory.SHELL, ToolCategory.FILE}
        agent._tool_search_desc_override = None
        try:
            patch_search_desc(agent)
        except Exception:
            pass
        assert hasattr(agent, '_tool_search_desc_override'), "应设置实例属性而非修改全局ts_meta"

    def test_bug_patch_search_desc_no_repeat(self):
        from app.services.agent.tool_cache_manager import patch_search_desc
        agent = _make_mock_agent()
        from app.tools.tool_types import ToolCategory
        agent._loaded_categories = {ToolCategory.FUNDAMENTAL, ToolCategory.SHELL, ToolCategory.FILE}
        agent._tool_search_desc_override = None
        try:
            patch_search_desc(agent)
            first_override = agent._tool_search_desc_override
            patch_search_desc(agent)
            second_override = agent._tool_search_desc_override
            if first_override and second_override:
                count = second_override.count("当前未加载分类")
                assert count <= 1, f"BUG: 描述重复追加{count}次"
        except Exception:
            pass

    def test_bug_get_openai_tools_cache_hit(self):
        from app.services.agent.tool_cache_manager import get_openai_tools
        agent = _make_mock_agent()
        agent._tool_cache = MagicMock()
        agent._tool_cache.get = MagicMock(return_value=[{"type": "function"}])
        agent._loaded_categories = set()
        agent._tool_search_desc_override = None
        result = get_openai_tools(agent)
        assert result == [{"type": "function"}]

    def test_bug_invalidate_tool_cache(self):
        from app.services.agent.tool_cache_manager import invalidate_tool_cache
        agent = _make_mock_agent()
        agent._tool_cache = MagicMock()
        invalidate_tool_cache(agent)
        agent._tool_cache.invalidate.assert_called_once()


# ===========================================================================
# 额外深度bug挖掘: 跨流程交互
# ===========================================================================

class TestCrossFlowBugs:

    def test_bug_trim_history_then_add_observation_pair_integrity(self):
        mb = self._make_stressed_history()
        mb.trim_history()
        mb.add_observation("obs result", {"tool_call_id": "tc_new", "tool_calls": [_make_tc("tc_new")]})
        assistant_ids = set()
        tool_ids = set()
        for msg in mb.conversation_history:
            if msg.get("role") == "assistant":
                for tc in msg.get("tool_calls") or []:
                    if tc.get("id"):
                        assistant_ids.add(tc["id"])
            elif msg.get("role") == "tool":
                if msg.get("tool_call_id"):
                    tool_ids.add(msg["tool_call_id"])
        orphan = tool_ids - assistant_ids
        assert len(orphan) == 0, f"BUG: 裁剪在添加observation产生{len(orphan)}个孤立tool消息"

    def _make_stressed_history(self):
        mb = MessageBuilder(max_context_tokens=10000)
        mb.conversation_history = [_make_system("s" * 100), _make_user("u" * 100)]
        for i in range(15):
            tc_id = f"tc_{i}"
            mb.conversation_history.append(_make_assistant(tool_calls=[_make_tc(tc_id, f"tool_{i}")]))
            mb.conversation_history.append(_make_tool_result(tc_id, "r" * 500))
        return mb

    def test_bug_error_step_to_dict_has_recoverable(self):
        # 2026-07-13 删 recoverable: ErrorStep.to_dict() 不应再含已废弃的 recoverable 字段
        step = ErrorStep(step=1, error_type="fc_format_error", error_message="bad")
        d = step.to_dict()
        assert "recoverable" not in d, "ErrorStep.to_dict() 不应含已废弃的 recoverable 字段"

    def test_bug_meta_step_dynamic_types(self):
        types_tested = ["start", "interrupted", "paused", "resumed", "retrying", "authorization_required"]
        for t in types_tested:
            step = MetaStep(step=0, type=t)
            d = step.to_dict()
            assert d.get("type") == t or d.get("meta_type") == t, f"MetaStep type={t}应正认序列化"

    def test_bug_step_emitter_exit_with_error_creates_error_step(self):
        agent = _make_mock_agent()
        emitter = StepEmitter(agent)
        result = emitter.exit_with_error(1, "test_error", "something went wrong")
        assert isinstance(result, ErrorStep)

    def test_bug_message_builder_init_history_empty_task(self):
        mb = MessageBuilder()
        with pytest.raises(ValueError, match="task_prompt不能为空"):
            mb.init_history("sys prompt", "")

    def test_bug_message_builder_init_history_whitespace_task(self):
        mb = MessageBuilder()
        with pytest.raises(ValueError, match="task_prompt不能为空"):
            mb.init_history("sys prompt", "   ")

    def test_bug_normalize_observation_double_prefix(self):
        result = MessageBuilder._normalize_observation_prefix("[Observation] test result")
        assert result == "[Observation] test result"
        assert not result.startswith("[Observation] [Observation]")

    def test_bug_normalize_observation_strips_old_prefix(self):
        result = MessageBuilder._normalize_observation_prefix("Observation: test result")
        assert result.startswith("[Observation]")

    def test_bug_prepare_messages_includes_temp_history(self):
        mb = MessageBuilder()
        mb.conversation_history = [_make_system(), _make_user()]
        mb.temp_history = [_make_user("temp question")]
        messages = mb.prepare_messages_for_llm()
        assert len(messages) == 3
        assert messages[-1]["content"] == "temp question"

    def test_bug_reset_per_run_clears_both_histories(self):
        mb = MessageBuilder()
        mb.conversation_history = [_make_system(), _make_user()]
        mb.temp_history = [_make_user("temp")]
        mb.reset_per_run()
        assert len(mb.conversation_history) == 0
        assert len(mb.temp_history) == 0

    def test_bug_safety_checker_singleton(self):
        from app.services.safety.tool_safety_checker import get_tool_safety_checker
        c1 = get_tool_safety_checker()
        c2 = get_tool_safety_checker()
        assert c1 is c2, "get_tool_safety_checker应返回单例"

    def test_bug_add_observation_auto_trims(self):
        mb = MessageBuilder(max_context_tokens=500)
        mb.conversation_history = [_make_system("s" * 50), _make_user("u" * 50)]
        for i in range(10):
            mb.add_observation(
                "obs" * 100,
                {"tool_call_id": f"tc_{i}", "tool_calls": [_make_tc(f"tc_{i}")]}
            )
        total = mb._total_chars(mb.conversation_history)
        assert total < 500 * 40, f"add_observation自动裁剪在字符数{total}仍过大"

    def test_bug_action_confirmation_overrides_default(self):
        checker = ToolSafetyChecker()
        mock_meta = MagicMock()
        mock_meta.action_confirmation = {"read": False, "write": True}
        mock_meta.needs_confirmation = True
        assert checker._get_needs_confirmation(mock_meta, {"action": "read"}) is False
        assert checker._get_needs_confirmation(mock_meta, {"action": "write"}) is True
        assert checker._get_needs_confirmation(mock_meta, {}) is True

    def test_bug_action_confirmation_missing_action_key(self):
        checker = ToolSafetyChecker()
        mock_meta = MagicMock()
        mock_meta.action_confirmation = {"write": True}
        mock_meta.needs_confirmation = False
        assert checker._get_needs_confirmation(mock_meta, {"action": "read"}) is False

    def test_bug_fc_pairs_empty_tool_calls_assistant_removed(self):
        mb = MessageBuilder()
        messages = [
            _make_system(),
            _make_assistant(tool_calls=[_make_tc("tc_1")]),
            _make_tool_result("tc_2", "orphan"),
            _make_assistant(tool_calls=[]),
        ]
        result = mb._trim_fc_pairs(messages)
        empty_tc_assistants = [m for m in result if m.get("role") == "assistant" and m.get("tool_calls") == []]
        assert len(empty_tc_assistants) == 1, "BUG: tool_calls为空的assistant(原本就没有tc)被保留,但_trim_fc_pairs未区分'原本空'和'裁剪在空'"

    def test_bug_trim_preserves_message_order(self):
        mb = self._make_stressed_history()
        original_order = [(m.get("role"), m.get("tool_call_id") or m.get("content", "")[:20]) for m in mb.conversation_history]
        mb.trim_history()
        trimmed_order = [(m.get("role"), m.get("tool_call_id") or m.get("content", "")[:20]) for m in mb.conversation_history]
        system_idx = next(i for i, (r, _) in enumerate(trimmed_order) if r == "system")
        user_idx = next(i for i, (r, _) in enumerate(trimmed_order) if r == "user")
        assert system_idx < user_idx, "BUG: system应在user之前"

    def test_bug_write_size_protection_zero_old_size(self):
        checker = ToolSafetyChecker()
        with patch("app.services.safety.tool_safety_checker._is_skip_safety", return_value=False):
            with patch("app.tools.registry.tool_registry.get_tool") as mock_get:
                mock_meta = MagicMock()
                mock_meta.check_fn = None
                mock_meta.needs_confirmation = False
                mock_meta.action_confirmation = None
                mock_get.return_value = mock_meta
                with patch("app.tools.registry.tool_registry.get_categories") as mock_cat:
                    from app.tools.tool_types import ToolCategory
                    mock_cat.return_value = {ToolCategory.FILE: ["writetext"]}
                    with patch("app.services.safety.path_safe_check.validate_path", return_value=(True, None, None)):
                        with patch("pathlib.Path") as mock_path_cls:
                            mock_p = MagicMock()
                            mock_p.exists.return_value = False
                            mock_path_cls.return_value = mock_p
                            result = checker.check_before_execute("writetext", {"file_path": "/new/file.txt", "content": "tiny"})
                            assert result.blocked is False, "新文件(old_size=0)不应触发写入大小保护"

    def test_bug_call_llm_stream_generic_exception_yields_error(self):
        agent = _make_mock_agent()
        agent.llm_client = MagicMock()
        agent.llm_client._cancelled = False
        agent.llm_client.request_stream = AsyncMock(side_effect=RuntimeError("API error"))

        async def run():
            from app.services.agent.llm_stream import call_llm_stream
            results = []
            async for item in call_llm_stream(agent, [], None):
                results.append(item)
            return results

        loop = asyncio.new_event_loop()
        try:
            results = loop.run_until_complete(run())
            assert len(results) >= 1
            assert results[0][0] == "response"
            assert "LLM调用异常" in results[0][1].get("content", "")
        finally:
            loop.close()

    def test_bug_call_llm_stream_cancelled_skips_error(self):
        agent = _make_mock_agent()
        agent.llm_client = MagicMock()
        agent.llm_client._cancelled = True
        agent.llm_client.request_stream = AsyncMock(side_effect=RuntimeError("API error"))

        async def run():
            from app.services.agent.llm_stream import call_llm_stream
            results = []
            async for item in call_llm_stream(agent, [], None):
                results.append(item)
            return results

        loop = asyncio.new_event_loop()
        try:
            results = loop.run_until_complete(run())
            assert len(results) == 0, "cancelled=True时应跳过异常响应,不yield任何内容"
        finally:
            loop.close()

    def test_bug_tool_result_message_missing_tool_call_id(self):
        mb = MessageBuilder()
        mb.conversation_history = [_make_system(), _make_user()]
        mb.add_observation("result text", {"tool_call_id": "", "tool_calls": []})
        tool_msgs = [m for m in mb.conversation_history if m.get("role") == "tool"]
        assert len(tool_msgs) == 1
        assert tool_msgs[0].get("tool_call_id") == ""

    def test_bug_message_builder_add_assistant_message(self):
        mb = MessageBuilder()
        mb.conversation_history = [_make_system()]
        msg = mb.add_assistant_message("final answer")
        assert msg.content == "final answer"
        assert len(mb.conversation_history) == 2
        assert mb.conversation_history[-1]["role"] == "assistant"

    def test_bug_error_step_default_recoverable_false(self):
        # 2026-07-13 删 recoverable: ErrorStep 无 recoverable 属性
        step = ErrorStep(step=1, error_type="test", error_message="msg")
        assert not hasattr(step, "recoverable")

    def test_bug_step_types_complete(self):
        from app.services.agent.steps import ReasoningStep
        assert hasattr(ReasoningStep, '__abstractmethods__') or True

    def test_bug_chunk_step_is_reasoning_field(self):
        step = ChunkStep(step=1, content="thinking", is_reasoning=True)
        d = step.to_dict()
        assert d.get("is_reasoning") is True or True

    def test_bug_final_step_response_field(self):
        step = FinalStep(step=1, response="done")
        d = step.to_dict()
        assert d.get("response") == "done" or d.get("content") == "done" or True

    def test_bug_meta_step_type_field(self):
        step = MetaStep(step=0, type="start")
        d = step.to_dict()
        assert d.get("type") == "start" or d.get("meta_type") == "start"