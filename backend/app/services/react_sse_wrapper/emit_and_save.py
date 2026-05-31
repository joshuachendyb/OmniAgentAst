# -*- coding: utf-8 -*-
"""
_emit_and_save — 从 react_sse_wrapper.py 拆出

复制来源: react_sse_wrapper.py 第75-95行
Author: 小沈 - 2026-05-31
"""

import json
import asyncio

from app.chat_stream.message_saver import save_execution_steps_to_db
from app.chat_stream.sse_formatter import format_agent_sse


async def emit_and_save(
    step_obj,
    session_id: str,
    current_execution_steps: list,
    current_content: str,
    sleep_seconds: float = 0.05,
) -> tuple:
    """复制自 react_sse_wrapper.py 第75-95行"""
    sse_data = format_agent_sse(step_obj)
    if sse_data.startswith("data: "):
        step_dict = json.loads(sse_data[6:])
        current_execution_steps.append(step_dict)
        step_type = step_dict.get('type')
        if step_type == 'final':
            current_content = step_dict.get('response', current_content) or current_content
        elif step_type == 'chunk':
            current_content = step_dict.get('content', current_content)
        await save_execution_steps_to_db(session_id, current_execution_steps, current_content)
    await asyncio.sleep(sleep_seconds)
    return sse_data, current_content
