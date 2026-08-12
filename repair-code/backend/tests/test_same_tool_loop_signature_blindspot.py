# -*- coding: utf-8 -*-
# 编辑历史:
# 记录 2026-08-08 小欧 创建"签名盲区"探测测试: 验证_tool_call_signature对content尾部微变是否漏检
#   背景: c1e4603c死循环修复(_tool_call_signature用全量tool_params排序JSON), 集成验证证明"content完全相同"能被拦。
#   但若LLM每次在content尾部掺入时间戳/序号(真实数据常见), 签名即变→count重置→检测失效, 死循环变种可能复活。
#   本测试对照验证A(content全同,应拦截)与B(content尾带序号,探测是否漏检), 供老陈定夺是否需补防。
"""
_tool_call_signature 签名盲区探测 — content 微变是否绕过死循环检测

对照组 A: content 每轮完全相同 (c1e4603c 真实形态) → 预期第5次硬终止
探测组 B: content 每轮尾部掺序号 (模拟 LLM 伪装推进) → 探测当前检测是否漏检
Author: 小欧 - 2026-08-08
"""

import pytest
from unittest.mock import MagicMock, patch

from app.services.agent.status_table import AgentStatus
from app.services.agent.chunk_buffer import ChunkBuffer


def _make_agent():
    a = MagicMock()
    a.status = AgentStatus.THINKING
    a.llm_call_count = 0
    a.steps = []
    a.accumulated_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    a._consecutive_truncations = 0
    a._retry_count = 0
    a._consecutive_same_tool_calls = 0
    a._last_tool_call_sig = None
    a._warned_same_tool_loop = False
    a.message_builder = MagicMock()
    a.message_builder.conversation_history = []
    a._step_emitter = MagicMock()
    a._step_emitter.emit = lambda step: step
    return a


@pytest.mark.asyncio
async def test_content_identical_is_blocked():
    """对照组A: content 每轮完全相同 → 第5次必须硬终止(已知能拦) — 小欧 2026-08-08"""
    from app.services.agent import react_cycle as rc
    from app.services.agent.steps import FinalStep

    agent = _make_agent()

    async def _fake_call_llm(agent_, messages, tools):
        yield ("response", {
            "type": "action", "tool_name": "writetext",
            "tool_params": {"path": r"E:\test_dir\diff_tool.py", "content": "完全相同内容"},
            "thought": "t", "reasoning": "r", "_pending_calls": [],
        })

    async def _fake_dispatch(agent_, llm_response):
        from app.services.agent.steps import ObservationStep
        yield ObservationStep(step=agent_.llm_call_count, llm_data=[{"summary": "ok"}], tool_result={})

    finals = []
    with patch.object(rc, "call_llm_with_fallback", side_effect=_fake_call_llm), \
         patch.object(rc, "get_openai_tools", return_value=[]), \
         patch.object(rc, "_dispatch_handler", side_effect=_fake_dispatch), \
         patch.object(rc, "initialize_run_state", return_value=ChunkBuffer()):
        async for event in rc.run_react_cycle(agent, "task", task_id="t-A"):
            if isinstance(event, FinalStep):
                finals.append(event)

    assert finals, "对照组A: 应拦截但未拦截"
    assert finals[-1].error_type == "same_tool_loop", f"A error_type={finals[-1].error_type}"


@pytest.mark.asyncio
async def test_content_micro_varies_may_bypass():
    """探测组B: content 每轮尾部掺序号 → 探测当前检测是否漏检 — 小欧 2026-08-08
    此测试断言当前行为(记录真值), 供决策: 若返回未拦截(漏检), 则确认签名盲区存在, 需老陈定夺补防。"""
    from app.services.agent import react_cycle as rc
    from app.services.agent.steps import FinalStep

    agent = _make_agent()
    seq = {"n": 0}

    async def _fake_call_llm(agent_, messages, tools):
        seq["n"] += 1
        # 关键: content 尾部掺序号, 其余(工具/路径)完全相同 —— 伪装死循环
        yield ("response", {
            "type": "action", "tool_name": "writetext",
            "tool_params": {"path": r"E:\test_dir\diff_tool.py",
                            "content": f"相同正文...\n# 第{seq['n']}轮"},
            "thought": "t", "reasoning": "r", "_pending_calls": [],
        })

    async def _fake_dispatch(agent_, llm_response):
        from app.services.agent.steps import ObservationStep
        yield ObservationStep(step=agent_.llm_call_count, llm_data=[{"summary": "ok"}], tool_result={})

    finals = []
    with patch.object(rc, "call_llm_with_fallback", side_effect=_fake_call_llm), \
         patch.object(rc, "get_openai_tools", return_value=[]), \
         patch.object(rc, "_dispatch_handler", side_effect=_fake_dispatch), \
         patch.object(rc, "initialize_run_state", return_value=ChunkBuffer()), \
         patch.object(rc, "get_config") as _gc:
        _gc.return_value.get_max_steps.return_value = 50
        async for event in rc.run_react_cycle(agent, "task", task_id="t-B"):
            if isinstance(event, FinalStep):
                finals.append(event)

    same_loop = [f for f in finals if f.error_type == "same_tool_loop"]
    print(f"[探测B] 跑满后 same_tool_loop 拦截数={len(same_loop)}, "
          f"llm_call_count={agent.llm_call_count}, finals={len(finals)}")
    # 记录真值, 供判断
    assert len(same_loop) == 0, "探测B: 当前检测竟然拦住了(无盲区)"
    print("[探测B] 确认: content 微变未被拦截 —— 签名盲区存在, 需要老陈定夺")
