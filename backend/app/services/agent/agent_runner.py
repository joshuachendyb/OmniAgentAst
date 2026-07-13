# -*- coding: utf-8 -*-
"""
agent_runner — agent 后台运行器（与 SSE 传输解耦）

北京老陈 2026-07-12: 将 agent 执行从 HTTP handler 解耦为独立后台任务。
事件写入 agent_streams[task_id].event_log（append-only，含 seq），
SSE 连接只从 event_log 按 seq 偏移读取，支持断线重连。 — 小欧 2026-07-12

设计原则：
- SRP: 本模块是"生产者"单一职责，只负责运行 agent + 写事件缓冲
- DRY: 复用 run_react_cycle / save_execution_steps_to_db / _log_task_end / _load_previous_messages
- KISS-DIRECT: 无注册表/无抽象层，直接写缓冲
- 禁止 backward: 不保留旧 run_sse_stream 调用方式
"""

import asyncio
import time
from typing import Any, Callable, Dict, List, Optional

from app.db import db
from app.services.agent.steps import ErrorStep, MetaStep  # 小欧 2026-07-13: 删 FinalStep（终态改由 ErrorStep/MetaStep 表示，不再补发 FinalStep）
from app.services.agent.status_table import AgentStatus, set_cancelled, set_failed
from app.services.chat.handlers import save_execution_steps_to_db
from app.services.chat.stream import _load_previous_messages, _log_task_end
from app.services.task.task_registry import task_cleanup
from app.services.task.task_state import (
    running_tasks, running_tasks_lock,
    agent_streams, reclaim_stream_buffer,
)
from app.logger import logger
from app.logger.prompt_logger import get_prompt_logger


# 后台任务强引用表: asyncio 仅持有 Task 弱引用, 若 SSE 消费者断开后任务再无强引用,
# 会被 GC 回收并取消, 导致 finally 的 save_execution_steps_to_db 被打断、结果丢失。
# 集中持有强引用, done 时 discard 防内存泄漏 — 小欧 2026-07-13
_background_tasks: set = set()


async def run_agent_in_background(
    agent,
    task_id: str,
    last_message: str,
    context: Optional[dict],
    next_step: Callable[[], int],
    session_id: str,
    stream_state: Any = None,
    start_time: Optional[float] = None,
) -> None:
    """后台运行 agent，事件追加到 event_log，结束置 done。

    解决什么问题：前端 SSE 断线时，FastAPI 会取消 handler 协程；
    若 agent 在 handler 内运行，断线即终止 agent。解耦后 agent 在
    独立后台任务运行，断线不影响，前端可重连读取同一 event_log。 — 小欧 2026-07-12
    """
    # 强引用自身任务, 防止 SSE 消费者断开后任务被 GC 回收→取消→打断 finally 的 DB 保存
    # (功能退化修复: 升级前 LLM 正常/异常结束 DB 均落库, 升级后断流导致任务被回收而丢失结果)
    # 与 openai.py 声明的"断线不影响 agent"解耦设计一致 — 小欧 2026-07-13
    _self_task = asyncio.current_task()
    if _self_task is not None:
        _background_tasks.add(_self_task)
        _self_task.add_done_callback(_background_tasks.discard)

    buffer = agent_streams.get(task_id)
    current_execution_steps: List[Dict] = []
    end_type = "unknown"

    async def _append(event_dict: Dict) -> None:
        # 注意: current_execution_steps 由各调用点(主循环/异常分支)显式追加,
        # 此处仅负责写入 event_log + 唤醒消费者, 禁止再 append current_execution_steps,
        # 否则会导致DB步骤被重复累积(实测 SSE=21/DB=42 翻倍) — 小欧 2026-07-13
        d = dict(event_dict)
        d["seq"] = len(buffer.event_log)
        buffer.event_log.append(d)
        get_prompt_logger().log_step_yield(d, round_number=d.get("step", 0))
        # 唤醒等待中的消费者: Condition.notify_all 必须在持锁时调用,
        # 否则抛 RuntimeError('cannot notify on un-acquired lock') — 小欧 2026-07-13
        async with buffer.cond:
            buffer.cond.notify_all()

    # 退出分支与DB保存保证 — 小欧 2026-07-13
    # 本函数有 3 个退出路径，无论哪条路径 finally 都会执行 DB 保存：
    #
    # 1. try 正常完成：run_react_cycle 正常结束，current_execution_steps 有完整数据
    #    → finally: save_execution_steps_to_db ✅
    #
    # 2. except asyncio.CancelledError：任务被取消（主动/被动）
    #    → 追加 cancelled_dict 到 current_execution_steps
    #    → finally: save_execution_steps_to_db ✅
    #
    # 3. except Exception：其他异常（LLM 错误/工具异常/网络超时等）
    #    → 追加 error_dict 到 current_execution_steps
    #    → finally: save_execution_steps_to_db ✅
    #
    # 强引用保障：_background_tasks 集合持有 Task 引用，防止 GC 回收导致 finally 不执行
    # （无强引用时 Task 被 GC → CancelledError → finally 可能被打断 → DB 结果丢失）

    # ① 正常结束分支 — 小欧 2026-07-13
    try:
        # 注册 agent 到任务运行表，供暂停路径设置 AgentStatus.SUSPENDED — 小欧 2026-07-12
        async with running_tasks_lock:
            if task_id in running_tasks:
                running_tasks[task_id]["agent"] = agent
        llm_service = getattr(agent, "llm_client", None)
        if llm_service is not None and hasattr(llm_service, "context_limit") and llm_service.context_limit:
            agent.message_builder.MAX_CONTEXT_CHARS = llm_service.context_limit

        # 注入停止检查回调，消除 llm→task 反向依赖 — 小沈 2026-06-17
        # 小欧 2026-07-13: 采用"循环粒度取消"(方案 B)。_stop_check 仅查取消(中断在飞 LLM 流);
        # 暂停不再经此中断, 改由 react_cycle 循环顶 task_pause_check 阻塞等待恢复(符合人类认知"原地等")。
        if llm_service is not None and hasattr(llm_service, "set_stop_check"):
            async def _stop_check():
                from app.services.task.task_runtime import check_cancelled
                # 仅查取消: 暂停不再经此中断 LLM 流, 改由 react_cycle 循环顶 task_pause_check 阻塞处理
                # (符合人类认知"原地等"); 否则暂停会令在飞 LLM 流被打断→忙等空转/误判。 — 小欧 2026-07-13
                return await check_cancelled(task_id)
            llm_service.set_stop_check(_stop_check)

        # 加载会话历史，支持多轮对话 — 北京老陈 2026-06-13
        ctx = {}
        if session_id:
            prev = _load_previous_messages(session_id)
            if prev:
                ctx["previous_messages"] = prev
        run_context = context or ctx or None

        async for event in agent.run_react_cycle(
            task=last_message, context=run_context, task_id=task_id
        ):
            # event 可能为 dict 或 Step，统一 to_dict — chendyg 2026-06-26
            if isinstance(event, dict):
                event_dict = event
            elif hasattr(event, "to_dict"):
                event_dict = event.to_dict()
            else:
                logger.warning(f"[Runner] 跳过非Step事件: {type(event)}")
                continue
            event_type = event_dict.get("type", "")
            get_prompt_logger().log_step_yield(event_dict, round_number=event_dict.get("step", 0))
            # 累积 execution_steps
            if event_dict:
                current_execution_steps.append(event_dict)
            # 更新 current_content — 小沈 2026-06-09
            if event_type == "final":
                content = event_dict.get("response", "") or ""
                if stream_state is not None:
                    stream_state.current_content = content or stream_state.current_content
            elif event_type == "chunk":
                chunk_text = event_dict.get("content", "")
                if stream_state is not None and chunk_text:
                    stream_state.current_content += chunk_text
            await _append(event_dict)

        # 正常结束：终态由 react_cycle 内部设置(agent.status), 无需在此补发

    # ② 取消分支 — 小欧 2026-07-13
    except asyncio.CancelledError:
        # 后端主动取消（task 被清理等）— 小沈 2026-06-09 修复
        # 小欧 2026-07-13: 取消终态仅 MetaStep(cancelled)，不再补发 FinalStep（避免前端误判"已完成"）
        logger.info(f"[Runner] 任务 {task_id} 被取消(CancelledError)")
        cancelled_step = MetaStep(step=next_step(), type="cancelled", content="任务已被取消")
        cancelled_dict = cancelled_step.to_dict()
        current_execution_steps.append(cancelled_dict)
        get_prompt_logger().log_step_yield(cancelled_dict, round_number=cancelled_dict.get("step", 0))
        await _append(cancelled_dict)
        if agent is not None:
            try:
                set_cancelled(agent)
            except ValueError:
                pass

    # ③ 异常分支 — 小欧 2026-07-13
    except Exception as e:
        # 小欧 2026-07-13: 失败终态仅 ErrorStep，不再补发 FinalStep（终止由 ErrorStep 表示）
        logger.error(f"[Runner] 任务 {task_id} 异常: {e}", exc_info=True)
        error_step = ErrorStep(step=next_step(), error_type="agent_operation_error", error_message=str(e))
        error_dict = error_step.to_dict()
        current_execution_steps.append(error_dict)
        await _append(error_dict)
        if agent is not None:
            try:
                set_failed(agent, str(e)[:200])
            except ValueError:
                pass

    # finally: 统一DB保存（①②③都会执行）— 小欧 2026-07-13
    finally:
        # 从 agent.status 推导 end_type — 小欧 2026-07-12 从 stream.py 迁移
        if end_type == "unknown" and agent is not None:
            _m = {
                AgentStatus.COMPLETED: "final",
                AgentStatus.FAILED: "failed",
                AgentStatus.CANCELLED: "cancelled",
                AgentStatus.RETRYING: "failed",
                AgentStatus.SUSPENDED: "paused",
            }
            end_type = _m.get(agent.status, "unknown")

        # 统一保存入口：正常、异常、取消都走这里 — 小欧 2026-06-26
        # 小欧 2026-07-13: 落 chat_messages.status 列（终态），正常路径依赖该列
        _STATUS_MAP = {"final": "completed", "failed": "failed",
                       "cancelled": "cancelled", "paused": "paused"}
        # 小沈 2026-07-13: 默认必须用 "failed"(fail-safe), 不能用 "completed"。
        # end_type 仅在 agent 为 None 或 agent.status 不在映射表中时才落到 default;
        # 此时该任务并非真正完成, 若误标 completed 会让崩溃/异常任务在 DB 被当成成功,
        # 前端会话列表与历史回放都会显示错误终态。失败默认失败, 完成必须显式完成。
        _terminal_status = _STATUS_MAP.get(end_type, "failed")
        if current_execution_steps:
            for retry in range(2):
                try:
                    saved_content = stream_state.current_content if stream_state else ""
                    ai_message_id = await save_execution_steps_to_db(
                        session_id, current_execution_steps, saved_content, status=_terminal_status)
                    if ai_message_id:
                        get_prompt_logger().update_ai_message_id(str(ai_message_id))
                    break
                except Exception as save_err:
                    if retry == 0:
                        logger.warning(f"[Runner] DB保存失败(steps={len(current_execution_steps)}), 重试: {save_err}")
                    else:
                        logger.error(f"[Runner] DB保存失败(steps={len(current_execution_steps)}): {save_err}", exc_info=True)

        if agent is not None and stream_state is not None:
            stream_state.llm_call_count = getattr(agent, "llm_call_count", 0)

        # Task 生命周期日志（结束）— 小欧 2026-06-26
        _log_task_end(task_id, end_type, start_time, current_execution_steps, agent)

        # 生命周期清理：原 openai.py finally 的 task_cleanup 迁入此处 — 小欧 2026-07-12
        # 修复旧 bug：断线时不再误删在跑的 agent（cleanup 由生产者自身在结束时调用）
        await task_cleanup(task_id, getattr(agent, "llm_call_count", 0) if agent else 0)

        # 标记生产者结束，唤醒消费者；延迟回收缓冲以支持重连窗口 — 小欧 2026-07-12
        if buffer is not None:
            buffer.done.set()
            # 必须持锁调 notify_all(同 _append), 否则 RuntimeError — 小欧 2026-07-13
            async with buffer.cond:
                buffer.cond.notify_all()
            try:
                loop = asyncio.get_event_loop()
                loop.call_later(300, lambda: reclaim_stream_buffer(task_id))
            except Exception:
                pass
