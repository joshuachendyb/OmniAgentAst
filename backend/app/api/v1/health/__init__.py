from fastapi import APIRouter
from .health import router as health_router
from .execute_tool import router as execute_tool_router

router = APIRouter()
router.include_router(health_router)
router.include_router(execute_tool_router)


@router.get("/tool/list")
async def list_tools():
    """
    获取所有已注册的工具列表
    """
    from app.tools import tool_registry

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
            "inputSchema": params,
        })

    return {
        "total": len(tool_list),
        "tools": tool_list
    }


__all__ = ["router"]
