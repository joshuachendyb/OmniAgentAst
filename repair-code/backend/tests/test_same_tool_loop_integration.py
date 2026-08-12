# -*- coding: utf-8 -*-
# 编辑历史:
# 记录 2026-08-08 小欧 创建集成回归测试: 验证run_react_cycle场景F(相同工具调用死循环双阈值)
#   背景: 日志挖掘发现c1e4603c(2026-08-08 02:21~03:15)真实业务死循环——187次完全相同writetext(diff_tool.py),
#   修复(60a5bfd7 07:44)晚于事故4小时; 现有单测test_same_tool_loop_defense仅验证计数函数, 未验证
#   _process_single_step/run_react_cycle完整链路"第5次相同调用→硬终止FinalStep(failed)+status=FAILED"。
#   本集成测试驱动真实run_react_cycle循环, mock LLM永远返回相同writetext action, 验证防御完整生效。
# 记录 2026-08-08 小欧 三审: 按老陈要求"回归验证修复真能挡住本次死循环模式", 补链路线覆盖
# 记录 2026-08-11 小欧 v1.6双阈值集成测试对齐: 原断言"仅第3轮注入1条"已过时, 现第2/3/4次各注入1条
#   (共3条, role=user + _temp_same_tool_warn, _warned_same_tool_loop int计数上限3), 第5次才硬终止
"""
相同工具调用死循环 — 集成回归测试 (run_react_cycle 场景F 完整链路)

目标: 验证 c1e4603c 死循环模式被修复真实拦截(非仅计数函数正确)。
模拟: LLM 每轮返回完全相同的 writetext action(每次工具都成功) — 与 c1e4603c 完全同构。
预期: 第2/3/4次(round2/3/4)各注入1条纠偏警告消息(共3条, v1.6双阈值); 第5次(round5)硬终止,
       yield FinalStep(outcome=failed, error_type=same_tool_loop), agent.status=FAILED, 循环停止。

Author: 小欧 - 2026-08-08
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from app.services.agent.status_table import AgentStatus
from app.services.agent.chunk_buffer import ChunkBuffer


def _make_agent():
    """构造场景F集成测试 agent — 小欧 2026-08-08"""
    a = MagicMock()
    a.status = AgentStatus.THINKING  # 模拟 initialize_run_state 已置 THINKING
    a.llm_call_count = 0
    a.steps = []
    a.accumulated_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    a._consecutive_truncations = 0
    a._retry_count = 0
    # 场景F 状态字段(与 initialize_run_state 对齐)
    a._consecutive_same_tool_calls = 0
    a._last_tool_call_sig = None
    a._warned_same_tool_loop = False
    # message_builder: conversation_history 真实list(供签名读取/警告注入), 其余 mock
    a.message_builder = MagicMock()
    a.message_builder.conversation_history = []
    # step_emitter: emit 返回 step 本身(与现有单测模式一致)
    a._step_emitter = MagicMock()
    a._step_emitter.emit = lambda step: step
    return a


# 与 c1e4603c 完全同构的 LLM 响应: 每次相同的 writetext
def _same_writetext_action():
    """构造与 c1e4603c 完全相同的 writetext action — 小欧 2026-08-08"""
    return {
        "type": "action",
        "tool_name": "writetext",
        "tool_params": {
            "path": "E:\\test_dir\\diff_tool.py",
            "content": "#!/usr/bin/env python3\n# -*- coding: utf-8 -*-\n\"\"\"diff_tool.py\"\"\"",
        },
        "reasoning": "第一阶段已完成。test.txt 是 UTF-8 编码、669 行、18213 字节",
        "thought": "第一阶段已完成。test.txt 是 UTF-8 编码、669 行、18213 字节",
        "_pending_calls": [],
    }


@pytest.mark.asyncio
async def test_same_tool_loop_terminates_at_5th_round():
    """集成: 连续5次相同writetext → 第5次硬终止 FinalStep(same_tool_loop) + status=FAILED — 小欧 2026-08-08"""
    from app.services.agent import react_cycle as rc

    agent = _make_agent()

    # patch LLM 永远返回相同 action
    async def _fake_call_llm(agent_, messages, tools):
        yield ("response", _same_writetext_action())

    # patch 分发: 模拟工具成功执行完成(不落盘), 保持 EXECUTING
    async def _fake_dispatch(agent_, llm_response):
        from app.services.agent.steps import ObservationStep
        yield ObservationStep(
            step=agent_.llm_call_count,
            llm_data=[{"summary": "写入文件 E:\\test_dir\\diff_tool.py 成功", "action": {}, "status": {"exec_code": "ok"}}],
            tool_result={},
        )

    with patch.object(rc, "call_llm_with_fallback", side_effect=_fake_call_llm), \
         patch.object(rc, "get_openai_tools", return_value=[]), \
         patch.object(rc, "_dispatch_handler", side_effect=_fake_dispatch), \
         patch.object(rc, "initialize_run_state", return_value=ChunkBuffer()):

        finals = []
        obs_steps = 0
        loop_warn_seen = False
        async for event in rc.run_react_cycle(agent, "多阶段文件处理任务", task_id="task-test-loop"):
            from app.services.agent.steps import FinalStep, ObservationStep
            if isinstance(event, FinalStep):
                finals.append(event)
            elif isinstance(event, ObservationStep):
                obs_steps += 1

        # 第1~4轮: 4次工具成功(ObservationStep); 第5轮硬终止
        assert obs_steps == 4, f"预期前4轮工具成功, 实际 obs_steps={obs_steps}"
        # 至少产出1个 FinalStep, 且为 same_tool_loop 硬终止
        assert finals, "未产出 FinalStep(same_tool_loop)"
        f = finals[-1]
        assert f.outcome == "failed", f"outcome 应为 failed, 实际={f.outcome}"
        assert f.error_type == "same_tool_loop", f"error_type 应为 same_tool_loop, 实际={f.error_type}"
        # 状态终态
        assert agent.status == AgentStatus.FAILED, f"agent.status 应为 FAILED, 实际={agent.status}"


@pytest.mark.asyncio
async def test_warns_injected_at_2nd_to_4th_rounds():
    """集成: 第2/3/4次相同调用各注入1条纠偏(user role + _temp_same_tool_warn, v1.6共3条), 第5次才硬终止 — 小欧 2026-08-11"""
    from app.services.agent import react_cycle as rc
    from app.services.agent.steps import FinalStep, ObservationStep

    agent = _make_agent()

    async def _fake_call_llm(agent_, messages, tools):
        yield ("response", _same_writetext_action())

    async def _fake_dispatch(agent_, llm_response):
        yield ObservationStep(
            step=agent_.llm_call_count,
            llm_data=[{"summary": "成功", "action": {}, "status": {"exec_code": "ok"}}],
            tool_result={},
        )

    with patch.object(rc, "call_llm_with_fallback", side_effect=_fake_call_llm), \
         patch.object(rc, "get_openai_tools", return_value=[]), \
         patch.object(rc, "_dispatch_handler", side_effect=_fake_dispatch), \
         patch.object(rc, "initialize_run_state", return_value=ChunkBuffer()):

        async for event in rc.run_react_cycle(agent, "任务", task_id="task-test-warn"):
            pass

        # 死循环中被注入的 user 纠偏消息(标记 _temp_same_tool_warn), 第2/3/4次各1条共3条
        warns = [m for m in agent.message_builder.conversation_history
                 if m.get("_temp_same_tool_warn")]
        # v1.6双阈值: 最多注入3条(第2/3/4次, int计数上限), 内容含工具名+签名
        assert len(warns) == 3, f"纠偏警告应注入3条(第2/3/4次各1), 实际={len(warns)}"
        assert "writetext" in warns[0]["content"]
        assert "完全相同" in warns[0]["content"]
        # 终态清理后不残留(断言pop_temp_messages被调 / 或注入标记最终被清理)
        # 注: _finalize_cycle 调 pop_temp_messages, 此处 conversation_history 为 mock list,
        #     真实清理逻辑由 message_builder 实现, 单测仅验证注入侧(见单测test_warn_idempotent)。
        # 终态
        assert agent.status == AgentStatus.FAILED


@pytest.mark.asyncio
async def test_changed_params_no_false_termination():
    """集成: 参数变化(LLM正常推进) → 计数重置, 绝不误伤终止 — 小欧 2026-08-08"""
    from app.services.agent import react_cycle as rc
    from app.services.agent.steps import ObservationStep

    agent = _make_agent()
    call_seq = {"n": 0}

    def _next_action():
        call_seq["n"] += 1
        # 每轮参数都不同(模拟正常推进)
        return {
            "type": "action",
            "tool_name": "writetext",
            "tool_params": {"path": f"E:\\test_dir\\file_{call_seq['n']}.txt", "content": f"内容{call_seq['n']}"},
            "reasoning": f"第{call_seq['n']}阶段处理",
            "thought": f"第{call_seq['n']}阶段处理",
            "_pending_calls": [],
        }

    async def _fake_call_llm(agent_, messages, tools):
        yield ("response", _next_action())

    async def _fake_dispatch(agent_, llm_response):
        yield ObservationStep(
            step=agent_.llm_call_count,
            llm_data=[{"summary": "成功", "action": {}, "status": {"exec_code": "ok"}}],
            tool_result={},
        )

    # 手动限制循环轮数: 跑8轮, 全部正常推进, 不应出现 same_tool_loop 终止
    from app.services.agent.steps import FinalStep
    finals = []
    with patch.object(rc, "call_llm_with_fallback", side_effect=_fake_call_llm), \
         patch.object(rc, "get_openai_tools", return_value=[]), \
         patch.object(rc, "_dispatch_handler", side_effect=_fake_dispatch), \
         patch.object(rc, "initialize_run_state", return_value=ChunkBuffer()), \
         patch.object(rc, "get_config") as _gc:
        # max_steps 拉大, 观察8轮正常推进
        _gc.return_value.get_max_steps.return_value = 20
        async for event in rc.run_react_cycle(agent, "任务", task_id="task-test-normal"):
            if isinstance(event, FinalStep):
                finals.append(event)
            # 到达 8 轮后中断(模拟用户停止观察)
            if agent.llm_call_count >= 8:
                break

        # 8轮正常推进: 无 same_tool_loop 终止
        assert not any(getattr(f, "error_type", None) == "same_tool_loop" for f in finals), \
            "参数变化不应触发 same_tool_loop 终止"
        # 计数应因参数变化不断重置, 保持在低位
        assert agent._consecutive_same_tool_calls <= 1, \
            f"参数变化后计数应重置, 实际={agent._consecutive_same_tool_calls}"
