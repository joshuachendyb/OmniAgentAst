# -*- coding: utf-8 -*-
"""test"""
import pytest
from app.services.agent.message_builder import MessageBuilder


def test_trim_to_budget_does_not_duplicate_paired_assistant():
    """trim to budget does not duplicate paired assistant"""
    builder = MessageBuilder()

    # 果勯查犵畝鍗昲istory: system + user + assistant(未塼ool_calls) + tool
    builder.conversation_history = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Use tool readtext"},
        {"role": "assistant", "content": None, "tool_calls": [{"id": "call_1", "type": "function", "function": {"name": "readtext", "arguments": "{}"}}]},
        {"role": "tool", "content": "file content", "tool_call_id": "call_1"},
    ]

    # 类册伐调用 _trim_to_budget 验证配崩行为
    system_msgs, user_msgs, obs_list, assistant_msgs = builder._classify_messages()

    # 验证列嗙被正认
    assert len(assistant_msgs) == 1  # 中查中猘ssistant
    assert len(obs_list) == 1       # 中查中猼ool

    # 璁惧緢复х个budget璁╁叏閮ㄩ查过繃
    trimmed = builder._trim_to_budget(obs_list, assistant_msgs, budget_tokens=999999)

    # 验证: 配崩否庝不搴旀湁里崩消息
    # trimmed 搴斿惈 [assistant_with_toolcalls, tool_msg] (顺序正认)
    assert len(trimmed) == 2, f"配崩搴斾骇出?误℃秷息? 完复緱{len(trimmed)}: {trimmed}"

    roles = [m.get("role") for m in trimmed]
    assert roles == ["assistant", "tool"], f"顺序搴斾为[assistant, tool], 完复緱{roles}"

    assistant_count = sum(1 for m in trimmed if m.get("role") == "assistant")
    assert assistant_count == 1, f"assistant中崩应里崩, 出虹现{assistant_count}娆?"


def test_trim_to_budget_paired_assistant_not_duplicated_with_extra_msgs():
    """trim to budget paired assistant not duplicated with extra msgs"""
    builder = MessageBuilder()

    builder.conversation_history = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "task"},
        {"role": "assistant", "content": None, "tool_calls": [
            {"id": "call_1", "type": "function", "function": {"name": "read", "arguments": "{}"}},
            {"id": "call_2", "type": "function", "function": {"name": "write", "arguments": "{}"}},
        ]},
        {"role": "tool", "content": "read_ok", "tool_call_id": "call_1"},
        {"role": "tool", "content": "write_ok", "tool_call_id": "call_2"},
    ]

    _, _, obs_list, assistant_msgs = builder._classify_messages()
    trimmed = builder._trim_to_budget(obs_list, assistant_msgs, budget_tokens=999999)

    # 搴斾为 [assistant, tool_1, tool_2]
    assistant_count = sum(1 for m in trimmed if m.get("role") == "assistant")
    assert assistant_count == 1, f"否屼一assistant中崩应里崩, 出虹现{assistant_count}娆?"
    assert len(trimmed) == 3, f"预期3误? 完复緱{len(trimmed)}"
