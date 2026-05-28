from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from datetime import datetime
import traceback

from app.api.v1 import health, operation_history, routes, sessions, messages, conversation, execution, metrics
# 兼容导入
config = routes
# chat_stream 暂时禁用，使用 chat_router 替代
from app.utils.logger import logger
from app.utils.monitoring import setup_monitoring

# 只过滤uvicorn的访问日志，不影响应用日志
import logging

from app.constants import DEFAULT_CORS_ORIGINS
from app.utils.version import get_version


logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

app_version = get_version()
print(app_version)

app = FastAPI(
    title="OmniAgentAst API",
    description="OmniAgentAst 桌面版后端API",
    version=app_version
)

logger.info("Backend v" + app_version + " started")

# CORS配置 - 显式指定前端源，避免通配符与credentials冲突
import os


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
from app.services.chat_router import router as chat_router_router, task_router
app.include_router(chat_router_router, prefix="/api/v1", tags=["chat"])
app.include_router(task_router, prefix="/api/v1", tags=["chat"])
app.include_router(operation_history.router, prefix="/api/v1", tags=["operation-history"])
app.include_router(config.router, prefix="/api/v1", tags=["config"])
app.include_router(sessions.router, prefix="/api/v1", tags=["sessions"])
app.include_router(messages.router, prefix="/api/v1", tags=["sessions"])
app.include_router(conversation.router, prefix="/api/v1", tags=["conversation"])
app.include_router(execution.router, prefix="/api/v1", tags=["execution"])
app.include_router(metrics.router, prefix="/api/v1", tags=["metrics"])


# 【阶段6更新】cleanup_expired_tasks 改为从 react_sse_wrapper 导入
import asyncio
from app.services.react_sse_wrapper import cleanup_expired_tasks
from app.db import db

@app.on_event("startup")
async def startup_event():
    """应用启动时注册工具 + 启动后台任务"""
    # S0: 初始化数据库
    db.init()
    
    # S1: 全量注册工具（确保首次请求时可用）
    from app.services.tools import ensure_tools_registered
    ensure_tools_registered()

    # S2: 启动后台清理任务
    async def cleanup_task():
        """定期清理过期任务"""
        while True:
            try:
                await cleanup_expired_tasks()
            except Exception as e:
                logger.error(f"清理过期任务失败: {e}")
            await asyncio.sleep(3600)  # 每小时执行一次
    
    # 启动后台任务
    asyncio.create_task(cleanup_task())
    logger.info("后台清理任务已启动")


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时清理后台shell进程"""
    # 【Phase 1修复 小健 2026-05-14】函数内import避免触发register
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
