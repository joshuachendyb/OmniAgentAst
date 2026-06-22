# -*- coding: utf-8 -*-
"""
sse_formatter — SSE事件格式化工具(纯函数)

从 app.chat_stream 下沉而来,消除task/react_sse_wrapper对chat_stream的反向依赖。
SSE格式化是纯字符串操作,不依赖任何业务逻辑,属于utils层。

小沈 2026-06-17
"""

import json
from typing import Any, Dict, Optional

from app.utils.time_utils import create_timestamp


def format_sse_event(event_type: str, step: int, data: Dict[str, Any]) -> str:
    """统一格式化 SSE 事件"""
    base = {
        'type': event_type,
        'step': step
    }
    if 'timestamp' in data:
        base['timestamp'] = data['timestamp']
    else:
        base['timestamp'] = create_timestamp()
    base.update(data)
    return f"data: {json.dumps(base, ensure_ascii=False)}\n\n"


def format_agent_sse(step_dict: dict, step: int = None) -> str:
    """Agent步骤dict → SSE字符串，只接受dict输入"""
    event_type = step_dict.get('type', '')
    step_num = step or step_dict.get('step', 0)
    if not event_type:
        return ''
    return format_sse_event(event_type, step_num, step_dict)


__all__ = ["format_sse_event", "format_agent_sse"]