# -*- coding: utf-8 -*-
"""
create_add_step_and_save — 从 message_saver.py 拷出

拷贝来源: message_saver.py 第126-151行
"""

from typing import List, Dict, Optional, Callable

from app.chat_stream.message_saver.add_step_and_save import add_step_and_save


def create_add_step_and_save(
    current_execution_steps: List[Dict],
    session_id: Optional[str]
) -> Callable:
    """拷贝自 message_saver.py 第126-151行"""
    async def add_step_and_save_func(step: Dict, content: Optional[str] = None) -> None:
        await add_step_and_save(current_execution_steps, step, session_id, content)

    return add_step_and_save_func
