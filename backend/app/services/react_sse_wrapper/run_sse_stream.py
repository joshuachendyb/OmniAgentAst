# -*- coding: utf-8 -*-
"""
_run_sse_stream — 纯SSE流运行器

小健 - 2026-06-08 修复P1: 删除SSE双重解析(Step→SSE字符串→dict)，改为直接to_dict()
                   删除每个chunk全量save，改为final时批量保存一次

Author: 小沈 - 2026-05-31
"""

import asyncio
from typing import List, Dict, Optional, AsyncGenerator, Any, Callable

from app.utils.logger import logger
from app.services.agent.types import AgentStatus


async def run_sse_stream(
    intent_type: str,
    llm_client,
    task_id: str,
    candidates: list,
    last_message: str,
    next_step: Callable[[], int],
    session_id: str,
    current_execution_steps: List,
    stream_state: Any = None,
    current_content_holder: Optional[list] = None,
    llm_call_count_holder: Optional[list] = None,
) -> AsyncGenerator[str, None]:
    """纯SSE流运行器 — 小沈 2026-06-09 支持StreamState"""
    from app.services.agent.agent_factory import AgentFactory
    from app.chat_stream import format_agent_sse, save_execution_steps_to_db

    agent = None
    log_tag = f"[{intent_type.upper()}Op]"
    error_label = f"{intent_type}操作执行失败"
    error_type = f'{intent_type}_operation_error'

    try:
        # R1-2修复: AgentFactory.create移入try块,确保失败时finally能保存 — 小沈 2026-06-09
        agent = AgentFactory.create(
            intent_type=intent_type, llm_client=llm_client,
            task_id=task_id, candidates=candidates,
        )
        
        # 【修复 2026-06-09 小沈】设置task_id，支持HTTP阻塞期间的取消检查
        if hasattr(llm_client, 'set_task_id'):
            llm_client.set_task_id(task_id)

        async for event in agent.run_react_cycle(
            task=last_message, context=None,
            task_id=task_id,
        ):
            # 直接to_dict() — dict则直接用（某些agent实现直接yield dict）
            event_dict = event if isinstance(event, dict) else event.to_dict()
            event_type = event_dict.get('type', '')

            # 累积execution_steps
            if event_dict:
                current_execution_steps.append(event_dict)

            # 更新current_content — 小沈 2026-06-09 支持StreamState
            if event_type == 'final':
                content = event_dict.get('response', '') or ''
                if stream_state is not None:
                    stream_state.current_content = content or stream_state.current_content
                elif current_content_holder is not None:
                    current_content_holder[0] = content or current_content_holder[0]
            elif event_type == 'chunk':
                content = event_dict.get('content', '')
                if stream_state is not None:
                    stream_state.current_content = content or stream_state.current_content
                elif current_content_holder is not None:
                    current_content_holder[0] = content or current_content_holder[0]

            # 格式化SSE(仅format，已用event_dict避免二次to_dict)
            sse_data = format_agent_sse(event_dict)

            # yield SSE
            if sse_data:
                yield sse_data

    except asyncio.CancelledError:
        # R3-1修复: CancelledError不是Exception子类,需单独捕获 — 小沈 2026-06-09
        # R3-2修复: 在finally保存前创建IncidentStep(interrupted),防止step丢失 — 小沈 2026-06-09
        # R3-3修复: CancelledError路径补FinalStep,保证客户端收到终态事件 — 小沈 2026-06-10
        logger.info(f"[SSE] 任务 {task_id} 被取消(CancelledError)")
        from app.services.agent.steps import IncidentStep, FinalStep
        interrupted_step = IncidentStep(
            step=next_step(), incident_value='interrupted', message='任务已被中断'
        )
        current_execution_steps.append(interrupted_step.to_dict())
        yield format_agent_sse(interrupted_step.to_dict())
        final_step = FinalStep(step=next_step(), response="任务已被中断")
        current_execution_steps.append(final_step.to_dict())
        yield format_agent_sse(final_step.to_dict())
        if agent is not None:
            agent.status = AgentStatus.COMPLETED

    except Exception as e:
        error_response = await _yield_error_sse(
            error_type=error_type, error_label=error_label, log_tag=log_tag,
            task_id=task_id, e=e, next_step=next_step,
            current_execution_steps=current_execution_steps, session_id=session_id,
        )
        yield error_response

    finally:
        # 统一保存入口：正常、异常、取消都走这里
        # 终止step包括: FinalStep / ErrorStep(blocked,user_rejected,parse_error,
        # empty_response,runtime_error) / IncidentStep(interrupted)
        if current_execution_steps:
            try:
                saved_content = stream_state.current_content if stream_state else (current_content_holder[0] if current_content_holder else "")
                await save_execution_steps_to_db(session_id, current_execution_steps, saved_content)
            except Exception as save_err:
                logger.error(f"[SSE] DB保存失败(steps={len(current_execution_steps)}): {save_err}", exc_info=True)

        if agent is not None:
            if stream_state is not None:
                stream_state.llm_call_count = getattr(agent, "llm_call_count", 0)
            elif llm_call_count_holder is not None:
                llm_call_count_holder[0] = getattr(agent, "llm_call_count", 0)


async def _yield_error_sse(error_type, error_label, log_tag, task_id, e, next_step, current_execution_steps, session_id):
    """内联错误SSE生成(避免外部模块依赖) — P2-18 使用ErrorStep替代手工dict"""
    from app.chat_stream import format_agent_sse
    from app.services.agent.steps import ErrorStep

    step_num = next_step()
    error_step = ErrorStep(
        step=step_num,
        error_type=error_type,
        error_message=str(e),
    )
    current_execution_steps.append(error_step.to_dict())
    # 【修改 2026-06-09 小沈】删除_save调用，统一在finally块中保存
    return format_agent_sse(error_step.to_dict())
