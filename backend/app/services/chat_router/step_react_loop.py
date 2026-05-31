# -*- coding: utf-8 -*-
"""
step_react_loop — 从 chat_router.py 拷出

拷贝来源: chat_router.py 第267-277行
"""

from typing import Any, Dict, List, Optional

from app.services.react_sse_wrapper import generate_sse_stream_with_retry


async def step_react_loop(messages, intent_type, confidence, candidates, provider, model,
                          task_id, session_id, ai_service, next_step, running_tasks, running_tasks_lock,
                          execution_steps):
    """拷贝自 chat_router.py 第267-277行"""
    messages_list = [{"role": msg.role, "content": msg.content} for msg in messages]
    async for event in generate_sse_stream_with_retry(
        messages=messages_list, intent_type=intent_type,
        confidence=confidence, candidates=candidates, provider=provider, model=model,
        task_id=task_id, session_id=session_id, ai_service=ai_service, next_step=next_step,
        running_tasks=running_tasks, running_tasks_lock=running_tasks_lock,
        current_execution_steps=execution_steps
    ):
        yield event
