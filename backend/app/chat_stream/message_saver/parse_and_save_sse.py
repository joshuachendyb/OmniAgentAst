# -*- coding: utf-8 -*-
"""
parse_and_save_sse — 从 message_saver.py 拷出

拷贝来源: message_saver.py 第159-196行
"""

import json
from typing import List, Dict

from app.chat_stream.message_saver.save_execution_steps_to_db import save_execution_steps_to_db


async def parse_and_save_sse(
    sse_data: str,
    current_execution_steps: List[Dict],
    session_id: str,
    current_content: str = ""
) -> Dict:
    """拷贝自 message_saver.py 第159-196行"""
    if sse_data.startswith("data: "):
        sse_data = sse_data[6:]

    step_data = json.loads(sse_data)
    current_execution_steps.append(step_data)
    await save_execution_steps_to_db(session_id, current_execution_steps, current_content)

    return step_data
