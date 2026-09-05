
# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-09-05 小健 8.4拆分(react_cycle.py拆四): 提取 _dispatch_handler(原行288-389, 含函数体内状态推断块337-389),
#   逐字复制只改import — 按type分派handler, 基于 event type 推断状态(物理上状态推断块在函数体内不可切分,整体随迁)

"""react_dispatch — 类型分派 + 状态推断

按type分派handler(action/answer), 依事件流(seen_types)推断终态/可恢复错误/拒绝计数。

8.4拆分自 react_cycle.py(老名消亡) — 小健 2026-09-05
"""

import time
from app.logger import log_and_print
from app.services.agent.status_table import AgentStatus, set_status, set_failed, set_cancelled, set_completed
from app.services.agent.handlers import (
    handle_action, handle_answer,
)
from app.services.agent.react_inference import _RECOVERABLE_ERRORS

async def _dispatch_handler(agent, llm_response):
    """按type分派handler，基于 event type 推断状态 — chendyg 2026-07-01 / 小欧 2026-07-13 去掉 recoverable
    
    type 路由表（知识备忘 — 小欧 2026-07-15）：
    ┌────────┬─────────────────┬───────────────────┐
    │ type   │ handler          │ 状态              │
    ├────────┼─────────────────┼───────────────────┤
    │ action │ handle_action    │ 继(不设终态)       │
    │ answer │ handle_answer    │ → FinalStep →     │
    │        │                  │   set_completed   │
    │ error  │ handle_answer    │ → ErrorStep →     │
    │        │ (error 分支)     │   set_failed      │
    │ 其他   │ handle_answer    │ → ErrorStep →     │
    │        │ (未知类型分支)   │   set_failed      │
    └────────┴─────────────────┴───────────────────┘
    type 产生于 llm_stream.py call_llm_stream() 末尾，
    规则：有 tool_calls → action；仅文本 → answer；异常 → error。
    type 不由 LLM 输出，由 agent 推断（详见 llm/core.py 头部）。
    
    状态推断规则:
    - 含 retrying → set_status(RETRYING)
    - 含 final → set_completed（按 outcome 子规则: failed→set_failed, cancelled→set_cancelled）
    - 含 error → 区分可恢复(拒绝/拦截,不失败,循环继续) 与 不可恢复(set_failed)
    - 其他 → 不设置状态,继续
    """
    parsed_type = llm_response.get("type", "answer")
    step = agent.llm_call_count
    thought = llm_response.get("thought", "")
    reasoning = llm_response.get("reasoning", "")
    if thought or reasoning:  # 2026-07-19 小欧 修复: reason-only action step也输出控制台
        reasoning_part = f"\n{time.strftime('%H:%M:%S')} === 推理 ===\n{reasoning}" if reasoning else ""
        log_and_print(f"{time.strftime('%H:%M:%S')} [Thought] step={step}, {thought}{reasoning_part}")  # 小欧 2026-07-02 控制台
    if parsed_type == "action":
        handler = handle_action(agent, llm_response)
    else:
        handler = handle_answer(agent, llm_response)

    _EV_FINAL, _EV_RETRY, _EV_ERROR = "final", "retrying", "error"
    seen_types = set()
    last_error_event = None
    final_event = None
    async for event in handler:
        seen_types.add(event.type)
        if event.type == _EV_ERROR:
            last_error_event = event
        elif event.type == _EV_FINAL:
            final_event = event
        yield event

    if _EV_RETRY in seen_types:
        set_status(agent, AgentStatus.RETRYING, "触发重试")
    elif _EV_FINAL in seen_types:
        # outcome 驱动终态声明: 读 FinalStep.outcome, 不依赖位置/类型 — 小欧 2026-07-18
        # 用循环内单独捕获的 final_event(真实 FinalStep), 不取末事件 last_event(#7: 末事件未必是final, 脆弱)
        oc = getattr(final_event, "outcome", "completed")
        if oc == "failed":
            set_failed(agent, getattr(final_event, "error_message", "") or final_event.get_content())
        elif oc == "cancelled":
            set_cancelled(agent)
        else:
            set_completed(agent)
    elif _EV_ERROR in seen_types:
        # 无 final → 可恢复错误(blocked/user_rejected/timeout, 循环继续)或原子异常(旧数据)
        error_event = last_error_event
        _kw = getattr(error_event, "_kwargs", {}) or {}
        err_type = _kw.get("error_type", "")
        error_msg = error_event.get_content() if hasattr(error_event, 'get_content') else ""
        if err_type in _RECOVERABLE_ERRORS:
            # 拒绝/拦截是可恢复的(拒绝≠失败, 符合人类认知): 不置终态, 反馈已进LLM历史,
            # 主循环 EXECUTING→THINKING 让LLM换工具。 — 小欧 2026-07-13
            # 计数按"同工具+同类型错误"累计(北京老陈 2026-07-13): 不同工具被拒不限次数
            # (往往是参数问题, 换工具/换参数即可); 仅同一工具同一类拒绝累计≥3次才说明LLM
            # 陷入死胡同, 必须停止 loop → FAILED。故用 per-(tool,type) 字典。
            # 工具名缺失时不累计(无法分键, 避免空名合并误累计), 保持可恢复回THINKING, 不误杀。
            _tool = llm_response.get("tool_name", "") or getattr(error_event, "tool_name", "")
            if _tool:
                _key = (str(_tool), str(err_type))
                _deny = getattr(agent, "_deny_counts", {}) or {}
                _deny[_key] = _deny.get(_key, 0) + 1
                agent._deny_counts = _deny
                if _deny[_key] >= 3:
                    # 2026-08-08 小欧 机制冲突修复: 场景F(双阈值 count==2/3/4 纠偏)已注入纠偏消息且LLM尚未调整
                    #   (_warned_same_tool_loop>0)时, 本处累计口径让位给纠偏, 给LLM调整机会,
                    #   避免"纠偏刚注入即被deny_counts判FAILED"致纠偏形同虚设(COM_03真实场景: 连续3次
                    #   delete被R6拦截, step=22纠偏与FAILED同轮触发, 响应仅6字"任务执行失败")。
                    #   连续同签名死循环由场景F count>=5(第5次)硬终止兜底; 非连续死胡同(签名变化重置标记)
                    #   仍由本处累计≥3次拦截, 语义不退化。 — 小欧 2026-08-08
                    if not getattr(agent, "_warned_same_tool_loop", 0):
                        set_failed(agent, f"工具 {_tool} 被反复{err_type}(≥3次), LLM陷入死胡同, 停止循环")
        else:
            set_failed(agent, error_msg)
    else:
        # 正常成功执行(无 error/retrying/final, 且确为 action 执行了工具): 重置该工具的拒绝计数
        # — 北京老陈 2026-07-13: 同工具成功后证明其未陷死胡同, 旧计数清零, 避免长会话里一次早已
        # 解决的历史拒绝在后续被误累计触发 FAILED(增强不退化, 逻辑无漏洞)。answer/final 步不重置。
        if llm_response.get("type") == "action":
            _tool = llm_response.get("tool_name", "")
            if _tool:
                _deny = getattr(agent, "_deny_counts", {}) or {}
                _deny.pop((str(_tool), "user_rejected"), None)
                _deny.pop((str(_tool), "blocked"), None)
                agent._deny_counts = _deny
