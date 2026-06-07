# -*- coding: utf-8 -*-
"""
_run_sse_stream — 纯SSE流运行器

小健 - 2026-06-07 清理:删除emit_and_save,改用emit_only+外部显式save

Author: 小沈 - 2026-05-31
"""

from typing import List, Dict, Optional, AsyncGenerator, Any, Callable

from app.utils.logger import logger
from app.services.react_sse_wrapper.emit_only import emit_only
from app.services.react_sse_wrapper.yield_error_sse import yield_error_sse


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
    """纯SSE流运行器"""
    from app.services.agent.agent_factory import AgentFactory
    from app.chat_stream.message_saver import save_execution_steps_to_db
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
        async for event in agent.run_stream(
            task=last_message, context=None,
            task_id=task_id,
        ):
            sse_data, current_content = await emit_only(event, current_content)
            if sse_data:
                # 显式保存(唯一路径)
                if sse_data.startswith("data: "):
                    import json
                    step_dict = json.loads(sse_data[6:])
                    current_execution_steps.append(step_dict)
                await save_execution_steps_to_db(session_id, current_execution_steps, current_content)
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
