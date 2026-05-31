# -*- coding: utf-8 -*-
"""
add_step_and_save — 从 message_saver.py 拷出

拷贝来源: message_saver.py 第92-118行
"""

from typing import List, Dict, Optional

from app.chat_stream.message_saver.save_execution_steps_to_db import save_execution_steps_to_db


async def add_step_and_save(
    current_execution_steps: List[Dict],
    step: Dict,
    session_id: Optional[str],
    content: Optional[str] = None
) -> None:
    """拷贝自 message_saver.py 第92-118行"""
    current_execution_steps.append(step)
    save_content = content if content else ""
    await save_execution_steps_to_db(session_id, current_execution_steps, save_content)
