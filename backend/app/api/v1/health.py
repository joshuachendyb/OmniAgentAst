
# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-10 - 小欧 - merged from health/ 3 files, only changed import paths
# 2026-07-23 - 小欧 - #14 fix: health check 加真实DB连接验证(chat/operations/task_tracker)
#   【病根】health check 始终返回"healthy", 不检查DB就绪状态, 无法发现表缺失/连接异常
#   【改法】遍历三库执行SELECT 1 + sqlite_master查表数, 任一失败则db_status="degraded"
#   【合规】SRP(health只检查状态不修改)+KISS-DIRECT(直接连库查,不引入复杂健康指标)
# 2026-07-28 - 小欧 - BUG#18: 删sqlite_master无用查询(SELECT COUNT(*)结果未赋值未使用); BUG#22: echo路由参数request改名data(避免与FastAPI内置Request类型变量混淆); BUG#23: 删死协程检查(iscoroutine永远为False, run_in_executor内同步函数不返回协程); 额外: list_tools中required_set预计算避免重复构建set
# 2026-08-08 - 小欧 - 全程统一本地时区: 2处响应 timestamp 改 get_local_iso_timestamp() (本地ISO无Z)
# 2026-08-12 - 小欧 - A1过渡红项(4.1.7/A4待消): /tool/execute API直调不走tool_executor, 注入 DefaultToolSecurityHooks
#   到 ContextVar hooks, 防止 record_operation/execute_with_safety 空钩子 NPE; A4 将此直调过渡移除 — 小欧 2026-08-12
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

from app.db import db
from app.logger import logger
from app.utils.time_utils import get_local_iso_timestamp  # 小欧 2026-08-08 全程统一本地时区
from app.tools import tool_registry
from app.services.task.task_context import _current_task_id
from app.tools.context import set_current_hooks, reset_current_hooks  # A1过渡红项 — 小欧 2026-08-12
from app.safety.default_hooks import DefaultToolSecurityHooks  # A1过渡红项 — 小欧 2026-08-12

router = APIRouter()

# ===== health =====

class HealthResponse(BaseModel):
    status: str
    timestamp: str
    version: str
    db_status: str = "unknown"  # 小欧 2026-07-23 #14: 真实DB连接验证

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
    db_status = "healthy"
    for db_name in ["chat", "operations", "task_tracker"]:
        try:
            with db.get_conn(db_name) as conn:
                conn.execute("SELECT 1")
        except Exception:
            logger.warning(f"[health] DB {db_name} 连接失败")
            db_status = "degraded"
    return HealthResponse(
        status="healthy" if db_status == "healthy" else "degraded",
        timestamp=get_local_iso_timestamp(),
        version=request.app.version,
        db_status=db_status,
    )

@router.post("/echo", response_model=EchoResponse)
async def echo(data: EchoRequest):
    """
    测试通信接口 - 回显收到的消息
    """
    return EchoResponse(
        received=data.message,
        timestamp=get_local_iso_timestamp()
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

        required_set = set(required)

        tool_list.append({
            "name": name,
            "description": desc[:100] if desc else "",
            "required_params": required,
            "optional_params": [p for p in props if p not in required_set],
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
        _hooks_token = set_current_hooks(DefaultToolSecurityHooks())  # A1过渡红项: 注入默认hooks — 小欧 2026-08-12

        if inspect.iscoroutinefunction(impl):
            result = await impl(**params)
        else:
            loop = asyncio.get_event_loop()
            _captured_task_id = _current_task_id.get()
            _captured_hooks = set_current_hooks(DefaultToolSecurityHooks())  # sync分支executor内需重注入 — 小欧 2026-08-12
            def _run_with_task_context():
                _current_task_id.set(_captured_task_id)
                set_current_hooks(_captured_hooks)
                return impl(**params)
            result = await loop.run_in_executor(None, _run_with_task_context)

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
    finally:
        try:
            reset_current_hooks(_hooks_token)
        except Exception:
            pass

