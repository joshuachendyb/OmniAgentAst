from fastapi import HTTPException
from app.utils.logger import logger


def _update_api_keys(config_data: dict, update) -> None:
    for provider_name, api_key in (update.provider_api_keys or {}).items():
        if provider_name in config_data.get('ai', {}):
            config_data['ai'][provider_name]['api_key'] = api_key.strip()
            logger.info(f"更新Provider API Key成功: {provider_name}")
        else:
            raise HTTPException(status_code=400, detail=f"不支持的Provider: {provider_name}")
