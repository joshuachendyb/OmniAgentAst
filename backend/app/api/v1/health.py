from fastapi import APIRouter
from datetime import datetime, timezone
from pydantic import BaseModel

# 使用统一的日志配置
from app.utils.logger import logger
from app.utils.version import get_version

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
async def health_check():
    """
    健康检查接口
    """
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(timezone.utc).isoformat(),
        version=get_version()  # 【修复-波次5】使用统一版本号
    )

@router.post("/echo", response_model=EchoResponse)
async def echo(request: EchoRequest):
    """
    测试通信接口 - 回显收到的消息
    """
    return EchoResponse(
        received=request.message,
        timestamp=datetime.now(timezone.utc).isoformat()
    )


class ToolExecuteRequest(BaseModel):
    tool_name: str
    params: dict = {}
    parameters: dict = {}  # 兼容别名 - 小健 2026-05-21


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
    # 兼容parameters和params字段, parameters优先 - 小健 2026-05-21
    params = request.parameters if request.parameters is not None else request.params
    
    # 获取工具实现
    impl = tool_registry.get_implementation(tool_name)
    
    if impl is None:
        return ToolExecuteResponse(
            tool_name=tool_name,
            success=False,
            error=f"Tool '{tool_name}' not found or not registered"
        )
    
    try:
        # 与Agent调用链保持一致：设置_current_task_id ContextVar
        # Agent在react_sse_wrapper.py:525生成task_id，在base_react.py:793设置ContextVar
        from app.services.context_vars import _current_task_id
        import uuid as _uuid
        _api_task_id = str(_uuid.uuid4())
        _current_task_id.set(_api_task_id)
        
        if inspect.iscoroutinefunction(impl):
            result = await impl(**params)
        else:
            loop = asyncio.get_event_loop()
            _captured_task_id = _current_task_id.get()
            def _run_with_task_context():
                _current_task_id.set(_captured_task_id)
                return impl(**params)
            result = await loop.run_in_executor(None, _run_with_task_context)
        
        # 处理返回结果
        if asyncio.iscoroutine(result):
            result = await result
            
        return ToolExecuteResponse(
            tool_name=tool_name,
            success=True,
            result=result if isinstance(result, dict) else {"output": str(result)}
        )
    except Exception as e:
        # 【修复 小健 2026-05-21】参数错误友好提示
        err_msg = str(e)
        if "missing" in err_msg and "required positional argument" in err_msg:
            import re as _re
            match = _re.search(r"missing \d+ required positional argument[s]?:\s*(.+)", err_msg)
            missing_params = match.group(1) if match else "未知参数"
            err_msg = f"缺少必填参数: {missing_params}。请参考tool/list获取{tool_name}的inputSchema"
        elif "missing 1 required positional argument" in err_msg:
            import re as _re
            match = _re.search(r"(\w+)\(\) missing \d+ required positional argument[s]?:\s*'?(\w+)'?", err_msg)
            if match:
                err_msg = f"工具{match.group(1)}缺少必填参数'{match.group(2)}'"
        return ToolExecuteResponse(
            tool_name=tool_name,
            success=False,
            error=err_msg
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
            "optional_params": props,
            "inputSchema": params,  # 完整JSON Schema - 小健 2026-05-21
        })
    
    return {
        "total": len(tool_list),
        "tools": tool_list
    }
