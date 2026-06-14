# -*- coding: utf-8 -*-
"""
get_service — 从 factory.py 拷出

拷贝来源: factory.py 第204-250行
"""

from typing import Optional
import threading

from app.utils.logger import setup_logger
from app.utils.time_utils import now_str
from app.services.llm_core import BaseAIService
from app.services.factory.close_instance_sync import close_instance_sync

logger = setup_logger(__name__)

_instance: Optional[BaseAIService] = None
_current_provider: str = ""
_instance_lock = threading.Lock()  # 【修复P1-1 2026-06-09 小沈】多线程部署安全


def _get_resolver_and_config():
    """获取resolver和配置 - 小沈 2026-06-08"""
    from app.services.ai_config_resolver import get_ai_config_resolver
    resolver = get_ai_config_resolver()
    final_provider, final_model = resolver.resolve_provider_model()
    ai_config = resolver.get_ai_config()
    return resolver, final_provider, final_model, ai_config


def _validate_provider_model(final_provider: str, final_model: str) -> None:
    """验证provider和model - 小沈 2026-06-08"""
    if not final_provider:
        raise ValueError("未找到有效的AI provider配置")
    if not final_model:
        raise ValueError("未找到有效的AI model配置")


def _check_cache_valid(final_provider: str, final_model: str) -> bool:
    """检查缓存是否有效 - 小沈 2026-06-08"""
    return _instance is not None and _current_provider == final_provider and _instance.model == final_model


def _cleanup_old_instance(new_provider: str = "") -> None:
    """清理旧实例 - 小沈 2026-06-08; 小欧 2026-06-09 新增new_provider参数"""
    global _instance, _current_provider
    old_instance = _instance
    _instance = None
    _current_provider = new_provider
    close_instance_sync(old_instance)


def _log_service_creation(final_provider: str, final_model: str) -> None:
    """记录服务创建日志 - 小沈 2026-06-08"""
    log_msg = f"[AIServiceFactory] 创建服务实例: provider={final_provider}, model={final_model}"
    print(f"[{now_str('%H:%M:%S')}] {log_msg}")
    logger.info(log_msg)


def _get_provider_config(ai_config: dict, final_provider: str) -> dict:
    """获取provider配置 - 小沈 2026-06-08"""
    provider_config = ai_config.get(final_provider, {})
    if not provider_config:
        raise ValueError(f"provider {final_provider} 的配置为空,请检查 config.yaml")
    return provider_config


def _create_service_instance(provider_config: dict, final_provider: str, final_model: str) -> BaseAIService:
    """创建服务实例 - 小沈 2026-06-08"""
    return BaseAIService(
        api_key=(provider_config.get("api_key") or "").strip(),
        model=final_model,
        api_base=(provider_config.get("api_base") or "https://api.openai.com/v1").strip(),
        provider=final_provider,
        timeout=provider_config.get("timeout", 30),
        max_tokens=provider_config.get("max_tokens", 4096),
        temperature=float(provider_config.get("temperature", 0.7)),
        seed=provider_config.get("seed", None),
    )


def get_service() -> BaseAIService:
    """拷贝自 factory.py 第204-250行 — P2-09修复: 删除未使用的config_path
    【修复P1-1 2026-06-09 小沈】threading.Lock保护多线程安全
    """
    global _instance, _current_provider

    _, final_provider, final_model, ai_config = _get_resolver_and_config()
    
    _validate_provider_model(final_provider, final_model)
    
    if _check_cache_valid(final_provider, final_model):
        return _instance
    
    with _instance_lock:
        # double-checked locking
        if _check_cache_valid(final_provider, final_model):
            return _instance
        _cleanup_old_instance(final_provider)
        
        _log_service_creation(final_provider, final_model)
        
        provider_config = _get_provider_config(ai_config, final_provider)
        
        _instance = _create_service_instance(provider_config, final_provider, final_model)

    return _instance


def reset_instance():
    """P1-07修复: 公开reset方法,替代直接操作私有变量
    【修复P1-1 2026-06-09 小沈】threading.Lock保护
    """
    global _instance, _current_provider
    with _instance_lock:
        old = _instance
        _instance = None
        _current_provider = ""
    return old


def set_instance(instance, provider=""):
    """P1-07修复: 公开set方法,替代直接操作私有变量
    【修复P1-1 2026-06-09 小沈】threading.Lock保护
    """
    global _instance, _current_provider
    with _instance_lock:
        _instance = instance
        _current_provider = provider


def create_service_instance(provider_config: dict, final_provider: str, final_model: str) -> BaseAIService:
    """公开接口：创建服务实例 — 小沈 2026-06-09"""
    return _create_service_instance(provider_config, final_provider, final_model)


def log_service_creation(final_provider: str, final_model: str) -> None:
    """公开接口：记录服务创建日志 — 小沈 2026-06-09"""
    _log_service_creation(final_provider, final_model)


def cleanup_old_instance(new_provider: str = "") -> None:
    """公开接口：清理旧实例 — 小沈 2026-06-09"""
    _cleanup_old_instance(new_provider)
