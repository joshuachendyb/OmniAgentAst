# -*- coding: utf-8 -*-
"""
_run_sse_stream — 纯SSE流运行器

小健 - 2026-06-08 修复P1: 删除SSE双重解析(Step→SSE字符串→dict)，改为直接to_dict()
                   删除每个chunk全量save，改为final时批量保存一次

Author: 小沈 - 2026-05-31
"""

from typing import List, Dict, Optional, AsyncGenerator, Any, Callable

from app.utils.logger import logger


async def run_sse_stream(
    intent_type: str,
    llm_client,
    task_id: str,
    ai_service,
    candidates: list,
    last_message: str,
    next_step: Callable[[], int],
    session_id: str,
    current_execution_steps: List,
    current_content: str,
    agent_llm_holder: Optional[Dict[str, Any]] = None,
) -> AsyncGenerator[str, None]:
    """纯SSE流运行器 — 直接to_dict(), final时批量保存"""
    from app.services.agent.agent_factory import AgentFactory
    from app.chat_stream import format_agent_sse, save_execution_steps_to_db

    agent = None
    log_tag = f"[{intent_type.upper()}Op]"
    error_label = f"{intent_type}操作执行失败"
    error_type = f'{intent_type}_operation_error'

    try:
        agent = AgentFactory.create(
            intent_type=intent_type, llm_client=llm_client,
            task_id=task_id, candidates=candidates,
        )
    except ValueError as e:
        logger.error(f"[ChatOp] intent_type='{intent_type}' 无专用Agent: {e}")
        raise

    try:
        async for event in agent.run_react_cycle(
            task=last_message, context=None,
            task_id=task_id,
        ):
            # 直接to_dict()，不走SSE字符串往返
            event_dict = event.to_dict() if hasattr(event, 'to_dict') else event
            event_type = event_dict.get('type', '') if isinstance(event_dict, dict) else ''

            # 累积execution_steps
            if event_dict:
                current_execution_steps.append(event_dict)

            # 更新current_content
            if event_type == 'final':
                current_content = event_dict.get('response', current_content) or current_content
            elif event_type == 'chunk':
                current_content = event_dict.get('content', current_content)

            # 格式化SSE(仅format，已用event_dict避免二次to_dict)
            sse_data = format_agent_sse(event_dict)

            # yield SSE
            if sse_data:
                yield sse_data

        # final时批量保存一次
        if current_execution_steps:
            await save_execution_steps_to_db(session_id, current_execution_steps, current_content)

    except Exception as e:
        error_response = await _yield_error_sse(
            error_type=error_type, error_label=error_label, log_tag=log_tag,
            task_id=task_id, e=e, next_step=next_step, ai_service=ai_service,
            current_execution_steps=current_execution_steps, session_id=session_id,
        )
        yield error_response
    finally:
        if agent_llm_holder is not None and agent is not None:
            agent_llm_holder["n"] = getattr(agent, "llm_call_count", 0)


async def _yield_error_sse(error_type, error_label, log_tag, task_id, e, next_step, ai_service, current_execution_steps, session_id):
    """内联错误SSE生成(避免外部模块依赖) — P2-18 使用ErrorStep替代手工dict"""
    from app.chat_stream import save_execution_steps_to_db, format_agent_sse
    from app.services.agent.steps import ErrorStep

    step_num = next_step()
    error_step = ErrorStep(
        step=step_num,
        error_type=error_type,
        error_message=str(e),
        error_label=error_label,
    )
    current_execution_steps.append(error_step.to_dict())
    await save_execution_steps_to_db(session_id, current_execution_steps, error_label)

    return format_agent_sse(error_step)
