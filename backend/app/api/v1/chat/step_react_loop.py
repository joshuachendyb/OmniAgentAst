# -*- coding: utf-8 -*-
"""
step_react_loop — 从 chat_router.py 拷出

task操作统一在 services/task/ 层，不再传递 running_tasks

统一: 小健 - 2026-05-31
"""

from typing import Any, Dict, List, Optional

from app.services.react_sse_wrapper import SSEConfig, generate_sse_stream_with_retry


async def step_react_loop(messages, intent_type, confidence, candidates, provider, model,
                          task_id, session_id, ai_service, next_step,
                          execution_steps):
    """拷贝自 chat_router.py 第267-277行"""
    messages_list = [{"role": msg.role, "content": msg.content} for msg in messages]
    config = SSEConfig(
        messages=messages_list, intent_type=intent_type,
        confidence=confidence, candidates=candidates, provider=provider, model=model,
        task_id=task_id, session_id=session_id, ai_service=ai_service, next_step=next_step,
    )
    async for event in generate_sse_stream_with_retry(
        config=config, current_execution_steps=execution_steps
    ):
        yield event
