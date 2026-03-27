from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from datetime import datetime
import traceback
from pathlib import Path

# 【已废弃】chat_non_stream 已不使用，前端已改用 sse.ts 流式聊天 V2
# from app.api.v1 import health, chat_non_stream, chat2, init_model_select, file_operations, config, sessions, security, execution, metrics
# 【阶段6废弃端点但保留代码】chat2.py 已移至 backup/chat2.py
# cleanup_expired_tasks 已迁移到 react_sse_wrapper.py
from app.api.v1 import health, init_model_select, file_operations, config, sessions, security, execution, metrics
# chat_stream 暂时禁用，使用 chat_router 替代
from app.utils.logger import logger
from app.utils.monitoring import setup_monitoring

# 只过滤uvicorn的访问日志，不影响应用日志
import logging
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

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
# 【已废弃】chat_non_stream.py 已不使用，前端已改用 sse.ts 流式聊天 V2
# app.include_router(chat_non_stream.router, prefix="/api/v1", tags=["chat"])
# 【暂时禁用】使用 chat2 替代 chat_stream（待验证后决定是否删除）
# app.include_router(chat_stream.router, prefix="/api/v1", tags=["chat"])
# 【阶段6废弃】chat2.py 端点已废弃，使用 chat_router (V2) 替代
# app.include_router(chat2.router, prefix="/api/v1", tags=["chat"])
# 【Stage 5 新增】chat_router - 6步完整流程版本
from app.services.chat_router import router as chat_router_router, task_router
app.include_router(chat_router_router, prefix="/api/v1", tags=["chat"])
app.include_router(task_router, prefix="/api/v1", tags=["chat"])
app.include_router(init_model_select.router, prefix="/api/v1", tags=["chat"])
app.include_router(file_operations.router, prefix="/api/v1", tags=["file-operations"])
app.include_router(config.router, prefix="/api/v1", tags=["config"])
app.include_router(sessions.router, prefix="/api/v1", tags=["sessions"])
app.include_router(security.router, prefix="/api/v1", tags=["security"])
app.include_router(execution.router, prefix="/api/v1", tags=["execution"])
app.include_router(metrics.router, prefix="/api/v1", tags=["metrics"])


# 【阶段6更新】cleanup_expired_tasks 改为从 react_sse_wrapper 导入
import asyncio
from app.services.react_sse_wrapper import cleanup_expired_tasks

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