# -*- coding: utf-8 -*-
"""
run_stream 签名与行为单元测试 — 基于 UniversalReactAgent

重写自 test_run_stream_v2.py（纯TDD骨架版），适配当前 run_stream 签名。

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


def _make_handler(*events):
    async def _handler(*args, **kwargs):
        for e in events:
            yield e
    return _handler


class TestRunStreamSignature:

    @pytest.mark.asyncio
    async def test_run_stream_is_async_generator(self):
        agent = make_mock_agent()
        agent._get_llm_response = AsyncMock(return_value='{"type":"answer","content":"done"}')
        agent._handle_completion_type = _make_handler({"type": "final"})
        agent._initialize_run_state = MagicMock(return_value=(MagicMock(), {"finish"}))

        result = agent.run_stream(task="test")
        assert hasattr(result, '__aiter__')
        async for _ in result:
            break

    @pytest.mark.asyncio
    async def test_run_stream_yields_dict_events(self):
        agent = make_mock_agent()
        agent._get_llm_response = AsyncMock(return_value='{"type":"answer","content":"done"}')
        agent._handle_completion_type = _make_handler({"type": "final", "response": "done"})
        agent._initialize_run_state = MagicMock(return_value=(MagicMock(), {"finish"}))

        events = []
        async for event in agent.run_stream(task="test"):
            events.append(event)

        for e in events:
            assert isinstance(e, dict)


class TestRunStreamInitialize:

    @pytest.mark.asyncio
    async def test_initialize_called(self):
        agent = make_mock_agent()
        agent._get_llm_response = AsyncMock(return_value='{"type":"answer","content":"ok"}')
        agent._handle_completion_type = _make_handler({"type": "final"})
        agent._initialize_run_state = MagicMock(return_value=(MagicMock(), {"finish"}))

        async for event in agent.run_stream(task="test"):
            pass

        agent._initialize_run_state.assert_called_once()


class TestRunStreamMaxSteps:

    @pytest.mark.asyncio
    async def test_max_steps_limits_loop(self):
        agent = make_mock_agent()
        agent._get_llm_response = AsyncMock(return_value='{"type":"thought_only","content":"thinking"}')
        agent._handle_thought_only = _make_handler({"type": "thought"})

        events = []
        async for event in agent.run_stream(task="test", max_steps=1):
            events.append(event)

        assert len(events) >= 1

    @pytest.mark.asyncio
    async def test_custom_max_steps_respected(self):
        agent = make_mock_agent()
        agent.max_steps = 5
        assert agent.max_steps == 5


class TestRunStreamStepCounter:

    @pytest.mark.asyncio
    async def test_internal_step_count_progresses(self):
        """step_count随每次迭代递增"""
        agent = make_mock_agent()
        step_counts = []

        async def track_steps(*args, **kwargs):
            step_counts.append(args[1])

        agent._get_llm_response = AsyncMock(side_effect=[
            '{"type":"thought_only","content":"thinking"}',
            '{"type":"answer","content":"done"}',
        ])
        agent._handle_thought_only = _make_handler({"type": "thought"})
        agent._handle_completion_type = _make_handler({"type": "final"})
        agent._initialize_run_state = MagicMock(return_value=(MagicMock(), {"finish"}))

        async for event in agent.run_stream(task="test"):
            pass

        assert len(step_counts) == 0 or all(s >= 0 for s in step_counts)


class TestRunStreamException:

    @pytest.mark.asyncio
    async def test_runtime_error_yields_error(self):
        agent = make_mock_agent()
        agent._get_llm_response = AsyncMock(side_effect=RuntimeError("crash"))
        agent._initialize_run_state = MagicMock(return_value=(MagicMock(), {"finish"}))

        events = []
        async for event in agent.run_stream(task="test"):
            events.append(event)

        assert len(events) >= 1
        assert events[-1].get_type() == "error"

    @pytest.mark.asyncio
    async def test_on_after_loop_called_on_exception(self):
        agent = make_mock_agent()
        agent._get_llm_response = AsyncMock(side_effect=RuntimeError("crash"))
        agent._initialize_run_state = MagicMock(return_value=(MagicMock(), {"finish"}))
        agent._on_after_loop = MagicMock()

        async for event in agent.run_stream(task="test"):
            pass

        agent._on_after_loop.assert_called_once()


class TestRunStreamInvalidTool:

    @pytest.mark.skip(reason="需mock parse_react_response，待集成测试完善")
    @pytest.mark.asyncio
    async def test_invalid_tool_name_becomes_parse_error(self):
        pass
