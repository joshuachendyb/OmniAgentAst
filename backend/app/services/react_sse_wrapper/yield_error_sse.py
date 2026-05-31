# -*- coding: utf-8 -*-
"""
_yield_error_sse — 从 react_sse_wrapper.py 拆出

复制来源: react_sse_wrapper.py 第58-76行
Author: 小沈 - 2026-05-31
"""

from app.services.agent.steps import StepFactory
from app.utils.logger import logger
from app.chat_stream.message_saver import save_execution_steps_to_db
from app.chat_stream.sse_formatter import format_agent_sse


async def yield_error_sse(
    error_type: str, error_label: str, log_tag: str,
    task_id: str, e: Exception, next_step, ai_service,
    current_execution_steps, session_id
) -> str:
    """复制自 react_sse_wrapper.py 第58-76行"""
    logger.error(f"{log_tag} 执行出错：task_id={task_id}, error={e}", exc_info=True)
    error_step_obj = StepFactory.create_error_step(
        step=next_step(), error_type=error_type, error_message=error_label,
        recoverable=False, model=ai_service.model, provider=ai_service.provider
    )
    error_response = format_agent_sse(error_step_obj)
    current_execution_steps.append(error_step_obj.to_dict())
    await save_execution_steps_to_db(session_id, current_execution_steps, error_label)
    return error_response
