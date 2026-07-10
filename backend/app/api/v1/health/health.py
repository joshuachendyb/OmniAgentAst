from fastapi import APIRouter, Request
from pydantic import BaseModel
from app.utils.time_utils import get_utc_timestamp
from app.tools import tool_registry

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


@router.get("/tool/list")
async def list_tools():
    """获取所有已注册的工具列表"""

    tools = tool_registry.to_openai_tools()

    tool_list = []
    for t in tools:
        func = t.get('function', {})
        name = func.get('name', '')
        desc = func.get('description', '')
        params = func.get('parameters', {})
        required = params.get('required', [])
        props = list(params.get('properties', {}).keys())

        tool_list.append({
            "name": name,
            "description": desc[:100] if desc else "",
            "required_params": required,
            "optional_params": [p for p in props if p not in set(required)],
            "inputSchema": params,
        })

    return {
        "total": len(tool_list),
        "tools": tool_list
    }
