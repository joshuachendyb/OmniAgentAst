# Windows需要ProactorEventLoop支持asyncio subprocess — 小沈 2026-06-28
# 编辑历史:
# 2026-07-15 小欧 修复后台清理闭包命名撞车: 原内部闭包 cleanup_task 与 task_registry.cleanup_task(删单个任务)同名不同义, 违反清晰命名/KISS; 展平为模块级 _periodic_cleanup_loop 并保存 task 引用, shutdown 时 cancel
# 2026-07-28 - 小欧 - BUG#4: version.txt为空时get_version直奔for line in f, 无行进入时version未赋值致UnboundLocalError; 补version="0.0.0"默认值。
# 2026-08-03 - 小欧 - 恢复7-30原设计(DB核实): 删shutdown里的shell_pool.cleanup_all()+日志与import; 该行系8-02恢复工程误加回, 7-30已决策main.py不清理(atexit+task完成清理全覆盖)。
# 2026-08-08 - 小欧 - 全程统一本地时区: 3处异常响应 timestamp 改 get_local_iso_timestamp() (本地ISO无Z)
# 2026-08-09 - 小欧 - task006 P7落地(日志级别优化): HTTP 4xx客户端错误与Validation(422)由ERROR降为WARNING, 5xx保持ERROR — 避免测试/非法请求噪音污染ERROR日志, 干扰真实故障排查
import sys
import asyncio
from typing import Optional
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    # Windows PowerShell 5.1中文输出编码修复 — 小欧 2026-07-07
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        # Python -u模式下可能抛AttributeError，忽略
        pass

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import traceback
from app.utils.time_utils import get_local_iso_timestamp  # 小欧 2026-08-08 全程统一本地时区
from app.tools import ensure_tools_registered
from app.config import get_config, get_code_root
from pathlib import Path
import os
import logging

from app.api.v1 import health, sessions, messages, metrics
from app.api.v1.model_routes import router as model_router
from app.api.v1.chat import router as chat_router, task_router, sse as chat_execution_router
from app.api.v1.task_queries import router as task_queries_router
from app.logger import logger
from app.services.monitoring import setup_monitoring
from app.constants import DEFAULT_CORS_ORIGINS
from app.services.task.task_registry import cleanup_expired_tasks
from app.db import db

logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_version() -> str:
    """从version.txt读取版本号 - 小沈 2026-05-27 - 小欧 2026-08-10 ⑬改调get_code_root"""
    try:
        code_root = Path(get_code_root())  # 代码库根(定位version.txt) — ⑬ 2026-08-10
        version_file = code_root / "version.txt"

        if version_file.exists():
            version = "0.0.0"
            with open(version_file, 'r', encoding='utf-8') as f:
                for line in f:
                    version = line.strip().lstrip('\ufeff')
                    if version:
                        break
            logger.debug(f"Successfully read version from version.txt: {version}")
            return version.lstrip('v')
    except Exception as e:
        logger.warning(f"Failed to read version.txt: {e}")
    return "0.0.0"


app_version = get_version()
logger.info(f"Backend version: {app_version}")

app = FastAPI(
    title="OmniAgentAst API",
    description="OmniAgentAst 桌面版后端API",
    version=app_version
)

logger.info("Backend v" + app_version + " started")

_cors_origins_str = os.getenv("CORS_ORIGINS", DEFAULT_CORS_ORIGINS)
_cors_origins = [origin.strip() for origin in _cors_origins_str.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

setup_monitoring(app)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    # 记录请求路径/方法/客户端, 便于定位 404 等异常的真正来源(原日志仅记状态码, 无法定位) — 小欧 2026-07-13
    client = request.client.host if request.client else "unknown"
    # 2026-08-09 小欧: task006 P7 — 4xx客户端错误降WARNING, 5xx服务端错误保持ERROR(真实故障), 减少噪音
    _log = logger.warning if exc.status_code < 500 else logger.error
    _log(f"HTTP Exception: {exc.status_code} - {exc.detail} | {request.method} {request.url.path} client={client}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.detail,
            "status_code": exc.status_code,
            "timestamp": get_local_iso_timestamp()
        }
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # 2026-08-09 小欧: task006 P7 — 422恒为客户端请求参数错误, 由ERROR降WARNING, 避免非法请求噪音污染ERROR日志
    logger.warning(f"Validation Error: {exc.errors()}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "error": "请求参数验证失败",
            "details": exc.errors(),
            "timestamp": get_local_iso_timestamp()
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    error_msg = str(exc)
    error_trace = traceback.format_exc()
    logger.error(f"Unhandled Exception: {error_msg}\n{error_trace}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": "服务器内部错误",
            "message": error_msg if app.debug else "请联系管理员",
            "timestamp": get_local_iso_timestamp()
        }
    )


app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(chat_router, prefix="/api/v1", tags=["chat"])
app.include_router(task_router, prefix="/api/v1", tags=["chat"])
app.include_router(model_router, prefix="/api/v1", tags=["config"])
app.include_router(sessions.router, prefix="/api/v1", tags=["sessions"])
app.include_router(messages.router, prefix="/api/v1", tags=["sessions"])

app.include_router(chat_execution_router.router, prefix="/api/v1", tags=["execution"])
app.include_router(metrics.router, prefix="/api/v1", tags=["metrics"])
app.include_router(task_queries_router, prefix="/api/v1", tags=["task-queries"])


_cleanup_task_ref: Optional[asyncio.Task] = None  # 后台清理循环 task 引用, 供 shutdown 时 cancel


async def _periodic_cleanup_loop() -> None:
    """后台周期清理循环: 每 3600s 调用 task_registry.cleanup_expired_tasks 兜底清理过期任务
       命名与 task_registry.cleanup_task(删单个任务) 区分, 避免混淆 (清晰命名/KISS)
    """
    while True:
        try:
            await cleanup_expired_tasks()
        except Exception as e:
            logger.error(f"清理过期任务失败: {e}")
        await asyncio.sleep(3600)


def _start_cleanup_task() -> None:
    """启动后台周期清理任务 — 小沈 2026-06-08; 闭包展平+改名 小欧 2026-07-15"""
    global _cleanup_task_ref
    _cleanup_task_ref = asyncio.create_task(_periodic_cleanup_loop())
    logger.info("后台清理任务已启动")


@app.on_event("startup")
async def startup_event():
    """应用启动时注册工具 + 启动后台任务 — 小健 2026-06-18 内联透传函数"""
    import time as _time
    _t0 = _time.time()
    db.init()
    logger.info(f"[启动耗时] db.init: {_time.time()-_t0:.3f}s")
    _t1 = _time.time()
    ensure_tools_registered()
    logger.info(f"[启动耗时] ensure_tools_registered: {_time.time()-_t1:.3f}s")
    _t2 = _time.time()
    _start_cleanup_task()
    logger.info(f"[启动耗时] _start_cleanup_task: {_time.time()-_t2:.3f}s")
    logger.info(f"[启动耗时] startup_event 合计: {_time.time()-_t0:.3f}s")
    print(f"当前版本: {app_version}")
    _cfg = get_config()
    print(f"LLM 配置: provider={_cfg.get('ai.provider')}, model={_cfg.get('ai.model')}")


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时清理资源 — 小健 2026-06-18 内联透传函数; 补充 cancel 清理循环 小欧 2026-07-15"""
    global _cleanup_task_ref
    if _cleanup_task_ref is not None and not _cleanup_task_ref.done():
        _cleanup_task_ref.cancel()
    from app.services.lifecycle import reset
    reset()


@app.get("/")
async def root():
    return {
        "message": "OmniAgentAst API",
        "version": app_version,
        "docs": "/docs"
    }


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    # 浏览器自动请求 favicon 时返回 204，避免 main.py:87 全局异常处理器记录 404 噪声 — 小欧 2026-07-13
    return Response(status_code=204)
