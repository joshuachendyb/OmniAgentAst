# -*- coding: utf-8 -*-
"""
health — merged from health/ 3 files
COPY from individual files, only changed import paths — 小欧 2026-07-10
"""

import asyncio
import inspect
import uuid as _uuid
import re as _re

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.utils.time_utils import get_utc_timestamp
from app.tools import tool_registry
from app.utils.message_id_tracker import _current_task_id

router = APIRouter()

# ===== health =====

class HealthResponse(BaseModel):
    status: str
    timestamp: str
    version: str

class EchoRequest(BaseModel):
    message: str

class EchoResponse(BaseModel):
    received: str
    timestamp: str

@router.get("/health", response_model=HealthResponse)
async def health_check(request: Request):
    """
    健康检查接口
    """
    return HealthResponse(
        status="healthy",
        timestamp=get_utc_timestamp(),
        version=request.app.version
    )

@router.post("/echo", response_model=EchoResponse)
async def echo(request: EchoRequest):
    """
    测试通信接口 - 回显收到的消息
    """
    return EchoResponse(
        received=request.message,
        timestamp=get_utc_timestamp()
    )


@router.get("/tool/list")
async def list_tools():
    """获取所有已注册的工具列表"""

    tools = tool_registry.to_openai_tools()

    tool_list = []
    for t in tools:
        func = t.get('function', {})
        name = func.get('name', '')
        desc = func.get('description', '')
        params = func.get('parameters', {})
        required = params.get('required', [])
        props = list(params.get('properties', {}).keys())

        tool_list.append({
            "name": name,
            "description": desc[:100] if desc else "",
            "required_params": required,
            "optional_params": [p for p in props if p not in set(required)],
            "inputSchema": params,
        })

    return {
        "total": len(tool_list),
        "tools": tool_list
    }


# ===== execute_tool =====

class ToolExecuteRequest(BaseModel):
    tool_name: str
    params: dict = {}

class ToolExecuteResponse(BaseModel):
    tool_name: str
    success: bool
    result: dict = {}
    error: str = ""

@router.post("/tool/execute", response_model=ToolExecuteResponse)
async def execute_tool(request: ToolExecuteRequest):
    """
    direct execution of the tool's test interface
    Usage: POST /api/v1/tool/execute
    Body: {"tool_name": "readtext", "params": {"path": "app/main.py"}}
    """
    tool_name = request.tool_name
    params = request.params

    impl = tool_registry.get_implementation(tool_name)

    if impl is None:
        return ToolExecuteResponse(
            tool_name=tool_name,
            success=False,
            error=f"Tool '{tool_name}' not found or not registered"
        )

    try:
        _api_task_id = str(_uuid.uuid4())
        _current_task_id.set(_api_task_id)

        if inspect.iscoroutinefunction(impl):
            result = await impl(**params)
        else:
            loop = asyncio.get_event_loop()
            _captured_task_id = _current_task_id.get()
            def _run_with_task_context():
                _current_task_id.set(_captured_task_id)
                return impl(**params)
            result = await loop.run_in_executor(None, _run_with_task_context)

        if asyncio.iscoroutine(result):
            result = await result

        return ToolExecuteResponse(
            tool_name=tool_name,
            success=True,
            result=result if isinstance(result, dict) else {"output": str(result)}
        )
    except Exception as e:
        err_msg = str(e)
        if "missing" in err_msg and "required positional argument" in err_msg:
            match = _re.search(r"missing \d+ required positional argument[s]?:\s*(.+)", err_msg)
            missing_params = match.group(1) if match else "未知参数"
            err_msg = f"缺少必填参数: {missing_params}。请参考tool/list获取{tool_name}的inputSchema"
        return ToolExecuteResponse(
            tool_name=tool_name,
            success=False,
            error=err_msg
        )

    try:
        _api_task_id = str(_uuid.uuid4())
        _current_task_id.set(_api_task_id)

        if inspect.iscoroutinefunction(impl):
            result = await impl(**params)
        else:
            loop = asyncio.get_event_loop()
            _captured_task_id = _current_task_id.get()
            def _run_with_task_context():
                _current_task_id.set(_captured_task_id)
                return impl(**params)
            result = await loop.run_in_executor(None, _run_with_task_context)

        if asyncio.iscoroutine(result):
            result = await result

        return ToolExecuteResponse(
            tool_name=tool_name,
            success=True,
            result=result if isinstance(result, dict) else {"output": str(result)}
        )
    except Exception as e:
        err_msg = str(e)
        if "missing" in err_msg and "required positional argument" in err_msg:
            match = _re.search(r"missing \d+ required positional argument[s]?:\s*(.+)", err_msg)
            missing_params = match.group(1) if match else "未知参数"
            err_msg = f"缺少必填参数: {missing_params}。请参考tool/list获取{tool_name}的inputSchema"
        return ToolExecuteResponse(
            tool_name=tool_name,
            success=False,
            error=err_msg
        )
