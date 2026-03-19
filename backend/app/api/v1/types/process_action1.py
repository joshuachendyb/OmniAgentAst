# backend/app/api/v1/types/process_action1.py
# action_tool 阶段处理逻辑
# 创建时间: 2026-03-19
# 创建人: 小沈

import logging
from typing import Any, Dict

from app.chat_stream_helpers import create_timestamp

logger = logging.getLogger(__name__)


# ============================================================
# build_action_notification - 构建 notification 类型 action_data
# ============================================================
def build_action_notification(step_func: Any, description: str) -> Dict:
    """
    构建 notification 类型的 action_data（action1 和 action2）

    设计文档字段对照（action_tool类型）：
    - type: action_tool
    - step: next_step()
    - timestamp: create_timestamp()
    - tool_name: 'notification'
    - tool_params: {'description': xxx}
    - execution_status: 'success'
    - summary: xxx
    - raw_data: None
    - action_retry_count: 0

    Args:
        step_func: next_step() 函数
        description: 通知描述

    Returns:
        action_data 字典
    """
    action_data = {
        'type': 'action_tool',
        'step': step_func(),
        'timestamp': create_timestamp(),
        'tool_name': 'notification',
        'tool_params': {'description': description},
        'execution_status': 'success',
        'summary': description,
        'raw_data': None,
        'action_retry_count': 0
    }
    return action_data


# ============================================================
# handle_action_event - 处理 Agent 返回的 action_tool 事件
# ============================================================
def handle_action_event(event: Dict, step_func: Any) -> Dict:
    """
    处理 Agent 返回的 action_tool 事件，构建 action_data

    设计文档字段对照（action_tool类型）：
    - type: action_tool
    - step: next_step()
    - timestamp: create_timestamp()
    - tool_name: event.tool_name
    - tool_params: event.tool_params
    - execution_status: event.execution_status
    - summary: event.summary
    - raw_data: event.raw_data
    - action_retry_count: event.action_retry_count

    Args:
        event: Agent 返回的 event 字典
        step_func: next_step() 函数

    Returns:
        action_data 字典
    """
    action_data = {
        'type': 'action_tool',
        'step': step_func(),
        'timestamp': create_timestamp(),
        'tool_name': event.get('tool_name', ''),
        'tool_params': event.get('tool_params', {}),
        'execution_status': event.get('execution_status', 'success'),
        'summary': event.get('summary', ''),
        'raw_data': event.get('raw_data'),
        'action_retry_count': event.get('action_retry_count', 0)
    }
    logger.info(
        f"[Step action_tool] 发送action_tool步骤 - step={action_data['step']}, "
        f"tool_name={action_data['tool_name']}, "
        f"execution_status={action_data['execution_status']}, "
        f"retry_count={action_data['action_retry_count']}"
    )
    return action_data
