# -*- coding: utf-8 -*-
"""
统一中断/暂停处理模块

从 chat_stream.py 拆分出来
职责：统一的中断/暂停处理
Author: 小沈 - 2026-03-22
Updated: 小欧 - 2026-05-30 改用 IncidentStep
"""

import asyncio
from typing import Dict, Optional, Callable, AsyncGenerator

from app.utils.time_utils import create_timestamp
from app.chat_stream.sse_formatter import format_agent_sse
from app.services.agent.steps import IncidentStep


def create_incident_data(incident_value: str, message: str, step: Optional[int] = None) -> dict:
    """
    创建统一的incident数据（保留给 chat_stream_query.py 使用）
    
    Args:
        incident_value: incident类型（interrupted/paused/resumed/retrying）
        message: 信息
        step: 步骤序号（可选）
    
    Returns:
        dict: incident数据
    """
    data = {
        'type': 'incident',
        'incident_value': incident_value,
        'content': message,
        'message': message,
        'timestamp': create_timestamp(),
        'is_reasoning': False,
        'reasoning': ''
    }
    if step is not None:
        data['step'] = step
    return data


async def check_and_yield_if_interrupted(
    task_id: str, 
    running_tasks: dict, 
    running_tasks_lock: asyncio.Lock,
    next_step: Optional[Callable[[], int]] = None
) -> tuple:
    """
    检查任务是否被中断，如果是则返回中断消息
    
    Args:
        task_id: 任务 ID
        running_tasks: 运行中任务字典
        running_tasks_lock: 任务锁
        next_step: 步骤计数器函数（可选）
    
    Returns:
        (is_interrupted, interrupt_message) 元组
    """
    async with running_tasks_lock:
        if running_tasks.get(task_id, {}).get("cancelled", False):
            step_value = next_step() if next_step else None
            incident_step = IncidentStep(
                step=step_value,
                incident_value='interrupted',
                message='任务已被中断'
            )
            return True, format_agent_sse(incident_step)
    return False, ""


async def check_and_yield_if_paused(
    task_id: str, 
    running_tasks: dict, 
    running_tasks_lock: asyncio.Lock,
    next_step: Optional[Callable[[], int]] = None
) -> AsyncGenerator[str, None]:
    """
    检查任务是否被暂停，如果是则发送paused事件并等待恢复
    
    Args:
        task_id: 任务ID
        running_tasks: 运行中任务字典
        running_tasks_lock: 任务锁
        next_step: 步骤计数器函数（可选）
    
    Yields:
        SSE 格式的事件字符串 (paused/resumed)
    """
    while True:
        async with running_tasks_lock:
            is_paused = running_tasks.get(task_id, {}).get("paused", False)
            is_cancelled = running_tasks.get(task_id, {}).get("cancelled", False)
            
            if is_cancelled:
                return
            
            if not is_paused:
                if running_tasks.get(task_id, {}).get("_was_paused", False):
                    step_value = next_step() if next_step else None
                    incident_step = IncidentStep(
                        step=step_value,
                        incident_value='resumed',
                        message='任务已恢复'
                    )
                    yield format_agent_sse(incident_step)
                    running_tasks[task_id]["_was_paused"] = False
                return
        
        if is_paused and not running_tasks.get(task_id, {}).get("_was_paused", False):
            async with running_tasks_lock:
                running_tasks[task_id]["_was_paused"] = True
            step_value = next_step() if next_step else None
            incident_step = IncidentStep(
                step=step_value,
                incident_value='paused',
                message='任务已暂停'
            )
            yield format_agent_sse(incident_step)
        
        await asyncio.sleep(0.5)
