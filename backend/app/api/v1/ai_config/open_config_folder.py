import os
import subprocess
from . import router
from pathlib import Path
from fastapi import HTTPException
from app.services import AIServiceFactory
from app.utils.logger import logger


@router.post("/config/open-folder")
async def open_config_folder():
    try:
        config_path = Path(AIServiceFactory.get_config_path())
        config_dir = str(config_path.parent)
        if not os.path.exists(config_dir):
            raise HTTPException(status_code=404, detail=f"配置目录不存在: {config_dir}")
        subprocess.Popen(['explorer', '/e,', config_dir],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL)
        logger.info(f"已打开配置目录: {config_dir}")
        return {"success": True, "path": config_dir}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"打开配置目录失败: {e}")
        raise HTTPException(status_code=500, detail=f"打开配置目录失败: {str(e)}")
