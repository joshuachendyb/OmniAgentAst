from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from app.api.v1 import health, chat, file_operations

app = FastAPI(
    title="OmniAgentAst API",
    description="OmniAgentAst 桌面版后端API",
    version="0.2.2"
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制为前端地址
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(chat.router, prefix="/api/v1", tags=["chat"])
app.include_router(file_operations.router, prefix="/api/v1", tags=["file-operations"])

@app.get("/")
async def root():
    return {
        "message": "OmniAgentAst API",
        "version": "0.2.2",
        "docs": "/docs"
    }

# 启动命令: uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
