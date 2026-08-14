# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-16 - 小欧 - StreamState 增 current_thought 字段, 运行期持有 thought 值
# 2026-07-18 - 小欧 - 消费者完全退出日志层: 删除prompt_logger全部5处引用(start_request/mark_completed/mark_error/save/import)
# 2026-07-22 - 小欧 - 修复: 模型不在 provider models 列表时, 不再抛 ValueError 致 ASGI 崩溃
#   背景: _validate_model_in_list raise ValueError → get_service() 在 generate() 外 → FastAPI 全局异常 → 长篇 traceback + 前端500
#   修复: get_service() 后通过 resolver.pop_model_warning() 获取 warning, 传入 step_start → send_start_step → MetaStep(warning=), 透传前端
#   合规: DRY + KISS + SLAP + SRP
# 2026-07-22 - 小欧 - 代码审查修复: import从函数内移至文件顶部(get_ai_config_resolver无循环依赖); validate_chat_config冗余import删除
# 2026-08-06 - 小欧 - TASK_START日志收口log_and_print统一双写: 原4条裸print(时间/TASK_START/task_id/user_input)不上日志文件+logger.info仅文件, 合并为2条log_and_print(logger.info+print双写, 首行已带完整时间戳), 修复7-23统一治理遗漏
# 2026-08-13 - 小欧 - A7(方案4.7.3步骤2): 编排逻辑一次性迁入 services/chat/stream_orchestrator.py, 本文件降为路由薄壳
#   (路由+DTO解包+调 orchestrator); 删除编排主体 generate/step_start/StreamState/_stream_with_control/chat_stream/
#   chat_stream_reconnect/generate_task_id/validate_chat_config 实现/_agent_tasks。无兼容 shim, 业务逻辑单一归属 orchestrator。
"""
chat_openai — Chat API 路由薄壳（A7 后仅保留路由与 DTO 解包）

编排逻辑迁至 services/chat/stream_orchestrator.py（方案4.7.3）
小健 - 2026-06-07 清理:删除save_step_to_db调用,改用统一save_execution_steps_to_db
"""
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.api.v1.chat.models import ChatRequest
from app.services.chat.stream_orchestrator import (
    chat_stream_orchestrator,
    chat_stream_reconnect_orchestrator,
    validate_chat_config,
)
from app.services.task.task_runtime import cancel_task
from app.services.task.task_registry import pause_task, resume_task
from app.services.task.hitl_confirmation import resolve_confirmation

router = APIRouter()
task_router = APIRouter()


@router.post("/chat/stream")
async def chat_stream_endpoint(request: ChatRequest):
    # DTO 在 API 层解包，避免 services 层反向依赖 api/v1 — 方案4.7.3 DTO边界约定
    return StreamingResponse(
        chat_stream_orchestrator(request.messages, request.session_id),
        media_type="text/event-stream",
    )


@task_router.post("/chat/stream/cancel/{task_id}")
async def cancel_stream_endpoint(task_id: str, session_id: Optional[str] = None):
    return await cancel_task(task_id, session_id)


@task_router.post("/chat/stream/pause/{task_id}")
async def pause_stream_endpoint(task_id: str, session_id: Optional[str] = None):
    return await pause_task(task_id, session_id)


@task_router.post("/chat/stream/resume/{task_id}")
async def resume_stream_endpoint(task_id: str, session_id: Optional[str] = None):
    return await resume_task(task_id, session_id)


@task_router.post("/chat/stream/confirm")
async def confirm_stream_endpoint(request: Request):
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


@router.get("/chat/validate")
async def validate_config_endpoint():
    return await validate_chat_config()


@router.get("/chat/stream/{task_id}")
async def chat_stream_reconnect(task_id: str, session_id: str = None, after_seq: int = 0):
    """SSE 重连端点：读同一任务的流态缓冲，不启动新 agent — 北京老陈 2026-07-12 小欧 2026-07-12"""
    return StreamingResponse(
        chat_stream_reconnect_orchestrator(task_id, session_id, after_seq),
        media_type="text/event-stream",
    )