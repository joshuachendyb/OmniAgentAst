# -*- coding: utf-8 -*-
# 编辑历史:
# 记录 2026-08-08 小欧 创建单元测试: react_cycle场景F相同工具调用死循环检测(_tool_call_signature/_check_same_tool_loop)
#   背景: P6_01(file_not_found)E2E超时根因是LLM连续40+步逐字重复同一Thought并反复调用完全相同工具(writetext写同一文件),
#   每次工具均success, 现有_consecutive_reasoning_only仅拦纯推理空转漏检; 本测试验证新增死循环防御不误伤正常流程。
# 记录 2026-08-08 小欧 v1.6双阈值: _check_same_tool_loop返回int(count=第N次, 首=1, 签名变化重置=1); 新增_warn_same_tool_loop测试
# 记录 2026-08-11 小欧 对齐task007进化: _warn_same_tool_loop注入role由assistant改user(面向LLM反馈指令强化服从, 提交debc5354f),
#   原test_injects_assistant_marked_message断言role==assistant过时→改名test_injects_user_marked_message断言role==user(测试过时修复)
"""
相同工具调用死循环检测 单元测试 — react_cycle.py 场景F

测试覆盖:
  1. _tool_call_signature: 签名计算(参数顺序无关/并行pending纳入/参数变化即签名变化)
  2. _check_same_tool_loop: 连续相同工具调用计数(count=第N次)/重置/达阈值返回count
  3. _warn_same_tool_loop: 幂等注入user role纠偏消息(带_temp_same_tool_warn标记, task007进化role=user)

Author: 小欧 - 2026-08-08 / 更新: 小欧 2026-08-11
"""

from unittest.mock import MagicMock

from app.services.agent.react_cycle import (
    _tool_call_signature,
    _check_same_tool_loop,
    _warn_same_tool_loop,
    _SAME_TOOL_WARN_ROUNDS,
    _MAX_CONSECUTIVE_SAME_TOOL_CALLS,
)


def _agent():
    """构造带死循环检测状态的agent — 小欧 2026-08-08"""
    a = MagicMock()
    a._consecutive_same_tool_calls = 0
    a._last_tool_call_sig = None
    a._warned_same_tool_loop = False
    a.llm_call_count = 0
    a.message_builder = MagicMock()
    a.message_builder.conversation_history = []
    return a


def _action(tool_name="writetext", params=None, pending=None):
    """构造action类型LLM响应 — 小欧 2026-08-08"""
    resp = {
        "type": "action",
        "tool_name": tool_name,
        "tool_params": params or {},
        "_pending_calls": pending or [],
    }
    return resp


class TestToolCallSignature:
    """_tool_call_signature 签名计算 — 小欧 2026-08-08"""

    def test_same_params_different_order_same_signature(self):
        """params字典顺序不同→签名相同(排序序列化)"""
        s1 = _tool_call_signature(_action(params={"content": "abc", "path": "x.txt"}))
        s2 = _tool_call_signature(_action(params={"path": "x.txt", "content": "abc"}))
        assert s1 == s2

    def test_different_params_different_signature(self):
        """参数内容不同→签名不同"""
        s1 = _tool_call_signature(_action(params={"content": "abc", "path": "x.txt"}))
        s2 = _tool_call_signature(_action(params={"content": "def", "path": "x.txt"}))
        assert s1 != s2

    def test_parallel_pending_included(self):
        """并行pending调用纳入签名(内容变化即签名变化)"""
        s1 = _tool_call_signature(_action(params={"path": "x"}, pending=[{"tool_name": "find", "tool_params": {"p": "1"}}]))
        s2 = _tool_call_signature(_action(params={"path": "x"}, pending=[{"tool_name": "find", "tool_params": {"p": "2"}}]))
        assert s1 != s2


class TestCheckSameToolLoop:
    """_check_same_tool_loop 双阈值计数判定 — 小欧 2026-08-08"""

    def test_first_call_count_is_one(self):
        """首次调用(无上次签名)count=1(第1次)"""
        a = _agent()
        assert _check_same_tool_loop(a, _action()) == 1
        assert a._consecutive_same_tool_calls == 1

    def test_same_call_accumulates(self):
        """连续相同调用: count递增到第N次"""
        a = _agent()
        assert _check_same_tool_loop(a, _action()) == 1
        assert _check_same_tool_loop(a, _action()) == 2
        assert _check_same_tool_loop(a, _action()) == 3   # == _SAME_TOOL_WARN_ROUNDS 纠偏阈值
        assert _check_same_tool_loop(a, _action()) == 4
        assert _check_same_tool_loop(a, _action()) >= _MAX_CONSECUTIVE_SAME_TOOL_CALLS  # >=5 硬终止阈值

    def test_warn_threshold_reached(self):
        """count==_SAME_TOOL_WARN_ROUNDS 即触发纠偏阈值"""
        a = _agent()
        for i in range(_SAME_TOOL_WARN_ROUNDS - 1):
            _check_same_tool_loop(a, _action())
        assert _check_same_tool_loop(a, _action()) == _SAME_TOOL_WARN_ROUNDS

    def test_changed_params_resets_counter(self):
        """参数变化→重置count=1(重新累计,不误伤正常推进)"""
        a = _agent()
        _check_same_tool_loop(a, _action(params={"content": "a"}))
        _check_same_tool_loop(a, _action(params={"content": "a"}))
        assert a._consecutive_same_tool_calls == 2
        # 参数变化→重置为1
        assert _check_same_tool_loop(a, _action(params={"content": "b"})) == 1
        assert a._consecutive_same_tool_calls == 1

    def test_changed_params_resets_warned_flag(self):
        """参数变化→重置count=1同时清纠偏标记(原True→0)"""
        a = _agent()
        a._warned_same_tool_loop = 1
        _check_same_tool_loop(a, _action(params={"content": "b"}))
        assert a._warned_same_tool_loop == 0

    def test_changed_tool_resets_counter(self):
        """换工具→重置count=1"""
        a = _agent()
        _check_same_tool_loop(a, _action("writetext", {"content": "x"}))
        _check_same_tool_loop(a, _action("writetext", {"content": "x"}))
        assert _check_same_tool_loop(a, _action("listdir", {"path": "x"})) == 1
        assert a._consecutive_same_tool_calls == 1


class TestWarnSameToolLoop:
    """_warn_same_tool_loop 纠偏注入(幂等+标记) — 小欧 2026-08-08"""

    def test_injects_user_marked_message(self):
        """注入user role消息带_temp_same_tool_warn标记(task007进化: role由assistant改user强化LLM服从)"""
        a = _agent()
        _warn_same_tool_loop(a, _action(), count=_SAME_TOOL_WARN_ROUNDS)
        msgs = a.message_builder.conversation_history
        assert len(msgs) == 1
        assert msgs[0]["role"] == "user"
        assert msgs[0]["_temp_same_tool_warn"] is True
        assert "writetext" in msgs[0]["content"]

    def test_idempotent_two_max(self):
        """最多注入3条(第2/3/4次), 第5次后调用不再追加 — v1.7(北京老陈)"""
        a = _agent()
        _warn_same_tool_loop(a, _action(), count=2)
        _warn_same_tool_loop(a, _action(), count=3)
        _warn_same_tool_loop(a, _action(), count=4)
        _warn_same_tool_loop(a, _action(), count=5)
        assert len(a.message_builder.conversation_history) == 3

    def test_sets_warned_count(self):
        """注入后_warned_same_tool_loop递增(第2次→1, 第3次→2, 第4次→3) — v1.7(北京老陈)"""
        a = _agent()
        _warn_same_tool_loop(a, _action(), count=2)
        assert a._warned_same_tool_loop == 1
        _warn_same_tool_loop(a, _action(), count=3)
        assert a._warned_same_tool_loop == 2
        _warn_same_tool_loop(a, _action(), count=4)
        assert a._warned_same_tool_loop == 3
