# -*- coding: utf-8 -*-
"""
test_inject_compact_pipeline.py — 北京老陈 2026-10-07

逐环节验证 start 注入/压缩链路的系统函数正确性(用例序号连续 1~5, 括号内为对应链路环节):

  用例1(环节1 DB还原)   history_loader._load_previous_messages
  用例2(环节2 初始化)   initialize_run_state.initialize_run_state (不建 conv)
        (环节3 注入)     start_step._build_injected_history (只留存 _injected_history_msgs)
        (环节4 契约)     start_step._build_start_contract
  用例3(环节4b 判定)    start_step._maybe_compact_injected_history (读 _injected_history_msgs)
  用例4(环节5 摘要生成) start_step._compact_injected_history → summary.generate_anchored_summary
        (环节6 装配)     react_loop 侧 [system, 摘要, task]
  用例5(环节7 未超窗)   零退化装配 [system, 历史, task]
  用例6(环节3 边界)     _build_injected_history 的 7 条异常分支(纯本地, 不连 LLM)

用例编号与环节编号两套: 用例名按 1~5 连续(便于 -k 选取与阅读), 环节号标在用例上方注释里
(环节是真实链路的固定顺序, 2/3/4 与 5/6 各合并进一个用例, 判定夹在 4 与 5 之间故曾编为 4b)。

真实链路: react_loop → assemble_start_step → 判定 → 摘要 → 装配, 不手搓 feed。
用法: pytest test_inject_compact_pipeline.py -v -s
"""
import asyncio
import os
import sys
from contextlib import contextmanager

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
# 摘要原文固定落在 backend/summary_out.txt(北京老陈 2026-10-08 定: 此文件位置不变)
SUMMARY_OUT = r"F:\OmniAgentAs-repair\backend\summary_out.txt"  # 摘要留档

# 六段字段名(中英等价) — 模型输出中文字段名同样算合规汇总
FIELDS = ["Goal", "Key Decisions", "Next Steps",
          "Critical Context", "Relevant Files", "Progress"]

# 2026-10-08 小欧 - 配置覆盖的"键原本不存在"哨兵(区别于值为 None)
_MISSING = object()
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
    """摘要原文写根目录 summary_out.txt(位置固定, 北京老陈 2026-10-08 裁定此文件不迁移)"""
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
    # 2026-10-08 小欧 修复死变量: mb 建了却从未挂到 agent(UniversalAgent 自建默认
    #   DEFAULT_CONTEXT_LIMIT=262144), 导致判定实际用 262144 而非 CTX_LIMIT,
    #   超窗阈值与打印值对不上(打印 121868 实际 131072)。显式挂上, 口径与真实
    #   agent_runner 一致(运行时由 llm_service.context_limit 覆盖同一属性)。— 小欧-2026-10-08
    agent.message_builder = mb
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


def _bare_agent():
    """构造只带被测函数所需最小面的 agent(纯本地, 不建 service 不连 LLM)

    _build_injected_history 只做一件事: 置 agent._injected_history_msgs,
    故无需完整 UniversalAgent 实例(真实 agent 见 _make_agent)。
    """
    class _A:  # noqa: N801 - 测试内私有桩类
        pass
    return _A()


@contextmanager
def _cfg_override(dotted_key, value):
    """临时改运行期配置值(仅内存, 不写配置文件)

    严禁写 config/config.yaml(配置污染铁律): 只改 Config 内部 _config_data 内存对象,
    with 退出后原值还原。dotted_key 形如 "tuning.compaction.start_enabled"。
    Config 只有 get() 无 setter, 故走 _config_data(与 Config.get 的取数路径同一份)。
    """
    cfg = get_config()
    parts = dotted_key.split(".")
    node = cfg._config_data          # Config.get 的唯一数据源, 改这里即生效
    for p in parts[:-1]:
        if not isinstance(node.get(p), dict):
            node[p] = {}
        node = node[p]
    old = node.get(parts[-1], _MISSING)
    node[parts[-1]] = value
    try:
        yield
    finally:
        if old is _MISSING:
            node.pop(parts[-1], None)
        else:
            node[parts[-1]] = old


def _inject(prev, context=None):
    """跑 _build_injected_history 并返回落地的 _injected_history_msgs"""
    agent = _bare_agent()
    ctx = {"previous_messages": prev} if context is None else context
    _build_injected_history(agent, ctx)
    return getattr(agent, "_injected_history_msgs", None)


# ── 用例1(环节1: DB 还原) ───────────────────────────────────────
def test_01_history_loader_restore():
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


# ── 用例2(环节2 初始化 + 环节3 注入 + 环节4 契约) ───────────────
def test_02_init_and_inject():
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


# ── 共用helper: assemble_start_step(判定+摘要) → react_loop 侧装配 ──
def _run_assemble_then_mount(agent, context, task=TASK):
    """复刻真实链路: await assemble_start_step(含判定+摘要) → 装配 conv"""
    import time as _t
    _t0 = _t.time()
    # 2026-10-08 小欧 - 必须 close: 新建事件循环却不关闭 → httpx 连接池随循环对象悬挂,
    #   pytest 收尾时抛 "coroutine method 'aclose' of 'Response.aiter_bytes' was never awaited";
    #   且循环对象未回收, 多次调用会累积(每用例各建一个) — 小欧-2026-10-08
    _loop = asyncio.new_event_loop()
    try:
        _loop.run_until_complete(assemble_start_step(agent, context))
    finally:
        _loop.close()
    summary = getattr(agent, "_start_summary", "") or ""
    agent.message_builder.init_history(getattr(agent, "_sys_prompt", "") or "", task or "")
    if summary:
        agent.message_builder.inject_history(
            [{"role": "assistant", "content": summary}])
    else:
        agent.message_builder.inject_history(getattr(agent, "_injected_history_msgs", None) or [])
    return summary, f"{_t.time()-_t0:.2f}s"


# ── 用例3(环节4b: 超窗判定, assemble_start_step 内部) ───────────
def test_03_threshold_check():
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


# ── 用例7: _maybe_compact_injected_history 边界分支 ───────────────
def test_07_threshold_edge_branches():
    """环节4b 边界: 关闭开关 / 空历史 / ratio 配置 / 阈值边界(不含/含)

    覆盖 start_step.py:140-163 四条此前从未执行的路径:
      :140 首行清零(脏标记必须被复位) / :146 start_enabled=False 短路
      :153 空 history 短路 / :158 ratio 从配置读取 / :161 阈值比较
    """
    # 分支1: 首行必须清零 — 预置脏标记, 调用后应被复位为 False
    agent = _make_agent()
    agent._needs_compact = True          # 脏: 上次任务留下的标记
    agent._injected_history_msgs = []
    _maybe_compact_injected_history(agent)
    assert agent._needs_compact is False, "首行未清零: 残留上次任务的标记"
    print("[判定边界1 首行清零] 预置True -> 调用后False [OK]")

    # 分支2: start_enabled=False → 短路, 即使历史超窗也不置标记
    agent = _make_agent()
    prev = _load_previous_messages(
        SESSION, context_root_task_id=ROOT_TASK, upper_message_id=UPPER_MSG_ID)
    context = {"previous_messages": prev}
    initialize_run_state(agent, TASK, agent.task_id, context)
    _build_injected_history(agent, context)
    assert agent._injected_history_msgs, "注入历史为空, 无法验证开关分支"
    with _cfg_override("tuning.compaction.start_enabled", False):
        _maybe_compact_injected_history(agent)
    assert agent._needs_compact is False, "start_enabled=False 时不应置标记"
    print("[判定边界2 开关短路] start_enabled=False + 205条超窗 -> 仍False [OK]")

    # 分支3: 空 history(缺属性 / None / 空列表)→ 短路且不置标记
    for attr_val in ("__absent__", None, []):
        agent = _make_agent()
        if attr_val == "__absent__":
            if hasattr(agent, "_injected_history_msgs"):
                delattr(agent, "_injected_history_msgs")
        else:
            agent._injected_history_msgs = attr_val
        _maybe_compact_injected_history(agent)
        assert agent._needs_compact is False, \
            f"_injected_history_msgs={attr_val} 应短路置False"
    print("[判定边界3 空历史短路] 缺属性/None/空列表 3种 -> 均False [OK]")

    # 分支4: ratio 从配置读取(改配置 → 阈值随之变化)
    prev5 = prev[:5]
    agent = _make_agent()
    context5 = {"previous_messages": prev5}
    initialize_run_state(agent, TASK, agent.task_id, context5)
    _build_injected_history(agent, context5)
    rough = MessageBuilder._estimate_tokens(agent._injected_history_msgs)
    # ratio=0 → 阈值0 → 必然超窗; ratio=1.0 → 阈值=ctx → 小历史必不超窗
    with _cfg_override("tuning.compaction.start_trigger_ratio", 0.0):
        _maybe_compact_injected_history(agent)
    assert agent._needs_compact is True, f"ratio=0 阈值应为0, {rough}>0 应超窗"
    print(f"[判定边界4 ratio读取] ratio=0 → 阈值0 → 超窗=True [OK]")

    agent = _make_agent()
    initialize_run_state(agent, TASK, agent.task_id, context5)
    _build_injected_history(agent, context5)
    with _cfg_override("tuning.compaction.start_trigger_ratio", 1.0):
        _maybe_compact_injected_history(agent)
    assert agent._needs_compact is False, \
        f"ratio=1.0 阈值={int(CTX_LIMIT * 1.0)}, 小历史 {rough} 不应超窗"
    print(f"[判定边界4 ratio读取] ratio=1.0 → 阈值{int(CTX_LIMIT)} → 超窗=False [OK]")

    # 分支5: 阈值边界 — 恰好等于阈值不置标记(严格大于才置)
    agent = _make_agent()
    agent._injected_history_msgs = [{"role": "user", "content": "x" * 400}]
    real_tokens = MessageBuilder._estimate_tokens(agent._injected_history_msgs)
    # 基准取 agent 实际持有的窗口(勿用 CTX_LIMIT 常量: 真实运行时该值由
    # agent_runner 用 llm_service.context_limit 覆盖, 断言必须跟实际值走)
    ctx = agent.message_builder.MAX_CONTEXT_TOKENS
    # 令阈值恰等于真实 token 数 → rough > threshold 为假 → 不置标记
    ratio_exact = real_tokens / float(ctx)
    with _cfg_override("tuning.compaction.start_trigger_ratio", ratio_exact):
        _maybe_compact_injected_history(agent)
    assert int(ctx * ratio_exact) == real_tokens, \
        f"阈值应恰等: int({ctx}×{ratio_exact})={int(ctx * ratio_exact)} != {real_tokens}"
    assert agent._needs_compact is False, \
        f"阈值恰等({real_tokens})时不应置标记(ratio={ratio_exact})"
    # 再压低一档阈值 → 变成严格小于 → 应置标记
    with _cfg_override("tuning.compaction.start_trigger_ratio", ratio_exact * 0.99):
        _maybe_compact_injected_history(agent)
    assert agent._needs_compact is True, (
        f"阈值略低于实际时应置标记: rough={real_tokens} "
        f"threshold={int(ctx * ratio_exact * 0.99)}")
    print(f"[判定边界5 阈值边界] ctx={ctx} 恰等={real_tokens}→False; 略低→True [OK]")


# ── 用例4(环节5 压缩 + 环节6 装配) ──────────────────────────────
def test_04_compact_and_assemble():
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


# ── 用例5(环节7: 未超窗零退化) ──────────────────────────────────
def test_05_no_compact_when_not_needed():
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


# ── 用例6: _build_injected_history 边界分支(7 条异常路径) ────────
def test_06_inject_edge_branches():
    """环节3 边界: _build_injected_history 的 7 条异常分支逐条执行

    真数据只走 happy path, 下列分支在任何一次真实任务里都未必命中,
    恰是它们藏 bug(尤其 :108 非dict剥离 = 防 provider 400 的病根防护)。
    """
    # 分支1: context 为 None / 非 dict → 空列表
    for bad_ctx in (None, [], "x", 123):
        fed = _inject([], context=bad_ctx)
        assert fed == [], f"context={bad_ctx!r} 应置空列表, 实际 {fed!r}"
    print(f"\n[边界1 context非法] context=None/[]/str/int 4种 -> 均置 [] [OK]")

    # 分支2: previous_messages 缺失 / 空 / 非 list → 空列表
    for bad_prev in (None, [], {}, "abc", 7):
        fed = _inject([], context={"previous_messages": bad_prev})
        assert fed == [], f"prev={bad_prev!r} 应置空列表, 实际 {fed!r}"
    fed = _inject([], context={})          # 键都不存在
    assert fed == [], "缺 previous_messages 键应置空列表"
    print("[边界2 prev非法] None/空list/空dict/str/int/缺键 6种 -> 均置 [] [OK]")

    # 分支3: tool_calls 含非 dict 元素 → 剥离(病根防护: 防 provider 400)
    prev = [
        {"role": "assistant", "content": None, "tool_calls": [
            {"id": "call_ok", "name": "bash", "arguments": "{}"},
            None,                                  # 非dict
            "字符串",                                # 非dict
            {"id": "call_ok2", "name": "grep", "arguments": "{}"},
        ]},
    ]
    fed = _inject(prev)
    assert len(fed) == 1, f"应留1条assistant, 实际 {len(fed)}"
    tcs = fed[0]["tool_calls"]
    assert len(tcs) == 2, f"应剥离为2个dict, 实际 {len(tcs)}"
    assert all(isinstance(t, dict) for t in tcs), "剥离后仍残留非dict元素"
    assert [t["id"] for t in tcs] == ["call_ok", "call_ok2"], "合法元素被误删"
    print(f"[边界3 剥离非dict] 4元素(含None/str) -> 留 {len(tcs)} 个dict [OK]")

    # 分支4: tool_calls 是裸 dict(非list) → 包成单元素 list
    prev = [{"role": "assistant", "content": None,
             "tool_calls": {"id": "c1", "name": "bash", "arguments": "{}"}}]
    fed = _inject(prev)
    assert len(fed) == 1 and isinstance(fed[0]["tool_calls"], list), \
        f"裸dict应包成list, 实际 {fed[0].get('tool_calls')!r}"
    assert fed[0]["tool_calls"][0]["id"] == "c1", "包单元素后内容不符"
    print("[边界4 裸dict包list] -> 单元素list [OK]")

    # 分支5: tool_calls 类型异常 → 空 → 回退 content(不丢整条 assistant)
    for bad_tc in ("字符串tool_calls", 123, object()):
        prev = [{"role": "assistant", "content": "答案正文",
                 "tool_calls": bad_tc}]
        fed = _inject(prev)
        assert len(fed) == 1, f"tool_calls={type(bad_tc).__name__} 应回退content留1条"
        assert fed[0] == {"role": "assistant", "content": "答案正文"}, \
            f"回退形态不对: {fed[0]!r}"
    # 类型异常且无 content → 整条丢弃(不得产出空 assistant)
    fed = _inject([{"role": "assistant", "content": None, "tool_calls": "坏"}])
    assert fed == [], "tool_calls坏且无content应丢弃该assistant"
    print("[边界5 异常回退content] 3种类型 -> 留content; 无content则丢弃 [OK]")

    # 分支6: user content 为空 → 丢弃; 非空 → 保留
    prev = [{"role": "user", "content": "正常问题"},
            {"role": "user", "content": ""},
            {"role": "user", "content": None},
            {"role": "user"},
            {"role": "assistant", "content": "上一轮答"}]
    fed = _inject(prev)
    assert [m["content"] for m in fed] == ["正常问题", "上一轮答"], \
        f"空user应被丢弃, 实际 {[m.get('content') for m in fed]}"
    print("[边界6 空user丢弃] 3种空形态 -> 丢弃; 正常user保留 [OK]")

    # 分支7: role=="system" 保留(非空) / 丢弃(空)
    prev = [{"role": "system", "content": "系统约束"},
            {"role": "system", "content": ""},
            {"role": "assistant", "content": "答"}]
    fed = _inject(prev)
    assert len(fed) == 2, f"应留 system+assistant 两条, 实际 {len(fed)}"
    assert fed[0] == {"role": "system", "content": "系统约束"}, \
        f"system形态不对: {fed[0]!r}"
    print("[边界7 system分支] 非空保留/空丢弃 [OK]")

    # 回归: 以上分支叠加, 末条 user 仍须跳过(防与 task 重复)
    prev = [
        {"role": "system", "content": "S"},
        {"role": "user", "content": "第一问"},
        {"role": "assistant", "content": None, "tool_calls": [
            {"id": "c1", "name": "bash", "arguments": "{}"}, None]},
        {"role": "tool", "tool_call_id": "c1", "content": "结果"},
        {"role": "user", "content": "末条须跳过"},
    ]
    fed = _inject(prev)
    assert len(fed) == 4, f"叠加后应4条, 实际 {len(fed)}"
    assert fed[-1]["role"] == "tool", "末条应是tool(末条user须跳过)"
    assert all(m.get("content") != "末条须跳过" for m in fed), "末条user未被跳过"
    asst = [m for m in fed if m["role"] == "assistant"]
    assert len(asst) == 1 and len(asst[0].get("tool_calls") or []) == 1, \
        "叠加后非dict未剥离"
    print("[边界叠加] 5条混合输入 -> 4条, 末条user跳过+非dict剥离 [OK]")


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "-s", "--no-header", "-x"]))