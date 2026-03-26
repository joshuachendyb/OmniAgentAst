# -*- coding: utf-8 -*-
"""
start_step - 发送 start 步骤的独立函数

统一方法：所有 API 调用 start 步骤时都使用此函数
避免在多个文件中重复 start 发送逻辑

【设计文档参考】：omni-对话预处理及Agent的流程设计文档-小沈-2026-03-25.md 阶段4

Author: 小沈 - 2026-03-26
"""

from typing import Dict, Any, List, Callable


async def send_start_step(
    ai_service: Any,
    task_id: str,
    next_step: Callable,
    user_message: str,
    security_check_result: Dict[str, Any],
    current_execution_steps: List[Dict[str, Any]],
    yield_func: Callable[[Dict[str, Any]], None]
) -> Dict[str, Any]:
    """
    发送 start 步骤的独立函数（统一方法）
    
    职责：
    1. 构建 start_data
    2. 通过 SSE 发送 start 步骤
    3. 保存到 current_execution_steps
    4. 返回 start_data（供后续 final/error 步骤使用）
    
    参数：
    - ai_service: AI 服务实例（用于获取 provider/model）
    - task_id: 任务ID
    - next_step: 获取步骤号函数
    - user_message: 用户消息（用于预览，取前40字）
    - security_check_result: 安全检查结果
    - current_execution_steps: 执行步骤列表
    - yield_func: SSE 发送回调函数
    
    返回：
    - start_data 字典（包含 display_name/provider/model 等）
    """
    from app.chat_stream.chat_helpers import create_timestamp
    
    # 1. 构建 start_data
    start_data = {
        'type': 'start',
        'step': next_step(),
        'timestamp': create_timestamp(),
        'display_name': f"{ai_service.provider} ({ai_service.model})",
        'provider': ai_service.provider,
        'model': ai_service.model,
        'task_id': task_id,
        'user_message': user_message[:40] if user_message else "",
        'security_check': {
            'is_safe': security_check_result.get('is_safe', True),
            'risk_level': security_check_result.get('risk_level'),
            'risk': security_check_result.get('risk'),
            'blocked': security_check_result.get('blocked', False)
        }
    }
    
    # 2. 发送 SSE（通过回调函数）
    yield_func(start_data)
    
    # 3. 保存到 current_execution_steps
    current_execution_steps.append(start_data)
    
    # 4. 返回 start_data
    return start_data
