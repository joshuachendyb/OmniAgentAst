# -*- coding: utf-8 -*-
"""
_should_retry_truncated_tool 鍗曞厓测试
鍖椾含鑰侀檲 2026-06-25
"""

import pytest
from unittest.mock import MagicMock

from app.services.agent.react_cycle import _should_retry_truncated_tool


def _make_agent(history):
    agent = MagicMock()
    agent.message_builder = MagicMock()
    agent.message_builder.conversation_history = history
    return agent


def _make_tc(tc_id="tc_1", name="readtext"):
    return {"id": tc_id, "type": "function", "function": {"name": name, "arguments": "{}"}}


class TestShouldRetryTruncatedTool:
    """test"""

    def test_answer_type_with_short_content_and_pending_tool_call(self):
        history = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "task"},
            {"role": "assistant", "tool_calls": [_make_tc("tc_1")]},
        ]
        agent = _make_agent(history)
        llm_response = {"type": "answer", "content": "short"}
        assert _should_retry_truncated_tool(agent, llm_response) is True

    def test_answer_type_with_tool_result_not_truncated(self):
        history = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "task"},
            {"role": "assistant", "tool_calls": [_make_tc("tc_1")]},
            {"role": "tool", "tool_call_id": "tc_1", "content": "result"},
        ]
        agent = _make_agent(history)
        llm_response = {"type": "answer", "content": "short"}
        assert _should_retry_truncated_tool(agent, llm_response) is False

    def test_action_type_never_truncated(self):
        agent = _make_agent([])
        llm_response = {"type": "action", "content": "short"}
        assert _should_retry_truncated_tool(agent, llm_response) is False

    def test_long_content_not_truncated(self):
        history = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "task"},
            {"role": "assistant", "tool_calls": [_make_tc("tc_1")]},
        ]
        agent = _make_agent(history)
        llm_response = {"type": "answer", "content": "x" * 501}
        assert _should_retry_truncated_tool(agent, llm_response) is False

    def test_empty_content_not_truncated(self):
        history = [
            {"role": "system", "content": "sys"},
            {"role": "assistant", "tool_calls": [_make_tc("tc_1")]},
        ]
        agent = _make_agent(history)
        llm_response = {"type": "answer", "content": ""}
        assert _should_retry_truncated_tool(agent, llm_response) is False

    def test_no_tool_calls_in_history_not_truncated(self):
        history = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "task"},
            {"role": "assistant", "content": "thinking"},
        ]
        agent = _make_agent(history)
        llm_response = {"type": "answer", "content": "short"}
        assert _should_retry_truncated_tool(agent, llm_response) is False

    def test_boundary_500_chars_is_truncated(self):
        history = [
            {"role": "assistant", "tool_calls": [_make_tc("tc_1")]},
        ]
        agent = _make_agent(history)
        llm_response = {"type": "answer", "content": "x" * 500}
        assert _should_retry_truncated_tool(agent, llm_response) is True

    def test_observation_role_also_blocks_retry(self):
        history = [
            {"role": "assistant", "tool_calls": [_make_tc("tc_1")]},
            {"role": "observation", "tool_call_id": "tc_1", "content": "result"},
        ]
        agent = _make_agent(history)
        llm_response = {"type": "answer", "content": "short"}
        assert _should_retry_truncated_tool(agent, llm_response) is False