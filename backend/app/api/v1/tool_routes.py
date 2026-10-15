# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-12 - 小欧 - 新建: A4 /tool/list + /tool/execute 由 health.py 迁出独立(方案4.4.3步骤3)。health.py 回归健康检查单一职责;
#   API 层只调 services/tool 门面, 不再import app.tools(守护测试 api禁tools 规则变绿); /tool/execute 加 X-Test-Mode 校验 + 生产开关默认关闭(步骤4, D2决策)。
# 2026-10-02 - 小欧 - 注册名归位: /tool/execute 用法示例 read→read
# 2026-10-15 北京老陈裁定(机制收敛) - "是否调试环境"三处并行机制收一处:
#   ① 删 tools.execute_tool_enabled(config.yaml 从无此键, 恒 False → 接口从未真正可开);
#   ② 删 X-Test-Mode 头(明文常量非密钥, 全库零发送方, 属伪安全, 且与①重复设卡);
#   ③ 统一读 logging.debug(LogConfig.is_debug_mode, 全项目已有唯一调试访问器)。
#   连带删死 import: get_config / Request; 改 import LogConfig。判定逻辑零改动。
# 2026-10-15 北京老陈裁定(开关外扩) - /tool/list 原不受任何约束(仅 /tool/execute 有门), 现两接口同受 _require_debug_mode():
#   开关逻辑抽成单一守卫函数, 不在两处各写一遍 if; 门关闭改抛 HTTPException(403) 而非 success=False 体
#   (/tool/list 原返回裸列表, 无响应模型可塞 error 字段)。连带修 execute 尾部 tool_name 残留引用(改 request.tool_name)。
"""
tool_routes — 工具测试路由(独立模块)

职责(方案4.4.3, 小欧 2026-08-12): 工具列表 + 工具测试执行接口。
依赖: 只调 services/tool 门面, 不直接接触 app.tools / app.safety(遵守 api 层边界)。

安全栏(2026-10-15 收敛): /tool/execute 仅测试用 — 单一门 = logging.debug, 非调试模式直接拒执行。
"""
from fastapi import APIRouter
from dataclasses import asdict
from typing import Optional

from pydantic import BaseModel

from app.api.v1._gates import require_debug_mode  # 2026-10-15 北京老陈裁定: 调试开关守卫与 /echo 共用
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
    # 2026-10-14 北京老陈裁定 - 跟随系统结构不自创: 安全预检 SafetyResult 原样回传, 调用方据
    #   blocked/requires_confirmation/auth_path 区分"拦截"与"待确认", 不再靠中文错误串猜。
    safety: Optional[dict] = None


# ===== 测试接口开关(单一门: logging.debug, 见 _gates.require_debug_mode) =====

@router.get("/tool/list")
async def list_tools_endpoint():
    """获取所有已注册的工具列表 — 小欧 2026-08-12(2026-10-15 北京老陈裁定: 同受调试开关约束)"""
    require_debug_mode()
    return list_tools()


@router.post("/tool/execute", response_model=ToolExecuteResponse)
async def execute_tool_endpoint(request: ToolExecuteRequest):
    """工具测试执行接口(仅测试用) — 小欧 2026-08-12

    2026-10-15 北京老陈裁定(机制收敛): 单一门 = logging.debug(is_debug_mode 统一访问器)。
      删 tools.execute_tool_enabled(config.yaml 从无此键, 恒 False → 接口从未真正可开) 与 X-Test-Mode 头
      (明文常量非密钥, 全库零发送方, 属伪安全)。同一"是否调试环境"概念此前散三处, 现收一处。
      与 /tool/list、/echo 共用 _gates.require_debug_mode(), 不各判各的。
    Usage: POST /api/v1/tool/execute   Body: {"tool_name": "read", "params": {"path": "app/main.py"}}
    """
    require_debug_mode()

    result = await execute_tool(request.tool_name, request.params)
    _sf = result.get("safety")
    return ToolExecuteResponse(
        tool_name=result.get("tool_name", request.tool_name),
        success=result.get("success", False),
        result=result.get("result", {}),
        error=result.get("error", ""),
        safety=asdict(_sf) if _sf is not None else None,
    )
