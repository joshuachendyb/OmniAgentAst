# Windows需要ProactorEventLoop支持asyncio subprocess — 小沈 2026-06-28
import sys
import asyncio
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
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import traceback
from app.utils.time_utils import get_utc_timestamp
from app.tools import ensure_tools_registered
from app.config import get_config
from app.tools.shell.shell_engine import cleanup_all_persistent_shells
from pathlib import Path
import os
import logging

from app.api.v1 import health, sessions, messages, execution, metrics
from app.api.v1.model_routes import router as model_router
from app.api.v1.chat import router as chat_router, task_router
from app.api.v1.task_queries import router as task_queries_router
from app.utils.logger import logger
from app.services.monitoring import setup_monitoring
from app.constants import DEFAULT_CORS_ORIGINS
from app.services.task.task_registry import cleanup_expired_tasks
from app.db import db

logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_version() -> str:
    """从version.txt读取版本号 - 小沈 2026-05-27"""
    try:
        current_file = Path(__file__).resolve()
        project_root = current_file.parent.parent.parent  # 项目根目录 — 小欧 2026-07-04
        version_file = project_root / "version.txt"

        if version_file.exists():
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
    logger.error(f"HTTP Exception: {exc.status_code} - {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.detail,
            "status_code": exc.status_code,
            "timestamp": get_utc_timestamp()
        }
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.error(f"Validation Error: {exc.errors()}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "error": "请求参数验证失败",
            "details": exc.errors(),
            "timestamp": get_utc_timestamp()
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
            "timestamp": get_utc_timestamp()
        }
    )


app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(chat_router, prefix="/api/v1", tags=["chat"])
app.include_router(task_router, prefix="/api/v1", tags=["chat"])
app.include_router(model_router, prefix="/api/v1", tags=["config"])
app.include_router(sessions.router, prefix="/api/v1", tags=["sessions"])
app.include_router(messages.router, prefix="/api/v1", tags=["sessions"])

app.include_router(execution.router, prefix="/api/v1", tags=["execution"])
app.include_router(metrics.router, prefix="/api/v1", tags=["metrics"])
app.include_router(task_queries_router, prefix="/api/v1", tags=["task-queries"])


def _start_cleanup_task():
    """启动清理任务 - 小沈 2026-06-08"""
    async def cleanup_task():
        """定期清理过期任务"""
        while True:
            try:
                await cleanup_expired_tasks()
            except Exception as e:
                logger.error(f"清理过期任务失败: {e}")
            await asyncio.sleep(3600)
    
    asyncio.create_task(cleanup_task())
    logger.info("后台清理任务已启动")


@app.on_event("startup")
async def startup_event():
    """应用启动时注册工具 + 启动后台任务 — 小健 2026-06-18 内联透传函数"""
    db.init()
    ensure_tools_registered()
    _start_cleanup_task()
    print(f"当前版本: {app_version}")
    _cfg = get_config()
    print(f"LLM 配置: provider={_cfg.get('ai.provider')}, model={_cfg.get('ai.model')}")


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时清理资源 — 小健 2026-06-18 内联透传函数"""
    from app.services.factory import reset
    reset()
    count = cleanup_all_persistent_shells()
    logger.info(f"已清理 {count} 个持久shell进程")


@app.get("/")
async def root():
    return {
        "message": "OmniAgentAst API",
        "version": app_version,
        "docs": "/docs"
    }
