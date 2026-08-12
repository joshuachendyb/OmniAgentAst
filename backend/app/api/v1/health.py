
# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-10 - 小欧 - merged from health/ 3 files, only changed import paths
# 2026-07-23 - 小欧 - #14 fix: health check 加真实DB连接验证(chat/operations/task_tracker)
#   【病根】health check 始终返回"healthy", 不检查DB就绪状态, 无法发现表缺失/连接异常
#   【改法】遍历三库执行SELECT 1 + sqlite_master查表数, 任一失败则db_status="degraded"
#   【合规】SRP(health只检查状态不修改)+KISS-DIRECT(直接连库查,不引入复杂健康指标)
# 2026-07-28 - 小欧 - BUG#18: 删sqlite_master无用查询(SELECT COUNT(*)结果未赋值未使用); BUG#22: echo路由参数request改名data(避免与FastAPI内置Request类型变量混淆); BUG#23: 删死协程检查(iscoroutine永远为False, run_in_executor内同步函数不返回协程); 额外: list_tools中required_set预计算避免重复构建set
# 2026-08-08 - 小欧 - 全程统一本地时区: 2处响应 timestamp 改 get_local_iso_timestamp() (本地ISO无Z)
# 2026-08-12 - 小欧 - A4(方案4.4.3步骤3): /tool/list + /tool/execute 迁出独立 tool_routes.py, health.py 回归健康检查单一职责;
#   删除 from app.tools import tool_registry 等越层 import(守护测试 api禁tools 变绿)。工具执行改走 services/tool 门面。
# 2026-08-12 - 小欧 - A1过渡红项历史(4.1.7/A4待消, 随A4迁出而移除代码, 历史按规范保留): /tool/execute 曾 API直调不走tool_executor,
#   注入 DefaultToolSecurityHooks 到 ContextVar 防空钩子 NPE; A4 建成 services/tool 门面后该过渡注入由 facade 统一接管, 移除。
"""
health — merged from health/ 3 files
COPY from individual files, only changed import paths — 小欧 2026-07-10
"""

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.db import db
from app.logger import logger
from app.utils.time_utils import get_local_iso_timestamp  # 小欧 2026-08-08 全程统一本地时区

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

