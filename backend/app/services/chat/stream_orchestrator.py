# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-13 - 小欧 - 新建: A7 聊天流编排器(方案4.7.3步骤1)。从 api/v1/chat/openai.py 一次性全迁编排逻辑
#   (chat_stream generate 主体 / _stream_with_control / StreamState / generate_task_id / validate_chat_config /
#   _agent_tasks / step_start), 仅改导入归属, 业务逻辑一字不改(禁止 backward, 无兼容 shim)。依赖路径以真实代码为准:
#   create_stream_buffer/get_stream_buffer 取 app.services.task.task_state, task_cancel_check* 取 app.services.task.task_runtime。
#   orchestrator 不依赖 api/v1 的 DTO(API 层解包 ChatRequest 后传原始参数)。
# 2026-08-13 - 小沈 - BUG-32修复(三堂会审): except Exception 块内 cancel bg_task, 避免后台 agent 继续运行但前端收到错误的
#   状态不一致; bg_task 预初始化 None 防 NameError; cancel 后 run_agent_in_background 的 finally 仍执行 DB 保存(已产出结果不丢失)
# 2026-08-13 - 小沈 - P4 agent→chat反向引用回调解耦: agent_runner 删除对 chat 模块的直接 import,
#   持久化回调(allocate_and_insert_message/append_execution_step/finalize_message/save_execution_steps_to_db/
#   _load_previous_messages/_log_task_end)由本编排器构造 db_ops SimpleNamespace 注入 run_agent_in_background,
#   依赖方向变为 chat→agent 单向。6个属性与原 agent_runner 直接 import 的6个chat函数一一对应,KISS-DIRECT。
"""
stream_orchestrator — 聊天流编排器(services 层)

职责(方案4.7.3, 小欧 2026-08-13): 负责任务生命周期、Agent 后台启动、SSE 消费编排。
API 层只保留路由薄壳, 编排逻辑单一归属本模块(SRP/SLAP)。
"""
import asyncio
import time
import uuid
from dataclasses import dataclass
from typing import Optional, AsyncGenerator

from app.services import get_service
from app.services.model.resolver import get_ai_config_resolver
from app.logger import logger, log_and_print
from app.services.chat.handlers import create_error_response, send_start_step
from app.utils.sse_formatter import format_agent_sse
from app.services.agent.steps.base import create_step_counter
from app.services.task.task_registry import register_task
from app.services.task.task_runtime import (
    task_cancel_check, task_pause_check_and_yield, task_cancel_check_and_yield,
)
from app.services.chat.stream import stream_reader
from app.services.agent.agent_runner import run_agent_in_background
from app.services.agent.universal_agent import UniversalAgent
from app.services.agent.steps.final_step import FinalStep
from app.services.task.task_state import create_stream_buffer, get_stream_buffer
from app.services.task.task_context import _current_task_id
from app.logger.shared_handler import set_session_id
from app.services.chat.storage import get_user_message_id, allocate_and_insert_message, append_execution_step, finalize_message
from app.services.chat.handlers import save_execution_steps_to_db
from app.services.chat.stream import _load_previous_messages, _log_task_end


# 后台 agent 任务强引用表: asyncio 仅持有 Task 弱引用, 若 SSE 消费者(generate)断开后任务再无强引用,
# 会被 GC 回收并取消, 导致 run_agent_in_background 的 finally(DB 保存)被打断、结果丢失(问题2)。
# 与 agent_runner._background_tasks 双重保险(后者 caller-agnostic): 本表在调用点持有引用,
# done 时 discard 防内存泄漏 — 小欧 2026-07-13(自 openai.py 迁入)
_agent_tasks: set = set()


def generate_task_id() -> str:
    """生成统一格式 task-{hex}，全链路唯一贯通 — 小欧 2026-07-16(自 openai.py 迁入)"""
    return f"task-{uuid.uuid4().hex}"


async def validate_chat_config():
    """聊天配置校验 — 自 api/v1/chat/openai.py 迁入 orchestrator — 小欧 2026-08-13"""
    from app.logger import logger
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


@dataclass
class StreamState:
    """流式状态 — 【修复P3-5】明确语义 — 北京老陈 2026-06-13(自 openai.py 迁入)"""
    llm_call_count: int = 0
    current_content: str = ""
    current_thought: str = ""  # 小欧 2026-07-16
    step_events: list = None

    def __post_init__(self):
        if self.step_events is None:
            self.step_events = []


async def chat_stream_orchestrator(
    messages: list,
    session_id: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """聊天流编排入口：负责任务生命周期、Agent 启动、SSE 消费。

    由 API 层解包 ChatRequest 后以 (messages, session_id) 调用；services 层不反向依赖 api/v1 DTO。
    """
    if not messages:
        yield create_error_response(error_type="invalid_request", error_message="消息列表不能为空")
        return
    user_input = messages[-1].content or ""
    if not user_input.strip():
        yield create_error_response(error_type="invalid_request", error_message="消息内容不能为空")
        return

    ai_service = get_service()
    session_id = session_id or str(uuid.uuid4())
    _model_warning = get_ai_config_resolver().pop_model_warning()

    task_id = generate_task_id()
    _task_token = _current_task_id.set(task_id)  # try/finally reset, 防 ContextVar 泄漏(方案4.7.3与A4对齐)
    set_session_id(session_id)
    next_step = create_step_counter()
    execution_steps = []
    state = StreamState()

    _task_start_time = time.time()
    _user_msg_id = None
    try:
        _user_msg_id = get_user_message_id(session_id)
    except Exception:
        logger.warning(f"[chat] 获取user_message_id失败: session_id={session_id}")
    log_and_print(f"INFO: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    log_and_print(
        f"[TASK_START] provider={ai_service.provider} model={ai_service.model} |\n "
        f"task_id={task_id} session_id={session_id} "
        f"user_message_id={_user_msg_id} |\n "
        f"user_input={user_input}"
    )

    bg_task = None  # BUG-32修复: 预初始化, 防 except 块 NameError — 小沈 2026-08-13
    try:
        buffer = create_stream_buffer(task_id)
        await register_task(task_id, ai_service)

        is_cancelled, cancel_msg = await task_cancel_check(task_id)
        if is_cancelled:
            yield cancel_msg
            return

        async for event in step_start(ai_service, task_id, next_step, user_input, execution_steps, session_id, warning=_model_warning):
            yield event

        if _model_warning:
            _final = FinalStep(
                step=next_step(), response="",
                outcome="failed",
                error_type="config_error",
                error_message=_model_warning,
                model=ai_service.model, provider=ai_service.provider,
                display_name=f"{ai_service.provider} ({ai_service.model})",
            )
            yield format_agent_sse(_final.to_dict())
            return

        agent = UniversalAgent(llm_client=ai_service, task_id=task_id)
        # P4: 构造 db_ops 命名空间注入 agent_runner, 消除 agent→chat 反向依赖 — 小沈 2026-08-13
        #   6个属性对应原 agent_runner 直接 import 的6个chat函数, KISS-DIRECT(一个对象替代6个回调)
        import types as _types
        _db_ops = _types.SimpleNamespace(
            allocate_and_insert=allocate_and_insert_message,
            append_step=append_execution_step,
            finalize=finalize_message,
            save_steps=save_execution_steps_to_db,
            load_previous=_load_previous_messages,
            log_task_end=_log_task_end,
        )
        # 持有强引用，防 GC 回收导致任务被取消→打断 DB 保存(问题2修复) — 小欧 2026-07-13
        bg_task = asyncio.create_task(run_agent_in_background(
            agent, task_id, user_input, None, next_step, session_id, state, _task_start_time,
            db_ops=_db_ops))
        _agent_tasks.add(bg_task)
        bg_task.add_done_callback(_agent_tasks.discard)

        async for sse_chunk in _stream_with_control(buffer, task_id, next_step, session_id, execution_steps, state):
            yield sse_chunk
    except asyncio.CancelledError:
        # 客户端断开：静默返回，agent 后台继续运行 — 北京老陈 2026-07-12 小欧 2026-07-12
        logger.info(f"[chat_stream_orchestrator] 客户端断开(task={task_id})，agent 后台继续")
        return
    except Exception as e:
        logger.error(f"[chat_stream_orchestrator] Error: {e}", exc_info=True)
        # BUG-32修复(三堂会审 小沈 2026-08-13): orchestrator 异常时 cancel bg_task, 避免后台继续运行但前端收到错误的状态不一致;
        #   bg_task 已启动(若进入 try 块内), cancel 后 run_agent_in_background 的 finally 仍会执行 DB 保存(已产出结果不丢失)。
        try:
            if bg_task and not bg_task.done():
                bg_task.cancel()
                logger.info(f"[chat_stream_orchestrator] 已取消后台 agent 任务: {task_id}")
        except Exception as _ce:
            logger.warning(f"[chat_stream_orchestrator] 取消 bg_task 失败: {_ce}")
        yield create_error_response(error_type="router_error", error_message=f"路由异常: {str(e)}")
    finally:
        _current_task_id.reset(_task_token)


async def step_start(ai_service, task_id, next_step, user_input, execution_steps, session_id, warning=None):
    """发送 start 步骤 — 自 openai.py 迁入 — 小欧 2026-08-13"""
    try:
        start_step = await send_start_step(
            ai_service=ai_service, task_id=task_id, next_step=next_step,
            user_message=user_input, security_check_result={},
            warning=warning,
        )
        start_dict = start_step.to_dict()
        execution_steps.append(start_dict)
        yield format_agent_sse(start_dict)
    except Exception as e:
        yield create_error_response(error_type="start_failed", error_message=f"start步骤失败: {e}")


async def _stream_with_control(buffer, task_id: str, next_step, session_id: str,
                               execution_steps: list, state=None, after_seq: int = 0):
    """SSE 消费者包装：读缓冲 + 注入 pause/cancel 检查 — 自 openai.py 迁入 — 小欧 2026-08-13

    首次请求(after_seq=0)与重连请求(after_seq=N)共用本函数，DRY。
    客户端断开时 CancelledError 向上传播，由 orchestrator 捕获。
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


async def chat_stream_reconnect_orchestrator(
    task_id: str, session_id: Optional[str] = None, after_seq: int = 0
) -> AsyncGenerator[str, None]:
    """SSE 重连编排：读同一任务的流态缓冲，不启动新 agent — 自 openai.py 迁入 — 小欧 2026-08-13"""
    buffer = get_stream_buffer(task_id)
    if not buffer:
        yield create_error_response(error_type="not_found", error_message="任务不存在或已结束")
        return
    next_step = create_step_counter()
    async for sse_chunk in _stream_with_control(
        buffer, task_id, next_step, session_id or "", [], None, after_seq
    ):
        yield sse_chunk