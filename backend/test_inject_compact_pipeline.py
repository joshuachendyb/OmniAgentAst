# -*- coding: utf-8 -*-
"""
test_inject_compact_pipeline.py — 北京老陈 2026-10-07

逐环节验证 start 注入/压缩链路的系统函数正确性:
  环节1  DB还原       history_loader._load_previous_messages
  环节2  初始化       initialize_run_state.initialize_run_state (不建 conv)
  环节3  注入         start_step.assemble_start_step → _build_injected_history
  环节4  契约         start_step._build_start_contract
  环节4b 判定         start_step._maybe_compact_injected_history (读 _injected_history_msgs)
  环节5  摘要生成     start_step._compact_injected_history → summary.generate_anchored_summary
  环节6  装配结构     react_loop 侧 [system, 摘要, task]
  环节7  未超窗       零退化装配 [system, 历史, task]

真实链路: react_loop → assemble_start_step → 判定 → 摘要 → 装配, 不手搓 feed。
用法: pytest test_inject_compact_pipeline.py -v -s
"""
import asyncio
import sys

import pytest

sys.path.insert(0, r"F:\OmniAgentAs-repair\backend")
try:
    sys.stdout.reconfigure(encoding="utf-8")   # 控制台 GBK, 避免中文/符号打印报错
except Exception:
    pass

from app.config import get_config
from app.db.models.chat_models import ModelRef
from app.services.agent.message_builder import MessageBuilder
from app.services.agent.universal_agent import UniversalAgent
from app.services.agent.initialize_run_state import initialize_run_state
from app.services.agent.start_step import (
    assemble_start_step, _build_injected_history, _build_start_contract,
    _maybe_compact_injected_history, _compact_injected_history,
)
from app.services.chat.history_loader import _load_previous_messages

SESSION = "f46451fb-df5f-407a-959e-1123ceb20504"
ROOT_TASK = "task-c06dcc18ffce4ab285cc66e72270b7be"
UPPER_MSG_ID = 1007217
TASK = "那你需要更新 问题 文件哦"
CTX_LIMIT = 243736
SUMMARY_OUT = r"F:\OmniAgentAs-repair\backend\summary_out.txt"  # 摘要原文留档

# 六段字段名(中英等价) — 模型输出中文字段名同样算合规汇总
FIELDS = ["Goal", "Key Decisions", "Next Steps",
          "Critical Context", "Relevant Files", "Progress"]
ALIASES = {
    "Goal": ["Goal", "目标"],
    "Key Decisions": ["Key Decisions", "关键决策", "关键结论"],
    "Next Steps": ["Next Steps", "下一步", "后续", "计划"],
    "Critical Context": ["Critical Context", "关键上下文", "上下文", "关键背景"],
    "Relevant Files": ["Relevant Files", "相关文件", "涉及文件", "文件清单"],
    "Progress": ["Progress", "进展", "进度", "已完成"],
}


def hit_fields(text):
    return [f for f in FIELDS if any(a in text for a in ALIASES[f])]


def save_summary(summary, hit, before, after, elapsed=None):
    """摘要原文写根目录 summary_out.txt"""
    header = (f"# 摘要 {len(hit)}/6  回填 {before}->{after} 条"
              + (f"  耗时 {elapsed}" if elapsed else "") + "\n\n")
    with open(SUMMARY_OUT, "w", encoding="utf-8") as f:
        f.write(header + (summary or "(未产出摘要)"))
    return SUMMARY_OUT


def _make_agent():
    """真实 agent + 真实 llm_client"""
    from app.services.lifecycle.service import create_service_instance
    prov, model = "sensenova", "glm-5.2"
    svc = create_service_instance(
        get_config().get(f"ai.{prov}") or {},
        ModelRef(provider=prov, model=model,
                 api_base="https://token.sensenova.cn/v1"))
    mb = MessageBuilder(max_context_tokens=CTX_LIMIT)
    agent = UniversalAgent(llm_client=svc, task_id="test-pipeline-20261007")
    agent._start_meta = {
        "user_input": TASK,
        "session_id": SESSION,
        "context_link_mode": None,
        "context_root_task_id": ROOT_TASK,
        "warning": None,
    }
    return agent


def _roles(conv):
    out = {}
    for m in conv:
        out[m["role"]] = out.get(m["role"], 0) + 1
    return out


def _fc_pairs_ok(conv):
    """FC 配对完整性: assistant.tool_calls 的每个 id 都有对应 tool 消息"""
    call_ids, tool_ids = set(), set()
    for m in conv:
        if m["role"] == "assistant":
            for tc in (m.get("tool_calls") or []):
                if isinstance(tc, dict):
                    call_ids.add(tc.get("id") or tc.get("tool_call_id"))
        elif m["role"] == "tool":
            tool_ids.add(m.get("tool_call_id"))
    missing = {i for i in call_ids if i} - tool_ids
    return len(call_ids), len(missing), missing


# ── 环节1: DB 还原 ─────────────────────────────────────────────
def test_stage1_history_loader_restore():
    """环节1: _load_previous_messages 还原结构正确(条数/角色/tool_calls 配对)"""
    prev = _load_previous_messages(
        SESSION, context_root_task_id=ROOT_TASK, upper_message_id=UPPER_MSG_ID)
    assert isinstance(prev, list) and prev, "还原结果为空"
    r = _roles(prev)
    print(f"\n[环节1 还原] 条数={len(prev)} 角色分布={r}")
    assert r.get("assistant", 0) > 0, "无 assistant 消息"
    assert r.get("tool", 0) > 0, "无 tool 消息"
    # tool 消息必须有 tool_call_id, 否则回传 provider 会400
    no_tcid = [m for m in prev if m["role"] == "tool" and not m.get("tool_call_id")]
    print(f"[环节1 还原] tool 缺 tool_call_id 数={len(no_tcid)}")
    assert not no_tcid, "存在缺 tool_call_id 的 tool 消息"
    # assistant.tool_calls 元素必须全是 dict(provider 400 病根)
    bad_tc = [tc for m in prev if m["role"] == "assistant"
              for tc in (m.get("tool_calls") or []) if not isinstance(tc, dict)]
    print(f"[环节1 还原] 非 dict 的 tool_calls 元素={len(bad_tc)}")
    assert not bad_tc, "assistant.tool_calls 含非 dict 元素(provider 400 病根)"


# ── 环节2+3+4: initialize_run_state → assemble_start_step ──────
def test_stage23_init_and_inject():
    """环节2-4: 初始化(不建消息) → 注入(只留存 fed) → StartStep 契约"""
    agent = _make_agent()
    prev = _load_previous_messages(
        SESSION, context_root_task_id=ROOT_TASK, upper_message_id=UPPER_MSG_ID)
    context = {"previous_messages": prev}

    # 环节2: 运行态初始化(重置状态/取 sys_prompt/写日志, 不再建消息)
    initialize_run_state(agent, TASK, agent.task_id, context)
    conv0 = agent.message_builder.conversation_history
    print(f"\n[环节2 初始化] conv={len(conv0)} (init_history 已推迟, 应 0) "
          f"_sys_prompt={len(getattr(agent, '_sys_prompt', ''))} 字符")
    assert len(conv0) == 0, "init_history 已移出, 初始化阶段不应有消息"
    assert getattr(agent, "_sys_prompt", ""), "_sys_prompt 未取到(契约依赖)"

    # 环节3: 构建注入历史(只留存 _injected_history_msgs, 不写 conv)
    _build_injected_history(agent, context)
    fed = getattr(agent, "_injected_history_msgs", None)
    assert fed, "_injected_history_msgs 未留存(压缩将无输入)"
    r = _roles(fed)
    print(f"[环节3 注入] _injected_history_msgs={len(fed)} 条 角色分布={r}")
    print(f"[环节3 注入] 末条 role={fed[-1]['role']!r}")
    assert len(fed) == len(prev) - 1, f"注入条数不符: {len(fed)} vs prev-1={len(prev)-1}"
    assert r.get("assistant", 0) > 0 and r.get("tool", 0) > 0, "注入历史角色异常"
    # 末条 prev user 须被跳过, 不与 task 重复
    dup = sum(1 for m in fed if m["role"] == "user" and m.get("content") == TASK)
    assert dup == 0, "prev 末条 user 未跳过, 与 task 重复"
    # 构建阶段不触发判定
    assert not hasattr(agent, "_needs_compact"), \
        "_build_injected_history 不应触发判定(属性不应被创建)"
    print("[环节3 注入] 构建阶段无 _needs_compact 属性 [OK]")

    # 环节4: StartStep 契约(直接调 _build_start_contract, 不经 assemble 避免触发摘要 LLM)
    start_step = _build_start_contract(agent, prev)
    assert start_step is not None, "_build_start_contract 未产出 StartStep(缺 _start_meta?)"

    def _f(step, name):
        v = getattr(step, name, None)
        if v is None:
            v = getattr(step, "_" + name, None)
        return v

    ctx_sum = _f(start_step, "context_summary") or {}
    user_msg = _f(start_step, "user_message") or ""
    sys_p = _f(start_step, "system_prompt") or ""
    step_task_id = _f(start_step, "task_id")
    print(f"[环节4 契约] type={start_step.type} step={start_step.step} "
          f"message_count={ctx_sum.get('message_count')} "
          f"total_tokens={ctx_sum.get('total_tokens')} "
          f"user_message={user_msg!r}")
    assert ctx_sum.get("message_count") == len(prev), "契约 message_count 不符"
    exp_tok = MessageBuilder._estimate_tokens(prev)
    assert ctx_sum.get("total_tokens") == exp_tok, \
        f"契约 total_tokens 不符: {ctx_sum.get('total_tokens')} != {exp_tok}"
    assert exp_tok > 0, "total_tokens 应为正"
    assert user_msg == TASK, "契约 user_message 不符"
    assert sys_p, "契约 system_prompt 为空"
    assert step_task_id == agent.task_id, "契约 task_id 不符"

    # FC 配对完整性(在 fed 上校验)
    ncalls, nmiss, miss = _fc_pairs_ok(fed)
    print(f"[环节4 契约] FC 调用={ncalls} 未配对={nmiss}")
    assert nmiss == 0, f"存在未配对 tool_calls: {list(miss)[:3]}"


# ── 共用: assemble_start_step(判定+摘要) → react_loop 侧装配 ─────
def _run_assemble_then_mount(agent, context, task=TASK):
    """复刻真实链路: await assemble_start_step(含判定+摘要) → 装配 conv"""
    import time as _t
    _t0 = _t.time()
    asyncio.new_event_loop().run_until_complete(assemble_start_step(agent, context))
    summary = getattr(agent, "_start_summary", "") or ""
    agent.message_builder.init_history(getattr(agent, "_sys_prompt", "") or "", task or "")
    if summary:
        agent.message_builder.inject_history(
            [{"role": "assistant", "content": summary}])
    else:
        agent.message_builder.inject_history(getattr(agent, "_injected_history_msgs", None) or [])
    return summary, f"{_t.time()-_t0:.2f}s"


# ── 环节4b: 超窗判定(assemble_start_step 内部) ──────────────────
def test_stage4b_threshold_check():
    """环节4b: _maybe_compact_injected_history 判定逻辑(契约构造之前)"""
    agent = _make_agent()
    prev = _load_previous_messages(
        SESSION, context_root_task_id=ROOT_TASK, upper_message_id=UPPER_MSG_ID)
    context = {"previous_messages": prev}
    initialize_run_state(agent, TASK, agent.task_id, context)
    _build_injected_history(agent, context)
    fed = agent._injected_history_msgs
    threshold = int(CTX_LIMIT * 0.5)
    rough = MessageBuilder._estimate_tokens(fed)
    print(f"\n[环节4b 判定] 阈值={threshold} 实际 tokens={rough} (基于 fed {len(fed)} 条)")
    _maybe_compact_injected_history(agent)
    print(f"[环节4b 判定] _needs_compact={agent._needs_compact} (应 True, 超窗)")
    assert agent._needs_compact is True, "205 条历史应超窗置标记"


# ── 环节5+6: 压缩摘要 + 装配 ───────────────────────────────────
def test_stage56_compact_and_assemble():
    """环节5-6: 判定 → 摘要生成 → 装配 [system, 摘要, task]"""
    agent = _make_agent()
    prev = _load_previous_messages(
        SESSION, context_root_task_id=ROOT_TASK, upper_message_id=UPPER_MSG_ID)
    context = {"previous_messages": prev}
    initialize_run_state(agent, TASK, agent.task_id, context)
    _build_injected_history(agent, context)
    fed_len = len(agent._injected_history_msgs)

    # 环节5: 真实链路 assemble_start_step(含判定+摘要) → 装配
    summary, cost = _run_assemble_then_mount(agent, context)
    conv = agent.message_builder.conversation_history
    hit = hit_fields(summary or "")
    print(f"\n[环节5 压缩] fed={fed_len} 条 -> 摘要 len={len(summary)} "
          f"六段={len(hit)}/6 耗时={cost}")
    print(f"[环节5 压缩] 缺段={[f for f in FIELDS if f not in hit]}")
    print(f"[环节5 压缩] summary 开头: {(summary or '')[:80]!r}")
    out = save_summary(summary, hit, fed_len, len(conv), cost)
    print(f"[环节5 压缩] 摘要留档: {out}")
    # 零退化: 失败时装配原历史(而非空 conv)
    if not summary:
        assert len(conv) == fed_len + 2, f"摘要为空应装配原历史, 实际 {len(conv)}"
        print("[环节5 压缩] 摘要为空 -> 零退化装配原历史 [OK]")
    else:
        assert len(conv) == 3, f"有摘要应装配 3 条, 实际 {len(conv)}"
        assert len(hit) == 6, f"摘要非六段: {len(hit)}/6"

    # 环节6: 装配结构 + _needs_compact 复位
    print(f"[环节6 装配] 结构={[m['role'] for m in conv]}")
    assert conv[0]["role"] == "system", "装配丢首条 system"
    assert conv[-1]["role"] == "user" and conv[-1].get("content") == TASK, "装配丢末条 task"
    assert conv[-1]["role"] != "tool", "末条为孤儿 tool"
    if summary:
        assert conv[1]["role"] == "assistant", "摘要应为 assistant 消息"
    assert agent._needs_compact is False, "_needs_compact 未复位"


# ── 环节7: 未超窗零退化 ────────────────────────────────────────
def test_stage7_no_compact_when_not_needed():
    """环节7: 未超窗时不生成摘要, 装配 [system, 原历史..., task]"""
    agent = _make_agent()
    prev = _load_previous_messages(
        SESSION, context_root_task_id=ROOT_TASK, upper_message_id=UPPER_MSG_ID)[:5]
    context = {"previous_messages": prev}
    initialize_run_state(agent, TASK, agent.task_id, context)
    _build_injected_history(agent, context)
    fed_len = len(agent._injected_history_msgs)

    summary, cost = _run_assemble_then_mount(agent, context)
    conv = agent.message_builder.conversation_history
    print(f"\n[环节7 短路] 小历史 fed={fed_len} 条 摘要={len(summary)} "
          f"conv={len(conv)} 耗时={cost}")
    assert summary == "", "未超窗不应产出摘要"
    assert conv[0]["role"] == "system", "装配丢首条 system"
    assert conv[-1].get("content") == TASK, "装配丢末条 task"
    assert len(conv) == fed_len + 2, f"未超窗应装配原历史({fed_len}+2), 实际 {len(conv)}"
    print("[环节7 短路] 未超窗 -> 零退化装配原历史 [OK]")


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "-s", "--no-header", "-x"]))