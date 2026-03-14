from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from datetime import datetime
import traceback
from pathlib import Path

from app.api.v1 import health, chat_non_stream, chat_stream, file_operations, config, sessions, security, execution, metrics
from app.utils.logger import logger
from app.utils.monitoring import setup_monitoring

# 配置日志 - 使用统一的 logger 配置，不再使用 basicConfig
# 日志统一在 app/utils/logger.py 中配置

def get_version() -> str:
    """从version.txt读取版本号"""
    try:
        current_file = Path(__file__).resolve()
        backend_dir = current_file.parent.parent
        project_root = backend_dir.parent
        version_file = project_root / "version.txt"
        
        print(f"[Version] current_file: {current_file}")
        print(f"[Version] backend_dir: {backend_dir}")
        print(f"[Version] project_root: {project_root}")
        print(f"[Version] version_file: {version_file}")
        print(f"[Version] version_file exists: {version_file.exists()}")
        
        if version_file.exists():
            with open(version_file, 'r', encoding='utf-8') as f:
                version = f.readline().strip()
            print(f"[Version] read version: {version}")
            return version.lstrip('v')
    except Exception as e:
        print(f"[Version] Failed to read version.txt: {e}")
    return "0.4.14"

app = FastAPI(
    title="OmniAgentAst API",
    description="OmniAgentAst 桌面版后端API",
    version=get_version()
)

print("OmniAgentAst Backend v" + get_version() + " started")

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
app.include_router(chat_non_stream.router, prefix="/api/v1", tags=["chat"])
app.include_router(chat_stream.router, prefix="/api/v1", tags=["chat"])
app.include_router(file_operations.router, prefix="/api/v1", tags=["file-operations"])
app.include_router(config.router, prefix="/api/v1", tags=["config"])
app.include_router(sessions.router, prefix="/api/v1", tags=["sessions"])
app.include_router(security.router, prefix="/api/v1", tags=["security"])
app.include_router(execution.router, prefix="/api/v1", tags=["execution"])
app.include_router(metrics.router, prefix="/api/v1", tags=["metrics"])


# 【小沈修复 2026-03-14】启动后台清理任务，定期清理过期任务
import asyncio
from app.api.v1.chat_stream import cleanup_expired_tasks

@app.on_event("startup")
async def startup_event():
    """应用启动时启动后台任务"""
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


@app.get("/")
async def root():
    return {
        "message": "OmniAgentAst API",
        "version": "0.2.2",
        "docs": "/docs"
    }