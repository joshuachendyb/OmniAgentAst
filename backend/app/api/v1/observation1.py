# backend/app/api/v1/types/process_observation1.py
# observation 阶段处理逻辑
# 创建时间: 2026-03-19
# 创建人: 小沈

import logging
from typing import Any, Dict

from app.chat_stream import create_timestamp

logger = logging.getLogger(__name__)


# ============================================================
# build_observation_security - 构建安全检测结果的 observation_data
# ============================================================
def build_observation_security(
    step_func: Any,
    is_safe: bool,
    risk: str = ""
) -> Dict:
    """
    构建安全检测结果的 observation_data（observation1）

    设计文档字段对照（observation类型）：
    - type: observation
    - step: next_step()
    - timestamp: create_timestamp()
    - obs_execution_status: 'success'
    - obs_summary: 安全检测通过/未通过
    - obs_raw_data: {'is_safe': xxx, 'risk': xxx}
    - content: ''（安全检测没有思考过程）
    - obs_reasoning: ''
    - obs_action_tool: 'security_check'
    - obs_params: {}
    - is_finished: True

    Args:
        step_func: next_step() 函数
        is_safe: 安全检测是否通过
        risk: 风险描述

    Returns:
        observation_data 字典
    """
    observation_data = {
        'type': 'observation',
        'step': step_func(),
        'timestamp': create_timestamp(),
        'obs_execution_status': 'success',
        'obs_summary': f'安全检测{"通过" if is_safe else "未通过"}',
        'obs_raw_data': {'is_safe': is_safe, 'risk': risk},
        'content': '',  # 安全检测没有思考过程
        'obs_reasoning': '',
        'obs_action_tool': 'security_check',
        'obs_params': {},
        'is_finished': True
    }
    return observation_data


# ============================================================
# handle_observation_event - 处理 Agent 返回的 observation 事件
# ============================================================
def handle_observation_event(event: Dict, step_func: Any) -> Dict:
    """
    处理 Agent 返回的 observation 事件，构建 observation_data

    设计文档字段对照（observation类型）：
    - type: observation
    - step: next_step()
    - timestamp: create_timestamp()
    - obs_execution_status: event.execution_status
    - obs_summary: event.summary
    - obs_raw_data: event.raw_data
    - content: event.content
    - obs_reasoning: event.reasoning
    - obs_action_tool: event.action_tool
    - obs_params: event.params
    - is_finished: event.is_finished

    Args:
        event: Agent 返回的 event 字典
        step_func: next_step() 函数

    Returns:
        observation_data 字典
    """
    observation_data = {
        'type': 'observation',
        'step': step_func(),
        'timestamp': create_timestamp(),
        'obs_execution_status': event.get('execution_status', 'success'),
        'obs_summary': event.get('summary', ''),
        'obs_raw_data': event.get('raw_data'),
        'content': event.get('content', ''),
        'obs_reasoning': event.get('reasoning', ''),
        'obs_action_tool': event.get('action_tool', ''),
        'obs_params': event.get('params', {}),
        'is_finished': event.get('is_finished', False)
    }
    logger.info(
        f"[Step observation] 发送observation步骤 - step={observation_data['step']}, "
        f"is_finished={observation_data['is_finished']}, "
        f"obs_execution_status={observation_data['obs_execution_status']}, "
        f"content长度={len(observation_data['content'])}"
    )
    return observation_data
