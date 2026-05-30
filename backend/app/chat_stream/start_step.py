# -*- coding: utf-8 -*-
"""
start_step - 发送 start 步骤的独立函数

统一方法：所有 API 调用 start 步骤时都使用此函数
避免在多个文件中重复 start 发送逻辑

【设计文档参考】：omni-对话预处理及Agent的流程设计文档-小沈-2026-03-25.md 阶段4

Author: 小沈 - 2026-03-26
Updated: 小欧 - 2026-05-30 返回 StartStep 对象
"""

from typing import Dict, Any, List, Callable

from app.utils.time_utils import create_timestamp
from app.services.agent.steps import StartStep


async def send_start_step(
    ai_service: Any,
    task_id: str,
    next_step: Callable,
    user_message: str,
    security_check_result: Dict[str, Any],
    current_execution_steps: List[Dict[str, Any]],
    session_id: str,
) -> StartStep:
    """
    发送 start 步骤的独立函数（统一方法）
    
    职责：
    1. 构建 StartStep 对象
    2. 保存 to_dict() 到 current_execution_steps
    3. 保存到数据库
    4. 返回 StartStep 对象
    
    参数：
    - ai_service: AI 服务实例（用于获取 provider/model）
    - task_id: 任务ID
    - next_step: 获取步骤号函数
    - user_message: 用户消息（完整显示，不截断）
    - security_check_result: 安全检查结果
    - current_execution_steps: 执行步骤列表
    - session_id: 会话ID（用于保存到数据库）
    
    返回：
    - StartStep 对象
    """
    start_step = StartStep(
        step=next_step(),
        display_name=f"{ai_service.provider} ({ai_service.model})",
        provider=ai_service.provider,
        model=ai_service.model,
        task_id=task_id,
        user_message=user_message if user_message else "",
        security_check={
            'is_safe': security_check_result.get('is_safe', True),
            'risk_level': security_check_result.get('risk_level'),
            'risk': security_check_result.get('risk'),
            'blocked': security_check_result.get('blocked', False)
        }
    )
    
    current_execution_steps.append(start_step.to_dict())
    
    from app.chat_stream.message_saver import save_execution_steps_to_db
    await save_execution_steps_to_db(session_id, current_execution_steps, "")
    
    return start_step
