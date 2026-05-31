from app.utils.logger import logger
from .models import SecurityConfig


def _update_security(config_data: dict, update) -> None:
    if not update.security:
        return
    config_data['security'] = {
        "contentFilterEnabled": update.security.contentFilterEnabled,
        "contentFilterLevel": update.security.contentFilterLevel,
        "whitelistEnabled": update.security.whitelistEnabled,
        "commandWhitelist": update.security.commandWhitelist,
        "commandBlacklist": update.security.commandBlacklist,
        "confirmDangerousOps": update.security.confirmDangerousOps,
        "maxFileSize": update.security.maxFileSize,
    }
    logger.info("更新安全配置成功")
