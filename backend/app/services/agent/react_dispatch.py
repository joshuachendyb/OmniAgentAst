
# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-09-05 小健 8.4拆分(react_cycle.py拆四): 提取 _dispatch_handler(原行288-389, 含函数体内状态推断块337-389),
#   逐字复制只改import — 按type分派handler, 基于 event type 推断状态(物理上状态推断块在函数体内不可切分,整体随迁)
# 2026-09-06 小欧 4B(5.7): handle_answer/handle_action 已纯函数化返 dict{events,result} →
#   本层消费改 verdict=await handler + for verdict["events"] 逐条 yield; seen_types/last_error/final 逐条收集
#   与下方终态推断块逐行保留, 语义无退化(4A=T4A, 4B=T4B, 5.7调度仍为 async generator 逐条外发) - 小欧-2026-09-06
# 2026-09-06 小欧 4C(5.8.1): 返 list 收口 — _dispatch_events 收集循环(双兼容 dict/列表源), 状态推断块逐行
#   保留, return _dispatch_events 置于状态推断之后(终态声明先执行, 与现状时序一致); 消费端 5.8.2 同 commit
#   await 拿 list, react_step L461 async-for 对 list 即崩, 5.8.1-5.8.5 同 commit 齐发(文档[6]5.8缺陷D1) - 小欧-2026-09-06
# 2026-09-06 小欧 方案C三堂会审缺陷3修复(独立user_rejected适配, 北京老陈裁定"拒绝≠error"):
#   独立 type="user_rejected" 后, 拒绝事件不再是 type="error"(error_type=user_rejected), seen_types 无 "error"
#   → 状态推断落 else"成功重置"分支: 拒绝计数既不累计(≥3次FAILED防死胡同机制失效) 反将已计数清零(语义错误)。
#   [修复] ①seen_types 收集新增 _EV_DENIED("user_rejected"), error/user_rejected 事件统一入 last_denial_event
#   槽(取轮内最后一条, 与旧"每次拒绝仅计一条"语义一致); ②推断分支改 `_EV_ERROR in seen_types or _EV_DENIED
#   in seen_types`, err_type 按 event.type 判 user_rejected, 复用原 _RECOVERABLE_ERRORS 计数通道((tool,type)
#   累计≥3→FAILED); ③blocked/timeout 仍走 error 分支行为不变; else"成功重置"仅真成功可达 — 小欧-2026-09-06
# 2026-09-06 小欧 BUG-2 计数错键修复(问题挖掘文档六.6.2/6.3): ①计数 tool_name 优先读事件级 _kw["tool_name"]
#   (拒绝事件自 2026-09-06 起带被拒工具名), 回退 llm_response.tool_name(旧事件/单工具兼容)——多工具并行拒绝
#   精确分键, 不再全落主工具名下; ②成功重置改按本轮 LLM 实际发出工具集清桶(fc_context.tool_calls→function.name,
#   与 llm_response_builder.py:41 同源; 顶层无 tool_calls, 候选diff字段已按真实结构核验修正),
#   不再误用主工具名清错桶——被拒工具计数跨轮永不归零的病根消除 — 小欧-2026-09-06
# 2026-09-17 小欧 - 统一拒绝事件 type="rejected": ①行78 _EV_DENIED 改为 "rejected"(原 "user_rejected"); ②行160 _deny.pop 改为 "rejected"(原 "user_rejected") - 小欧-2026-09-17
# 2026-09-17 小欧 会审V3整改(#12/#15): ①失败文案 err_type 英文→中文映射("工具 X 被反复拒绝/拦截/超时"); ②成功重置清桶补 pop(("timeout")) 旧键 - 小欧-2026-09-17
# 2026-09-17 小欧 会审V3整改(#1/#2) 复核三遍修正: ①(#1)≥3次拒绝终态原因丢失——set_failed 同步写 agent._last_error
#   (统一 rejected 后 blocked/timeout 不再走 type="error", step_emitter 不记录, 守卫读空→终态退化成通用文案);
#   ②(#2)拒绝计数桶合并——计数键按 reject_type 细分(safety/sandbox/user/timeout 分桶, 防"拦截1+超时1+拒绝1"合并误判≥3),
#   成功重置清桶遍历 _DENY_KEY_TYPES 全量 6 键防残留; _ERR_CN 扩 safety/sandbox/user 中文映射 — 小欧-2026-09-17

"""react_dispatch — 类型分派 + 状态推断

按type分派handler(action/answer), 依事件流(seen_types)推断终态/可恢复错误/拒绝计数。

8.4拆分自 react_cycle.py(老名消亡) — 小健 2026-09-05
"""

import time
from typing import Dict, List
from app.logger import log_and_print
from app.services.agent.status_table import AgentStatus, set_status, set_failed, set_cancelled, set_completed
from app.services.agent.handlers import (
    handle_action, handle_answer,
)
from app.services.agent.react_inference import _RECOVERABLE_ERRORS

# 2026-09-17 小欧 会审V3整改(#2): 全量拒绝类键清单——rejected/blocked/timeout 为旧 error 通道时代键(兼容保留),
#   safety/sandbox/user 为统一 rejected 事件的 reject_type 取值; 成功清桶需遍历全清防残留 — 小欧-2026-09-17
_DENY_KEY_TYPES = ("rejected", "blocked", "timeout", "safety", "sandbox", "user")

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

    _EV_FINAL, _EV_RETRY, _EV_ERROR, _EV_DENIED = "final", "retrying", "error", "rejected"
    # 2026-09-17 小欧 会审V3(#12): 失败文案 err_type 英文→中文映射(用户可见, 原样透出 "rejected"/"blocked"/"timeout" 生硬);
    #   #2整改: 分桶的拒绝类型扩展——rejected 的 reject_type(safety/sandbox/user/timeout) 直接入文案 — 小欧-2026-09-17
    _ERR_CN: Dict[str, str] = {
        "rejected": "拒绝", "blocked": "拦截", "timeout": "超时",
        "safety": "安全拦截", "sandbox": "沙箱拦截", "user": "用户拒绝",
    }
    seen_types = set()
    last_denial_event = None
    final_event = None
    # 4C(5.8.1): 返 list — 收集 _dispatch_events, 状态推断块逐行保留, 循环尾 return(5.8.2 消费 await 拿 list 同 commit) — 小欧-2026-09-06
    verdict = await handler  # handler 为 handle_action/handle_answer(agent, llm_response) 的 coroutine 结果
    _dispatch_events: List = []
    for event in (verdict.get("events", []) if isinstance(verdict, dict) else verdict):
        seen_types.add(event.type)
        # 方案C(2026-09-06 小欧): error/独立 user_rejected 统一入 last_denial_event 槽(轮内最后一条,
        #   与旧"拒绝/拦截每次仅计一条"语义一致); 独立 type 后 user_rejected 不再是 error 的子类型 — 小欧-2026-09-06
        if event.type in (_EV_ERROR, _EV_DENIED):
            last_denial_event = event
        elif event.type == _EV_FINAL:
            final_event = event
        _dispatch_events.append(event)

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
    elif _EV_ERROR in seen_types or _EV_DENIED in seen_types:
        # 无 final → 可恢复拒绝/拦截(blocked/user_rejected/timeout, 循环继续)或原子异常(旧数据)
        error_event = last_denial_event
        _kw = getattr(error_event, "_kwargs", {}) or {}
        # 方案C(2026-09-06 小欧): 独立拒绝事件 type 即 err_type(旧 error 型时代由 error_type 承载, 迁移映射);
        #   阻塞/超时仍读 error_type(独立拒绝事件无 error_type/severity, 与北京老陈裁定一致) — 小欧-2026-09-06
        if error_event.type == _EV_DENIED:
            err_type = _EV_DENIED
        else:
            err_type = _kw.get("error_type", "")
        error_msg = error_event.get_content() if hasattr(error_event, 'get_content') else ""
        if err_type in _RECOVERABLE_ERRORS:
            # 拒绝/拦截是可恢复的(拒绝≠失败, 符合人类认知): 不置终态, 反馈已进LLM历史,
            # 主循环 EXECUTING→THINKING 让LLM换工具。 — 小欧 2026-07-13
            # 计数按"同工具+同类型错误"累计(北京老陈 2026-07-13): 不同工具被拒不限次数
            # (往往是参数问题, 换工具/换参数即可); 仅同一工具同一类拒绝累计≥3次才说明LLM
            # 陷入死胡同, 必须停止 loop → FAILED。故用 per-(tool,type) 字典。
            # 工具名缺失时不累计(无法分键, 避免空名合并误累计), 保持可恢复回THINKING, 不误杀。
            # BUG-2修复(2026-09-06 小欧): tool_name 优先取事件级(被拒工具精确分键), 回退 llm_response(单工具/旧事件兼容) — 小欧-2026-09-06
            _tool = _kw.get("tool_name", "") or llm_response.get("tool_name", "")
            if _tool:
                # #2整改(2026-09-17 小欧): 分桶键按 reject_type 细分(rejected 事件带 safety/sandbox/user/timeout),
                #   杜绝不同拒绝原因合并计一桶(safety拦截+timeout超时+user拒绝 原同落 "rejected" → 误判≥3 FAILED) — 小欧-2026-09-17
                _rk = _kw.get("reject_type", "") or err_type
                _key = (str(_tool), str(_rk))
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
                        _fail_msg = f"工具 {_tool} 被累计{_ERR_CN.get(_rk, _rk)}(终身≥3次, 非连续), LLM陷入死胡同, 停止循环"  # 2026-09-24 小欧: “反复”改“累计”, 与per-(tool,type)终身累计实现对齐(P9-03/04三弹各跨40+分钟实证)
                        set_failed(agent, _fail_msg)
                        # #1整改(2026-09-17 小欧): set_failed 同步写 _last_error, 供 agent_runner 守卫取回终态原因。
                        #   原 blocked/timeout 走 type="error" 在 step_emitter:66 记录 _last_error; 统一 rejected 后不再触发, 原因丢失 — 小欧-2026-09-17
                        agent._last_error = (str(_rk), _fail_msg)
        else:
            set_failed(agent, error_msg)
    else:
        # 正常成功执行(无 error/retrying/final, 且确为 action 执行了工具): 重置该工具的拒绝计数
        # — 北京老陈 2026-07-13: 同工具成功后证明其未陷死胡同, 旧计数清零, 避免长会话里一次早已
        # 解决的历史拒绝在后续被误累计触发 FAILED(增强不退化, 逻辑无漏洞)。answer/final 步不重置。
        if llm_response.get("type") == "action":
            # BUG-2修复(2026-09-06 小欧, 问题挖掘文档六.6.3): 成功轮按本轮 LLM 实际发出的工具调用清桶
            #   (并行多工具全清, 不再误用主工具名清错桶)——源=fc_context.tool_calls(OpenAI原生, 函数名在
            #   function.name, 与 llm_response_builder.py:41 同源; 顶层无 tool_calls, 候选diff字段按真实结构修正);
            #   无调用条目时回退 tool_name(旧格式兼容, 不空清不误清) — 小欧-2026-09-06
            _tc_list = (llm_response.get("fc_context") or {}).get("tool_calls") or []
            _tools = [tc.get("function", {}).get("name", "") for tc in _tc_list
                      if tc.get("function", {}).get("name")]
            if not _tools and llm_response.get("tool_name"):
                _tools = [llm_response.get("tool_name")]
            if _tools:
                _deny = getattr(agent, "_deny_counts", {}) or {}
                for _t in _tools:
                    # #2整改(2026-09-17 小欧): 成功重置清桶遍历全量键类型(rejected/blocked/timeout 旧 error 时代键
                    #   + safety/sandbox/user reject_type 键), 杜绝新旧键残留漂移 — 小欧-2026-09-17
                    for _dt in _DENY_KEY_TYPES:
                        _deny.pop((str(_t), _dt), None)
                agent._deny_counts = _deny

    # 4C(5.8.1): return _dispatch_events 置于状态推断之后(终态声明在主循环 LLM 轮内先行, 时序与现状一致) — 小欧-2026-09-06
    return _dispatch_events
