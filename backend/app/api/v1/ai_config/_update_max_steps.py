from fastapi import HTTPException
from app.utils.logger import logger


def _update_max_steps(config_data: dict, update) -> None:
    if update.max_steps < 1:
        raise HTTPException(status_code=400, detail="max_steps 必须大于等于 1")
    if update.max_steps > 1000:
        raise HTTPException(status_code=400, detail="max_steps 不能超过 1000")
    config_data.setdefault('app', {})['max_steps'] = update.max_steps
    logger.info(f"更新max_steps: {update.max_steps}")
