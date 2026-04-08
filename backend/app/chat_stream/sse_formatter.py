# -*- coding: utf-8 -*-
"""
SSE 事件格式化工具函数

提供统一的 SSE 事件格式化功能，用于将各种类型的消息转换为 SSE 格式字符串。
Author: 小沈 - 2026-03-22
"""

import json
from datetime import datetime
from typing import Any, Dict, Optional

from app.chat_stream.chat_helpers import create_timestamp


def format_sse_event(event_type: str, step: int, data: Dict[str, Any]) -> str:
    """
    统一格式化 SSE 事件

    Args:
        event_type: 事件类型 (thought/action_tool/observation/final/error)
        step: 步骤编号
        data: 事件数据字典

    Returns:
        SSE 格式字符串: "data: {json}\n\n"
    """
    base = {
        'type': event_type,
        'step': step
    }
    # 【小沈修复 2026-03-24】如果 data 已经有 timestamp，保留它；否则生成毫秒时间戳
    if 'timestamp' in data:
        base['timestamp'] = data['timestamp']
    else:
        base['timestamp'] = create_timestamp()
    base.update(data)
    return f"data: {json.dumps(base, ensure_ascii=False)}\n\n"


def format_thought_sse(
    step: int,
    content: str,
    reasoning: str = '',
    action_tool: str = '',
    params: Optional[Dict] = None
) -> str:
    """
    格式化 thought 事件

    Args:
        step: 步骤编号
        content: 思考内容
        reasoning: 推理过程
        action_tool: 目标工具
        params: 工具参数

    Returns:
        SSE 格式字符串
    """
    return format_sse_event('thought', step, {
        'content': content,
        'reasoning': reasoning,
        'action_tool': action_tool,
        'params': params or {}
    })


def format_action_tool_sse(
    step: int,
    tool_name: str,
    tool_params: Optional[Dict] = None,
    execution_status: str = 'success',
    summary: str = '',
    raw_data: Any = None,
    action_retry_count: int = 0
) -> str:
    """
    格式化 action_tool 事件

    Args:
        step: 步骤编号
        tool_name: 工具名称
        tool_params: 工具参数字典
        execution_status: 执行状态 (success/failed/error)
        summary: 执行摘要
        raw_data: 原始数据
        action_retry_count: 重试次数

    Returns:
        SSE 格式字符串
    """
    return format_sse_event('action_tool', step, {
        'tool_name': tool_name,
        'tool_params': tool_params or {},
        'execution_status': execution_status,
        'summary': summary,
        'raw_data': raw_data,
        'action_retry_count': action_retry_count
    })


def format_observation_sse(
    step: int,
    content: str = '',
    tool_name: str = '',
    timestamp: str = ''
) -> str:
    """
    格式化 observation 事件

    Args:
        step: 步骤编号
        content: 内容（工具执行结果简述）
        tool_name: 工具名称

    Returns:
        SSE 格式字符串
    """
    return format_sse_event('observation', step, {
        'type': 'observation',
        'step': step,
        'timestamp': timestamp,
        'tool_name': tool_name,
        'content': content
    })


__all__ = [
    "format_sse_event",
    "format_thought_sse",
    "format_action_tool_sse",
    "format_observation_sse",
]
