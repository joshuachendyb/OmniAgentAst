from typing import Optional
from app.utils.logger import logger
from app.services import AIServiceFactory


def _invalidate_ai_service_cache(provider: Optional[str] = None) -> None:
    """清理AIServiceFactory缓存，强制下次重新读取配置 - 小健 2026-05-25"""
    AIServiceFactory._instance = None
    AIServiceFactory._config = None
    if provider:
        AIServiceFactory._current_provider = provider
    logger.info("已清空AIServiceFactory缓存，下次调用将重新加载配置")
