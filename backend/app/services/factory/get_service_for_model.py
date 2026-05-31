# -*- coding: utf-8 -*-
"""
get_service_for_model — 从 factory.py 拷出

拷贝来源: factory.py 第264-323行
"""

from datetime import datetime
from typing import Optional

from app.utils.logger import setup_logger
from app.services.llm_core import BaseAIService
from app.services.factory.close_instance_sync import close_instance_sync

logger = setup_logger("OmniAgentAst.AIServiceFactory")


def get_service_for_model(provider: str, model: str, config_path: Optional[str] = None):
    """拷贝自 factory.py 第264-323行"""
    import app.services.factory.get_service as gs

    from app.services.ai_config_resolver import get_ai_config_resolver
    resolver = get_ai_config_resolver()
    ai_config = resolver.get_ai_config()

    try:
        provider_config = resolver.get_service_config(provider, model)
    except ValueError as e:
        raise ValueError(str(e))

    old_instance = gs._instance
    gs._instance = None
    gs._current_provider = provider
    close_instance_sync(old_instance)

    log_msg = f"[AIServiceFactory] 创建服务实例: provider={provider}, model={model}"
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {log_msg}")
    logger.info(log_msg)

    if not provider_config:
        provider_config = {}

    gs._instance = BaseAIService(
        api_key=(provider_config.get("api_key") or "").strip(),
        model=model,
        api_base=(provider_config.get("api_base") or "https://api.openai.com/v1").strip(),
        provider=provider,
        timeout=provider_config.get("timeout", 30),
        max_tokens=provider_config.get("max_tokens", 4096),
        temperature=float(provider_config.get("temperature", 0.7)),
        seed=provider_config.get("seed", None),
    )

    return gs._instance
