# -*- coding: utf-8 -*-
"""
Chat Router — 路由层入口

从 chat_router.py 拆出，遵循 SRP：
- 各功能函数独立文件
- 本文件只保留路由定义和装饰器

Author: 小沈 - 2026-03-26
"""

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.api.v1.chat.models import ChatRequest
from app.api.v1.chat.chat_stream_v2 import chat_stream_v2
from app.api.v1.chat.cancel_stream_task import cancel_stream_task
from app.api.v1.chat.pause_stream_task import pause_stream_task
from app.api.v1.chat.resume_stream_task import resume_stream_task
from app.api.v1.chat.confirm_operation import confirm_operation
from app.api.v1.chat.validate_chat_config import validate_chat_config

router = APIRouter()
task_router = APIRouter()


@router.post("/chat/stream")
async def chat_stream_endpoint(request: ChatRequest):
    return await chat_stream_v2(request)


@task_router.post("/chat/stream/cancel/{task_id}")
async def cancel_stream_endpoint(task_id: str, session_id: str = None):
    return await cancel_stream_task(task_id, session_id)


@task_router.post("/chat/stream/pause/{task_id}")
async def pause_stream_endpoint(task_id: str, session_id: str = None):
    return await pause_stream_task(task_id, session_id)


@task_router.post("/chat/stream/resume/{task_id}")
async def resume_stream_endpoint(task_id: str, session_id: str = None):
    return await resume_stream_task(task_id, session_id)


@task_router.post("/chat/stream/confirm")
async def confirm_stream_endpoint(request: Request):
    return await confirm_operation(request)


@router.get("/chat/validate")
async def validate_config_endpoint():
    return await validate_chat_config()
