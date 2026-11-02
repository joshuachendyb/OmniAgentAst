
# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-10 - 小欧 - merged from health/ 3 files, only changed import paths
# 2026-07-23 - 小欧 - 修复: health check 加真实DB连接验证(chat/operations/task_tracker)
#   【病根】health check 始终返回"healthy", 不检查DB就绪状态, 无法发现表缺失/连接异常
#   【改法】遍历三库执行SELECT 1 + sqlite_master查表数, 任一失败则db_status="degraded"
#   【合规】SRP(health只检查状态不修改)+KISS-DIRECT(直接连库查,不引入复杂健康指标)
# 2026-07-28 - 小欧 - BUG#18: 删sqlite_master无用查询(SELECT COUNT(*)结果未赋值未使用); BUG#22: echo路由参数request改名data(避免与FastAPI内置Request类型变量混淆); BUG#23: 删死协程检查(iscoroutine永远为False, run_in_executor内同步函数不返回协程); 额外: list_tools中required_set预计算避免重复构建set
# 2026-08-08 - 小欧 - 全程统一本地时区: 2处响应 timestamp 改 get_local_iso_timestamp() (本地ISO无Z)
# 2026-08-12 - 小欧 - A4(方案4.4.3步骤3): /tool/list + /tool/execute 迁出独立 tool_routes.py, health.py 回归健康检查单一职责;
#   删除 from app.tools import tool_registry 等越层 import(守护测试 api禁tools 变绿)。工具执行改走 services/tool 门面。
# 2026-08-12 - 小欧 - A1过渡红项历史(4.1.7/A4待消, 随A4迁出而移除代码, 历史按规范保留): /tool/execute 曾 API直调不走tool_executor,
#   注入 DefaultToolSecurityHooks 到 ContextVar 防空钩子 NPE; A4 建成 services/tool 门面后该过渡注入由 facade 统一接管, 移除。
# 2026-08-24 - 小欧 - 后端卡死修复: /health 的 SELECT 1 经 db.atxn 进子线程 offload 出事件循环; 被动 health 不再因 loop 被 agent 落库同步写独占而超时(零改动连接管理, 复用 atxn 薄壳)
# 2026-09-21 - 小欧 - 修复: health.version 由 request.app.version(import 时快照, 永不跟随 version.txt 更新)改调
#   settings_service.app_version()(每次实时读文件); 消除与 /settings.version、GET /config/version-file 长期不一致
# 2026-10-15 北京老陈裁定(开关外扩) - /echo(调试通信探针, 非产品功能) 纳入 require_debug_mode 约束:
#   守卫提为共用模块 api/v1/_gates.py, 与 /tool/list、/tool/execute 同一道门; 不在 health.py 复写一遍(违 DRY)。/health 不受影响。
# 2026-11-02 小欧 - /health 响应加 host 字段(Host头): 顶栏服务胶囊需显示真实后端地址, 开发(Vite代理)/打包(同源或直连)通用 — 小欧-2026-11-02
# 2026-11-02 小欧 - /health 再加 server_ip(本机局域网IP, lru_cache)与 pid: 他人访问地址与卡死排错要用的可执行信息 — 小欧-2026-11-02
# 2026-11-02 小欧 - 再加 uptime_s(进程存活时长)与 loop_lag_ms(事件循环调度延迟点采样): 前端"耗时"只能推断卡死,
#   这两个字段把"网络慢"与"事件循环被占死"分开, 与 AGENTS.md 的 py-spy 取证串成一条证据链 — 小欧-2026-11-02
"""
health — merged from health/ 3 files
COPY from individual files, only changed import paths — 小欧 2026-07-10
"""

from fastapi import APIRouter, Request
from pydantic import BaseModel

import os
import socket
import asyncio
import time
from functools import lru_cache

from app.api.v1._gates import require_debug_mode  # 2026-10-15 北京老陈裁定: /echo 受调试开关约束
from app.db import db
from app.logger import logger
from app.services.settings.settings_service import app_version as get_app_version
from app.utils.time_utils import get_local_iso_timestamp  # 小欧 2026-08-08 全程统一本地时区

router = APIRouter()


@lru_cache(maxsize=1)
def _server_lan_ip() -> str:
    """本机局域网IP(进程内只解析一次) — 2026-11-02 小欧: 供顶栏服务胶囊显示可被他人访问的地址"""
    try:
        return socket.gethostbyname(socket.gethostname())
    except OSError:
        return ""

# 2026-11-02 小欧 - 进程启动时刻(本模块在 app 导入期加载, 与进程启动同刻); monotonic 不受系统时钟调整影响
_STARTED_AT = time.monotonic()


async def _loop_lag_ms() -> float:
    """事件循环调度延迟(点采样, 毫秒) — 2026-11-02 小欧

    做法: 让出一次控制权, 量"多久才被重新调度"。循环被同步任务占死时该值显著上升,
    故可与前端往返耗时对照, 区分"网络慢"与"事件循环卡住"。只代表此刻, 不是历史峰值。
    """
    started = time.monotonic()
    await asyncio.sleep(0)
    return round((time.monotonic() - started) * 1000, 3)

# ===== health =====

class HealthResponse(BaseModel):
    status: str
    timestamp: str
    version: str
    db_status: str = "unknown"  # 小欧 2026-07-23 #14: 真实DB连接验证
    host: str = ""  # 2026-11-02 小欧 - 后端视角访问地址(Host头), 顶栏服务胶囊显示真实后端地址(开发/打包通用)
    server_ip: str = ""  # 2026-11-02 小欧 - 本机局域网IP, 供他人访问时使用
    pid: int = 0  # 2026-11-02 小欧 - 进程号, 卡死时直接对应 py-spy dump --pid
    uptime_s: float = 0.0  # 2026-11-02 小欧 - 进程已存活秒数(重启即归零, 与 pid 变化互相印证)
    loop_lag_ms: float = 0.0  # 2026-11-02 小欧 - 事件循环调度延迟点采样, 区分网络慢与循环被占死

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
            # 落库 offload 出事件循环(后端卡死修复 小欧 2026-08-24): 被动 /health 不再因 loop 被占而超时
            await db.atxn(db_name, lambda conn: conn.execute("SELECT 1"))
        except Exception:
            logger.warning(f"[health] DB {db_name} 连接失败")
            db_status = "degraded"
    return HealthResponse(
        status="healthy" if db_status == "healthy" else "degraded",
        timestamp=get_local_iso_timestamp(),
        version=get_app_version(),
        db_status=db_status,
        # 2026-11-02 小欧 - Host头即前端实际访问到的后端地址: dev经Vite代理(changeOrigin)=proxy target, 打包=访问域名或直连地址
        host=request.headers.get("host", ""),
        server_ip=_server_lan_ip(),
        pid=os.getpid(),
        # 2026-11-02 小欧 - 存活时长与循环延迟: 顶栏胶囊据此区分"重启过/网络慢/事件循环被占死"
        uptime_s=round(time.monotonic() - _STARTED_AT, 3),
        loop_lag_ms=await _loop_lag_ms(),
    )

@router.post("/echo", response_model=EchoResponse)
async def echo(data: EchoRequest):
    """
    测试通信接口 - 回显收到的消息
    2026-10-15 北京老陈裁定: 调试探针非产品功能, 纳入 require_debug_mode 约束(与 /tool/* 同一道门)。
    """
    require_debug_mode()
    return EchoResponse(
        received=data.message,
        timestamp=get_local_iso_timestamp()
    )

