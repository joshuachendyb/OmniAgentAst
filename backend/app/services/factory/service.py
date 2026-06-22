# -*- coding: utf-8 -*-
"""
service — 服务创建与获取

合并: get_service + get_service_for_model
小沈 2026-06-17
"""

from typing import Optional
import threading

from app.utils.logger import setup_logger
from app.utils.time_utils import now_str
from app.services.llm import BaseAIService
from app.services.factory.lifecycle import close_instance_sync

logger = setup_logger(__name__)

_instance: Optional[BaseAIService] = None
_current_provider: str = ""
_instance_lock = threading.Lock()


def get_resolver_and_config():
    """获取resolver和配置 — 小沈 2026-06-08; 2026-06-17 去除_前缀"""
    from app.services.ai_config_resolver import get_ai_config_resolver
    resolver = get_ai_config_resolver()
    final_provider, final_model = resolver.resolve_provider_model()
    ai_config = resolver.get_ai_config()
    return resolver, final_provider, final_model, ai_config


def validate_provider_model(final_provider: str, final_model: str) -> None:
    """验证provider和model — 小沈 2026-06-08; 2026-06-17 去除_前缀"""
    if not final_provider:
        raise ValueError("未找到有效的AI provider配置")
    if not final_model:
        raise ValueError("未找到有效的AI model配置")


def check_cache_valid(final_provider: str, final_model: str) -> bool:
    """检查缓存是否有效 — 小沈 2026-06-08; 2026-06-17 去除_前缀"""
    return _instance is not None and _current_provider == final_provider and _instance.model == final_model


def cleanup_old_instance(new_provider: str = "") -> None:
    """清理旧实例 — 小沈 2026-06-08; 小欧 2026-06-09 新增new_provider参数; 2026-06-17 去除_前缀+透传层"""
    global _instance, _current_provider
    old_instance = _instance
    _instance = None
    _current_provider = new_provider
    close_instance_sync(old_instance)


def log_service_creation(final_provider: str, final_model: str) -> None:
    """记录服务创建日志 — 小沈 2026-06-08; 2026-06-17 去除_前缀+透传层"""
    log_msg = f"[AIServiceFactory] 创建服务实例: provider={final_provider}, model={final_model}"
    print(f"[{now_str('%H:%M:%S')}] {log_msg}")
    logger.info(log_msg)


def get_provider_config(ai_config: dict, final_provider: str) -> dict:
    """获取provider配置 — 小沈 2026-06-08; 2026-06-17 去除_前缀"""
    provider_config = ai_config.get(final_provider, {})
    if not provider_config:
        raise ValueError(f"provider {final_provider} 的配置为空,请检查 config.yaml")
    return provider_config


def create_service_instance(provider_config: dict, final_provider: str, final_model: str) -> BaseAIService:
    """创建服务实例 — 小沈 2026-06-08; 2026-06-17 去除_前缀+透传层"""
    return BaseAIService(
        api_key=(provider_config.get("api_key") or "").strip(),
        model=final_model,
        api_base=(provider_config.get("api_base") or "https://api.openai.com/v1").strip(),
        provider=final_provider,
        timeout=provider_config.get("timeout", 30),
        max_tokens=provider_config.get("max_tokens"),
        temperature=float(provider_config.get("temperature", 0.7)),
        seed=provider_config.get("seed", None),
    )


def get_service() -> BaseAIService:
    """获取服务实例 — 小沈 2026-06-08
    P2-09修复: 删除未使用的config_path
    【修复P1-1 2026-06-09 小沈】threading.Lock保护多线程安全
    """
    global _instance, _current_provider

    _, final_provider, final_model, ai_config = get_resolver_and_config()

    validate_provider_model(final_provider, final_model)

    if check_cache_valid(final_provider, final_model):
        return _instance

    with _instance_lock:
        if check_cache_valid(final_provider, final_model):
            return _instance
        cleanup_old_instance(final_provider)

        log_service_creation(final_provider, final_model)

        provider_config = get_provider_config(ai_config, final_provider)

        _instance = create_service_instance(provider_config, final_provider, final_model)

    return _instance


def reset_instance():
    """重置实例 — 小沈 2026-06-08
    P1-07修复: 公开reset方法,替代直接操作私有变量
    【修复P1-1 2026-06-09 小沈】threading.Lock保护
    """
    global _instance, _current_provider
    with _instance_lock:
        old = _instance
        _instance = None
        _current_provider = ""
    return old


def set_instance(instance, provider=""):
    """设置实例 — 小沈 2026-06-08
    P1-07修复: 公开set方法,替代直接操作私有变量
    【修复P1-1 2026-06-09 小沈】threading.Lock保护
    """
    global _instance, _current_provider
    with _instance_lock:
        _instance = instance
        _current_provider = provider


def get_service_for_model(provider: str, model: str):
    """获取指定provider/model的服务实例 — 小沈 2026-06-08
    P2-07修复: 使用set_instance替代直接操作私有变量; P2-09: 删除未使用的config_path
    """
    from app.services.ai_config_resolver import get_ai_config_resolver
    resolver = get_ai_config_resolver()
    ai_config = resolver.get_ai_config()
    
    provider_config = resolver.get_service_config(provider, model)
    
    cleanup_old_instance(provider)
    
    log_service_creation(provider, model)
    
    if not provider_config:
        provider_config = {}
    
    instance = create_service_instance(provider_config, provider, model)
    set_instance(instance, provider)

    return instance