"""
AI配置解析器 — 直接读配置,无效就报错

Author: 小沈 - 2026-06-07
"""

from typing import Dict, Any, Tuple, Optional
from app.config import Config, get_config


class AIConfigResolver:
    
    def __init__(self, config: Optional[Config] = None):
        self._config = config or get_config()
    
    def get_ai_config(self) -> Dict[str, Any]:
        return self._config.get("ai", {})
    
    def resolve_provider_model(self) -> Tuple[str, str]:
        """直接读配置的provider和model,无效就报错"""
        ai_config = self.get_ai_config()
        provider = ai_config.get("provider", "")
        model = ai_config.get("model", "")
        if not provider or not model:
            raise ValueError(f"AI配置缺少provider或model: provider={provider}, model={model}")
        if provider not in ai_config:
            raise ValueError(f"配置文件中不存在 provider: {provider}")
        provider_config = ai_config[provider]
        if not isinstance(provider_config, dict):
            raise ValueError(f"provider {provider} 配置格式错误")
        models = provider_config.get("models", [])
        if model not in models:
            raise ValueError(f"model {model} 不在 provider {provider} 的 models 列表中")
        return provider, model
    
    def get_service_config(self, provider: str, model: str) -> Dict[str, Any]:
        ai_config = self.get_ai_config()
        if provider not in ai_config:
            raise ValueError(f"配置文件中不存在 provider: {provider}")
        return ai_config[provider]


_global_resolver: Optional[AIConfigResolver] = None


def get_ai_config_resolver() -> AIConfigResolver:
    global _global_resolver
    if _global_resolver is None:
        _global_resolver = AIConfigResolver()
    return _global_resolver
