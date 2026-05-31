from . import router
from .models import ConfigPathResponse
from pathlib import Path
from fastapi import HTTPException
from app.services import AIServiceFactory
from app.utils.logger import logger


@router.get("/config/path", response_model=ConfigPathResponse)
async def get_config_path():
    try:
        config_path = Path(AIServiceFactory.get_config_path())
        return ConfigPathResponse(
            config_path=str(config_path),
            config_dir=str(config_path.parent),
            exists=config_path.exists()
        )
    except Exception as e:
        logger.error(f"获取配置路径失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取配置路径失败: {str(e)}")
