# -*- coding: utf-8 -*-
"""
_run_sse_stream — 从 react_sse_wrapper.py 拆出

复制来源: react_sse_wrapper.py 第154-215行
Author: 小沈 - 2026-05-31
"""

from typing import List, Dict, Optional, AsyncGenerator, Any, Callable

from app.utils.logger import logger
from app.services.agent.generic_react import GenericReactAgent
from app.services.react_sse_wrapper.is_cancelled_and_yield import is_cancelled_and_yield
from app.services.react_sse_wrapper.emit_and_save import emit_and_save
from app.services.react_sse_wrapper.yield_error_sse import yield_error_sse


async def run_sse_stream(
    intent_type: str,
    llm_client,
    task_id: str,
    ai_service,
    candidates: list,
    last_message: str,
    next_step: Callable[[], int],
    running_tasks: dict,
    running_tasks_lock,
    session_id: str,
    current_execution_steps: list,
    current_content: str,
    agent_llm_holder: Optional[Dict[str, Any]] = None,
) -> AsyncGenerator[str, None]:
    """复制自 react_sse_wrapper.py 第154-215行"""
    from app.services.agent.agent_factory import AgentFactory
    agent = None
    log_tag = f"[{intent_type.upper()}Op]"
    error_label = f"{intent_type}操作执行失败"
    error_type = f'{intent_type}_operation_error'
    try:
        agent = AgentFactory.create(
            intent_type=intent_type, llm_client=llm_client,
            task_id=task_id, candidates=candidates,
        )
    except ValueError:
        logger.info(f"[ChatOp] intent_type='{intent_type}' 无专用Agent，使用通用TextStrategy兜底")
        from app.services.agent.llm_strategies import TextStrategy
        strategy = TextStrategy() if ai_service else None
        agent = GenericReactAgent(llm_client=llm_client, task_id=task_id, strategy=strategy)
        log_tag = "[GenericOp]"
        error_label = "操作执行失败"
        error_type = 'generic_operation_error'
    try:
        async for event in agent.run_stream(
            task=last_message, context=None,
            task_id=task_id,
            running_tasks=running_tasks,
        ):
            cancelled_sse = await is_cancelled_and_yield(
                task_id, running_tasks, running_tasks_lock, next_step,
                session_id, current_execution_steps, current_content
            )
            if cancelled_sse:
                yield cancelled_sse
                break
            sse_data, current_content = await emit_and_save(event, session_id, current_execution_steps, current_content)
            if sse_data:
                logger.info(f"{log_tag} SSE发送数据")
                yield sse_data
    except Exception as e:
        error_response = await yield_error_sse(
            error_type=error_type, error_label=error_label, log_tag=log_tag,
            task_id=task_id, e=e, next_step=next_step, ai_service=ai_service,
            current_execution_steps=current_execution_steps, session_id=session_id,
        )
        yield error_response
    finally:
        if agent_llm_holder is not None and agent is not None:
            agent_llm_holder["n"] = getattr(agent, "llm_call_count", 0)
