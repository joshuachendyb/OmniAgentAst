# -*- coding: utf-8 -*-
"""
SSE 事件格式化工具函数

提供统一的 SSE 事件格式化功能，用于将各种类型的消息转换为 SSE 格式字符串。
Author: 小沈 - 2026-03-22
Updated: 2026-05-30 删除 8 个 format_*_sse，format_agent_sse 支持 dict+Step 双输入
"""

import json
from datetime import datetime
from typing import Any, Dict, Optional

from app.utils.time_utils import create_timestamp


def format_sse_event(event_type: str, step: int, data: Dict[str, Any]) -> str:
    """
    统一格式化 SSE 事件

    Args:
        event_type: 事件类型 (thought/action_tool/observation/final/error)
        step: 步骤编号
        data: 事件数据字典

    Returns:
        SSE 格式字符串: "data: {json}\\n\\n"
    """
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


def format_agent_sse(event_or_step, step: int = None, model: str = '', provider: str = '') -> str:
    """
    统一Agent事件SSE格式化入口

    支持两种输入：
    1. Step 对象（新代码）：format_agent_sse(step_obj)
    2. dict（chat_stream_query.py）：format_agent_sse(event_dict, step, model, provider)

    Args:
        event_or_step: ReasoningStep 子类实例，或 event dict
        step: 步骤编号（仅 dict 输入时使用）
        model: 模型名称（仅 dict 输入时使用）
        provider: 提供商（仅 dict 输入时使用）

    Returns:
        SSE格式字符串，空字符串表示无需发送
    """
    if isinstance(event_or_step, dict):
        event_type = event_or_step.get('type', '')
        step_num = step or event_or_step.get('step', 0)
        data = event_or_step
    else:
        event_type = event_or_step.get_type()
        step_num = event_or_step.step
        data = event_or_step.to_dict()

    if not event_type:
        return ''

    return format_sse_event(event_type, step_num, data)


__all__ = [
    "format_sse_event",
    "format_agent_sse",
]
