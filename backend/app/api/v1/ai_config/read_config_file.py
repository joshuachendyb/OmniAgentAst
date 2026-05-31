from . import router
from ._helpers import get_config_path
from ._decorators import handle_config_errors
from fastapi import HTTPException


@router.get("/config/read")
@handle_config_errors("读取配置文件")
async def read_config_file():
    config_path = get_config_path()
    if not config_path.exists():
        raise HTTPException(status_code=404, detail=f"配置文件不存在: {config_path}")
    with open(config_path, 'r', encoding='utf-8') as f:
        content = f.read()
    return {"config_content": content}
