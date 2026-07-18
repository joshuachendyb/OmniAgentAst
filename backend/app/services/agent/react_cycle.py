# -*- coding: utf-8 -*-
# 编辑历史:
# 记录 2026-07-01 chendyg 状态集中管理重构v2
#   - 状态用 status_table, 数据 handler 自己写
#   - _dispatch_handler 基于 event type 推断状态
#   - handler 保留 add_observation/add_assistant_message, 不绕路
# 记录 2026-07-17 小沈 FC重命名: import/LLMResponseError同步
# 记录 2026-07-17 小欧 B3扩展+修正: 检测reasoning-only空转并软引导(修正has_tool_results屏蔽使已调工具后仍可警告); 改add_observation→add_assistant_message(避免空tool_call_id孤立tool消息致LLM参数不合法, 参照edca06261昨天修正); warning去具体工具名
# 记录 2026-07-18 小欧 FinalStep多态自包含终态重构:
#   【病根】原react_cycle中取消/截断/无终态等路径用MetaStep(cancelled)表示终态,
#          与answer_handler的FinalStep(completed)不一致; _dispatch_handler基于event.type位置推断终态,
#          逻辑分散且易遗漏(如空响应路径set_failed但不产出终态step)。
#   【思路】统一终态语义: 所有终态路径改用FinalStep(outcome=xxx),
#          _dispatch_handler改为outcome驱动终态声明(不依赖位置/类型); 可恢复错误仍用ErrorStep。
#   【改法】①场景B/C/D/循环结束无终态: MetaStep(cancelled)→FinalStep(outcome="cancelled")
#          ②_dispatch_handler: 从位置驱动改为outcome驱动(set_failed/set_cancelled/set_completed)
#          ③可恢复错误(ErrorStep)和可恢复拒绝(_RECOVERABLE_ERRORS)保持不变
# 2026-07-18 - 小欧 - 修复#7 _dispatch_handler 用循环内单独捕获的 final_event 读 outcome, 不取末事件last_event(末事件未必是final,脆弱); 修复#9 stale注释 MetaStep(cancelled)→FinalStep(outcome="cancelled")
"""
run_react_cycle — ReAct 循环核心（薄调度）

职责: 循环调度 + 类型分派 + 状态推断，不含业务逻辑
业务逻辑在 handlers/ 目录
"""

import asyncio
import time
from typing import Any, Dict, Optional, AsyncGenerator

from app.logger import logger
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
    for i in range(len(history) - 1, -1, -1):
        msg = history[i]
        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            for j in range(i + 1, len(history)):
                next_msg = history[j]
                if next_msg.get("role") in ("tool", "observation"):
                    return False
            return True
    return False


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
    - "retrying" → 置RETRYING（重试由编排层except块处理）
    - "error" → set_failed
    - "final" → set_completed
    - 其他 → continue（不设状态）
    """
    parsed_type = llm_response.get("type", "answer")
    step = agent.llm_call_count
    thought = llm_response.get("thought", "")
    reasoning = llm_response.get("reasoning", "")
    if thought:
        reasoning_part = f"\n{time.strftime('%H:%M:%S')} === 推理 ===\n{reasoning}" if reasoning else ""
        print(f"{time.strftime('%H:%M:%S')} [Thought] step={step}, {thought}{reasoning_part}")  # 小欧 2026-07-02 控制台
    if parsed_type == "action":
        handler = handle_action(agent, llm_response)
    else:
        handler = handle_answer(agent, llm_response)

    seen_types = set()
    last_error_event = None
    final_event = None
    async for event in handler:
        seen_types.add(event.type)
        if event.type == "error":
            last_error_event = event
        elif event.type == "final":
            final_event = event
        yield event

    if "retrying" in seen_types:
        set_status(agent, AgentStatus.RETRYING, "触发重试")
    elif "final" in seen_types:
        # outcome 驱动终态声明: 读 FinalStep.outcome, 不依赖位置/类型 — 小欧 2026-07-18
        # 用循环内单独捕获的 final_event(真实 FinalStep), 不取末事件 last_event(#7: 末事件未必是final, 脆弱)
        oc = getattr(final_event, "outcome", "completed")
        if oc == "failed":
            set_failed(agent, getattr(final_event, "error_message", "") or final_event.get_content())
        elif oc == "cancelled":
            set_cancelled(agent)
        else:
            set_completed(agent)
    elif "error" in seen_types:
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

    # ── Phase 3: 响应分发 ──────────────────────────────────────
    set_status(agent, AgentStatus.EXECUTING)

    step = agent.llm_call_count

    # ── 场景A: 空响应 — LLM未返回有效数据 ──────────────────────
    if not llm_response or not isinstance(llm_response, dict):
        logger.error(f"[run_react_cycle] _call_llm返回无效响应: {type(llm_response)}")
        print(f"{time.strftime('%H:%M:%S')} [Error] step={step}, empty_response")  # 小欧 2026-07-02 控制台
        set_failed(agent, "LLM返回空响应")
        yield agent._step_emitter.emit(ErrorStep(
            step=step, error_type="empty_response",
            error_message="LLM返回空响应"
        ))
        return

    # ── 场景B: 任务取消(llm_client._cancelled, 历史兜底; 主路径见循环顶 check_cancelled) ──
    if getattr(getattr(agent, 'llm_client', None), '_cancelled', False):
        print(f"{time.strftime('%H:%M:%S')} [Cancel] step={step}, cancelled")  # 小欧 2026-07-02 控制台
        yield agent._step_emitter.emit(FinalStep(
            step=step,
            response="任务已被中断",
            outcome="cancelled",  # 小欧 2026-07-18: MetaStep→FinalStep, 终态统一type=final+outcome声明
        ))
        set_cancelled(agent)
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
            agent.message_builder.add_assistant_message(obs_text)  # 2026-07-17 - 小欧 - 改add_assistant_message(参照edca06261昨天修正: add_observation空tool_call_id会创建孤立tool消息致LLM参数不合法)
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
            print(f"{time.strftime('%H:%M:%S')} [Cancel] step={step}, consecutive_truncation")  # 小欧 2026-07-02 控制台
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
            response=f"max_steps={max_steps}, 无可用步骤",
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
            async for event in _process_single_step(agent, chunk_buffer):
                yield event

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
                    set_failed(agent, "可恢复错误重试超限")
                    break
                set_status(agent, AgentStatus.THINKING, f"第{agent._retry_count}次重试")
            elif agent.status == AgentStatus.EXECUTING:
                set_status(agent, AgentStatus.THINKING)

            if chunk_buffer.should_force_stop():
                logger.warning(f"[run_react_cycle] chunk累积超时({agent.llm_call_count}步),强制停止")
                set_failed(agent, f"chunk累积超时({agent.llm_call_count}步)")
                yield agent._step_emitter.emit(ErrorStep(step=agent.llm_call_count, error_type="chunk_buffer_timeout", error_message="chunk buffer累积超时，强制停止"))
                break

        if agent.status not in (
            AgentStatus.COMPLETED,
            AgentStatus.FAILED,
            AgentStatus.CANCELLED,
        ):
            logger.warning(f"[run_react_cycle] 循环结束无终态(status={agent.status}), 终止")
            yield agent._step_emitter.emit(FinalStep(
                step=agent.llm_call_count,
                response=f"ReAct循环结束但无终态(status={agent.status})",
                outcome="cancelled",  # 小欧 2026-07-18: MetaStep→FinalStep, 循环结束无终态兜底统一
            ))
            set_cancelled(agent)

    except Exception as e:
        logger.error(f"[run_react_cycle] 异常: {e}", exc_info=True)
        if _is_recoverable_error(e):
            # 可恢复异常(FC格式/网络/超时) → 系统重试通知, 由 RETRYING 态驱动编排层重试 — 小欧 2026-07-13
            logger.warning(f"[run_react_cycle] 可恢复异常, 触发重试: {e}")
            yield agent._step_emitter.emit(MetaStep(
                type="retrying",
                step=agent.llm_call_count,
                content=f"LLM 请求异常，准备重试: {e}",
            ))
            agent._retry_count = getattr(agent, '_retry_count', 0) + 1
            if agent._retry_count > 3:
                set_failed(agent, f"重试超限: {e}")
            else:
                set_status(agent, AgentStatus.RETRYING, str(e)[:200])
        else:
            error_step = handle_react_error(agent, e, agent.llm_call_count)
            yield agent._step_emitter.emit(error_step)
            set_failed(agent, f"循环异常: {e}"[:200])

    finally:
        _finalize_cycle(agent)
