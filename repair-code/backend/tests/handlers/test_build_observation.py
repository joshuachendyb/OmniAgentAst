# -*- coding: utf-8 -*-
"""build_observation 绔埌绔试请?鈥?小欧 2026-06-22

测试build_observation完整娴佺▼,宮ock agent + step_emitter銆?瑕嗙洊鍗曞伐鍏枫查佸苟行屻查佸紓常搞查佽竟缂樻儏内点查?"""

import pytest
from unittest.mock import MagicMock
from typing import Any, Dict, List

pytestmark = pytest.mark.asyncio

from app.services.agent.handlers.action_handler import (
    ObservationContext, build_observation,
)
from app.services.agent.steps import ActionStep, ObservationStep


@pytest.fixture
def mock_agent():
    agent = MagicMock()
    agent._step_emitter = MagicMock()
    agent._step_emitter.emit = MagicMock(side_effect=lambda x: x)
    agent.message_builder = MagicMock()
    agent.llm_call_count = 1
    agent.task_id = "test-task-id"
    return agent


def make_result(data: Any = None, llm_data: Dict = None, other_data: Dict = None) -> Dict:
    return {"data": data, "llm_data": llm_data or {}, "other_data": other_data or {}}


def make_llm_data(exec_code: str = "success", summary: str = "ok",
                  tool: str = "test_tool", duration_ms: int = 10) -> Dict:
    return {
        "summary": summary,
        "action": {"tool": tool, "tool_zh": "测试", "target": "x", "params": {}},
        "status": {"exec_code": exec_code, "message": "", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {},
    }


class TestBuildObservation:

    async def _run(self, ctx: ObservationContext) -> List:
        return await build_observation(ctx)

    # ============================================================
    # 鍩写湰路径
    # ============================================================

    async def test_single_success(self, mock_agent):
        result = make_result(data="file content", llm_data=make_llm_data("success", "读取户愬姛"))
        ctx = ObservationContext(
            agent=mock_agent,
            all_calls=[{"tool_name": "read_file", "tool_params": {"path": "/a.txt"}}],
            results=[result],
            step=1,
            tool_name="read_file", tool_params={"path": "/a.txt"},
            is_parallel=False, pending_calls=[],
        )
        events = await self._run(ctx)

        assert len(events) == 2
        assert isinstance(events[0], ActionStep)
        assert events[0]._tool_name == "read_file"
        assert events[0]._step == 1
        assert events[0]._execution_status == "success"

        assert isinstance(events[1], ObservationStep)
        assert events[1]._step == 1
        assert len(events[1]._llm_data) == 1
        assert events[1]._llm_data[0]["summary"] == "读取户愬姛"
        assert events[1]._other_data == {}

    async def test_single_error(self, mock_agent):
        result = make_result(data=None, llm_data=make_llm_data("error", "读取失败"))
        ctx = ObservationContext(
            agent=mock_agent,
            all_calls=[{"tool_name": "read_file", "tool_params": {"path": "/a.txt"}}],
            results=[result],
            step=2,
            tool_name="read_file", tool_params={"path": "/a.txt"},
            is_parallel=False, pending_calls=[],
        )
        events = await self._run(ctx)
        assert events[0]._execution_status == "error"
        assert len(events[1]._llm_data) == 1
        assert events[1]._llm_data[0]["status"]["exec_code"] == "error"

    async def test_exception_result(self, mock_agent):
        exc = ValueError("纾佺洏错误")
        ctx = ObservationContext(
            agent=mock_agent,
            all_calls=[{"tool_name": "read_file", "tool_params": {"path": "/bad.txt"}}],
            results=[exc],
            step=1,
            tool_name="read_file", tool_params={"path": "/bad.txt"},
            is_parallel=False, pending_calls=[],
        )
        events = await self._run(ctx)
        assert events[0]._execution_status == "error"
        assert isinstance(events[0], ActionStep)
        assert isinstance(events[1], ObservationStep)
        assert events[1]._llm_data == []

    # ============================================================
    # 并行路径
    # ============================================================

    async def test_parallel_two_success(self, mock_agent):
        results = [
            make_result(data=1, llm_data=make_llm_data("success", "A", "tool_a", 10),
                       other_data={"warning": "娉户剰A"}),
            make_result(data=2, llm_data=make_llm_data("success", "B", "tool_b", 20),
                       other_data={"warning": "娉户剰B"}),
        ]
        ctx = ObservationContext(
            agent=mock_agent,
            all_calls=[
                {"tool_name": "tool_a", "tool_params": {"x": 1}},
                {"tool_name": "tool_b", "tool_params": {"y": 2}},
            ],
            results=results,
            step=3,
            tool_name="tool_a", tool_params={"x": 1},
            is_parallel=True, pending_calls=[],
        )
        events = await self._run(ctx)

        assert len(events) == 3
        assert isinstance(events[0], ActionStep)
        assert events[0]._tool_name == "tool_a"
        assert isinstance(events[1], ActionStep)
        assert events[1]._tool_name == "tool_b"

        obs = events[2]
        assert isinstance(obs, ObservationStep)
        assert len(obs._llm_data) == 2
        assert obs._llm_data[0]["summary"] == "A"
        assert obs._llm_data[1]["summary"] == "B"
        assert "娉户剰A" in obs._other_data.get("warning", "")
        assert "娉户剰B" in obs._other_data.get("warning", "")
        assert isinstance(obs._tool_result, list)
        assert len(obs._tool_result) == 2
        assert obs._parallel_results is not None
        assert obs._parallel_results[0]["llm_data"]["summary"] == "A"

    async def test_parallel_mixed_success_error(self, mock_agent):
        results = [
            make_result(data="ok", llm_data=make_llm_data("success", "户愬姛", "tool_a")),
            make_result(data="err", llm_data=make_llm_data("error", "失败", "tool_b")),
        ]
        ctx = ObservationContext(
            agent=mock_agent,
            all_calls=[
                {"tool_name": "tool_a", "tool_params": {}},
                {"tool_name": "tool_b", "tool_params": {}},
            ],
            results=results,
            step=1,
            tool_name="tool_a", tool_params={},
            is_parallel=True, pending_calls=[],
        )
        events = await self._run(ctx)
        obs = events[2]
        assert len(obs._llm_data) == 2
        # 各是各的，不merge — 北京老陈 2026-07-08
        assert obs._llm_data[0]["status"]["exec_code"] == "success"
        assert obs._llm_data[1]["status"]["exec_code"] == "error"
        assert obs._llm_data[0]["action"]["tool"] == "tool_a"
        assert obs._llm_data[1]["action"]["tool"] == "tool_b"

    # ============================================================
    # 输照紭鎯容喌
    # ============================================================

    async def test_no_results(self, mock_agent):
        ctx = ObservationContext(
            agent=mock_agent,
            all_calls=[{"tool_name": "read_file", "tool_params": {}}],
            results=[],
            step=1,
            tool_name="read_file", tool_params={},
            is_parallel=False, pending_calls=[],
        )
        events = await self._run(ctx)
        assert len(events) == 1
        assert isinstance(events[0], ObservationStep)
        assert events[0]._llm_data == []

    async def test_result_missing_llm_data(self, mock_agent):
        result = {"data": "x"}
        ctx = ObservationContext(
            agent=mock_agent,
            all_calls=[{"tool_name": "test", "tool_params": {}}],
            results=[result],
            step=1,
            tool_name="test", tool_params={},
            is_parallel=False, pending_calls=[],
        )
        events = await self._run(ctx)
        assert events[0]._execution_status == "error"
        obs = events[1]
        assert obs._llm_data == [{}]
        assert obs._other_data == {}

    async def test_result_with_other_data(self, mock_agent):
        result = make_result(
            data="x",
            llm_data=make_llm_data("success", "ok"),
            other_data={"return_direct": True, "attachment": "file.txt"},
        )
        ctx = ObservationContext(
            agent=mock_agent,
            all_calls=[{"tool_name": "test", "tool_params": {}}],
            results=[result],
            step=1,
            tool_name="test", tool_params={},
            is_parallel=False, pending_calls=[],
        )
        events = await self._run(ctx)
        obs = events[1]
        assert obs._other_data.get("return_direct") is True
        assert obs._other_data.get("attachment") == "file.txt"

    async def test_fc_context_passed(self, mock_agent):
        result = make_result(data="x", llm_data=make_llm_data("success", "ok"))
        fc_ctx = {"tool_call_id": "call_123", "tool_calls": [{"id": "call_123", "function": {"name": "test"}}]}
        ctx = ObservationContext(
            agent=mock_agent,
            all_calls=[{"tool_name": "test", "tool_params": {}, "_tool_call_id": "call_123"}],
            results=[result],
            step=1,
            tool_name="test", tool_params={},
            is_parallel=False, pending_calls=[],
            fc_context=fc_ctx,
        )
        events = await self._run(ctx)
        mock_agent.message_builder.add_assistant_tool_call.assert_called_once()
        call_args = mock_agent.message_builder.add_assistant_tool_call.call_args
        assert call_args[0][0] == [{"id": "call_123", "function": {"name": "test"}}]
        mock_agent.message_builder.add_tool_result.assert_called_once()
        tool_args = mock_agent.message_builder.add_tool_result.call_args
        assert tool_args[0][0] == "call_123"

    async def test_fc_context_empty(self, mock_agent):
        result = make_result(data="x", llm_data=make_llm_data("success", "ok"))
        ctx = ObservationContext(
            agent=mock_agent,
            all_calls=[{"tool_name": "test", "tool_params": {}}],
            results=[result],
            step=1,
            tool_name="test", tool_params={},
            is_parallel=False, pending_calls=[],
            fc_context={},
        )
        events = await self._run(ctx)
        mock_agent.message_builder.add_assistant_tool_call.assert_not_called()
        mock_agent.message_builder.add_tool_result.assert_called_once()

    async def test_message_builder_exception_swallowed(self, mock_agent):
        mock_agent.message_builder.add_tool_result.side_effect = RuntimeError("builder宕╂簝")
        result = make_result(data="x", llm_data=make_llm_data("success", "ok"))
        ctx = ObservationContext(
            agent=mock_agent,
            all_calls=[{"tool_name": "test", "tool_params": {}}],
            results=[result],
            step=1,
            tool_name="test", tool_params={},
            is_parallel=False, pending_calls=[],
        )
        events = await self._run(ctx)
        assert len(events) == 2

    async def test_single_result_tool_result_not_list(self, mock_agent):
        result = make_result(data="single_value", llm_data=make_llm_data("success", "ok"))
        ctx = ObservationContext(
            agent=mock_agent,
            all_calls=[{"tool_name": "test", "tool_params": {}}],
            results=[result],
            step=1,
            tool_name="test", tool_params={},
            is_parallel=False, pending_calls=[],
        )
        events = await self._run(ctx)
        obs = events[1]
        assert obs._tool_result == result["data"]

    async def test_llm_data_none_in_result_not_crash(self, mock_agent):
        result = {"data": "x", "llm_data": None, "other_data": {}}
        ctx = ObservationContext(
            agent=mock_agent,
            all_calls=[{"tool_name": "test", "tool_params": {}}],
            results=[result],
            step=1,
            tool_name="test", tool_params={},
            is_parallel=False, pending_calls=[],
        )
        events = await self._run(ctx)
        obs = events[1]
        assert obs._llm_data is not None
