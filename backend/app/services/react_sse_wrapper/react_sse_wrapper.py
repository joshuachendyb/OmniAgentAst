# -*- coding: utf-8 -*-
"""
React SSE Wrapper — 主入口

从 react_sse_wrapper.py 拆出，遵循 SRP：
- 各功能函数独立文件
- 本文件只保留 generate_sse_stream 和 generate_sse_stream_with_retry
- task操作全部在 run_sse_stream 层处理，本文件不碰

Author: 小沈 - 2026-03-26
重构: 小健 - 2026-05-31 — task操作全部移入run_sse_stream层
"""

import json
import asyncio
import traceback
import httpx
from dataclasses import dataclass, field
from typing import List, Dict, Optional, AsyncGenerator, Any, Callable

from app.utils.logger import logger
from app.utils.retry import create_sse_retry_engine
from app.utils.display_name_cache import cache_display_name
from app.utils.time_utils import create_step_counter
from app.services.react_sse_wrapper.log_prompts import log_prompts
from app.services.react_sse_wrapper.run_sse_stream import run_sse_stream
from app.services.react_sse_wrapper.handle_client_disconnect import handle_client_disconnect
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
    current_execution_steps: Optional[List[Dict]] = None
) -> AsyncGenerator[str, None]:
    """SSE 流式生成器 — 主入口，不碰task操作"""
    if current_execution_steps is None:
        current_execution_steps = []
    if config.next_step is None:
        config.next_step = create_step_counter()

    if config.ai_service is None:
        raise ValueError("[AIServiceFactory] react_sse_wrapper 禁止创建 ai_service，必须由 chat_router 传入")
    logger.info(f"[AIServiceFactory] 使用 router 传入的 ai_service（复用）")

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
        session_id = config.session_id or str(uuid.uuid4())
        last_message = config.messages[-1]["content"] if config.messages else ""

        async for sse_chunk in run_sse_stream(
            intent_type=config.intent_type, llm_client=config.ai_service, task_id=config.task_id,
            ai_service=config.ai_service, candidates=config.candidates, last_message=last_message,
            next_step=config.next_step,
            session_id=session_id, current_execution_steps=current_execution_steps,
            current_content=current_content, agent_llm_holder=agent_llm_holder,
        ):
            yield sse_chunk

    except asyncio.CancelledError:
        async for sse_event in handle_client_disconnect(
            config.task_id, config.session_id, current_execution_steps, current_content,
            config.next_step,
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


async def generate_sse_stream_with_retry(
    config: SSEConfig,
    current_execution_steps: Optional[List[Dict]] = None,
) -> AsyncGenerator[str, None]:
    """SSE会话重试 — 主入口"""
    retry_engine = create_sse_retry_engine()
    while True:
        try:
            async for event in generate_sse_stream(
                config, current_execution_steps,
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
