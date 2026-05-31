from . import router
from .models import ConfigPathResponse
from ._helpers import get_config_path
from ._decorators import handle_config_errors


@router.get("/config/path", response_model=ConfigPathResponse)
@handle_config_errors("获取配置路径")
async def get_config_path_endpoint():
    config_path = get_config_path()
    return ConfigPathResponse(
        config_path=str(config_path),
        config_dir=str(config_path.parent),
        exists=config_path.exists()
    )
