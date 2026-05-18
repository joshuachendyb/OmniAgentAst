from fastapi import APIRouter
from datetime import datetime
from pydantic import BaseModel
from pathlib import Path

# 使用统一的日志配置
from app.utils.logger import logger

router = APIRouter()

class HealthResponse(BaseModel):
    status: str
    timestamp: str
    version: str


# 【修复-波次5】从version.txt读取版本号，确保与main.py一致
# 【修复-2026-02-18】使用绝对路径，确保在任何工作目录下都能正确读取
# 【修复-2026-02-28】添加UTF-8编码支持，解决中文编码问题
# 【修复-2026-03-01】只读取第一行作为版本号
def get_version() -> str:
    """从version.txt读取版本号"""
    try:
        # 使用绝对路径：从当前文件(backend/app/api/v1/health.py)向上三级到项目根目录
        current_file = Path(__file__).resolve()
        api_dir = current_file.parent.parent.parent
        backend_dir = api_dir.parent
        project_root = backend_dir.parent
        version_file = project_root / "version.txt"
        
        if version_file.exists():
            # 【修复】使用UTF-8编码读取，解决中文编码问题
            # 【修复】只读取第一行作为版本号
            with open(version_file, 'r', encoding='utf-8') as f:
                version = f.readline().strip()
            logger.info(f"Successfully read version from version.txt: {version}")
            # 去掉v前缀（如果有）
            return version.lstrip('v')
    except Exception as e:
        logger.warning(f"Failed to read version.txt: {e}")
    return "0.4.14"  # 默认版本（更新为最新版本）

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


class ToolExecuteRequest(BaseModel):
    tool_name: str
    params: dict = {}


class ToolExecuteResponse(BaseModel):
    tool_name: str
    success: bool
    result: dict = {}
    error: str = ""


@router.post("/tool/execute", response_model=ToolExecuteResponse)
async def execute_tool(request: ToolExecuteRequest):
    """
    直接执行工具的测试接口
    用法: POST /api/v1/tool/execute
    Body: {"tool_name": "read_file", "params": {"path": "app/main.py"}}
    """
    from app.services.tools import ensure_tools_registered, tool_registry
    import asyncio
    import inspect
    
    # 确保工具已注册
    ensure_tools_registered()
    
    tool_name = request.tool_name
    params = request.params
    
    # 获取工具实现
    impl = tool_registry.get_implementation(tool_name)
    
    if impl is None:
        return ToolExecuteResponse(
            tool_name=tool_name,
            success=False,
            error=f"Tool '{tool_name}' not found or not registered"
        )
    
    try:
        # 检查是否异步函数
        if inspect.iscoroutinefunction(impl):
            result = await impl(**params)
        else:
            # 同步函数放到线程池执行，避免阻塞
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, lambda: impl(**params))
        
        # 处理返回结果
        if asyncio.iscoroutine(result):
            result = await result
            
        return ToolExecuteResponse(
            tool_name=tool_name,
            success=True,
            result=result if isinstance(result, dict) else {"output": str(result)}
        )
    except Exception as e:
        return ToolExecuteResponse(
            tool_name=tool_name,
            success=False,
            error=str(e)
        )


@router.get("/tool/list")
async def list_tools():
    """
    获取所有已注册的工具列表
    """
    from app.services.tools import ensure_tools_registered, tool_registry
    
    ensure_tools_registered()
    
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
            "optional_params": props
        })
    
    return {
        "total": len(tool_list),
        "tools": tool_list
    }
