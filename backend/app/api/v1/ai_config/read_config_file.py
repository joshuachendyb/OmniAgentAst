from . import router
from pathlib import Path
from fastapi import HTTPException
from app.services import AIServiceFactory
from app.utils.logger import logger


@router.get("/config/read")
async def read_config_file():
    try:
        config_path = Path(AIServiceFactory.get_config_path())
        if not config_path.exists():
            raise HTTPException(status_code=404, detail=f"配置文件不存在: {config_path}")
        with open(config_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return {"config_content": content}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"读取配置文件失败: {e}")
        raise HTTPException(status_code=500, detail=f"读取配置文件失败: {str(e)}")
