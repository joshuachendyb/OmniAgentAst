import os
import subprocess
from . import router
from ._helpers import get_config_path
from ._decorators import handle_config_errors
from fastapi import HTTPException
from app.utils.response_utils import api_success
from app.utils.logger import logger


@router.post("/config/open-folder")
@handle_config_errors("打开配置目录")
async def open_config_folder():
    config_path = get_config_path()
    config_dir = str(config_path.parent)
    if not os.path.exists(config_dir):
        raise HTTPException(status_code=404, detail=f"配置目录不存在: {config_dir}")
    subprocess.Popen(['explorer', '/e,', config_dir],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL)
    logger.info(f"已打开配置目录: {config_dir}")
    return api_success(path=config_dir)
