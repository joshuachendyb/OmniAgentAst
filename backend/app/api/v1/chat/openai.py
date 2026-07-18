# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-16 - 小欧 - StreamState 增 current_thought 字段, 运行期持有 thought 值
# 2026-07-18 - 小欧 - 消费者完全退出日志层: 删除prompt_logger全部5处引用(start_request/mark_completed/mark_error/save/import)
"""
chat_openai — Chat API层入口（路由+实现合一）

小健 - 2026-06-07 清理:删除save_step_to_db调用,改用统一save_execution_steps_to_db
task操作只在本层处理:register → cancel检查 → pause检查 → stream → cancel检查 → cleanup

统一: 小健 - 2026-05-31
更新: 小健 - 2026-06-17 重命名chat_stream_v2→chat_stream，删除版本后缀
合并: 北京老陈 - 2026-06-23 chat_router.py合并入chat_openai.py，删除chat_router.py
更新: 小欧 - 2026-07-16 统一TaskID: 新增generate_task_id(), :181改用, 修正ask_id→task_id笔误
"""

import asyncio
import time
import uuid
from dataclasses import dataclass
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse, PlainTextResponse
from typing import Optional
from app.services.chat.storage import get_user_message_id

from app.services import get_service
from app.logger import logger
from app.services.chat.handlers import create_error_response, send_start_step
from app.utils.sse_formatter import format_agent_sse
from app.api.v1.chat.models import ChatRequest
from app.services.agent.steps.base import create_step_counter
from app.services.task.task_registry import register_task
from app.services.task.task_runtime import (
    task_cancel_check, task_pause_check_and_yield,
    task_cancel_check_and_yield, check_cancelled,
)
from app.services.chat.stream import stream_reader
from app.services.agent.agent_runner import run_agent_in_background
from app.services.agent.universal_agent import UniversalAgent
from app.services.task.task_state import create_stream_buffer, get_stream_buffer
from app.services.task.task_context import _current_task_id, session_id_var
from app.services.task.hitl_confirmation import resolve_confirmation

router = APIRouter()

# 后台 agent 任务强引用表: asyncio 仅持有 Task 弱引用, 若 SSE 消费者(generate)断开后任务再无强引用,
# 会被 GC 回收并取消, 导致 run_agent_in_background 的 finally(DB 保存)被打断、结果丢失(问题2)。
# 与 agent_runner._background_tasks 双重保险(后者 caller-agnostic): 本表在调用点持有引用,
# done 时 discard 防内存泄漏 — 小欧 2026-07-13
_agent_tasks: set = set()


def generate_task_id() -> str:
    """生成统一格式 task-{hex}，全链路唯一贯通 — 小欧 2026-07-16"""
    return f"task-{uuid.uuid4().hex}"


async def validate_chat_config():
    """拷贝自 validate_chat_config.py — 内联入 chat_openai.py 小欧 2026-07-10"""
    from app.logger import logger
    from app.services.model.resolver import get_ai_config_resolver
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
    current_thought: str = ""  # 小欧 2026-07-16
    step_events: list = None

    def __post_init__(self):
        if self.step_events is None:
            self.step_events = []


async def chat_stream(request: ChatRequest):
    """API层入口 — 小沈 2026-06-08 重构
    北京老陈 2026-07-12: agent 执行与 SSE 传输解耦 — 小欧 2026-07-12

    流程：注册控制态 + 创建流态缓冲 + 启动后台生产者(agent) + 消费者(SSE)读缓冲
    """
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
        """SSE 消费者生成器 — 小欧 2026-07-12"""
        task_id = generate_task_id()
        _current_task_id.set(task_id)
        # 注入会话标识到日志上下文, 使本轮请求全链路日志带 session_id, 便于按会话过滤排查 — 小欧 2026-07-17
        session_id_var.set(session_id)
        next_step = create_step_counter()
        execution_steps = []
        state = StreamState()

        # Task 生命周期日志（开始）— 小欧 2026-06-26
        _task_start_time = time.time()
        _user_msg_id = None
        try:
            _user_msg_id = get_user_message_id(session_id)
        except Exception:
            logger.warning(f"[chat] 获取user_message_id失败: session_id={session_id}")
        print(f"INFO: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"[TASK_START]:provider={ai_service.provider} model={ai_service.model}")
        print(f"task_id={task_id} session_id={session_id} user_message_id={_user_msg_id} |")
        print(f"user_input={user_input}")
        logger.info(
            f"[TASK_START]:provider={ai_service.provider} model={ai_service.model} | "
            f"task_id={task_id} session_id={session_id} "
            f"user_message_id={_user_msg_id} | "
            f"user_input={user_input}"
        )

        try:
            # 创建流态缓冲 + 注册控制态 — 小欧 2026-07-12
            buffer = create_stream_buffer(task_id)
            await register_task(task_id, ai_service)

            is_cancelled, cancel_msg = await task_cancel_check(task_id)
            if is_cancelled:
                yield cancel_msg
                return

            # 发送 start 步骤 — 小沈 2026-06-08
            async for event in step_start(ai_service, task_id, next_step, user_input, execution_steps, session_id):
                yield event

            # 启动后台生产者(agent)，与 SSE 传输解耦 — 北京老陈 2026-07-12 小欧 2026-07-12
            agent = UniversalAgent(llm_client=ai_service, task_id=task_id)
            # 持有强引用，防 GC 回收导致任务被取消→打断 DB 保存(问题2修复) — 小欧 2026-07-13
            bg_task = asyncio.create_task(run_agent_in_background(
                agent, task_id, user_input, None, next_step, session_id, state, _task_start_time))
            _agent_tasks.add(bg_task)
            bg_task.add_done_callback(_agent_tasks.discard)

            # 消费者：读缓冲 + 注入 pause/cancel 检查
            async for sse_chunk in _stream_with_control(buffer, task_id, next_step, session_id, execution_steps, state):
                yield sse_chunk
        except asyncio.CancelledError:
            # 客户端断开：静默返回，agent 后台继续运行 — 北京老陈 2026-07-12 小欧 2026-07-12
            logger.info(f"[chat_stream] 客户端断开(task={task_id})，agent 后台继续")
            return
        except Exception as e:
            logger.error(f"[chat_stream] Error: {e}", exc_info=True)
            yield create_error_response(error_type="router_error", error_message=f"路由异常: {str(e)}")

    return StreamingResponse(generate(), media_type="text/event-stream")


async def _stream_with_control(buffer, task_id: str, next_step, session_id: str,
                               execution_steps: list, state=None, after_seq: int = 0):
    """SSE 消费者包装：读缓冲 + 注入 pause/cancel 检查 — 小欧 2026-07-12

    首次请求(after_seq=0)与重连请求(after_seq=N)共用本函数，DRY。
    客户端断开时 CancelledError 向上传播，由 generate() 捕获（不标记完成）。
    """
    async for sse_chunk in stream_reader(buffer, task_id, after_seq):
        async for pause_event in task_pause_check_and_yield(task_id, next_step):
            yield pause_event
        cancelled_sse = await task_cancel_check_and_yield(
            task_id, next_step, session_id, execution_steps,
            state.current_content if state else "")
        if cancelled_sse:
            yield cancelled_sse
            return
        yield sse_chunk


@router.get("/chat/stream/{task_id}")
async def chat_stream_reconnect(task_id: str, session_id: str = None, after_seq: int = 0):
    """SSE 重连端点：读同一任务的流态缓冲，不启动新 agent — 北京老陈 2026-07-12 小欧 2026-07-12

    前端断线重连(最多3次)走此端点；3次全失败由前端发 cancel 置为取消。
    """
    buffer = get_stream_buffer(task_id)
    if not buffer:
        return PlainTextResponse(
            content=create_error_response(error_type="not_found", error_message="任务不存在或已结束"),
            media_type="text/event-stream"
        )
    next_step = create_step_counter()
    return StreamingResponse(
        _stream_with_control(buffer, task_id, next_step, session_id or "", [], None, after_seq),
        media_type="text/event-stream"
    )
