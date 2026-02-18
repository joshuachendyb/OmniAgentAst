from fastapi import APIRouter
from datetime import datetime
from pydantic import BaseModel
from pathlib import Path

router = APIRouter()

class HealthResponse(BaseModel):
    status: str
    timestamp: str
    version: str


# 【修复-波次5】从version.txt读取版本号，确保与main.py一致
def get_version() -> str:
    """从version.txt读取版本号"""
    try:
        # 从api/v1目录向上三级找到项目根目录
        version_file = Path(__file__).parent.parent.parent.parent / "version.txt"
        if version_file.exists():
            version = version_file.read_text().strip()
            # 去掉v前缀（如果有）
            return version.lstrip('v')
    except Exception:
        pass
    return "0.2.3"  # 默认版本

class EchoRequest(BaseModel):
    message: str

class EchoResponse(BaseModel):
    received: str
    timestamp: str

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    健康检查接口
    """
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow().isoformat(),
        version=get_version()  # 【修复-波次5】使用统一版本号
    )

@router.post("/echo", response_model=EchoResponse)
async def echo(request: EchoRequest):
    """
    测试通信接口 - 回显收到的消息
    """
    return EchoResponse(
        received=request.message,
        timestamp=datetime.utcnow().isoformat()
    )
