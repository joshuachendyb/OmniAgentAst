# -*- coding: utf-8 -*-
"""test"""
import pytest
from unittest.mock import MagicMock, patch
from app.services.agent.status_table import AgentStatus


def _make_tc(tc_id="tc_1", name="readtext"):
    return {"id": tc_id, "type": "function", "function": {"name": name, "arguments": "{}"}}


@pytest.mark.asyncio
async def test_process_single_step_history_not_defined():
    """process single step history not defined"""
    from app.services.agent.react_cycle import _process_single_step

    agent = MagicMock()
    agent.llm_call_count = 0
    agent._consecutive_truncations = 0
    agent.status = AgentStatus.EXECUTING
    agent.llm_client = MagicMock()
    agent.llm_client.model = "gpt-4"
    agent.llm_client.provider = "openai"
    agent.llm_client._cancelled = False  # 必须是惧紡璁剧置,请惁列?MagicMock 返回 truthy

    # conversation_history 否湭完我垚的?tool_calls,堣Е名戞埅方娴嬶級
    agent.message_builder = MagicMock()
    agent.message_builder.conversation_history = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "task"},
        {"role": "assistant", "tool_calls": [_make_tc("tc_1")]},
    ]

    # _step_emitter.emit 原熸牱返回
    agent._step_emitter = MagicMock()
    agent._step_emitter.emit = MagicMock(side_effect=lambda x: x)
    agent._step_emitter.exit_with_error = MagicMock()

    def set_failed(msg):
        agent.status = AgentStatus.FAILED

    agent.set_failed = MagicMock(side_effect=set_failed)

    def _create_cancelled_chunk():
        from app.services.agent.steps import ChunkStep
        return ChunkStep(step=agent.llm_call_count, content="")

    agent._create_cancelled_chunk = _create_cancelled_chunk

    chunk_buffer = MagicMock()
    chunk_buffer.append = MagicMock()

    # Mock call_llm_with_fallback 返回鐭?answer,堟埅方娴下Е名戞潯件讹級
    fake_response = ("response", {"type": "answer", "content": "OK"})

    with patch("app.services.agent.react_cycle.call_llm_with_fallback") as mock_cllf:
        async def mock_iter(*args, **kwargs):
            yield fake_response
        mock_cllf.return_value = mock_iter()

        with patch("app.services.agent.react_cycle.get_openai_tools") as mock_got:
            mock_got.return_value = []

            try:
                events = []
                async for event in _process_single_step(agent, chunk_buffer):
                    events.append(event)
                # 如果璧到埌连欓噷,岃是庢病有crash,屼絾名兘娌℃湁解﹀彂户柇路径
                """test"""
                print(f"DEBUG: agent.status={agent.status}")
            except NameError as e:
                pytest.fail(f"BUG: _process_single_step should not throw NameError: {e}")
            except Exception as e:
                # 非為未因紓常革,类撳嵃修℃伅
                print(f"DEBUG: 鍏朵粬异常: {type(e).__name__}: {e}")
