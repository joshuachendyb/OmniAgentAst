# -*- coding: utf-8 -*-
"""
React SSE Wrapper — 主入口

从 react_sse_wrapper.py 拆出，遵循 SRP：
- 各功能函数独立文件
- 本文件只保留 generate_sse_stream 和 generate_sse_stream_with_retry

Author: 小沈 - 2026-03-26
重构: 2026-05-31 小健 - SSEConfig参数分组（问题16修复）
"""

import json
import asyncio
import uuid
import traceback
import httpx
from dataclasses import dataclass, field
from typing import List, Dict, Optional, AsyncGenerator, Any, Callable

from app.utils.logger import logger
from app.utils.retry import create_sse_retry_engine
from app.utils.display_name_cache import cache_display_name
from app.chat_stream.incident_handler import check_and_yield_if_interrupted, check_and_yield_if_paused
from app.utils.time_utils import create_step_counter
from app.services.task_lifecycle import TaskLifecycleManager

from app.services.react_sse_wrapper.task_registry import running_tasks_lock, running_tasks
from app.services.react_sse_wrapper.log_prompts import log_prompts
from app.services.react_sse_wrapper.run_sse_stream import run_sse_stream
from app.services.react_sse_wrapper.handle_client_disconnect import handle_client_disconnect
from app.services.react_sse_wrapper.cleanup_task import cleanup_task
from app.services.react_sse_wrapper.save_step_to_db import save_step_to_db


@dataclass
class SSEConfig:
    """SSE参数分组 — 消除14参数函数SLAP违反 小健2026-05-31"""
    messages: List[Dict[str, str]]
    intent_type: str = "generic"
    confidence: float = 0.0
    candidates: List[str] = field(default_factory=list)
    provider: Optional[str] = None
    model: Optional[str] = None
    temperature: float = 0.7
    task_id: Optional[str] = None
    session_id: Optional[str] = None
    ai_service: Optional[Any] = None
    next_step: Optional[Callable[[], int]] = None


async def generate_sse_stream(
    config: SSEConfig,
    running_tasks: Optional[Dict[str, Any]] = None,
    running_tasks_lock: Optional[asyncio.Lock] = None,
    current_execution_steps: Optional[List[Dict]] = None
) -> AsyncGenerator[str, None]:
    """SSE 流式生成器 — 主入口"""
    if running_tasks is None or running_tasks_lock is None:
        raise ValueError("running_tasks and running_tasks_lock must be provided")
    if current_execution_steps is None:
        current_execution_steps = []
    if config.next_step is None:
        config.next_step = create_step_counter()
    if not config.task_id:
        config.task_id = str(uuid.uuid4())

    if config.ai_service is None:
        raise ValueError("[AIServiceFactory] react_sse_wrapper 禁止创建 ai_service，必须由 chat_router 传入")
    logger.info(f"[AIServiceFactory] 使用 router 传入的 ai_service（复用）")

    manager = TaskLifecycleManager(running_tasks, running_tasks_lock)
    await manager.register(config.task_id, config.ai_service)

    llm_call_count = 0
    agent_llm_holder: Dict[str, Any] = {"n": 0}
    current_content: str = ""
    display_name = f"{config.ai_service.provider} ({config.ai_service.model})"
    if config.session_id:
        cache_display_name(config.session_id, display_name)

    logger.info(f"[LLM Total Counter] ====== New conversation started, counter reset to 0 ======")

    if config.intent_type not in ("", "generic") and config.ai_service:
        await log_prompts(config.messages, config.intent_type, config.confidence, config.session_id, config.task_id)

    try:
        is_interrupted, interrupt_msg = await check_and_yield_if_interrupted(config.task_id, running_tasks, running_tasks_lock)
        if is_interrupted:
            yield interrupt_msg
            await save_step_to_db(interrupt_msg, config.session_id, current_execution_steps, current_content or "")
            return

        async for pause_event in check_and_yield_if_paused(config.task_id, running_tasks, running_tasks_lock):
            yield pause_event
            await save_step_to_db(pause_event, config.session_id, current_execution_steps, current_content or "")

        session_id = config.session_id or str(uuid.uuid4())
        last_message = config.messages[-1]["content"] if config.messages else ""

        async for sse_chunk in run_sse_stream(
            intent_type=config.intent_type, llm_client=config.ai_service, task_id=config.task_id,
            ai_service=config.ai_service, candidates=config.candidates, last_message=last_message,
            next_step=config.next_step, running_tasks=running_tasks, running_tasks_lock=running_tasks_lock,
            session_id=session_id, current_execution_steps=current_execution_steps,
            current_content=current_content, agent_llm_holder=agent_llm_holder,
        ):
            yield sse_chunk

    except asyncio.CancelledError:
        async for sse_event in handle_client_disconnect(
            config.task_id, session_id, current_execution_steps, current_content,
            config.next_step, running_tasks, running_tasks_lock,
        ):
            yield sse_event

    except Exception as e:
        logger.error(f"流式响应异常：task_id={config.task_id}, error={e}", exc_info=True)
        from app.services.react_sse_wrapper.yield_error_sse import yield_error_sse
        error_response = await yield_error_sse(
            error_type="stream_error", error_label="流式响应异常", log_tag="[SSE]",
            task_id=config.task_id, e=e, next_step=config.next_step, ai_service=config.ai_service,
            current_execution_steps=current_execution_steps, session_id=config.session_id,
        )
        yield error_response

    finally:
        await cleanup_task(config.task_id, manager, agent_llm_holder, llm_call_count)


async def generate_sse_stream_with_retry(
    config: SSEConfig,
    running_tasks: Optional[Dict[str, Any]] = None,
    running_tasks_lock: Optional[asyncio.Lock] = None,
    current_execution_steps: Optional[List[Dict]] = None,
) -> AsyncGenerator[str, None]:
    """SSE会话重试 — 主入口"""
    retry_engine = create_sse_retry_engine()
    while True:
        try:
            async for event in generate_sse_stream(
                config, running_tasks, running_tasks_lock, current_execution_steps,
            ):
                yield event
            return
        except asyncio.CancelledError:
            return
        except (asyncio.TimeoutError, ConnectionError, httpx.RemoteProtocolError,
                httpx.ConnectError, httpx.ReadTimeout) as e:
            if retry_engine.exhausted:
                logger.error(f"[SSE重试] 耗尽，放弃: {e}")
                error_data = {"type": "error", "error": {"type": "connection_error",
                    "message": "SSE连接失败，重试耗尽", "detail": str(e)}}
                yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"
                return
            delay = retry_engine.current_delay
            logger.warning(f"[SSE重试] 第{retry_engine.attempt_count}次，等待{delay:.0f}s: {e}")
            await asyncio.sleep(delay)
            retry_engine.record_attempt()
        except Exception as e:
            error_data = {"type": "error", "error": {"type": "unknown_error",
                "message": str(e), "detail": traceback.format_exc()}}
            yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"
            return
