# -*- coding: utf-8 -*-
"""
get_service_for_model — 从 factory.py 拷出

拷贝来源: factory.py 第264-323行

【小欧 2026-06-09】委托到 get_service.py 共享函数，消除重复
P1-07/P2-07修复: 使用公开set_instance替代私有变量访问
"""

from typing import Optional

from app.utils.logger import setup_logger
from app.services.factory.get_service import (
    create_service_instance,
    log_service_creation,
    cleanup_old_instance,
    set_instance,
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


def get_service_for_model(provider: str, model: str):
    """P2-07修复: 使用set_instance替代直接操作私有变量; P2-09: 删除未使用的config_path"""
    resolver, ai_config = _get_resolver_and_ai_config()
    
    provider_config = _get_provider_config_safe(resolver, provider, model)
    
    cleanup_old_instance(provider)
    
    log_service_creation(provider, model)
    
    if not provider_config:
        provider_config = {}
    
    instance = create_service_instance(provider_config, provider, model)
    set_instance(instance, provider)

    return instance
