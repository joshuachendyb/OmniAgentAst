# -*- coding: utf-8 -*-
"""
_run_sse_stream — 纯SSE流运行器

小健 - 2026-06-08 修复P1: 删除SSE双重解析(Step→SSE字符串→dict)，改为直接to_dict()
                   删除每个chunk全量save，改为final时批量保存一次

Author: 小沈 - 2026-05-31
"""

import asyncio
from typing import List, AsyncGenerator, Any, Callable, Dict

from app.utils.logger import logger
from app.services.agent.types import AgentStatus
from app.services.task.task_state_queries import check_cancelled, check_paused


def _load_previous_messages(session_id: str) -> List[Dict[str, str]]:
    """从DB加载会话历史消息 — 小健 2026-06-17 委托db层，消除SQLite越界"""
    from app.db import db
    try:
        with db.get_conn("chat") as conn:
            rows = conn.execute(
                "SELECT role, content FROM chat_messages "
                "WHERE session_id=? ORDER BY id ASC",
                (session_id,),
            ).fetchall()
        messages = []
        for role, content in rows:
            if role in ("user", "assistant"):
                messages.append({"role": role, "content": content or ""})
        return messages[:-1] if len(messages) > 1 else []
    except Exception:
        return []


async def run_sse_stream(
    llm_client,
    task_id: str,
    last_message: str,
    next_step: Callable[[], int],
    session_id: str,
    current_execution_steps: List,
    stream_state: Any = None,
) -> AsyncGenerator[str, None]:
    """纯SSE流运行器 — 小沈 2026-06-09 支持StreamState"""
    from app.services.agent.universal_agent import UniversalAgent
    from app.utils.sse_formatter import format_agent_sse
    from app.services.react_sse_wrapper.chat_stream import save_execution_steps_to_db

    agent = None
    log_tag = "[AgentOp]"
    error_label = "操作执行失败"
    error_type = "agent_operation_error"

    try:
        agent = UniversalAgent(
            llm_client=llm_client, task_id=task_id,
        )
        
        # 【2026-06-17 小沈】注入停止检查回调，消除llm→task反向依赖
        # 修复: check_cancelled/check_paused是async，不能用lambda的or短路(会跳过check_paused)
        if hasattr(llm_client, 'set_stop_check'):
            async def _stop_check():
                return await check_cancelled(task_id) or await check_paused(task_id)
            llm_client.set_stop_check(_stop_check)

        # 加载会话历史，支持多轮对话 — 北京老陈 2026-06-13
        context = {}
        if session_id:
            prev = _load_previous_messages(session_id)
            if prev:
                context["previous_messages"] = prev

        async for event in agent.run_react_cycle(
            task=last_message, context=context or None,
            task_id=task_id,
        ):
            # 直接to_dict() — dict则直接用（某些agent实现直接yield dict）
            event_dict = event if isinstance(event, dict) else event.to_dict()
            event_type = event_dict.get('type', '')
            from app.utils.prompt_logger import get_prompt_logger
            get_prompt_logger().log_step_yield(event_dict, round_number=event_dict.get('step', 0))

            # 累积execution_steps
            if event_dict:
                current_execution_steps.append(event_dict)

            # 更新current_content — 小沈 2026-06-09 支持StreamState
            if event_type == 'final':
                content = event_dict.get('response', '') or ''
                if stream_state is not None:
                    stream_state.current_content = content or stream_state.current_content
            elif event_type == 'chunk':
                chunk_text = event_dict.get('content', '')
                if stream_state is not None and chunk_text:
                    stream_state.current_content += chunk_text

            # 格式化SSE(仅format，已用event_dict避免二次to_dict)
            sse_data = format_agent_sse(event_dict)

            # yield SSE
            if sse_data:
                yield sse_data

    except asyncio.CancelledError:
        # R3-1修复: CancelledError不是Exception子类,需单独捕获 — 小沈 2026-06-09
        # R3-2修复: 在finally保存前创建IncidentStep(interrupted),防止step丢失 — 小沈 2026-06-09
        # R3-3修复: CancelledError路径补FinalStep,保证客户端收到终态事件 — 小沈 2026-06-10
        logger.info(f"[SSE] 任务 {task_id} 被取消(CancelledError)")
        from app.services.agent.steps import MetaStep, FinalStep
        interrupted_step = MetaStep(step=next_step(), type="interrupted", message='任务已被中断')
        current_execution_steps.append(interrupted_step.to_dict())
        yield format_agent_sse(interrupted_step.to_dict())
        final_step = FinalStep(step=next_step(), response="任务已被中断")
        current_execution_steps.append(final_step.to_dict())
        yield format_agent_sse(final_step.to_dict())
        if agent is not None:
            agent.status = AgentStatus.COMPLETED

    except Exception as e:
        error_response = await _yield_error_sse(
            error_type=error_type, error_label=error_label, log_tag=log_tag,
            task_id=task_id, e=e, next_step=next_step,
            current_execution_steps=current_execution_steps, session_id=session_id,
        )
        yield error_response
        # 小健 2026-06-19: error后补发FinalStep,保证客户端收到终态事件
        from app.services.agent.steps import FinalStep
        final_step = FinalStep(step=next_step(), response=f"执行异常: {str(e)[:200]}")
        current_execution_steps.append(final_step.to_dict())
        yield format_agent_sse(final_step.to_dict())
        if agent is not None:
            agent.status = AgentStatus.FAILED

    finally:
        # 统一保存入口：正常、异常、取消都走这里
        if current_execution_steps:
            try:
                saved_content = stream_state.current_content if stream_state else ""
                await save_execution_steps_to_db(session_id, current_execution_steps, saved_content)
            except Exception as save_err:
                logger.error(f"[SSE] DB保存失败(steps={len(current_execution_steps)}): {save_err}", exc_info=True)

        if agent is not None and stream_state is not None:
            stream_state.llm_call_count = getattr(agent, "llm_call_count", 0)


async def _yield_error_sse(error_type, error_label, log_tag, task_id, e, next_step, current_execution_steps, session_id):
    """内联错误SSE生成(避免外部模块依赖) — P2-18 使用ErrorStep替代手工dict"""
    from app.utils.sse_formatter import format_agent_sse
    from app.services.agent.steps import ErrorStep

    step_num = next_step()
    error_step = ErrorStep(
        step=step_num,
        error_type=error_type,
        error_message=str(e),
    )
    current_execution_steps.append(error_step.to_dict())
    # 【修改 2026-06-09 小沈】删除_save调用，统一在finally块中保存
    return format_agent_sse(error_step.to_dict())
