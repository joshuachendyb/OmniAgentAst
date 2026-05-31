# -*- coding: utf-8 -*-
"""
Chat Router — 路由层入口

task操作统一在 services/task/ 层，本文件只做路由分发

Author: 小沈 - 2026-03-26
统一: 小健 - 2026-05-31 — 删除task wrapper，直接调库
"""

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.api.v1.chat.models import ChatRequest
from app.api.v1.chat.chat_stream_v2 import chat_stream_v2
from app.api.v1.chat.confirm_operation import confirm_operation
from app.api.v1.chat.validate_chat_config import validate_chat_config

router = APIRouter()
task_router = APIRouter()


@router.post("/chat/stream")
async def chat_stream_endpoint(request: ChatRequest):
    return await chat_stream_v2(request)


@task_router.post("/chat/stream/cancel/{task_id}")
async def cancel_stream_endpoint(task_id: str, session_id: str = None):
    from app.services.task.task_cancel import cancel_task
    return await cancel_task(task_id, session_id)


@task_router.post("/chat/stream/pause/{task_id}")
async def pause_stream_endpoint(task_id: str, session_id: str = None):
    from app.services.task.task_pause import pause_task
    return await pause_task(task_id, session_id)


@task_router.post("/chat/stream/resume/{task_id}")
async def resume_stream_endpoint(task_id: str, session_id: str = None):
    from app.services.task.task_resume import resume_task
    return await resume_task(task_id, session_id)


@task_router.post("/chat/stream/confirm")
async def confirm_stream_endpoint(request: Request):
    return await confirm_operation(request)


@router.get("/chat/validate")
async def validate_config_endpoint():
    return await validate_chat_config()
