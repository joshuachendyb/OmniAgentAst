import asyncio
import inspect
from fastapi import APIRouter
from pydantic import BaseModel
import uuid as _uuid
import re as _re

router = APIRouter()

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
    from app.services.tools import tool_registry

    tool_name = request.tool_name
    params = request.params

    impl = tool_registry.get_implementation(tool_name)

    if impl is None:
        return ToolExecuteResponse(
            tool_name=tool_name,
            success=False,
            error=f"Tool '{tool_name}' not found or not registered"
        )

    try:
        from app.services.context_vars import _current_task_id
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

        if asyncio.iscoroutine(result):
            result = await result

        return ToolExecuteResponse(
            tool_name=tool_name,
            success=True,
            result=result if isinstance(result, dict) else {"output": str(result)}
        )
    except Exception as e:
        err_msg = str(e)
        if "missing" in err_msg and "required positional argument" in err_msg:
            match = _re.search(r"missing \d+ required positional argument[s]?:\s*(.+)", err_msg)
            missing_params = match.group(1) if match else "未知参数"
            err_msg = f"缺少必填参数: {missing_params}。请参考tool/list获取{tool_name}的inputSchema"
        return ToolExecuteResponse(
            tool_name=tool_name,
            success=False,
            error=err_msg
        )
