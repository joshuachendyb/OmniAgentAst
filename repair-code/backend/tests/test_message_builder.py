# -*- coding: utf-8 -*-
"""
MessageBuilder 鍗曞厓测试 鈥?trim_history / _classify_messages / _trim_fc_pairs
鍖椾含鑰侀檲 2026-06-25
"""

import pytest
from app.services.agent.message_builder import MessageBuilder


def _make_system(content="system prompt"):
    return {"role": "system", "content": content}


def _make_user(content="user task"):
    return {"role": "user", "content": content}


def _make_assistant(content=None, tool_calls=None):
    msg = {"role": "assistant"}
    if content is not None:
        msg["content"] = content
    if tool_calls is not None:
        msg["tool_calls"] = tool_calls
    return msg


def _make_tool(tool_call_id="tc_1", content="tool result"):
    return {"role": "tool", "tool_call_id": tool_call_id, "content": content}


def _make_tc(tc_id="tc_1", name="readtext", args='{"path":"x"}'):
    return {"id": tc_id, "type": "function", "function": {"name": name, "arguments": args}}


class TestClassifyMessages:
    """_classify_messages 列嗙被测试"""

    def test_empty_history(self):
        mb = MessageBuilder()
        result = mb._classify_messages()
        assert result == ([], [], [], [])

    def test_all_roles(self):
        mb = MessageBuilder()
        mb.conversation_history = [
            _make_system(),
            _make_user(),
            _make_assistant(tool_calls=[_make_tc("tc_1")]),
            _make_tool("tc_1"),
            _make_assistant(content="final answer"),
        ]
        sys_m, user_m, obs_m, asst_m = mb._classify_messages()
        assert len(sys_m) == 1
        assert len(user_m) == 1
        assert len(obs_m) == 1
        assert len(asst_m) == 2

    def test_multiple_observations(self):
        mb = MessageBuilder()
        mb.conversation_history = [
            _make_system(),
            _make_user(),
            _make_assistant(tool_calls=[_make_tc("tc_1"), _make_tc("tc_2")]),
            _make_tool("tc_1"),
            _make_tool("tc_2"),
        ]
        _, _, obs_m, _ = mb._classify_messages()
        assert len(obs_m) == 2


class TestTrimFcPairs:
    """_trim_fc_pairs FC配崩瑁佸壀测试"""

    def test_paired_kept(self):
        messages = [
            _make_system(),
            _make_user(),
            _make_assistant(tool_calls=[_make_tc("tc_1")]),
            _make_tool("tc_1"),
        ]
        result = MessageBuilder._trim_fc_pairs(messages)
        assert len(result) == 4

    def test_orphan_tool_removed(self):
        messages = [
            _make_system(),
            _make_user(),
            _make_tool("tc_orphan"),
        ]
        result = MessageBuilder._trim_fc_pairs(messages)
        assert len(result) == 2
        assert all(m.get("role") != "tool" for m in result)

    def test_orphan_assistant_tool_calls_removed(self):
        messages = [
            _make_system(),
            _make_user(),
            _make_assistant(tool_calls=[_make_tc("tc_orphan")]),
        ]
        result = MessageBuilder._trim_fc_pairs(messages)
        assert len(result) == 2

    def test_partial_pair_keeps_matched(self):
        tc1 = _make_tc("tc_1")
        tc2 = _make_tc("tc_2")
        messages = [
            _make_system(),
            _make_user(),
            _make_assistant(tool_calls=[tc1, tc2]),
            _make_tool("tc_1"),
        ]
        result = MessageBuilder._trim_fc_pairs(messages)
        assistant_msgs = [m for m in result if m.get("role") == "assistant"]
        tool_msgs = [m for m in result if m.get("role") == "tool"]
        assert len(tool_msgs) == 1
        assert len(assistant_msgs) == 1
        assert len(assistant_msgs[0].get("tool_calls", [])) == 1
        assert assistant_msgs[0]["tool_calls"][0]["id"] == "tc_1"

    def test_no_tool_calls_passes_through(self):
        messages = [
            _make_system(),
            _make_user(),
            _make_assistant(content="hello"),
        ]
        result = MessageBuilder._trim_fc_pairs(messages)
        assert len(result) == 3


class TestTrimHistory:
    """trim_history 完整瑁佸壀娴佺▼测试"""

    def test_no_trim_when_under_budget(self):
        mb = MessageBuilder(max_context_tokens=200000)
        mb.conversation_history = [
            _make_system(),
            _make_user(),
            _make_assistant(content="short answer"),
        ]
        original = list(mb.conversation_history)
        mb.trim_history()
        assert mb.conversation_history == original

    def test_trim_triggers_at_80_percent(self):
        mb = MessageBuilder(max_context_tokens=1000)
        big_content = "x" * 900
        mb.conversation_history = [
            _make_system("sys"),
            _make_user("usr"),
            _make_assistant(tool_calls=[_make_tc("tc_1")]),
            _make_tool("tc_1", big_content),
            _make_assistant(tool_calls=[_make_tc("tc_2")]),
            _make_tool("tc_2", big_content),
            _make_assistant(content="done"),
        ]
        mb.trim_history()
        assert len(mb.conversation_history) >= 2
        assert mb.conversation_history[0]["role"] == "system"
        assert mb.conversation_history[1]["role"] == "user"

    def test_trim_preserves_system_and_user(self):
        mb = MessageBuilder(max_context_tokens=500)
        mb.conversation_history = [
            _make_system("system prompt"),
            _make_user("user task"),
            _make_assistant(tool_calls=[_make_tc("tc_1")]),
            _make_tool("tc_1", "x" * 400),
            _make_assistant(content="final"),
        ]
        mb.trim_history()
        assert mb.conversation_history[0]["role"] == "system"
        assert mb.conversation_history[1]["role"] == "user"

    def test_trim_keeps_recent_over_old(self):
        mb = MessageBuilder(max_context_tokens=800)
        mb.conversation_history = [
            _make_system("sys"),
            _make_user("usr"),
            _make_assistant(tool_calls=[_make_tc("tc_old")]),
            _make_tool("tc_old", "old " * 100),
            _make_assistant(tool_calls=[_make_tc("tc_new")]),
            _make_tool("tc_new", "new " * 10),
        ]
        mb.trim_history()
        tool_ids = [m.get("tool_call_id") for m in mb.conversation_history if m.get("role") == "tool"]
        if tool_ids:
            assert "tc_new" in tool_ids

    def test_no_trim_when_only_two_messages(self):
        mb = MessageBuilder(max_context_tokens=100)
        mb.conversation_history = [
            _make_system("x" * 200),
            _make_user("y" * 200),
        ]
        mb.trim_history()
        assert len(mb.conversation_history) == 2


class TestTotalChars:
    """_total_chars 存楃璁＄畻测试"""

    def test_content_only(self):
        msgs = [{"role": "user", "content": "hello"}]
        assert MessageBuilder._total_chars(msgs) == 5

    def test_none_content(self):
        msgs = [{"role": "assistant", "content": None, "tool_calls": []}]
        assert MessageBuilder._total_chars(msgs) == 0

    def test_tool_calls_counted(self):
        tc = _make_tc("tc_1", "readtext", '{"path":"/a"}')
        msgs = [{"role": "assistant", "content": None, "tool_calls": [tc]}]
        total = MessageBuilder._total_chars(msgs)
        assert total > 0

    def test_empty_list(self):
        assert MessageBuilder._total_chars([]) == 0


class TestNormalizeObservationPrefix:
    """empty list"""

    def test_already_prefixed(self):
        result = MessageBuilder._normalize_observation_prefix("[Observation] done")
        assert result == "[Observation] done"

    def test_add_prefix(self):
        result = MessageBuilder._normalize_observation_prefix("file content here")
        assert result == "[Observation] file content here"

    def test_strip_observation_colon(self):
        result = MessageBuilder._normalize_observation_prefix("Observation: some text")
        assert result == "[Observation] some text"

    def test_no_double_prefix(self):
        result = MessageBuilder._normalize_observation_prefix("Observation: [Observation] text")
        assert result == "[Observation] text"