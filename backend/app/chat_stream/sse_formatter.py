# -*- coding: utf-8 -*-
"""
SSE 事件格式化工具函数

提供统一的 SSE 事件格式化功能，用于将各种类型的消息转换为 SSE 格式字符串。
Author: 小沈 - 2026-03-22
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
    thought: str = '',
    tool_name: str = '',
    tool_params: Optional[Dict] = None
) -> str:
    """
    格式化 thought 事件

    Args:
        step: 步骤编号
        content: 思考内容
        reasoning: 推理过程
        thought: 详细思考过程
        tool_name: 目标工具
        tool_params: 工具参数

    Returns:
        SSE 格式字符串
    """
    # 【修复 2026-05-05 小沈】SSE输出增加thought字段
    return format_sse_event('thought', step, {
        'content': content,
        'thought': thought,
        'reasoning': reasoning,
        'tool_name': tool_name,
        'tool_params': tool_params or {}
    })


def format_action_tool_sse(
    step: int,
    tool_name: str,
    tool_params: Optional[Dict] = None,
    execution_status: str = 'success',
    execution_result: Any = None,
    execution_time_ms: int = 0,
    action_retry_count: int = 0,
) -> str:
    """
    格式化 action_tool 事件 — 只传执行结果摘要（status/data/耗时/重试）
    summary/error_message 由 observation 事件传递，不在此出现
    """
    return format_sse_event('action_tool', step, {
        'tool_name': tool_name,
        'tool_params': tool_params or {},
        'execution_status': execution_status,
        'execution_result': execution_result,
        'execution_time_ms': execution_time_ms,
        'action_retry_count': action_retry_count,
    })


def format_observation_sse(
    step: int,
    observation: Dict[str, Any],
    code: str = '',
    timestamp: str = ''
) -> str:
    """
    格式化 observation 事件 — observation为JSON对象（第13章设计方案）
    
    Args:
        step: 步骤编号
        observation: observation JSON对象，包含 summary/tool_name/tool_params/return_direct等
        code: 状态码（SUCCESS/ERROR/WARNING）
        timestamp: 时间戳
    
    Returns:
        SSE 格式字符串
    """
    d = {'observation': observation}
    if code:
        d['code'] = code
    if timestamp:
        d['timestamp'] = timestamp
    return format_sse_event('observation', step, d)


def format_chunk_sse(
    event: Dict[str, Any], step: int, model: str, provider: str
) -> str:
    """
    格式化chunk类型的SSE事件 — 从react_sse_wrapper.py迁移过来统一入口
    
    Args:
        event: chunk事件 dict，包含content/thought/reasoning/timestamp/is_reasoning
        step: 步骤编号
        model: 模型名称
        provider: 提供商
    
    Returns:
        SSE格式的字符串
    """
    chunk_data = {
        "type": "chunk",
        "step": step,
        "content": event.get("content", ""),
        "thought": event.get("thought", ""),
        "reasoning": event.get("reasoning", ""),
        "timestamp": event.get("timestamp", ""),
        "is_reasoning": event.get("is_reasoning", False),
        "_thinking": event.get("_thinking", ""),
        "model": model,
        "provider": provider
    }
    return format_sse_event("chunk", step, chunk_data)


def format_start_sse(start_data: Dict[str, Any]) -> str:
    """
    格式化 start 事件 — 从start_data dict构建，统一SSE入口

    Args:
        start_data: start数据字典，包含step/display_name/provider/model/
                    task_id/user_message/security_check等字段

    Returns:
        SSE格式的响应字符串
    """
    step = start_data.get('step', 0)
    data = {k: v for k, v in start_data.items() if k not in ('type', 'step')}
    return format_sse_event('start', step, data)


def format_final_sse(
    response: str,
    step: Optional[int] = None,
    display_name: Optional[str] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    is_finished: bool = True,
    thought: str = '',
    is_streaming: bool = False,
    is_reasoning: bool = False
) -> str:
    """
    格式化 final 事件 — SSE统一入口
    
    Args:
        response: 最终回复内容
        step: 步骤序号（可选）
        display_name: 模型显示名称（可选）
        provider: 模型提供商（可选）
        model: 模型名称（可选）
        is_finished: 是否完成
        thought: 思考内容
        is_streaming: 是否流式输出
        is_reasoning: 是否在推理中
    
    Returns:
        SSE格式的响应字符串
    """
    final_display_name = display_name
    if not final_display_name and provider and model:
        final_display_name = f"{provider} ({model})"
    elif not final_display_name and provider:
        final_display_name = provider
    elif not final_display_name and model:
        final_display_name = model
    
    data = {
        'response': response,
        'is_finished': is_finished,
        'thought': thought,
        'is_streaming': is_streaming,
        'is_reasoning': is_reasoning,
        'display_name': final_display_name,
        'model': model,
        'provider': provider,
    }
    if step is not None:
        return format_sse_event('final', step, data)
    else:
        base = {'type': 'final', 'timestamp': create_timestamp()}
        base.update(data)
        return f"data: {json.dumps(base, ensure_ascii=False)}\n\n"


def format_error_sse(
    error_type: str,
    error_message: str,
    step: Optional[int] = None,
    model: Optional[str] = None,
    provider: Optional[str] = None,
    details: Optional[str] = None,
    stack: Optional[str] = None,
    recoverable: Optional[bool] = None,
    retry_after: Optional[int] = None
) -> str:
    """
    格式化 error 事件 — SSE统一入口
    
    Args:
        error_type: 错误类型
        error_message: 错误信息
        step: 步骤序号（可选）
        model: 模型名称（可选）
        provider: 提供商（可选）
        details: 详细错误信息（可选）
        stack: 堆栈信息（可选）
        recoverable: 是否可恢复
        retry_after: 重试等待秒数（可选）
    
    Returns:
        SSE格式的响应字符串
    """
    data = {
        'error_type': error_type,
        'error_message': error_message,
    }
    if model is not None:
        data['model'] = model
    if provider is not None:
        data['provider'] = provider
    if details is not None:
        data['details'] = details
    if stack is not None:
        data['stack'] = stack
    if recoverable is not None:
        data['recoverable'] = recoverable
    if retry_after is not None:
        data['retry_after'] = retry_after
    
    if step is not None:
        return format_sse_event('error', step, data)
    else:
        base = {'type': 'error', 'timestamp': create_timestamp()}
        base.update(data)
        return f"data: {json.dumps(base, ensure_ascii=False)}\n\n"


def format_incident_sse(
    incident_value: str,
    message: str,
    step: Optional[int] = None,
    content: Optional[str] = None,
) -> str:
    """
    格式化 incident 事件 — SSE统一入口
    
    Args:
        incident_value: incident类型值（如 'interrupted', 'paused', 'retrying'）
        message: 消息内容
        step: 步骤序号（可选）
        content: 内容（可选，默认等于message）
    
    Returns:
        SSE格式的响应字符串
    """
    data = {
        'incident_value': incident_value,
        'message': message,
        'content': content if content is not None else message,
    }
    if step is not None:
        return format_sse_event('incident', step, data)
    else:
        base = {'type': 'incident', 'timestamp': create_timestamp()}
        base.update(data)
        return f"data: {json.dumps(base, ensure_ascii=False)}\n\n"


def format_agent_sse(event: Dict[str, Any], step: int, model: str, provider: str) -> str:
    """
    统一Agent事件SSE格式化入口 — 根据event type分发到对应format_*_sse函数

    Args:
        event: Agent输出的event dict，必须包含type字段
        step: 步骤编号
        model: 模型名称
        provider: 提供商

    Returns:
        SSE格式字符串
    """
    event_type = event.get('type', '')

    if event_type == 'thought':
        return format_thought_sse(
            step=step,
            content=event.get('content', ''),
            thought=event.get('thought', ''),
            reasoning=event.get('reasoning', ''),
            tool_name=event.get('tool_name', event.get('action_tool', '')),
            tool_params=event.get('tool_params', event.get('params', {}))
        )
    elif event_type == 'action_tool':
        return format_action_tool_sse(
            step=step,
            tool_name=event.get('tool_name', ''),
            tool_params=event.get('tool_params', {}),
            execution_status=event.get('execution_status', 'success'),
            execution_result=event.get('execution_result'),
            execution_time_ms=event.get('execution_time_ms', 0),
            action_retry_count=event.get('action_retry_count', 0),
        )
    elif event_type == 'observation':
        return format_observation_sse(
            step=step,
            observation=event.get('observation', {}),
            code=event.get('code', ''),
            timestamp=event.get('timestamp', '')
        )
    elif event_type == 'final':
        return format_final_sse(
            response=event.get('response', ''),
            step=step,
            display_name=f"{provider} ({model})",
            provider=provider,
            model=model,
            is_finished=event.get('is_finished', True),
            thought=event.get('thought', ''),
            is_streaming=event.get('is_streaming', False),
            is_reasoning=event.get('is_reasoning', False)
        )
    elif event_type == 'incident':
        return format_incident_sse(
            event.get('incident_value', ''),
            event.get('message', ''),
            step=step,
            content=event.get('content', event.get('message', ''))
        )
    elif event_type == 'interrupted':
        return format_incident_sse(
            'interrupted',
            event.get('message', '用户取消了任务'),
            step=step
        )
    elif event_type == 'error':
        return format_error_sse(
            error_type=event.get('error_type', 'agent'),
            error_message=event.get('error_message', '未知错误'),
            model=model,
            provider=provider,
            recoverable=event.get('recoverable', event.get('retryable', False)),
            step=step
        )
    elif event_type == 'chunk':
        return format_chunk_sse(
            event=event,
            step=step,
            model=model,
            provider=provider
        )

    return ''


__all__ = [
    "format_sse_event",
    "format_thought_sse",
    "format_action_tool_sse",
    "format_observation_sse",
    "format_chunk_sse",
    "format_start_sse",
    "format_final_sse",
    "format_error_sse",
    "format_incident_sse",
    "format_agent_sse",
]
