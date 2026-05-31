from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from datetime import datetime
import traceback
import os
import logging
import asyncio

from app.api.v1 import health, ai_config, sessions, messages, conversation, execution, metrics
from app.api.v1.chat import router as chat_router_router, task_router
from app.api.v1.task_queries import router as task_queries_router
from app.utils.logger import logger
from app.utils.monitoring import setup_monitoring
from app.constants import DEFAULT_CORS_ORIGINS
from app.utils.version import get_version
from app.services.react_sse_wrapper import cleanup_expired_tasks
from app.db import db

logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

app_version = get_version()
print(app_version)

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
            "timestamp": datetime.utcnow().isoformat()
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
            "timestamp": datetime.utcnow().isoformat()
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
            "timestamp": datetime.utcnow().isoformat()
        }
    )


app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(chat_router_router, prefix="/api/v1", tags=["chat"])
app.include_router(task_router, prefix="/api/v1", tags=["chat"])
app.include_router(ai_config.router, prefix="/api/v1", tags=["config"])
app.include_router(sessions.router, prefix="/api/v1", tags=["sessions"])
app.include_router(messages.router, prefix="/api/v1", tags=["sessions"])
app.include_router(conversation.router, prefix="/api/v1", tags=["conversation"])
app.include_router(execution.router, prefix="/api/v1", tags=["execution"])
app.include_router(metrics.router, prefix="/api/v1", tags=["metrics"])
app.include_router(task_queries_router, prefix="/api/v1", tags=["task-queries"])


@app.on_event("startup")
async def startup_event():
    """应用启动时注册工具 + 启动后台任务"""
    db.init()

    # 全量注册工具（确保首次请求时可用）
    from app.services.tools import ensure_tools_registered
    ensure_tools_registered()

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


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时清理资源"""
    from app.services.factory import AIServiceFactory
    await AIServiceFactory.reset()

    from app.services.tools.shell.shell_tools import cleanup_background_shells
    count = cleanup_background_shells()
    logger.info(f"已清理 {count} 个后台shell进程")


@app.get("/")
async def root():
    return {
        "message": "OmniAgentAst API",
        "version": app_version,
        "docs": "/docs"
    }
