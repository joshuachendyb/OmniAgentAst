from fastapi import HTTPException
from app.utils.logger import logger
from app.services import AIServiceFactory


def _update_provider(config_data: dict, update) -> None:
    ai_config = config_data.get('ai', {})
    if update.ai_provider not in ai_config:
        raise HTTPException(status_code=400, detail=f"不支持的提供商: {update.ai_provider}")
    config_data['ai']['provider'] = update.ai_provider
    AIServiceFactory.reset()
    logger.info(f"更新AI Provider: {update.ai_provider}")
