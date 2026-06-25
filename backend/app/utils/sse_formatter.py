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


def _break_circular(obj: Any, seen: set = None) -> Any:
    """递归删除循环引用 — 小欧 2026-06-26"""
    if seen is None:
        seen = set()
    obj_id = id(obj)
    if obj_id in seen:
        return f"<circular:{type(obj).__name__}>"
    seen.add(obj_id)
    if isinstance(obj, dict):
        return {k: _break_circular(v, seen) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_break_circular(v, seen) for v in obj]
    return obj


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
    try:
        return f"data: {json.dumps(base, ensure_ascii=False)}\n\n"
    except (ValueError, TypeError, OverflowError):
        safe = _break_circular(base)
        return f"data: {json.dumps(safe, ensure_ascii=False)}\n\n"


def format_agent_sse(step_dict: dict, step: int = None) -> str:
    """Agent步骤dict → SSE字符串，只接受dict输入"""
    event_type = step_dict.get('type', '')
    step_num = step or step_dict.get('step', 0)
    if not event_type:
        return ''
    return format_sse_event(event_type, step_num, step_dict)


__all__ = ["format_sse_event", "format_agent_sse"]