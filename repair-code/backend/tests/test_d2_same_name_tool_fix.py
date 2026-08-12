"""
D2修复验证测试: 同批同名工具一个被拒另一个保留

场景: LLM FC模式返回2个edittext调用, 一个路径越权被blocked, 另一个路径合法通过
预期: _out中只保留合法的那个edittext, 被拒的被移除

小欧 2026-08-11
"""
import sys
import os
import asyncio
from unittest.mock import MagicMock, patch

import pytest


def test_d2_same_name_tool_one_denied_one_passes():
    """核心测试: 2个同名工具, 1个blocked, 另1个应保留在_out中"""
    from app.services.safety.tool_safety_checker import SafetyResult
    from app.services.agent.handlers.action_handler import check_safety_and_confirm

    # 构造2个同名edittext调用, 不同路径
    call_allowed = {
        "tool_name": "edittext",
        "tool_params": {"path": "F:\\project\\src\\main.py", "content": "# safe edit"}
    }
    call_blocked = {
        "tool_name": "edittext",
        "tool_params": {"path": "C:\\Windows\\System32\\config\\SAM", "content": "# evil edit"}
    }
    all_calls = [call_allowed, call_blocked]

    # mock safety_checker: call_allowed放行, call_blocked拦截
    mock_checker = MagicMock()
    mock_checker.check_before_execute = MagicMock(side_effect=[
        SafetyResult(blocked=False, requires_confirmation=False, safety_level="safe"),
        SafetyResult(blocked=True, message="路径越权(系统禁区): C:\\Windows\\System32", safety_level="dangerous"),
    ])

    # mock agent
    mock_agent = MagicMock()
    mock_agent._step_emitter = MagicMock()
    mock_agent._step_emitter.emit = MagicMock(return_value=MagicMock())

    # _out: 调用方传入的列表
    _out = list(all_calls)

    async def run():
        with patch("app.services.safety.tool_safety_checker.get_tool_safety_checker", return_value=mock_checker):
            async for _ in check_safety_and_confirm(
                agent=mock_agent, all_calls=all_calls, step=1, fc_context={}, _out=_out
            ):
                pass

    asyncio.run(run())

    # 断言: _out只剩1个, 且是call_allowed
    assert len(_out) == 1, f"预期_out长度1, 实际{len(_out)}"
    assert _out[0] is call_allowed, "保留的应是call_allowed对象"
    assert _out[0]["tool_params"]["path"] == "F:\\project\\src\\main.py"


def test_d2_old_logic_would_fail():
    """对比: 旧逻辑(按tool_name过滤)会把2个同名工具全杀, 新逻辑精准"""
    call_allowed = {"tool_name": "edittext", "tool_params": {"path": "safe"}}
    call_blocked = {"tool_name": "edittext", "tool_params": {"path": "evil"}}
    all_calls = [call_allowed, call_blocked]

    # 旧逻辑: 按tool_name过滤 -> 全杀
    _denied_old = [("edittext", "被安全策略拦截", call_blocked)]
    _out_old = list(all_calls)
    _denied_cns = {d[0] for d in _denied_old}
    _out_old[:] = [c for c in all_calls if c.get("tool_name", "") not in _denied_cns]
    assert len(_out_old) == 0, "旧逻辑: 2个同名工具全被移除(误杀)"

    # 新逻辑: 按call对象id过滤 -> 精准
    _denied_new = [("edittext", "被安全策略拦截", call_blocked)]
    _out_new = list(all_calls)
    _denied_call_ids = {id(d[2]) for d in _denied_new}
    _out_new[:] = [c for c in all_calls if id(c) not in _denied_call_ids]
    assert len(_out_new) == 1, "新逻辑: 只移除被拒的"
    assert _out_new[0] is call_allowed, "新逻辑: 保留的是合法调用"


def test_d2_three_same_name_two_denied():
    """扩展: 3个同名工具, 2个被拒, 1个保留"""
    call_1 = {"tool_name": "edittext", "tool_params": {"path": "evil1"}}
    call_2 = {"tool_name": "edittext", "tool_params": {"path": "evil2"}}
    call_3 = {"tool_name": "edittext", "tool_params": {"path": "safe"}}
    all_calls = [call_1, call_2, call_3]

    _denied = [
        ("edittext", "blocked", call_1),
        ("edittext", "blocked", call_2),
    ]
    _out = list(all_calls)
    _denied_call_ids = {id(d[2]) for d in _denied}
    _out[:] = [c for c in all_calls if id(c) not in _denied_call_ids]

    assert len(_out) == 1
    assert _out[0] is call_3


def test_d2_all_denied_different_names():
    """正常场景: 不同名工具各被拒, 全部移除(无误杀)"""
    call_a = {"tool_name": "edittext", "tool_params": {"path": "evil"}}
    call_b = {"tool_name": "delete_file", "tool_params": {"path": "evil2"}}
    all_calls = [call_a, call_b]

    _denied = [
        ("edittext", "blocked", call_a),
        ("delete_file", "blocked", call_b),
    ]
    _out = list(all_calls)
    _denied_call_ids = {id(d[2]) for d in _denied}
    _out[:] = [c for c in all_calls if id(c) not in _denied_call_ids]

    assert len(_out) == 0
