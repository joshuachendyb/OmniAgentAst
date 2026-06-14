from fastapi import APIRouter, Request
from pydantic import BaseModel
from app.utils.time_utils import get_utc_timestamp

router = APIRouter()

class HealthResponse(BaseModel):
    status: str
    timestamp: str
    version: str

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
    return HealthResponse(
        status="healthy",
        timestamp=get_utc_timestamp(),
        version=request.app.version
    )

@router.post("/echo", response_model=EchoResponse)
async def echo(request: EchoRequest):
    """
    测试通信接口 - 回显收到的消息
    """
    return EchoResponse(
        received=request.message,
        timestamp=get_utc_timestamp()
    )
