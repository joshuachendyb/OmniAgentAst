# -*- coding: utf-8 -*-
"""
get_service — 从 factory.py 拷出

拷贝来源: factory.py 第204-250行
"""

from datetime import datetime
from typing import Optional

from app.utils.logger import setup_logger
from app.services.llm_core import BaseAIService
from app.services.factory.close_instance_sync import close_instance_sync

logger = setup_logger("OmniAgentAst.AIServiceFactory")

_instance: Optional[BaseAIService] = None
_current_provider: str = ""


def get_service(config_path: Optional[str] = None) -> BaseAIService:
    """拷贝自 factory.py 第204-250行"""
    global _instance, _current_provider

    from app.services.ai_config_resolver import get_ai_config_resolver
    resolver = get_ai_config_resolver()
    final_provider, final_model = resolver.resolve_provider_model()
    ai_config = resolver.get_ai_config()

    if not final_provider:
        raise ValueError("未找到有效的AI provider配置")
    if not final_model:
        raise ValueError("未找到有效的AI model配置")

    if _instance is not None and _current_provider == final_provider and _instance.model == final_model:
        return _instance

    old_instance = _instance
    _instance = None
    _current_provider = final_provider
    close_instance_sync(old_instance)

    log_msg = f"[AIServiceFactory] 创建服务实例: provider={final_provider}, model={final_model}"
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {log_msg}")
    logger.info(log_msg)

    provider_config = ai_config.get(final_provider, {})
    if not provider_config:
        raise ValueError(f"provider {final_provider} 的配置为空，请检查 config.yaml")

    _instance = BaseAIService(
        api_key=(provider_config.get("api_key") or "").strip(),
        model=final_model,
        api_base=(provider_config.get("api_base") or "https://api.openai.com/v1").strip(),
        provider=final_provider,
        timeout=provider_config.get("timeout", 30),
        max_tokens=provider_config.get("max_tokens", 4096),
        temperature=float(provider_config.get("temperature", 0.7)),
        seed=provider_config.get("seed", None),
    )

    return _instance
