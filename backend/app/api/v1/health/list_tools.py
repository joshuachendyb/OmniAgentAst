from fastapi import APIRouter

router = APIRouter()

@router.get("/tool/list")
async def list_tools():
    """
    获取所有已注册的工具列表
    """
    from app.services.tools import tool_registry

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
