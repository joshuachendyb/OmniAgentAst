# -*- coding: utf-8 -*-
"""
_save_step_to_db — 从 react_sse_wrapper.py 拆出

复制来源: react_sse_wrapper.py 第264-273行
Author: 小沈 - 2026-05-31
"""

import json
from typing import List

from app.chat_stream.message_saver import save_execution_steps_to_db


async def save_step_to_db(
    sse_event: str, session_id: str,
    current_execution_steps: List, current_content: str
) -> None:
    """复制自 react_sse_wrapper.py 第264-273行"""
    if sse_event.startswith("data: "):
        step_data = json.loads(sse_event[6:])
        current_execution_steps.append(step_data)
        await save_execution_steps_to_db(session_id, current_execution_steps, current_content)
