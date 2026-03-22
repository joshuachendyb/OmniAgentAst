# backend/app/api/v1/three_operation.py
# 三步操作入口主函数
# 创建时间: 2026-03-19
# 创建人: 小沈

import json
import logging
import asyncio
import uuid
from typing import Any, Dict, AsyncGenerator

from app.chat_stream_helpers import create_timestamp

logger = logging.getLogger(__name__)


# ============================================================
# process_file_operation - 文件操作入口主函数
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

    流程：
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
    from app.api.v1.action1 import build_action_notification, handle_action_event
    from app.api.v1.observation1 import build_observation_security, handle_observation_event
    from app.services.agent.agent import IntentAgent
    from app.services.safety_checker import check_command_safety
    from app.chat_stream_helpers import create_incident_data, create_error_response
    from app.config import get_config

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
    safety_result = check_command_safety(last_message)
    is_safe = safety_result.get("is_safe", True)
    risk = safety_result.get("risk", "")

    # 5. 安全检测未通过，返回错误
    if not is_safe:
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

    agent = IntentAgent(
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
        config = get_config()
        max_steps = config.get('app', {}).get('max_steps', 100)

        agent_events = []
        async for event in agent.run_stream(last_message, max_steps=max_steps):
            # 检查中断
            async with running_tasks_lock:
                if running_tasks.get(task_id, {}).get("cancelled", False):
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
