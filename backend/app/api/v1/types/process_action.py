# backend/app/api/v1/types/process_action.py
# action_tool 和 observation 阶段处理逻辑
# 创建时间: 2026-03-19
# 创建人: 小沈
# 参考: doc-ReAct重构/Action与Observation拆为独立函数的说明.md

import json
import logging
import asyncio
import uuid
from typing import Any, Dict, Optional, AsyncGenerator

from app.chat_stream_helpers import create_timestamp

logger = logging.getLogger(__name__)


# ============================================================
# build_action_notification - 构建 notification 类型 action_data
# 设计文档: 3.1节第1个函数
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
# build_observation_security - 构建安全检测结果的 observation_data
# 设计文档: 3.1节第2个函数
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
# handle_action_event - 处理 Agent 返回的 action_tool 事件
# 设计文档: 3.1节第3个函数
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


# ============================================================
# handle_observation_event - 处理 Agent 返回的 observation 事件
# 设计文档: 3.1节第4个函数
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


# ============================================================
# process_file_operation - 文件操作入口主函数
# 设计文档: 3.1节第5个函数（核心函数）
# ============================================================
async def process_file_operation(
    last_message: str,
    ai_service: Any,
    task_id: str,
    current_execution_steps: list,
    current_content: Any,
    running_tasks: Dict,
    running_tasks_lock: Any,
    next_step: Any,
    add_step_and_save: Any
) -> AsyncGenerator[Dict, None]:
    """
    处理文件操作入口

    流程（对应设计文档3.2）：
    1. yield action1（notification，开始执行）
    2. 保存数据库
    3. 检查中断
    4. 安全检测
    5. yield observation1（安全检测结果）
    6. 保存数据库
    7. yield action2（启动Agent）
    8. 保存数据库
    9. 执行 Agent.run_stream()，yield 内部事件

    Yields:
        action_data / observation_data 字典
        结束信号: {'_file_operation_complete': True, 'agent_events': []}
    """
    # 1. yield action1（notification，开始执行）
    action1_data = build_action_notification(
        step_func=next_step,
        description='检测到文件操作意图，开始执行...'
    )
    logger.info(
        f"[Step action_tool] 发送action_tool步骤 - "
        f"step={action1_data['step']}, "
        f"tool_name={action1_data['tool_name']}, "
        f"summary={action1_data['summary']}"
    )
    yield action1_data

    # 2. 保存数据库
    current_execution_steps.append(action1_data)
    await add_step_and_save(action1_data, action1_data['summary'])

    await asyncio.sleep(0.3)

    # 3. 检查中断
    async with running_tasks_lock:
        if running_tasks.get(task_id, {}).get("cancelled", False):
            from app.chat_stream_helpers import create_incident_data
            interrupted_data = create_incident_data(
                'interrupted',
                '任务已被中断',
                step=next_step()
            )
            logger.info(
                f"[Step incident] 发送incident步骤 - "
                f"incident_type=interrupted, message=任务已被中断"
            )
            yield {'_incident': interrupted_data}
            return

    # 4. 安全检测
    from app.services.file_operation_agent import FileOperationAgent
    from app.services.safety_checker import check_command_safety

    safety_result = check_command_safety(last_message)
    is_safe = safety_result.get("is_safe", True)
    risk = safety_result.get("risk", "")

    # 5. 安全检测未通过，返回错误
    if not is_safe:
        from app.chat_stream_helpers import create_error_response
        error_message = f"危险操作需确认: {risk}"
        logger.info(f"[Step error] 发送error步骤(安全检测) - risk={risk}")

        error_data = create_error_response(
            error_type="security_error",
            message=error_message,
            code="SECURITY_BLOCKED",
            model=ai_service.model,
            provider=ai_service.provider,
            retryable=False,
            step=next_step()
        )

        error_step = {
            'type': 'error',
            'step': next_step(),
            'error_type': 'security_error',
            'message': error_message,
            'code': 'SECURITY_BLOCKED',
            'timestamp': create_timestamp()
        }
        await add_step_and_save(error_step, f"安全拦截: {risk}")

        yield {'_error': error_data, '_error_step': error_step}
        return

    # 6. yield observation1（安全检测结果）
    observation1_data = build_observation_security(
        step_func=next_step,
        is_safe=is_safe,
        risk=risk
    )
    logger.info(
        f"[Step observation] 发送observation步骤 - "
        f"step={observation1_data['step']}, "
        f"is_finished={observation1_data['is_finished']}, "
        f"obs_execution_status={observation1_data['obs_execution_status']}"
    )
    yield observation1_data

    # 7. 保存数据库
    current_execution_steps.append(observation1_data)
    await add_step_and_save(observation1_data, observation1_data['obs_summary'])

    await asyncio.sleep(0.3)

    # 8. 创建 Agent 执行
    session_id = str(uuid.uuid4())

    async def llm_client(message, history=None):
        response = await ai_service.chat(message, history)
        return type('obj', (object,), {'content': response.content})()

    agent = FileOperationAgent(
        llm_client=llm_client,
        session_id=session_id
    )

    # 9. yield action2（启动Agent）
    action2_data = build_action_notification(
        step_func=next_step,
        description='执行文件操作...'
    )
    logger.info(
        f"[Step action_tool] 发送action_tool步骤 - "
        f"step={action2_data['step']}, "
        f"tool_name={action2_data['tool_name']}, "
        f"summary={action2_data['summary']}"
    )
    yield action2_data

    # 10. 保存数据库
    current_execution_steps.append(action2_data)
    await add_step_and_save(action2_data, action2_data['summary'])

    # 11. 执行 Agent.run_stream()，yield 内部事件
    try:
        from app.config import get_config
        config = get_config()
        max_steps = config.get('app', {}).get('max_steps', 100)

        agent_events = []
        async for event in agent.run_stream(last_message, max_steps=max_steps):
            # 检查中断
            async with running_tasks_lock:
                if running_tasks.get(task_id, {}).get("cancelled", False):
                    from app.chat_stream_helpers import create_incident_data
                    interrupted_data = create_incident_data(
                        'interrupted',
                        '任务已被中断',
                        step=next_step()
                    )
                    logger.info(
                        f"[Step incident] 发送incident步骤 - "
                        f"incident_type=interrupted, message=任务已被中断"
                    )
                    yield {'_incident': interrupted_data}
                    break

            event_type = event.get('type')

            # 根据 event_type 分发处理
            if event_type == 'action_tool':
                action_data = handle_action_event(event, next_step)
                current_execution_steps.append(action_data)
                await add_step_and_save(action_data, action_data['summary'])
                yield {'_action': action_data}

            elif event_type == 'observation':
                observation_data = handle_observation_event(event, next_step)
                current_execution_steps.append(observation_data)
                await add_step_and_save(observation_data, observation_data['obs_summary'])
                yield {'_observation': observation_data}

            elif event_type in ('thought', 'final', 'error'):
                # 这些类型保留在 chat_stream.py 中处理
                agent_events.append(event)
                yield {'_raw_event': event}

            await asyncio.sleep(0.05)

        # 结束信号
        yield {'_file_operation_complete': True, 'agent_events': agent_events}

    except Exception as e:
        logger.error(f"文件操作执行出错：task_id={task_id}, error={e}", exc_info=True)
        from app.chat_stream_helpers import create_error_response

        error_message = "文件操作执行失败"
        error_data = create_error_response(
            error_type="file_operation_error",
            message=error_message,
            model=ai_service.model,
            provider=ai_service.provider,
            retryable=False,
            step=next_step()
        )

        error_step = {
            'type': 'error',
            'step': next_step(),
            'error_type': 'file_operation_error',
            'message': error_message,
            'code': 'FILE_OPERATION_ERROR',
            'timestamp': create_timestamp()
        }
        await add_step_and_save(error_step, f"文件操作错误: {error_message}")

        yield {'_error': error_data, '_error_step': error_step, '_file_operation_complete': True}
