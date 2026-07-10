# -*- coding: utf-8 -*-
"""
chat_openai — Chat API层入口（路由+实现合一）

小健 - 2026-06-07 清理:删除save_step_to_db调用,改用统一save_execution_steps_to_db
task操作只在本层处理:register → interrupt检查 → pause检查 → stream → cancel检查 → cleanup

统一: 小健 - 2026-05-31
更新: 小健 - 2026-06-17 重命名chat_stream_v2→chat_stream，删除版本后缀
合并: 北京老陈 - 2026-06-23 chat_router.py合并入chat_openai.py，删除chat_router.py
"""

import asyncio
import time
import uuid
from dataclasses import dataclass
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse, PlainTextResponse
from typing import Optional
from app.utils.message_id_tracker import get_user_message_id

from app.services import get_service
from app.utils.logger import logger
from app.services.chat.handlers import create_error_response, send_start_step
from app.utils.sse_formatter import format_agent_sse
from app.api.v1.chat.models import ChatRequest
from app.services.agent.steps.base import create_step_counter
from app.services.task.task_registry import register_task, task_cleanup
from app.services.task.task_runtime import (
    task_interrupt_check, task_pause_check_and_yield,
    task_cancel_check_and_yield, check_cancelled,
)
from app.services.chat.stream import run_sse_stream
from app.utils.message_id_tracker import _current_task_id
from app.utils.prompt_logger import get_prompt_logger
from app.services.task.hitl_confirmation import resolve_confirmation

router = APIRouter()

async def validate_chat_config():
    """拷贝自 validate_chat_config.py — 内联入 chat_openai.py 小欧 2026-07-10"""
    from app.utils.logger import logger
    from app.services.ai_config_resolver import get_ai_config_resolver
    try:
        resolver = get_ai_config_resolver()
        is_valid, final_provider, final_model, error_messages = resolver.validate_config()
        if not is_valid:
            return {
                "valid": False,
                "message": f"配置验证失败: {', '.join(error_messages)}",
                "provider": final_provider or "unknown",
                "model": final_model or ""
            }
        return {
            "valid": True,
            "message": f"配置验证通过: {final_provider} ({final_model})",
            "provider": final_provider,
            "model": final_model
        }
    except Exception as e:
        logger.error(f"验证AI服务配置失败: {e}")
        return {
            "valid": False,
            "message": f"验证失败: {str(e)}",
            "provider": "unknown",
            "model": ""
        }
task_router = APIRouter()


@router.post("/chat/stream")
async def chat_stream_endpoint(request: ChatRequest):
    return await chat_stream(request)


@task_router.post("/chat/stream/cancel/{task_id}")
async def cancel_stream_endpoint(task_id: str, session_id: Optional[str] = None):
    from app.services.task.task_runtime import cancel_task
    return await cancel_task(task_id, session_id)


@task_router.post("/chat/stream/pause/{task_id}")
async def pause_stream_endpoint(task_id: str, session_id: Optional[str] = None):
    from app.services.task.task_registry import pause_task
    return await pause_task(task_id, session_id)


@task_router.post("/chat/stream/resume/{task_id}")
async def resume_stream_endpoint(task_id: str, session_id: Optional[str] = None):
    from app.services.task.task_registry import resume_task
    return await resume_task(task_id, session_id)


@task_router.post("/chat/stream/confirm")
async def confirm_stream_endpoint(request: Request):
    return await confirm_operation(request)


@router.get("/chat/validate")
async def validate_config_endpoint():
    return await validate_chat_config()


async def step_start(ai_service, task_id, next_step, user_input, execution_steps, session_id):
    """拷贝自 step_start.py"""
    try:
        start_step = await send_start_step(
            ai_service=ai_service, task_id=task_id, next_step=next_step,
            user_message=user_input, security_check_result={},
        )
        start_dict = start_step.to_dict()
        execution_steps.append(start_dict)
        yield format_agent_sse(start_dict)
    except Exception as e:
        yield create_error_response(error_type="start_failed", error_message=f"start步骤失败: {e}")


async def confirm_operation(request: Request):
    """拷贝自 confirm_operation.py — HITL人工确认"""
    body = await request.json()
    confirm_id = body.get("confirm_id")
    confirmed = body.get("confirmed", True)
    trust_session = body.get("trust_session", False)

    if not confirm_id:
        return {"success": False, "error": "missing confirm_id"}

    ok = resolve_confirmation(confirm_id, confirmed, trust_session)

    if not ok:
        return {"success": False, "error": "confirm_id not found or already processed"}

    return {"success": True}


@dataclass
class StreamState:
    """流式状态 — 【修复P3-5】明确语义 — 北京老陈 2026-06-13"""
    llm_call_count: int = 0
    current_content: str = ""
    step_events: list = None

    def __post_init__(self):
        if self.step_events is None:
            self.step_events = []


async def chat_stream(request: ChatRequest):
    """API层入口 — 小沈 2026-06-08 重构"""
    if not request.messages:
        return PlainTextResponse(
            content=create_error_response(error_type="invalid_request", error_message="消息列表不能为空"),
            media_type="text/event-stream"
        )

    # 【P1-19修复】content可能为None，加or ""防御；空内容直接拒绝 — chendyg 2026-06-26
    user_input = request.messages[-1].content or ""
    if not user_input.strip():
        return PlainTextResponse(
            content=create_error_response(error_type="invalid_request", error_message="消息内容不能为空"),
            media_type="text/event-stream"
        )
    ai_service = get_service()
    session_id = request.session_id or str(uuid.uuid4())

    async def generate():
        """生成器 — 小沈 2026-06-08 重构"""
        task_id = str(uuid.uuid4())
        _current_task_id.set(task_id)
        next_step = create_step_counter()
        execution_steps = []
        state = StreamState()

        prompt_logger = get_prompt_logger()
        prompt_logger.start_request(user_input, session_id)

        # Task 生命周期日志（开始）— 小欧 2026-06-26
        _task_start_time = time.time()
        _user_msg_id = None
        try:
            _user_msg_id = get_user_message_id(session_id)
        except Exception:
            logger.warning(f"[chat] 获取user_message_id失败: session_id={session_id}")
        print(f"INFO: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"[TASK_START]:provider={ai_service.provider} model={ai_service.model}")
        print(f"ask_id={task_id} session_id={session_id} user_message_id={_user_msg_id} |")
        print(f"user_input={user_input}")
        logger.info(
            f"[TASK_START]:provider={ai_service.provider} model={ai_service.model} | "
            f"ask_id={task_id} session_id={session_id} "
            f"user_message_id={_user_msg_id} | "
            f"user_input={user_input}"
        )

        try:
            await register_task(task_id, ai_service)

            is_interrupted, interrupt_msg = await task_interrupt_check(task_id)
            if is_interrupted:
                yield interrupt_msg
                await task_cleanup(task_id, 0)
                return

            async for event in step_start(ai_service, task_id, next_step, user_input, execution_steps, session_id):
                yield event

            # llm_service=ai_service — ai_service是BaseAIService实例
            # 小欧 2026-07-09: llm_client→llm_service重命名
            sse_stream = run_sse_stream(
                llm_service=ai_service, task_id=task_id,
                last_message=user_input,
                next_step=next_step,
                session_id=session_id, current_execution_steps=execution_steps,
                stream_state=state, start_time=_task_start_time,
            )
            cancel_event = asyncio.Event()

            async def _cancel_poller():
                while not cancel_event.is_set():
                    await asyncio.sleep(1)
                    if await check_cancelled(task_id):
                        logger.info(f"[chat_stream] cancel轮询检测到取消, 通知主协程")
                        cancel_event.set()
                        return

            poller_task = asyncio.create_task(_cancel_poller())
            try:
                async for sse_chunk in sse_stream:
                    if cancel_event.is_set():
                        break
                    async for pause_event in task_pause_check_and_yield(task_id, next_step):
                        yield pause_event

                    cancelled_sse = await task_cancel_check_and_yield(
                        task_id, next_step, session_id, execution_steps, state.current_content
                    )
                    if cancelled_sse:
                        yield cancelled_sse
                        break
                    yield sse_chunk
                else:
                    prompt_logger.mark_completed()
            finally:
                # break/cancel 路径也标记已完成,避免遗漏 — 小欧 2026-07-01
                current_log = prompt_logger.get_current_log()
                if current_log and current_log["基本信息"].get("状态") == "处理中":
                    prompt_logger.mark_completed()
                cancel_event.set()
                poller_task.cancel()
                try:
                    await poller_task
                except asyncio.CancelledError:
                    pass
                await sse_stream.aclose()

        except Exception as e:
            logger.error(f"[chat_stream] Error: {e}", exc_info=True)
            prompt_logger.mark_error(str(e))
            yield create_error_response(error_type="router_error", error_message=f"路由异常: {str(e)}")
        finally:
            await task_cleanup(task_id, state.llm_call_count)
            prompt_logger.save()

    return StreamingResponse(generate(), media_type="text/event-stream")
