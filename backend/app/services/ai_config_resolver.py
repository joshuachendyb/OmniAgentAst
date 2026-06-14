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
    
    def _extract_provider_model(self, ai_config: Dict[str, Any]) -> Tuple[str, str]:
        """提取provider和model - 小沈 2026-06-08"""
        provider = ai_config.get("provider", "")
        model = ai_config.get("model", "")
        return provider, model
    
    def _validate_provider_model_not_empty(self, provider: str, model: str) -> None:
        """验证provider和model不为空 - 小沈 2026-06-08"""
        if not provider or not model:
            raise ValueError(f"AI配置缺少provider或model: provider={provider}, model={model}")
    
    def _validate_provider_exists(self, ai_config: Dict[str, Any], provider: str) -> None:
        """验证provider存在 - 小沈 2026-06-08"""
        if provider not in ai_config:
            raise ValueError(f"配置文件中不存在 provider: {provider}")
    
    def _get_provider_config(self, ai_config: Dict[str, Any], provider: str) -> Dict[str, Any]:
        """获取provider配置 - 小沈 2026-06-08"""
        provider_config = ai_config[provider]
        if not isinstance(provider_config, dict):
            raise ValueError(f"provider {provider} 配置格式错误")
        return provider_config
    
    def _validate_model_in_list(self, provider_config: Dict[str, Any], provider: str, model: str) -> None:
        """验证model在列表中 - 小沈 2026-06-08"""
        models = provider_config.get("models", [])
        if model not in models:
            raise ValueError(f"model {model} 不在 provider {provider} 的 models 列表中")
    
    def resolve_provider_model(self) -> Tuple[str, str]:
        """直接读配置的provider和model,无效就报错"""
        ai_config = self.get_ai_config()
        provider, model = self._extract_provider_model(ai_config)
        
        self._validate_provider_model_not_empty(provider, model)
        self._validate_provider_exists(ai_config, provider)
        provider_config = self._get_provider_config(ai_config, provider)
        self._validate_model_in_list(provider_config, provider, model)
        
        return provider, model
    
    def get_service_config(self, provider: str, model: str) -> Dict[str, Any]:
        ai_config = self.get_ai_config()
        if provider not in ai_config:
            raise ValueError(f"配置文件中不存在 provider: {provider}")
        return ai_config[provider]

    def validate_config(self) -> tuple:
        """验证AI配置有效性 — 完全复用已有方法
        Returns:
            (is_valid, provider, model, error_messages)
        """
        ai_config = self.get_ai_config()
        provider, model = self._extract_provider_model(ai_config)
        errors = []
        try:
            self._validate_provider_model_not_empty(provider, model)
            self._validate_provider_exists(ai_config, provider)
            provider_config = self._get_provider_config(ai_config, provider)
            self._validate_model_in_list(provider_config, provider, model)
        except ValueError as e:
            errors.append(str(e))
        return (len(errors) == 0, provider or "unknown", model or "", errors)


_global_resolver: Optional[AIConfigResolver] = None


def get_ai_config_resolver() -> AIConfigResolver:
    global _global_resolver
    if _global_resolver is None:
        _global_resolver = AIConfigResolver()
    return _global_resolver
