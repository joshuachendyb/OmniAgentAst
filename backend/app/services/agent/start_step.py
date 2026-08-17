# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-17 小健 新建: start 任务输入装配完整过程独立模块(北京老陈驱动, 痛斥 start 业务割裂散落多处)——把
#   start 全部业务收拢一个文件: 注入会话历史 _inject_conversation_history / 超窗判定 _maybe_compact_injected_history
#   / C4 锚定摘要回填 _compact_injected_history / 装配入口 assemble_start_step; 自 initialize_run_state.py 与
#   react_cycle.py 迁入, 单一归属; react_cycle 只保留薄调用(不 import chat 层, P4 解耦)
# 2026-08-17 小健 三思三省彻底收敛(老陈驱动): 契约构造业务自 sse_events 迁入本模块——新增 _build_start_contract
#   在单模块内算 context_summary 快照(message_count/total_tokens) + 构造 MetaStep(type="start", step=0),
#   并据 orchestrator 注入的运行元数据 agent._start_meta(ai_service/task_id/next_step/user_input/session_id/
#   链字段/warning)装配; assemble_start_step 改为③态直接 _build_start_contract, 不再依赖 chat 层 _start_step_factory
#   闭包/factory; 业务彻底单归属 start_step.py, sse_events 删除 build_start_step/send_start_step — 小健 2026-08-17
# 2026-08-17 小健 最合理核查修复(老陈追问"是否最合理"): ① DRY——_start_meta 删除 ai_service 冗余键(与
#   agent.llm_client 同对象, orchestrator 构造 agent 时注入), _build_start_contract 直接读 agent.llm_client;
#   _start_meta 仅装 agent 拿不到的 chat 数据(task_id/next_step/user_input/session_id/链字段/warning);
#   ② KISS/SLAP——assemble_start_step/_build_start_contract 去掉无谓 async(内部零 await), 同步函数直线返回
# 2026-08-17 小健 全系统DRY扫描收敛(老陈指示按10大规范): task_id 改读 agent.task_id(base_agent:59 权威持有,
#   orchestrator 构造时注入), 不再依赖 _start_meta["task_id"]; _start_meta 只承载 next_step/session_id/user_input/
#   链字段/warning(react_cycle 拿不到的必需运行数据), 与 ai_service 删除同属真冗余收敛(单一归属) — 小健 2026-08-17
"""
start_step — start 任务输入装配完整过程(单一模块, 一个入口)

职责(SRP): 仅承载「start 前置装配环节」全部业务——
  - _inject_conversation_history: 注入会话历史(多轮对话上下文回填 message_builder)
  - _maybe_compact_injected_history: 超窗判定(C4, 置 _needs_compact 标记)
  - _compact_injected_history: C4 锚定摘要回填(超窗时一次性清洗注入历史)
  - _build_start_contract: 契约构造(context_summary 快照 + MetaStep 任务输入契约, 自 sse_events 迁入)
  - assemble_start_step: 唯一对外入口(注入历史 → 超窗判定 → 契约构造)
依据: [1] 10.1.1(功能逻辑) / 10.1.2(字段清单) / 10.1.6(C4 清洗) / 10.1.7④⑤(装配落点) / 10.1.8 S3/S4/S5。
"""
from typing import Any, Dict, List, Optional

from app.logger import logger


def _inject_conversation_history(agent, context: Optional[Dict[str, Any]]) -> None:
    """注入会话历史(多轮对话支持) — 北京老陈 2026-06-13; 小沈 2026-06-17 参数名self→agent
    小健 2026-06-26: 修复丢失tool消息和带tool_calls的assistant消息的bug(P0-1)，保留FC协议完整性
    chendyg 2026-06-30: 修复重复user消息bug——previous_messages中最后一条user与init_history注入的task重复
    小健 2026-08-17: 自 initialize_run_state 迁入 start_step(单一归属)

    适用场景: start 装配第一步——把 context.previous_messages 回填 message_builder(多轮对话上下文)。
    使用方法: 直接调用, 传 agent + context; context 无 previous_messages 则空转安全。
    输入: agent 含 message_builder; context 含 previous_messages 历史消息列表。
    输出: 无(内部调用 message_builder.inject_history 装载历史)。
    前置条件: init_history 已装载(system + task); 最后一条 user 跳过(防与 task 重复)。
    """
    if not context or not isinstance(context, dict):
        return
    prev = context.get("previous_messages")
    if not prev or not isinstance(prev, list):
        return
    last_user_idx = -1
    for i in range(len(prev) - 1, -1, -1):
        if prev[i].get("role") == "user":
            last_user_idx = i
            break
    history_msgs = []
    for i, msg in enumerate(prev):
        if i == last_user_idx:
            continue
        role = msg.get("role")
        if role == "tool":
            entry = {"role": "tool", "tool_call_id": msg.get("tool_call_id", ""), "content": msg.get("content", "")}
            # M-04: FC协议需要name字段 — 小欧 2026-07-10
            name = msg.get("name")
            if name:
                entry["name"] = name
            history_msgs.append(entry)
        elif role == "assistant":
            tc_raw = msg.get("tool_calls")
            # 历史重载边界校验 — 小欧 2026-07-18
            # 病根: 持久化 assistant.tool_calls 若含非dict元素(截断/畸形LLM响应落库),
            #       原样回传致 provider 400("Can only get item pairs from a mapping")并触发FC降级。
            # 修复: 仅保留dict元素, 非dict一律剥离; 剥离后为空则回退content分支(无退化)。
            if isinstance(tc_raw, list):
                tc = [t for t in tc_raw if isinstance(t, dict)]
            elif isinstance(tc_raw, dict):
                tc = [tc_raw]
            else:
                tc = []
            if tc:
                history_msgs.append({
                    "role": "assistant",
                    "tool_calls": tc,
                    "content": msg.get("content"),
                })
            elif msg.get("content"):
                history_msgs.append({"role": "assistant", "content": msg["content"]})
        elif role == "user" and msg.get("content"):
            history_msgs.append({"role": "user", "content": msg["content"]})
        elif role == "system" and msg.get("content"):
            history_msgs.append({"role": "system", "content": msg["content"]})
    agent.message_builder.inject_history(history_msgs)


def _maybe_compact_injected_history(agent) -> None:
    """C4 超窗标记(10.1.7⑤ / 10.1.8 S5): 注入历史后估算 token, 超窗则置 _needs_compact — 小健 2026-08-17

    适用场景: start 装配第二步——注入历史后立即判定是否超窗, 为 while 前 C4 摘要回填铺标记。
    使用方法: 直接调用, 传 agent; 超窗置 agent._needs_compact=True(仅标记不触发 LLM)。
    输入: agent 含 message_builder.conversation_history。
    输出: 无(置 agent._needs_compact 布尔标记)。
    前置条件: 注入历史已装载; COMPACTION_ENABLED=False 期间置 False 行为同现状(零退化)。
    关联逻辑: 估算复用 MessageBuilder._estimate_tokens(DRY); 阈值对齐全局 MAX_CONTEXT_TOKENS × MAX_CONTEXT_RATIO。
    """
    agent._needs_compact = False
    from app.services.agent.compaction.compaction_constants import (  # 局部导入避免包级新依赖
        COMPACTION_ENABLED,
        MAX_CONTEXT_RATIO,
        MAX_CONTEXT_TOKENS,
    )
    if not COMPACTION_ENABLED:
        return
    from app.services.agent.message_builder import MessageBuilder
    history = agent.message_builder.conversation_history
    if not history:
        return
    rough = MessageBuilder._estimate_tokens(history)
    if rough > int(MAX_CONTEXT_TOKENS * MAX_CONTEXT_RATIO):
        agent._needs_compact = True
        logger.debug(f"[start_step] 历史超窗({rough}>{int(MAX_CONTEXT_TOKENS*MAX_CONTEXT_RATIO)}), 置 _needs_compact")


async def _compact_injected_history(agent) -> None:
    """C4 超窗锚定摘要回填(10.1.7⑤/10.1.8 S5) — 小健 2026-08-17

    适用场景: start 装配后、while 前一次性清洗注入的历史(超窗时)。
    使用方法: 由 assemble 后置条件调用或 run_react_cycle while 前 await; 摘要回填 conversation_history。
    输入: agent 含 message_builder.conversation_history。
    输出: 无(超窗时以 assistant 摘要消息回填: system[:1] + 摘要 + 最新 task[-1:])。
    前置条件: _maybe_compact_injected_history 已置 _needs_compact=True; 失败兜底原样保留零退化。
    关联逻辑: 摘要生成/模板/截断全归 compaction 模块(SRP); tools=None 走 llm_stream Text 模式。
    """
    from app.services.agent.compaction.summary import generate_anchored_summary

    history = agent.message_builder.conversation_history
    if not history:
        agent._needs_compact = False
        return
    try:
        summary_text = await generate_anchored_summary(agent, history)
    except Exception as e:
        logger.warning(f"[start_step] 锚定摘要失败, 保留原历史(零退化): {type(e).__name__}: {e!r}")
        summary_text = ""
    if summary_text:
        agent.message_builder.conversation_history = (
            history[:1] + [{"role": "assistant", "content": summary_text}] + history[-1:]
        )
        logger.debug(f"[start_step] 摘要回填完成 (tok={len(summary_text)}, 历史 {len(history)}→{3})")
    agent._needs_compact = False


def _build_start_contract(agent, previous_messages: Optional[List]) -> Optional["MetaStep"]:
    """构造 start 任务输入契约 MetaStep(单一归属) — 小健 2026-08-17

    适用场景: start 装配第③步——据 orchestrator 注入的运行元数据(_start_meta)算 context_summary 快照,
    构造 MetaStep(type="start", step=0); 自 sse_events 迁入(start 契约构造业务完整归此模块)。
    使用方法: 由 assemble_start_step 调用; previous_messages 用于快照 message_count/total_tokens。
    输入: agent 含 _sys_prompt(initialize_run_state 已取) / llm_client(orchestrator 构造时注入, provider/model)
          + _start_meta(dict: task_id/next_step/user_input/session_id/context_link_mode/context_root_task_id/warning,
          orchestrator 注入); previous_messages 历史消息列表(空列表则快照 message_count=0)。
    输出: MetaStep(type="start", step=0) —— 任务输入契约: 任务头部 + system_prompt + user_message + context_summary。
    前置条件: _start_meta 已注入(缺则返回 None 旁路兼容); next_step 首次调用须返 0。
    依赖方向: 仅 agent 属性 + MetaStep/MessageBuilder(俱 agent 层), 不 import chat 层(P4 解耦)。
    设计文档: [1] 10.1.1 / 10.1.2 / 10.1.7④ / 10.1.8 S3/S4。
    """
    from app.services.agent.steps import MetaStep  # 局部导入防包级环
    from app.services.agent.message_builder import MessageBuilder

    _meta = getattr(agent, "_start_meta", None)
    _ai = getattr(agent, "llm_client", None)
    _next = _meta.get("next_step") if isinstance(_meta, dict) else None
    if _ai is None or _next is None:
        return None
    _prev = previous_messages or []
    context_summary = {
        "session_id": _meta.get("session_id"),
        "context_link_mode": _meta.get("context_link_mode"),
        "context_root_task_id": _meta.get("context_root_task_id"),
        "message_count": len(_prev),
        "total_tokens": MessageBuilder._estimate_tokens(_prev),
    }
    return MetaStep(
        step=_next(),
        type="start",
        content=_meta.get("user_input") or "",
        display_name=f"{_ai.provider} ({_ai.model})",
        provider=_ai.provider,
        model=_ai.model,
        task_id=getattr(agent, "task_id", None),  # DRY: agent.task_id 权威持有(base_agent:59), 不重复注入 _start_meta — 小健 2026-08-17
        system_prompt=getattr(agent, "_sys_prompt", ""),
        context_summary=context_summary,
        warning=_meta.get("warning"),
    )


def assemble_start_step(agent, context: Optional[Dict]) -> Optional["MetaStep"]:
    """start 任务输入装配完整过程(唯一对外入口, 单模块单归属) — 小健 2026-08-17

    适用场景: run_react_cycle 在 initialize_run_state 之后、while 之前调用一次, 完成 start 全部业务。
    使用方法: 传 agent + context, 返回构造好的 MetaStep(调用方 emit); 无 _start_meta 时返回 None。
    业务顺序(不可乱): ① 注入会话历史 → ② 超窗判定(C4 置 _needs_compact) → ③ 构造任务输入契约 MetaStep
    (语境 summary 快照 + 任务输入契约); 超窗时由调用方在 while 前 await _compact_injected_history 回填。
    输入: agent 含 _sys_prompt(initialize_run_state 已取) / llm_client / _start_meta(orchestrator 注入的运行元数据);
          context 含 previous_messages(注入历史 + 快照 message_count/total_tokens)。
    输出: MetaStep(type="start", step=0) 或 None(无 _start_meta 时保持旁路兼容)。
    前置条件: initialize_run_state 已执行(agent.steps 已重置、init_history 已装载、_sys_prompt 已就绪)。
    依赖方向: 只读 agent 属性 + context, 不 import chat 层(P4 解耦); 运行元数据由 orchestrator 注入 _start_meta。
    设计文档: [1] 10.1.1 / 10.1.2 / 10.1.7④⑤ / 10.1.8 S3/S4/S5。
    """
    # ① 注入会话历史(任务输入装配第一步)
    _inject_conversation_history(agent, context)
    # ② 超窗判定(C4, 注入后立即判定, 置 _needs_compact 供 while 前回填用)
    _maybe_compact_injected_history(agent)

    # ③ 构造任务输入契约(MetaStep): 据 _start_meta 运行元数据 + previous_messages 快照, 缺 _start_meta 则 None
    _prev_msgs = context.get("previous_messages") if isinstance(context, dict) else None
    return _build_start_contract(agent, _prev_msgs)
