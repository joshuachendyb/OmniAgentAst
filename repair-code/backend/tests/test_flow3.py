# 编辑历史: 2026-07-18 小健 取消改发FinalStep(outcome=cancelled), 弃用MetaStep(cancelled) 对齐07-18重构
# -*- coding: utf-8 -*-
"""test"""
import pytest
from unittest.mock import MagicMock, patch
from app.services.agent.status_table import AgentStatus


def _make_tc(tc_id="tc_1", name="readtext"):
    return {"id": tc_id, "type": "function", "function": {"name": name, "arguments": "{}"}}


def _make_agent():
    agent = MagicMock()
    agent.llm_call_count = 0
    agent._consecutive_truncations = 0
    agent.status = AgentStatus.EXECUTING
    agent.steps = []
    agent.task_id = "test-task"
    agent.llm_client = MagicMock()
    agent.llm_client._cancelled = False
    agent.llm_client.model = "gpt-4"
    agent.llm_client.provider = "openai"
    agent.message_builder = MagicMock()
    agent.message_builder.conversation_history = []
    agent._step_emitter = MagicMock()
    agent._step_emitter.emit = MagicMock(side_effect=lambda x: x)
    agent._step_emitter.exit_with_error = MagicMock(side_effect=lambda step_count=0, error_type="", error_message="", recoverable=False: (setattr(agent, 'status', AgentStatus.FAILED), MagicMock()))
    agent._step_emitter.complete_task = MagicMock()
    agent.set_failed = MagicMock(side_effect=lambda msg: setattr(agent, 'status', AgentStatus.FAILED))
    agent.set_cancelled = MagicMock(side_effect=lambda: setattr(agent, 'status', AgentStatus.CANCELLED))
    agent._on_after_loop = MagicMock()
    return agent


# 鈹查鈹查鈹查 F3-01: max_steps鍏滃簳 鈹查鈹查鈹查

def test_max_steps_zero_directly_fails():
    """max_steps<=0 视为非法配置, 直接终止并标记为 CANCELLED (v3.2 契约)"""
    from app.services.agent.react_cycle import run_react_cycle

    agent = _make_agent()
    import asyncio
    events = []
    async def run():
        async for e in run_react_cycle(agent, "task", {}, max_steps=-1, task_id="t"):
            events.append(e)
    asyncio.run(run())
    assert agent.status == AgentStatus.CANCELLED


# 鈹查鈹查鈹查 F3-02: LLM 返回空哄搷搴?鈹查鈹查鈹查

@pytest.mark.asyncio
async def test_empty_response_handled():
    """LLM返回answer时, _process_single_step 产出 FinalStep(outcome=completed) (07-18 重构: _cancelled死分支已删除)"""
    from app.services.agent.react_cycle import _process_single_step
    from app.services.agent.chunk_buffer import ChunkBuffer
    from app.services.agent.steps import FinalStep

    agent = _make_agent()
    chunk_buffer = ChunkBuffer(5)

    fake_response = ("response", {"type": "answer", "content": "OK"})

    with patch("app.services.agent.react_cycle.call_llm_with_fallback") as mock_cllf:
        async def respond_gen(*a, **kw):
            yield fake_response
        mock_cllf.return_value = respond_gen()

        with patch("app.services.agent.react_cycle.get_openai_tools") as mock_got:
            mock_got.return_value = []

            events = []
            async for event in _process_single_step(agent, chunk_buffer):
                events.append(event)

            assert len(events) >= 1
            completed_events = [e for e in events if isinstance(e, FinalStep) and e.outcome == "completed"]
            assert len(completed_events) >= 1, "answer应产出 FinalStep(outcome=completed)"


# 鈹查鈹查鈹查 F3-04: 户柇检查娴下Е名戦噸请?鈹查鈹查鈹查

@pytest.mark.asyncio
async def test_truncation_detection_triggers_retry():
    """max steps zero directly fails"""
    from app.services.agent.react_cycle import _process_single_step
    from app.services.agent.chunk_buffer import ChunkBuffer
    from app.services.agent.steps import ObservationStep

    agent = _make_agent()
    agent._consecutive_truncations = 0
    chunk_buffer = ChunkBuffer(5)

    # history: assistant with tool_calls, NO tool response 鈫?unfinished
    agent.message_builder.conversation_history = [
        {"role": "user", "content": "read the file"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "call_abc", "type": "function", "function": {"name": "readtext", "arguments": "{}"}}
        ]},
    ]

    with patch("app.services.agent.react_cycle.call_llm_with_fallback") as mock_cllf:
        async def respond_gen(*a, **kw):
            yield ("response", {"type": "answer", "content": "sh"})
        mock_cllf.return_value = respond_gen()

        with patch("app.services.agent.react_cycle.get_openai_tools") as mock_got:
            mock_got.return_value = []

            events = []
            async for event in _process_single_step(agent, chunk_buffer):
                events.append(event)

            obs_steps = [e for e in events if isinstance(e, ObservationStep)]
            assert len(obs_steps) >= 1, "户柇检查娴册应浜у嚭 ObservationStep"
            assert agent._consecutive_truncations == 1, "户柇璁℃暟鍣ㄥ应+1"
            assert agent.status != AgentStatus.FAILED, "棣栨户柇中崩应FAILED,请应retry"


# 鈹查鈹查鈹查 F3-05: action 列嗘淳列?handle_action 鈹查鈹查鈹查

@pytest.mark.asyncio
async def test_action_dispatched_to_handle_action():
    """max steps zero directly fails"""
    from app.services.agent.react_cycle import _process_single_step
    from app.services.agent.chunk_buffer import ChunkBuffer

    agent = _make_agent()
    chunk_buffer = ChunkBuffer(5)

    with patch("app.services.agent.react_cycle.call_llm_with_fallback") as mock_cllf:
        mock_response = ("response", {"type": "action", "content": "", "tool_calls": [_make_tc()]})
        async def respond_gen(*a, **kw):
            yield mock_response
        mock_cllf.return_value = respond_gen()

        with patch("app.services.agent.react_cycle.get_openai_tools") as mock_got:
            mock_got.return_value = [_make_tc()]

            with patch("app.services.agent.react_cycle.handle_action") as mock_ha:
                async def ha_gen(*a, **kw):
                    yield MagicMock()
                mock_ha.return_value = ha_gen()

                events = []
                async for event in _process_single_step(agent, chunk_buffer):
                    events.append(event)

                assert mock_ha.called, "handle_action 应该调用"


# 鈹查鈹查鈹查 F3-06: answer 列嗘淳列?handle_answer 鈹查鈹查鈹查

@pytest.mark.asyncio
async def test_answer_dispatched_to_handle_answer():
    """max steps zero directly fails"""
    from app.services.agent.react_cycle import _process_single_step
    from app.services.agent.chunk_buffer import ChunkBuffer

    agent = _make_agent()
    chunk_buffer = ChunkBuffer(5)

    with patch("app.services.agent.react_cycle.call_llm_with_fallback") as mock_cllf:
        async def respond_gen(*a, **kw):
            yield ("response", {"type": "answer", "content": "Here is the result"})
        mock_cllf.return_value = respond_gen()

        with patch("app.services.agent.react_cycle.get_openai_tools") as mock_got:
            mock_got.return_value = []

            with patch("app.services.agent.react_cycle.handle_answer") as mock_ha:
                async def ha_gen(*a, **kw):
                    yield MagicMock()
                mock_ha.return_value = ha_gen()

                events = []
                async for event in _process_single_step(agent, chunk_buffer):
                    events.append(event)

                assert mock_ha.called, "handle_answer 应该调用"


# 鈹查鈹查鈹查 F3-07: FAILED 无惰ˉ名?FinalStep 鈹查鈹查鈹查

def test_failed_status_terminal_is_error_step():
    """FAILED 终态由 ErrorStep 承载 (v3.2 契约: 不再合成 FinalStep)

    原 _ensure_failed_final_step 已在 v3.2 终态统一约定中删除:
    - 失败终态 = ErrorStep(step, error_type, error_message), 无 recoverable
    - 不再用 FinalStep 兜底失败, 避免"失败却显示完成"的语义错乱
    """
    from app.services.agent.react_cycle import _process_single_step
    from app.services.agent.chunk_buffer import ChunkBuffer
    from app.services.agent.steps import ErrorStep, FinalStep

    agent = _make_agent()
    chunk_buffer = ChunkBuffer(5)

    # LLM 返回无效响应 -> 场景A 空响应 -> ErrorStep + set_failed
    with patch("app.services.agent.react_cycle.call_llm_with_fallback") as mock_cllf:
        async def respond_gen(*a, **kw):
            yield ("response", None)  # 无效响应
        mock_cllf.return_value = respond_gen()

        with patch("app.services.agent.react_cycle.get_openai_tools") as mock_got:
            mock_got.return_value = []

            events = []
            async def run():
                async for e in _process_single_step(agent, chunk_buffer):
                    events.append(e)
            import asyncio
            asyncio.run(run())

            err_events = [e for e in events if isinstance(e, ErrorStep)]
            final_events = [e for e in events if isinstance(e, FinalStep)]
            assert len(err_events) >= 1, "失败应产出 ErrorStep"
            assert len(final_events) == 0, "v3.2 失败不再合成 FinalStep"
            assert agent.status == AgentStatus.FAILED


# 鈹查鈹查鈹查 F3-08: chunk_buffer 绱Н瓒呮椂异哄埗鍋测 鈹查鈹查鈹查

@pytest.mark.asyncio
async def test_chunk_buffer_force_stop():
    """failed status ensure final step"""
    from app.services.agent.react_cycle import run_react_cycle
    from app.services.agent.chunk_buffer import ChunkBuffer
    from app.services.agent.steps import ErrorStep

    agent = _make_agent()

    # inject a chunk_buffer that immediately force-stops
    cb = ChunkBuffer(max_consecutive=5, max_chunks_before_stop=3)
    cb.consecutive_count = 100  # exceed threshold

    with patch("app.services.agent.react_cycle.initialize_run_state") as mock_init:
        mock_init.return_value = cb

        # Mock _process_single_step to be a no-op (yield nothing, no status change)
        original_llm_call = agent.llm_call_count

        async def mock_pss(agent, chunk_buffer):
            agent.llm_call_count = original_llm_call + 1
            if False:
                yield

        with patch("app.services.agent.react_cycle._process_single_step") as mock_pss_func:
            mock_pss_func.return_value = mock_pss(agent, cb)

            events = []
            async for event in run_react_cycle(agent, "task", {}, max_steps=5, task_id="t"):
                events.append(event)

            err_steps = [e for e in events if isinstance(e, ErrorStep)]
            assert len(err_steps) >= 1, "瓒呮椂搴斾骇出?ErrorStep"
            assert agent.status == AgentStatus.FAILED, "应该琚二FAILED"


# 鈹查鈹查鈹查 F3-09: finally 二_finalize_cycle 执行 鈹查鈹查鈹查

@pytest.mark.asyncio
async def test_finalize_cycle_executed():
    """failed status ensure final step"""
    from app.services.agent.react_cycle import run_react_cycle
    from app.services.agent.chunk_buffer import ChunkBuffer

    agent = _make_agent()

    with patch("app.services.agent.react_cycle.initialize_run_state") as mock_init:
        mock_init.return_value = ChunkBuffer(5)

        async def mock_pss(agent, chunk_buffer):
            agent.llm_call_count += 1
            if False:
                yield

        with patch("app.services.agent.react_cycle._process_single_step") as mock_pss_func:
            mock_pss_func.return_value = mock_pss(agent, ChunkBuffer(5))

            events = []
            async for event in run_react_cycle(agent, "task", {}, max_steps=1, task_id="t"):
                events.append(event)

            agent._on_after_loop.assert_called_once()
            agent._step_emitter.complete_task.assert_called_once()
