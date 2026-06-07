# -*- coding: utf-8 -*-
"""
_emit_only — 仅格式化SSE,不保存(保存由外部显式调用)

小健 - 2026-06-07 清理:删除隐式save,消除两条保存路径的混乱

复制来源: react_sse_wrapper.py 第75-95行
Author: 小沈 - 2026-05-31
"""

import asyncio

from app.chat_stream.sse_formatter import format_agent_sse


async def emit_only(
    step_obj,
    current_content: str,
    sleep_seconds: float = 0.05,
) -> tuple:
    """仅格式化SSE,不保存"""
    sse_data = format_agent_sse(step_obj)
    if sse_data.startswith("data: "):
        import json
        step_dict = json.loads(sse_data[6:])
        step_type = step_dict.get('type')
        if step_type == 'final':
            current_content = step_dict.get('response', current_content) or current_content
        elif step_type == 'chunk':
            current_content = step_dict.get('content', current_content)
    await asyncio.sleep(sleep_seconds)
    return sse_data, current_content
