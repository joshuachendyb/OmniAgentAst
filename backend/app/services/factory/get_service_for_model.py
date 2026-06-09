# -*- coding: utf-8 -*-
"""
get_service_for_model — 从 factory.py 拷出

拷贝来源: factory.py 第264-323行

【小欧 2026-06-09】委托到 get_service.py 共享函数，消除重复
"""

from typing import Optional

from app.utils.logger import setup_logger
from app.services.factory.get_service import (
    _create_service_instance,
    _log_service_creation,
    _cleanup_old_instance,
)

logger = setup_logger("OmniAgentAst.AIServiceFactory")


def _get_resolver_and_ai_config():
    """获取resolver和AI配置 - 小沈 2026-06-08"""
    from app.services.ai_config_resolver import get_ai_config_resolver
    resolver = get_ai_config_resolver()
    ai_config = resolver.get_ai_config()
    return resolver, ai_config


def _get_provider_config_safe(resolver, provider: str, model: str) -> dict:
    """安全获取provider配置 - 小沈 2026-06-08"""
    try:
        return resolver.get_service_config(provider, model)
    except ValueError as e:
        raise ValueError(str(e))


def get_service_for_model(provider: str, model: str, config_path: Optional[str] = None):
    """拷贝自 factory.py 第264-323行"""
    import app.services.factory.get_service as gs

    resolver, ai_config = _get_resolver_and_ai_config()
    
    provider_config = _get_provider_config_safe(resolver, provider, model)
    
    _cleanup_old_instance(provider)
    
    _log_service_creation(provider, model)
    
    if not provider_config:
        provider_config = {}
    
    gs._instance = _create_service_instance(provider_config, provider, model)

    return gs._instance
