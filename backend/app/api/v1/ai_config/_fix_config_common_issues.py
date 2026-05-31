from typing import Dict, Any
from app.utils.logger import logger


def _fix_config_common_issues(config_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    自动修复常见的配置问题

    修复内容：
    1. 删除所有 provider 下废弃的 model 字段
    """
    ai_config = config_data.get('ai', {})

    for provider_name in ai_config.keys():
        if provider_name == 'provider' or provider_name == 'model':
            continue
        provider_data = ai_config.get(provider_name, {})
        if isinstance(provider_data, dict) and 'model' in provider_data:
            del provider_data['model']
            logger.info(f"已删除 provider '{provider_name}' 下废弃的 model 字段")

    return config_data
