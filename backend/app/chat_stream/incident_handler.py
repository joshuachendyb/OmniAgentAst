# -*- coding: utf-8 -*-
"""
统一中断/暂停处理模块

从 chat_stream.py 拆分出来
职责：统一的中断/暂停处理
Author: 小沈 - 2026-03-22
"""

import asyncio
import json
from typing import Dict, Optional, Callable, AsyncGenerator

from app.chat_stream.chat_helpers import create_timestamp


def create_incident_data(incident_value: str, message: str, step: Optional[int] = None) -> dict:
    """
    创建统一的incident数据
    
    Args:
        incident_value: incident类型（interrupted/paused/resumed/retrying）
        message: 信息
        step: 步骤序号（可选）
    
    Returns:
        dict: incident数据
    """
    data = {
        'type': 'incident',  # 固定为incident
        'incident_value': incident_value,
        'message': message,
        'timestamp': create_timestamp()
    }
    if step is not None:
        data['step'] = step
    return data


async def check_and_yield_if_interrupted(
    task_id: str, 
    running_tasks: dict, 
    running_tasks_lock: asyncio.Lock,
    next_step: Optional[Callable[[], int]] = None
) -> tuple[bool, str]:
    """
    检查任务是否被中断，如果是则返回中断消息
    
    Args:
        task_id: 任务 ID
        running_tasks: 运行中任务字典
        running_tasks_lock: 任务锁
        next_step: 步骤计数器函数（可选）
    
    Returns:
        (is_interrupted, interrupt_message) 元组
        - is_interrupted: 是否被中断
        - interrupt_message: 中断消息（如果未被中断则为空字符串）
    """
    async with running_tasks_lock:
        if running_tasks.get(task_id, {}).get("cancelled", False):
            step_value = next_step() if next_step else None
            incident_data = create_incident_data('interrupted', '任务已被中断', step=step_value)
            return True, f"data: {json.dumps(incident_data)}\n\n"
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
                return  # 暂停期间被取消了
            
            if not is_paused:
                # 不再暂停，恢复发送
                if running_tasks.get(task_id, {}).get("_was_paused", False):
                    step_value = next_step() if next_step else None
                    resumed_data = create_incident_data('resumed', '任务已恢复', step=step_value)
                    yield f"data: {json.dumps(resumed_data)}\n\n"
                    running_tasks[task_id]["_was_paused"] = False
                return
        
        # 暂停中，等待恢复
        if is_paused and not running_tasks.get(task_id, {}).get("_was_paused", False):
            # 刚进入暂停状态，发送paused事件
            async with running_tasks_lock:
                running_tasks[task_id]["_was_paused"] = True
            step_value = next_step() if next_step else None
            paused_data = create_incident_data('paused', '任务已暂停', step=step_value)
            yield f"data: {json.dumps(paused_data)}\n\n"
        
        await asyncio.sleep(0.5)  # 每0.5秒检查一次
