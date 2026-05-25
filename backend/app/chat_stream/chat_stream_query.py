# -*- coding: utf-8 -*-
"""
流式问答处理模块

从 chat_stream.py 的 generate() 函数中拆分的流式问答逻辑
用于处理问答类消息（无文件操作）

Author: 小沈 - 2026-03-22
"""

import json
import asyncio
from typing import List, Dict, Optional, Any, Callable, AsyncGenerator, Tuple

from app.utils.retry_controller import RetryController
from app.utils.idle_timeout import IdleTimeoutIterator, IdleTimeoutError
from app.chat_stream.chat_helpers import create_timestamp, create_final_response
from app.chat_stream.error_handler import create_error_response
from app.services.agent.reasoning_steps import StepFactory
from app.chat_stream.sse_formatter import format_sse_event
from app.chat_stream.incident_handler import (
    create_incident_data,
    check_and_yield_if_paused,
    check_and_yield_if_interrupted,
)
from app.utils.logger import logger
from app.config import get_config


def _build_history(
    messages: Any,
) -> List[Dict[str, str]]:
    """从request.messages构建历史消息列表

    使用场景:
    - chat_stream_query中构建LLM调用所需的history参数
    - 所有需要将ChatRequest.messages转为history格式的场景

    使用示例:
        history = _build_history(request.messages)

    返回数据说明:
    - 返回List[Dict[str, str]]，每个元素为{"role": ..., "content": ...}
    - 如果messages只有1条，返回空列表（仅当前消息，无历史）

    Author: 小沈 - 2026-03-22
    """
    history: List[Dict[str, str]] = []
    if len(messages) > 1:
        for msg in messages[:-1]:
            history.append({"role": msg.role, "content": msg.content})
    return history


def _init_retry_state(
    ai_service: Any,
    max_retries: int = 3,
) -> Dict[str, Any]:
    """初始化重试循环所需的状态变量

    使用场景:
    - chat_stream_query中重试循环前的状态初始化
    - 需要统一初始化重试控制器、超时时间、保护计数器的场景

    使用示例:
        state = _init_retry_state(ai_service, max_retries=3)
        retry_controller = state["retry_controller"]

    返回数据说明:
    - chat_timeout: float, AI服务超时时间（秒）
    - max_retries: int, 最大重试次数
    - retry_controller: RetryController实例
    - ai_call_successful: bool, 初始为False
    - last_error: Optional[str], 初始为None
    - last_error_type: Optional[str], 初始为None
    - full_content: str, 初始为空
    - chunk_count: int, 初始为0
    - max_chunk_count: int, 最大chunk数量(5000)
    - empty_content_count: int, 连续空content次数(0)
    - max_empty_content_count: int, 最大连续空content次数(100)

    Author: 小沈 - 2026-03-22
    """
    chat_timeout = ai_service.timeout if hasattr(ai_service, 'timeout') and ai_service.timeout else 60
    return {
        "chat_timeout": float(chat_timeout),
        "max_retries": max_retries,
        "retry_controller": RetryController(max_retries=max_retries),
        "ai_call_successful": False,
        "last_error": None,
        "last_error_type": None,
        "full_content": "",
        "chunk_count": 0,
        "max_chunk_count": 5000,
        "empty_content_count": 0,
        "max_empty_content_count": 100,
    }


async def _execute_retry_loop(
    ai_service: Any,
    history: List[Dict[str, str]],
    task_id: str,
    running_tasks: dict,
    running_tasks_lock: asyncio.Lock,
    next_step: Callable[[], int],
    current_execution_steps: List[Dict],
    save_execution_steps_to_db: Callable,
    add_step_and_save: Callable,
    state: Dict[str, Any],
    llm_call_count: int,
    last_is_reasoning: Optional[bool],
) -> AsyncGenerator[Tuple[str, Optional[Dict[str, Any]]], None]:
    """执行重试循环，yield (sse_event, step_data) 元组

    使用场景:
    - chat_stream_query中重试循环的核心逻辑
    - 需要IdleTimeoutIterator包装流式迭代并自动重试的场景

    使用示例:
        async for sse_event, step_data in _execute_retry_loop(...):
            if sse_event:
                yield sse_event

    返回数据说明:
    - yield: Tuple[str, Optional[Dict[str, Any]]]
      - sse_event: SSE格式事件字符串，可直接yield给前端
      - step_data: 可选的步骤数据，用于DB保存
    - 循环结束后通过修改state字典传递最终状态

    Author: 小沈 - 2026-03-22
    """
    retry_controller = state["retry_controller"]
    chat_timeout = state["chat_timeout"]
    max_retries = state["max_retries"]

    for retry_attempt in range(max_retries + 1):
        if retry_attempt > 0:
            retry_data = create_incident_data(
                'retrying',
                f'请求超时，正在重试 ({retry_attempt}/{max_retries})...',
                step=next_step()
            )
            yield (f"data: {json.dumps(retry_data)}\n\n", None)
            await add_step_and_save(retry_data, None)

        full_content = ""
        chunk_count = 0
        has_received_content = False
        empty_content_count = 0
        idle_timeout_stream = None

        try:
            llm_call_count += 1
            idle_timeout_stream = IdleTimeoutIterator(
                ai_service.chat_stream(message="", history=history),
                timeout_seconds=chat_timeout,
                name=f"AI-Stream-{retry_attempt + 1}"
            )

            async for chunk in idle_timeout_stream:
                chunk_count += 1

                if chunk_count > state["max_chunk_count"]:
                    logger.warning(f"[AI Call] 超过最大chunk数量 {state['max_chunk_count']}，强制结束")
                    break
                if not chunk.content and getattr(chunk, 'is_reasoning', False):
                    empty_content_count += 1
                    if empty_content_count > state["max_empty_content_count"]:
                        logger.warning(f"[AI Call] 连续 {state['max_empty_content_count']} 次无实际内容，强制结束")
                        break
                else:
                    empty_content_count = 0

                async with running_tasks_lock:
                    if running_tasks.get(task_id, {}).get("cancelled", False):
                        interrupted_data = create_incident_data(
                            'interrupted', '任务已被中断', step=next_step()
                        )
                        yield (f"data: {json.dumps(interrupted_data)}\n\n", None)
                        return

                async for pause_event in check_and_yield_if_paused(
                    task_id, running_tasks, running_tasks_lock, next_step
                ):
                    yield (pause_event, None)

                if chunk.stream_error:
                    state["last_error"] = chunk.stream_error
                    state["last_error_type"] = getattr(chunk, 'stream_error_type', 'unknown')
                    logger.warning(f"[AI Call] 流式请求返回错误: {chunk.stream_error}, error_type: {state['last_error_type']}")
                    logger.error(f"[AI Call] 检测到错误，不重试: {chunk.stream_error}")
                    state["ai_call_successful"] = False
                    break

                current_is_reasoning = getattr(chunk, 'is_reasoning', False)
                if chunk.content:
                    chunk_step = StepFactory.create_chunk_step(
                        step=next_step(), content=chunk.content, is_reasoning=current_is_reasoning
                    )
                    chunk_data = chunk_step.to_dict()
                    current_execution_steps.append(chunk_data)
                    has_received_content = True
                    full_content += chunk.content

                    if last_is_reasoning != current_is_reasoning:
                        try:
                            await save_execution_steps_to_db(current_execution_steps, full_content)
                        except Exception as e:
                            logger.error(f"[Save] is_reasoning变化保存失败: {e}", exc_info=True)
                        last_is_reasoning = current_is_reasoning

                    yield (f"data: {json.dumps(chunk_data)}\n\n", None)

                if chunk.is_done:
                    break

        except IdleTimeoutError as e:
            state["last_error"] = str(e)
            state["last_error_type"] = 'idle_timeout'
            elapsed = idle_timeout_stream.get_elapsed_time() if idle_timeout_stream else chat_timeout
            logger.warning(f"[AI Call] 第{retry_attempt + 1}次调用空闲超时：{elapsed:.1f}秒无内容")

        except Exception as e:
            state["last_error"] = str(e)
            state["last_error_type"] = 'network_error'
            logger.error(f"[AI Call] 第{retry_attempt + 1}次调用异常: {e}")

        if has_received_content:
            state["ai_call_successful"] = True
            state["full_content"] = full_content
            break

        elif state["last_error_type"] == 'idle_timeout':
            if retry_controller.can_retry():
                retry_controller.increment_retry()
                continue
            else:
                logger.error(f"[AI Call] 第{retry_attempt + 1}次调用空闲超时，已达最大重试次数{max_retries}")
                state["ai_call_successful"] = False
                break

        elif state["last_error_type"] == 'network_error':
            if retry_controller.can_retry():
                retry_controller.increment_retry()
                continue
            else:
                logger.error(f"[AI Call] 第{retry_attempt + 1}次调用网络错误，已达最大重试次数{max_retries}")
                state["ai_call_successful"] = False
                break

        elif state["last_error"]:
            logger.error(f"[AI Call] 第{retry_attempt + 1}次调用失败（其他错误）: {state['last_error']}")
            state["ai_call_successful"] = False
            break

        else:
            if has_received_content and full_content.strip():
                state["ai_call_successful"] = True
                state["full_content"] = full_content
                break
            else:
                logger.warning(f"[AI Call] 第{retry_attempt + 1}次调用完成但无内容（流结束，模型未返回有效内容）")
                if retry_controller.can_retry():
                    retry_controller.increment_retry()
                    continue
                else:
                    error_step_value = next_step()
                    error_message = "模型未能生成有效回复，请尝试更换问题或稍后重试"
                    error_response = create_error_response(
                        error_type="empty_response",
                        error_message=error_message,
                        model=ai_service.model,
                        provider=ai_service.provider,
                        recoverable=True,
                        retry_after=3,
                        step=error_step_value
                    )
                    error_step_obj = StepFactory.create_error_step(
                        step=error_step_value,
                        error_type='empty_response',
                        error_message=error_message,
                        model=ai_service.model,
                        provider=ai_service.provider,
                        recoverable=True,
                        retry_after=3
                    )
                    error_step_dict = error_step_obj.to_dict()
                    yield (error_response, error_step_dict)
                    await add_step_and_save(error_step_dict, f"错误: {error_message}")
                    return


async def _handle_retry_exhausted(
    ai_service: Any,
    state: Dict[str, Any],
    next_step: Callable[[], int],
    add_step_and_save: Callable,
) -> Optional[Tuple[str, Dict[str, Any]]]:
    """重试耗尽时的错误处理

    使用场景:
    - chat_stream_query中重试循环结束后的失败处理
    - ai_call_successful为False时调用

    使用示例:
        result = await _handle_retry_exhausted(ai_service, state, next_step, add_step_and_save)
        if result:
            error_sse, error_dict = result
            yield error_sse

    返回数据说明:
    - None: 不需要处理（成功场景）
    - Tuple: (error_sse_event, error_step_dict)，需要yield给前端并保存DB

    Author: 小沈 - 2026-03-22
    """
    if state["ai_call_successful"]:
        return None

    logger.error(f"[AI Call] 重试失败，ai_call_successful={state['ai_call_successful']}")
    last_error = state.get("last_error")
    last_error_type = state.get("last_error_type")

    error_step_value = next_step()
    error_step_obj = StepFactory.create_error_step(
        step=error_step_value,
        error_type=last_error_type or "retry_failed",
        error_message=last_error or "模型未能生成有效回复，请尝试更换问题或稍后重试",
        recoverable=True,
        model=ai_service.model,
        provider=ai_service.provider,
        retry_after=3
    )
    error_step_dict = error_step_obj.to_dict()
    error_response = format_sse_event('error', error_step_value, error_step_dict)

    if last_error:
        logger.error(f"[AI Call] 所有重试失败，最后错误: {last_error}, 类型: {last_error_type}")
    else:
        logger.error(f"[AI Call] 所有重试失败，无有效响应（模型返回空内容）")

    await add_step_and_save(error_step_dict, f"错误: {error_step_dict['error_message']}")
    return (error_response, error_step_dict)


async def chat_stream_query(
    request,
    ai_service,
    task_id: str,
    llm_call_count: int,
    current_execution_steps: List[Dict],
    current_content: str,
    last_is_reasoning: Optional[bool],
    last_message: str,
    running_tasks: dict,
    running_tasks_lock: asyncio.Lock,
    next_step: Callable[[], int],
    display_name: str,
    session_id: Optional[str],
    save_execution_steps_to_db: Callable,
    add_step_and_save: Callable,
) -> AsyncGenerator[str, None]:
    """流式问答处理函数，处理问答类消息的流式响应（无文件操作）

    流程：start → thought → chunk → final

    Author: 小沈 - 2026-03-22
    """
    async with running_tasks_lock:
        if running_tasks.get(task_id, {}).get("cancelled", False):
            interrupted_data = create_incident_data('interrupted', '任务已被中断', step=next_step())
            yield f"data: {json.dumps(interrupted_data)}\n\n"
            return

    history = _build_history(request.messages)
    state = _init_retry_state(ai_service, max_retries=3)

    async for sse_event, step_data in _execute_retry_loop(
        ai_service, history, task_id, running_tasks, running_tasks_lock,
        next_step, current_execution_steps, save_execution_steps_to_db,
        add_step_and_save, state, llm_call_count, last_is_reasoning,
    ):
        if sse_event:
            yield sse_event

    retry_result = await _handle_retry_exhausted(ai_service, state, next_step, add_step_and_save)
    if retry_result:
        error_sse, _ = retry_result
        yield error_sse
        return

    full_content = state["full_content"]
    final_step_value = next_step()
    final_step_obj = StepFactory.create_final_step(step=final_step_value, response=full_content)
    final_step_dict = final_step_obj.to_dict()
    final_step_dict.update({"model": ai_service.model, "provider": ai_service.provider})
    current_execution_steps.append(final_step_dict)
    await save_execution_steps_to_db(current_execution_steps, full_content)

    yield create_final_response(
        content=full_content, model=ai_service.model,
        provider=ai_service.provider, display_name=display_name,
        step=final_step_value
    )
