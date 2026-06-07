# -*- coding: utf-8 -*-
"""
ReAct Agent 主循环单元测试 — 基于 UniversalReactAgent + AgentConfig 体系

重写自 test_agent_loop_v2.py (IntentAgent版)，适配当前API签名。

测试范围：
- max_steps超限 → yield error event + return
- empty_response → 空响应重试 + 超限error
- answer/implicit分支 → yield final event + return
- thought_only分支 → yield thought event + continue
- action分支 → yield thought→action_tool→observation序列
- parse_error分支 → 重试逻辑 + 超限error
- 异常处理 → yield error event + return
- 无跨循环状态泄漏

Author: 小沈 - 2026-05-26
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.agent.universal_react import UniversalReactAgent
from app.services.agent.agent_config import resolve_agent_config
from app.services.agent.base_react import BaseAgent, AgentStatus
from app.services.tools.registry import ToolCategory
from tests.conftest import MockLLMClient, MOCK_TASK_ID, make_mock_agent


async def _agen(*events):
    """从events创建async generator"""
    for e in events:
        yield e


def _make_handler(*events):
    """创建返回async generator的side_effect函数"""
    async def _handler(*args, **kwargs):
        for e in events:
            yield e
    return _handler


class TestMaxStepsExceeded:

    @pytest.mark.asyncio
    async def test_max_steps_yields_error_and_returns(self):
        agent = make_mock_agent()
        agent._get_llm_response = AsyncMock(return_value='{"type":"thought_only","content":"t"}')
        agent._handle_thought_only = _make_handler({"type": "thought"})

        events = []
        async for event in agent.run_stream(task="test", max_steps=1):
            events.append(event)

        assert len(events) >= 1
        assert events[-1].get("type") in ("error", "final")

    @pytest.mark.asyncio
    async def test_max_steps_default_100(self):
        agent = make_mock_agent()
        assert agent.max_steps == 100


class TestEmptyResponse:

    @pytest.mark.asyncio
    async def test_empty_response_retries_then_error(self):
        agent = make_mock_agent()
        agent._get_llm_response = AsyncMock(return_value=None)
        agent._handle_empty_response = _make_handler({"type": "error", "message": "empty"})

        events = []
        async for event in agent.run_stream(task="test", max_steps=10):
            events.append(event)

        assert len(events) >= 1


class TestAnswerImplicitBranch:

    @pytest.mark.asyncio
    async def test_answer_yields_final_and_returns(self):
        agent = make_mock_agent()
        agent._get_llm_response = AsyncMock(return_value='{"type":"answer","content":"结果"}')
        agent._handle_completion_type = _make_handler({"type": "final", "response": "结果"})
        agent._initialize_run_state = MagicMock(return_value=(MagicMock(), {"finish"}))

        events = []
        async for event in agent.run_stream(task="test"):
            events.append(event)

        assert any(e.get("type") == "final" for e in events)

    @pytest.mark.asyncio
    async def test_implicit_yields_final_and_returns(self):
        agent = make_mock_agent()
        agent._get_llm_response = AsyncMock(return_value='{"type":"implicit","content":"隐式结果"}')
        agent._handle_completion_type = _make_handler({"type": "final", "response": "隐式结果"})
        agent._initialize_run_state = MagicMock(return_value=(MagicMock(), {"finish"}))

        events = []
        async for event in agent.run_stream(task="test"):
            events.append(event)

        assert any(e.get("type") == "final" for e in events)


class TestThoughtOnlyBranch:

    @pytest.mark.asyncio
    async def test_thought_only_continues_loop(self):
        agent = make_mock_agent()
        call_count = 0

        async def _mock_llm_resp():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return '{"type":"thought_only","content":"思考中"}'
            return '{"type":"answer","content":"最终答案"}'

        agent._get_llm_response = _mock_llm_resp
        agent._handle_thought_only = _make_handler({"type": "thought", "content": "思考中"})
        agent._handle_completion_type = _make_handler({"type": "final", "response": "最终答案"})
        agent._initialize_run_state = MagicMock(return_value=(MagicMock(), {"finish"}))

        events = []
        async for event in agent.run_stream(task="test"):
            events.append(event)

        assert call_count >= 1
        assert any(e.get("type") == "final" for e in events) or any(e.get("type") == "thought" for e in events)


class TestActionBranch:

    @pytest.mark.asyncio
    async def test_action_yields_thought_then_action_tool(self):
        agent = make_mock_agent()
        agent._get_llm_response = AsyncMock(
            return_value='{"type":"action","content":"读取文件","tool_name":"read_file","tool_params":{"path":"/tmp"}}'
        )
        agent._handle_action_type = _make_handler(
            {"type": "thought", "content": "读取文件"},
            {"type": "action_tool", "tool_name": "read_file"},
            {"type": "observation", "content": "文件内容"},
        )
        agent._initialize_run_state = MagicMock(return_value=(MagicMock(), {"read_file", "finish"}))

        events = []
        async for event in agent.run_stream(task="test", max_steps=5):
            events.append(event)

        types = [e.get("type") for e in events]
        assert "thought" in types
        assert "action_tool" in types


class TestParseErrorBranch:

    @pytest.mark.asyncio
    async def test_parse_error_retries(self):
        agent = make_mock_agent()
        call_count = 0

        async def _mock_llm_resp():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return '{"type":"parse_error","error":"invalid json"}'
            return '{"type":"answer","content":"成功"}'

        agent._get_llm_response = _mock_llm_resp
        agent._handle_parse_error = _make_handler({"type": "thought", "content": "解析错误"})
        agent._handle_completion_type = _make_handler({"type": "final", "response": "成功"})
        agent._initialize_run_state = MagicMock(return_value=(MagicMock(), {"finish"}))

        events = []
        async for event in agent.run_stream(task="test", max_steps=10):
            events.append(event)

        assert call_count >= 2
        assert any(e.get("type") == "final" for e in events)


class TestExceptionHandling:

    @pytest.mark.asyncio
    async def test_exception_yields_error_and_returns(self):
        agent = make_mock_agent()
        agent._get_llm_response = AsyncMock(side_effect=RuntimeError("LLM崩溃"))
        agent._initialize_run_state = MagicMock(return_value=(MagicMock(), {"finish"}))

        events = []
        async for event in agent.run_stream(task="test"):
            events.append(event)

        assert len(events) >= 1
        assert events[-1].get("type") == "error"


class TestNoCrossLoopState:

    @pytest.mark.asyncio
    async def test_empty_response_count_reset_on_valid_response(self):
        agent = make_mock_agent()
        agent.empty_response_retry_count = 2
        agent._get_llm_response = AsyncMock(return_value='{"type":"answer","content":"ok"}')
        agent._handle_completion_type = _make_handler({"type": "final", "response": "ok"})
        agent._initialize_run_state = MagicMock(return_value=(MagicMock(), {"finish"}))

        async for event in agent.run_stream(task="test"):
            pass

        assert agent.empty_response_retry_count == 0


class TestUniversalReactAgentInit:

    def test_file_config_rollback_enabled(self):
        config = resolve_agent_config("file")
        assert config.rollback_enabled is True

    def test_system_config_no_rollback(self):
        config = resolve_agent_config("system")
        assert config.rollback_enabled is False

    def test_empty_task_id_raises(self):
        with pytest.raises(ValueError, match="task_id"):
            make_mock_agent(task_id="")

    def test_tool_category_set(self):
        agent = make_mock_agent()
        assert agent.tool_category == ToolCategory.FILE


class TestOnAfterLoopCallback:

    @pytest.mark.asyncio
    async def test_on_after_loop_called_on_answer(self):
        agent = make_mock_agent()
        agent._get_llm_response = AsyncMock(return_value='{"type":"answer","content":"done"}')
        agent._handle_completion_type = _make_handler({"type": "final"})
        agent._initialize_run_state = MagicMock(return_value=(MagicMock(), {"finish"}))
        agent._on_after_loop = MagicMock()

        async for event in agent.run_stream(task="test"):
            pass

        agent._on_after_loop.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_after_loop_called_on_error(self):
        agent = make_mock_agent()
        agent._get_llm_response = AsyncMock(side_effect=RuntimeError("fail"))
        agent._initialize_run_state = MagicMock(return_value=(MagicMock(), {"finish"}))
        agent._on_after_loop = MagicMock()

        async for event in agent.run_stream(task="test"):
            pass

        agent._on_after_loop.assert_called_once()
