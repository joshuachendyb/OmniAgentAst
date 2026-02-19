from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from datetime import datetime
import traceback
import logging
from pathlib import Path

from app.api.v1 import health, chat, file_operations, config, sessions, security, execution
from app.utils.logger import logger

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# 【修复-波次5】从version.txt读取版本号，确保所有地方版本一致
# 【修复-2026-02-18】使用绝对路径，确保在任何工作目录下都能正确读取
def get_version() -> str:
    """从version.txt读取版本号"""
    try:
        # 使用绝对路径：从当前文件(backend/app/main.py)向上两级到项目根目录
        current_file = Path(__file__).resolve()
        backend_dir = current_file.parent.parent
        project_root = backend_dir.parent
        version_file = project_root / "version.txt"
        
        logger.info(f"Looking for version.txt at: {version_file}")
        
        if version_file.exists():
            version = version_file.read_text().strip()
            logger.info(f"Read version: {version}")
            # 去掉v前缀（如果有）
            return version.lstrip('v')
        else:
            logger.warning(f"version.txt not found at {version_file}")
    except Exception as e:
        logger.warning(f"Failed to read version.txt: {e}")
    return "0.3.5"  # 默认版本（更新为最新版本）

app = FastAPI(
    title="OmniAgentAst API",
    description="OmniAgentAst 桌面版后端API",
    version=get_version()
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制为前端地址
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 【修复】全局异常处理 - HTTP异常
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """处理HTTP异常"""
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

# 【修复】全局异常处理 - 验证异常
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """处理请求验证异常"""
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

# 【修复】全局异常处理 - 通用异常
@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """处理所有未捕获的异常"""
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

# 注册路由
app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(chat.router, prefix="/api/v1", tags=["chat"])
app.include_router(file_operations.router, prefix="/api/v1", tags=["file-operations"])
app.include_router(config.router, prefix="/api/v1", tags=["config"])
app.include_router(sessions.router, prefix="/api/v1", tags=["sessions"])
app.include_router(security.router, prefix="/api/v1", tags=["security"])
app.include_router(execution.router, prefix="/api/v1", tags=["execution"])

@app.get("/")
async def root():
    return {
        "message": "OmniAgentAst API",
        "version": "0.2.2",
        "docs": "/docs"
    }

# 启动命令: uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
