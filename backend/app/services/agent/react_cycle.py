
# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-01 chendyg 状态集中管理重构v2
#   - 状态用 status_table, 数据 handler 自己写
#   - _dispatch_handler 基于 event type 推断状态
#   - handler 保留 add_observation/add_assistant_message, 不绕路
# 2026-07-17 小沈 FC重命名: import/LLMResponseError同步
# 2026-07-17 小欧 B3扩展+修正: 检测reasoning-only空转并软引导(修正has_tool_results屏蔽使已调工具后仍可警告); 改add_observation→add_assistant_message(避免空tool_call_id孤立tool消息致LLM参数不合法, 参照edca06261昨天修正); warning去具体工具名
# 2026-07-18 小欧 #27 fix: 删llm_client._cancelled死分支
# 2026-07-18 小欧 #28 fix: 更新docstring状态推断规则
# 2026-07-18 小欧 #29 fix: 抽取_EV_FINAL/_EV_RETRY/_EV_ERROR常量
# 2026-07-18 小欧 FinalStep多态自包含终态重构:
#   【病根】原react_cycle中取消/截断/无终态等路径用MetaStep(cancelled)表示终态,
#          与answer_handler的FinalStep(completed)不一致; _dispatch_handler基于event.type位置推断终态,
#          逻辑分散且易遗漏(如空响应路径set_failed但不产出终态step)。
#   【思路】统一终态语义: 所有终态路径改用FinalStep(outcome=xxx),
#          _dispatch_handler改为outcome驱动终态声明(不依赖位置/类型); 可恢复错误仍用ErrorStep。
#   【改法】①场景B/C/D/循环结束无终态: MetaStep(cancelled)→FinalStep(outcome="cancelled")
#          ②_dispatch_handler: 从位置驱动改为outcome驱动(set_failed/set_cancelled/set_completed)
#          ③可恢复错误(ErrorStep)和可恢复拒绝(_RECOVERABLE_ERRORS)保持不变
# 2026-07-18 - 小欧 - 修复#7 _dispatch_handler 用循环内单独捕获的 final_event 读 outcome, 不取末事件last_event(末事件未必是final,脆弱); 修复#9 stale注释 MetaStep(cancelled)→FinalStep(outcome="cancelled")
# 2026-07-18 - 小欧 - F1 fix: 可恢复异常从外层except移入per-step内层try, continue回卷while真重试, 不再误标failed
# 2026-07-18 - 小欧 - F3 fix: _should_retry_truncated_tool O(n²)嵌套循环→单遍O(n)
# 2026-07-19 小欧 控制台打印修复: if thought→if thought or reasoning(空content有reasoning的action step也能输出)
# 2026-07-19 小欧 推理空转不持久化: _finalize_cycle(finally出口)开头直调agent.message_builder.pop_temp_messages()弹掉残留标记推理再持久化; 落点单一收口(KISS-DIRECT), 生产直调无防御守卫, 测试mock缺message_builder属测试缺陷
# 2026-07-19 小欧 R1优化: B3空转警告(场景C reasoning-only子分支)改幂等注入+复用_temp_reasoning标记收口; 已存在相同标记消息则跳过,杜绝连续空转累积重复警告(history堆积/持久化残留); 终态统一由pop_temp_messages弹掉,零新机制(DRY/KISS); 正常answer无工具分支(else)不变仍持久化
# 2026-07-22 小欧 LLM 响应后提取 usage.total_tokens → message_builder.last_total_tokens，供下轮增量裁剪用
# 2026-07-22 小欧 usage 扩展: 三字段(prompt/completion/total)累加 accumulated_usage; emit MetaStep(type="usage") 逐次报告本次消耗
# 2026-07-22 小欧 MetaStep usage: 从 **_usage 解包改为手动三字段，精确控制输出
# 2026-07-23 小欧 - log_and_print统一: 3处print()替换为log_and_print()(Thought/Error/Cancel控制台输出), 导入log_and_print
# 2026-08-08 小欧 相同工具调用死循环检测(场景F)新增:
#   【病根】P6_01(file_not_found)超时根因: LLM连续40+步逐字重复同一Thought并反复调用完全相同工具+相同参数
#          (writetext写同一diff_tool.py), 每次工具均success, 现有_consecutive_reasoning_only仅拦"纯推理无工具
#          调用"空转, 本模式漏检, 致死循环直抵max_steps=10000。
#   【方案】_tool_call_signature计算action调用签名(含并行pending); _check_same_tool_loop返回int连续计数(count=第N次),
#           双阈值: count==3(_SAME_TOOL_WARN_ROUNDS)注入assistant role纠偏消息尝试唤醒, count>=5硬终止failed;
#           签名变化重置count=1+清纠偏标记; 正常任务签名各异零误伤, 增强不退化。
# 2026-08-08 小欧 v1.6 双阈值实施: 单阈值(bool终止)升级为双阈值(3纠偏+5硬终止), 新增_warn_same_tool_loop
# 2026-08-08 小欧 v1.7 双阈值调整(北京老陈 2026-08-08 指示"第2次就发纠偏; 2/3/4次发, >=5结束"):
#   - 纠偏: 第2次(count==2)即发第1条(原第3次), 第2/3/4次各发1条共3条(原第3/4次共2条)
#   - 硬终止: count>=5(原count>5第6次, 收紧回第5次)
#   - 实现: _SAME_TOOL_WARN_ROUNDS 3→2, _SAME_TOOL_WARN_MAX 2→3; 判定改 _SAME_TOOL_WARN_ROUNDS<=cnt<5 区间发纠偏,
#     cnt>=5 硬终止; _warned_same_tool_loop 为 int 计数(发纠偏条数, 上限_SAME_TOOL_WARN_MAX),
#     重置/初始化点(签名变化/非action/initialize_run_state)由 False 改 0;
#     deny_counts 让位判断 not _warned_same_tool_loop 真值语义不变(int>0即已发)


"""
run_react_cycle — ReAct 循环核心（薄调度）

职责: 循环调度 + 类型分派 + 状态推断，不含业务逻辑
业务逻辑在 handlers/ 目录
"""

import asyncio
import json
import time
from typing import Any, Dict, Optional, AsyncGenerator

from app.logger import logger, log_and_print
from app.services.llm.error_classifier import SystemErrorClassifier
from app.logger.prompt_logger import get_prompt_logger
from app.config import get_config
from app.services.agent.steps import ChunkStep, MetaStep, ObservationStep, ErrorStep, FinalStep
from app.services.agent.status_table import AgentStatus, set_status, set_failed, set_completed, set_cancelled
from app.services.agent.initialize_run_state import initialize_run_state
from app.services.agent.handlers import (
    handle_action, handle_answer,
)
from app.services.agent.llm_stream import call_llm_with_fallback
from app.services.agent.tool_cache_manager import get_openai_tools

_MAX_CONSECUTIVE_TRUNCATIONS = 3

# 相同工具调用死循环防御(双阈值纠偏/硬终止): LLM连续调用完全相同工具+相同参数时,
# 第2次(count==2)、第3次(count==3)、第4次(count==4)各注入一条assistant role纠偏消息尝试唤醒调整(共3条);
# count>=5(第5次)判定死循环硬终止。
# 2026-08-08 - 小欧 - P6_01(file_not_found)超时根因: LLM连续40+步逐字重复同一Thought并反复调用
#   相同writetext(diff_tool.py), 每次均success, 现有_consecutive_reasoning_only仅拦"纯推理无工具"
#   空转, 本模式漏检, 致死循环直抵max_steps=10000。v1.6升级为由单阈值硬终止改为双阈值(纠偏+硬终止)。
# v1.7(北京老陈 2026-08-08): 纠偏起点提前——第2次(count==2)就发第1条纠偏(原第3次), 第2/3/4次共发3条,
#   硬终止 count>=5(原count>5第6次)收紧; 给LLM尽早调整机会(第2次发现完全相同即提醒)。
_SAME_TOOL_WARN_ROUNDS = 2             # 纠偏起点阈值: count==2(第2次相同调用)注入第1条警告 — 小欧 2026-08-08
_SAME_TOOL_WARN_MAX = 3                # 纠偏最大条数: 第2/3/4次共3条 — 小欧 2026-08-08
_MAX_CONSECUTIVE_SAME_TOOL_CALLS = 5   # 硬终止阈值: count>=5(第5次相同调用)时硬终止 — 小欧 2026-08-08

# 可恢复的拒绝/拦截错误: 拒绝≠失败(符合人类认知, 助手应换工具继续) — 小欧 2026-07-13
# 反馈已写入LLM历史(_add_denial_feedback), 循环回THINKING由主循环 EXECUTING→THINKING 处理;
# 仅当"同一工具+同类型错误"累计>=3次才置 FAILED(说明LLM陷入死胡同) — 北京老陈 2026-07-13。
_RECOVERABLE_ERRORS = {"user_rejected", "blocked"}


def handle_react_error(agent, error, step):
    """统一处理ReAct循环中的错误 — 只创建 ErrorStep，不设状态 — chendyg 2026-07-01
    小欧 2026-07-13: 删 recoverable（终态由 ErrorStep 表示，不再用 flag 区分可恢复）"""
    error_type = SystemErrorClassifier.classify_error(error).name.lower()
    logger.error(f"[ErrorHandler] 错误类型={error_type}: {error}")
    return ErrorStep(step=step, error_type=error_type, error_message=str(error))


def _is_recoverable_error(error) -> bool:
    """判断错误是否可恢复（FC格式错误/网络错误/超时） — chendyg 2026-07-01"""
    try:
        from app.services.llm.core import LLMResponseError
        if isinstance(error, LLMResponseError):
            return True
    except ImportError:
        pass
    if isinstance(error, asyncio.TimeoutError):
        return True
    try:
        import httpx
        if isinstance(error, (
            httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError,
            httpx.ProxyError, httpx.TooManyRedirects,
        )):
            return True
    except ImportError:
        pass
    return False


def _should_retry_truncated_tool(agent, llm_response: Dict) -> bool:
    """检测LLM应答是否因输出截断导致工具调用遗漏
    
    条件:
    1. 返回类型是answer
    2. 内容很短(<500字,可能截断)
    3. 对话历史中存在带tool_calls的assistant消息(LLM之前处于工具模式)
    4. 该tool_call**未被成功执行**(无对应tool角色响应) — P0-2修复 2026-06-23 小欧
    E-3修复 2026-06-25 小欧: 阈值100→500,覆盖更多截断场景
    """
    if llm_response.get("type") != "answer":
        return False
    content = llm_response.get("content", "")
    if not content or len(content) > 500:
        return False
    history = agent.message_builder.conversation_history
    _seen_response = False
    for msg in reversed(history):
        role = msg.get("role")
        if role in ("tool", "observation"):
            _seen_response = True
        elif role == "assistant" and msg.get("tool_calls"):
            return not _seen_response
    return False


def _tool_call_signature(llm_response: Dict) -> str:
    """计算action响应的工具调用签名(全部调用含并行) — 小欧 2026-08-08
    用于相同工具调用死循环检测: 签名=tool_name+规范化tool_params的排序JSON,
    连续多步完全相同签名即判死循环。sort_keys保证字典顺序无关, 参数内容变化即签名变化。"""
    calls = []
    _primary = (llm_response.get("tool_name", "") or "",
                llm_response.get("tool_params") or {})
    calls.append(_primary)
    for _pc in llm_response.get("_pending_calls") or []:
        calls.append((_pc.get("tool_name", "") or "", _pc.get("tool_params") or {}))
    return json.dumps(calls, sort_keys=True, ensure_ascii=False)


def _check_same_tool_loop(agent, llm_response: Dict) -> int:
    """相同工具调用死循环检测(计数) — 小欧 2026-08-08
    count语义="第几continuous相同调用": 首个相同签名(count基准起始)。
    无上次签名(首调用)计count=1; 与上轮签名相同则count+1; 签名变化则重置count=1并清纠偏计数。
    返回int连续计数供调用方分支(count==2/3/4纠偏 / count>=5硬终止)。action语义下调用; 非action由调用方归零。"""
    _sig = _tool_call_signature(llm_response)
    if _sig and _sig == getattr(agent, "_last_tool_call_sig", None):
        agent._consecutive_same_tool_calls = getattr(agent, "_consecutive_same_tool_calls", 0) + 1
    else:
        agent._consecutive_same_tool_calls = 1      # 新签名起点=1, 标记同步重置 — 小欧 2026-08-08
        agent._warned_same_tool_loop = 0            # int计数(发纠偏次数)重置 — 小欧 2026-08-08
    agent._last_tool_call_sig = _sig
    return agent._consecutive_same_tool_calls


def _warn_same_tool_loop(agent, llm_response: Dict, count: int) -> None:
    """注入纠偏提醒(带_temp_same_tool_warn标记, 终态统一清理) — 小欧 2026-08-08
    连续相同调用达count==2/3/4(第2/3/4次)时各注入一条assistant role观察消息尝试唤醒LLM调整;
    最多注入3条(第2/3/4次, _warned_same_tool_loop为int计数), 标记供pop_temp_messages
    弹掉防止持久化污染。原布尔幂等→int计数(北京老陈 2026-08-08 指示"第2次就发纠偏")。"""
    if getattr(agent, "_warned_same_tool_loop", 0) >= _SAME_TOOL_WARN_MAX:
        return  # 最多警告3次(第2/3/4次) — 小欧 2026-08-08
    _tool = llm_response.get("tool_name", "") or ""
    _sig = _tool_call_signature(llm_response)
    obs_text = (
        f"[Observation] 警告: 你刚才连续调用了相同的工具 {_tool} 且参数**完全相同**, "
        f"已连续 {count} 次, 签名={_sig[:80]}... "
        f"结果本质相同, 可能陷入思维循环。请检查: 1) 是否获得了新信息; 2) 是否需要更换策略。"
    )
    agent.message_builder.conversation_history.append({
        "role": "assistant",
        "content": obs_text,
        "_temp_same_tool_warn": True,
    })
    agent._warned_same_tool_loop = getattr(agent, "_warned_same_tool_loop", 0) + 1
    logger.info(f"[run_react_cycle] LLM连续{count}次调用相同工具 {_tool}, 注入纠偏警告(第{agent._warned_same_tool_loop}条)")
    log_and_print(f"{time.strftime('%H:%M:%S')} [Loop] step={agent.llm_call_count} same tool warn={_tool}")


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
        # 无 final → 可恢复错误(blocked/user_rejected, 循环继续)或原子异常(旧数据)
        error_event = last_error_event
        err_type = getattr(error_event, "error_type", "")
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
                    # 2026-08-08 小欧 机制冲突修复: 场景F(双阈值 count==3 纠偏)已注入纠偏消息且LLM尚未调整
                    #   (_warned_same_tool_loop>0)时, 本处累计口径让位给纠偏, 给LLM调整机会,
                    #   避免"纠偏刚注入即被deny_counts判FAILED"致纠偏形同虚设(COM_03真实场景: 连续3次
                    #   delete被R6拦截, step=22纠偏与FAILED同轮触发, 响应仅6字"任务执行失败")。
                    #   连续同签名死循环由场景F count>5(第6次)硬终止兜底; 非连续死胡同(签名变化重置标记)
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


def _finalize_cycle(agent):
    """循环后收尾: 状态回调+任务追踪 — 小健 2026-06-17 从finally提取"""
    agent.message_builder.pop_temp_messages()  # 小欧 2026-07-19 安全网: 清除残留标记推理再持久化
    agent._on_after_loop()
    agent._step_emitter.complete_task(agent.status == AgentStatus.COMPLETED)


async def _process_single_step(agent, chunk_buffer) -> AsyncGenerator:
    """单步ReAct调度: LLM调用→响应处理→分发 — 小欧 2026-06-25 / 小欧 2026-07-09 加分区注释"""

    # ── Phase 1: LLM 调用准备 ──────────────────────────────────
    agent.llm_call_count += 1
    agent.message_builder.trim_history()  # 唯一裁剪入口 — 小欧 2026-07-01
    messages = agent.message_builder.prepare_messages_for_llm()
    openai_tools = get_openai_tools(agent)

    logger.info(f"[LLM] 调用#{agent.llm_call_count}, messages={len(messages)}, tools={len(openai_tools)}, model={getattr(agent.llm_client, 'model', '?')}")

    prompt_logger = get_prompt_logger()
    prompt_logger.log_llm_call(
        round_number=agent.llm_call_count,
        messages=messages,
        model=getattr(agent.llm_client, 'model', 'unknown'),
        provider=getattr(agent.llm_client, 'provider', 'unknown'),
        call_type="tools",
        tools=openai_tools,
    )

    if not openai_tools:
        logger.error("[_process_single_step] 无可用工具")

    # ── Phase 2: LLM 流式调用 ──────────────────────────────────
    llm_response = None
    async for chunk_or_response in call_llm_with_fallback(agent, messages, openai_tools):
        chunk_type, chunk_data = chunk_or_response

        if chunk_type == "chunk":
            content = chunk_data.content if hasattr(chunk_data, 'content') else str(chunk_data)
            is_reasoning = getattr(chunk_data, 'is_reasoning', False)
            chunk_buffer.append(content)
            chunk_step = ChunkStep(
                step=agent.llm_call_count,
                content=content,
                is_reasoning=is_reasoning,
            )
            yield agent._step_emitter.emit(chunk_step)
        elif chunk_type == "response":
            llm_response = chunk_data
            chunk_buffer.clear()
            # LLM usage 处理: 裁剪触发 + 累积消耗 + 逐次报告 — 小欧 2026-07-22
            _usage = llm_response.get("usage") if isinstance(llm_response, dict) else None
            if _usage and isinstance(_usage, dict):
                # 裁剪触发: 记录精确 total_tokens 供下轮增量裁剪
                _tt = _usage.get("total_tokens")
                if _tt is not None:
                    agent.message_builder.last_total_tokens = int(_tt)
                # 累积消耗: 三个字段逐次累加
                for _k in ("prompt_tokens", "completion_tokens", "total_tokens"):
                    _v = _usage.get(_k)
                    if _v is not None:
                        agent.accumulated_usage[_k] += int(_v)
                # 逐次报告: emit MetaStep(type="usage") 带本次 usage 三个值
                _usage_step = MetaStep(
                    step=agent.llm_call_count,
                    type="usage",
                    content="",
                    prompt_tokens=_usage.get("prompt_tokens"),
                    completion_tokens=_usage.get("completion_tokens"),
                    total_tokens=_usage.get("total_tokens"),
                )
                yield agent._step_emitter.emit(_usage_step)

    # ── Phase 3: 响应分发 ──────────────────────────────────────
    set_status(agent, AgentStatus.EXECUTING)

    step = agent.llm_call_count

    # ── 场景A: 空响应 — LLM未返回有效数据 ──────────────────────
    if not llm_response or not isinstance(llm_response, dict):
        logger.error(f"[run_react_cycle] _call_llm返回无效响应: {type(llm_response)}")
        log_and_print(f"{time.strftime('%H:%M:%S')} [Error] step={step}, empty_response")  # 小欧 2026-07-02 控制台
        set_failed(agent, "LLM返回空响应，任务终止")
        yield agent._step_emitter.emit(ErrorStep(
            step=step, error_type="empty_response",
            error_message="LLM返回空响应，任务终止"  # Bug1: 不误导LLM(agent已fail),只陈述事实 — 小欧 2026-07-23
        ))
        return

    # ── 场景C: LLM直接回答/纯推理 → 注入复核warning（不重试）— 小健 2026-07-03
    # 设计: fall through到正常分发, warning进history,
    # 下轮循环LLM会看到这条observation并重新思考 — 小欧 2026-07-09
    # 2026-07-17 - 小欧 - 扩展: 原仅检content(有content的answer), reasoning-only(空转)被漏检;
    #   现也检reasoning, 且reasoning-only不受has_tool_results限制(否则已调工具后空转仍沉默, 恰是task-2ffbc517场景);
    #   与answer_handler的硬终止(A增强版)互补: 本处软引导, 引导失败则由A硬终止兜底。
    if (llm_response.get("type") == "answer"
            and (llm_response.get("content") or llm_response.get("reasoning"))):
        _content = llm_response.get("content", "") or ""
        _reasoning = llm_response.get("reasoning", "") or ""
        if not _content:
            # reasoning-only(纯推理无工具无答案空转): 必警告, 不受has_tool_results限制
            logger.warning(f"[B3] LLM返回reasoning-only(空转)未调用工具(step={step})")
            obs_text = ("[Observation] 警告: 你当前仅在推理未调用工具, 若已掌握所需信息请直接给出最终答案, "
                        "否则应调用工具获取信息, 避免空转")
            # 小欧 R1优化(2026-07-19): B3空转警告幂等注入+复用_temp_reasoning标记收口,
            #   已存在相同标记消息则跳过,杜绝连续空转累积重复警告(history堆积/持久化残留);
            #   终态由_finalize_cycle.pop_temp_messages统一弹掉,符合"空转不持久化"设计,零新机制(DRY/KISS)
            _hist = agent.message_builder.conversation_history
            if not any(m.get("role") == "assistant" and m.get("_temp_reasoning") and m.get("content") == obs_text
                       for m in _hist):
                _hist.append({
                    "role": "assistant",
                    "content": obs_text,
                    "reasoning": "",
                    "reasoning_content": "",
                    "_temp_reasoning": True,
                })
        else:
            has_tool_results = any(
                msg.get("role") == "tool"
                for msg in agent.message_builder.conversation_history
            )
            if not has_tool_results:
                logger.warning(f"[B3] LLM返回answer但未调用任何工具(step={step})")
                obs_text = "[Observation] 警告: 你未调用任何工具-->必须复核3遍用户任务:[1]问答任务补充说明;[2] 多步任务就继续调用工具"
                agent.message_builder.add_assistant_message(obs_text)  # 2026-07-17 - 小欧 - 同reasoning-only分支: 改add_assistant_message避免孤立tool消息致LLM参数不合法

    # ── 场景D: 输出截断重试 — 检测preamble截断,注入重试observation ── 小健 2026-07-03
    if _should_retry_truncated_tool(agent, llm_response):
        content = llm_response.get("content", "")
        agent._consecutive_truncations = getattr(agent, '_consecutive_truncations', 0) + 1
        logger.warning(f"[run_react_cycle] 检测到LLM输出截断(step={step}, 连续第{agent._consecutive_truncations}次, content={content[:50]})")

        if agent._consecutive_truncations >= _MAX_CONSECUTIVE_TRUNCATIONS:
            logger.error(f"[run_react_cycle] LLM连续截断{_MAX_CONSECUTIVE_TRUNCATIONS}次, 停止重试")
            log_and_print(f"{time.strftime('%H:%M:%S')} [Cancel] step={step}, consecutive_truncation")  # 小欧 2026-07-02 控制台
            yield agent._step_emitter.emit(FinalStep(
                step=step,
                response=f"LLM连续{_MAX_CONSECUTIVE_TRUNCATIONS}次输出截断",
                outcome="cancelled",  # 小欧 2026-07-18: MetaStep→FinalStep, 连续截断终态统一
            ))
            set_cancelled(agent)
            return

        obs_text = "[Observation] 工具调用输出不完整，请重新调用该工具并补充完整参数"
        _retry_tc_id = ""
        history = agent.message_builder.conversation_history
        for i in range(len(history) - 1, -1, -1):
            msg = history[i]
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                _retry_tc_id = msg["tool_calls"][-1].get("id", "")
                break
        agent.message_builder.add_observation(
            obs_text, {"tool_call_id": _retry_tc_id, "tool_calls": [], "llm_content": content},
        )
        yield agent._step_emitter.emit(ObservationStep(
            step=step,
            llm_data=[{"summary": "LLM工具调用输出截断", "action": {}, "status": {"exec_code": "error", "message": obs_text}}],
            tool_result={},
        ))
        return

# ── 场景F: 相同工具调用死循环检测(双阈值纠偏/硬终止) ──────────
    # 2026-08-08 - 小欧 - P6_01(file_not_found)超时根因修复:
    #   【病根】LLM连续40+步逐字重复同一Thought并反复调用完全相同工具+相同参数(writetext写同一diff_tool.py),
    #          每次工具执行均success, 现有_consecutive_reasoning_only仅拦"纯推理无工具调用"空转, 本模式漏检,
    #          致死循环直抵max_steps=10000(约40+分钟)。
    #   【方案】对action响应计算工具调用签名(tool_name+规范化tool_params, 含并行pending),
    #          _check_same_tool_loop返回int连续计数(count=第N次), 双阈值:
    #          count==2/3/4(_SAME_TOOL_WARN_ROUNDS起)各注入assistant role纠偏消息(尝试唤醒调整, 最多3条);
    #          count>=5(_MAX_CONSECUTIVE_SAME_TOOL_CALLS)判定死循环硬终止failed。
    #          正常任务LLM每轮工具/参数各异或需新信息, 签名必不同, count重置, 零误伤(增强不退化)。
    if llm_response.get("type") == "action":
        _cnt = _check_same_tool_loop(agent, llm_response)
        if _SAME_TOOL_WARN_ROUNDS <= _cnt < _MAX_CONSECUTIVE_SAME_TOOL_CALLS:
            # count==2/3/4: 各发1条纠偏(共3条, 内部幂等上限_SAME_TOOL_WARN_MAX) — 小欧 2026-08-08
            _warn_same_tool_loop(agent, llm_response, _cnt)
        elif _cnt >= _MAX_CONSECUTIVE_SAME_TOOL_CALLS:    # count>=5(第5次相同调用): 硬终止 — 小欧 2026-08-08
            logger.warning(f"[run_react_cycle] LLM连续{_cnt}步调用相同工具(step={step}), 判定死循环, 终止")
            log_and_print(f"{time.strftime('%H:%M:%S')} [Cancel] step={step}, same_tool_loop")  # 小欧 2026-08-08 控制台
            set_failed(agent, f"模型连续{_cnt}步重复调用相同工具, 疑似死循环, 任务终止")
            yield agent._step_emitter.emit(FinalStep(
                step=step,
                response="模型反复调用相同工具未取得进展，任务已终止（疑似死循环）",
                thought=llm_response.get("reasoning", "") or llm_response.get("thought", ""),
                outcome="failed",
                error_type="same_tool_loop",
                error_message=f"模型连续{_cnt}步重复调用相同工具，疑似死循环",
            ))
            return
    else:
        # 非action(正常answer/final): 死循环检测仅在action语义下, 归零防残留(含纠偏标记) — 小欧 2026-08-08
        agent._consecutive_same_tool_calls = 0
        agent._last_tool_call_sig = None
        agent._warned_same_tool_loop = 0            # int计数归零 — 小欧 2026-08-08

    # ── 场景E: 正常分发 ─────────────────────────────────────────
    agent._consecutive_truncations = 0
    async for event in _dispatch_handler(agent, llm_response):
        yield event


async def run_react_cycle(
    agent,
    task: str,
    context: Optional[Dict[str, Any]] = None,
    max_steps: Optional[int] = None,
    task_id: Optional[str] = None,
):
    """ReAct循环:调用LLM→解析→分派handler→产出Step — chendyg 2026-07-01 状态集中管理重构v2"""
    if max_steps is None:
        max_steps = get_config().get_max_steps()

    chunk_buffer = initialize_run_state(agent, task, task_id, context)

    if max_steps <= 0:
        logger.warning(f"[run_react_cycle] max_steps={max_steps}, 直接终止")
        yield agent._step_emitter.emit(FinalStep(
            step=0,
            response=f"最大步骤数({max_steps})，无可执行步骤，任务取消",  # Bug2+5: max_steps<=0不是"已耗尽"; outcome=cancelled→消息一致 — 小欧 2026-07-23
            outcome="cancelled",  # 小欧 2026-07-18: MetaStep→FinalStep, max_steps=0终态统一
        ))
        set_cancelled(agent)
        _finalize_cycle(agent)
        return

    try:
        while agent.llm_call_count < max_steps:
            # ── 用户取消检测(循环粒度, 方案 B) ──
            # 小沈 2026-07-13: 本处采用"循环粒度取消"(方案 B), 不采用"流式中途打断"(方案 A)。
            # 选 B 不选 A 的原因(利弊权衡, 见 doc-7月优化/流式LLM中途取消方案取舍分析-小沈-2026-07-13.md):
    #   1) 正确性已满足: B 在每轮 LLM 调用前检测 check_cancelled, 取消即干净终止为
    #      FinalStep(outcome="cancelled")(2026-07-18 重构: 原 MetaStep(cancelled)→FinalStep),
    #      DB status 列落 cancelled, 终态语义 100% 正确, 绝不再误判 failed。
            #   2) 零回归风险: A 需给 LLMClient 加 set_stop_check 并在 httpx 流式热路径逐 chunk 轮询,
            #      涉及 client_sdk/llm_stream/call_llm_with_fallback 重试链路, 改动面大、易引入连接泄漏/
            #      异常语义混淆(CancelledError 是 BaseException 会绕过 except Exception), 必须配真实 LLM E2E。
            #   3) 体验代价可接受: B 的缺点是"长生成任务需等本轮 LLM 结束才停"; 多数 LLM 调用仅秒级,
            #      属可接受体验, 非语义缺陷。
            #   4) A 留作后续独立增强项, 待补单测+E2E 后单独排期, 不阻塞本次上线。
            # 注: 原 react_cycle 场景B 依赖 llm_client._cancelled, 该属性全局从未赋值(死代码),
            # 曾导致用户取消误走 empty_response→ErrorStep(failed)。 — 小沈 2026-07-13
            if task_id:
                from app.services.task.task_runtime import check_cancelled, task_pause_check
                if await check_cancelled(task_id):
                    logger.info(f"[run_react_cycle] 检测到任务取消(task_id={task_id}), 终止为 cancelled")
                    yield agent._step_emitter.emit(FinalStep(
                        step=agent.llm_call_count,
                        response="任务已被用户取消", outcome="cancelled",  # 小欧 2026-07-18: MetaStep→FinalStep, 用户取消终态统一
                    ))
                    set_cancelled(agent)
                    break
                # 用户暂停检测(循环粒度, 阻塞等待恢复) — 小欧 2026-07-13
                # 符合人类认知: 你喊暂停, 助手原地等(真BLOCK), 不空转、不误判为取消/完成。
                # 阻塞点在 task_pause_check 内 pause_event.wait(); 恢复后回 THINKING 继续。
                # 注意: 此处只查暂停不查取消(取消已在上方处理); 暂停不再经 LLMClient._stop_check
                # 中断流式(已在 agent_runner 改为仅查取消), 故暂停在"下一轮循环顶"干净生效。
                async for pause_event in task_pause_check(task_id):
                    yield pause_event
            try:
                async for event in _process_single_step(agent, chunk_buffer):
                    yield event
            except Exception as _step_err:
                if _is_recoverable_error(_step_err):
                    agent._retry_count = getattr(agent, '_retry_count', 0) + 1
                    if agent._retry_count > 3:
                        logger.error(f"[run_react_cycle] 可恢复错误重试超限: {_step_err}")
                        set_failed(agent, f"可恢复错误重试已达上限(3次): {_step_err}")  # task007: 明确上限值 — 小欧 2026-07-23
                        break
                    logger.warning(f"[run_react_cycle] 可恢复异常, 第{agent._retry_count}次重试: {_step_err}")
                    yield agent._step_emitter.emit(MetaStep(
                        type="retrying",
                        step=agent.llm_call_count,
                        content=f"LLM请求异常，准备重试: {_step_err}",
                    ))
                    set_status(agent, AgentStatus.RETRYING, str(_step_err)[:200])
                    continue
                raise
            if agent.status in (AgentStatus.COMPLETED, AgentStatus.FAILED, AgentStatus.CANCELLED):
                break

            # ======== RETRYING 处理（react循环重试）========
            # 说明：本态是"可恢复错误后的重试中间态"。llm_call_count 已+1，
            # react循环回 THINKING 重新调用LLM（即第N次重试），并非原地重跑当前step。
            # 与 tool_retry_engine 的"工具级重试"（同工具重执行）及 base_service 的
            # HTTP请求重试是两套独立机制，勿混淆。 — 小欧 2026-07-12 修正矛盾注释
            if agent.status == AgentStatus.RETRYING:
                agent._retry_count = getattr(agent, '_retry_count', 0) + 1
                if agent._retry_count > 3:
                    set_failed(agent, "可恢复错误重试已达上限(3次)")  # task007: 明确上限值 — 小欧 2026-07-23
                    break
                set_status(agent, AgentStatus.THINKING, f"第{agent._retry_count}次重试")
            elif agent.status == AgentStatus.EXECUTING:
                set_status(agent, AgentStatus.THINKING)

            if chunk_buffer.should_force_stop():
                logger.warning(f"[run_react_cycle] chunk累积超时({agent.llm_call_count}步),强制停止")
                set_failed(agent, f"chunk累积超时({agent.llm_call_count}步)")
                yield agent._step_emitter.emit(ErrorStep(step=agent.llm_call_count, error_type="chunk_buffer_timeout", error_message="响应累积超时，任务强制终止"))  # task007: 更友好 — 小欧 2026-07-23
                break

        if agent.status not in (
            AgentStatus.COMPLETED,
            AgentStatus.FAILED,
            AgentStatus.CANCELLED,
        ):
            logger.warning(f"[run_react_cycle] 循环结束无终态(status={agent.status}), 终止")
            yield agent._step_emitter.emit(FinalStep(
                step=agent.llm_call_count,
                response=f"任务循环结束未设终态(status={agent.status})",  # Bug3: 循环自然退出不是"异常",用事实描述 — 小欧 2026-07-23
                outcome="cancelled",  # 小欧 2026-07-18: MetaStep→FinalStep, 循环结束无终态兜底统一
            ))
            set_cancelled(agent)

    except Exception as e:
        logger.error(f"[run_react_cycle] 不可恢复异常: {e}", exc_info=True)
        error_step = handle_react_error(agent, e, agent.llm_call_count)
        yield agent._step_emitter.emit(error_step)
        set_failed(agent, f"循环异常: {e}"[:200])

    finally:
        _finalize_cycle(agent)

