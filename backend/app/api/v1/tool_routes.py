# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-12 - 小欧 - 新建: A4 /tool/list + /tool/execute 由 health.py 迁出独立(方案4.4.3步骤3)。health.py 回归健康检查单一职责;
#   API 层只调 services/tool 门面, 不再import app.tools(守护测试 api禁tools 规则变绿); /tool/execute 加 X-Test-Mode 校验 + 生产开关默认关闭(步骤4, D2决策)。
"""
tool_routes — 工具测试路由(独立模块)

职责(方案4.4.3, 小欧 2026-08-12): 工具列表 + 工具测试执行接口。
依赖: 只调 services/tool 门面, 不直接接触 app.tools / app.safety(遵守 api 层边界)。

安全栏(步骤4, D2): /tool/execute 仅测试用 — 需 X-Test-Mode 头 + 生产开关 tools.execute_tool_enabled 默认 False。
"""
from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.config import get_config
from app.services.tool import list_tools, execute_tool

router = APIRouter()


class ToolExecuteRequest(BaseModel):
    tool_name: str
    params: dict = {}


class ToolExecuteResponse(BaseModel):
    tool_name: str
    success: bool
    result: dict = {}
    error: str = ""


# ===== 测试接口开关 =====

def _tool_execute_enabled() -> bool:
    """生产开关: 默认关闭(仅测试用) — 配置 tools.execute_tool_enabled 控制 — 小欧 2026-08-12"""
    try:
        return bool(get_config().get("tools.execute_tool_enabled", False))
    except Exception:
        return False


@router.get("/tool/list")
async def list_tools_endpoint():
    """获取所有已注册的工具列表 — 小欧 2026-08-12"""
    return list_tools()


@router.post("/tool/execute", response_model=ToolExecuteResponse)
async def execute_tool_endpoint(request: ToolExecuteRequest, http_request: Request):
    """工具测试执行接口(仅测试用) — 小欧 2026-08-12

    安全栏值: 需 X-Test-Mode 头 = '1'/'true' 且 tools.execute_tool_enabled 开关打开; 否则生产拒执行。
    Usage: POST /api/v1/tool/execute   Body: {"tool_name": "readtext", "params": {"path": "app/main.py"}}
    """
    tool_name = request.tool_name
    params = request.params

    if not _tool_execute_enabled():
        return ToolExecuteResponse(tool_name=tool_name, success=False,
                                   error="工具测试接口已关闭(生产禁用, 需在config开启 tools.execute_tool_enabled)")
    test_header = (http_request.headers.get("X-Test-Mode") or "").strip().lower()
    if test_header not in ("1", "true", "yes"):
        return ToolExecuteResponse(tool_name=tool_name, success=False,
                                   error="缺少 X-Test-Mode 请求头(工具测试接口仅用于测试)")

    result = await execute_tool(tool_name, params)
    return ToolExecuteResponse(
        tool_name=result.get("tool_name", tool_name),
        success=result.get("success", False),
        result=result.get("result", {}),
        error=result.get("error", ""),
    )